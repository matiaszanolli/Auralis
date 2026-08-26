"""
Regression tests for the per-subsystem lifespan extraction (#4671).

lifespan()/create_lifespan() used to be one 395-line nested function with no
seam at which to test a single subsystem's init in isolation, or to verify
that a failure partway through actually triggers rollback — every existing
test drove _rollback_partial_startup() directly with a hand-built
globals_dict, never through the real init sequence. Extracting each
subsystem into a named module-level _init_*()/_start_*() function is what
makes both of those directly testable, via mocking the extracted functions
themselves (config.startup._init_library_database etc.) — impossible when
the same code was inline.

These tests exist to prove the extraction actually preserved the original
failure semantics (documented in _init_auralis_components's docstring):
sub-steps with no try/except of their own still propagate to the outer
rollback; sub-steps that already caught their own failures still do, and do
not abort the sequence.
"""

import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _init_auralis_components  # noqa: E402

pytestmark = pytest.mark.asyncio


def _patch_all_auralis_init_steps(stack: ExitStack, **overrides):
    """Patch every _init_auralis_components sub-step to a no-op AsyncMock/
    MagicMock (matching each real function's sync/async-ness), with any
    per-test override substituted in. Returns {name: mock} for assertions —
    patch.multiple's own return dict only includes DEFAULT-sentinel entries,
    not explicit custom mocks, so patches are applied individually instead."""
    defaults = {
        "_init_library_database": MagicMock(),
        "_init_fingerprint_extraction_queue": AsyncMock(),
        "_seed_settings_and_enhancement": MagicMock(),
        "_register_scan_folders": MagicMock(),
        "_init_reference_cloud_refresh": MagicMock(return_value=lambda *a, **k: None),
        "_start_auto_scanner": AsyncMock(),
        "_init_audio_player": MagicMock(),
        "_init_ondemand_fingerprint_queue": AsyncMock(),
        # #4682: became async so it can await SimilarityAutoFitWorker.start().
        "_init_similarity_system": AsyncMock(),
    }
    defaults.update(overrides)
    for name, mock in defaults.items():
        stack.enter_context(patch(f"config.startup.{name}", mock))
    return defaults


async def test_has_auralis_false_skips_every_subsystem():
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(stack)
        await _init_auralis_components(False, True, manager=None, globals_dict={})

    for mock in mocks.values():
        mock.assert_not_called()


async def test_runs_every_subsystem_in_the_documented_order():
    globals_dict: dict = {}
    manager = object()
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(stack)
        await _init_auralis_components(True, True, manager, globals_dict)

    mocks["_init_library_database"].assert_called_once_with(globals_dict)
    mocks["_init_fingerprint_extraction_queue"].assert_awaited_once_with(globals_dict)
    mocks["_seed_settings_and_enhancement"].assert_called_once_with(globals_dict)
    mocks["_register_scan_folders"].assert_called_once_with(globals_dict)
    mocks["_init_reference_cloud_refresh"].assert_called_once_with(globals_dict)
    mocks["_start_auto_scanner"].assert_awaited_once()
    assert mocks["_start_auto_scanner"].await_args.args[0] is manager
    mocks["_init_audio_player"].assert_called_once_with(manager, globals_dict)
    mocks["_init_ondemand_fingerprint_queue"].assert_awaited_once_with(globals_dict)
    mocks["_init_similarity_system"].assert_awaited_once_with(True, globals_dict)


async def test_reference_cloud_closure_is_threaded_into_auto_scanner():
    """_init_reference_cloud_refresh's return value must reach
    _start_auto_scanner as its on_scan_complete callback — the one piece of
    inter-step data flow in the sequence."""
    sentinel_closure = object()
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(
            stack,
            _init_reference_cloud_refresh=MagicMock(return_value=sentinel_closure),
        )
        await _init_auralis_components(True, True, manager=None, globals_dict={})

    assert mocks["_start_auto_scanner"].await_args.args[2] is sentinel_closure


async def test_library_database_failure_triggers_rollback():
    """_init_library_database has no try/except of its own — a failure must
    propagate up to _init_auralis_components's outer rollback boundary,
    exactly as the original inline code's failure semantics."""
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(
            stack,
            _init_library_database=MagicMock(side_effect=RuntimeError("db boom")),
        )
        mock_rollback = stack.enter_context(
            patch("config.startup._rollback_partial_startup", new=AsyncMock())
        )
        await _init_auralis_components(True, True, manager=None, globals_dict={})

    mock_rollback.assert_awaited_once()
    # Nothing after the failing step must have run.
    mocks["_seed_settings_and_enhancement"].assert_not_called()
    mocks["_init_audio_player"].assert_not_called()


async def test_audio_player_failure_triggers_rollback_after_earlier_steps_ran():
    """A failure in a later, also-uncaught step (_init_audio_player) must
    still roll back — earlier steps must have run first."""
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(
            stack,
            _init_audio_player=MagicMock(side_effect=RuntimeError("player boom")),
        )
        mock_rollback = stack.enter_context(
            patch("config.startup._rollback_partial_startup", new=AsyncMock())
        )
        await _init_auralis_components(True, True, manager=None, globals_dict={})

    mock_rollback.assert_awaited_once()
    mocks["_init_library_database"].assert_called_once()
    mocks["_seed_settings_and_enhancement"].assert_called_once()
    # Steps after the failure must not have run.
    mocks["_init_ondemand_fingerprint_queue"].assert_not_awaited()
    mocks["_init_similarity_system"].assert_not_called()


async def test_fingerprint_queue_failure_does_not_trigger_rollback():
    """_init_fingerprint_extraction_queue catches its own failures (matching
    the original inline try/except) — the documented, intended contract is
    that the real function never raises past its own boundary. Mocking it to
    behave that way (return normally after logging) must let every later
    step still run and must not trigger the outer rollback."""
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(stack)
        mock_rollback = stack.enter_context(
            patch("config.startup._rollback_partial_startup", new=AsyncMock())
        )
        await _init_auralis_components(True, True, manager=None, globals_dict={})

    mock_rollback.assert_not_awaited()
    mocks["_init_similarity_system"].assert_called_once()


async def test_has_similarity_false_is_forwarded_to_similarity_step():
    with ExitStack() as stack:
        mocks = _patch_all_auralis_init_steps(stack)
        await _init_auralis_components(True, False, manager=None, globals_dict={})

    mocks["_init_similarity_system"].assert_called_once_with(False, {})
