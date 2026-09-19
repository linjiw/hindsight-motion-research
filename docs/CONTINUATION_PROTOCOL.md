# Matched incoming-state continuation v1

Registered September 18, 2026, before native execution, following the user's request to continue the research plan. This is the first, unperturbed **same-phase handoff** subset of matrix row 2, after the [complete-reference pilot](COMPLETE_TASK_RESULTS_zh.md). It is not the whole switching/recovery/composer matrix. [Registration](../configs/continuation_v1.plan.json) is separate from both previous native ledgers.

## Question and fixed panel

Does a robot that reached an incoming state using continuous reference retain complete-task support when the next supplied reference is replaced with the same-phase Linear29 reconstruction? A continuous identity handoff controls for the adapter. Failure only under Linear29 could come from reconstruction loss or the abrupt reference update; this pilot does not separate these mechanisms. Success warrants a more demanding interface test, not new-codec training or a robustness claim.

Use the same two development clips (00976, 00265), existing +5 mm swept-envelope beam tasks, teacher, seed, frozen codec ranges and goal050/recovery/stop scorer as the parent. No geometry search, range refit, extra smoothing, handoff anchor or disturbance. Full root and future reference remain supplied. Clear scenes are not repeated. Broader clip ancestry is unresolved.

Select four handoff indices from each **already recorded continuous** beam run before evaluating any new continuation:

| State label | Fixed rule for pre-action handoff index k |
| --- | --- |
| Pre-entry | max(1, parent entry_tick − 15) |
| Entry | parent entry_tick + 1 |
| Exit | parent clear_tick + 1 |
| Pre-hold | parent control_steps − 50 − 10 |

These are phase proxies, not a guarantee that a precise lowering/braking event occurs there. Parent scorer ticks identify post-step samples; handoff k follows k executed physics/control steps. This gives 00976: 26, 42, 79, 186; 00265: 53, 69, 149, 207. No index is reselected based on Linear29 outcomes. Eight states × two methods = sixteen planned episodes.

## Native adapter and common prefix

Both methods reset with the original continuous motion and execute it through action k−1. Native conversion reconstructs the candidate library tensors using the same FK, joint/body order and derivative code as the original loader. Rebuilding the continuous library must match the resident library within 1e−5 before execution. The continuous handoff assigns exact clones of the resident tensors; the Linear29 handoff assigns the converted candidate.

The assignment occurs after action k−1 is computed, before that action's physics step. The action already chosen is unchanged; the next observation is therefore constructed normally from the new reference, with the same observation-history update/noise schedule. There is no extra observation computation, robot reset, state teleport, history reset, or RNG reset at the handoff. Preserve the reference cursor and all controller/actuator state. Candidate future information is absent from every prefix action.

At pre-action k, record root pose/velocity, all joint positions/velocities, body state, raw causal actor observation, action-manager current/previous action, controller observation buffers, cursor, and Torch/NumPy/Python RNG hashes. Retain the entire prefix's executed actions, decoder proprioception, pre-action physical states, contact samples and reference inputs for pair auditing. Dynamic parameters must also match. This uses actual deterministic prefix execution, not a claim of complete simulator snapshot restoration.

The reference remains a privileged diagnostic input. Measured state/history must match across methods; candidate reference futures are expected to differ. Full body/root reference fields are updated coherently. Scoring uses actual robot/contact measurements, not reference fidelity. Positive imitation masks remain disabled and collection stays development-only.

## Gates, outcomes and costs

For each state, run continuous first. It must reproduce the corresponding old continuous prefix within 1e−5 and finish the complete task before its Linear29 pair is launched. A failed gate stops the queue, preserves the failure and reports the remaining cells unrun. After each pair, require matching common-prefix actions/state/contact, incoming dynamics/causal observation/controller history and RNG. A mismatch stops further launches and invalidates representation attribution for that pair. A behavioral Linear29 failure is an outcome, not a retry opportunity.

Report every planned cell, conditional paired successes/losses, failure stage/contact body, completion time, handoff q/qdot discontinuity, adapter error and matching audit. Keep parent replay parity separate from pair matching. Independent complete-task success-tail/contact audit is reused. Four state samples from one clip do not constitute four independent motions; do not derive a generalization confidence interval from this panel.

Maximum sixteen attempts, 8,000 control steps, 32,000 scored physics samples; each attempt has a 500-tick horizon and 600 s process limit. The existing serial gate requires 12,000 MiB free GPU and 16,384 MiB available host memory twice, 20 s apart, with at most 300 s waiting per launch. No retries or training. Infrastructure failure, failed qualification/matching, or resource timeout stops the queue. User continuation authorizes this bounded new registration; the old 168-attempt balance is untouched.

Cost includes the full continuous prefix and its teacher lookahead, the full original root, and the candidate future. Reusing a previously shown continuous future does not make that information free. This is not a compressed end-to-end mission bitrate comparison. Preserve licensed references, raw trajectories, targets and controller assets locally; publish aggregate evidence and code only.

## Interpretation and next step

If all qualified pairs succeed, report support at these sampled states, not a valid-start-window certificate. Next distinguish genuinely new chunk choices or reference retiming from simple same-phase compression; independently register perturbations and any seam mitigation. If Linear29 alone fails, first inspect reference jumps and wrist-range clipping, with matched controls to distinguish these from lost temporal information. If continuous or matching fails, fix/qualify the interface before spending more representation budget.
