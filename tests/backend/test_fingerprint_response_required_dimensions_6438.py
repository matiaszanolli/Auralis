"""The fingerprint response models promise all 25 dimensions as numbers (#6438).

Every dimension was ``float | None = None``, so the schema advertised a null the DB
(``NOT NULL`` columns) and both emitters never produce, and the frontend - which types the
dimensions as ``number`` - did unguarded arithmetic on them (a null summed as 0).
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.albums_fingerprint import median_fingerprint  # noqa: E402
from routers.albums_models import AlbumFingerprintEntry, AlbumFingerprintResponse  # noqa: E402
from routers.fingerprint_status import TrackFingerprintResponse  # noqa: E402
from schemas import FingerprintVectorResponse  # noqa: E402

DIMENSIONS = sorted(FingerprintVectorResponse.model_fields)


def _full() -> dict[str, float]:
    return {name: 0.5 for name in DIMENSIONS}


def test_vector_has_25_required_dimensions():
    assert len(DIMENSIONS) == 25
    assert all(FingerprintVectorResponse.model_fields[n].is_required() for n in DIMENSIONS)


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_a_null_or_missing_dimension_is_rejected(dimension):
    nulled = {**_full(), dimension: None}
    with pytest.raises(ValidationError):
        FingerprintVectorResponse(**nulled)
    missing = {k: v for k, v in _full().items() if k != dimension}
    with pytest.raises(ValidationError):
        FingerprintVectorResponse(**missing)


def test_album_responses_require_a_fingerprint_instead_of_defaulting_to_all_null():
    with pytest.raises(ValidationError):
        AlbumFingerprintEntry(album_id=1, fingerprinted_track_count=1)
    with pytest.raises(ValidationError):
        AlbumFingerprintResponse(album_id=1, track_count=1, fingerprinted_track_count=1)


def test_track_title_is_required_and_not_null():
    base = {"track_id": 1, "fingerprint": _full()}
    with pytest.raises(ValidationError):
        TrackFingerprintResponse(**base, track_title=None)
    with pytest.raises(ValidationError):
        TrackFingerprintResponse(**base)
    assert TrackFingerprintResponse(**base, track_title="Song").track_title == "Song"


def test_median_emitter_output_satisfies_the_model():
    class Row:
        pass

    rows = []
    for _ in range(3):
        r = Row()
        for col in ("sub_bass_pct bass_pct low_mid_pct mid_pct upper_mid_pct presence_pct air_pct lufs "
                    "crest_db bass_mid_ratio tempo_bpm rhythm_stability transient_density silence_ratio "
                    "spectral_centroid spectral_rolloff spectral_flatness harmonic_ratio pitch_stability "
                    "chroma_energy dynamic_range_variation loudness_variation_std peak_consistency "
                    "stereo_width phase_correlation").split():
            setattr(r, col, 0.25)
        rows.append(r)
    parsed = FingerprintVectorResponse(**median_fingerprint(rows))
    assert set(parsed.model_dump()) == set(DIMENSIONS)
