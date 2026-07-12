# Issue #2164 Resolution: WebSocket Streaming Task Orphan Race

**Status**: ✅ **FIXED**
**Date**: 2026-02-14
**Severity**: HIGH
**Files Modified**: 1
**Tests Added**: 1 (4 test cases)

---

## Summary

Fixed a critical race condition where rapid WebSocket play messages would orphan streaming tasks, making pause/stop commands non-functional.

## The Bug

When a user rapidly switched tracks (e.g., `play_enhanced(A)` → `play_enhanced(B)`), the following race condition occurred:

1. Handler for message B cancels task A
2. Handler creates task B and stores it in `_active_streaming_tasks[ws_id]`
3. Task A's `finally` block fires (because it was just cancelled)
4. Task A's `finally` block sees `ws_id` exists in `_active_streaming_tasks`
5. **BUG**: Task A's `finally` block deletes the entry, which is now task B's reference!
6. Task B is orphaned - subsequent pause/stop commands can't find it

### Impact

- **What broke**: Pause/stop commands became non-functional after rapid track switching
- **When**: Any time user switches tracks quickly (common during browsing)
- **Blast radius**: Per-WebSocket connection, affects all streaming until disconnect

---

## The Fix

Added task identity checks to all three streaming coroutines' `finally` blocks:

### Before (Buggy)

```python
async def stream_audio():
    try:
        # ... streaming code ...
    finally:
        # BUG: Unconditionally deletes, even if replaced by new task
        if ws_id in _active_streaming_tasks:
            del _active_streaming_tasks[ws_id]
```

### After (Fixed)

```python
async def stream_audio():
    # Capture task identity at start (fixes #2164)
    my_task = asyncio.current_task()
    try:
        # ... streaming code ...
    finally:
        # Only delete our own reference, not a successor's
        if _active_streaming_tasks.get(ws_id) is my_task:
            del _active_streaming_tasks[ws_id]
```

### Key Insight

The `is` identity check ensures that a cancelled task only deletes its own reference from the dictionary. If a new task has replaced it, the `is` check fails and the new task's reference is preserved.

---

## Changes

### Modified Files

**[auralis-web/backend/routers/system.py](auralis-web/backend/routers/system.py)**

Applied the fix to all three streaming coroutines:

1. **`stream_audio()`** (lines 210-268) - Enhanced playback (`play_enhanced` message)
   - Added `my_task = asyncio.current_task()` at line 212
   - Changed finally block to use identity check at line 267

2. **`stream_normal()`** (lines 289-327) - Normal playback (`play_normal` message)
   - Added `my_task = asyncio.current_task()` at line 294
   - Changed finally block to use identity check at line 326

3. **`stream_from_position()`** (lines 411-456) - Seek playback (`seek` message)
   - Added `my_task = asyncio.current_task()` at line 419
   - Changed finally block to use identity check at line 455

### Added Tests

**[tests/backend/test_websocket_task_orphan_race.py](tests/backend/test_websocket_task_orphan_race.py)** - New file with 4 test cases:

1. **`test_task_identity_check_prevents_orphan`** - Core fix verification
   - Simulates rapid task switching
   - Verifies task2's reference is NOT deleted by task1's finally block

2. **`test_old_pattern_demonstrates_bug`** - Bug demonstration
   - Shows the old pattern would fail
   - Documents the exact behavior we're preventing

3. **`test_triple_rapid_switch_with_fix`** - Stress test
   - Rapid switching through 3 tasks
   - Verifies robustness under extreme conditions

4. **`test_pause_cancels_correct_task`** - Acceptance criteria
   - Tests: play_enhanced(A) → play_enhanced(B) → pause
   - Verifies pause correctly cancels task B

All tests pass ✅

---

## Verification

```bash
# Run the new tests
python -m pytest tests/backend/test_websocket_task_orphan_race.py -vv

# Result: All 4 tests pass
✅ test_task_identity_check_prevents_orphan
✅ test_old_pattern_demonstrates_bug
✅ test_triple_rapid_switch_with_fix
✅ test_pause_cancels_correct_task
```

---

## Acceptance Criteria (from issue #2164)

- [x] Finally block only deletes its own task reference
- [x] Rapid `play_enhanced` → `play_enhanced` → `pause` correctly pauses the second stream
- [x] Test: send two `play_enhanced` messages within 100ms, verify second stream is controllable
- [x] Test: rapid play messages don't orphan tasks

---

## Related Issues

- **#2076** - WebSocket stream loop TOCTOU race (different: interleaved reads)
- **#2106** - Backend pause destroys streaming task (complementary: pause behavior)

---

## Notes

This is a **classic async cleanup race condition**. The pattern used here (task identity check in finally block) is the standard Python asyncio solution for this class of bugs.

The fix is minimal, surgical, and has zero performance impact. It simply adds one identity comparison in the cleanup path.
