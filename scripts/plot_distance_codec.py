"""Plot measured admission resources beside the explicitly unrun comparison."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'results/distance_codec.json').read_text())
admission = json.loads((root / 'results/distance_followup.json').read_text())['native_admission']
assert data['native_attempts'] == 0 and data['unrun'] == 4
fig = plt.figure(figsize=(12, 6.3))
grid = fig.add_gridspec(2, 2, width_ratios=[1.2, 1], hspace=.52, wspace=.2)
left = fig.add_subplot(grid[:, 0]); left.axis('off')
left.text(0, .95, 'Four registered cases. Zero launches.', fontsize=15, weight='bold', va='top')
left.text(0, .82, 'Original / +0.60 m beam goal\nSame frozen composer, scene, motor and scorer', fontsize=11, linespacing=1.5)
table = left.table(cellText=[['Original goal', 'UNRUN', 'UNRUN'], ['Goal +0.60 m', 'UNRUN', 'UNRUN']],
    colLabels=['Task', 'Continuous', 'Linear29'], colWidths=[.38, .31, .31], cellLoc='center', bbox=[0, .47, .96, .25])
table.auto_set_font_size(False); table.set_fontsize(10)
for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor('#ccd2cb'); cell.set_facecolor('#e9eee5' if row == 0 else '#f6f5ef')
    if row and col: cell.get_text().set_color('#725e4c')
left.text(0, .35, 'OFFLINE CHECKS COMPLETED', fontsize=10, color='#1c6153', weight='bold')
left.text(0, .26, '792 historical continuous states replay exactly.\nAll four decoded arrays re-derived exactly.\nFive committed frames preserved.\nNo new codec task outcome or physical retention claim.', fontsize=10, linespacing=1.7, va='top')
samples = admission['samples']; times = [s['elapsed_seconds'] for s in samples]
for i, (key, threshold, label, color) in enumerate([
    ('free_gpu_mib', admission['required_gpu_mib'], 'Free GPU memory (GiB)', '#1c6153'),
    ('available_host_mib', admission['required_host_mib'], 'Available host memory (GiB)', '#bd693c')]):
    ax = fig.add_subplot(grid[i, 1])
    values = [s[key] / 1024 for s in samples]
    ax.plot(times, values, marker='o', markersize=3, color=color)
    ax.axhline(threshold / 1024, color='#777e75', ls='--', lw=1)
    ax.text(300, threshold / 1024 + .08, 'required', ha='right', fontsize=9, color='#555e55')
    ax.set_xlim(0, 300); ax.set_ylabel(label); ax.set_xlabel('Resource wait elapsed (s)')
    ax.spines[['top', 'right']].set_visible(False)
fig.suptitle('Distance-codec experiment: prepared, resource-deferred', x=.035, ha='left', fontsize=17, weight='bold')
fig.text(.035, .04, '15 samples over the registered 300 s wait; none met both thresholds. Admission requires two ready samples 20 s apart.\n'
    'Zero native attempts, control steps, retries or training. Resource deferral is not a robot/task failure.', fontsize=10, color='#43514c')
fig.subplots_adjust(left=.04, right=.96, top=.87, bottom=.2)
fig.savefig(root / 'artifacts/distance_codec.png', dpi=180)
plt.close(fig)
