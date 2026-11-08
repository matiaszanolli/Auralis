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
])
def test_fixed_target_and_per_chunk_paths_agree(overrides):
    """Cross-path consistency: the per-chunk fingerprint EQ (generate_eq_curve) and
    the fixed-target EQ come from one law, so they agree for ANY fingerprint --
    not only near the corpus median, where the two laws used to coincide."""
    fingerprint = {**_median_fingerprint(), **overrides}
    coords = SimpleNamespace(fingerprint=fingerprint)
    per_chunk = generate_eq_curve(coords, None)

    targets = generate_targets_from_fingerprint(fingerprint)
    fixed = convert_targets_to_parameters(targets)

    for shelf in ('low_shelf_gain', 'low_mid_gain', 'mid_gain', 'high_mid_gain', 'high_shelf_gain'):
        assert fixed.eq_curve[shelf] == pytest.approx(per_chunk[shelf], abs=1e-9), (
            f'{shelf}: fixed-target {fixed.eq_curve[shelf]:.2f} dB vs '
            f'per-chunk {per_chunk[shelf]:.2f} dB (#5695)'
        )


def test_no_second_copy_of_band_ideals_remains():
    """CONSISTENCY: the fixed-target path reads the shared table (same object) and
    holds no table of its own, and no corpus literal lives outside dsp/constants."""
    import core.mastering_target_generation as mtg

    assert mtg.CORPUS_BAND_CENTERS is CORPUS_BAND_CENTERS
    assert not hasattr(mtg, '_IDEAL_BAND_SHARE')
    root = Path(__file__).resolve().parents[2]
    for rel in (
        'auralis/core/processing/parameter_generator_eq.py',
        'auralis-web/backend/core/mastering_target_generation.py',
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
