"""Bounded request lifetime and exact dense-prefix contract, without a motor."""
from dataclasses import asdict, dataclass, field

import numpy as np


def first_difference(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.ndim < 1 or a.shape[1:] != b.shape[1:] or not min(len(a), len(b)):
        raise ValueError('Incompatible time-series shapes')
    if a.dtype.kind in 'buifc' and b.dtype.kind in 'buifc':
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError('Nonfinite commitment field')
    elif a.dtype.kind not in 'US' or b.dtype.kind not in 'US':
        raise ValueError('Unsupported commitment dtype')
    n = min(len(a), len(b))
    changed = np.flatnonzero(np.any((a[:n] != b[:n]).reshape(n, -1), axis=1))
    # Stop at the end of the shorter real array; padding cannot extend admission.
    return int(changed[0]) if len(changed) else n


def prefix_contract(pairs, decoded, decision_tick, committed_ticks=5):
    if committed_ticks != 5 or type(decision_tick) is not int or decision_tick < 0:
        raise ValueError('Only the declared five-control-tick profile is supported')
    if set(pairs) != set(decoded) or not pairs:
        raise ValueError('Incomplete family coverage')
    rows = []
    for family, (short, loop) in pairs.items():
        if short.names != loop.names or short.dt != .02 or loop.dt != .02:
            raise ValueError('Joint order, clock or array schema mismatch')
        # Short is a direct source without explicit donor metadata. Compare its
        # identity mapping with the loop's recorded donor/bridge annotations;
        # never write these inferred fields into either motion artifact.
        views = []
        for candidate in (short, loop):
            arrays = dict(candidate.arrays)
            arrays.setdefault('base_source_index', np.arange(candidate.length))
            arrays.setdefault('base_source_family', np.full(candidate.length, family))
            arrays.setdefault('synthetic_bridge', np.zeros(candidate.length, bool))
            views.append(arrays)
        if set(views[0]) != set(views[1]):
            raise ValueError('Unresolved array schema mismatch')
        fields = {}
        for key, a in views[0].items():
            b = views[1][key]
            if a.ndim and len(a) == short.length:
                if not b.ndim or len(b) != loop.length:
                    raise ValueError('Inconsistent time axis: ' + key)
                fields[key] = first_difference(a, b)
            elif not np.array_equal(a, b):
                raise ValueError('Static metadata mismatch: ' + key)
        for method in ('continuous', 'linear29'):
            differences = dict(fields)
            if method == 'linear29':
                routes = decoded[family]
                for j, key in enumerate(('joint_position', 'joint_velocity')):
                    if any(routes[r][j].shape != pairs[family][i].arrays[key].shape
                           for i, r in enumerate(('short', 'loop'))):
                        raise ValueError('Decoded shape mismatch')
                    differences['decoded_' + key] = first_difference(routes['short'][j], routes['loop'][j])
            first = min(differences.values())
            rows.append(dict(family=family, method=method, first_difference_by_field=differences,
                first_unequal_or_unavailable_frame=first, latest_accept_tick=first - committed_ticks))
    limit = min(r['latest_accept_tick'] for r in rows)
    if limit < decision_tick:
        raise ValueError('No legal commitment window at the registered decision')
    return dict(schema='hindsight_pending_exit_commitment_v1', decision_tick=decision_tick,
        committed_control_ticks=committed_ticks, dense_dt_s=.02, native_sample_stride=5,
        native_horizon_samples=10, latest_accept_tick=limit, rows=rows,
        semantics='Current through current+4 dense frames are committed; later forecasts may be revised. No full-preview equivalence claim.')


@dataclass
class PendingRequest:
    decision_tick: int
    latest_accept_tick: int
    enabled: bool = True
    status: str = 'unrequested'
    requested: int | None = None
    accepted_tick: int | None = None
    expired_tick: int | None = None
    choice: int = 0
    events: list = field(default_factory=list)

    def __post_init__(self):
        if self.latest_accept_tick < self.decision_tick:
            raise ValueError('Empty admission window')

    def observe(self, tick, *, requested=None, clear=None, margin=None):
        if tick < self.decision_tick:
            return self.choice
        if self.status == 'unrequested':
            if tick != self.decision_tick or requested not in (0, 1) or type(clear) is not bool:
                raise ValueError('Request must be latched once at the decision tick')
            self.requested = requested
            if not requested:
                self.status = 'selected_short'
            elif clear:
                self.choice, self.status, self.accepted_tick = 1, 'accepted', tick
            else:
                self.status = 'pending' if self.enabled else 'rejected'
        elif self.status == 'pending':
            if tick != self.events[-1]['tick'] + 1 or requested is not None:
                raise ValueError('Pending checks must preserve clock and latched request')
            if tick > self.latest_accept_tick:
                self.status, self.expired_tick = 'expired', tick
            elif type(clear) is not bool:
                raise ValueError('Measured gate required within the admission window')
            elif clear:
                self.choice, self.status, self.accepted_tick = 1, 'accepted', tick
        else:
            return self.choice
        self.events.append(dict(tick=tick, status=self.status, measured_clear=clear,
            clearance_margin_m=margin, chosen=self.choice))
        return self.choice

    def receipt(self):
        return asdict(self)
