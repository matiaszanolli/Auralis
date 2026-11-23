"""
Regression: one targets law for every render path (#6356)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once a reference cloud existed, whole-file jobs took their EQ from ``delta_eq``,
a second band-to-gain law that drove half the high shelf from the air share the
streaming law deliberately ignores (the fingerprint's air band stops at 11 kHz).
A corpus-median track with 3x the corpus air share got 0.00 dB everywhere when
streamed and -0.98 dB of high shelf when exported, and the two paths also
differed in loudness plan, compression, blend and width.

Every path now builds its targets with ``mastering_targets``; the cloud only
changes the band centers the one EQ law pulls toward.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES
from auralis.core.config import UnifiedConfig
from auralis.core.processing import continuous_mode as cm
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters
from auralis.core.processing.mastering_targets import generate_targets_from_fingerprint
from auralis.core.processing.parameter_generator_eq import (
    band_centers_from_target,
    eq_curve_from_fingerprint,
)
from auralis.core.utils import fingerprint_default
from auralis.dsp.constants import CORPUS_BAND_CENTERS

ROOT = Path(__file__).resolve().parents[3]


def _median_fingerprint(**overrides: float) -> dict[str, float]:
    fp = {name: fingerprint_default(name) for name in DIMENSION_NAMES}
    fp.update({f'{band}_pct': share for band, share in CORPUS_BAND_CENTERS.items()})
    fp.update(overrides)
    return fp


class _Ref:
    """ORM-like reference row: every dimension at the median, with overrides."""

    __table__ = object()

    def __init__(self, track_id: int, **overrides: float):
        self.track_id = track_id
        self.reference_weight = 1.0
        for name, value in _median_fingerprint(**overrides).items():
            setattr(self, name, value)


class _Repo:
    def __init__(self, cloud):
        self._cloud = cloud

    def get_reference_cloud(self):
        return list(self._cloud)


def _job_params(fingerprint, cloud=None):
    """Parameters as a whole-file job derives them (ContinuousMode, no fixed targets)."""
    mode = cm.ContinuousMode(
        UnifiedConfig(), MagicMock(), MagicMock(),
        fingerprint_repository=_Repo(cloud) if cloud else None,
    )
    with patch.object(cm, 'fingerprint_preloaded', return_value=fingerprint):
        return mode._resolve_parameters(np.zeros((44100, 2)), None)


AIR_HEAVY = _median_fingerprint(air_pct=3 * CORPUS_BAND_CENTERS['air'])


class TestAirShareMovesNoShelf:
    def test_streaming_targets(self):
        targets = generate_targets_from_fingerprint(AIR_HEAVY)
        assert targets['eq_curve_db']['high_shelf_gain'] == 0.0

    def test_whole_file_job_without_a_cloud(self):
        assert _job_params(AIR_HEAVY).eq_curve['high_shelf_gain'] == 0.0

    def test_whole_file_job_with_a_cloud_whose_air_differs(self):
        """The delta_eq case: cloud target air != source air used to cut the shelf."""
        cloud = [_Ref(i, air_pct=CORPUS_BAND_CENTERS['air']) for i in range(5)]
        assert _job_params(AIR_HEAVY, cloud).eq_curve['high_shelf_gain'] == 0.0

    def test_streaming_and_job_agree_on_an_air_heavy_track(self):
        streamed = convert_targets_to_parameters(generate_targets_from_fingerprint(AIR_HEAVY))
        assert _job_params(AIR_HEAVY) == streamed


class TestCloudOnlyMovesTheCenters:
    def test_job_with_a_cloud_uses_the_one_law_with_cloud_centers(self):
        cloud = [_Ref(i, bass_pct=0.30, mid_pct=0.30) for i in range(5)]
        source = _median_fingerprint(bass_pct=0.50)

        params = _job_params(source, cloud)

        expected = eq_curve_from_fingerprint(source, {**CORPUS_BAND_CENTERS, 'bass': 0.30, 'mid': 0.30})
        for band, gain in expected.items():
            assert params.eq_curve[band] == pytest.approx(gain)

    def test_corpus_centers_are_the_no_cloud_default(self):
        assert band_centers_from_target(None) == CORPUS_BAND_CENTERS
        assert eq_curve_from_fingerprint(AIR_HEAVY) == eq_curve_from_fingerprint(
            AIR_HEAVY, CORPUS_BAND_CENTERS
        )

    def test_a_band_the_target_lacks_keeps_its_corpus_center(self):
        centers = band_centers_from_target({'bass_pct': 0.3})
        assert centers['bass'] == 0.3
        assert centers['mid'] == CORPUS_BAND_CENTERS['mid']


def test_the_eq_law_has_exactly_one_caller():
    """WIRING: every path reaches the EQ law through the targets law, so no
    second band-to-gain derivation can reappear beside it."""
    callers = []
    for base in ('auralis', 'auralis-web/backend'):
        for path in (ROOT / base).rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            if re.search(r'\beq_curve_from_fingerprint\(', text) and path.name != 'parameter_generator_eq.py':
                callers.append(path.relative_to(ROOT).as_posix())
    assert callers == ['auralis/core/processing/mastering_targets.py']
    assert not (ROOT / 'auralis/core/processing/delta_eq.py').exists()
