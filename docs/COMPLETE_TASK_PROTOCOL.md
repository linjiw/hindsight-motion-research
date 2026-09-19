# Complete-task reference support: continuous versus Linear29 v1

Registered September 18, 2026, before new native execution. Implements **row 1** of the [research plan](RESEARCH_PLAN_zh.md) and [adopted guidance](RESEARCH_GUIDANCE_20260918_zh.md). The user requested proceeding with this experiment. The separate [machine-readable registration](../configs/complete_task_v1.plan.json) caps this development pilot at eight attempts; the historical 168-attempt balance is untouched.

## Question and interpretation

Can an existing complete reference execute approach, low passage, full-body exit, upright recovery and sustained goal stopping under the same controller? Does replacing its full-rate joints with Linear29 lose that ability? Continuous failure points first to task/reference/controller support. Paired continuous success and Linear29 failure, with matching reset state and dynamics, supports investigating representation loss within this route. Both succeeding warrants incoming-state and causal-composer tests, not a claim that compression never matters.

These are **prescribed full-reference diagnostics**, not autonomous navigation. Neither method chooses its reference or generates root goals. No LLM or learned codec is involved. The main 2×3 matrix's other two rows remain unrun.

## Frozen inputs and comparison

Reuse source clips 00976 and 00265 from the existing adjacent project's source-qualification packet. Both have a six-second local-duck reference including an appended two-second endpoint hold; its physical success must still be measured. They are authored descendants of existing generated/repaired motions, not new human demonstrations. Their broader ancestry independence is unresolved. They are development inputs; all outcomes stay in this repository's separate ledger.

For each source, use its existing clear/early task and the previously authored +5 mm swept-envelope low beam. These geometries were selected using prior development evidence, before this codec comparison. This is deliberately a support pilot, not a scene-generalization test or a new geometry search. Use one fixed seed, one native environment and the same teacher for each pair. No repeated runs count as independent evidence.

The controller is the adjacent task-qualified SONIC teacher, SHA-256 `afd649cfbbfd28833550e11a0f8c3b7a5f6a05ee8b4021dd0dac97a6f94733ce`, frozen across methods. It differs from this repository's earlier `e6bdab…` teacher, so historical success rates are not pooled. The complete-task runner disables reference-fidelity termination and automatic reference-end resets; it stops on measured task completion, contact, a fall guard or deadline.

**Continuous:** full 50 Hz root/quaternion and 29 joints. **Linear29:** 12-bit signed joint knots at frames 2,7,… (10 Hz), frozen training-only scales from the existing clearance study, linear interpolation and constant boundary extrapolation. No new scale fitting. Report clipping and offline error. Root and quaternion remain identical at 50 Hz and are fully charged.

Both routes use the same prescribed reset position/velocity. Linear29 retains the first two exact joint frames as an explicit reset anchor, charged at 2×29×32 bits. This replaces the historical 0.6 s original entry plus 0.6 s blend; no such entry bridge is used. This is **Linear29 with a two-frame reset anchor**, not an unassisted causal representation. Initial joint velocities, root state, 930D proprioceptive history, physical parameters and Torch RNG must match within 1e-5/numerically identical RNG hashes. Reference futures differ by design and are not part of the matched causal observation criterion.

## Task profile and scoring

Retain the already implemented profile `whole_body_passage_upright_recovery_goal050_stop_v1`: 0.50 m 3D goal tolerance, speed ≤0.10 m/s, 15 upright recovery ticks followed by 50 new hold ticks, at 50 Hz. The earlier research suggestion of 0.25 m was an unqualified candidate; it is **not silently substituted for or claimed by this pilot**. A stricter profile would be a separate comparison. Keeping the established profile isolates the representation change.

Require ordered entry/crossing, full modeled collision-envelope exit at least 2 cm beyond the beam's trailing edge, source-specific frozen pelvis-height range and torso-tilt limit, upright recovery, then uninterrupted goal hold. Low-beam tasks additionally require a sampled lowered body envelope while crossing; clear tasks retain their virtual gate and do not require ducking. All modeled links, including hands/feet, count for exit. Enclosing bounds are conservative and sampled, not continuous collision certificates.

Pair-resolved normal contacts are recorded at 200 Hz. Foot-floor contact is allowed; any obstacle or non-foot floor force above 1 N fails. Absolute pelvis height below 0.25 m fails. Maximum horizon is 500 control steps/10 s. No hidden demonstration fidelity threshold enters complete-task success. Record passage, recovery, hold, final goal distance, contacts, fall, timeout and their timestamps separately.

## Order, resource gate and stopping

First execute all four clear runs (continuous and Linear29 for each source). A source's two beam runs require its continuous clear success and a matched clear-pair entry audit. Linear29 clear failure is retained and does not automatically censor the paired beam comparison. If the gate fails, both beam cases remain explicitly unrun. No replacement source, reference, geometry, threshold or seed is chosen after an outcome.

Use the existing serial resource gate: ≥12,000 MiB free GPU and ≥16,384 MiB available host memory for two checks 20 s apart. Wait at most 300 s per admission; timeout defers remaining work. Each native launch has a 600 s process limit and counts as an attempt even if startup fails. Infrastructure failure stops the queue; there are no retries. Maximum total budget is eight attempts, 4,000 scored control steps and 16,000 physics contact samples (plus simulator setup overhead). No training. A single-use execution receipt prevents rerunning the packet.

Pin reference, codec scale, teacher/config, scene, collision asset, task/config/command and actual external source contents before launch. Save code snapshots and logs. The sibling working tree is only read; its uncommitted changes are not modified or merged. Local references and trajectories stay out of Git and the website.

## Audit and next decision

Report all eight scheduled cells as success/failure/unrun/infrastructure failure. The denominator is not conditioned on a favorable codec result. Audit each executed method pair's full initial state, history, dynamics and RNG; mismatch invalidates a representation attribution. Report exact paired gains/losses and costs, not a generalized success rate or a confidence interval from two development clips.

Preserve the complete-task scorer's support evidence, but release no positive student-training labels: the adapter clears imitation query masks and writes an explicit development-only contract. Existing external `train` naming is only an internal recorder compatibility shim, not authorization to use these rows for training.

If complete continuous support is reliable, register the next **actual incoming-state** test with qualified snapshots or exact deterministic prefix replay that restores controller history. Only after that should the causal composer row remove supplied reference/root assistance. If continuous fails, diagnose its failed task stage before adding a tokenizer or training a student.

```bash
RESEARCH_PY=/home/linjiw/groot-wbc-sonic-sim-trackb/.venv_research/bin/python
PYTHONPATH=src:/home/linjiw/groot-wbc-sonic-sim-trackb "$RESEARCH_PY" \
  -m hindsight_motion.complete_task prepare runs/complete_task_20260918_v1
PYTHONPATH=src "$RESEARCH_PY" -m hindsight_motion.complete_task \
  run runs/complete_task_20260918_v1
```

Preparation and execution both refuse overwrite/relaunch. Native execution uses `.venv_isaaclab`, not the analysis interpreter running the serial queue.
