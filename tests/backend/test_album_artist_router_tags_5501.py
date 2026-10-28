"""albums and artists routers carry an OpenAPI tag (#5501).

They were the only two registered router factories built with a bare
`APIRouter(dependencies=...)`, so their endpoints landed in an untagged group in
Swagger UI instead of the per-domain grouping every sibling has. They sit with
tracks and the rest of the library.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.albums import create_albums_router  # noqa: E402
from routers.artists import create_artists_router  # noqa: E402


@pytest.mark.parametrize("factory", [create_albums_router, create_artists_router])
def test_every_route_is_tagged_library(factory):
    router = factory(lambda: MagicMock())

    assert router.routes, "the factory registered no routes"
    for route in router.routes:
        assert list(getattr(route, "tags", [])) == ["library"], route.path
