"""Publish aggregate outcomes, including failed and censored endpoint measures."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'results/selection_boundary_admission02.json').read_text())
colors = {'continuous': '#1c6153', 'linear29': '#bd693c'}
labels = {'earlier200-beam': 'Beam 20 cm earlier', 'lower100-beam': 'Ceiling 10 cm lower', 'farther600-beam': 'Goal 60 cm farther'}
fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), gridspec_kw={'width_ratios': [1.8, 1]})
for i, row in enumerate(data['rows']):
    color = colors[row['method']]
    if row['status'] != 'completed':
        axes[0].text(0.1, i, row['status'], va='center')
        continue
    axes[0].barh(i, row['completion_time_s'], color=color, height=.6, alpha=1 if row['success'] else .45)
    outcome = 'PASS' if row['success'] else ('CONTACT' if row['max_obstacle_force_n'] > 0 else 'DEADLINE')
    annotation = f"{outcome} · {row['completion_time_s']:.2f} s"
    if outcome == 'CONTACT':
        annotation += f" · {row['max_obstacle_force_n']:.0f} N"
    axes[0].text(row['completion_time_s'] + .12, i, annotation, va='center', fontsize=9)
    axes[1].scatter(row['final_goal_distance_m'], i, color=color, marker='o' if row['success'] else 'x', s=50)
    axes[1].text(row['final_goal_distance_m'] + .045, i, f"{row['final_goal_distance_m']:.3f} m", va='center', fontsize=9)
axes[0].set_yticks(range(6), [labels[r['condition']] + '\n' + ('Continuous' if r['method'] == 'continuous' else 'Linear29') for r in data['rows']], fontsize=9)
axes[1].set_yticks([])
axes[0].set_xlim(0, 14)
axes[0].set_xlabel('Elapsed execution (s); failures are not completions')
axes[1].set_xlabel('Goal distance at stop / censoring (m)')
axes[1].set_xlim(0, max(r.get('final_goal_distance_m', 0) for r in data['rows']) + .5)
axes[0].axvline(10, color='#7c837c', ls=':', lw=1)
axes[1].axvline(.5, color='#7c837c', ls='--', lw=1)
axes[1].text(.5, -.65, 'Goal tolerance', fontsize=9, ha='center')
for ax in axes:
    ax.set_ylim(5.65, -.8)
    ax.spines[['top', 'right']].set_visible(False)
fig.suptitle('Both representations retain the three tested task outcomes', x=.025, ha='left', fontsize=15, fontweight='bold')
fig.text(.025, .89, f"COMPLETED SCREEN: {data['completed_episodes']} / {data['scheduled_cases']} executed; all four task failures retained", fontsize=11, color='#6c452b')
fig.text(.025, .04, f"{data['new_native_attempts']} new attempts + {data['reused_native_attempts']} prior executions · {data['control_steps']:,} total control steps · zero training\n"
         'Three development contexts selected after a prior screen; one ancestry and seed. One pass, one contact and one deadline per method.\n'
         'Same continuous planner bank. This diagnostic does not establish equivalence or generalization.', fontsize=9, color='#43514c')
fig.subplots_adjust(left=.2, right=.98, top=.86, bottom=.22, wspace=.13)
fig.savefig(root / 'artifacts/selection_boundary_admission02.png', dpi=180)
plt.close(fig)
