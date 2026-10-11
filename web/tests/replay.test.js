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
  for (const source of ['fixture', 'recorded evaluation replay', 'live']) {
    input.source = source;
    const data = organizeReplay(input);
    assert.deepEqual(data.focus, { version: repair, scenario: 'val-26-high' });
    assert.equal(data.versions.get(repair).acceptance, 'repair');
    assert.equal(data.versions.get(cost._id).acceptance, 'cost');
    assert.equal(data.versions.get(baseline).acceptance, null);
    assert.deepEqual(data.versions.get(cost._id).verdict.reasons, ['unparsed evaluator text']);
  }
  delete input.focus;
  assert.deepEqual(organizeReplay(input).focus, { version: repair, scenario: 'val-26-high' });
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
