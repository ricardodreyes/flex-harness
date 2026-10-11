import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(process.env.PLAYWRIGHT_PACKAGE || '/opt/homebrew/lib/node_modules/@playwright/mcp/package.json');
const { chromium } = require('playwright');
const url = process.env.FLEX_URL || 'http://127.0.0.1:4173';
const evidence = new URL('../evidence/', import.meta.url);
const replay = JSON.parse(await readFile(new URL('../public/replay.json', import.meta.url), 'utf8'));
assert.equal(replay.source, 'recorded evaluation replay', 'Export the final recorded replay before this check.');
assert.deepEqual(replay.focus, { baseline: 'v0', version: 'g1-289b1a', scenario: 'val-26-high' });
assert.equal(replay.final_results.length, 7);
assert.equal(replay.evolve_runs.length, 2);
assert.equal(replay.featured_rejection, 'g4-4a14cc');
const repair = replay.versions.find(version => version._id === replay.focus.version);
const rejected = replay.versions.find(version => version._id === replay.featured_rejection);
const currency = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
const errors = [];
const consoleMessages = [];
const apiRequests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (['error', 'warning'].includes(message.type())) consoleMessages.push(message.text()); });
page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url()); });
const results = [];
const screenshot = (name, fullPage = true) => page.screenshot({ path: fileURLToPath(new URL(name, evidence)), fullPage });
const load = async (target = url) => {
  await page.goto(target);
  await page.locator('main').waitFor();
  await page.locator('main.error[role="status"]').waitFor({ state: 'hidden' });
};
const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'The page must not overflow horizontally.');
const replace = async payload => {
  await page.unroute('**/replay.json');
  await page.route('**/replay.json', route => route.fulfill({ json: payload }));
  await load();
};
const panel = title => page.locator('section.panel').filter({ has: page.getByRole('heading', { name: title, exact: true }) });
const behavior = panel('Same hours. Same jobs. Different decisions.');
const evaluation = () => page.locator('section.panel').filter({ has: page.locator('.verdict-reasons') });
const assertReasons = async (container, version) => {
  const paragraphs = await container.locator(':scope > p').allTextContents();
  for (const reason of version.verdict.reasons) assert.ok(paragraphs.includes(reason), `Missing verbatim reason for ${version._id}.`);
};

try {
  const response = page.waitForResponse(response => new URL(response.url()).pathname === '/replay.json');
  await load();
  assert.deepEqual(await (await response).json(), replay, 'The served build must contain the current exported replay.');
  assert.match(await page.locator('h1').innerText(), /Restarts got expensive/);
  assert.equal(await page.locator('section.panel').count(), 6);
  for (const source of await page.locator('.source').all()) assert.equal((await source.textContent()).trim(), `● ${replay.source}`);
  assert.equal(await page.locator('svg[role="img"]').count(), 4);
  assert.equal(await page.locator('#proposal').inputValue(), repair._id);
  await evaluation().getByText('Accepted repair', { exact: true }).waitFor();
  await assertReasons(page.locator('.verdict-reasons'), repair);
  assert.match(await page.locator('.hero-note').innerText(), /Read-only evaluation records/);
  const problemRun = replay.runs.find(run => run.version === replay.focus.baseline && run.scenario === 'dev-13-high');
  assert.ok(problemRun);
  assert.match(await page.locator('#problem .section-intro').innerText(), /^dev-13-high/);
  assert.deepEqual(await page.locator('#problem .diagnosis > p').allTextContents(), problemRun.diagnosis);
  results.push('The served replay matches the export; all six panels and nested views carry the recorded evaluation replay label.');

  const scoreboard = page.locator('.scoreboard');
  const scoreRows = scoreboard.locator('tbody tr');
  assert.equal(await scoreRows.count(), replay.final_results.length);
  for (const [index, result] of replay.final_results.entries()) {
    const row = scoreRows.nth(index);
    assert.ok((await row.getByRole('rowheader').innerText()).endsWith(result.version));
    const cells = await row.locator('td').allTextContents();
    assert.match(cells[0], result.role === 'reference' ? /^Reference · / : /^Promoted · /);
    const totals = Object.values(result.scenarios).map(scenario => scenario.totals);
    const sum = key => totals.reduce((total, values) => total + values[key], 0);
    assert.equal(cells[1], `${sum('jobs_completed')} / ${sum('jobs_total')} jobs · ${sum('late_job_hours')} late job-hours`);
    assert.equal(cells[2], currency(result.training_cost));
  }
  assert.equal(replay.final_results.filter(result => result.role === 'reference').length, 2);
  assert.equal(await scoreboard.getByText(/^Reference · /).count(), 2);
  await panel('All seven pinned versions, on the final scenarios.').getByText('Every version met every final deadline. The repair evidence is the validation verdict.', { exact: true }).waitFor();
  results.push('All seven pinned versions render in source order with exact final totals and costs; both references and the validation-versus-final distinction are labeled.');

  const groups = page.locator('.evolve-run');
  assert.equal(await groups.count(), replay.evolve_runs.length);
  for (const [index, group] of replay.evolve_runs.entries()) {
    const container = groups.nth(index);
    assert.equal(await container.getByRole('heading').innerText(), `Evolve run ${group.run}`);
    const items = container.locator('li');
    assert.equal(await items.count(), group.versions.length);
    for (const [position, id] of group.versions.entries()) {
      assert.equal(await items.nth(position).locator('strong').innerText(), `Run ${group.run} / ${id.split('-')[0]} · ${id}`);
      const version = replay.versions.find(version => version._id === id);
      assert.ok((await items.nth(position).locator('span').innerText()).endsWith(version.parent));
    }
  }
  for (const version of [repair, rejected]) {
    const feature = page.locator('.featured-verdicts article').filter({ has: page.getByRole('heading', { name: new RegExp(version._id) }) });
    assert.equal(await feature.count(), 1);
    await assertReasons(feature, version);
  }
  results.push('Both evolve runs list every proposal with run, generation and parent; featured repair and rejection reasons remain verbatim.');

  assert.match(await behavior.locator('.selection').innerText(), /val-26-high · v0 → Run 1 \/ g1 · g1-289b1a/);
  assert.equal(await page.locator('#scenario').count(), 0);
  assert.match(await page.locator('.jobs > .subtle').innerText(), /Work during hour N completes at the end of h N, at offset N \+ 1/);
  const baseline = replay.runs.find(run => run.version === replay.focus.baseline && run.scenario === replay.focus.scenario);
  const candidate = replay.runs.find(run => run.version === replay.focus.version && run.scenario === replay.focus.scenario);
  const jobRows = page.locator('.jobs tbody tr');
  assert.equal(await jobRows.count(), baseline.jobs.length);
  for (const row of await jobRows.all()) {
    const id = await row.getByRole('rowheader').innerText();
    const before = baseline.jobs.find(job => job.id === id);
    const after = candidate.jobs.find(job => job.id === id);
    assert.ok(before && after, `Job ${id} must belong to both pinned runs.`);
    const completed = job => job.done_h === null ? 'Unfinished' : `End of h ${job.done_h}`;
    assert.deepEqual(await row.locator('td').allTextContents(), [`h ${before.arrive_h}`, `h ${before.deadline_h}`, completed(before), completed(after), `${before.late_h} → ${after.late_h}`]);
  }
  await noOverflow();
  await screenshot('recorded-desktop.png');
  await screenshot('recorded-projector.png', false);
  await page.locator('section.panel').filter({ has: scoreboard }).screenshot({ path: fileURLToPath(new URL('recorded-scoreboard.png', evidence)) });
  await page.locator('section.panel').filter({ has: page.locator('.evolve-run') }).screenshot({ path: fileURLToPath(new URL('recorded-lineage.png', evidence)) });
  results.push('The behavior panel pairs v0 and g1-289b1a on val-26-high; every job shows completion at the end of its final work hour.');

  const slider = page.locator('#hour-window');
  await slider.focus();
  assert.notEqual(await slider.evaluate(element => getComputedStyle(element).outlineStyle), 'none');
  const window = await slider.evaluate(input => ({ value: Number(input.value), max: Number(input.max), step: Number(input.step) }));
  const direction = window.value < window.max ? 1 : -1;
  await page.keyboard.press(direction > 0 ? 'ArrowRight' : 'ArrowLeft');
  assert.equal(Number(await slider.inputValue()), window.value + direction * window.step);
  const pinnedBehavior = await behavior.innerText();
  await page.locator('#proposal').selectOption(rejected._id);
  await evaluation().getByText('Rejected', { exact: true }).waitFor();
  await assertReasons(page.locator('.verdict-reasons'), rejected);
  assert.equal(await behavior.innerText(), pinnedBehavior, 'Inspecting a rejection must not change the pinned repair evidence.');
  results.push('The hour slider works by keyboard with a visible focus indicator; choosing the rejected proposal leaves the repair behavior pinned.');

  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await page.locator('#proposal').selectOption(repair._id);
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await screenshot('recorded-mobile.png');
  await load(new URL('?mode=live', url).href);
  assert.equal(await page.locator('#proposal').inputValue(), repair._id);
  assert.equal(await page.locator('.scoreboard tbody tr').count(), 7);
  assert.deepEqual(apiRequests, [], 'The recorded-only demo must never call a live API.');
  assert.deepEqual(errors, []);
  assert.deepEqual(consoleMessages, []);
  results.push('The 390px page has no horizontal body overflow; ?mode=live still renders recorded data with no API requests or browser warnings/errors.');

  const missing = structuredClone(replay);
  for (const run of missing.runs) { delete run.jobs; delete run.diagnosis; }
  await replace(missing);
  assert.match(await page.locator('.diagnosis').innerText(), /unavailable/i);
  assert.match(await page.locator('.jobs').innerText(), /unavailable/i);
  results.push('Missing diagnosis and job outcomes remain explicitly unavailable.');

  const malformed = structuredClone(replay);
  const invalid = malformed.versions.find(version => version._id === rejected._id);
  invalid.policy = { rules: 'invalid recorded policy' };
  malformed.runs = malformed.runs.filter(run => run.version !== invalid._id);
  malformed.hours = malformed.hours.filter(hour => hour.meta.version !== invalid._id);
  malformed.misses = malformed.misses.filter(miss => miss.version !== invalid._id);
  await replace(malformed);
  await page.locator('#proposal').selectOption(invalid._id);
  await evaluation().getByText('Rejected', { exact: true }).waitFor();
  await assertReasons(page.locator('.verdict-reasons'), rejected);
  assert.match(await page.locator('.policy-grid').innerText(), /unavailable/i);
  assert.equal(await behavior.locator('svg[role="img"]').count(), 4);
  results.push('A malformed rejected policy without runs retains its verdict and the pinned repair charts.');

  const long = structuredClone(replay);
  for (const version of long.versions) { version.rationale = 'A'; version.predicted = 'A'.repeat(220); }
  await replace(long);
  await noOverflow();
  results.push('Short and unbroken 220-character proposal text stay within the mobile page.');

  const expensive = structuredClone(replay);
  expensive.versions.find(version => version._id === repair._id).verdict.cost_delta_pct = 12.34;
  await replace(expensive);
  await evaluation().getByText('Accepted repair', { exact: true }).waitFor();
  assert.match(await evaluation().innerText(), /\+12\.34%/);
  await assertReasons(page.locator('.verdict-reasons'), repair);
  results.push('A costly accepted repair displays its positive cost change without changing the verbatim reason.');

  await replace({ ...replay, focus: undefined, featured_rejection: null, final_results: [], evolve_runs: [], versions: [], runs: [], hours: [], misses: [] });
  assert.match(await page.locator('main').innerText(), /No recorded proposal/i);
  results.push('An empty replay shows a named empty state.');

  await page.unroute('**/replay.json');
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/replay.json', async route => { await gate; await route.fulfill({ json: replay }); });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByRole('status').waitFor();
  assert.match(await page.getByRole('status').innerText(), /Loading/);
  release();
  await page.locator('#proposal').waitFor();
  assert.deepEqual(errors, []);
  assert.deepEqual(consoleMessages, []);
  results.push('A delayed replay exposes a loading state and then renders.');

  await page.unroute('**/replay.json');
  await page.route('**/replay.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto(url);
  await page.getByRole('alert').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /Static replay unavailable/);
  await screenshot('recorded-error.png');
  assert.deepEqual(errors, []);
  assert.ok(consoleMessages.every(message => message.includes('503')), 'Only the injected HTTP 503 may create a console error.');
  results.push('HTTP failure shows an actionable error without fixture fallback.');
  await writeFile(new URL('browser-check.json', evidence), JSON.stringify({ url, results, expectedErrorConsole: consoleMessages }, null, 2) + '\n');
  console.log(results.join('\n'));
} finally {
  await browser.close();
}
