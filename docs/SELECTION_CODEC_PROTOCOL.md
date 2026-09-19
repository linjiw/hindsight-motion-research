# Continuous versus Linear29 after public motion selection

September 19, 2026. The user requested continuing the saved plan. The sibling
repository has advanced to `273970f1` and already provides the planned two-motion
bank and public-state selector. Its four-trial result uses one source ancestry,
two familiar contexts and clean planned orientations. Reuse those assets; do not
repeat bank acquisition or pool its scores into this repository.

## Question and comparison fixed before execution

Does the frozen Linear29 reconstruction preserve complete-task execution when
the reference is selected and retimed from measured state, goal and a known map?
Our prior 8/8 per-method handoffs supplied the correct phase and future. This
pilot instead uses the existing public selector, with internal library state.

The [registration](../configs/selection_codec_v1.plan.json) permits four native
attempts, ordered clear continuous/Linear29 then beam continuous/Linear29, at
most 500 control ticks each, 600 s per process and 300 s resource waiting. No
retry, training or historical-budget consumption. Both continuous controls must
complete and reproduce their earlier physical trajectories exactly before the
paired codec is interpreted. Every method pair must share exact reset state,
initial proprioceptive/action history, dynamics and RNG. Infrastructure failure,
control/parity failure or timeout stops the queue; codec behavioral failures
remain outcomes. Keep all receipts and unrun cells.

## Representation and causal boundary

Both arms use the same continuous bank, initial candidate score, alignment,
support checks, seam limits, five-frame commitments and retiming algorithm.
Only q/qdot delivered to the native encoder changes. Subsequent physical states
and resulting retiming can differ: those are closed-loop treatment effects, not
matched-state mechanism estimates. Candidate choice is checked at matched reset.

Encode both 499-frame candidates with the old 12-bit, 10 Hz Linear29 grid
(indices 2,7,...,497) and frozen scales mapped by joint name. Keep the two reset
anchor frames, constant endpoint interpolation and original planned root
orientation. Recompute qdot on the 50 Hz library grid using the native forward
difference convention, including its final penultimate-difference padding.
This is an explicit extension from the earlier 300-frame files; no scale fitting,
new anchor, handoff blend or library search is performed.

After selection and retiming, gather by the actual committed dense source
indices. The sibling corrected an old scalar cursor that did not always name
the committed current frame. The new route must reproduce all recorded continuous
references on the 725 old public states and all ten corrected source indices
before launch. A tail cursor must never replace those indices. Planned root,
support and collision bounds stay in the continuous planner; decoded support is
not presumed physically identical and is tested by execution.

No task clip ID, teacher future, supplied phase or teacher action enters public
selection. The simulator still loads a motion asset for reset/legacy plumbing;
the initial-state distribution is familiar, not motion-independent. Localization
is zero-delay simulator root pose. The motor receives the same normalized 930D
history and a clean 640D reference in both methods. Reference orientation noise
is not an extra intervention. New trajectories cannot become positive student
labels. No sibling code or old evidence is edited.

## Audit, cost and decision

Before physics, verify the bound bank/data, corrected telemetry, named scale
conversion, native velocity convention and exact continuous-reference replay.
Record offline reconstruction and clipping separately from physical outcomes.
After physics, recompute full-body geometry, substep forbidden forces and all
scorer fields from recorded poses/trace. Check task completion, recovery, fresh
50-tick stop, deadline, selected candidate, retiming and support rejections.
The inherited goal050 and contact contract are unchanged.

Continuous failure or parity loss means this integration is not qualified.
Continuous success with Linear29 failure isolates an operational reference-route
loss under this fixed planner; later diagnostics distinguish clipping, sampling
and execution. Both passing supports a varied-scene comparison, not equivalence,
robustness or cross-ancestry generalization. One source and one reset per context
do not support population confidence intervals or a timing advantage claim.

Logical codec payload is reported for the library stream only. The selector
retains the full continuous bank and extra geometry/support records, so reduced
joint payload is not total system memory, wire traffic or acquisition savings.
No native experiment beyond these four attempts follows automatically.
