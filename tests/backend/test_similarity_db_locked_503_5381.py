"""A locked database is a retryable 503 on the similarity-family routes, not a 500 (#5381).

_with_similarity_error_handling sent every non-HTTP exception to _internal_error_response, so an
OperationalError from a plain repository read during a concurrent scan came back as an opaque 500
while handle_query_error (used elsewhere) maps it to 503.
"""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.similarity_common import _with_similarity_error_handling  # noqa: E402

pytestmark = pytest.mark.asyncio


def _locked():
    return OperationalError("SELECT 1", {}, Exception("database is locked"))


async def test_operational_error_becomes_a_503_without_the_driver_text():
    @_with_similarity_error_handling("find similar tracks")
    async def route():
        raise _locked()

    with pytest.raises(HTTPException) as caught:
        await route()

    assert caught.value.status_code == 503
    assert "database is locked" not in str(caught.value.detail)
    assert "find similar tracks" in str(caught.value.detail)


async def test_other_failures_stay_a_500_with_a_correlation_ref():
    @_with_similarity_error_handling("find similar tracks")
    async def route():
        raise RuntimeError("boom")

    with pytest.raises(HTTPException) as caught:
        await route()

    assert caught.value.status_code == 500
    assert "ref " in str(caught.value.detail)


async def test_an_http_exception_passes_through_untouched():
    @_with_similarity_error_handling("find similar tracks")
    async def route():
        raise HTTPException(status_code=404, detail="gone")

    with pytest.raises(HTTPException) as caught:
        await route()

    assert caught.value.status_code == 404
