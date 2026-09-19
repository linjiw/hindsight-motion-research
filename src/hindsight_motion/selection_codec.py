"""Named-joint codec for a selected library; no simulator dependency."""
import numpy as np

from .clearance_tokens import interpolate_knots, quantize12


def native_velocity(q, dt=.02):
    q = np.asarray(q, dtype=np.float32)
    if q.ndim != 2 or len(q) < 3 or not np.isfinite(q).all() or dt != .02:
        raise ValueError("Expected finite dense 50Hz joint positions")
    difference = np.diff(q, axis=0) / np.float32(dt)
    # Match the pinned native loader, including its unusual endpoint rule.
    return np.concatenate([difference, difference[-2:-1]], axis=0)


def decode_candidate(q, joint_names, scale, scale_names):
    names, source = tuple(joint_names), tuple(scale_names)
    q, scale = np.asarray(q), np.asarray(scale)
    if (q.ndim != 2 or q.shape[1] != 29 or len(q) < 8
            or len(names) != 29 or len(set(names)) != 29 or set(names) != set(source)
            or len(source) != 29 or scale.shape != (29,) or (scale <= 0).any()
            or not np.isfinite(q).all() or not np.isfinite(scale).all()):
        raise ValueError("Invalid named 29-joint codec input")
    ordered = scale[[source.index(n) for n in names]]
    symbols, knots, clipped = quantize12(q[2::5].astype(float), ordered)
    decoded = interpolate_knots(knots, len(q)).astype(np.float32)
    decoded[:2] = q[:2]
    audit = dict(frames=len(q), knots=len(knots), clipped_symbols=clipped,
                 symbols=int(symbols.size), joint_payload_bits=int(symbols.size*12),
                 reset_anchor_bits=2*29*32, q_rmse_rad=float(np.sqrt(np.mean((decoded-q)**2))),
                 q_max_rad=float(np.max(abs(decoded-q))))
    return decoded, native_velocity(decoded), audit


def gather_reference(q, qdot, dense_indices):
    indices = np.asarray(dense_indices)
    if (indices.ndim != 1 or len(indices) < 46 or indices.dtype.kind not in 'iu'
            or (indices < 0).any() or (indices >= len(q)).any()
            or q.shape != qdot.shape):
        raise ValueError("Need valid committed indices covering the native horizon")
    return q[indices], qdot[indices]
