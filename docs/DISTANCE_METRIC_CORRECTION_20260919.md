# Goal-distance reporting correction

2026-09-19. During the distance-codec admission-02 audit, source inspection exposed an earlier labeling error. **The frozen complete-task scorer uses 3D root-to-goal distance; the exit endpoint predictor uses XY distance.** The scorer, thresholds, input tasks and all original result files remain unchanged. This is a reporting correction, not a new outcome definition or rerun.

The bound sibling `gear_sonic/research/scene_distillation/duck_task.py` computes `np.linalg.norm(root - task['goal_xyz'], axis=-1)` before the 0.50 m goal test. Its initial legacy navigation component likewise supplies the recorded `final_goal_distance_m`. The exit-choice code compares predicted endpoints with `[:2]`. Thus endpoint prediction errors, final 3D goal errors and final-window means are different measurements.

The original [distance-codec protocol](DISTANCE_CODEC_PROTOCOL.md) incorrectly called the frozen radius “0.50 m XY.” Some prior local sync prose, following the sibling reports, also called their `final_goal_distance_m` values XY. Those immutable registrations/source reports are retained; use this correction when interpreting them. The machine registration's bound scorer always determined success. No intervention used a replacement XY scorer, and the independent scorer audits reproduce all outcomes exactly.

| Admission-02 case | Final 3D distance used by the scorer | Separately measured final XY distance |
| --- | --- | --- |
| Original / continuous | 0.029953 m | 0.029608 m |
| Original / Linear29 | 0.090251 m | 0.090160 m |
| Farther / continuous | 0.384866 m | 0.384815 m |
| Farther / Linear29 | 0.674383 m | 0.674365 m |

The public admission aggregate explicitly retains both `final_goal_distance_3d_m` and `final_goal_error_xy_m`. Its `final_goal_margin_xy_m` is descriptive horizontal margin, not the scorer's margin; the latter is `0.50 - final_goal_distance_3d_m`. The sibling's endpoint-calibration `goal_radius_margin_m` is derived from recorded 3D goal distance, including its 0.016580 m minimum. Calibrated predicted endpoint errors remain XY, and errors against a final-50 mean endpoint are not errors of the final root sample.

Evidence: [four-case aggregate](../results/distance_codec_admission02.json), [separate sibling calibration snapshot](../results/endpoint_controller_sync.json), and [exploratory endpoint audit](../results/endpoint_codec_transfer.json). These small metric differences do not change any reported pass/fail category in this panel. Future protocols must name the dimensions explicitly.
