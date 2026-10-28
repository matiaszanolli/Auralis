"""POST /graph/build does not send a caller who already fitted in a circle (#5890)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import HTTPException

from routers.similarity_graph import build_similarity_graph


@pytest.mark.asyncio
async def test_missing_builder_is_a_503_that_names_the_delay_not_just_fit_first():
    with pytest.raises(HTTPException) as excinfo:
        await build_similarity_graph(k=10, clear_existing=True, graph_builder=None)

    assert excinfo.value.status_code == 503
    assert "within a few minutes" in excinfo.value.detail
