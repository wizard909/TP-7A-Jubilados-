# TP de arquitectura 7A: beneficios municipales

Prototipo local del recorrido mínimo del escenario 7A. El padrón nacional se representa con un mock; la aplicación, Keycloak y PostgreSQL se ejecutan como servicios reales de la demo.

## Arranque

1. Instalar y abrir Docker Desktop.
2. Copiar `.env.example` como `.env` y reemplazar las cuatro claves de ejemplo. No subir `.env` al repositorio.
3. Desde esta carpeta, ejecutar `docker compose up -d --build`.
4. Abrir <http://localhost:8080/>. Keycloak puede tardar unos segundos más que la aplicación; si el primer login falla durante el arranque, esperar a que `docker compose logs keycloak` muestre `started`.

Servicios: aplicación `localhost:8080`, Keycloak `localhost:8180`, PostgreSQL y padrón solo en la red interna de Compose. El archivo `../outputs/openapi.yaml` describe la API municipal y `../outputs/padron-mock-openapi.yaml` el contrato esperado del mock.

## Mostrar en la tablet por Tailscale

Con esta PC prendida, Docker Desktop abierto y Tailscale activo en ambos dispositivos, se puede abrir <http://100.71.189.82:8080/> en el navegador de la tablet. No hay que exportar ni instalar una app en Android. Mientras esté habilitado Funnel, el login continúa por la dirección pública HTTPS indicada abajo.

## Compartir con compañeros desde otra red

La demo está publicada temporalmente mediante Tailscale Funnel en <https://desktop-ct73bo3.taila837d6.ts.net:8443/>. Los visitantes no necesitan Tailscale. Funnel recibe HTTPS público y lo reenvía a la aplicación y al login que siguen corriendo en esta PC; no aloja ni copia el proyecto. La PC, Docker Desktop, Tailscale y los cuatro contenedores deben permanecer encendidos. La configuración de la aplicación y Keycloak usa las direcciones `APP_PUBLIC_URL` y `KEYCLOAK_PUBLIC_URL` del `.env` local. Para apagar la publicación sin afectar los contenedores, ejecutar `tailscale funnel --https=8443 off` y `tailscale funnel --https=10000 off`. El servicio preexistente en el puerto 443 permanece privado en la tailnet.

## Usuarios de prueba

La contraseña de los cuatro usuarios es `TEST_PASSWORD` del `.env` local.

| Usuario | Rol | Respuesta del padrón |
| --- | --- | --- |
| `vecino1` | vecino | jubilado, permite aprobar |
| `vecino2` | vecino | no registrado, impide aprobar |
| `vecino3` | vecino | mock no disponible, deja pendiente |
| `agente1` | agente | revisa y decide |

Para una demo: entrar como `vecino1`, presentar tarifa social, salir; entrar como `agente1`, abrir la pendiente y aprobar con un motivo; salir y volver como `vecino1` para ver el resultado. Repetir con `vecino2` o `vecino3` para mostrar las otras respuestas. Para mostrar el rechazo, el agente puede rechazar directamente una solicitud pendiente con un motivo.

## Qué está probado y qué falta

Se levantaron los cuatro servicios con Compose y se comprobó por HTTP el login de ambos roles, la creación, aprobación, consulta del resultado, bloqueo de solicitud ajena y los estados 401, 403, 409 y 503. Tras recrear la aplicación y Keycloak, el mismo vecino volvió a consultar una solicitud aprobada: PostgreSQL conservó el trámite y Keycloak la identidad. Una comprobación automática con axe-core en ancho móvil de 360 px no encontró infracciones WCAG A/AA ni desbordamiento horizontal en portada, login, inicio del vecino y resultado. Un recorrido automatizado con Tab y Enter alcanzó ingreso, selector, botón y resultado con foco visible.

En Chrome a 360 px, con red simulada de 400 kbps y 200 ms de latencia, la portada cargó en 0,27 s; el login, en 1,11 s; el inicio del vecino, en 0,84 s; y el resultado, en 0,38 s. El login original descargaba 1.907.888 bytes y demoró 41,27 s en la misma emulación. Un tema propio heredado del tema base de Keycloak redujo esa descarga a 17.661 bytes y puso el ingreso en español. Es una medición local, no una promesa de rendimiento para todos los dispositivos.

Una prueba local contrastó las operaciones del caso mínimo con `openapi.yaml`: tokens OIDC de ambos roles, respuestas validadas con JSON Schema, cabecera `Location` y errores 400, 401, 403, 404 y 409. La falla 503 del mock se comprobó en el recorrido funcional. Es cobertura del recorrido mostrado, no de todas las combinaciones posibles.

Faltan la revisión humana con celular y lector de pantalla y una revisión de seguridad antes de cualquier uso fuera de la demo. Las comprobaciones automáticas no certifican WCAG AA.

El realm de Keycloak se importa la primera vez y su estado de prueba se conserva en el volumen `kcdata`. Si se cambia el archivo del realm con un volumen existente, la importación no lo sobrescribe: el script `apply_realm_settings.py` aplica el idioma y el tema a ese volumen con Keycloak levantado. No usar las claves de prueba fuera de este entorno.
