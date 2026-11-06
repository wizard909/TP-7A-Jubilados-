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

En el paquete completo, junto a esta carpeta, están:

- [`outputs/openapi.yaml`](../outputs/openapi.yaml): contrato de la API municipal.
- [`outputs/padron-mock-openapi.yaml`](../outputs/padron-mock-openapi.yaml): contrato del padrón simulado.
- [`outputs/TP_Arquitectura_Jubilados.docx`](../outputs/TP_Arquitectura_Jubilados.docx): decisiones de arquitectura, diagramas, ADR y evidencia de verificación.

La API usa el prefijo `/api/v1`. Las páginas web y la API forman parte de la misma aplicación. El documento explica la correspondencia entre estos servicios, el C4 de Contenedores y las decisiones tomadas.

## Alcance de la implementación

El padrón y sus respuestas son ficticios; los usuarios de Keycloak también son de prueba. Las solicitudes creadas durante la ejecución sí se persisten en PostgreSQL. El proyecto demuestra el caso de uso elegido y no es un sistema municipal en producción. Las comprobaciones automáticas de accesibilidad y rendimiento registradas en el documento no equivalen a una certificación WCAG AA ni a mediciones en dispositivos reales.
