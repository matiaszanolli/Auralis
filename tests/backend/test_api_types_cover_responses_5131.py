"""The frontend wire types name every field the backend's list responses carry (#5131).

`TrackApiResponse`, `AlbumApiResponse` and `ArtistApiResponse` modelled only a subset of what the
endpoints' `response_model`s serialize, so a feature needing a DR badge or a play count hit a
spurious "property does not exist" error and reached for a cast. This pins both directions:
every backend field is typed (add the field to `api/transformers/types.ts`), and the types name
nothing the backend does not send (unless listed below with its reason).
"""

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from routers.artists_models import ArtistResponse  # noqa: E402
from schemas.library import AlbumResponse, TrackResponse  # noqa: E402

_TYPES = (_REPO_ROOT / "auralis-web" / "frontend" / "src" / "api" / "transformers" / "types.ts").read_text()

# Typed on the frontend but deliberately absent from the response model.
_FRONTEND_ONLY = {
    "TrackApiResponse": {"filepath"},  # optional: no transport populates it (#3205)
}


def _interface_keys(name: str) -> set[str]:
    body = re.search(rf"export interface {name} \{{(.*?)\n\}}", _TYPES, re.S)
    assert body, f"{name} not found in types.ts"
    return set(re.findall(r"^  ([a-z_]+)\??:", body.group(1), re.M))


@pytest.mark.parametrize(
    "interface, model",
    [
        ("TrackApiResponse", TrackResponse),
        ("AlbumApiResponse", AlbumResponse),
        ("ArtistApiResponse", ArtistResponse),
    ],
)
def test_every_backend_field_is_typed_and_nothing_extra_is(interface, model):
    typed = _interface_keys(interface)
    sent = set(model.model_fields)

    assert sent - typed == set(), f"{interface} omits fields the backend sends: {sorted(sent - typed)}"
    assert typed - sent == _FRONTEND_ONLY.get(interface, set()), (
        f"{interface} names fields the backend never sends: {sorted(typed - sent)}"
    )
