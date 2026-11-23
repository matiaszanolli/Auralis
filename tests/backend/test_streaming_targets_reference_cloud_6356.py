"""
Streaming fixed targets pull toward the reference cloud, like whole-file jobs (#6356)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The soft k-NN target only ever reached ContinuousMode's own fingerprint path, so a
streamed track was toned against the corpus centers while the same track exported
as a job was toned against its nearest references. MasteringTargetService now asks
the same ReferenceCloud, so both paths produce one plan.
"""

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
from core.mastering_target_service import MasteringTargetService


def _fingerprint(**overrides: float) -> dict[str, float]:
    fp = {name: fingerprint_default(name) for name in DIMENSION_NAMES}
    fp.update({f'{band}_pct': share for band, share in CORPUS_BAND_CENTERS.items()})
    fp.update(overrides)
    return fp


class _Ref:
    __table__ = object()

    def __init__(self, track_id: int, **overrides: float):
        self.track_id = track_id
        self.reference_weight = 1.0
        for name, value in _fingerprint(**overrides).items():
            setattr(self, name, value)


class _Repo:
    def __init__(self, cloud):
        self.cloud = cloud

    def get_reference_cloud(self):
        if isinstance(self.cloud, Exception):
            raise self.cloud
        return list(self.cloud)


SOURCE = _fingerprint(bass_pct=0.55, mid_pct=0.15)
CLOUD = [_Ref(i, bass_pct=0.30, mid_pct=0.30) for i in range(6)]


def test_streaming_targets_use_the_cloud_centers():
    service = MasteringTargetService(get_fingerprints_repository=lambda: _Repo(CLOUD))

    targets = service.generate_targets_from_fingerprint(SOURCE)

    expected = generate_targets_from_fingerprint(
        SOURCE, {**CORPUS_BAND_CENTERS, 'bass': 0.30, 'mid': 0.30}
    )
    assert targets['eq_curve_db'] == pytest.approx(expected['eq_curve_db'])
    assert targets['eq_curve_db'] != pytest.approx(
        generate_targets_from_fingerprint(SOURCE)['eq_curve_db']
    )


@pytest.mark.parametrize('repo', [None, _Repo([]), _Repo(RuntimeError('db busy')), object()])
def test_no_usable_cloud_falls_back_to_corpus_centers(repo):
    """No repository, an empty cloud, a failing read, or a repository without the
    method: corpus centers, never an exception or missing targets."""
    service = MasteringTargetService(get_fingerprints_repository=(lambda: repo) if repo else None)

    assert service.generate_targets_from_fingerprint(SOURCE) == generate_targets_from_fingerprint(SOURCE)


def test_a_stream_and_a_whole_file_job_get_the_same_plan():
    repo = _Repo(CLOUD)
    streamed = convert_targets_to_parameters(
        MasteringTargetService(get_fingerprints_repository=lambda: repo)
        .generate_targets_from_fingerprint(SOURCE)
    )

    mode = cm.ContinuousMode(UnifiedConfig(), MagicMock(), MagicMock(), fingerprint_repository=repo)
    with patch.object(cm, 'fingerprint_preloaded', return_value=SOURCE):
        job = mode._resolve_parameters(np.zeros((44100, 2)), None)

    assert job == streamed
