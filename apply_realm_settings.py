"""Apply the demo realm's locale and login theme to an existing Keycloak volume."""

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parent
env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
base = 'http://localhost:8180'


def request(method, url, data=None, token=None, content_type='application/json'):
    headers = {'Content-Type': content_type}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = data if isinstance(data, bytes) or data is None else json.dumps(data).encode()
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=20) as response:
        payload = response.read()
        return json.loads(payload) if payload else None


credentials = urlencode({
    'grant_type': 'password', 'client_id': 'admin-cli',
    'username': 'admin', 'password': env['KEYCLOAK_ADMIN_PASSWORD'],
}).encode()
auth = request('POST', f'{base}/realms/master/protocol/openid-connect/token', credentials,
               content_type='application/x-www-form-urlencoded')
token = auth['access_token']
realm = request('GET', f'{base}/admin/realms/municipio', token=token)
realm.update({
    'internationalizationEnabled': True,
    'supportedLocales': ['es'],
    'defaultLocale': 'es',
    'loginTheme': 'municipio',
})
request('PUT', f'{base}/admin/realms/municipio', realm, token=token)
confirmed = request('GET', f'{base}/admin/realms/municipio', token=token)
for key in ('internationalizationEnabled', 'supportedLocales', 'defaultLocale', 'loginTheme'):
    assert confirmed[key] == realm[key], key

demo_host = env.get('DEMO_HOST', 'localhost')
app_public_url = env.get('APP_PUBLIC_URL', f'http://{demo_host}:8080').rstrip('/')
client = next(c for c in request('GET', f'{base}/admin/realms/municipio/clients?clientId=municipio-web', token=token)
              if c['clientId'] == 'municipio-web')
client['redirectUris'] = list(dict.fromkeys(client.get('redirectUris', []) + [
    'http://localhost:8080/auth/callback', f'http://{demo_host}:8080/auth/callback',
    f'{app_public_url}/auth/callback',
]))
client['webOrigins'] = list(dict.fromkeys(client.get('webOrigins', []) + [
    'http://localhost:8080', f'http://{demo_host}:8080', app_public_url,
]))
request('PUT', f"{base}/admin/realms/municipio/clients/{client['id']}", client, token=token)
print('Realm municipio: idioma, tema y dirección de demo aplicados.')
