"""
The -11 LUFS loud-master anchor is one constant (#6226).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``-11.0`` was spelled in three files with no link between them
(``SimpleMasteringConfig.TARGET_LUFS``, ``AdaptiveLoudnessControl.TARGET_LUFS``
and the soft-clip ramp literal), so retuning the loud-master target required
editing all three. They now read ``LOUD_MASTER_TARGET_LUFS`` from
``dsp/utils/loudness_targets.py``, next to the -14 family #5795 created.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.core.config.genre_profiles import get_default_genre_profile
from auralis.core.config.preset_profiles import get_preset_profile
from auralis.core.mastering_branches.soft_clip_params import compute_soft_clip_threshold
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.utils.fingerprint_unpacker import FingerprintUnpacker
from auralis.dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from auralis.dsp.utils.loudness_targets import (
    DEFAULT_TARGET_LUFS,
    LOUD_MASTER_TARGET_LUFS,
)


def test_loud_master_anchor_is_shared_by_all_three_sites():
    assert SimpleMasteringConfig().TARGET_LUFS == LOUD_MASTER_TARGET_LUFS == -11.0
    assert AdaptiveLoudnessControl.TARGET_LUFS == LOUD_MASTER_TARGET_LUFS


def test_soft_clip_params_unchanged_for_sample_fingerprints():
    """The ramp must behave identically to the old literal for sample inputs."""
    config = SimpleMasteringConfig()
    for lufs in (-30.0, -20.0, -14.0, -11.0, -8.0):
        unpacker = FingerprintUnpacker.from_dict({"lufs": lufs})
        threshold_db, ceiling = compute_soft_clip_threshold(unpacker, config, verbose=False)
        loudness_factor = max(0.0, min(1.0, (-11.0 - lufs) / 9.0))
        assert threshold_db == -2.0 + (1.5 * (1.0 - loudness_factor))
        assert ceiling == 0.92 + (0.07 * loudness_factor)


def test_minus_fourteen_defaults_read_the_named_constant():
    assert get_default_genre_profile().target_lufs == DEFAULT_TARGET_LUFS
    assert get_preset_profile("adaptive").target_lufs == DEFAULT_TARGET_LUFS
    assert FingerprintUnpacker.from_dict({}).lufs == DEFAULT_TARGET_LUFS
