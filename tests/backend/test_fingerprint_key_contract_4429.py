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
:license: GPLv3, see LICENSE for more details.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRACK_ROUTER = _REPO_ROOT / "auralis-web" / "backend" / "routers" / "fingerprint_status.py"
_ALBUM_ROUTER = _REPO_ROOT / "auralis-web" / "backend" / "routers" / "albums.py"
_FE_TYPE = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "utils" / "fingerprintToGradient.ts"
)

# Envelope/identity keys that live alongside the 25 fingerprint dimensions in
# the response but are not part of the AudioFingerprint shape.
_NON_DIMENSION_KEYS = {
    "track_id",
    "has_fingerprint",
    "status",
    "message",
    "fingerprint",
    "computed_at",
    "version",
    "album_id",
    "track_count",
}


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


def _emitted_keys(path: Path) -> set[str]:
    """Fingerprint dict keys the given router emits."""
    source = path.read_text()
    source = re.sub(r"#[^\n]*", "", source)  # drop comments
    keys = set(re.findall(r"""["']([a-z_][a-z0-9_]*)["']\s*:\s*""", source))
    # albums.py emits via ('db_col', 'api_key') tuples rather than dict literals.
    keys |= {api for _db, api in re.findall(r"""\(\s*['"]([a-z_]+)['"]\s*,\s*['"]([a-z_]+)['"]\s*\)""", source)}
    return keys - _NON_DIMENSION_KEYS


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


def test_track_endpoint_dimension_keys_exist_on_frontend_type():
    """Every fingerprint key the track endpoint emits is modelled on the FE."""
    fe = _frontend_fields()
    emitted = _emitted_keys(_TRACK_ROUTER)
    # Only compare keys that look like fingerprint dimensions: the FE type is
    # the authority on the dimension set, so anything it already knows about,
    # plus the one under test, must reconcile.
    dimensions = {k for k in emitted if k in fe or k.startswith("loudness_variation")}
    missing = dimensions - fe
    assert not missing, (
        f"{_TRACK_ROUTER.name} emits fingerprint keys with no AudioFingerprint "
        f"field: {sorted(missing)}"
    )


def test_both_routers_agree_on_the_loudness_key():
    """SIBLING: albums.py emits the same fingerprint shape as the track route."""
    for path in (_TRACK_ROUTER, _ALBUM_ROUTER):
        keys = _emitted_keys(path)
        assert "loudness_variation_std" in keys, (
            f"{path.name} no longer emits loudness_variation_std"
        )
        assert "loudness_variation" not in keys, (
            f"{path.name} emits the bare `loudness_variation`, which the "
            f"frontend does not model (#4429)"
        )
