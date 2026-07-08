"""
Regression tests for the partial-startup rollback (#3812 / BE-MW-3, regression of #3540 / BE-NEW-82).

CONTEXT: If a startup step fails (e.g. EnhancedAudioPlayer init) after
fingerprint_queue.start() / auto_scanner.start() already spawned background
tasks, a rollback that only nulls globals_dict entries WITHOUT awaiting
.stop() on those already-running services leaves them alive — still calling
into a library_manager that's about to be rolled back to None, crashing
inside the background task with AttributeError on every subsequent tick.

_rollback_partial_startup() must await .stop() on each already-started
service (tolerating a failing .stop() itself) before nulling it, then null
the remaining components that never own an async task of their own.

:license: GPLv3
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import (
    _ROLLBACK_COMPONENTS_TO_NULL,
    _ROLLBACK_SERVICES_TO_STOP,
    _rollback_partial_startup,
)


def _running_service() -> Mock:
    svc = Mock()
    svc.stop = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_stops_all_already_running_services_before_nulling():
    """Every service that had actually started must have .stop() awaited,
    each with the kwargs its own shutdown call needs."""
    scanner, ondemand, fpq = _running_service(), _running_service(), _running_service()
    globals_dict = {
        'auto_scanner': scanner,
        'ondemand_fingerprint_queue': ondemand,
        'fingerprint_queue': fpq,
    }

    await _rollback_partial_startup(globals_dict)

    scanner.stop.assert_awaited_once_with()
    ondemand.stop.assert_awaited_once_with()
    fpq.stop.assert_awaited_once_with(timeout=30.0)


@pytest.mark.asyncio
async def test_nulls_services_after_stopping_them():
    """A stopped service must be removed from globals_dict, not left dangling
    (a stale reference would still be truthy for any router that checks it)."""
    globals_dict = {
        'auto_scanner': _running_service(),
        'ondemand_fingerprint_queue': _running_service(),
        'fingerprint_queue': _running_service(),
    }

    await _rollback_partial_startup(globals_dict)

    for key in ('auto_scanner', 'ondemand_fingerprint_queue', 'fingerprint_queue'):
        assert globals_dict[key] is None, f"{key} must be nulled after rollback"


@pytest.mark.asyncio
async def test_nulls_simple_components():
    """Components that never own a background task are simply nulled."""
    globals_dict = {name: Mock() for name in _ROLLBACK_COMPONENTS_TO_NULL}

    await _rollback_partial_startup(globals_dict)

    for name in _ROLLBACK_COMPONENTS_TO_NULL:
        assert globals_dict[name] is None


@pytest.mark.asyncio
async def test_absent_services_are_skipped_without_error():
    """A service that was never started (key absent, or None) must not raise —
    rollback can be triggered by a failure at ANY point in startup, including
    before some services were even created."""
    globals_dict: dict = {}  # nothing started yet

    await _rollback_partial_startup(globals_dict)  # must not raise

    for key, _ in _ROLLBACK_SERVICES_TO_STOP:
        assert globals_dict.get(key) is None


@pytest.mark.asyncio
async def test_a_failing_stop_does_not_abort_the_rest_of_rollback():
    """One service's .stop() raising must not prevent the others from being
    stopped and nulled, and must not prevent the plain-null components from
    being cleared either — a single misbehaving service can't leave the rest
    of the app in the half-broken 'truthy but rolled-back' state this issue
    describes."""
    ok_scanner = _running_service()
    broken_ondemand = Mock()
    broken_ondemand.stop = AsyncMock(side_effect=RuntimeError("stop failed"))
    ok_fpq = _running_service()

    globals_dict = {
        'auto_scanner': ok_scanner,
        'ondemand_fingerprint_queue': broken_ondemand,
        'fingerprint_queue': ok_fpq,
        'library_manager': Mock(),
    }

    await _rollback_partial_startup(globals_dict)  # must not raise

    ok_scanner.stop.assert_awaited_once()
    broken_ondemand.stop.assert_awaited_once()
    ok_fpq.stop.assert_awaited_once()
    assert globals_dict['auto_scanner'] is None
    assert globals_dict['ondemand_fingerprint_queue'] is None, (
        "must still be nulled even though its own .stop() raised"
    )
    assert globals_dict['fingerprint_queue'] is None
    assert globals_dict['library_manager'] is None


@pytest.mark.asyncio
async def test_dead_fingerprint_extractor_and_storage_entries_removed():
    """Regression guard for the dead-code half of #3812: fingerprint_extractor
    and fingerprint_storage were never set anywhere in startup.py, so nulling
    them in the rollback list was a no-op masquerading as real cleanup. They
    must not reappear in the rollback component list."""
    assert 'fingerprint_extractor' not in _ROLLBACK_COMPONENTS_TO_NULL
    assert 'fingerprint_storage' not in _ROLLBACK_COMPONENTS_TO_NULL


@pytest.mark.asyncio
async def test_stop_kwargs_match_each_services_expected_shutdown_call():
    """fingerprint_queue needs a timeout (its worker pool can take a while to
    drain); the others don't. Verify the exact kwargs shape rollback uses."""
    services = dict(_ROLLBACK_SERVICES_TO_STOP)
    assert services['auto_scanner'] == {}
    assert services['ondemand_fingerprint_queue'] == {}
    assert services['fingerprint_queue'] == {'timeout': 30.0}
