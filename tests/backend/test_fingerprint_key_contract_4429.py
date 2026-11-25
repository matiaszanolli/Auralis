"""Contract: the fingerprint payload keys match the frontend type (#4429).

`GET /api/tracks/{id}/fingerprint` emitted `loudness_variation_std` while the
frontend `AudioFingerprint` interface declared `loudness_variation`. The field
is optional on the TS side, so nothing failed to compile and nothing threw —
the value was simply `undefined` forever.

That was not cosmetic. `albumCharacterDescriptors.analyzeDynamics` reads it as
``fp.loudness_variation ?? 1.5``, and 1.5 sits between the two thresholds
(``> 2.5`` → "Variable", ``< 1.0`` → "Consistent"), so the fallback matched
neither branch and those dynamics tags could never be emitted for any album.

A silent-undefined mismatch on an optional field is invisible to both type
systems, so this test closes the class rather than the instance: every key the
backend emits must exist on the frontend interface.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES
from auralis.library.models import Track

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from routers.albums_fingerprint import get_album_fingerprint  # noqa: E402
from routers.fingerprint_status import get_track_fingerprint  # noqa: E402

_FE_TYPE = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "utils" / "fingerprintToGradient.ts"
)


def _frontend_fields() -> set[str]:
    """Field names declared on the `AudioFingerprint` interface."""
    source = _FE_TYPE.read_text()
    match = re.search(
        r"export interface AudioFingerprint\s*\{(.*?)^\}", source, re.DOTALL | re.MULTILINE
    )
    assert match, "could not locate the AudioFingerprint interface"
    body = match.group(1)
    # Strip block and line comments so commented-out field names don't count.
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    return set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\??\s*:", body, re.MULTILINE))


def test_loudness_variation_key_matches():
    """The specific #4429 mismatch, pinned by name."""
    fe = _frontend_fields()
    assert "loudness_variation_std" in fe, (
        "AudioFingerprint must declare loudness_variation_std — the key both "
        "routers actually emit and the name used by the DB column and every "
        "Python consumer."
    )
    assert "loudness_variation" not in fe, (
        "AudioFingerprint still declares the old `loudness_variation`, which no "
        "backend emitter ever sends (#4429)."
    )


@pytest.mark.asyncio
async def test_both_routers_agree_on_the_loudness_key():
    stored = SimpleNamespace(**dict.fromkeys(DIMENSION_NAMES, 0.25))
    stored.loudness_variation_std = 3.25
    repos = Mock()
    repos.tracks.get_by_id.return_value = Track(title="Song", filepath="/music/song.wav")
    repos.albums.get_summary.return_value = SimpleNamespace(title="Album", track_count_expr=1)
    repos.fingerprints.get_by_track_id.return_value = stored
    repos.fingerprints.get_by_album_ids.return_value = {1: [stored]}

    track = (await get_track_fingerprint(1, repos=repos))["fingerprint"]
    album = (await get_album_fingerprint(1, repos=repos))["fingerprint"]

    frontend = _frontend_fields()
    assert set(track) == set(album) == frontend
    assert track["loudness_variation_std"] == album["loudness_variation_std"] == 3.25
