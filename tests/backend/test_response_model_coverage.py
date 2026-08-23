"""Every JSON endpoint declares a `response_model`, and no model drops a field (#3838).

Two distinct failure modes are pinned here, because the fix for the first one
*creates* the second:

1. **Coverage.** ~45 endpoints across 14 routers returned bare
   `dict[str, Any]`, so their OpenAPI "Schema" tab was empty and no typed
   client could be generated from them. `test_every_json_route_declares_a_response_model`
   is the ratchet: a new route without one fails unless it is added to
   `EXEMPT` with a reason.

2. **Silent field deletion.** `response_model` FILTERS the response — any key
   the model does not declare is stripped before it reaches the client, with
   no error and no log line. That makes an incomplete model strictly worse
   than no model at all. The serializers here have *two* live output shapes
   that do not agree — `Model.to_dict()` and the `DEFAULT_*_FIELDS` getattr
   fallback `serialize_object()` uses for Mocks and detached instances — so a
   model derived from either one alone silently deletes the other's extra
   keys. The `*_covers_*` tests below compute the union from the real code and
   assert the model is a superset.

The union is computed, never hand-listed: hand-listing would reintroduce
exactly the drift this is meant to catch.
"""

import re
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from routers.serializers import (  # noqa: E402
    DEFAULT_ALBUM_FIELDS,
    DEFAULT_ARTIST_FIELDS,
    DEFAULT_PLAYLIST_FIELDS,
    DEFAULT_TRACK_FIELDS,
)
from schemas import (  # noqa: E402
    AlbumResponse,
    FingerprintVectorResponse,
    PlaylistResponse,
    TrackResponse,
)

from auralis.library.models.core import Album, Artist, Playlist, Track  # noqa: E402


# ---------------------------------------------------------------------------
# Routes exempt from the response_model requirement
# ---------------------------------------------------------------------------
#
# Keyed by "<path-relative-to-backend>:<route path>". Each entry needs a reason;
# "we didn't get to it" is not one — that is what this test exists to catch.
EXEMPT: dict[str, str] = {
    "main.py:/": "returns HTMLResponse (dev banner / frontend-missing page), not JSON",
    "routers/artwork.py:/api/albums/{album_id}/artwork": "returns raw image bytes",
    "routers/processing_api.py:/job/{job_id}/download": "returns FileResponse (audio file)",
    # Not endpoints at all — `@router.get(...)` inside docstring examples. Left
    # as exemptions rather than special-cased in the scanner, so that if either
    # example ever becomes a real route it shows up here instead of passing
    # silently.
    "routers/dependencies.py:/api/tracks": "docstring example, not a registered route",
    "routers/dependencies.py:/api/artists": "docstring example, not a registered route",
    "routers/pagination.py:/api/artists": "docstring example, not a registered route",
}

_DECORATOR_RE = re.compile(r"\s*@(?:router|app)\.(get|post|delete|put|patch)\(")
# Routers converted under #4670 hoist their handlers to module level and
# register them from a short assembler with explicit `add_api_route()` calls
# instead of decorating nested closures. Those routes carry exactly the same
# obligation, so the scanner has to recognise both spellings — matching only
# decorators would silently drop every converted router out of the ratchet.
_ADD_ROUTE_RE = re.compile(r"\s*(?:router|app)\.add_api_route\(")


def _iter_route_decorators():
    """Yield (relpath, line_no, method, route_path, has_response_model).

    Parses source rather than introspecting the live app: several routers are
    built by `create_*_router()` factories whose registration depends on
    optional imports, so an import-time failure would silently shrink the set
    the ratchet checks — the opposite of what a ratchet is for.
    """
    for path in sorted(_BACKEND.rglob("*.py")):
        rel = path.relative_to(_BACKEND)
        if any(part in {".mypy_cache", "build", "dist", "__pycache__"} for part in rel.parts):
            continue
        lines = path.read_text().split("\n")
        for i, line in enumerate(lines):
            match = _DECORATOR_RE.match(line)
            add_match = _ADD_ROUTE_RE.match(line) if not match else None
            if not match and not add_match:
                continue
            # Consume until the decorator's parens balance — response_model=
            # is frequently on a continuation line.
            depth = 0
            chunk = []
            j = i
            while j < len(lines):
                chunk.append(lines[j])
                depth += lines[j].count("(") - lines[j].count(")")
                if depth <= 0:
                    break
                j += 1
            decorator = "\n".join(chunk)
            route = re.search(r'\(\s*["\']([^"\']*)["\']', decorator)
            route_path = route.group(1) if route else "?"
            has_model = "response_model=" in decorator
            if match:
                yield (str(rel), i + 1, match.group(1).upper(), route_path, has_model)
                continue
            # add_api_route() takes its verbs as a list, so one call can be
            # several routes; yield each so the ratchet counts them all.
            methods = re.search(r"methods\s*=\s*\[([^\]]*)\]", decorator)
            for verb in re.findall(r'["\'](\w+)["\']', methods.group(1) if methods else ""):
                yield (str(rel), i + 1, verb.upper(), route_path, has_model)


class TestRouteCoverage:
    """Every JSON-returning route carries a response_model."""

    def test_every_json_route_declares_a_response_model(self):
        missing = [
            (rel, line, method, route)
            for rel, line, method, route, has_model in _iter_route_decorators()
            if not has_model and f"{rel}:{route}" not in EXEMPT
        ]
        assert not missing, (
            "Endpoints without response_model= (add one, or add to EXEMPT with a reason):\n"
            + "\n".join(f"  {rel}:{line} {method} {route}" for rel, line, method, route in missing)
        )

    def test_exempt_entries_still_correspond_to_real_decorators(self):
        """A stale exemption is a hole in the ratchet — fail when one rots."""
        seen = {f"{rel}:{route}" for rel, _line, _m, route, _h in _iter_route_decorators()}
        stale = sorted(set(EXEMPT) - seen)
        assert not stale, f"EXEMPT entries no longer match any decorator: {stale}"

    def test_scanner_actually_finds_routes(self):
        """Guard against the scanner silently matching nothing and passing."""
        assert len(list(_iter_route_decorators())) > 50


# ---------------------------------------------------------------------------
# Field coverage: models must be a superset of every live serializer shape
# ---------------------------------------------------------------------------


def _fields(model: type[BaseModel]) -> set[str]:
    """Field names as they appear on the wire (alias when one is set)."""
    return {info.alias or name for name, info in model.model_fields.items()}


def _to_dict_keys(instance) -> set[str]:
    """Keys emitted by a detached ORM instance's to_dict().

    Detached is the interesting case: `Track.to_dict()` has an except-branch
    that returns a *reduced* key set, and relationship reads go through
    `_safe_collection`/`_safe_scalar`. Either way the keys returned here are
    keys that can reach a client.
    """
    return set(instance.to_dict().keys())


class TestDomainModelFieldCoverage:
    """Union of (to_dict, DEFAULT_*_FIELDS) ⊆ model fields, for each domain type."""

    def test_track_response_covers_both_serializer_paths(self):
        emitted = _to_dict_keys(Track()) | set(DEFAULT_TRACK_FIELDS)
        dropped = emitted - _fields(TrackResponse)
        assert not dropped, (
            f"TrackResponse would silently delete these keys from every track "
            f"payload: {sorted(dropped)}"
        )

    def test_album_response_covers_both_serializer_paths(self):
        emitted = _to_dict_keys(Album()) | set(DEFAULT_ALBUM_FIELDS)
        dropped = emitted - _fields(AlbumResponse)
        assert not dropped, f"AlbumResponse would silently delete: {sorted(dropped)}"

    def test_playlist_response_covers_both_serializer_paths(self):
        emitted = _to_dict_keys(Playlist()) | set(DEFAULT_PLAYLIST_FIELDS)
        dropped = emitted - _fields(PlaylistResponse)
        assert not dropped, f"PlaylistResponse would silently delete: {sorted(dropped)}"

    def test_artist_response_covers_both_serializer_paths(self):
        """artists.py predates #3838 but shares the same two-shape hazard."""
        from routers.artists import ArtistResponse

        emitted = _to_dict_keys(Artist()) | set(DEFAULT_ARTIST_FIELDS)
        dropped = emitted - _fields(ArtistResponse)
        assert not dropped, f"ArtistResponse would silently delete: {sorted(dropped)}"

    def test_no_response_model_declares_a_camelcase_field(self):
        """One entity, one casing on the wire (#4679).

        `AlbumDetailResponse` used to be the sole camelCase response model in
        the backend, so `GET /api/albums` and `GET /api/albums/{id}` emitted
        the same entity in two incompatible shapes against a single declared
        frontend contract. Both endpoints share `AlbumResponse` now; this
        asserts no sibling quietly reintroduces the split.
        """
        import schemas as schemas_module

        offenders = {
            f"{name}.{field}"
            for name, model in vars(schemas_module).items()
            if isinstance(model, type) and issubclass(model, BaseModel)
            and model.__module__ == schemas_module.__name__
            for field in model.model_fields
            if any(char.isupper() for char in field)
        }
        assert not offenders, f"camelCase response fields: {sorted(offenders)}"

    def test_track_response_still_withholds_filepath(self):
        """#3205: the server-side path is server-only and must not become a field."""
        assert "filepath" not in _fields(TrackResponse)


class TestFingerprintVectorCoverage:
    """Both fingerprint emitters agree with the one shared model (#2477)."""

    def _album_router_api_keys(self) -> set[str]:
        """The api-side names from albums.py's `db_to_api` rename table."""
        source = (_BACKEND / "routers" / "albums.py").read_text()
        block = source[source.index("db_to_api"):source.index("median_fingerprint = {}")]
        keys = set(re.findall(r"\(\s*'[a-z_0-9]+'\s*,\s*'([a-z_0-9]+)'\s*\)", block))
        assert len(keys) == 25, f"expected 25 fingerprint dimensions, parsed {len(keys)}"
        return keys

    def _track_router_api_keys(self) -> set[str]:
        """The literal keys the per-track fingerprint endpoint emits."""
        source = (_BACKEND / "routers" / "fingerprint_status.py").read_text()
        block = source[source.index('"fingerprint": {'):]
        block = block[: block.index("},")]
        keys = set(re.findall(r'"([a-z_0-9]+)":\s*fp\.', block))
        assert len(keys) == 25, f"expected 25 fingerprint dimensions, parsed {len(keys)}"
        return keys

    def test_album_median_fingerprint_keys_are_all_declared(self):
        dropped = self._album_router_api_keys() - _fields(FingerprintVectorResponse)
        assert not dropped, f"album fingerprint keys not declared: {sorted(dropped)}"

    def test_track_fingerprint_keys_are_all_declared(self):
        dropped = self._track_router_api_keys() - _fields(FingerprintVectorResponse)
        assert not dropped, f"track fingerprint keys not declared: {sorted(dropped)}"

    def test_both_emitters_agree(self):
        """The two endpoints must not drift apart again — that WAS #2477."""
        assert self._album_router_api_keys() == self._track_router_api_keys()


class TestLibraryStatsCoverage:
    """LibraryStatsResponse covers what StatsRepository actually emits."""

    def test_library_stats_response_covers_repository_output(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from auralis.library.models.core import Base
        from auralis.library.repositories.stats_repository import StatsRepository
        from routers.library import LibraryStatsResponse

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        repo = StatsRepository(sessionmaker(bind=engine))

        emitted = set(repo.get_library_stats().keys())
        dropped = emitted - _fields(LibraryStatsResponse)
        assert not dropped, (
            f"LibraryStatsResponse would silently delete: {sorted(dropped)}"
        )

    def test_the_duplicate_average_aliases_are_all_kept(self):
        """The repository emits average_dr AND avg_dr_rating; both are consumed."""
        from routers.library import LibraryStatsResponse

        fields = _fields(LibraryStatsResponse)
        assert {"average_dr", "avg_dr_rating", "average_lufs", "avg_lufs"} <= fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
