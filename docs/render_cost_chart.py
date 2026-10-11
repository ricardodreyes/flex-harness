#!/usr/bin/env python3
"""Run with the repository root and optional output directory as arguments."""
import json
import math
from pathlib import Path
import sys
from xml.sax.saxutils import escape

repo = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent
out.mkdir(parents=True, exist_ok=True)
final = json.loads((repo / 'results/final.json').read_text())
ablation = json.loads((repo / 'results/exploratory-keepwarm-ablation.json').read_text())
versions = ['v0', 'restart_aware', 'control', 'g5-e942f4']
expected_ids = ['final-31', 'final-32', 'final-33']
base_scenarios = final['v0']['scenarios']
for version in versions:
    result = final[version]
    assert result['identity']['scenario_ids'] == expected_ids, version
    scenarios = result['scenarios']
    assert list(scenarios) == expected_ids, version
    assert sum(s['totals']['jobs_total'] for s in scenarios.values()) == 38, version
    assert sum(s['totals']['jobs_completed'] for s in scenarios.values()) == 38, version
    for scenario_id, scenario in scenarios.items():
        totals = scenario['totals']
        assert scenario['passes'] and scenario['feasible'], (version, scenario_id)
        assert totals['late_job_hours'] == totals['jobs_late'] == totals['unfinished_kwh'] == 0, version
        assert math.isclose(totals['productive_kwh'], base_scenarios[scenario_id]['totals']['productive_kwh']), version
        assert math.isclose(totals['work_kwh'], totals['productive_kwh']), version
    assert math.isclose(result['training_cost'], sum(s['totals']['training_energy_cost'] for s in scenarios.values())), version
assert ablation['scenarios'] == expected_ids
assert 'after the freeze' in ablation['label']
champion = final['g5-e942f4']['training_cost']
assert math.isclose(champion, ablation['results']['g5-e942f4']['training_energy_cost'])
removed = ablation['results']['g5-e942f4 without 1% keep-warm rule']
for result in ablation['results'].values():
    assert result['jobs_completed'] == 38
    assert result['late_job_hours'] == result['unfinished_kwh'] == 0
assert removed['trickle_hours'] == 0
baseline = final['v0']['training_cost']
champion_saving = 100 * (1 - champion / baseline)
ablation_saving = 100 * (1 - removed['training_energy_cost'] / baseline)
assert f'{champion_saving:.2f}' == '12.18'
assert f'{ablation_saving:.2f}' == '4.28'
productive = sum(s['totals']['productive_kwh'] for s in base_scenarios.values())

parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">',
         '<title id="title">Same work, different electricity cost</title>',
         '<desc id="desc">Four frozen policies and one exploratory ablation completed all 38 jobs on time. Frozen champion saved 12.18 percent against v0. Removing its simulated keep-warm rule reduced savings to 4.28 percent.</desc>',
         '<rect width="1600" height="900" fill="#ffffff"/>']

def text(x, y, value, size=22, color='#182535', weight='normal', anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>')

text(64, 78, 'Same work, different electricity cost', 43, weight='bold')
text(64, 117, 'Three test workloads sharing one 12-day window of real California electricity prices.', 23, '#4b596a')
text(64, 157, f'ALL 38 JOBS ON TIME  /  {productive:,.2f} productive kWh in the frozen comparison', 20, '#185b47', 'bold')
text(64, 212, 'FROZEN COMPARISON', 16, '#617184', 'bold')
text(375, 212, 'Training electricity cost (USD)  ·  lower is better', 18, '#4b596a')
x0, width, maximum = 375, 970, 20000
for tick in range(0, 20001, 5000):
    x = x0 + tick / maximum * width
    for top, bottom in [(234, 565), (648, 728)]:
        parts.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="#e4e9ef" stroke-width="1"/>')
    text(x, 766, '$0' if tick == 0 else f'${tick // 1000}k', 19, '#617184', anchor='middle')
rows = [
    ('Original scheduler', 'v0', final['v0']['training_cost'], 278, '#8291a3', None),
    ('Restart-aware reference', 'restart_aware', final['restart_aware']['training_cost'], 363, '#8291a3', None),
    ('Control reference', 'control', final['control']['training_cost'], 448, '#8291a3', None),
    ('Frozen champion', 'g5-e942f4', champion, 533, '#1463df', f'{champion_saving:.2f}% lower than v0'),
    ('Without keep-warm rule', 'g5-e942f4 ablation', removed['training_energy_cost'], 683, '#b36a26', f'{ablation_saving:.2f}% lower than v0'),
]
for name, version, cost, y, color, saving in rows:
    text(64, y - 2, name, 21, weight='bold' if saving else 'normal')
    text(64, y + 23, version, 17, '#617184')
    bar_width = cost / maximum * width
    parts.append(f'<rect x="{x0}" y="{y - 27}" width="{bar_width:.3f}" height="52" rx="3" fill="{color}"/>')
    text(1536, y - 1 if saving else y + 8, f'${cost:,.2f}', 23, color if saving else '#182535', 'bold', 'end')
    if saving:
        text(1536, y + 23, saving, 17, color, anchor='end')
parts.append('<line x1="64" y1="594" x2="1536" y2="594" stroke="#c7cfd9" stroke-width="1"/>')
text(64, 626, 'EXPLORATORY ABLATION, AFTER THE FREEZE', 16, '#8c511b', 'bold')
text(64, 815, 'The 1% keep-warm rule is physically unvalidated. Jobs and restart costs are simulated.', 20, '#4b596a')
text(64, 852, 'Sources: results/final.json and results/exploratory-keepwarm-ablation.json  ·  Flex  ·  11 Oct 2026', 17, '#617184')
parts.append('</svg>')
svg = out / 'cost-comparison.svg'
svg.write_text('\n'.join(parts) + '\n')
print(f'PASS: 4 frozen policies; 38 jobs each; zero late hours; equal productive work {productive:,.2f} kWh.')
print(f'PASS: exploratory ablation completed 38 jobs; zero late hours; zero unfinished work.')
print(f'PASS: champion savings {champion_saving:.2f}%; ablation savings {ablation_saving:.2f}%.')
print(f'Wrote {svg}.')
