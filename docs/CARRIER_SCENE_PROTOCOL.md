# Qualified carrier → critical scene: CMU/107

This bounded follow-up tests whether the original/tuck carrier qualified in the
latest coverage screen supplies an obstacle-dependent behavior choice outside
the existing KIT acquisition sources. The executable registration is
[`configs/carrier_scene_v1.plan.json`](../configs/carrier_scene_v1.plan.json),
created before geometry search and native execution.

The two plausible outcomes distinguish teacher support from scene utility:
empty-plane execution may provide sufficient arm-clearance contrast, or the two
supported behaviors may have too little robust separation to make an obstacle
informative. Even admitted geometry can fail when executed with an obstacle.

## Frozen comparison

Reuse the existing CMU/107 `carrier00` references and six measured preflight
episodes: original and tuck, each at three registered lateral offsets. Do not
rename the original motion “wide,” construct new edits, or retrain a codec.
Check reference, native-motion, teacher, and episode identities before use.
Retain the existing nominal teacher/robot/decoder and actor/teacher/target split.

Evaluate the historical 145-candidate portal grid: five times (1.4–2.6 s) and
29 gap widths (0.44–1.00 m in 0.02 m steps). The target's sampled enclosing
collision boxes must clear by at least 3 cm in every measured repetition. An
analytic arm primitive's inscribed ball must overlap an obstacle by at least
1 cm in every original-motion repetition. A nonpositive enclosing-box bound
alone is not a proven collision. Full trajectories, including approach and exit,
enter the tests. These remain sampled bounds, not continuous certificates.

Both continuations must also have at least 3 cm sampled clearance when the gap
is increased by 0.60 m or the portal is displaced laterally by 2.0 m. The removed
condition has no obstacles. Select the largest worst-repetition critical slack;
break ties by frame then gap. If nothing passes, retain all rejections and stop
before simulation. No extra search or relaxed threshold is authorized by this
registration.

## Native execution and budget

One admitted portal receives four conditions × two continuations × three
original preflight offsets = **24 main episodes maximum**, in one serial launch.
The global main budget starts at 312/480 and would reach 336/480. No new preflight
or model training is scheduled. A launched infrastructure failure still consumes
the scheduled attempts; do not automatically retry.

Use the existing resource queue: two checks 20 seconds apart with ≥12,000 MiB
free GPU memory and ≥16 GiB available host RAM. This stage waits at most ten
minutes, then records deferral without launching. Do not interrupt other jobs.

A qualified panel needs all six control episodes plus tucked critical passage
to pass the existing tracking, contact, moving-goal and exit criteria; original
critical execution must have measured shoulder/elbow/wrist obstacle contact.
Measured entry states must agree within 10⁻⁵. Preserve contact isolation,
200-step validity, original 10 cm body/25 cm root thresholds and support masks.
Record every failure as well as every pass.

## Interpretation and subsequent work

This is one additional source-group acquisition attempt, selected after the
coverage screen. It is development evidence, not a held-out generalization test.
Successful qualification could increase canonical acquisition coverage by one
pair and one group; the 24 repeated episodes are not 24 independent tasks.

If the geometry fails, diagnose whether the carrier lacks a discriminating arm
envelope before spending simulation budget. If execution fails, distinguish
target/control tracking failures from missing arm contact and geometry mismatch.
If all panels pass, prioritize a registered equal-budget proposer comparison
(random placement, root-conditioned, continuous-body, token-conditioned) with a
common scorer. Student training remains gated on an ancestry-aware split and a
separate learner protocol; current positive student training is not authorized
by the data contract. Navigation, language, and world-model benefits remain open.

## Separately registered fixed-contrast follow-up

The first grid admitted **0/145** original/tuck candidates. This completed
negative result is retained unchanged in its proposal directory. The follow-up
[`carrier_contrast_v1.plan.json`](../configs/carrier_contrast_v1.plan.json)
was registered after that result, before constructing a different contrast.
It is a new study stage, not a replacement for the original comparison.

Apply the already existing `critical.edit_motion` wide preset to the same
unedited carrier, and repeat the fixed tuck preset. No angle search, retiming,
root modification, or threshold change is allowed. Preserve exact root/leg/waist
references and common entry/exit; the tuck reference must equal the earlier one.
The construction receipt records those checks and native serialization fidelity.

At most **six new preflight episodes in one launch** test wide and tuck at the
three unchanged offsets. If either continuation fails any repetition, stop
without obstacle generation. If both qualify, apply the same 145-grid and
worst-repetition gates, then at most 24 main episodes in one launch. Both stages
use the same resource gate and ten-minute wait limit, with no automatic launch
recovery. Preflight attempts and main attempts retain separate ledgers.

Any resulting advantage is for an engineered wide/tuck comparison. It must not
be described as the natural original motion's need to tuck, a new human intent
label, or held-out generalization.
