"""
Model Helpers
~~~~~~~~~~~~~

Shared helpers used by the ORM `to_dict()` implementations across the
`auralis.library.models` package (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _safe_collection(instance: Any, attr: str) -> list[Any]:
    """
    Read a relationship collection, degrading to `[]` instead of raising.

    Every `to_dict()` in this package runs on instances the repositories have
    `expunge()`d from their session, so a relationship that was not
    eager-loaded raises `DetachedInstanceError` on first access. The
    repositories' `selectinload()` options are the *primary* guarantee that
    these values are correct; this helper is the backstop that turns a missed
    eager-load into a degraded field rather than an unhandled 500 far from
    its cause (#4500, #4641).

    A miss is logged at WARNING so it is diagnosable — a silently-empty
    collection is exactly how #4500 hid for as long as it did. Callers that
    need to distinguish "empty" from "unavailable" must not rely on the
    returned length alone.
    """
    try:
        return list(getattr(instance, attr))
    except Exception:
        logger.warning(
            "%s.%s could not be loaded (detached instance?); "
            "reporting it as empty. The owning repository is missing a "
            "selectinload(%s.%s).",
            type(instance).__name__, attr, type(instance).__name__, attr,
        )
        return []


def _safe_scalar(instance: Any, attr: str) -> Any | None:
    """
    Read a scalar (many-to-one) relationship, degrading to `None`.

    Same rationale as :func:`_safe_collection` — see #4641.
    """
    try:
        return getattr(instance, attr)
    except Exception:
        logger.warning(
            "%s.%s could not be loaded (detached instance?); reporting None. "
            "The owning repository is missing a joinedload/selectinload(%s.%s).",
            type(instance).__name__, attr, type(instance).__name__, attr,
        )
        return None
