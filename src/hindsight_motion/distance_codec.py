"""Explicit composed-clock reference treatment, without simulator dependencies."""
from dataclasses import replace

import numpy as np

from .selection_codec import gather_reference


def validate_commitment(decoded, decision_tick):
    """Reject a decoded branch change inside the five committed control frames."""
    for family, routes in decoded.items():
        for route in ('short', 'loop'):
            q, v = routes[route]
            if (q.ndim != 2 or q.shape[1] != 29 or q.shape != v.shape
                    or len(q) < decision_tick + 5 or not np.isfinite(q).all()
                    or not np.isfinite(v).all()):
                raise ValueError('Invalid decoded option: ' + family + '/' + route)
        for index in (0, 1):
            if not np.array_equal(routes['short'][index][:decision_tick + 5],
                                  routes['loop'][index][:decision_tick + 5]):
                raise ValueError('Decoded option changes a committed frame')


def motor_chunk(chunk, decoded, family, choice, cursor, method):
    if method not in ('continuous', 'linear29') or choice not in (0, 1):
        raise ValueError('Unknown registered representation or exit choice')
    if method == 'continuous':
        return chunk
    q, v = decoded[family]['loop' if choice else 'short']
    if not 0 <= cursor < len(q):
        raise ValueError('Invalid composed cursor')
    indices = np.minimum(cursor + np.arange(len(chunk.joint_position)), len(q) - 1)
    joint, velocity = gather_reference(q, v, indices)
    return replace(chunk, joint_position=joint, joint_velocity=velocity)
