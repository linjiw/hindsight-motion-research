from dataclasses import dataclass

import numpy as np
import pytest

from hindsight_motion.distance_codec import motor_chunk, validate_commitment


@dataclass
class Chunk:
    joint_position: np.ndarray
    joint_velocity: np.ndarray
    root_xyz: np.ndarray
    support: np.ndarray


def fixture():
    short = np.zeros((180, 29), np.float32)
    loop = short.copy()
    loop[168:] = 1
    decoded = {'duck': {'short': (short, short.copy()), 'loop': (loop, loop.copy())}}
    return decoded, Chunk(short[:60], short[:60], np.ones((60, 3)), np.ones((60, 2), bool))


def test_branch_forecast_can_change_but_commitment_cannot():
    decoded, _ = fixture()
    validate_commitment(decoded, 126)
    decoded['duck']['loop'][1][130, 0] = 1
    with pytest.raises(ValueError, match='committed'):
        validate_commitment(decoded, 126)


def test_composed_clock_keeps_root_support_and_clamps_terminal():
    decoded, chunk = fixture()
    treated = motor_chunk(chunk, decoded, 'duck', 1, 160, 'linear29')
    assert treated.root_xyz is chunk.root_xyz and treated.support is chunk.support
    assert (treated.joint_position[:8] == 0).all()
    assert (treated.joint_position[8:] == 1).all()
    assert treated.joint_position.shape == chunk.joint_position.shape
    assert (decoded['duck']['short'][0] == 0).all()


def test_continuous_preserves_supplied_velocity():
    decoded, chunk = fixture()
    chunk.joint_velocity = np.full((60, 29), .123, np.float32)
    assert motor_chunk(chunk, decoded, 'duck', 0, 0, 'continuous') is chunk
    with pytest.raises(ValueError, match='Unknown'):
        motor_chunk(chunk, decoded, 'duck', 2, 0, 'linear29')
