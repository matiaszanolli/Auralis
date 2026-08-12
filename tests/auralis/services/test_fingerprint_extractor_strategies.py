"""Behaviour of the split `extract_and_store` strategies (#4283).

`FingerprintExtractor.extract_and_store` was a 146-line method nesting sidecar
validity, sidecar version, file-size guard, analysis, dimension filtering and
the DB write at depth 5. It is now a dispatcher over four strategy methods:
`_load_sidecar_fingerprint`, `_compute_fingerprint`, `_prepare_for_storage` and
`_write_sidecar`.

A pure-refactor split is only safe if the branch behaviour is pinned, so each
decision the old nest made is asserted here against the seam it now lives on —
in particular the ones that must NOT store anything: stale sidecar version,
short sidecar, oversized file, incomplete vector, failed upsert.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.metrics.constants import (
    FINGERPRINT_DIMENSION_NAMES,
    FingerprintConstants,
)
from auralis.services.fingerprint_extractor import (
    MAX_FINGERPRINT_FILE_SIZE_MB,
    FingerprintExtractor,
)


def _complete_fingerprint(**overrides) -> dict:
    """A full 25-dimension fingerprint, all dimensions present."""
    fp = {name: 0.5 for name in FINGERPRINT_DIMENSION_NAMES}
    fp.update(overrides)
    return fp


@pytest.fixture
def repo():
    r = MagicMock()
    r.upsert.return_value = True
    return r


@pytest.fixture
def extractor(repo):
    """Extractor with sidecars enabled and a mocked SidecarManager."""
    with patch("auralis.services.fingerprint_extractor.AudioFingerprintAnalyzer"):
        ex = FingerprintExtractor(fingerprint_repository=repo, use_sidecar_files=True)
    ex.sidecar_manager = MagicMock()
    ex.sidecar_manager.is_valid.return_value = False
    return ex


@pytest.fixture
def audio_file(tmp_path) -> Path:
    path = tmp_path / "track.flac"
    path.write_bytes(b"\0" * 2048)
    return path


class TestDimensionNamesConstant:
    """The names and the count must not drift apart (#4283)."""

    def test_name_count_matches_declared_dimension_count(self):
        assert len(FINGERPRINT_DIMENSION_NAMES) == FingerprintConstants.FINGERPRINT_DIMENSIONS

    def test_version_key_is_not_a_dimension(self):
        """fingerprint_version is stamped alongside the vector, not part of it."""
        assert "fingerprint_version" not in FINGERPRINT_DIMENSION_NAMES


class TestSidecarStrategy:
    """`_load_sidecar_fingerprint` — the fast path and every reason to skip it."""

    def test_valid_current_sidecar_is_used_and_no_analysis_runs(self, extractor, audio_file):
        extractor.sidecar_manager.is_valid.return_value = True
        extractor.sidecar_manager.get_fingerprint.return_value = _complete_fingerprint(
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION
        )

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint"
        ) as analyse:
            assert extractor.extract_and_store(1, str(audio_file)) is True

        analyse.assert_not_called()
        extractor.fingerprint_repo.upsert.assert_called_once()

    def test_cached_fingerprint_is_not_written_back_as_a_sidecar(self, extractor, audio_file):
        """It came FROM the sidecar; rewriting it is pure I/O for nothing."""
        extractor.sidecar_manager.is_valid.return_value = True
        extractor.sidecar_manager.get_fingerprint.return_value = _complete_fingerprint(
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION
        )

        extractor.extract_and_store(1, str(audio_file))

        extractor.sidecar_manager.write.assert_not_called()

    def test_stale_algorithm_version_falls_through_to_analysis(self, extractor, audio_file):
        extractor.sidecar_manager.is_valid.return_value = True
        extractor.sidecar_manager.get_fingerprint.return_value = _complete_fingerprint(
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION - 1
        )

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(),
        ) as analyse:
            assert extractor.extract_and_store(1, str(audio_file)) is True

        analyse.assert_called_once()

    def test_short_sidecar_vector_falls_through_to_analysis(self, extractor, audio_file):
        extractor.sidecar_manager.is_valid.return_value = True
        extractor.sidecar_manager.get_fingerprint.return_value = {"lufs": -14.0}

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(),
        ) as analyse:
            assert extractor.extract_and_store(1, str(audio_file)) is True

        analyse.assert_called_once()

    def test_sidecar_not_consulted_when_feature_disabled(self, repo, audio_file):
        with patch("auralis.services.fingerprint_extractor.AudioFingerprintAnalyzer"):
            ex = FingerprintExtractor(fingerprint_repository=repo, use_sidecar_files=False)
        assert ex.sidecar_manager is None

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(),
        ):
            assert ex.extract_and_store(1, str(audio_file)) is True

    def test_returns_none_when_sidecar_invalid(self, extractor, audio_file):
        extractor.sidecar_manager.is_valid.return_value = False
        assert extractor._load_sidecar_fingerprint(1, audio_file) is None


class TestComputeStrategy:
    """`_compute_fingerprint` — the size guard and the analyzer contract."""

    def test_oversized_file_is_skipped_without_analysis(self, extractor, tmp_path):
        big = tmp_path / "big.flac"
        big.write_bytes(b"\0" * 16)
        over_bytes = int((MAX_FINGERPRINT_FILE_SIZE_MB + 1) * 1024 * 1024)

        with (
            patch.object(Path, "stat") as stat,
            patch(
                "auralis.services.fingerprint_extractor.compute_windowed_fingerprint"
            ) as analyse,
        ):
            stat.return_value = MagicMock(st_size=over_bytes)
            assert extractor._compute_fingerprint(1, big) is None

        analyse.assert_not_called()

    def test_analyzer_returning_none_is_reported_as_failure(self, extractor, audio_file):
        """compute_windowed_fingerprint returns None on failure, not {} (#4595)."""
        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=None,
        ):
            assert extractor._compute_fingerprint(1, audio_file) is None
            assert extractor.extract_and_store(1, str(audio_file)) is False

        extractor.fingerprint_repo.upsert.assert_not_called()

    def test_intermediates_are_released_even_when_analysis_raises(self, extractor, audio_file):
        """The gc.collect() is in a finally: a raising analyzer must still hit it."""
        with (
            patch(
                "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
                side_effect=RuntimeError("decode failed"),
            ),
            patch("auralis.services.fingerprint_extractor.gc.collect") as collect,
        ):
            with pytest.raises(RuntimeError):
                extractor._compute_fingerprint(1, audio_file)

        collect.assert_called_once()

    def test_extract_and_store_swallows_analysis_errors(self, extractor, audio_file):
        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            side_effect=RuntimeError("decode failed"),
        ):
            assert extractor.extract_and_store(1, str(audio_file)) is False


class TestPrepareForStorage:
    """`_prepare_for_storage` — filtering, completeness, version stamping."""

    def test_metadata_keys_are_stripped(self, extractor):
        raw = _complete_fingerprint(_harmonic_analysis_method="rust", extra_junk=1)

        stored = extractor._prepare_for_storage(1, raw)

        assert stored is not None
        assert "_harmonic_analysis_method" not in stored
        assert "extra_junk" not in stored

    def test_version_is_stamped_from_the_authoritative_constant(self, extractor):
        stored = extractor._prepare_for_storage(1, _complete_fingerprint())

        assert stored["fingerprint_version"] == FINGERPRINT_ALGORITHM_VERSION

    def test_every_dimension_survives_filtering(self, extractor):
        stored = extractor._prepare_for_storage(1, _complete_fingerprint())

        assert FINGERPRINT_DIMENSION_NAMES <= set(stored)

    def test_incomplete_vector_is_rejected(self, extractor):
        """#3306: a partial vector must never be stored as a zero-padded row."""
        partial = _complete_fingerprint()
        partial.pop("lufs")

        assert extractor._prepare_for_storage(1, partial) is None

    def test_incomplete_vector_never_reaches_the_repository(self, extractor, audio_file):
        partial = _complete_fingerprint()
        partial.pop("stereo_width")

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=partial,
        ):
            assert extractor.extract_and_store(1, str(audio_file)) is False

        extractor.fingerprint_repo.upsert.assert_not_called()
        extractor.sidecar_manager.write.assert_not_called()

    def test_metadata_only_payload_is_rejected_not_stored_empty(self, extractor):
        assert extractor._prepare_for_storage(1, {"_harmonic_analysis_method": "rust"}) is None


class TestStoreAndSidecarWrite:
    """The dispatcher's DB write and sidecar write-back ordering."""

    def test_fresh_analysis_writes_a_sidecar(self, extractor, audio_file):
        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(),
        ):
            assert extractor.extract_and_store(7, str(audio_file)) is True

        extractor.sidecar_manager.write.assert_called_once()
        written_path, payload = extractor.sidecar_manager.write.call_args[0]
        assert written_path == audio_file
        assert payload["metadata"]["track_id"] == 7
        assert payload["metadata"]["filename"] == audio_file.name
        assert payload["fingerprint"]["fingerprint_version"] == FINGERPRINT_ALGORITHM_VERSION

    def test_failed_upsert_returns_false_and_skips_the_sidecar(self, extractor, audio_file):
        """No sidecar for a fingerprint the DB rejected — it would then be
        served from cache forever without a matching row."""
        extractor.fingerprint_repo.upsert.return_value = False

        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(),
        ):
            assert extractor.extract_and_store(1, str(audio_file)) is False

        extractor.sidecar_manager.write.assert_not_called()

    def test_stored_vector_is_the_filtered_one(self, extractor, audio_file):
        with patch(
            "auralis.services.fingerprint_extractor.compute_windowed_fingerprint",
            return_value=_complete_fingerprint(_harmonic_analysis_method="rust"),
        ):
            extractor.extract_and_store(1, str(audio_file))

        _track_id, stored = extractor.fingerprint_repo.upsert.call_args[0]
        assert "_harmonic_analysis_method" not in stored
        assert set(stored) == FINGERPRINT_DIMENSION_NAMES | {"fingerprint_version"}
