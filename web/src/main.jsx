import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { organizeReplay } from './replay.js';
import './style.css';

const fmt = (value, digits = 0) => value === undefined || value === null ? 'Unavailable' : value.toLocaleString('en-US', { maximumFractionDigits: digits });
const money = value => value === undefined ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
const signed = value => value === null || value === undefined ? 'Unavailable' : `${value >= 0 ? '+' : ''}${fmt(value, 2)}%`;
const versionLabel = version => version?.evolveRun ? `Run ${version.evolveRun} / ${version.generation} · ${version._id}` : version?._id ?? 'Unavailable';
const label = version => version?.author === 'baseline' ? 'Tuned baseline' : version?.author === 'control' ? 'Hand-authored control' : 'Supervisor proposal';

function Source({ source }) { return <span className="source"><span aria-hidden="true">●</span> {source}</span>; }
function Panel({ n, title, source, children, className = '' }) {
  return <section className={`panel ${className}`}><div className="section-top"><p className="eyebrow">{n}</p><Source source={source} /></div><h2>{title}</h2>{children}</section>;
}
function Metric({ value, name, note }) { return <div className="metric"><strong>{value}</strong><span>{name}</span>{note && <small>{note}</small>}</div>; }

function Baseline({ comparison, source }) {
  if (!comparison || comparison.unavailable) return <aside className="baseline"><Source source={source} /><p>{comparison?.unavailable ?? 'Matched baseline unavailable.'}</p></aside>;
  const base = comparison.baseline.totals;
  const candidate = comparison.candidate.totals;
  const rows = [
    ['Completed jobs', `${fmt(base.jobs_completed)} / ${fmt(base.jobs_total)}`, `${fmt(candidate.jobs_completed)} / ${fmt(candidate.jobs_total)}`],
    ['Productive work', `${fmt(base.productive_kwh, 1)} kWh`, `${fmt(candidate.productive_kwh, 1)} kWh`],
    ['Late jobs / job-hours', `${base.jobs_late} / ${base.late_job_hours}`, `${candidate.jobs_late} / ${candidate.late_job_hours}`],
    ['Unfinished work', `${fmt(base.unfinished_kwh, 1)} kWh`, `${fmt(candidate.unfinished_kwh, 1)} kWh`],
    ['Training electricity', money(base.training_energy_cost), money(candidate.training_energy_cost)],
    ['Whole-site electricity', money(base.total_energy_cost), money(candidate.total_energy_cost)],
    ['Safety cuts / infeasible hours', `${base.cap_interventions} / ${base.infeasible_hours}`, `${candidate.cap_interventions} / ${candidate.infeasible_hours}`],
  ];
  const wins = [];
  if (base.training_energy_cost < candidate.training_energy_cost) wins.push(`costs ${money(candidate.training_energy_cost - base.training_energy_cost)} less in training electricity`);
  if (base.late_job_hours < candidate.late_job_hours) wins.push('has fewer late job-hours');
  if (base.jobs_completed > candidate.jobs_completed) wins.push('completes more jobs');
  return <aside className="baseline"><div className="section-top"><h3>The baseline stays in view</h3><Source source={source} /></div><p className="subtle">{comparison.scenarioId} · matched evaluator + manifest</p>
    <div className="table-scroll"><table><thead><tr><th scope="col">Raw result</th><th scope="col">Tuned baseline</th><th scope="col">Selected proposal</th></tr></thead><tbody>{rows.map(([name, before, after]) => <tr key={name}><th scope="row">{name}</th><td>{before}</td><td>{after}</td></tr>)}</tbody></table></div>
    <p className="baseline-win">{wins.length ? `Baseline advantage. It ${wins.join(' and ')}.` : 'No baseline advantage on cost, completed jobs, or late job-hours in this scenario.'}</p>
  </aside>;
}

function RuleList({ version, other, source }) {
  const policy = version?.policy;
  if (!policy) return <p>Parent policy unavailable.</p>;
  if (!version.policyValid) return <article className="policy"><div className="section-top"><h3>{label(version)}</h3><Source source={source} /></div><p className="small">Invalid proposal. The evaluator rejected this policy. Structured rule diff unavailable.</p><pre>{JSON.stringify(policy, null, 2)}</pre></article>;
  const condition = c => `${c.field} ${c.op} ${typeof c.value === 'object' ? `${c.value.field} × ${c.value.times} + ${c.value.plus}` : c.value}`;
  return <article className="policy"><div className="section-top"><h3>{label(version)}</h3><Source source={source} /></div><p className="mono small">{versionLabel(version)}</p>
    <div className="context-fields">{policy.context_fields.map(field => <code key={field} className={other && !other.policy.context_fields?.includes(field) ? 'added' : ''}>{other && !other.policy.context_fields?.includes(field) ? '+ ' : ''}{field}</code>)}{other?.policy.context_fields?.filter(field => !policy.context_fields.includes(field)).map(field => <code key={field}>− {field} removed</code>)}</div>
    <ol>{policy.rules.map((rule, index) => {
      const changed = other && JSON.stringify(rule) !== JSON.stringify(other.policy.rules?.[index]);
      return <li key={index} className={changed ? 'changed' : ''}><code>{rule.when.map(condition).join(' AND ') || 'always'}</code><span>request <b>{fmt(rule.power * 100)}%</b></span></li>;
    })}</ol><p className="small">Otherwise request {fmt(policy.default_power * 100)}%. {other && policy.default_power !== other.policy.default_power ? `Changed from ${fmt(other.policy.default_power * 100)}%. ` : ''}First matching rule wins.</p>
  </article>;
}

function Lines({ hours, keys, domain, title, unit, source, events = false }) {
  const width = 940, height = 205, left = 60, right = 14, top = 16, bottom = 34;
  const first = hours[0].h, last = hours.at(-1).h;
  const x = h => left + (h - first) / Math.max(1, last - first) * (width - left - right);
  const y = value => top + (domain[1] - value) / Math.max(1, domain[1] - domain[0]) * (height - top - bottom);
  return <div className="chart"><div className="section-top"><h4>{title}</h4><Source source={source} /></div><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. ${unit}, hours ${first} to ${last}.`}>
    {events && hours.filter(h => h.event).map(h => <rect key={h.h} x={x(h.h)} y={top} width={Math.max(2, x(first + 1) - x(first))} height={height - top - bottom} fill="#e8ecf2" />)}
    {[domain[0], (domain[0] + domain[1]) / 2, domain[1]].map(value => <g key={value}><line x1={left} y1={y(value)} x2={width - right} y2={y(value)} stroke="#dfe3e9" /><text x={left - 9} y={y(value) + 4} textAnchor="end">{fmt(value)}</text></g>)}
    {keys.map(({ key, dash, color, width: strokeWidth }) => <polyline key={key} points={hours.map(hour => `${x(hour.h)},${y(hour[key])}`).join(' ')} fill="none" stroke={color} strokeWidth={strokeWidth ?? 2} strokeDasharray={dash} />)}
    {[0, 0.25, 0.5, 0.75, 1].map(fraction => { const h = Math.round(first + fraction * (last - first)); return <text key={fraction} x={x(h)} y={height - 10} textAnchor="middle">h {h}</text>; })}
  </svg><div className="legend"><span>{unit}</span>{keys.map(key => <span key={key.key}><i style={{ borderColor: key.color, borderTopStyle: key.dash ? 'dashed' : 'solid' }} />{key.label}</span>)}{events && <span><i className="event-key" /> event hour</span>}</div></div>;
}

function Behavior({ comparison, source }) {
  const eventHour = comparison.hours?.find(hour => hour.before?.event)?.h ?? 12;
  const defaultStart = Math.max(0, Math.floor((eventHour - 12) / 24) * 24);
  const [start, setStart] = useState(defaultStart);
  useEffect(() => setStart(defaultStart), [comparison.scenarioId, comparison.version._id, defaultStart]);
  if (comparison.unavailable) return <p role="status">{comparison.unavailable}</p>;
  if (!comparison.hoursAvailable) return <p role="status">Matched hourly records unavailable. Both runs need the same hour keys.</p>;
  const all = comparison.hours;
  const first = all[0].h, last = all.at(-1).h;
  const windowStart = Math.min(Math.max(first, start), Math.max(first, last - 95));
  const visible = all.filter(hour => hour.h >= windowStart && hour.h < windowStart + 96);
  const power = [{ key: 'requested_kw', label: 'Requested', color: '#8e98aa', dash: '5 5' }, { key: 'executed_kw', label: 'Executed', color: '#2855d9', width: 2.8 }, { key: 'overhead_kw', label: 'Warm-up overhead', color: '#17202e' }];
  const before = visible.map(hour => hour.before), after = visible.map(hour => hour.after);
  const priceDomain = [Math.min(0, ...before.map(h => h.price)), Math.max(1, ...before.map(h => h.price))];
  return <><div className="window-control"><label htmlFor="hour-window">Same 96-hour window <b>h {windowStart}–{visible.at(-1).h}</b></label><input id="hour-window" type="range" min={first} max={Math.max(first, last - 95)} step="24" value={windowStart} onChange={event => setStart(Number(event.target.value))} /><span className="small">Drag through all {all.length} recorded hours. Every job remains listed below.</span></div>
    <Lines hours={before} keys={power} domain={[0, 700]} title="Before · frozen baseline requests and actual draw" unit="kW" source={source} events />
    <Lines hours={after} keys={power} domain={[0, 700]} title={`After · ${comparison.version._id} on the same hours`} unit="kW" source={source} events />
    <Lines hours={before} keys={[{ key: 'price', label: 'CAISO day-ahead price', color: '#2855d9' }]} domain={priceDomain} title="Shared operating conditions · electricity price" unit="$/MWh" source={source} events />
    <Lines hours={before} keys={[{ key: 'safety_limit_kw', label: 'Training safety limit', color: '#17202e' }, { key: 'inference_kw', label: 'Inference demand', color: '#8e98aa', dash: '5 5' }]} domain={[0, 700]} title="Shared operating conditions · event safety" unit="kW" source={source} events />
    <div className="jobs"><div className="section-top"><h3>Every job, from arrival to completion</h3><Source source={source} /></div><p className="subtle">Hour offsets from scenario start. Work during hour N completes at the end of h N, at offset N + 1. Deadlines are hour boundaries. Unfinished jobs have no completion hour.</p>
      {!comparison.jobsAvailable ? <p>Job outcomes unavailable in these recorded runs. Export the stored simulator jobs to enable this view.</p> : <div className="table-scroll job-scroll"><table><thead><tr><th scope="col">Job</th><th scope="col">Arrival</th><th scope="col">Deadline</th><th scope="col">Baseline completion</th><th scope="col">Proposal completion</th><th scope="col">Late hours baseline → proposal</th></tr></thead><tbody>{comparison.jobs.map(({ id, before: b, after: a }) => <tr key={id} className={b.late_h || a.late_h ? 'job-late' : ''}><th scope="row">{id}</th><td>h {b.arrive_h}</td><td>h {b.deadline_h}</td><td>{b.done_h === null ? 'Unfinished' : `End of h ${b.done_h}`}</td><td>{a.done_h === null ? 'Unfinished' : `End of h ${a.done_h}`}</td><td>{b.late_h} → {a.late_h}</td></tr>)}</tbody></table></div>}
    </div></>;
}

function Lineage({ data }) {
  if (!data.evolve_runs.length) return null;
  const featured = [data.versions.get(data.focus?.version), data.versions.get(data.featured_rejection)].filter(Boolean);
  return <Panel n="Evolution history" title="Two runs. One recorded lineage." source={data.source}>
    <p className="section-intro">Generation numbers restart for each evolve run. Parent links show which policy each proposal changed.</p>
    <div className="featured-verdicts">{featured.map(version => <article key={version._id}><h3>{version.verdict.accepted ? 'Featured repair' : 'Featured rejection'} · {versionLabel(version)}</h3><p className="small">Evaluator reasons, verbatim</p>{version.verdict.reasons.map((reason, index) => <p key={index}>{reason}</p>)}</article>)}</div>
    {data.evolve_runs.map(group => <div className="evolve-run" key={group.run}><h3>Evolve run {group.run}</h3><ol>{group.versions.map(id => {
      const version = data.versions.get(id);
      return <li key={id}><strong>{versionLabel(version)}</strong><span>{version.verdict?.accepted ? `Accepted ${version.acceptance}` : version.verdict ? 'Rejected' : 'Not evaluated'} · parent {versionLabel(data.versions.get(version.parent))}</span></li>;
    })}</ol></div>)}
  </Panel>;
}

function FinalScoreboard({ data }) {
  if (!data.final_results.length) return null;
  return <Panel n="Final evaluation" title="All seven pinned versions, on the final scenarios." source={data.source}>
    <p className="section-intro">{data.allFinalDeadlines ? 'Every version met every final deadline. The repair evidence is the validation verdict.' : 'Final deadline outcomes differ. The repair evidence is the validation verdict.'}</p>
    <p className="small subtle">The five promoted versions and two labeled references share the same final evaluator, manifest, and three scenarios. Training electricity cost is summed across those scenarios.</p>
    <div className="table-scroll"><table className="scoreboard"><thead><tr><th scope="col">Pinned version</th><th scope="col">Role</th><th scope="col">Final jobs / late job-hours</th><th scope="col">Training electricity</th></tr></thead><tbody>{data.final_results.map(row => {
      const results = Object.values(row.scenarios);
      const sum = key => results.reduce((total, result) => total + result.totals[key], 0);
      const version = data.versions.get(row.version);
      return <tr key={row.version}><th scope="row">{version ? versionLabel(version) : row.version}</th><td>{row.role === 'reference' ? `Reference · ${row.author === 'control' ? 'hand-authored control' : 'baseline'}` : row.version === data.focus?.baseline ? 'Promoted · tuned baseline' : `Promoted · accepted ${row.acceptance}`}</td><td>{sum('jobs_completed')} / {sum('jobs_total')} jobs · {sum('late_job_hours')} late job-hours</td><td>{money(row.training_cost)}</td></tr>;
    })}</tbody></table></div>
    <p className="small subtle">Evaluator {data.final_results[0].identity.evaluator_version} · scenarios {data.final_results[0].identity.scenario_ids.join(', ')} · manifest <code>{data.final_results[0].identity.manifest_sha256.slice(0, 12)}</code></p>
  </Panel>;
}

function Story({ data }) {
  const [proposalId, setProposalId] = useState(data.focus?.version ?? data.proposals[0]?._id ?? '');
  const proposal = data.versions.get(proposalId);
  const choices = [...new Set(data.runList.filter(run => run.version === proposalId && run.split === 'validation').map(run => run.scenario))].sort();
  const [scenarioId, setScenarioId] = useState(data.focus?.scenario ?? choices[0] ?? '');
  const activeScenario = choices.includes(scenarioId) ? scenarioId : choices[0];
  if (!proposal) return <main><Panel n="Replay" title="No recorded proposal is available" source={data.source}><p>Export a version with a parent and its evaluated runs to tell the repair story.</p></Panel></main>;
  const comparison = data.comparison(proposalId, activeScenario);
  const pinned = data.source === 'recorded evaluation replay' && data.focus;
  const behavior = pinned ? data.comparison(data.focus.version, data.focus.scenario) : comparison;
  const problemRun = pinned
    ? data.runList.find(run => run.version === data.focus.baseline && run.scenario === 'dev-13-high')
    : data.runList.filter(run => run.version === proposal.parent && run.split === 'dev').sort((a, b) => b.totals.late_job_hours - a.totals.late_job_hours)[0];
  const problem = problemRun ? data.comparison(pinned ? data.focus.version : proposalId, problemRun.scenario) : null;
  const totals = problemRun?.totals;
  const verdict = proposal.verdict;
  const parent = data.versions.get(proposal.parent);
  const evaluationTitle = !verdict ? 'The evaluation result is not available.' : !verdict.accepted ? 'The evaluator rejected this proposal.'
    : verdict.fixed.length ? 'Deadlines restored. The electricity bill stays visible.'
      : 'Lower cost. The same validation pass set.';
  return <><header className="masthead"><a href="#top" className="wordmark">flex<span>.</span></a><span>Recursive Harnessing / power scheduling</span><Source source={data.source} /></header><main id="top">
    <section className="hero"><div className="section-top"><p className="eyebrow">A schedule should adapt when its world changes</p><Source source={data.source} /></div><h1>Restarts got expensive.<br /><span>The rules had to change.</span></h1><p className="intro">The same training work. A larger warm-up bill. Flex tests a policy repair against a frozen evaluator, with the tuned baseline beside every result.</p><div className="hero-note">{data.source === 'fixture' ? 'Simulator fixture. The proposals below are hand-authored controls, not supervisor-generated repairs.' : 'Read-only evaluation records. Author labels distinguish supervisor proposals from hand-authored controls.'}</div><a href="#problem" className="story-link">Follow the repair <span aria-hidden="true">↓</span></a></section>
    <div id="problem"><Panel n="01 / observed problem" title="Stopping was cheap. Starting again is not." source={data.source}><p className="section-intro">{problemRun?.scenario ?? 'Development run unavailable'} · the parent scheduler under the changed conditions. Warm-up draws electricity but completes no training work.</p><div className="metrics"><Metric value={fmt(totals?.jobs_late)} name="late jobs" note={`${fmt(totals?.late_job_hours)} late job-hours`} /><Metric value={fmt(totals?.restarts)} name="restarts" /><Metric value={fmt(totals?.overhead_kwh)} name="warm-up kWh" /></div><div className="diagnosis"><h3>The simulator’s diagnosis</h3>{problemRun?.diagnosis?.length ? problemRun.diagnosis.map((line, index) => <p key={index}>{line}</p>) : <p>Simulator diagnosis unavailable in this run. Totals are not a substitute for diagnosis lines.</p>}</div><Baseline comparison={problem} source={data.source} /></Panel></div>
    <Lineage data={data} />
    <Panel n="02 / proposed change" title="Change the policy. Keep the evaluator fixed." source={data.source}><div className="selection"><label htmlFor="proposal">Inspect a proposal</label><select id="proposal" value={proposalId} onChange={event => setProposalId(event.target.value)}>{data.proposals.map(version => <option key={version._id} value={version._id}>{versionLabel(version)} · {version.verdict?.accepted ? `accepted ${version.acceptance}` : version.verdict ? 'rejected' : 'not evaluated'}</option>)}</select></div><p className="author-label">{label(proposal)} · {versionLabel(proposal)} · parent {versionLabel(parent)}</p><div className="proposal-copy"><div><h3>Rationale</h3><p>{proposal.rationale}</p></div><div><h3>Prediction</h3><p>{proposal.predicted}</p></div></div><p className="small subtle">Added context fields have a + marker. Shaded rules differ at this position. Rule order is behavior.</p><div className="policy-grid"><RuleList version={parent} source={data.source} /><RuleList version={proposal} other={parent} source={data.source} /></div><Baseline comparison={comparison} source={data.source} /></Panel>
    <Panel n="03 / evaluation" title={evaluationTitle} source={data.source}><div className="metrics"><Metric value={verdict ? verdict.accepted ? `Accepted ${proposal.acceptance}` : 'Rejected' : 'Unavailable'} name="fixed evaluator verdict" /><Metric value={verdict ? `${verdict.fixed.length} / ${verdict.regressed.length}` : 'Unavailable'} name="fixed / regressed scenarios" /><Metric value={signed(verdict?.cost_delta_pct)} name="training electricity cost change" note="Against the actual parent across the evaluator’s feasible comparison set" /></div><div className="verdict-reasons"><h3>Evaluator reasons, verbatim</h3>{verdict?.reasons.map((reason, i) => <p key={i}>{reason}</p>) ?? <p>Verdict unavailable. This proposal has no recorded evaluator result.</p>}<p><b>Fixed</b> {verdict?.fixed.join(', ') || 'None recorded'}</p><p><b>Regressed</b> {verdict?.regressed.join(', ') || 'None recorded'}</p></div><p className="small subtle">Acceptance prioritizes physical limits, then deadlines and completed work, then training electricity cost. It does not mean the tuned baseline lost on cost.</p><Baseline comparison={comparison} source={data.source} /></Panel>
    <Panel n="04 / changed behavior" title="Same hours. Same jobs. Different decisions." source={data.source}><div className="selection">{pinned ? <p><b>{data.focus.scenario}</b> · {data.focus.baseline} → {versionLabel(data.versions.get(data.focus.version))}</p> : <><label htmlFor="scenario">Validation scenario</label><select id="scenario" value={activeScenario ?? ''} onChange={event => setScenarioId(event.target.value)}>{choices.map(id => <option key={id}>{id}</option>)}</select></>}</div><p className="section-intro">The frozen baseline and featured repair share one evaluator, manifest, workload, and time axis. The policy diff and verdict compare the proposal with its actual parent. Requested power is bounded by safety and the work the queue can absorb.</p><Baseline comparison={behavior} source={data.source} /><Behavior comparison={behavior} source={data.source} /></Panel>
    <FinalScoreboard data={data} />
    <footer><Source source={data.source} /><p>{data.runs.size} runs · evaluator {comparison.candidate?.identity.evaluator_version ?? 'unavailable'} · manifest <code>{comparison.candidate?.identity.manifest_sha256.slice(0, 12) ?? 'unavailable'}</code></p><p>Simulated training workload. Real CAISO NP15 day-ahead prices. {data.final_results.length ? 'Final scores are held-out results. The repair evidence comes from validation.' : 'Development and validation only. No final-result claim.'}</p><p className="small">Replay generated {data.generated_at ? new Date(data.generated_at).toLocaleString() : 'at an unavailable time'}.</p></footer>
  </main></>;
}

function App() {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    fetch('/replay.json', { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error('Static replay unavailable. Export replay.json first.');
      return response.json();
    }).then(input => {
      setState({ data: organizeReplay(input) });
    }).catch(error => { if (error.name !== 'AbortError') setState({ error: error.message }); });
    return () => controller.abort();
  }, []);
  if (state.error) return <main className="error" role="alert"><p className="eyebrow">Flex / replay unavailable</p><h1>There is no result to show.</h1><p>{state.error}</p><p>Nothing has been replaced with fixture data.</p></main>;
  if (state.loading) return <main className="error" role="status"><p>Loading the recorded story…</p></main>;
  return <Story data={state.data} />;
}

createRoot(document.getElementById('root')).render(<App />);
