# Temporal decoding, leg fidelity, and teacher coverage

## Research decision

The previous RVQ+body9 representation improved obstacle-clearance reconstruction but passed 0/18 empty-scene executions. Two plausible contributors are large changes between decoded patches and inaccurate leg trajectories. This study compares implemented repairs before selecting a new tokenizer architecture.

The scientific registration is `configs/token_mechanism_v1.plan.json`. It predates reference construction and native launches. The teacher, native robot assets, task thresholds, common-entry adapter, source pairs and perturbations remain fixed.

## Decoder comparison

Three existing development pairs (`arm03`, `arm02`, `hybrid205`) × two continuations × three offsets × eight methods = 144 scheduled preflight episodes.

| Method | Temporal operation | Leg information | Joint logical payload |
| --- | --- | --- | ---: |
| Continuous | Original 50 Hz reference | Original | 46,400 bit/s |
| Linear29 | 10 Hz scalar knots, linear interpolation | 10 Hz 12-bit scalar knots | 3,480 bit/s |
| Body9 raw | Frozen RVQ + anatomy residual decoder | RVQ | 1,220 bit/s |
| Body9 smooth | Symmetric five-frame binomial filter | Filtered RVQ | 1,220 bit/s |
| Body9 + original legs | Raw upper body | Original 50 Hz legs | 20,420 bit/s |
| Smooth + original legs | Filtered upper body | Original 50 Hz legs | 20,420 bit/s |
| Body9 + leg12 | Raw upper body | Frozen Linear29 leg subset | 2,660 bit/s |
| Smooth + leg12 | Filtered upper body | Frozen Linear29 leg subset | 2,660 bit/s |

The filter is `[1,4,6,4,1]/16`, with edge replication. Leg replacement happens **after** filtering. Its twelve channels are the native canonical hip, knee and ankle angles. The filter adds no per-motion symbols but needs future reference samples; this is an offline decoder operation, not a causal actor observation.

All methods retain the same 11,200 bit/s full-rate root stream and original entry through 0.6 s, with a quintic transition ending at 1.2 s. Entry information, model and container overhead are excluded from the logical joint rates. Native joint-limit corrections are measured. Original-leg methods are privileged diagnostics, not matched-rate compression results.

### What the factorial contrast can identify

The raw/smooth × decoded/original-leg comparison measures the effects of these specific reference interventions with a frozen tracker. Smoothing changes within-patch motion as well as boundary changes; it does not isolate a pure seam effect. Original-leg replacement changes position fidelity and temporal derivatives together. Report their interaction and practical leg12 alternatives without claiming a universal explanation for all tokenizers.

Measure native passage/tracking, fidelity to the original continuous reference, original-body/root errors, completion, goal error and contacts. Original-motion fidelity uses mean body error ≤10 cm, maximum root XY error ≤25 cm and 200 valid pre-action rows. Shared measured entry tolerates at most 10⁻⁵ error.

### Promotion to frozen scenes

For each of the two predetermined main cases (`arm03`, `hybrid205`), choose the first fully qualified practical method in this fixed order:

1. Body9 raw.
2. Body9 smooth.
3. Body9 + leg12.
4. Smooth + leg12.

Both continuations must pass all three preflight offsets, and the continuous control must qualify. Execute the selected method and a fresh continuous control under the existing critical, relaxed, removed and displaced geometries. No oracle main scenes; no scene movement to accommodate reconstruction. Maximum new main episodes: 96, counted against the global 480 ceiling (216 used before this stage).

## Additional teacher coverage

The prior acquisition used a `walk` filename filter. This stage scans the local 900-motion bank without a filename condition, while retaining the same four-second kinematic eligibility rules and excluding every previously physically examined source group.

The eligible pool contains 57 clips from 35 new source groups. Select the descriptor-nearest clip per group, at most eight groups, against the fixed KIT/205 and KIT/9 gait anchors. Compare each **unedited** carrier with its smooth arm-tuck version under all three offsets: 48 episodes. Do not retime or apply duck/bend edits in this coverage screen.

Report original and tuck qualification separately. A carrier is acquisition-ready only when both pass every offset from matched entry states. This does not make it an obstacle-qualified pair. Proposed next-stage scenes require executable alternative behaviors, geometry refinement and complete interventions.

## Complementary CPU diagnostics

- Evaluate all eight decoders on the 643 unchanged candidates from the prior four-pair geometry study. Continuous-reference geometry is the comparison target; it is not a physical collision label. Use full decoded motions here, without the native entry adapter.
- Inspect executed-reference joint changes after 1.2 s, retaining the original body9 and Linear29 reconstructions as exact baseline checks.
- Measure ankle-link position, orientation and velocity reconstruction using the validated native-URDF forward kinematics. These are kinematic errors, not measurements of physical foot contact or sliding.

The geometry extension has its own before-computation registration in `runs/token_mechanism_geometry_20260915_v1/registration.json`. Foot diagnostics are exploratory and labeled accordingly. No model is fitted on these evaluation outcomes.

## Infrastructure failure and recovery accounting

The initial 144-slot mechanism launch (`token_mechanism_preflight_20260915_v1`) stopped with `CUBLAS_STATUS_ALLOC_FAILED`. Available GPU memory had been checked, but concurrent workloads grew during initialization. No episode arrays or outcome records were produced. Retain its launch, exit, log and 144 scheduled slots separately from recorded executions and behavioral failures.

An explicit amendment, `configs/token_mechanism_recovery_v1.plan.json`, permits exactly one recovery launch in a new directory using all the same references and tasks. It changes no scientific method or selection rule. Before admission, require at least 12,000 MiB free GPU memory and 16 GiB available host memory on two checks at least 20 seconds apart. Run project batches serially and do not interrupt other jobs.

The amended stage maximum is 336 scheduled preflight slots across three launches: 144 failed infrastructure slots, 144 recovery slots and 48 carrier slots. The unamended scientific population is 192 recorded preflight episodes. Report the actual recorded count, even if recovery is deferred or fails. No further automatic recovery is allowed.

## Relation to the scene proposer and future student

This study decides which motion representation can preserve both scene-relevant body geometry and teacher-executable locomotion. A representation that reproduces shoulder clearance while corrupting stance/gait cannot alone certify an executable motion–scene pair.

The proposer may consume full motion, geometric bounds and future-derived relation supervision offline. Its generated scenes must pass separate geometry, teacher-support and intervention checks. `No scene` and `unsupported motion` remain valid outputs. Failed teacher qualification is not an obstacle-placement failure label.

The future navigation student consumes causal robot observations, available scene information and goals. It predicts the frozen controller's compatible motor latent/action, or uses an independently qualified adapter. Neither mocap RVQ codes, oracle legs nor the teacher's future reference become actor inputs. Source descendants stay grouped; extra preflight frames do not create independent scene tasks.
