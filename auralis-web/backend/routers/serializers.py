"""
Object serialization utilities for consistent API responses.

Converts database rows to dictionaries for JSON serialization. A row's own
``to_dict()`` is the single source of the response shape -- the declared
Pydantic models in ``schemas/library.py`` and ``routers/*_models.py`` are
pinned against it by ``tests/backend/test_response_model_coverage.py``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def serialize_object(obj: Any) -> dict[str, Any]:
    """
    Serialize a single database row with its own ``to_dict()``.

    The model's ``to_dict()`` already degrades for a detached instance (it
    reads relationships through ``_safe_collection()`` / ``_safe_scalar()``),
    so an exception from it is a real defect: it is logged and re-raised
    rather than masked by a second, hand-maintained response shape (#5803).

    Args:
        obj: Row to serialize, or None

    Returns:
        ``obj.to_dict()``, or ``{}`` for None

    Raises:
        TypeError: ``obj`` has no ``to_dict()`` returning a dict
    """
    if obj is None:
        return {}

    try:
        result = obj.to_dict()
    except Exception:
        logger.exception("to_dict() failed on %s", type(obj).__name__)
        raise
    if not isinstance(result, dict):
        raise TypeError(
            f"{type(obj).__name__}.to_dict() returned {type(result).__name__}, not dict"
        )
    return result


def serialize_objects(objects: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of rows with :func:`serialize_object`."""
    return [serialize_object(obj) for obj in objects]
