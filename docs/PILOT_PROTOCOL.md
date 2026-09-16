# Frozen exploratory pilot — 2026-09-15

Question: after preserving the same continuous root trajectory and orientation, how much does quantizing the articulated G1 motion change whole-body obstacle clearance? Can actual local mocap produce nonempty hindsight scene candidates?

This is an offline representation and scene-generation pilot. No closed-loop navigation, causal human intent, physical stability, or functional counterfactual validity is inferred from it.

## Inputs and split

Use all 900 local retargeted AMASS NPZ files listed by the source TSV. Validate shapes, finite values, time base, quaternions and G1 link ordering. Record SHA-256 for every input. AMASS originals and robot retargets are distinct inventories, not additive unique performances.

Split by the source collection + subject/session directory, hash with seed 20260915: 70% train, 15% development, 15% test. One group never crosses splits. Preserve historic split as metadata but use a new explicitly exploratory grouping; this corpus has been used in earlier projects, so this is not a fresh confirmatory benchmark. Source-directory grouping cannot rule out undocumented cross-directory duplicates.

Use one up-to-four-second window per motion, chosen by maximum start-to-end root translation among 1-second-stride windows. Record original frame offsets. Keep true 50 Hz timing; trim only trailing incomplete 5-frame patches. A clip end is not a stop label.

## Representations

1. Full continuous joint angles (reference).
2. A fixed training-median joint configuration carried by the same root translation and quaternion (rigid-pose diagnostic).
3. K-means vector quantization of 5-frame joint-angle patches, 128 codes, 25 iterations, at most 20,000 training patches.
4. Two-stage residual vector quantization, same 128-code budget per stage.

VQ/RVQ here are learned Euclidean codebooks, not pretrained neural VQ-VAEs or language-aligned tokens. Every method shares continuous root position/orientation. Quantization alone does not compress that side channel. Model fitting uses training groups only; no hyperparameter selection on test.

## Geometry and independent probes

Recompute forward kinematics using a hash-recorded G1 XML. Retain model mesh hashes. Measure discrepancy from the existing bank instead of silently mixing models.

For every collidable robot geometry, use MuJoCo's bounding sphere (`geom_rbound` about `geom_xpos`). These enclose the model collision geometries, but can substantially overestimate occupied space. Minimum signed box clearance is exact for these sphere proxies; it is not exact mesh clearance. Sample all retained 50 Hz frames; this is not continuous-time collision certification.

Generate 48 scene-independent probe boxes per motion using a separately seeded sampler around sampled root positions and random heights/sizes. Use the same probes for all representations. Report clearance MAE, collision-decision disagreement, false-safe counts, and link-origin reconstruction error. A full-geometry sidecar would preserve the original check by construction and must not be presented as an equal-information learned-model gain. Cluster bootstrap intervals by source directory, never by frame.

## Hindsight candidates

For clips with >=0.6 m translation, propose 64 simple supported objects: floor-standing pillars, low blocks, and three-box portals (beam plus two supports). Candidate positions are centered near the route; include diverse heights and lateral offsets. Each candidate is checked against the entire selected clip, with 30 mm proxy clearance and original start/end exclusion. Retain up to 3 passing scenes. Report all rejection counts.

Rank full-body candidates by overlap with the rigid-pose diagnostic and then proximity. Compare an equally budgeted random-order filter and a filter using only the rigid-pose diagnostic. A rigid-pose overlap is an information witness, not an executable alternative; the fixed-pose trajectory is not a valid physical counterfactual. Label all exports `geometry_candidate`, `physics_verified=false`, `functional_counterfactual_verified=false`.

## Interpretation and next decision

Errors above a 30 mm placement margin support retaining continuous geometry and improving the tokenizer; low reconstruction error alone does not establish navigation utility. Full-body-versus-rigid differences are descriptive information diagnostics. The next causal experiment needs independently executable matched motions, obstacle removal, and achieved-state simulation. Scene-first independent closed-loop evaluation remains a separate experiment.
