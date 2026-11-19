# Beneficios municipales para jubilados

Implementación del recorrido mínimo del escenario 7A de Arquitectura de Software. Un vecino autenticado presenta una solicitud de beneficio, un agente municipal la decide y el vecino consulta el resultado. Para aprobar, la aplicación consulta un padrón nacional simulado. La solicitud y su decisión se guardan en PostgreSQL.

## Qué incluye

| Componente | Función |
| --- | --- |
| Aplicación Python/FastAPI | Sirve las páginas web, la API y las reglas del recorrido. |
| PostgreSQL | Guarda solicitudes y decisiones en un volumen de Docker. |
| Keycloak | Autentica a los usuarios de prueba mediante OIDC y les asigna los roles `vecino` y `agente`. |
| Padrón simulado | Responde a la verificación de la condición de jubilado o pensionado. No consulta un padrón real. |

El catálogo de dos beneficios está definido en el código; la vinculación entre usuarios de prueba e identificadores del padrón, en `compose.yaml`. No hay un formulario de datos personales: la aplicación obtiene la identidad de la sesión iniciada en Keycloak.

## Levantar el entorno local

Se necesita Docker con Compose. Los puertos `8080` y `8180` deben estar libres.

1. En esta carpeta, copiar `.env.example` como `.env`.
2. Reemplazar los cuatro valores de ejemplo: `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`, `SESSION_SECRET` y `TEST_PASSWORD`. `TEST_PASSWORD` será la contraseña de los cuatro usuarios de prueba.
3. Ejecutar:

   ```sh
   docker compose up -d --build
   ```

4. Abrir <http://localhost:8080/>. Keycloak puede tardar un poco más en iniciar. El estado de los servicios se consulta con `docker compose ps`; los mensajes de Keycloak, con `docker compose logs keycloak`.

La aplicación se publica en `localhost:8080` y Keycloak en `localhost:8180`. PostgreSQL y el padrón solo son accesibles dentro de la red de Compose. Para detener los servicios sin borrar los datos, ejecutar `docker compose down`.

**Importante:** Keycloak importa los usuarios al crear su volumen por primera vez. Cambiar `TEST_PASSWORD` en `.env` después de ese primer arranque no modifica las contraseñas de usuarios ya importados. Las solicitudes también permanecen en el volumen de PostgreSQL después de `docker compose down`.

Si ya tenés un volumen de Keycloak de una versión anterior, ejecutá una vez `python apply_realm_settings.py` desde la raíz del proyecto con Keycloak arriba. Así se habilita el retorno al portal al cerrar sesión. La actualización conserva usuarios, contraseñas y solicitudes.

## Usuarios y recorrido de prueba

| Usuario | Rol | Respuesta del padrón simulado |
| --- | --- | --- |
| `vecino1` | Vecino | Jubilado: se puede aprobar. |
| `vecino2` | Vecino | No registrado: no se puede aprobar. |
| `vecino3` | Vecino | Servicio no disponible: la solicitud queda pendiente. |
| `agente1` | Agente | Revisa y decide solicitudes. |

Todos usan la contraseña `TEST_PASSWORD` configurada en `.env` antes del primer arranque.

Para comprobar el recorrido principal:

1. Iniciar sesión como `vecino1`, elegir un beneficio y presentar la solicitud. Queda **pendiente**.
2. Salir, entrar como `agente1`, abrir la solicitud pendiente, escribir un motivo y aprobarla. En ese momento se consulta el padrón simulado.
3. Salir y volver como `vecino1`. La solicitud muestra **aprobada** y conserva el motivo.

Como comprobaciones adicionales, una solicitud de `vecino2` no se puede aprobar porque el padrón responde `no_registrado`; con `vecino3`, el mock devuelve `503` y la solicitud sigue pendiente. El agente también puede rechazar directamente una solicitud pendiente e indicar un motivo.

## Contratos y documento

Los siguientes entregables están en el repositorio:

- [Informe de arquitectura del equipo](docs/TP_Arquitectura_Jubilados.docx)
- [Arquitectura implementada y verificaciones](docs/ARQUITECTURA.md)
- [Contrato de la API municipal](docs/openapi.yaml)
- [Contrato del padrón simulado](docs/padron-mock-openapi.yaml)

La API usa el prefijo `/api/v1`. Las páginas web y la API forman parte de la misma aplicación. El documento explica la correspondencia entre estos servicios, el C4 de Contenedores y las decisiones tomadas.

## Backend modular

`app/main.py` compone FastAPI. `app/web.py` renderiza la MPA y `app/api.py` expone el contrato REST. Ambas rutas usan los casos de uso de `app/solicitudes/servicio.py`. La entidad `Solicitud` y las reglas de aplicación funcionan sin FastAPI, SQLAlchemy ni HTTPX. El repositorio SQLAlchemy posee la escritura y el adaptador del padrón traduce su respuesta al resultado interno. PostgreSQL acepta una sola decisión por solicitud mediante un `UPDATE` condicionado por el estado pendiente.


## Alcance de la implementación

El padrón y sus respuestas son ficticios; los usuarios de Keycloak también son de prueba. Las solicitudes creadas durante la ejecución sí se persisten en PostgreSQL. El proyecto demuestra el caso de uso elegido y no es un sistema municipal en producción. Las comprobaciones automáticas de accesibilidad y rendimiento registradas en el documento no equivalen a una certificación WCAG AA ni a mediciones en dispositivos reales.

## Verificaciones reproducibles

Para trabajar en la copia Windows desde Ubuntu 24.04:

```sh
cd /mnt/e/Proyectos/TP-7A-Jubilados/TP-7A-Jubilados-
sudo docker compose up -d --build
```

Si tu usuario ya tiene acceso a Docker, se puede omitir `sudo`. En este equipo se instaló Docker Engine desde el repositorio oficial de Ubuntu; la instalación y `hello-world` pasaron.

Los servicios de esta demo HTTP con Keycloak `start-dev` solo se publican en `127.0.0.1`. No es una configuración para un servidor público. Las contraseñas quedan en `.env` y los cuatro usuarios de prueba usan `TEST_PASSWORD`; no compartir ese archivo ni subirlo a Git.

Las pruebas aisladas usan SQLite local para simular fallas y concurrencia. También controlan la dirección de los imports. La base de la demo queda separada:

```sh
sudo docker compose run --rm --no-deps \
  -v ./tests:/app/tests:ro -v ./mock:/app/mock:ro \
  -e DATABASE_URL=sqlite:// app \
  python -m unittest discover -s tests -p 'test_*.py' -v
```

Con Python 3.10 o superior, el recorrido real usa los cuatro usuarios, OIDC Authorization Code con PKCE, API y formularios. Crea solicitudes ficticias y deja un resultado JSON sin contraseñas ni tokens:

```sh
python3 tests/smoke_compose.py --env .env --output smoke-result.json
```

Para sumar validación JSON Schema contra los contratos, usar un entorno virtual con `requirements-test.txt` y agregar `--contracts docs`. La opción `--persisted-id ID` verifica además una solicitud aprobada de una ejecución anterior después de recrear los servicios conservando los volúmenes. Para repetir la prueba de persistencia, usá `requests_created.vecino1` del primer informe, recreá los servicios con `docker compose up -d --force-recreate` y ejecutá otra vez con `--persisted-id ID`. El recuento total puede variar por las solicitudes pendientes existentes.

El estado de continuidad está en [docs/CONTINUAR.md](docs/CONTINUAR.md). Las clases y fuentes locales quedan en `.contexto-local/`, fuera de Git. Las comprobaciones automáticas y la revisión visual no certifican WCAG AA; siguen pendientes lector de pantalla y celular real.

El [procedimiento de accesibilidad y red emulada](tests/accesibilidad/README.md) cubre escritorio, 360 y 320 px, teclado, Keycloak, cierre de sesión y cambio de cuenta. El informe distingue la evidencia automática del trabajo manual pendiente.
