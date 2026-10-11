export const fields = {
  versions: ['_id', 'parent', 'policy', 'rationale', 'predicted', 'author', 'status', 'verdict', 'identity', 'created_at'],
  runs: ['_id', 'version', 'scenario', 'split', 'totals', 'identity', 'created_at', 'jobs', 'diagnosis'],
  hours: ['h', 'ts', 'price', 'requested_kw', 'executed_kw', 'productive_kw', 'overhead_kw', 'inference_kw', 'event', 'safety_limit_kw', 'energy_cost', 'meta'],
  misses: ['run', 'version', 'scenario', 'h', 'ts', 'kind', 'job', 'detail', 'context'],
};

const totalFields = ['jobs_total', 'jobs_completed', 'jobs_late', 'late_job_hours', 'work_kwh', 'productive_kwh', 'overhead_kwh', 'unfinished_kwh', 'starts', 'restarts', 'cap_interventions', 'infeasible_hours', 'training_energy_cost', 'total_energy_cost'];
const jobFields = ['id', 'arrive_h', 'deadline_h', 'work_kwh', 'done_h', 'late_h', 'starts', 'overhead_kwh'];
const identityFields = ['evaluator_version', 'manifest_sha256', 'policy_sha256', 'scenario_ids'];
const observationFields = ['hour_of_day', 'price', 'price_pct', 'event_now', 'event_in_h', 'slack_h', 'need_h', 'queued_jobs', 'running', 'restart_kwh'];
const pick = (object, keys) => object && typeof object === 'object' ? Object.fromEntries(keys.filter(key => Object.hasOwn(object, key)).map(key => [key, object[key]])) : {};
const requireValue = (valid, message) => { if (!valid) throw new Error(message); };
const number = value => typeof value === 'number' && Number.isFinite(value);
const text = value => typeof value === 'string';
const strings = value => Array.isArray(value) && value.every(text);

export function sanitizeRecord(kind, input) {
  const record = pick(input, fields[kind]);
  if (record.identity) record.identity = pick(record.identity, identityFields);
  if (kind === 'versions') {
    record.policy = pick(record.policy, ['context_fields', 'default_power', 'rules']);
    if (Array.isArray(record.policy.rules)) record.policy.rules = record.policy.rules.map(inputRule => {
      const rule = pick(inputRule, ['power', 'when']);
      if (Array.isArray(rule.when)) rule.when = rule.when.map(inputCondition => {
        const condition = pick(inputCondition, ['field', 'op', 'value']);
        if (condition.value && typeof condition.value === 'object') condition.value = pick(condition.value, ['field', 'times', 'plus']);
        return condition;
      });
      return rule;
    });
    if (record.verdict) record.verdict = pick(record.verdict, ['accepted', 'reasons', 'fixed', 'regressed', 'cost_delta_pct']);
    record.acceptance = record.verdict?.accepted ? record.verdict.fixed?.length ? 'repair' : 'cost' : null;
  }
  if (kind === 'runs') {
    record.totals = pick(record.totals, totalFields);
    if (record.jobs) record.jobs = record.jobs.map(job => pick(job, jobFields));
  }
  if (kind === 'hours') record.meta = pick(record.meta, ['run', 'version', 'scenario']);
  if (kind === 'misses') record.context = pick(record.context, observationFields);
  return record;
}

function validateIdentity(identity) {
  requireValue(identity && identityFields.slice(0, 3).every(key => text(identity[key])) && strings(identity.scenario_ids), 'Missing evaluation identity.');
}

function validatePolicy(policy) {
  requireValue(policy && strings(policy.context_fields) && number(policy.default_power) && Array.isArray(policy.rules), 'Invalid policy shape.');
  for (const rule of policy.rules) {
    requireValue(number(rule.power) && Array.isArray(rule.when), 'Invalid ordered rule.');
    for (const condition of rule.when) {
      const value = condition.value;
      requireValue(text(condition.field) && ['<', '<=', '>', '>=', '=='].includes(condition.op), 'Invalid policy condition.');
      requireValue(number(value) || typeof value === 'boolean' || (value && text(value.field) && number(value.times) && number(value.plus)), 'Invalid policy comparison.');
    }
  }
}

function compatible(left, right) {
  return left.identity.evaluator_version === right.identity.evaluator_version
    && left.identity.manifest_sha256 === right.identity.manifest_sha256
    && JSON.stringify([...left.identity.scenario_ids].sort()) === JSON.stringify([...right.identity.scenario_ids].sort());
}

export function organizeReplay(input) {
  requireValue(input?.schema_version === 1 && ['fixture', 'recorded evaluation replay', 'live'].includes(input.source), 'Unsupported replay or source.');
  for (const name of ['versions', 'runs', 'hours', 'misses', 'scenarios']) requireValue(Array.isArray(input[name]), `Missing ${name} records.`);
  const replay = { schema_version: 1, source: input.source, generated_at: input.generated_at, scenarios: input.scenarios };
  for (const name of Object.keys(fields)) replay[name] = input[name].map(record => sanitizeRecord(name, record));
  const versions = new Map();
  for (const version of replay.versions) {
    requireValue(text(version._id) && !versions.has(version._id), 'Duplicate or invalid version id.');
    requireValue(['baseline', 'control', 'supervisor'].includes(version.author), 'Invalid policy author.');
    requireValue(text(version.rationale) && text(version.predicted), 'Missing proposal explanation.');
    try { validatePolicy(version.policy); version.policyValid = true; }
    catch (error) {
      requireValue(version.verdict?.accepted === false || version.status === 'rejected', error.message);
      version.policyValid = false;
    }
    if (version.identity) validateIdentity(version.identity);
    if (version.verdict) {
      const verdict = version.verdict;
      requireValue(typeof verdict.accepted === 'boolean' && strings(verdict.reasons) && strings(verdict.fixed) && strings(verdict.regressed)
        && (verdict.cost_delta_pct === null || number(verdict.cost_delta_pct)), 'Invalid evaluator verdict.');
    }
    versions.set(version._id, version);
  }
  const runs = new Map();
  const runKeys = new Set();
  for (const record of replay.runs) {
    const key = JSON.stringify([record.version, record.scenario]);
    requireValue(text(record._id) && !runs.has(record._id) && !runKeys.has(key) && versions.has(record.version) && text(record.scenario), 'Duplicate or unlinked run.');
    runKeys.add(key);
    requireValue(['dev', 'validation'].includes(record.split), 'Final runs are outside this demonstration.');
    validateIdentity(record.identity);
    requireValue(record.identity.scenario_ids.includes(record.scenario), 'Run scenario is absent from its evaluation identity.');
    const version = versions.get(record.version);
    requireValue(!version.identity || version.identity.policy_sha256 === record.identity.policy_sha256, 'Run policy does not match its version.');
    for (const key of totalFields) requireValue(number(record.totals[key]), `Unavailable total ${key}.`);
    if (record.diagnosis !== undefined) requireValue(strings(record.diagnosis), 'Invalid simulator diagnosis.');
    if (record.jobs !== undefined) {
      requireValue(Array.isArray(record.jobs), 'Invalid job outcomes.');
      const ids = new Set();
      for (const job of record.jobs) {
        requireValue(text(job.id) && !ids.has(job.id), 'Duplicate or invalid job id.');
        ids.add(job.id);
        requireValue(jobFields.filter(key => !['id', 'done_h'].includes(key)).every(key => number(job[key]))
          && (job.done_h === null || number(job.done_h)), 'Invalid job outcome.');
      }
    }
    runs.set(record._id, { ...record, hours: [] });
  }
  const seenHours = new Set();
  for (const hour of replay.hours) {
    const record = runs.get(hour.meta.run);
    requireValue(record && record.version === hour.meta.version && record.scenario === hour.meta.scenario, 'Hour metadata does not match its run.');
    requireValue(fields.hours.filter(key => !['meta', 'ts', 'event'].includes(key)).every(key => number(hour[key])) && typeof hour.event === 'boolean', 'Invalid hourly record.');
    const key = `${record._id}:${hour.h}`;
    requireValue(!seenHours.has(key), 'Duplicate hour in a run.');
    seenHours.add(key);
    record.hours.push(hour);
  }
  for (const record of runs.values()) record.hours.sort((a, b) => a.h - b.h);
  const newest = (a, b) => String(b.created_at).localeCompare(String(a.created_at)) || b._id.localeCompare(a._id);
  const runList = [...runs.values()].sort(newest);
  const baselines = replay.versions.filter(version => version.author === 'baseline');
  const proposals = replay.versions.filter(version => version.parent !== null).sort((a, b) => Number(b.verdict?.accepted) - Number(a.verdict?.accepted) || newest(a, b));
  const comparison = (versionId, scenarioId) => {
    const version = versions.get(versionId);
    const candidate = runList.find(record => record.version === versionId && record.scenario === scenarioId);
    if (!candidate) return { version, scenarioId, unavailable: 'Candidate run unavailable.' };
    const find = ids => runList.find(record => ids.includes(record.version) && record.scenario === scenarioId && compatible(record, candidate));
    const parent = find([version.parent]);
    const baseline = find(baselines.map(record => record._id));
    let unavailable = !parent ? 'Parent run with matching evaluator and manifest unavailable.'
      : !baseline ? 'Tuned baseline with matching evaluator and manifest unavailable.' : null;
    const beforeHours = new Map((baseline?.hours ?? []).map(hour => [hour.h, hour]));
    const afterHours = new Map(candidate.hours.map(hour => [hour.h, hour]));
    const hourIds = [...new Set([...beforeHours.keys(), ...afterHours.keys()])].sort((a, b) => a - b);
    const hours = hourIds.map(h => ({ h, before: beforeHours.get(h), after: afterHours.get(h) }));
    const beforeJobs = new Map((baseline?.jobs ?? []).map(job => [job.id, job]));
    const afterJobs = new Map((candidate.jobs ?? []).map(job => [job.id, job]));
    const jobs = [...new Set([...beforeJobs.keys(), ...afterJobs.keys()])].map(id => ({ id, before: beforeJobs.get(id), after: afterJobs.get(id) }));
    const scenario = replay.scenarios.find(item => item.id === scenarioId);
    const expectedHours = scenario ? scenario.arrival_days * 24 + scenario.tail_h : null;
    const hoursAvailable = hours.length > 0 && hours.every((hour, index) => hour.h === index && hour.before && hour.after)
      && (expectedHours === null || hours.length === expectedHours);
    const inputsMatch = hoursAvailable && hours.every(hour => ['ts', 'price', 'inference_kw', 'event', 'safety_limit_kw'].every(key => hour.before[key] === hour.after[key]));
    const jobsAvailable = baseline?.jobs !== undefined && candidate.jobs !== undefined
      && baseline.jobs.length === baseline.totals.jobs_total && candidate.jobs.length === candidate.totals.jobs_total
      && jobs.every(job => job.before && job.after);
    const workloadsMatch = jobsAvailable && jobs.every(job => ['arrive_h', 'deadline_h', 'work_kwh'].every(key => job.before[key] === job.after[key]));
    if (hoursAvailable && !inputsMatch) unavailable = 'Operating inputs differ. Before/after comparison is unavailable.';
    if (jobsAvailable && !workloadsMatch) unavailable = 'Job workloads differ. Before/after comparison is unavailable.';
    return { version, scenarioId, candidate, parent, baseline, unavailable, hours, jobs,
      hoursAvailable: hoursAvailable && inputsMatch,
      jobsAvailable: jobsAvailable && workloadsMatch };
  };
  let focus = input.focus;
  if (focus !== undefined) {
    requireValue(focus && text(focus.version) && text(focus.scenario)
      && versions.get(focus.version)?.acceptance === 'repair', 'Invalid replay focus.');
    const selected = comparison(focus.version, focus.scenario);
    requireValue(selected.candidate?.split === 'validation' && !selected.unavailable, 'Replay focus does not match compatible validation runs.');
    focus = { version: focus.version, scenario: focus.scenario };
  } else {
    const repair = proposals.filter(version => version.acceptance === 'repair').sort(newest)
      .find(version => runList.some(record => record.version === version._id && record.scenario === 'val-26-high'));
    if (repair) focus = { version: repair._id, scenario: 'val-26-high' };
  }
  return { ...replay, focus, versions, runs, runList, proposals, comparison };
}
