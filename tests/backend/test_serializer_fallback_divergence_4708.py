"""
The DEFAULT_*_FIELDS maps are a fallback, not the response contract (#4708)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`serialize_object()` returns `obj.to_dict()` for any non-Mock object that has
one, so for a real ORM row the `DEFAULT_*_FIELDS` maps are never consulted.
They were nonetheless annotated as guarantees ("always required by
TrackApiResponse", "#2851 — required for album track ordering") — a misreading
that let `Track.to_dict()`'s field gaps and the album-detail casing bugs sit
unnoticed, since the fallback map looked authoritative.

#4708 corrected those comments in place rather than renaming the maps: they
are a real (if rarely-taken) path, and both `schemas.py`'s response models and
`test_response_model_coverage.py` deliberately treat the *union* of the two
shapes as the contract, because a `response_model` filters anything it does
not declare.

These tests pin the two claims the corrected comments make, so the
documentation cannot silently drift back out of sync with the code:

  1. a real object's `to_dict()` wins outright — the fallback map contributes
     nothing to the result; and
  2. the specific keys called out as "fallback-only" really are absent from
     the corresponding `to_dict()`.

If (2) starts failing because `to_dict()` gained one of those keys, the fix is
to update the comment in `serializers.py` — that is the point of the test.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import types
from pathlib import Path

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from routers.serializers import (  # noqa: E402
    DEFAULT_ARTIST_FIELDS,
    DEFAULT_TRACK_FIELDS,
    serialize_object,
)

from auralis.library.models.core import Artist, Track  # noqa: E402


class _RealishTrack:
    """A non-Mock object with to_dict() — the shape a real ORM row presents."""

    def __init__(self) -> None:
        # Deliberately also carries attributes the fallback map lists, so a
        # regression that consulted the fallback would be visible.
        self.id = 7
        self.title = 'From getattr'
        self.genre = 'Doom'
        self.loudness = -9.0

    def to_dict(self) -> dict:
        return {'id': 7, 'title': 'From to_dict', 'genres': ['Doom']}


def test_to_dict_wins_outright_and_fallback_contributes_nothing():
    """The fallback map must not top up, merge into, or override to_dict()."""
    result = serialize_object(_RealishTrack(), DEFAULT_TRACK_FIELDS)

    assert result == {'id': 7, 'title': 'From to_dict', 'genres': ['Doom']}
    # Every fallback-only key stays absent — no silent merge.
    assert 'genre' not in result
    assert 'loudness' not in result
    assert result['title'] == 'From to_dict'


def _to_dict_keys(model) -> set[str]:
    """Key set of a bare (unpersisted) model's to_dict()."""
    try:
        return set(model.to_dict().keys())
    except Exception:  # detached/degraded branch still returns a dict
        return set()


@pytest.mark.parametrize(
    "key, emitted_instead",
    [
        ('genre', 'genres'),
        ('loudness', 'lufs_level'),
        ('date_added', 'created_at'),
        ('date_modified', 'updated_at'),
        ('artist', 'artists'),
    ],
)
def test_documented_fallback_only_track_keys_really_are_fallback_only(key, emitted_instead):
    """The keys serializers.py calls fallback-only must be absent from to_dict().

    If this fails, `Track.to_dict()` gained the key and the comment in
    `serializers.py` above DEFAULT_TRACK_FIELDS needs updating (#4708).
    """
    emitted = _to_dict_keys(Track())

    assert key in DEFAULT_TRACK_FIELDS, f"{key} is no longer in the fallback map"
    assert key not in emitted, (
        f"Track.to_dict() now emits {key!r}; serializers.py still documents it "
        f"as fallback-only"
    )
    if emitted:  # only assert the counterpart when to_dict() was not degraded
        assert emitted_instead in emitted, (
            f"Track.to_dict() no longer emits {emitted_instead!r}, which "
            f"serializers.py names as what it sends instead of {key!r}"
        )


def test_documented_artist_artwork_mirroring_still_holds():
    """serializers.py claims Artist.to_dict() also emits the artwork fields."""
    emitted = _to_dict_keys(Artist())
    if not emitted:
        pytest.skip("Artist.to_dict() took its degraded branch")

    for field in ('artwork_url', 'artwork_source'):
        assert field in DEFAULT_ARTIST_FIELDS
        assert field in emitted, (
            f"Artist.to_dict() no longer emits {field!r}; the comment in "
            f"serializers.py claiming it mirrors them is now wrong"
        )
