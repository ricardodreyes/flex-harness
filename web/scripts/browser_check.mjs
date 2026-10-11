import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(process.env.PLAYWRIGHT_PACKAGE || import.meta.url);
const { chromium } = require('playwright');
const url = process.env.FLEX_URL || 'http://127.0.0.1:4173';
const evidence = new URL('../evidence/', import.meta.url);
const fixture = JSON.parse(await readFile(new URL('../public/replay.json', import.meta.url), 'utf8'));
assert.equal(fixture.source, 'fixture', 'Run this check against the simulator fixture before the freeze.');
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
const results = [];
const screenshot = name => page.screenshot({ path: fileURLToPath(new URL(name, evidence)), fullPage: true });
const load = async () => {
  await page.goto(url);
  await page.locator('main').waitFor();
  await page.getByRole('status').waitFor({ state: 'hidden' });
};
const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
const replace = async payload => {
  await page.unroute('**/replay.json');
  await page.route('**/replay.json', route => route.fulfill({ json: payload }));
  await load();
};

try {
  await load();
  assert.match(await page.locator('h1').innerText(), /Restarts got expensive/);
  assert.equal(await page.locator('section.panel').count(), 4);
  for (const panel of await page.locator('section.panel').all()) {
    assert.equal((await panel.locator(':scope > .section-top .source').textContent()).trim(), '● fixture');
  }
  assert.equal(await page.locator('svg[role="img"]').count(), 4);
  assert.equal(await page.locator('#proposal').inputValue(), fixture.focus.version);
  assert.equal(await page.locator('#scenario').inputValue(), fixture.focus.scenario);
  await page.locator('section.panel').nth(2).getByText('Accepted repair', { exact: true }).waitFor();
  assert.match(await page.locator('.hero-note').innerText(), /hand-authored controls/i);
  await noOverflow();
  await screenshot('fixture-desktop.png');
  results.push('Desktop fixture renders four labeled story panels and four charts.');

  await page.locator('#hour-window').focus();
  assert.notEqual(await page.locator('#hour-window').evaluate(element => getComputedStyle(element).outlineStyle), 'none');
  const window = await page.locator('#hour-window').evaluate(input => ({ value: Number(input.value), max: Number(input.max), step: Number(input.step) }));
  const direction = window.value < window.max ? 1 : -1;
  await page.keyboard.press(direction > 0 ? 'ArrowRight' : 'ArrowLeft');
  assert.equal(Number(await page.locator('#hour-window').inputValue()), window.value + direction * window.step);
  const scenario = await page.locator('#scenario').inputValue();
  const alternate = (await page.locator('#scenario option').evaluateAll(options => options.map(option => option.value))).find(value => value !== scenario);
  assert.ok(alternate, 'The fixture must offer more than one validation scenario.');
  await page.locator('#scenario').selectOption(alternate);
  await page.waitForFunction(value => document.querySelectorAll('.baseline > .subtle')[1]?.textContent.startsWith(value), alternate);
  assert.equal(await page.locator('#scenario').inputValue(), alternate);
  results.push('Keyboard focus, the shared hour slider, and scenario selection work.');

  const rejected = fixture.versions.find(version => version.verdict && !version.verdict.accepted);
  assert.ok(rejected, 'The fixture must include a rejected proposal.');
  await page.locator('#proposal').selectOption(rejected._id);
  await page.locator('section.panel').nth(2).getByText('Rejected', { exact: true }).waitFor();
  assert.match(await page.locator('section.panel').nth(2).innerText(), /Rejected/);
  for (const reason of rejected.verdict.reasons) assert.ok((await page.locator('.verdict-reasons').innerText()).includes(reason));
  await screenshot('fixture-rejected.png');
  results.push('Rejected proposals retain the evaluator reasons.');

  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: fileURLToPath(new URL('fixture-mobile.png', evidence)) });
  assert.deepEqual(errors, []);
  results.push('The 390px page has no horizontal body overflow. Normal interaction has no console errors or warnings.');

  const missing = structuredClone(fixture);
  for (const run of missing.runs) { delete run.jobs; delete run.diagnosis; }
  await replace(missing);
  assert.match(await page.locator('.diagnosis').innerText(), /unavailable/i);
  assert.match(await page.locator('.jobs').innerText(), /unavailable/i);
  results.push('Missing simulator diagnosis and job outcomes remain unavailable.');

  const malformed = structuredClone(fixture);
  const invalid = malformed.versions.find(version => version._id === rejected._id);
  invalid.policy = { rules: 'invalid fixture policy' };
  malformed.runs = malformed.runs.filter(run => run.version !== invalid._id);
  malformed.hours = malformed.hours.filter(hour => hour.meta.version !== invalid._id);
  malformed.misses = malformed.misses.filter(miss => miss.version !== invalid._id);
  await replace(malformed);
  await page.locator('#proposal').selectOption(invalid._id);
  await page.locator('section.panel').nth(2).getByText('Rejected', { exact: true }).waitFor();
  assert.deepEqual((await page.locator('.verdict-reasons > p').allTextContents()).slice(0, rejected.verdict.reasons.length), rejected.verdict.reasons);
  assert.match(await page.locator('main').innerText(), /unavailable/i);
  results.push('Malformed rejected policy without runs still shows its verdict.');

  const long = structuredClone(fixture);
  for (const version of long.versions) {
    version.rationale = 'A';
    version.predicted = 'A'.repeat(220);
  }
  await replace(long);
  await noOverflow();
  results.push('One-character and 220-character proposal copy stay within the mobile page.');

  const expensive = structuredClone(fixture);
  const repair = expensive.versions.find(version => version.verdict);
  repair.verdict.accepted = true;
  repair.verdict.fixed = [expensive.scenarios.find(scenario => scenario.split === 'validation').id];
  repair.verdict.cost_delta_pct = 12.34;
  await replace(expensive);
  await page.locator('#proposal').selectOption(repair._id);
  await page.locator('section.panel').nth(2).getByText('Accepted repair', { exact: true }).waitFor();
  assert.match(await page.locator('section.panel').nth(2).innerText(), /\+12\.34%/);
  assert.match(await page.locator('section.panel').nth(2).innerText(), /Deadlines restored/);
  results.push('An injected costly repair displays its positive cost change plainly.');


  await replace({ ...fixture, focus: undefined, versions: [], runs: [], hours: [], misses: [] });
  assert.match(await page.locator('main').innerText(), /No recorded proposal/i);
  results.push('An empty replay shows a named empty state.');

  await page.unroute('**/replay.json');
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/replay.json', async route => { await gate; await route.fulfill({ json: fixture }); });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByRole('status').waitFor();
  assert.match(await page.getByRole('status').innerText(), /Loading/);
  release();
  await page.locator('#proposal').waitFor();
  results.push('A delayed replay exposes a loading state and then renders.');

  assert.deepEqual(errors, []);
  await page.unroute('**/replay.json');
  await page.route('**/replay.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto(url);
  await page.getByRole('alert').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /Static replay unavailable/);
  await screenshot('fixture-error.png');
  results.push('HTTP failure shows an actionable error without fixture fallback.');

  await page.unroute('**/replay.json');
  await page.setViewportSize({ width: 1440, height: 1080 });
  let apiRequests = 0;
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/replay') apiRequests += 1; });
  await page.goto(new URL('?mode=live', url).href);
  await page.getByRole('alert').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /Live mode is available only in the local development server/);
  assert.equal(apiRequests, 0);
  results.push('Production live mode is disabled without making an API request.');
  await load();
  await screenshot('fixture-desktop.png');
  await page.screenshot({ path: fileURLToPath(new URL('fixture-projector.png', evidence)) });
  await writeFile(new URL('browser-check.json', evidence), JSON.stringify({ url, results, expectedErrorConsole: errors }, null, 2) + '\n');
  console.log(results.join('\n'));
} finally {
  await browser.close();
}
