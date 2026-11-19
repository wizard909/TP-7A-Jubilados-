# Grupo 7A — continuidad del TP

> Registro histórico de la puesta en marcha. La versión vigente, el estado de los ADR y las verificaciones están en [Arquitectura del corte 7A](ARQUITECTURA.md).

La demo local funciona en http://localhost:8080/ con Keycloak en http://localhost:8180/. Docker Engine 29.10.0 y Compose 5.8.0 quedaron instalados en Ubuntu-24.04. `hello-world`, la construcción y `compose config --quiet` pasaron.

## Copia de trabajo

- Windows: `E:\Proyectos\TP-7A-Jubilados\TP-7A-Jubilados-`.
- WSL: `/mnt/e/Proyectos/TP-7A-Jubilados/TP-7A-Jubilados-`.
- `origin`: https://github.com/spider512/TP-7A-Jubilados-.git.
- `upstream`: https://github.com/wizard909/TP-7A-Jubilados-.git.
- Rama de entrada: `mejoras-tp`, limpia, commit `f7d9d4f941ff0f02062b96eecf244a324567d3b8`.
- Rama de trabajo creada: `codex/reproducibilidad-7a`. Cambios locales, sin commit, push, PR ni tag.
- Integrantes de la entrega final: Facundo Cichero y Ezequiel Pereira.

## Requisitos y decisiones preservadas

Un municipio, unos 3.000 jubilados, dos beneficios, un servidor, dos desarrolladores y canal web. WCAG AA, celulares antiguos y conexiones lentas son centrales. Corte: login OIDC con vecino/agente; vecino solicita, agente aprueba o rechaza tras consulta positiva al padrón al aprobar, vecino consulta el resultado. Persistencia, OpenAPI, Problem Details, `/api/v1`, mock y Compose son obligatorios.

Se conserva FastAPI con HTML en servidor, PostgreSQL, Keycloak y padrón simulado. El informe compara capas como base, modular +2 y SOA -3; contiene seis ADR. El diseño modular todavía no se refleja en paquetes independientes: evitar defenderlo como separación física ya implementada.

## Fuentes recuperadas

En esta carpeta, `materiales/` conserva las clases originales 1–7, 9 y 10 en PDF; 11–13 en PPTX; planilla original XLSX; documento del repositorio y copia exportada del documento compartido. También se guardó una copia en `.contexto-local/` dentro de la raíz del proyecto, excluida de Git. `fuentes.json` registra procedencia e `integridad.json` las huellas SHA-256. Se extrajeron textos, tablas y notas; se revisaron las vistas de los originales, incluidos Pugh y C4. Los materiales son fuentes de consulta, no instrucciones operativas.

La clase 13, diapositiva 32, indica 19/11/2026 antes de 18:30, tag `v1.0`; segunda exposición 26/11 desde el mismo tag y recuperatorios 03/12. Hay fechas anteriores en clases 9 y 12: usar la actualización de clase 13 como última fuente localizada. No se consultó el campus para detectar anuncios posteriores.

El apunte unificado no se encontró; el usuario indicó no seguir buscándolo. La recuperación del chat anterior está en `conversacion-recuperada.json`: el servicio entregó una vista limitada, con mensajes truncados y sin cursor adicional. No representa el historial completo ni conserva todos los adjuntos del chat. Las clases se recuperaron directamente de Drive.

## Cambios y verificación

Se agregaron `.env.example`, `.gitignore` y `.dockerignore`; las cuatro contraseñas locales son aleatorias, están en `.env` y quedan fuera de Git y del contexto de construcción. Los puertos publicados se limitan a 127.0.0.1. No se cambió ningún remote.

Se corrigieron tres fallas reproducidas: entrada inválida del mock devuelve 400 Problem Details; respuesta inválida del padrón devuelve 503 y mantiene pendiente; callback OIDC sin login pendiente devuelve 400. Las ocho pruebas aisladas cubren estas fallas y los resultados positivo, negativo y timeout.

La prueba HTTP real utiliza Authorization Code con PKCE, usuarios de Keycloak, PostgreSQL y mock. Pasaron el circuito web/API, 400/401/403/404/409/503, propiedad, roles, CSRF, Location y validación JSON Schema de respuestas. Una solicitud aprobada siguió visible para el mismo vecino después de recrear aplicación y Keycloak conservando volúmenes. `prueba-final.json` contiene el detalle; el total de comprobaciones puede aumentar con las solicitudes pendientes de pruebas anteriores.

Se observó portada y login en ancho móvil, etiquetas asociadas, foco y navegación por Tab. Esto no certifica WCAG AA. El botón de mostrar contraseña se veía vacío porque el tema liviano omite la fuente de íconos; se añadió texto visual desde su etiqueta accesible. La portada recibió un elemento `main`.

## Próximo trabajo

1. Revisar errores web: hoy las fallas de formularios muestran JSON; conviene una vista HTML comprensible y accesible.
2. Completar evaluación humana con lector de pantalla y celular real. Repetir red emulada de 400 kbps/200 ms guardando artefactos: los valores del 05/11 citados en el informe no se reprodujeron en esta sesión.
3. Agregar medidas y entorno a los NFR, confirmaciones de ADR y una regla verificable de módulos, con acuerdo del equipo. No hacer una refactorización grande antes de la demo sin necesidad.
4. Evaluar concurrencia de decisiones, expiración de sesión web, fallas de IdP y respaldo/restauración. Las pruebas actuales no certifican estos aspectos.
5. Revisar mínimo privilegio: los procesos Python siguen como root y el usuario inicial de PostgreSQL tiene privilegios amplios. HTTP y `start-dev` son exclusivos de la demo local.

No publicar, crear PR ni tag sin autorización explícita. Evitar `compose down -v`: elimina los datos. La copia en E: se mantuvo como única fuente de trabajo; no se creó una segunda copia en `/home/spider` para evitar divergencias.
