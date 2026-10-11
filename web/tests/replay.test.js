import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { organizeReplay, sanitizeRecord } from '../src/replay.js';

const fixture = JSON.parse(execFileSync('uv', ['run', '--frozen', 'python', '-c',
  'import json; from web.scripts.export_replay import fixture, serialize; print(json.dumps(fixture(), default=serialize))'], {
  cwd: fileURLToPath(new URL('../../', import.meta.url)), maxBuffer: 8 * 1024 * 1024,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1',
    UV_PROJECT_ENVIRONMENT: fileURLToPath(new URL('../.venv', import.meta.url)),
    UV_CACHE_DIR: fileURLToPath(new URL('../.cache/uv', import.meta.url)) },
}));
const copy = () => structuredClone(fixture);
const repair = 'fixture-control-repair';
const baseline = 'fixture-incumbent';
const scenarioId = fixture.focus.scenario;
const scenario = fixture.scenarios.find(record => record.id === scenarioId);
const expectedHours = scenario.arrival_days * 24 + scenario.tail_h;
const finalSource = JSON.parse(readFileSync(new URL('../../results/final.json', import.meta.url)));
const finalManifest = JSON.parse(readFileSync(new URL('../../results/final_manifest.json', import.meta.url)));

function finalReplay() {
  const input = copy();
  input.source = 'recorded evaluation replay';
  input.final_results = Object.entries(finalSource).map(([version, row]) => ({ version, ...structuredClone(row) }));
  input.versions.push(...finalManifest.pinned.filter(row => row.role !== 'reference').map(row => ({
    _id: row.version, parent: row.version === 'v0' ? null : 'v0', author: row.author, policy: row.policy,
    status: 'retired', identity: row.identity, rationale: 'Recorded proposal', predicted: 'Recorded prediction',
  })));
  input.evolve_runs = [
    { run: 1, versions: ['g1-289b1a', 'g5-683c0e'] },
    { run: 2, versions: ['g4-eac5bd', 'g5-e942f4'] },
  ];
  return input;
}

test('demo summary and copied ablation agree with the committed evidence', () => {
  const replay = JSON.parse(readFileSync(new URL('../public/replay.json', import.meta.url)));
  assert.equal(replay.source, 'recorded evaluation replay');
  for (const [version, passed] of [['v0', 10], ['g1-289b1a', 12]]) {
    const runs = replay.runs.filter(run => run.version === version && run.split === 'validation');
    assert.equal(runs.length, 12);
    assert.ok(runs.every(run => run.totals.infeasible_hours === 0));
    assert.equal(runs.filter(run => ['late_job_hours', 'unfinished_kwh', 'cap_interventions'].every(key => run.totals[key] === 0)).length, passed);
  }
  assert.equal(replay.scenarios.find(row => row.id === 'val-26-low').settings.restart_kwh, 35);
  assert.equal(replay.scenarios.find(row => row.id === 'val-26-high').settings.restart_kwh, 1050);
  const rejected = replay.versions.find(row => row._id === 'g4-4a14cc').verdict;
  assert.equal(rejected.accepted, false);
  assert.equal(rejected.cost_delta_pct.toFixed(2), '-2.57');
  assert.deepEqual(rejected.reasons, ['regression on val-26-high: late_job_hours 0 -> 1']);
  const source = readFileSync(new URL('../../results/exploratory-keepwarm-ablation.json', import.meta.url), 'utf8');
  assert.equal(readFileSync(new URL('../src/keepwarm-ablation.json', import.meta.url), 'utf8'), source);
  const ablation = JSON.parse(source);
  assert.deepEqual(ablation.scenarios, ['final-31', 'final-32', 'final-33']);
  assert.equal(Object.keys(finalSource).length, 7);
  assert.deepEqual(Object.values(ablation.results).map(row => [row.jobs_completed, row.late_job_hours]), [[38, 0], [38, 0]]);
  assert.deepEqual(Object.values(ablation.results).map(row => (100 * (1 - row.training_energy_cost / finalSource.v0.training_cost)).toFixed(2)), ['12.18', '4.28']);
  assert.equal(ablation.results['g5-e942f4'].training_energy_cost, finalSource['g5-e942f4'].training_cost);
  for (const reference of ['restart_aware', 'control']) assert.ok(ablation.results['g5-e942f4 without 1% keep-warm rule'].training_energy_cost > finalSource[reference].training_cost);
});

test('final scores retain all seven pins, references and separate final identities', () => {
  const data = organizeReplay(finalReplay());
  assert.deepEqual(data.final_results.map(row => row.version), Object.keys(finalSource));
  assert.deepEqual(data.final_results.filter(row => row.role === 'reference').map(row => row.version), ['restart_aware', 'control']);
  assert.equal(data.allFinalDeadlines, true);
  assert.equal(data.versions.get('g5-683c0e').evolveRun, 1);
  assert.equal(data.versions.get('g4-eac5bd').evolveRun, 2);
  assert.equal(data.versions.get('g4-eac5bd').generation, 'g4');
  assert.equal(data.versions.get('g4-eac5bd').parent, 'v0');
  assert.ok(data.runList.every(run => run.split !== 'final'));
  const late = finalReplay();
  late.final_results[0].scenarios['final-31'].totals.late_job_hours = 1;
  assert.equal(organizeReplay(late).allFinalDeadlines, false);
});

test('final score coverage, totals and lineage fail closed when inconsistent', () => {
  for (const mutate of [
    input => input.final_results.pop(),
    input => { input.final_results[0].training_cost += 1; },
    input => { delete input.final_results[0].scenarios['final-31']; },
    input => { input.final_results[0].identity.policy_sha256 = 'other'; },
    input => { input.evolve_runs[1].versions.push('missing'); },
    input => { input.source = 'fixture'; },
    input => { input.source = 'live'; },
  ]) {
    const input = finalReplay();
    mutate(input);
    assert.throws(() => organizeReplay(input));
  }
});

test('stored baseline without a version identity is checked against its persisted run hashes', () => {
  const input = finalReplay();
  delete input.versions.find(version => version._id === 'v0').identity;
  const run = structuredClone(input.runs.find(record => record.version === baseline));
  run._id = `v0:${run.scenario}`;
  run.version = 'v0';
  run.identity.policy_sha256 = finalSource.v0.identity.policy_sha256;
  input.runs.push(run);
  assert.equal(organizeReplay(input).final_results[0].version, 'v0');
  run.identity.policy_sha256 = 'another-policy';
  assert.throws(() => organizeReplay(input), /Final version does not match/);
});

test('real simulator fixture retains authors, validation verdict, diagnosis, hours and jobs', () => {
  const data = organizeReplay(fixture);
  assert.equal(data.source, 'fixture');
  assert.equal(data.versions.get(repair).author, 'control');
  const validationIds = fixture.runs.filter(run => run.version === repair && run.split === 'validation').map(run => run.scenario);
  for (const proposal of data.proposals) {
    assert.equal(typeof proposal.verdict.accepted, 'boolean');
    assert.deepEqual(proposal.verdict, fixture.versions.find(version => version._id === proposal._id).verdict);
    assert.ok([...proposal.verdict.fixed, ...proposal.verdict.regressed].every(id => validationIds.includes(id)));
  }
  assert.deepEqual(data.versions.get(repair).identity.scenario_ids, validationIds);
  const comparison = data.comparison(repair, scenarioId);
  assert.equal(comparison.unavailable, null);
  assert.equal(comparison.baseline.version, baseline);
  assert.equal(comparison.hoursAvailable, true);
  assert.equal(comparison.jobsAvailable, true);
  assert.equal(comparison.hours.length, expectedHours);
  const problem = fixture.runs.find(run => run.version === baseline && run.split === 'dev');
  assert.ok(problem.diagnosis.length > 0);
  assert.deepEqual(data.runs.get(problem._id).diagnosis, problem.diagnosis);
  assert.ok(data.runList.every(run => run.split !== 'final'));
});

test('hours join by h and jobs by id regardless of record order', () => {
  const input = copy();
  input.hours.reverse();
  for (const run of input.runs) run.jobs.reverse();
  const comparison = organizeReplay(input).comparison(repair, scenarioId);
  assert.equal(comparison.hours[0].h, 0);
  assert.equal(comparison.hours.at(-1).h, expectedHours - 1);
  assert.ok(comparison.jobs.every(job => job.before.id === job.after.id));
});

test('a later generation keeps its parent distinct from the frozen baseline', () => {
  const input = copy();
  const ancestor = structuredClone(input.versions.find(version => version._id === baseline));
  ancestor._id = 'ancestor';
  ancestor.author = 'supervisor';
  ancestor.parent = baseline;
  input.versions.push(ancestor);
  const parentRun = structuredClone(input.runs.find(run => run.version === baseline && run.scenario === scenarioId));
  parentRun._id = `ancestor:${scenarioId}`;
  parentRun.version = 'ancestor';
  parentRun.jobs[0].done_h = 1;
  input.runs.push(parentRun);
  input.versions.find(version => version._id === repair).parent = 'ancestor';
  const comparison = organizeReplay(input).comparison(repair, scenarioId);
  assert.equal(comparison.parent.version, 'ancestor');
  assert.equal(comparison.baseline.version, baseline);
  assert.equal(comparison.hoursAvailable, true);
  assert.equal(comparison.jobs[0].before.done_h, comparison.baseline.jobs[0].done_h);
  assert.notEqual(comparison.jobs[0].before.done_h, parentRun.jobs[0].done_h);
  assert.equal(comparison.hours[0].before.meta.version, baseline);
});

test('focus opens the accepted repair even with a newer cost acceptance', () => {
  const input = copy();
  const cost = structuredClone(input.versions.find(version => version._id === repair));
  cost._id = 'newest-cost';
  cost.created_at = '2099-01-01T00:00:00Z';
  cost.verdict.fixed = [];
  cost.verdict.reasons = ['unparsed evaluator text'];
  input.versions.push(cost);
  for (const source of ['fixture', 'recorded evaluation replay']) {
    input.source = source;
    const data = organizeReplay(input);
    assert.deepEqual(data.focus, { baseline, version: repair, scenario: 'val-26-high' });
    assert.equal(data.versions.get(repair).acceptance, 'repair');
    assert.equal(data.versions.get(cost._id).acceptance, 'cost');
    assert.equal(data.versions.get(baseline).acceptance, null);
    assert.deepEqual(data.versions.get(cost._id).verdict.reasons, ['unparsed evaluator text']);
  }
  delete input.focus;
  assert.deepEqual(organizeReplay(input).focus, { baseline, version: repair, scenario: 'val-26-high' });
});

test('unknown or incompatible focus fails instead of opening another proposal', () => {
  for (const focus of [{ version: 'missing', scenario: scenarioId }, { version: baseline, scenario: scenarioId },
    { version: repair, scenario: 'missing' }]) {
    const input = copy();
    input.focus = focus;
    assert.throws(() => organizeReplay(input), /focus/);
  }
  const input = copy();
  input.runs.find(run => run.version === repair && run.scenario === scenarioId).identity.manifest_sha256 = 'other';
  assert.throws(() => organizeReplay(input), /focus/);
});

test('retired baselines, ancestors and proposals retain comparisons and verbatim verdicts', () => {
  const input = copy();
  input.versions.find(version => version._id === baseline).status = 'retired';
  const ancestor = input.versions.find(version => version._id === repair);
  ancestor.status = 'retired';
  ancestor.verdict = {
    accepted: true,
    reasons: ['repairs val-23-high; training energy +2.1% to restore deadlines'],
    fixed: ['val-23-high'], regressed: [], cost_delta_pct: 2.1,
  };
  const successor = input.versions.find(version => version._id === 'fixture-control-cheap');
  successor.parent = repair;
  successor.status = 'rejected';
  successor.verdict = {
    accepted: false,
    reasons: ['not cheaper: training energy +10.10%', 'regression on val-23-high', 'incomplete evaluation'],
    fixed: [], regressed: ['val-23-high'], cost_delta_pct: null,
  };
  const data = organizeReplay(input);
  assert.equal(data.versions.get(baseline).status, 'retired');
  assert.ok(data.proposals.some(version => version._id === repair && version.status === 'retired'));
  assert.deepEqual(data.versions.get(repair).verdict, ancestor.verdict);
  assert.deepEqual(data.versions.get(successor._id).verdict, successor.verdict);
  const historical = data.comparison(repair, scenarioId);
  assert.equal(historical.unavailable, null);
  assert.equal(historical.baseline.version, baseline);
  const current = data.comparison(successor._id, scenarioId);
  assert.equal(current.unavailable, null);
  assert.equal(current.parent.version, repair);
  assert.equal(current.baseline.version, baseline);
});

test('mismatched evaluator and manifest never become comparisons', () => {
  for (const field of ['evaluator_version', 'manifest_sha256', 'scenario_ids']) {
    const input = copy();
    delete input.focus;
    const candidate = input.runs.find(run => run.version === repair && run.scenario === scenarioId);
    candidate.identity[field] = field === 'scenario_ids' ? [...candidate.identity.scenario_ids, 'unmatched-scenario'] : 'different';
    const comparison = organizeReplay(input).comparison(repair, scenarioId);
    assert.match(comparison.unavailable, /matching evaluator and manifest unavailable/);
    assert.equal(comparison.parent, undefined);
  }
});

test('incomplete hours and jobs stay unavailable instead of becoming zeros', () => {
  const input = copy();
  input.hours = input.hours.filter(hour => !(hour.meta.scenario === scenarioId && hour.h === Math.floor(expectedHours / 2)));
  const comparison = organizeReplay(input).comparison(repair, scenarioId);
  assert.equal(comparison.hoursAvailable, false);
  const inputJobs = copy();
  inputJobs.runs.find(run => run.version === repair && run.scenario === scenarioId).jobs.pop();
  assert.equal(organizeReplay(inputJobs).comparison(repair, scenarioId).jobsAvailable, false);
  delete inputJobs.runs.find(run => run.version === repair && run.scenario === scenarioId).jobs;
  assert.equal(organizeReplay(inputJobs).comparison(repair, scenarioId).jobsAvailable, false);
});

test('different operating inputs and workloads refuse before/after claims', () => {
  for (const field of ['ts', 'price', 'inference_kw', 'event', 'safety_limit_kw']) {
    const input = copy();
    delete input.focus;
    const hour = input.hours.find(hour => hour.meta.version === repair && hour.meta.scenario === scenarioId);
    hour[field] = field === 'ts' ? '2020-01-01T00:00:00Z' : field === 'event' ? !hour.event : hour[field] + 1;
    assert.match(organizeReplay(input).comparison(repair, scenarioId).unavailable, /Operating inputs differ/);
  }
  for (const field of ['arrive_h', 'deadline_h', 'work_kwh']) {
    const input = copy();
    delete input.focus;
    input.runs.find(run => run.version === repair && run.scenario === scenarioId).jobs[0][field] += 1;
    assert.match(organizeReplay(input).comparison(repair, scenarioId).unavailable, /Job workloads differ/);
  }
});

test('invalid rejected proposals preserve reasons even with no runs', () => {
  const input = copy();
  const rejected = input.versions.find(version => version._id === 'fixture-control-cheap');
  rejected.policy = { rules: [null, { when: [null], power: 1 }] };
  rejected.verdict.reasons = ['invalid policy', 'missing context_fields'];
  input.runs = input.runs.filter(run => run.version !== rejected._id);
  input.hours = input.hours.filter(hour => hour.meta.version !== rejected._id);
  const data = organizeReplay(input);
  assert.equal(data.versions.get(rejected._id).policyValid, false);
  assert.deepEqual(data.versions.get(rejected._id).verdict.reasons, ['invalid policy', 'missing context_fields']);
  assert.equal(data.comparison(rejected._id, scenarioId).unavailable, 'Candidate run unavailable.');
});

test('duplicate records and missing numeric totals fail at the boundary', () => {
  const input = copy();
  input.hours.push(input.hours[0]);
  assert.throws(() => organizeReplay(input), /Duplicate hour/);
  const missing = copy();
  delete missing.runs[0].totals.training_energy_cost;
  assert.throws(() => organizeReplay(missing), /Unavailable total training_energy_cost/);
  const duplicate = copy();
  duplicate.runs.push({ ...duplicate.runs[0], _id: 'another-id-for-the-same-run' });
  assert.throws(() => organizeReplay(duplicate), /Duplicate or unlinked run/);
});

test('public artifact contains only replay and known fields exclude private extras', () => {
  assert.deepEqual(readdirSync(new URL('../public/', import.meta.url)), ['replay.json']);
  const version = { ...fixture.versions[0], secret: 'private', policy: { ...fixture.versions[0].policy, credential: 'private' } };
  const record = sanitizeRecord('versions', version);
  assert.equal(record.secret, undefined);
  assert.equal(record.policy.credential, undefined);
  assert.doesNotMatch(JSON.stringify(fixture), /mongodb(?:\+srv)?:\/\/|MONGODB_READER_URI|BEGIN PRIVATE KEY/);
});

test('production assets contain no database module, URI or server environment variables', () => {
  const dist = new URL('../dist/', import.meta.url);
  const assets = new URL('assets/', dist);
  for (const file of readdirSync(assets)) {
    assert.doesNotMatch(readFileSync(new URL(file, assets), 'utf8'), /mongodb(?:\+srv)?:\/\/|MONGODB_READER_URI|MongoClient|loadEnvFile/);
  }
  assert.deepEqual(JSON.parse(readFileSync(new URL('replay.json', dist))),
    JSON.parse(readFileSync(new URL('../public/replay.json', import.meta.url))));
});
