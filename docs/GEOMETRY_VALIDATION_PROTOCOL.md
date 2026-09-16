# Independent model-geometry recheck

Before running this check: evaluate every exported test-split scene from the fixed pilot (84 scenes from 28 source motions). No scene selection by the recheck outcome. Use the same pinned XML and full MuJoCo collision geometry instead of enclosing sphere proxies. MuJoCo mesh collision uses the simulator's collision representation, including convex approximations; this is not a guarantee about visual nonconvex mesh surfaces.

Insert scene boxes into a fresh MuJoCo MjSpec. Evaluate `mj_geomDistance` for each robot/obstacle pair, using the enclosing-sphere lower bound only to skip pairs that cannot improve the running minimum. Check each retained 50 Hz pose and one midpoint per adjacent pair (100 Hz): linearly interpolate root translation and joint angles; use quaternion SLERP for the root. Do not integrate dynamics.

Recheck both original motion and the training-median rigid-pose diagnostic. Report model-geometry minimum clearance, overlap, frame count and body part attaining the minimum. Report the fraction of proxy rigid-overlap witnesses retained with model collision geometry. This calibrates proxy conservatism and temporal sampling; neither comparator has acquired physical execution validity.

Do not discard or relabel original exports. Store a separate verification table. Mark `physics_verified=false`, `continuous_time_certified=false` on all records.
