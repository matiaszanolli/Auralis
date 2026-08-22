#!/usr/bin/env python3

"""
Fingerprint-Repository Registry Resolution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Resolves the process-wide ``FingerprintRepository`` for ChunkedAudioProcessor's
Tier-1 (DB) fingerprint lookup, plus the once-per-process warning latch that
reports a misresolved component registry. Extracted from chunked_processor.py
(#4245) — this is registry plumbing, not a chunk-streaming concern.

``_default_get_fingerprints_repository`` / ``_reset_registry_miss_warning`` are
re-exported from ``core.chunked_processor`` (its historical home) so existing
imports — ``core/mastering_target_service.py`` and several
``tests/backend/test_*`` files — keep working unchanged.

The module logger is deliberately named ``core.chunked_processor`` rather than
``__name__`` (see :mod:`core.chunked_processor` module docstring note): several
regression tests assert on ``caplog.at_level(..., logger="core.chunked_processor")``
for exactly these warnings (#4714 / #4578), and log-record attribution follows
whichever logger emitted the record, not whichever module the code physically
lives in.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("core.chunked_processor")


# Latched so a misresolved registry is reported once rather than on every
# per-track Tier-1 lookup (#4714). Reset by tests via _reset_registry_miss_warning().
_registry_miss_warned = False


def _warn_once_on_registry_miss(message: str) -> None:
    """Log a registry misresolution at WARNING, exactly once per process."""
    global _registry_miss_warned
    if _registry_miss_warned:
        return
    _registry_miss_warned = True
    logger.warning(f"⚠️  {message}")


def _reset_registry_miss_warning() -> None:
    """Clear the latch. Test-only — production never un-misresolves."""
    global _registry_miss_warned
    _registry_miss_warned = False


def _default_get_fingerprints_repository() -> Any | None:
    """Return the global FingerprintRepository for Tier-1 (DB) fingerprint lookup.

    ChunkedAudioProcessor is constructed from many call sites (streaming controller,
    recommendation service, cache warmer, enhancement route). Rather than thread the
    repository factory through every one, the DB-tier accessor reads the
    ``repository_factory`` from the process-wide component registry that startup
    populates. Returns ``None`` (Tier-1 silently skipped, as before) when the
    registry isn't set up yet — e.g. in unit tests — so this never raises
    (#3836 / BE-PE-3).

    #4578: this previously imported ``config.globals.globals_dict``, a *second*
    dict that startup never touched and that did not even declare the
    ``repository_factory`` key, so it returned ``None`` unconditionally in
    production and every construction fell through to the slow fingerprint
    tiers. It now goes through ``get_component_registry()``, which resolves the
    single registered dict at call time.

    #4714: the "return None" paths below are not equivalent, and treating them
    as one is what let #3836 ship dead for months. Two are legitimate (no
    registry at all in a bare unit test; startup has not populated the factory
    yet), but a registry that does not even *declare* the key — the exact #4578
    shape — can never be main.py's dict and means a reader has resolved the
    wrong object. That case, and a genuine exception, log loudly instead of
    degrading in silence. Still never raises: Tier-1 is an optimisation, and
    processor construction must not depend on it.
    """
    try:
        from config.globals import get_component_registry
        registry = get_component_registry()
        if registry is None:
            # Bare unit-test context — main.py was never imported.
            logger.debug("No component registry set; skipping Tier-1 fingerprint lookup")
            return None
        if "repository_factory" not in registry:
            _warn_once_on_registry_miss(
                "the registered component registry does not declare "
                "'repository_factory' — a reader has resolved a registry that is "
                "not main.py's (#4578/#4714); Tier-1 DB fingerprint lookup is dead "
                "and every mastering target will fall through to the slow tiers"
            )
            return None
        factory = registry["repository_factory"]
        if factory is None:
            # Pre-startup window: the key exists, _init_library_database has
            # not run yet. Legitimate and transient.
            logger.debug("repository_factory not populated yet; skipping Tier-1 lookup")
            return None
        return factory.fingerprints
    except Exception as e:  # defensive: never break processor init
        _warn_once_on_registry_miss(f"Tier-1 fingerprint repository lookup failed: {e}")
        return None
