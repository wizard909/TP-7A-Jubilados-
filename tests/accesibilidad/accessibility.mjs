import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const portal = new URL('http://localhost:8080');
const identity = new URL('http://localhost:8180');
const password = process.env.TEST_PASSWORD ?? readFileSync(new URL('../../.env', import.meta.url), 'utf8')
  .split(/\r?\n/).find(line => line.startsWith('TEST_PASSWORD='))?.slice('TEST_PASSWORD='.length);
assert(password, 'Falta TEST_PASSWORD de la demo local');
const headed = process.env.A11Y_HEADED === '1';
const report = { axe: require('axe-core').version, browser: '', checks: [], keyboard: [] };
const browser = await chromium.launch({
  headless: !headed,
  executablePath: process.env.A11Y_CHROME || undefined,
  args: ['--no-proxy-server'],
});
report.browser = browser.version();

async function pause(page) {
  if (headed) await page.waitForTimeout(600); // Da tiempo al lector de pantalla para registrar el foco.
}

async function focusUsingTab(page, selector) {
  for (let i = 0; i < 200; i += 1) {
    await page.keyboard.press('Tab');
    if (await page.locator(':focus').evaluateAll((els, s) => els[0]?.matches(s), selector)) {
      const style = await page.locator(':focus').evaluate(el => {
        const css = getComputedStyle(el);
        return { outline: css.outlineStyle, width: parseFloat(css.outlineWidth) };
      });
      assert(style.outline !== 'none' && style.width >= 1, 'Foco invisible: ' + selector);
      await pause(page);
      return;
    }
  }
  assert.fail('No se alcanzó con Tab: ' + selector);
}

async function enter(page, selector) {
  await focusUsingTab(page, selector);
  await page.keyboard.press('Enter');
}

async function skipToMain(page) {
  await page.keyboard.press('Tab');
  assert.equal(await page.locator(':focus').getAttribute('href'), '#contenido');
  await page.keyboard.press('Enter');
  assert.equal(await page.locator(':focus').getAttribute('id'), 'contenido');
  await pause(page);
}

async function audit(page, name, expectedWidth) {
  await page.addScriptTag({ path: require.resolve('axe-core') });
  const result = await page.evaluate(async () => {
    const findings = await window.axe.run({
      runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice'] },
    });
    return {
      viewportWidth: window.innerWidth,
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      violations: findings.violations.map(issue => ({ id: issue.id, nodes: issue.nodes.map(node => node.target) })),
      manual: [...new Set(findings.incomplete.map(issue => issue.id))],
      manualNodes: findings.incomplete.map(issue => ({ id: issue.id, nodes: issue.nodes.map(node => node.target) })),
      passedRules: findings.passes.length,
    };
  });
  report.checks.push({ name, ...result });
  assert.equal(await page.locator('main').count(), 1, name + ': región principal');
  assert.equal(await page.locator('h1').count(), 1, name + ': encabezado principal');
  assert.match(await page.locator('html').getAttribute('lang'), /^es(?:-|$)/);
  assert.equal(result.viewportWidth, expectedWidth, name + ': ancho efectivo');
  assert.equal(result.scrollWidth, result.width, name + ': desbordamiento horizontal');
  assert.deepEqual(result.violations, [], name + ': axe encontró infracciones');
}

async function login(page, user, setup) {
  await page.goto(portal.href);
  await audit(page, setup.name + ' portada', setup.width);
  await skipToMain(page);
  await enter(page, 'a[href="/login"]');
  await page.waitForURL(identity.origin + '/**');
  await page.locator('#username').waitFor();
  await pause(page);
  assert.equal(await page.locator(':focus').getAttribute('id'), 'username');
  assert.equal(await page.locator('#username').getAttribute('autocomplete'), 'username');
  assert.equal(await page.locator('#password').getAttribute('autocomplete'), 'current-password');
  assert.equal(await page.locator('meta[name=viewport]').count(), 1);
  await audit(page, setup.name + ' Keycloak', setup.width);
  await page.keyboard.insertText(user);
  await focusUsingTab(page, '#password');
  await page.keyboard.insertText(setup.tryWrong ? 'clave incorrecta de prueba' : password);
  await focusUsingTab(page, 'button[data-password-toggle]');
  await page.keyboard.press('Space');
  assert.equal(await page.locator('#password').getAttribute('type'), 'text');
  assert.match(await page.locator(':focus').getAttribute('aria-label'), /Ocultar contraseña/i);
  await page.keyboard.press('Space');
  assert.equal(await page.locator('#password').getAttribute('type'), 'password');
  await enter(page, '#kc-login');
  if (setup.tryWrong) {
    await page.locator('#input-error').waitFor();
    await pause(page);
    assert.equal(await page.locator(':focus').getAttribute('id'), 'username');
    for (const field of ['#username','#password']) {
      assert.equal(await page.locator(field).getAttribute('aria-invalid'), 'true');
      assert.equal(await page.locator(field).getAttribute('aria-describedby'), 'input-error');
    }
    assert.match(await page.locator('#input-error').innerText(), /Usuario o contraseña incorrectos/i);
    await audit(page, setup.name + ' credenciales inválidas', setup.width);
    await focusUsingTab(page, '#password');
    await page.keyboard.insertText(password);
    await enter(page, '#kc-login');
  }
  await page.waitForURL(portal.href);
  assert((await page.locator('.session-name').textContent()).includes(user));
  report.keyboard.push(setup.name + ' ingreso con ' + user);
}

async function create(page, benefit, setup) {
  await page.goto(portal.href);
  await skipToMain(page);
  await focusUsingTab(page, 'input[name=beneficio]');
  if (benefit === 'descuento-transporte') await page.keyboard.press('ArrowDown');
  else await page.keyboard.press('Space');
  assert.equal(await page.locator('input[name=beneficio]:checked').inputValue(), benefit);
  await enter(page, 'button[type=submit]');
  await page.waitForURL('**/web/solicitudes/*');
  await pause(page);
  assert.match(await page.title(), /Solicitud pendiente/);
  assert.equal(await page.locator('[data-estado]').innerText(), 'Pendiente');
  assert.match(await page.locator('.notice').innerText(), /Recibimos tu solicitud/);
  await audit(page, setup.name + ' confirmación del vecino', setup.width);
  return new URL(page.url()).pathname;
}

async function decide(page, path, state, reason, setup) {
  await page.goto(portal.href);
  await skipToMain(page);
  const link = page.locator('a[href="' + path + '"]');
  assert.match(await link.ariaSnapshot(), /link "Revisar solicitud .+ Pendiente"/);
  await enter(page, 'a[href="' + path + '"]');
  await page.waitForURL(portal.origin + path);
  await audit(page, setup.name + ' revisión del agente', setup.width);
  await skipToMain(page);
  await focusUsingTab(page, '#motivo');
  await page.keyboard.insertText(reason);
  await enter(page, 'button[value="' + state + '"]');
}

async function flow(setup) {
  const { width, isMobile } = setup;
  const context = await browser.newContext({
    viewport: { width, height: 850 }, isMobile, hasTouch: isMobile,
  });
  try {
    const page = await context.newPage();
    await login(page,'vecino1',setup);
    await audit(page,setup.name + ' inicio del vecino',width);
    const approved = await create(page,'tarifa-social',setup);
    const rejected = await create(page,'descuento-transporte',setup);
    await enter(page,'a[href="/logout"]');
    await page.waitForURL(portal.href);
    await login(page,'agente1',{...setup,tryWrong:false});
    await audit(page,setup.name + ' bandeja',width);
    const approvedReason = 'Verificación de accesibilidad. Se aprobó el beneficio.';
    const rejectedReason = 'Verificación de accesibilidad. Se rechazó el beneficio.';
    await decide(page,approved,'aprobada',approvedReason,setup);
    await page.waitForURL(portal.origin+approved);
    assert.match(await page.title(), /Solicitud aprobada/);
    await decide(page,rejected,'rechazada',rejectedReason,setup);
    await page.waitForURL(portal.origin+rejected);
    assert.match(await page.title(), /Solicitud rechazada/);
    if (setup.tryWrong) {
      await context.clearCookies();
      await login(page,'vecino3',{...setup,tryWrong:false});
      const unavailable = await create(page,'tarifa-social',setup);
      await context.clearCookies();
      await login(page,'agente1',{...setup,tryWrong:false});
      const reason = 'Verificación de accesibilidad. El motivo se conserva.';
      const result = page.waitForResponse(r=>r.request().method()==='POST' && r.url().endsWith('/decision'));
      await decide(page,unavailable,'aprobada',reason,setup);
      assert.equal((await result).status(),503);
      await page.waitForURL(portal.origin+unavailable+'/decision');
      await page.waitForFunction(()=>document.activeElement.id==='error-titulo');
      await pause(page);
      assert.equal(await page.locator(':focus').getAttribute('aria-describedby'),'error-detalle');
      assert.match(await page.locator('#error-detalle').innerText(), /padrón.*pendiente/i);
      assert.equal(await page.locator('#motivo').inputValue(),reason);
      await audit(page,setup.name + ' error de padrón',width);
    }
    await enter(page,'a[href="/logout"]');
    await page.waitForURL(portal.href);
    await login(page,'vecino1',{...setup,tryWrong:false});
    for (const [target,state,reason] of [[approved,'aprobada',approvedReason],[rejected,'rechazada',rejectedReason]]) {
      await page.goto(portal.href);
      await skipToMain(page);
      assert.match(await page.locator('a[href="' + target + '"]').ariaSnapshot(), /link "Ver detalle (?:Tarifa social|Descuento en transporte) (?:Aprobada|Rechazada)"/);
      await enter(page,'a[href="' + target + '"]');
      await page.waitForURL(portal.origin+target);
      await pause(page);
      assert.match(await page.title(), new RegExp('Solicitud '+state));
      assert.equal(await page.locator('[data-estado]').innerText(),state[0].toUpperCase()+state.slice(1));
      assert.equal(await page.locator('.resolution p').innerText(),reason);
      await audit(page,setup.name + ' resultado ' + state,width);
    }
    await enter(page,'a[href="/logout"]');
    await page.waitForURL(portal.href);
    const response = await page.goto(portal.origin+approved);
    assert.equal(response.status(),401);
    assert.match(response.headers()['content-type'], /text\/html/);
    await page.waitForFunction(()=>document.activeElement.id==='error-titulo');
    assert.equal(await page.getByRole('link',{name:'Iniciar sesión'}).count(),1);
    await audit(page,setup.name + ' sesión vencida',width);
    report.keyboard.push(setup.name + ' vecino y agente completan creación, decisión, consulta y salida');
  } finally { await context.close(); }
}

try {
  await flow({ name: 'Escritorio', width: 1366, isMobile: false, tryWrong: true });
  if (!headed) {
    await flow({ name: 'Móvil', width: 360, isMobile: true, tryWrong: false });
    await flow({ name: 'Reflujo', width: 320, isMobile: true, tryWrong: false });
  }
  console.log(report.checks.length + ' vistas auditadas, ' + report.keyboard.length + ' recorridos de teclado registrados.');
} finally {
  await browser.close();
  if (process.env.A11Y_REPORT) writeFileSync(process.env.A11Y_REPORT, JSON.stringify(report,null,2)+'\n');
}
