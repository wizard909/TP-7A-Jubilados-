import { readFileSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const portal = 'http://localhost:8080';
const keycloak = 'http://localhost:8180';
const password = process.env.TEST_PASSWORD ?? readFileSync(new URL('../../.env', import.meta.url), 'utf8')
  .split(/\r?\n/).find(line => line.startsWith('TEST_PASSWORD='))?.slice('TEST_PASSWORD='.length);
assert(password);

async function measure(page, stage, navigate, readings) {
  const start = performance.now();
  await navigate();
  await page.waitForLoadState('load');
  await page.waitForFunction(() => performance.getEntriesByType('navigation')[0]?.loadEventEnd > 0);
  const observation = await page.evaluate(() => {
    const [nav] = performance.getEntriesByType('navigation');
    const resources = performance.getEntriesByType('resource').filter(asset => asset.name.startsWith('http'));
    const objects = [nav, ...resources];
    return {
      loadMs: Math.round(nav.loadEventEnd),
      bodyBytes: objects.reduce((bytes, item) => bytes + item.encodedBodySize, 0),
      displayedRequests: document.querySelectorAll('.request-card').length,
      origins: [...new Set(objects.map(item => new URL(item.name).origin))],
    };
  });
  assert(observation.origins.every(origin => origin === portal || origin === keycloak));
  readings.push({stage, ...observation, actionToLoadMs: Math.round(performance.now() - start)});
}

async function main() {
  const browser = await chromium.launch({executablePath:process.env.A11Y_CHROME || undefined,
    args:['--no-proxy-server']});
  const profile = {width:360, height:800, latencyMs:200, downloadKbps:400, uploadKbps:400,
    cache:'deshabilitada', samples:3, cpu:'sin limitación', browser:browser.version()};
  const trials = [];
  try {
    for (let i = 0; i < profile.samples; i += 1) {
      const context = await browser.newContext({viewport:{width:profile.width,height:profile.height}, isMobile:true,
        hasTouch:true, deviceScaleFactor:1});
      try {
        const page = await context.newPage();
        const cdp = await context.newCDPSession(page);
        await cdp.send('Network.enable');
        await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
        await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:profile.latencyMs,
          downloadThroughput:50_000,uploadThroughput:50_000});
        const readings = [];
        await measure(page, 'Portada', () => page.goto(portal), readings);
        await measure(page, 'Login Keycloak', async () => {
          await page.getByRole('link',{name:'Iniciar sesión'}).click();
          await page.waitForURL(url => url.origin === keycloak);
        }, readings);
        await page.locator('#username').fill('vecino1');
        await page.locator('#password').fill(password);
        await measure(page, 'Inicio vecino', async () => {
          await page.locator('#kc-login').click();
          await page.waitForURL(portal + '/');
        }, readings);
        await page.getByRole('radio').first().check();
        await measure(page, 'Detalle después del alta', async () => {
          await page.getByRole('button',{name:'Presentar solicitud'}).click();
          await page.waitForURL('**/web/solicitudes/*');
        }, readings);
        trials.push(readings);
      } finally { await context.close(); }
    }
    const summary = trials[0].map(({stage}, index) => {
      const samples = trials.map(trial => trial[index]);
      const median = key => samples.map(sample => sample[key]).sort((a,b) => a-b)[1];
      return {stage, medianLoadMs:median('loadMs'), medianActionToLoadMs:median('actionToLoadMs'),
        medianBodyBytes:median('bodyBytes'), requestCards:samples.map(sample => sample.displayedRequests)};
    });
    const report = {profile, method:'Navigation Timing y Resource Timing. Bytes del cuerpo codificado del documento final y sus recursos, sin cabeceras ni redirecciones. Acción a carga incluye ida y vuelta OIDC y la instrumentación.', trials, summary};
    if (process.env.NETWORK_REPORT) writeFileSync(process.env.NETWORK_REPORT, JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode=1; });
