"""A separate temporal interface over the frozen distance-exit controller."""
import numpy as np

from gear_sonic.research.hindsight_training.observations import rotation_wxyz
from gear_sonic.research.scene_distillation.duck_distance_exit import DistanceExitComposer

from .pending_exit import PendingRequest, prefix_contract


def measured_clearance(composer, measured):
    _, _, bounds = composer.fk.forward(measured)
    clear, margins = True, []
    for obstacle in composer.obstacles:
        if obstacle['shape'] != 'beam':
            raise ValueError('Only the inherited beam/clear gate is supported')
        local = (bounds - obstacle['center_xyz']) @ rotation_wxyz(obstacle['quaternion_wxyz'])
        boundary = obstacle['full_dimensions_xyz'][0] / 2 + .02
        rear = float(local[..., 0].min())
        clear &= bool(rear >= boundary)  # Same arithmetic/comparison as the frozen gate.
        margins.append(rear - boundary)
    return bool(clear), min(margins) if margins else None


class PendingExitComposer(DistanceExitComposer):
    def __init__(self, bank_path, measured, goal, obstacles, *, decoded, contract, enabled=True):
        super().__init__(bank_path, measured, goal, obstacles)
        self.decoded = decoded
        # Check the selected, world-aligned candidate too; the published contract
        # covers all families and both motor representations before launch.
        actual = prefix_contract({self.family: self.pair}, {self.family: decoded[self.family]}, self.decision_tick)
        if (contract['decision_tick'] != self.decision_tick
                or contract['committed_control_ticks'] != 5
                or contract['latest_accept_tick'] > actual['latest_accept_tick']):
            raise ValueError('Unproved admission deadline')
        self.pending = PendingRequest(self.decision_tick, contract['latest_accept_tick'], enabled)
        self.contract = contract

    def reference(self, measured):
        tick = self.tick
        if self.pending.status == 'pending':
            clear, margin = (measured_clearance(self, measured)
                             if tick <= self.pending.latest_accept_tick else (None, None))
            self.choice = self.pending.observe(tick, clear=clear, margin=margin)
        chunk = super().reference(measured)
        if tick == self.decision_tick:
            clear, margin = measured_clearance(self, measured)
            if clear != self.decision['measured_clear']:
                raise ValueError('Frozen gate parity failed')
            choice = self.pending.observe(tick, requested=self.decision['requested'], clear=clear, margin=margin)
            if choice != self.choice:
                raise ValueError('Initial decision parity failed')
        return chunk
