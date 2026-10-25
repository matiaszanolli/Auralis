"""
Fixed-target EQ is calibrated to the corpus centers (#5695)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fixed-target path compared each band's share with hand-set "ideal"
shares that described nothing real fingerprints look like, then summed
bands into shelves — a corpus-median track got bass clamped at -6 dB and a
+9.5 dB high shelf, a content-independent bass-cut/treble-boost on every
fixed-target render. The ideals are now the 512-track corpus medians in
``auralis/dsp/constants.CORPUS_BAND_CENTERS``, shared with the per-chunk
fingerprint EQ path so the two cannot drift.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from auralis.core.processing.fixed_target_params import convert_targets_to_parameters
from auralis.core.processing.parameter_generator_eq import generate_eq_curve
from auralis.dsp.constants import CORPUS_BAND_CENTERS

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.mastering_target_generation import generate_targets_from_fingerprint  # noqa: E402


def _median_fingerprint() -> dict[str, float]:
    fp = {f'{band}_pct': share for band, share in CORPUS_BAND_CENTERS.items()}
    fp.update({'lufs': -14.0, 'crest_db': 12.0})
    return fp


def test_median_fingerprint_gets_zero_band_adjustments():
    """A corpus-median track needs no correction: every band within ±1 dB
    of 0 BEFORE the clamp (they are exactly 0)."""
    targets = generate_targets_from_fingerprint(_median_fingerprint())
    eq = targets['eq_adjustments_db']
    for band, center in CORPUS_BAND_CENTERS.items():
        assert eq[band] == pytest.approx(0.0, abs=1.0), (
            f'{band}: {eq[band]} dB — the fixed-target tilt is back (#5695)'
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


def test_fixed_target_and_per_chunk_paths_agree_near_center():
    """Cross-path consistency: the per-chunk fingerprint EQ
    (generate_eq_curve) and the fixed-target shelves for the same
    corpus-median material differ by < 2 dB across the spectrum."""
    coords = SimpleNamespace(fingerprint=_median_fingerprint())
    per_chunk = generate_eq_curve(coords, None)

    targets = generate_targets_from_fingerprint(_median_fingerprint())
    fixed = convert_targets_to_parameters(targets)

    for shelf in ('low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_mid_gain', 'high_shelf_gain'):
        assert abs(fixed.eq_curve[shelf] - per_chunk[shelf]) < 2.0, (
            f'{shelf}: fixed-target {fixed.eq_curve[shelf]:.2f} dB vs '
            f'per-chunk {per_chunk[shelf]:.2f} dB (#5695)'
        )


def test_no_second_copy_of_band_ideals_remains():
    """CONSISTENCY: the fixed-target path's table IS the shared table (same
    object), and no corpus literal lives outside dsp/constants."""
    import core.mastering_target_generation as mtg

    assert mtg._IDEAL_BAND_SHARE is CORPUS_BAND_CENTERS
    root = Path(__file__).resolve().parents[2]
    for rel in (
        'auralis/core/processing/parameter_generator_eq.py',
        'auralis-web/backend/core/mastering_target_generation.py',
        'auralis-web/backend/core/mastering_target_service.py',
    ):
        assert '0.4561' not in (root / rel).read_text(), rel


def test_extreme_deviation_still_clamps():
    """The ±6 dB per-band ceiling survives the recalibration."""
    fp = _median_fingerprint()
    fp['bass_pct'] = 1.0  # everything is bass
    eq = generate_targets_from_fingerprint(fp)['eq_adjustments_db']
    assert eq['bass'] == -6.0

    fp = _median_fingerprint()
    fp['bass_pct'] = 0.0  # no bass at all
    eq = generate_targets_from_fingerprint(fp)['eq_adjustments_db']
    assert eq['bass'] == 6.0
