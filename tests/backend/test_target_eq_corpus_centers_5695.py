"""
Fixed-target EQ is calibrated to the corpus centers (#5695)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fixed-target path compared each band's share with hand-set "ideal"
shares that described nothing real fingerprints look like, then summed
bands into shelves — a corpus-median track got bass clamped at -6 dB and a
+9.5 dB high shelf, a content-independent bass-cut/treble-boost on every
fixed-target render. The ideals are now the 512-track corpus medians in
``auralis/dsp/constants.CORPUS_BAND_CENTERS``, and since #6356 every render path
derives its targets with ``auralis/core/processing/mastering_targets.py``, so the
paths cannot drift.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES
from auralis.core.config import UnifiedConfig
from auralis.core.processing import continuous_mode as cm
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters
from auralis.core.processing.mastering_targets import generate_targets_from_fingerprint
from auralis.core.utils import fingerprint_default
from auralis.dsp.constants import CORPUS_BAND_CENTERS


def _median_fingerprint() -> dict[str, float]:
    fp = {f'{band}_pct': share for band, share in CORPUS_BAND_CENTERS.items()}
    fp.update({'lufs': -14.0, 'crest_db': 12.0})
    return fp


def test_median_fingerprint_gets_zero_band_adjustments():
    """A corpus-median track needs no correction: every band within ±1 dB
    of 0 BEFORE the clamp (they are exactly 0)."""
    targets = generate_targets_from_fingerprint(_median_fingerprint())
    eq = targets['eq_curve_db']
    for band, gain in eq.items():
        assert gain == pytest.approx(0.0, abs=1.0), (
            f'{band}: {gain} dB — the fixed-target tilt is back (#5695)'
        )


def test_median_fingerprint_shelves_within_1db():
    """convert_targets_to_parameters SUMS bands into the shelves; with
    corpus-calibrated ideals the sums are calibrated too."""
    targets = generate_targets_from_fingerprint(_median_fingerprint())
    params = convert_targets_to_parameters(targets)

    for shelf in ('low_shelf_gain', 'high_shelf_gain'):
        assert abs(params.eq_curve[shelf]) < 1.0, (
            f'{shelf}={params.eq_curve[shelf]} dB — the fixed-target tilt is '
            f'back (#5695)'
        )


@pytest.mark.parametrize('overrides', [
    {},
    {'bass_pct': 0.32, 'mid_pct': 0.37},          # tonally far from the median
    {'bass_pct': 0.72, 'low_mid_pct': 0.13},
    {'air_pct': 0.0, 'presence_pct': 0.003},
    {'air_pct': 0.05, 'lufs': -24.0, 'crest_db': 18.0},
])
def test_fixed_target_and_fingerprint_paths_agree(overrides):
    """Cross-path consistency (#5695, #6356): ContinuousMode's own fingerprint path
    (whole-file jobs, the per-chunk fallback) and the streaming fixed targets turn
    the same fingerprint into the same parameters -- every EQ gain, the blend,
    loudness, compression and width -- for ANY fingerprint."""
    complete = {name: fingerprint_default(name) for name in DIMENSION_NAMES}
    fingerprint = {**complete, **_median_fingerprint(), **overrides}
    mode = cm.ContinuousMode(UnifiedConfig(), MagicMock(), MagicMock())
    with patch.object(cm, 'fingerprint_preloaded', return_value=fingerprint):
        from_fingerprint = mode._resolve_parameters(np.zeros((44100, 2)), None)

    fixed = convert_targets_to_parameters(generate_targets_from_fingerprint(fingerprint))

    assert from_fingerprint == fixed


def test_no_second_copy_of_band_ideals_remains():
    """CONSISTENCY: the targets law holds no table of its own, and no corpus
    literal lives outside dsp/constants."""
    import auralis.core.processing.mastering_targets as mt
    import auralis.core.processing.parameter_generator_eq as eq_law

    assert eq_law.CORPUS_BAND_CENTERS is CORPUS_BAND_CENTERS
    assert not hasattr(mt, '_IDEAL_BAND_SHARE')
    root = Path(__file__).resolve().parents[2]
    for rel in (
        'auralis/core/processing/parameter_generator_eq.py',
        'auralis/core/processing/mastering_targets.py',
        'auralis-web/backend/core/mastering_target_service.py',
    ):
        assert '0.4561' not in (root / rel).read_text(), rel


def test_extreme_deviation_stays_inside_the_band_authority():
    """The per-band authority (low shelf: 5 dB) survives the recalibration, and the
    direction is right at both extremes."""
    fp = _median_fingerprint()
    fp['bass_pct'] = 1.0  # everything is bass
    assert -5.0 <= generate_targets_from_fingerprint(fp)['eq_curve_db']['low_shelf_gain'] < 0.0

    fp = _median_fingerprint()
    fp['bass_pct'] = 0.0  # no bass at all
    assert 0.0 < generate_targets_from_fingerprint(fp)['eq_curve_db']['low_shelf_gain'] <= 5.0
