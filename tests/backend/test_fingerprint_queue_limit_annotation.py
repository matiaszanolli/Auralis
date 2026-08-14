# -*- coding: utf-8 -*-

"""
Regression: enqueue-all's `limit` is honestly typed as optional (#4701)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`enqueue_all_missing_fingerprints` annotated `limit: int` while defaulting it
to `None`. Pydantic does not validate defaults, so runtime behaviour was
correct ("all missing tracks"), but the annotation was a lie: mypy could not
flag a future `limit > 0` added to the handler, and the generated OpenAPI
schema advertised a non-nullable integer whose documented default is `null`.

These tests pin the annotation and the surviving `ge`/`le` bounds.

:license: GPLv3
"""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture(scope="module")
def enqueue_all_handler():
    """The registered enqueue-all endpoint function."""
    from routers.fingerprint_queue import create_fingerprint_queue_router

    router = create_fingerprint_queue_router(lambda: None)

    for route in router.routes:
        if getattr(route, "path", None) == "/api/similarity/fingerprint-queue/enqueue-all":
            return route.endpoint

    pytest.fail("enqueue-all route not registered")


def test_limit_is_annotated_optional(enqueue_all_handler):
    """#4701: `limit: int` with a `None` default was an untrue annotation."""
    annotation = inspect.signature(enqueue_all_handler).parameters["limit"].annotation

    assert annotation == (int | None), (
        f"limit must be int | None to match its None default, got {annotation!r}"
    )


def test_limit_default_is_none(enqueue_all_handler):
    """None is the documented 'enqueue everything missing' sentinel."""
    from fastapi.params import Query

    default = inspect.signature(enqueue_all_handler).parameters["limit"].default

    assert isinstance(default, Query)
    assert default.default is None


def test_limit_bounds_are_intact(enqueue_all_handler):
    """The ge/le bounds must still reject 0 and 20001 (422) when supplied."""
    default = inspect.signature(enqueue_all_handler).parameters["limit"].default
    constraints = {type(m).__name__: m for m in default.metadata}

    assert constraints["Ge"].ge == 1
    assert constraints["Le"].le == 10000


def test_repository_treats_none_limit_as_all():
    """The None sentinel is genuinely honoured downstream, not an untyped default."""
    from auralis.library.repositories.fingerprint_repository import (
        FingerprintRepository,
    )

    limit_param = inspect.signature(
        FingerprintRepository.get_missing_fingerprints
    ).parameters["limit"]

    assert limit_param.annotation == (int | None)
    assert limit_param.default is None
