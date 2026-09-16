# Small-model proposal ranking pilot

This follow-up is specified before fitting the proposal model. It reuses the frozen source groups and the 64 candidate scenes per translating motion from the geometry pilot. It is exploratory, not a new independent test set.

## Target

Train a small neural module to rank supported primitive scenes before invoking the exact same sphere-proxy validator. The supervised target is full-body sampled proxy clearance >=30 mm. This target concerns geometric admissibility, not motion necessity, aesthetics, or physical navigation utility.

Use three input ablations: root path/orientation + candidate geometry; add kinematic event statistics; add time-binned RVQ code histograms. Root information includes root height and full orientation, so the baseline has access to crouch/root cues. Four temporal bins preserve coarse order; within-bin order is lost. Events are deterministic geometry descriptions, not LLM-generated annotations.

All variants have the same padded input width and MLP architecture (64,64,1), Adam 0.001, BCE loss, batch size 256, exactly 400 updates, seeds 0 and 1, CPU. Zero-pad unavailable input blocks. Use training-only normalization and no development-based model selection. Save both seeds, their parameters, training curves, split hashes and test predictions. No pretrained language model or external inference service is used.

## Evaluation

Report Brier score and precision of the 10 highest-ranked candidate scenes per motion, plus the fraction of motions that find at least one valid scene in those 10 validator queries. Include random candidate order under the same query budget and a full-label oracle upper bound. Scores are evaluated on every eligible test motion, including those with no valid candidate. Also report all-zero and all-positive candidate groups, and label prevalence.

Bootstrap paired differences between token/seed and root/same-seed by source directory, 1,000 draws. This quantifies variability over this fixed corpus conditional on the training seed, not broad generalization or training-seed uncertainty. Model-selected candidates still require the geometry verifier; never export classifier predictions as safety labels.
