"""Prueba real de la demo: OIDC Authorization Code+PKCE, web, API y permisos.

Ejecutar desde Windows o WSL con Python 3.10+. Crea solicitudes ficticias
identificadas por sus motivos; nunca imprime contraseñas, códigos ni tokens.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import base64
import hashlib
import http.cookiejar
from html.parser import HTMLParser
import json
import pathlib
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoopbackCookiePolicy(http.cookiejar.DefaultCookiePolicy):
    """Iguala el tratamiento de localhost como contexto confiable del navegador."""
    def return_ok_secure(self, cookie, request):
        if urllib.parse.urlparse(request.full_url).hostname in {'localhost', '127.0.0.1', '::1'}:
            return True
        return super().return_ok_secure(cookie, request)


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'action': attrs.get('action', ''), 'fields': {}}
            self.forms.append(self.current)
        if tag == 'input' and self.current is not None and attrs.get('name'):
            self.current['fields'][attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar(policy=LoopbackCookiePolicy())), NoRedirect())

    def request(self, method, url, *, form=None, body=None, token=None):
        headers = {}
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        if token:
            headers['Authorization'] = 'Bearer ' + token
        target = urllib.parse.urlparse(url)
        if target.hostname == 'localhost':
            # Evita demoras de fallback IPv6 en WSL y conserva el Host publico OIDC.
            headers['Host'] = target.netloc
            url = target._replace(netloc='127.0.0.1:' + str(target.port or 80)).geturl()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        start = time.perf_counter()
        try:
            response = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            return {'status': response.status, 'headers': response.headers,
                    'text': raw.decode('utf8'), 'bytes': len(raw),
                    'seconds': round(time.perf_counter() - start, 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', default='http://localhost:8080')
    parser.add_argument('--keycloak', default='http://localhost:8180')
    parser.add_argument('--env', default='.env')
    parser.add_argument('--output', default='smoke-result.json')
    parser.add_argument('--persisted-id', help='Verifica una solicitud de una ejecucion anterior')
    parser.add_argument('--contracts', help='Directorio con ambos contratos YAML; requiere requirements-test.txt')
    args = parser.parse_args()
    env = dict(line.strip().split('=', 1) for line in pathlib.Path(args.env).read_text().splitlines()
               if line.strip() and not line.lstrip().startswith('#') and '=' in line)
    password = env['TEST_PASSWORD']
    app, kc = args.app.rstrip('/'), args.keycloak.rstrip('/') + '/realms/municipio'
    results = []
    ids = {}
    contract = None
    if args.contracts:
        import yaml
        from jsonschema import Draft202012Validator, FormatChecker
        contract = yaml.safe_load((pathlib.Path(args.contracts)/'openapi.yaml').read_text(encoding='utf8'))

    def check(name, ok, detail=None):
        results.append({'check': name, 'passed': bool(ok), **({'detail': detail} if detail is not None else {})})
        print(('PASS ' if ok else 'FAIL ') + name)

    def status(name, response, expected):
        check(name, response['status'] == expected, {'expected': expected, 'actual': response['status']})
        if expected >= 400:
            check(name + ': Problem Details',
                  response['headers'].get('Content-Type', '').startswith('application/problem+json')
                  and json.loads(response['text']).get('status') == expected)
            schema(name, response, 'Problem')

    def schema(name, response, schema_name):
        if contract:
            schema = {**contract['components']['schemas'][schema_name], 'components': contract['components']}
            errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(json.loads(response['text'])))
            check(name + ': esquema ' + schema_name, not errors,
                  [e.message for e in errors])

    def login_form(client, response, user):
        status('Formulario OIDC ' + user, response, 200)
        forms = Forms(response['text']).forms
        form = next(f for f in forms if 'username' in f['fields'])
        data = {**form['fields'], 'username': user, 'password': password, 'credentialId': ''}
        r = client.request('POST', form['action'], form=data)
        status('Credenciales OIDC ' + user, r, 302)
        return r['headers']['Location']

    def web_login(user):
        client = Client()
        r = client.request('GET', app + '/login')
        status('Inicio login web ' + user, r, 307)
        r = client.request('GET', r['headers']['Location'])
        target = login_form(client, r, user)
        r = client.request('GET', target)
        status('Callback PKCE web ' + user, r, 303)
        r = client.request('GET', app + '/')
        check('Sesion web ' + user, r['status'] == 200 and ('Sesión de ' + user) in r['text'])
        return client, r

    def token(user):
        client = Client()
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        state = secrets.token_urlsafe(24)
        params = {'client_id':'municipio-web', 'redirect_uri':app+'/auth/callback',
                  'response_type':'code', 'scope':'openid profile', 'state':state,
                  'code_challenge':challenge, 'code_challenge_method':'S256', 'prompt':'login'}
        r = client.request('GET', kc + '/protocol/openid-connect/auth?' + urllib.parse.urlencode(params))
        target = login_form(client, r, user)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
        check('Estado OIDC API ' + user, query.get('state') == [state])
        r = client.request('POST', kc + '/protocol/openid-connect/token', form={
            'grant_type':'authorization_code', 'client_id':'municipio-web',
            'redirect_uri':app+'/auth/callback', 'code':query['code'][0], 'code_verifier':verifier})
        status('Token PKCE ' + user, r, 200)
        return json.loads(r['text'])['access_token']

    public = Client()
    try:
        r = public.request('GET', app + '/')
        status('Portada', r, 200)
        r = public.request('GET', app + '/api/v1/beneficios')
        check('Dos beneficios publicos', r['status'] == 200 and len(json.loads(r['text'])) == 2)
        for item in json.loads(r['text']):
            schema('Catalogo', {'text':json.dumps(item)}, 'Beneficio')
        status('Sin token', public.request('POST', app + '/api/v1/solicitudes', body={'beneficioId':'tarifa-social'}),401)
        status('Token invalido', public.request('GET', app + '/api/v1/solicitudes?estado=pendiente', token='invalid'),401)
        tokens = {u:token(u) for u in ('vecino1','agente1','vecino2','vecino3')}
        def api(method, path, user='vecino1', body=None):
            return public.request(method, app + path, body=body, token=tokens[user])
        status('Agente no crea', api('POST','/api/v1/solicitudes','agente1',{'beneficioId':'tarifa-social'}),403)
        status('Vecino no lista pendientes',api('GET','/api/v1/solicitudes?estado=pendiente'),403)
        status('Beneficio invalido',api('POST','/api/v1/solicitudes',body={'beneficioId':'inexistente'}),400)
        status('No acepta identidad enviada',api('POST','/api/v1/solicitudes',body={'beneficioId':'tarifa-social','solicitanteId':'otro'}),400)
        status('Solicitud inexistente',api('GET','/api/v1/solicitudes/00000000-0000-0000-0000-000000000000'),404)
        status('Filtro invalido',api('GET','/api/v1/solicitudes?estado=aprobada','agente1'),400)
        for user in ('vecino1','vecino2','vecino3'):
            r = api('POST','/api/v1/solicitudes',user,{'beneficioId':'tarifa-social'})
            status('Crear ' + user,r,201)
            schema('Crear ' + user,r,'Solicitud')
            item = json.loads(r['text']); ids[user]=item['id']
            check('Location ' + user,r['headers'].get('Location') == '/api/v1/solicitudes/'+item['id'])
            check('Estado inicial ' + user,item['estado']=='pendiente')
        r=api('GET','/api/v1/solicitudes?estado=pendiente','agente1')
        status('Agente lista pendientes',r,200)
        for item in json.loads(r['text']):
            schema('Listado pendiente',{'text':json.dumps(item)},'Solicitud')
        path='/api/v1/solicitudes/'+ids['vecino1']
        status('Solicitud ajena',api('GET',path,'vecino2'),403)
        status('Vecino no decide',api('PATCH',path,body={'estado':'aprobada','motivo':'Prueba automatizada'}),403)
        status('Decision sin motivo',api('PATCH',path,'agente1',{'estado':'aprobada','motivo':' '}),400)
        r=api('PATCH',path,'agente1',{'estado':'aprobada','motivo':'Prueba automatizada: padron positivo'})
        status('Aprobacion positiva',r,200);schema('Aprobacion',r,'Solicitud')
        r=api('GET',path)
        schema('Consulta del vecino',r,'Solicitud')
        check('Vecino consulta aprobacion',json.loads(r['text'])['estado']=='aprobada')
        status('No decide dos veces',api('PATCH',path,'agente1',{'estado':'rechazada','motivo':'Intento repetido'}),409)
        race = api('POST', '/api/v1/solicitudes', body={'beneficioId':'tarifa-social'})
        status('Crear solicitud para concurrencia', race, 201)
        race_path = race['headers']['Location']
        barrier = Barrier(2, timeout=10)

        def concurrent_decision(state):
            barrier.wait()
            return Client().request('PATCH', app + race_path, token=tokens['agente1'],
                                    body={'estado':state, 'motivo':'Concurrencia: ' + state})

        with ThreadPoolExecutor(max_workers=2) as pool:
            decisions = list(pool.map(concurrent_decision, ('aprobada', 'rechazada')))
        check('PostgreSQL admite una sola decisión concurrente', sorted(r['status'] for r in decisions) == [200, 409])
        if sorted(r['status'] for r in decisions) == [200, 409]:
            winner = next(r for r in decisions if r['status'] == 200)
            loser = next(r for r in decisions if r['status'] == 409)
            status('Conflicto concurrente', loser, 409)
            final = api('GET', race_path)
            check('Decisión concurrente ganadora persistida', final['status'] == 200 and
                  json.loads(final['text']) == json.loads(winner['text']))
        for user,expected in [('vecino2',409),('vecino3',503)]:
            path2='/api/v1/solicitudes/'+ids[user]
            status('Padron '+user,api('PATCH',path2,'agente1',{'estado':'aprobada','motivo':'Prueba automatizada'}),expected)
            check('Sigue pendiente '+user,json.loads(api('GET',path2,user)['text'])['estado']=='pendiente')
        r=api('PATCH','/api/v1/solicitudes/'+ids['vecino2'],'agente1',{'estado':'rechazada','motivo':'Prueba automatizada: no registrado'})
        status('Rechazo con motivo',r,200)
        check('Vecino consulta rechazo',json.loads(api('GET','/api/v1/solicitudes/'+ids['vecino2'],'vecino2')['text'])['estado']=='rechazada')
        neighbour,home=web_login('vecino1')
        csrf=next(f['fields']['csrf'] for f in Forms(home['text']).forms if 'csrf' in f['fields'])
        status('CSRF invalido',neighbour.request('POST',app+'/web/solicitudes',form={'beneficio':'tarifa-social','csrf':'invalido'}),403)
        r=neighbour.request('POST',app+'/web/solicitudes',form={'beneficio':'descuento-transporte','csrf':csrf})
        status('Formulario crea solicitud',r,303)
        webpath=r['headers']['Location']; ids['web']=webpath.rsplit('/',1)[-1]
        agent,_=web_login('agente1')
        r=agent.request('GET',app+webpath)
        csrf=next(f['fields']['csrf'] for f in Forms(r['text']).forms if 'csrf' in f['fields'])
        status('Formulario agente aprueba',agent.request('POST',app+webpath+'/decision',form={'estado':'aprobada','motivo':'Prueba automatizada por formularios','csrf':csrf}),303)
        r=neighbour.request('GET',app+webpath)
        check('Vecino ve resultado web',r['status']==200 and 'data-estado="aprobada">Aprobada</strong>' in r['text'])
        check('Peso HTML de resultado',r['bytes']<100_000,{'bytes':r['bytes'],'nota':'HTML solamente; sin red emulada'})
        if args.persisted_id:
            r=api('GET','/api/v1/solicitudes/'+args.persisted_id)
            check('Persistencia e identidad tras recrear',r['status']==200 and json.loads(r['text'])['estado']=='aprobada')
    except Exception as exc:
        check('Ejecucion completa',False,{'exception':type(exc).__name__})
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'app':app,
            'scope':'HTTP real con OIDC PKCE, PostgreSQL y mock; no auditoria WCAG ni prueba de carga',
            'requests_created':ids,'passed':sum(r['passed'] for r in results),
            'failed':sum(not r['passed'] for r in results),'checks':results}
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print(f"Resultado: {report['passed']} verificaciones correctas; {report['failed']} fallidas")
    return bool(report['failed'])


if __name__ == '__main__':
    raise SystemExit(main())
