# Prueba del portal con teclado y axe

Con la demo activa y Node.js disponible, ejecutá estos comandos desde esta carpeta.

```sh
npm ci
npx playwright install chromium
npm test
```

La prueba usa el `TEST_PASSWORD` de `.env`. Crea solicitudes ficticias para recorrer aprobación, rechazo, resultado y error de padrón. Comprueba ingreso por Keycloak, ancho móvil efectivo, foco, nombres accesibles, errores y el enlace de salto. Corre con Chromium en escritorio, 360 px y 320 px. Axe comprueba las reglas aplicables WCAG A y AA de 2.0, 2.1 y 2.2 y las buenas prácticas activadas.

Podés definir `A11Y_REPORT` con una ruta de salida JSON y `A11Y_CHROME` con la ruta a otro ejecutable de Chromium. Para observar la corrida de escritorio con un lector de pantalla, iniciá el lector antes y definí `A11Y_HEADED=1`. El informe omite credenciales y tokens.


## Red móvil emulada

Desde esta carpeta, con la misma demo y dependencias instaladas, ejecutá `node red-movil.mjs`. El escenario mide portada, login, inicio del vecino y alta en tres corridas con Chrome a 360 px, caché deshabilitada, 400 kbps en ambos sentidos y 200 ms de latencia. Crea tres solicitudes ficticias. Podés indicar `NETWORK_REPORT` para guardar el JSON en un archivo local. La prueba mide condiciones de laboratorio y se complementa con una evaluación en dispositivos reales.
