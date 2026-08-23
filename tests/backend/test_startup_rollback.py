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
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import (
    _ROLLBACK_COMPONENTS_TO_NULL,
    _ROLLBACK_SERVICES_TO_STOP,
    _rollback_partial_startup,
    _shutdown_components,
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


class TestRollbackReallyTearsDownOwnedResources:
    """#4764: library_manager, audio_player, and player_state_manager used to
    be bare-nulled on rollback with no teardown call, unlike every background
    *service* above. Once nulled, _shutdown_components' `if globals_dict.get(
    ...)` guard can never fire for them again — the SQLite engine, the audio
    device, and (if playback had started) the 1 Hz broadcast task were then
    unreachable for the rest of the process lifetime.
    """

    async def test_library_manager_is_shut_down_before_being_nulled(self):
        library_manager = Mock()
        globals_dict = {"library_manager": library_manager}

        await _rollback_partial_startup(globals_dict)

        library_manager.shutdown.assert_called_once()
        assert globals_dict["library_manager"] is None

    async def test_audio_player_is_stopped_and_cleaned_up_before_being_nulled(self):
        audio_player = Mock()
        globals_dict = {"audio_player": audio_player}

        await _rollback_partial_startup(globals_dict)

        audio_player.stop.assert_called_once()
        audio_player.cleanup.assert_called_once()
        assert globals_dict["audio_player"] is None

    async def test_player_state_manager_is_shut_down_before_being_nulled(self):
        player_state_manager = Mock()
        player_state_manager.shutdown = AsyncMock()
        globals_dict = {"player_state_manager": player_state_manager}

        await _rollback_partial_startup(globals_dict)

        player_state_manager.shutdown.assert_awaited_once()
        assert globals_dict["player_state_manager"] is None

    async def test_all_three_teardowns_happen_together_in_one_rollback(self):
        """Integration-style check per this issue's own test plan: simulate a
        startup failure after LibraryDatabase() and AudioPlayer() both
        succeeded (e.g. PlayerStateManager construction raising next), and
        assert every owned resource's teardown method fired exactly once."""
        library_manager = Mock()
        audio_player = Mock()
        player_state_manager = Mock()
        player_state_manager.shutdown = AsyncMock()
        globals_dict = {
            "library_manager": library_manager,
            "audio_player": audio_player,
            "player_state_manager": player_state_manager,
        }

        await _rollback_partial_startup(globals_dict)

        library_manager.shutdown.assert_called_once()
        audio_player.stop.assert_called_once()
        audio_player.cleanup.assert_called_once()
        player_state_manager.shutdown.assert_awaited_once()
        for key in globals_dict:
            assert globals_dict[key] is None

    async def test_a_failing_teardown_does_not_abort_the_rest_of_rollback(self):
        """Best-effort, like every other rollback step: one resource's
        teardown raising must not prevent the others from being torn down
        and nulled."""
        library_manager = Mock()
        library_manager.shutdown.side_effect = RuntimeError("WAL checkpoint failed")
        audio_player = Mock()
        globals_dict = {"library_manager": library_manager, "audio_player": audio_player}

        await _rollback_partial_startup(globals_dict)  # must not raise

        audio_player.stop.assert_called_once()
        assert globals_dict["library_manager"] is None
        assert globals_dict["audio_player"] is None

    async def test_shutdown_components_and_rollback_use_the_same_teardown(self):
        """CONSISTENCY: the two paths share the teardown helpers, so a future
        change to how library_manager/audio_player/player_state_manager are
        torn down cannot silently diverge between rollback and normal
        shutdown again. Patches the module-level imports _shutdown_components
        unconditionally reaches for (same pattern as
        test_shutdown_step_isolation.py's _quiet_externals()) so this stays a
        unit test of the three teardown calls, not an integration test of the
        whole shutdown sequence."""
        library_manager = Mock()
        audio_player = Mock()
        player_state_manager = Mock(shutdown=AsyncMock())
        globals_dict = {
            "library_manager": library_manager,
            "audio_player": audio_player,
            "player_state_manager": player_state_manager,
        }

        with (
            patch("core.processor_factory.get_processor_factory", Mock()),
            patch("services.artwork_downloader.close_artwork_downloader", AsyncMock()),
            patch("analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded", AsyncMock()),
        ):
            await _shutdown_components(globals_dict)

        library_manager.shutdown.assert_called_once()
        audio_player.stop.assert_called_once()
        audio_player.cleanup.assert_called_once()
        player_state_manager.shutdown.assert_awaited_once()
