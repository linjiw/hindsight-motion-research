"""Aggregate-only figure; contains no source or executed motion trajectories."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "results/complete_task.json").read_text())
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.6), gridspec_kw={"width_ratios": [1.8, 1]})
groups = [(s, c) for s in ("00976", "00265") for c in ("clear", "beam")]
colors = ["#1c6153", "#bb592e"]
for j, method in enumerate(("continuous", "linear29")):
    selected = [next(r for r in data["rows"] if (r["source_clip"], r["condition"], r["method"]) == (*g, method)) for g in groups]
    times = [r.get("completion_time_s", 0) for r in selected]
    bars = axes[0].bar(np.arange(4) + (j-.5)*.34, times, .34, color=colors[j],
                       label="Continuous" if j == 0 else "Linear29 + reset anchor")
    for bar, row in zip(bars, selected):
        label = "PASS" if row.get("success") else ("FAIL" if row["status"] == "completed" else "UNRUN")
        axes[0].text(bar.get_x()+bar.get_width()/2, bar.get_height()+.08, label,
                     ha="center", va="bottom", fontsize=8)
axes[0].set_xticks(np.arange(4), [f"{s}\n{c}" for s, c in groups])
axes[0].set_ylabel("Recorded task duration (s)")
axes[0].set_ylim(0, max(r.get("completion_time_s", 0) for r in data["rows"])+1.3)
axes[0].set_title("Prescribed reference → passage → recovery → stop", loc="left", pad=18)
axes[0].legend(frameon=False, fontsize=9, loc="upper left")
audit = data["codec_audit"][0]
duration = audit["frames"]*.02
joint = [audit["frames"]*29*32/duration/1000, audit["joint_payload_bits"]/duration/1000]
root = [audit["common_root_bits"]/duration/1000]*2
anchor = [0, audit["reset_anchor_bits"]/duration/1000]
axes[1].bar([0, 1], joint, color="#1c6153", label="Joint payload")
axes[1].bar([0, 1], root, bottom=joint, color="#9cb997", label="Original root")
axes[1].bar([0, 1], anchor, bottom=np.array(joint)+root, color="#bb592e", label="Reset anchor")
axes[1].set_xticks([0, 1], ["Continuous", "Linear29"])
axes[1].set_ylabel("Logical payload (kbit/s)")
axes[1].set_title("Charge root and boundary information", loc="left", pad=18)
axes[1].legend(frameon=False, fontsize=9)
fig.suptitle("Complete-task reference pilot · development evidence", x=.07, ha="left", fontsize=16, fontweight="bold")
fig.text(.07, .02, "8 scheduled episodes · 2 prior clips · 0.50 m goal / 0.10 m/s / 1 s hold\n"
         "Same frozen teacher; full future reference supplied. No held-out, causal-composer or learned-policy claim.", fontsize=9, color="#4a5651")
fig.subplots_adjust(left=.07, right=.98, bottom=.22, top=.80, wspace=.32)
fig.savefig(ROOT / "artifacts/complete_task.png", dpi=180)
plt.close(fig)
