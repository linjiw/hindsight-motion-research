# Critical motion decisions: native experiment and data contract

## Research question

Can a hindsight scene proposer place an obstacle where a physically executable whole-body adjustment improves passage, while both alternatives remain usable when that obstacle is relaxed, removed, or displaced?

The first native experiment isolates **arm clearance**. It uses a real retargeted KIT walking carrier and two smooth arm edits. This is a constructed, executed contrast; it is not evidence that the human originally moved to avoid an unseen obstacle.

## Executed preparation

The source bank is `/home/linjiw/dataset/amass-licensed/phase-g-bank-rebuilt-fmt8`. Six named walking carriers from six KIT source groups were selected before native execution. Every carrier produced four candidates: unchanged, tucked arms, wide arms, and a 90-degree root-yaw edit. Each reference is a four-second, 50 Hz window. Arm edits preserve root and leg references exactly, share the first/last 0.6 seconds, and use 0.6-second quintic transitions.

The checkpoint is the released SONIC teacher at `/home/linjiw/research-data/m2s-sonic-qualification-20260912/release/checkpoint.pt`, SHA-256 `e6bdab3f64a39336b3d41877d4f497d05f58af275f288ec0e6746c283ded8909`. No teacher training was performed. The G1 encoder and native dynamic decoder run in IsaacLab/PhysX, with a 50 Hz controller and 200 Hz physics.

The native adapter preserves the source root height, normalizes the horizontal origin, verifies quaternion conventions, and verifies serialized motion roundtrip error below `1e-6`. Source and reference joints use MuJoCo order; live actions and joints use the recorded IsaacLab order. The compatibility field `smpl_joints` is not SMPL supervision.

### Two separately registered preflight batches

| Configuration | Attempts | Native sequence completion | Strict tracking support |
| --- | ---: | ---: | ---: |
| Released evaluation defaults, including observation noise and startup robot randomization | 24 | 23 | 3 |
| Same candidates, nominal robot properties and noiseless observations | 24 | 24 | 6 |

Strict support requires no native termination, mean global tracked-body error at most 10 cm, and maximum root XY error at most 25 cm. Native sequence completion alone does not satisfy this contract. None of the 90-degree yaw edits qualified: rotating root orientation without creating a compatible stepping motion is insufficient.

The first batch had identical initial root/joint states but different observed proprioception across paired environments. The second batch removed those nuisance differences. Carrier `KIT_205_walking_slow02_poses_100_jpos` supports both arm edits, with identical initial root state, joint state, velocities, and 930-dimensional proprioceptive history. Its mean body errors are approximately 4.7 cm for tucked arms and 5.0 cm for wide arms in the controlled empty-plane preflight.

Both batches and all failures are retained under `runs/critical_preflight_20260915_v{1,2}`. The 48 preflight episodes consume their own registered budget. A failed standalone collision-asset export initialized `SimulationApp` directly and crashed before any rollout; its log is retained. Export succeeded using the runtime's `AppLauncher` initialization. This diagnostic is not counted as a robot episode.

## Scene proposer

The proposer uses measured empty-plane executions and the native converted G1 collision asset: 45 collision primitives/meshes, including fixed hand collision shapes. It enumerates 145 passages: five locations along the motion and 29 opening widths from 0.44 to 1.00 m in 0.02 m steps.

For each proposal:

1. Enclosing collision boxes must leave at least 3 cm separation for the tucked execution at every recorded sample.
2. A ball inscribed in an analytic arm collision primitive must overlap a wall by at least 1 cm for the wide execution. Mesh bounding-box centers are excluded from this inner witness.
3. Rank admitted proposals by the smaller remaining margin of these two tests.

The selected opening is **0.76 m**. Its sampled tucked clearance lower bound is **4.94 cm**, and the wide-arm inner witness penetrates by **2.58 cm**. Those measurements propose a testable scene; they do not establish its physical outcome or continuous collision safety.

This stage implements a deterministic proposer that seeks a useful behavioral distinction. The earlier small learned rankers still predict geometric validity. No learned criticality proposer is claimed from one motion pair.

## Registered intervention panel

| Factor | Values |
| --- | --- |
| Continuation | Tucked arms, wide arms |
| Scene | Critical opening; opening widened by 0.60 m; walls removed; walls displaced laterally by 2 m |
| Initial-state perturbation | Root displaced laterally by 0, −1.5, or +1.5 cm |
| Total | 1 pair × 2 continuations × 4 scenes × 3 starts = 24 attempted episodes |

Each run uses a separate single-environment simulator scene, the same teacher and nominal robot, and no observation noise. Initial perturbations are explicitly applied and recorded; seed changes alone are not treated as perturbations. A per-panel audit compares measured initial root state, joints, joint velocities, and proprioceptive history across all eight runs. No fallback, repair, or replacement execution fills a success quota.

The main study's earlier upper limit is 480 episodes. This first stage uses 24 and covers one motion pair in one family, rather than the eventual 20 pairs in two supported families.

### Physical outcomes

Every body has a pair-resolved contact sensor for the floor and each obstacle. Normal forces are recorded at every 200 Hz physics step. Foot-floor support is allowed; obstacle contact and non-foot floor contact above 1 N fail the contact requirement. These sensors do not measure tangential friction force.

Passage success requires all of:

- Strict tracking support under the thresholds above.
- No undesired environment contact above 1 N.
- Final pelvis within 25 cm of the common goal.
- Final pelvis at least 20 cm beyond the nominal passage plane.

The terminal requirement is **moving arrival**. No stable stopping or holding behavior is required or claimed. A wide-arm rollout may remain upright and complete its reference clock while being blocked by the wall; goal and contact outcomes retain that failure.

A verified arm-clearance relation requires a complete matched panel: both alternatives pass all three control scenes, the tucked alternative passes the critical scene, and the wide alternative makes an arm/hand obstacle contact there. Missing panels, mismatched entry state, failures in removed controls, and leg-only contacts do not qualify.

## Motion, scene, relation, and motor representations

| Representation | Contents | Role |
| --- | --- | --- |
| Motion codes | Two 128-entry RVQ indices per five-frame patch; continuous root side channel retained | Reference-derived temporal representation; training target/posterior input |
| Scene tokens | Per-object local center, six rotation values, full dimensions, type; explicit padding mask and complete-map flag | Causal actor input computed from current measured pose and known map |
| Relation targets | Executed contact body, obstacle, time interval, paired-control support, and supported arm behavior | Training-only labels, assigned after intervention audit |
| Native motor representation | SONIC's 64-dimensional continuous decoder input | Teacher target, tied to the exact decoder; not interchangeable with RVQ indices |

Each completed scene episode exports:

- `actor-view.npz`: 930D causal proprioception, current local goal, metric scene object tokens, and availability fields.
- `teacher-view.npz`: privileged state and future reference information.
- `target-view.npz`: same-state teacher actions, native motor tokens, and support masks.
- Raw state trajectories, pair-resolved contacts, task/scene hashes, and outcome receipts for auditing.

The stored 930D proprioception is the actual causal input captured at the native decoder, after the teacher's preprocessing. A deployment adapter must reproduce that preprocessing. Actions use native IsaacLab joint order, are clipped by the wrapper at magnitude 20, and feed joint-position targets with the robot's default offsets and per-joint scale (`0.25 × effort_limit / stiffness` in the frozen G1 configuration). They are not joint torques. Decoder weights, normalization, joint ordering, offsets, scales, and control frequency must remain compatible when reusing the 64D motor targets.

Unsafe contrast rollouts remain available as negative outcome evidence. Their canonical motor-imitation support is false. Future reference, phase, source identity, and contact-derived relation labels are excluded from actor inputs. All current samples are development data, with `positive_student_training_authorized=false`; a fresh ancestry-aware split is required before a student training/evaluation claim.

The actor map/goal transform uses simulator pose as exact localization, with a complete known map. This is an explicit resource assumption for the current experiment. Camera/depth perception, uncertain localization, and partial-map tokens require a separate observation study.

### Executed token-clearance diagnostic

The two reference root trajectories are exactly identical. Existing RVQ codes distinguish 26 of 40 temporal patches, but that does not ensure the clearance distinction survives decoding.

A separate exploratory audit first validated URDF forward kinematics against the measured native body traces, then reconstructed both references with the existing codebooks and the native collision envelopes. The selected passage gives:

| Tucked-arm representation | Sampled clearance lower bound | Passes the 3 cm separation screen? |
| --- | ---: | --- |
| Continuous reference | 9.89 cm | Yes |
| VQ, 128 entries | 0.99 cm | No |
| RVQ, two 128-entry levels | −1.19 cm | No |

These are **kinematic bounds on reconstructed references**, not measured clearances of newly executed decoded motions. A negative bound does not prove collision. The physically executed uncompressed tucked motion has a different sampled bound, 4.94 cm, because the tracker deviates from its reference.

Across all 145 correlated proposed passages, VQ changes 44 and RVQ changes 36 of the tucked reference's 3 cm separation decisions. Mean bound errors are 7.19 and 5.66 cm. For the wide reference, the corresponding decision changes are 7 and 1, and mean bound errors are 5.23 and 2.35 cm. This small, selected contrast is development evidence; it is not a tokenizer benchmark or generalization estimate.

The next representation comparison should therefore test whether explicit local hand/elbow/foot/pelvis geometry channels or a clearance-sensitive training loss preserve these decisions. Keep native SONIC motor tokens as a separate target and freeze a fresh evaluation split before fitting the revised representation.

## Follow-up decisions

1. Expand qualified carriers and independently qualify a second mechanism, such as ducking or stepping over. Use natural motions or contact-consistent motion edits; the yaw-only edit is rejected.
2. Test several physical gap widths and larger state/dynamics disturbances. The current geometric width ranges are sampled bounds; only the selected 0.76 m width receives physical interventions.
3. Collect multiple source groups before training a criticality-aware proposer. Compare it with random safe placement and the geometry-only ranker at the same proposal/execution budget.
4. Evaluate representations against intervention outcomes, including whether compression preserves the body-part/time distinction. Code presence alone does not establish usefulness.
5. Distill a known-map, goal-conditioned student with a frozen teacher/decoder and explicit support masks. Use a scene-first held-out test to measure task improvement. Add grounded language after those controls work.

This experiment validates a local construction-and-verification mechanism. It does not yet establish autonomous scene-conditioned navigation, broad dataset utility, sim-to-real transfer, learned scene generation, BFM improvement, or text-to-navigation.

## Entry points

Code: `critical.py`, `native.py`, `interventions.py`, `scene_native.py`, `critical_analysis.py`, `critical_validate.py`, and `critical_present.py` under `src/hindsight_motion`.

The frozen task list is `runs/critical_interventions_20260915_v1/tasks.json`; outcomes, relation audits, receipts, and canonical views are stored beside it. Source motions and licensed descendants remain local.
