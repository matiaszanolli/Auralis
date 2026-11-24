# Subsystem: Player Engine & Backend State

[`auralis/player/`](../../auralis/player/) is the Python playback engine: a track buffer, a
playback state machine, a queue, a gapless next-track prebuffer and a small real-time DSP
chain, wrapped in one facade (`AudioPlayer`). The FastAPI backend owns an instance of it and
mirrors its state into a separate, async `PlayerStateManager` that the renderer actually
reads.

> **Scope.** The engine package, the backend services that drive it, and the two state models
> (engine vs. wire). The DSP that masters audio for playback is documented in
> [dsp-engine.md](dsp-engine.md); the REST/WebSocket surface in [backend-api.md](backend-api.md);
> library rows and repositories in [library.md](library.md).

---

## 1. What the Python player does, and what it does not

The audio that reaches the speakers does **not** come out of `AudioPlayer`. In the shipped app
the renderer plays PCM that the backend streams over the `/ws` WebSocket (chunked, mastered by
`ChunkedAudioProcessor`; see [backend-api.md §4–5](backend-api.md#4-websocket-protocol-ws)),
and volume is a client-side Web Audio gain (the backend only broadcasts the value). Nothing
outside `auralis/player/` calls `AudioPlayer.get_audio_chunk()`, so the engine's pull loop,
its `RealtimeProcessor` and its auto-advance thread never run in the app.

What the engine *is* used for by the backend:

| Role | Engine piece |
|------|--------------|
| **Authoritative queue** (order, contents, current index, shuffle, repeat) | `QueueController` / `QueueManager` |
| **Track navigation** (`next` / `previous`, gapless commit) | `AudioPlayer.next_track` / `previous_track`, `GaplessPlaybackEngine` |
| **Load / transport calls** made when a queue is set or a track is loaded | `load_file`, `load_track_from_library`, `play`, `pause`, `stop`, `seek` |
| **Standalone use** (embedding, tests, the `get_audio_chunk` pull loop) | the whole package |

Loading is a real decode: `load_file` decodes the whole file into `AudioFileManager.audio_data`
and the gapless engine decodes the *next* queue entry into a prebuffer, even though the renderer
plays a separately streamed copy.

The wire-facing player state is a second model, `PlayerState`, owned by the backend
(§10). The two are bridged by services, not shared.

---

## 2. Component map

`AudioPlayer` ([`enhanced_audio_player.py`](../../auralis/player/enhanced_audio_player.py)) is a
facade. It composes five component objects and mixes in four method groups.

| Component | Class | File | Owns |
|-----------|-------|------|------|
| Transport state machine | `PlaybackController` | [`playback_controller.py`](../../auralis/player/playback_controller.py) | `state`, `position` (samples), state-change callbacks |
| Audio buffer | `AudioFileManager` | [`audio_file_manager.py`](../../auralis/player/audio_file_manager.py) | decoded `audio_data`, `sample_rate`, `current_file`, reference audio, `_audio_lock` |
| Queue | `QueueController` | [`queue_controller.py`](../../auralis/player/queue_controller.py) | a `QueueManager`, library lookups, change listener |
| Next-track prebuffer | `GaplessPlaybackEngine` | [`gapless_playback_engine.py`](../../auralis/player/gapless_playback_engine.py) | prebuffered audio, prebuffer thread, `update_lock` |
| Library / callbacks / stats | `IntegrationManager` | [`integration_manager.py`](../../auralis/player/integration_manager.py) | current-track snapshot, external callbacks, session stats |
| Real-time DSP | `RealtimeProcessor` | [`realtime/processor.py`](../../auralis/player/realtime/processor.py) | level matcher, auto-master, safety ceiling |

Mixins on `AudioPlayer` (each its own file): `PlayerFileLoadingMixin` (`load_file`,
`load_reference`, `load_track_from_library`), `PlayerQueueNavigationMixin` (`next_track`,
`previous_track`, `add_to_queue`, `load_playlist`, `clear_queue`), `PlayerStreamingMixin`
(`get_audio_chunk`, the auto-advance thread), `PlayerCallbacksMixin` (`set_effect_enabled`,
`get_queue_info`, `set_shuffle`, `set_repeat`) and `PlayerFingerprintLoaderMixin`
(`_schedule_fingerprint_load`). Paths are `auralis/player/player_*_mixin.py` and
`auralis/player/fingerprint_loader_mixin.py`.

`AudioPlayer` itself keeps `__init__`, the transport methods (`play`, `pause`, `stop`, `seek`,
the `position` property and its setter) and `cleanup`. The mixins are mixed in, not composed as
helper objects, so state such as `_track_generation` and `_audio_lock` stays directly on the
player instance and existing tests that patch it by name keep working.

`PlayerConfig` ([`config.py`](../../auralis/player/config.py)) holds the knobs. The backend
builds the player with bare `PlayerConfig()` (`auralis-web/backend/config/startup/components.py`),
so the shipped values are the constructor defaults: level matching on, **auto-mastering off**,
`buffer_size=1024`, `realtime_safety_peak=0.95`.

### Mixin host-hook convention

A mixin that calls a method its host (or a sibling mixin) provides declares it as a **bare
class-level annotation** with a "Provided by X" comment, never as a
`raise NotImplementedError` stub:

```python
class PlayerQueueNavigationMixin:
    # Provided by PlayerFileLoadingMixin.
    load_file: Callable[[str], bool]
```

A runtime stub would sit in the MRO ahead of the sibling that really implements the method and
shadow it. The same rule holds for state the host creates in `__init__`
(`file_manager: AudioFileManager`, `_stop_requested: threading.Event`, ...): annotate, do not
assign. The pattern repeats in the queue (`QueueManager` hosts `QueueNavigationMixin`,
`QueueSelectionMixin`, `ShuffleMixin`), `IntegrationManager`, `PrebufferMixin` and
`PlaybackNotifierMixin`.

---

## 3. The playback state model (`PlaybackController`)

`PlaybackState` is a `str` enum (`stopped`, `playing`, `paused`, `loading`, `error`) so the
backend can serialise it directly; `auralis-web/backend/player_state.py` re-exports it so engine
and wire share one enum. `LOADING` exists for the backend's `PlayerStateManager.set_track`; the
engine controller never enters it. `load_and_stop()` goes straight to `STOPPED` so observers
never see a half-loaded state.

Transitions, all under one `threading.RLock` (`PlaybackController._lock`): `play()` moves
`STOPPED` / `PAUSED` to `PLAYING` and is rejected in `ERROR` or when already playing; `pause()`
moves `PLAYING` to `PAUSED`; `stop()` moves `PLAYING` / `PAUSED` to `STOPPED` and resets the
position; `seek(samples, max_samples)` clamps to `[0, max_samples]`; `load_and_stop()` resets the
position and goes to `STOPPED` (the only way out of `ERROR`, with `set_error()` the way in);
`read_and_advance_position()` and `read_and_advance_if_playing()` are the chunk reader's atomic
read-then-advance, with the stored position clamped to `max_samples`.

Each mutator snapshots the new state **inside** the lock and fires callbacks **after** releasing
it. The snapshot carries `state`, `action` and a monotonic `seq` assigned in transition order,
so a listener that mirrors state keeps the highest `seq` seen and drops older events that were
dispatched late. `get_state_snapshot()` returns `(state, is_playing)` in one acquisition.

### Deferred notifications and the lock-held guard

The state callback registered by `IntegrationManager` takes `_position_lock` and then re-enters
`_audio_lock`, the opposite order from `get_playback_info()`. A mutator that fired its callbacks
while the caller held `_audio_lock` would be an AB-BA deadlock. Two pieces prevent it
([`playback_notifier.py`](../../auralis/player/playback_notifier.py),
[`lock_held_hooks.py`](../../auralis/player/lock_held_hooks.py)):

- `PlaybackController.defer_notifications()` is a thread-local, re-entrant context manager that
  queues notifications and flushes them, in order, when the **outermost** scope exits. Callers
  open it as the *outer* context: `with playback.defer_notifications(), file_manager._audio_lock:`
  so it exits (and flushes) after `_audio_lock` is released.
- `AudioFileManager.load_file(on_loaded=...)` and `GaplessPlaybackEngine.advance_with_prebuffer(on_swap=...)`
  run their hook inside `lock_held_hook(...)`. If a notification would dispatch inside such a
  hook without a deferral scope, `LockHeldNotificationError` is raised instead of hanging the
  player.

---

## 4. Locks and their order

Player locks: `AudioPlayer._track_change_lock` (RLock; one track change at a time),
`GaplessPlaybackEngine.update_lock` (RLock; prebuffer fields), `IntegrationManager._position_lock`
(RLock; current track and position reads), `AudioFileManager._audio_lock` (RLock; `audio_data`,
`sample_rate`, `current_file`, `closed`), `PlaybackController._lock` (RLock; state, position,
callbacks, event `seq`), `QueueManager._lock` (RLock; tracks, index, shuffle snapshot, repeat),
`AudioPlayer._fingerprint_lock` (Lock; generation and fingerprint) and the DSP locks
(`RealtimeProcessor.lock`, `AutoMasterProcessor._lock`, `RealtimeLevelMatcher._lock`).

Documented orders: `_track_change_lock` is outermost (taken before every other player lock);
`update_lock` is taken before `_audio_lock`, never after; `_position_lock` before `_audio_lock`;
`_audio_lock` before `PlaybackController._lock` and `QueueManager._lock`. Rules that follow:

- **Never block under `_audio_lock`.** Decoding happens into a local buffer first; only the swap
  (`audio_data`, `sample_rate`, `current_file`, plus the caller's hook) happens under the lock.
  The audio-thread reader takes the same lock, so a disk read inside it is an audible dropout.
- **Callbacks, joins and queue listeners run outside locks.** `QueueController` calls its change
  listener after `QueueManager._lock` is released, because the gapless engine takes `update_lock`
  before touching the queue.
- **Read what you need atomically.** `AudioFileManager.get_state_snapshot()`,
  `IntegrationManager._track_position_snapshot()` and `QueueManager.get_queue_info()` each return
  a consistent tuple/dict from one acquisition; do not reassemble them from separate reads.

---

## 5. Track loading and serialised track changes

The loaded track is several pieces written in separate critical sections (audio buffer, current
track, queue pointer, scheduled fingerprint). Two overlapping loads used to settle in
decode-completion order and pair one track's audio with another's metadata. Every
track-changing method of `AudioPlayer` (`load_file`, `load_track_from_library`, `next_track`,
`previous_track`, `add_to_queue`, `load_playlist`) is wrapped by `@serialised_track_change`
([`track_change.py`](../../auralis/player/track_change.py)), which holds `_track_change_lock`.
The lock is re-entrant (`previous_track` calls `load_file`) and must never be taken while
holding `_audio_lock`.

`load_file(path)`:

1. `file_manager.load_file(path, on_loaded=playback.load_and_stop)` decodes outside any lock,
   then swaps the buffer and resets position/state in **one** `_audio_lock` hold, so a chunk
   reader never sees new audio at the old position. `defer_notifications()` is the outer scope.
2. On success: `_schedule_fingerprint_load(path)`, `gapless.start_prebuffering()`, and an
   integration notification `file_loaded`.
3. On failure: `_note_failed_load()` enters `ERROR` only if nothing playable remains loaded; a
   failed load that leaves the previous track intact does not wedge a healthy player.

`load_track_from_library(track_id)` goes through `IntegrationManager.load_track_from_library`
([`integration_library.py`](../../auralis/player/integration_library.py)): look the track up via
`repos.tracks.get_by_id`, load the file (deferral scope around the decode and swap only, not the
DB reads), `set_current_track`, `record_play`, optional reference auto-selection
(`recommended_reference`, else `find_similar`), then a `track_loaded` notification.

`AudioFileManager.close()` (called from `cleanup()`) sets `closed` under `_audio_lock`; every
swap checks it, so a load or advance that was mid-decode when `cleanup()` ran cannot install a
buffer afterwards.

### Fingerprint loading on track change

Every load path (`load_file`, `load_track_from_library`, gapless `next_track`) calls
`_schedule_fingerprint_load(path)` ([`fingerprint_loader_mixin.py`](../../auralis/player/fingerprint_loader_mixin.py)):

1. Under `_fingerprint_lock`: increment `_track_generation` and clear the previous track's
   fingerprint (`_current_fingerprint = None`, `processor.set_fingerprint(None)`), so its makeup
   gain and ceiling never shape the new track while the new fingerprint resolves.
2. If `processor.auto_master is None` (the shipped configuration), stop: `set_fingerprint` would be a
   no-op and nothing else reads the result, so no thread is spawned. The backend fingerprints
   library tracks through its own queue (see [fingerprinting.md §5](fingerprinting.md#5-background-scheduling-how-tracks-get-fingerprinted)).
3. Otherwise spawn a daemon `fingerprint-loader` thread. `FingerprintService.get_or_compute`
   resolves the 25D fingerprint through three tiers (database, `.25d` sidecar, on-demand
   analysis; see [fingerprinting.md §3](fingerprinting.md#3-storage--two-25d-systems)).
4. The result is applied **under `_fingerprint_lock` after re-checking** that its generation still
   equals `_track_generation`; a stale thread discards its result. The failure and exception
   paths use the same check, so a stale error handler cannot reset a newer track's fingerprint.
   `cleanup()` bumps the generation so any in-flight loader discards itself.

---

## 6. The queue

`QueueController` ([`queue_controller.py`](../../auralis/player/queue_controller.py), plus
[`queue_loading.py`](../../auralis/player/queue_loading.py) and
[`queue_locked_state.py`](../../auralis/player/queue_locked_state.py)) wraps `QueueManager`
([`components/queue_manager.py`](../../auralis/player/components/queue_manager.py), with
[`queue_navigation.py`](../../auralis/player/components/queue_navigation.py),
[`queue_selection.py`](../../auralis/player/components/queue_selection.py) and
[`queue_shuffle.py`](../../auralis/player/components/queue_shuffle.py)).

- **Entries are dicts.** Library entries come from `Track.to_dict()`; `set_queue` builds
  `{'filepath': ...}` for bare paths. `entry_path()` in
  [`queue_entry.py`](../../auralis/player/queue_entry.py) is the one reader for the path across
  the `filepath` / `file_path` / `path` spellings. Use it; do not `.get('file_path')`.
  `QueueEntryTrack` stands in for a library `Track` when only the queue entry is known (after a
  queue-driven advance) and strips the path keys from `to_dict()`.
- **Atomic bulk replace.** `set_queue` and `load_playlist` clear, repopulate and write
  `current_index` under one `QueueManager._lock` hold, with rows serialised before the lock is
  taken. A concurrent `has_next_track()` never sees a momentarily empty queue.
- **Atomic navigation primitives**, each one lock acquisition: `step_previous()` returns
  `(track, saved_index, moved_to)`; `rollback_index(saved, expected_current)` is a
  compare-and-set so a failed load restores the index only if nothing moved it meanwhile;
  `advance_if_next_matches(expected)` commits a gapless advance only if the slot still holds the
  track that was prebuffered; `remove_if_index_matches_current` reports whether the removed
  entry was current.
- **Shuffle** shuffles in place keeping the current track first and snapshots the original order
  once (`_pre_shuffle_tracks`); `unshuffle()` restores it. Any structural edit
  (`add`, `insert`, `remove`, `reorder`, `move`, `clear`) drops the snapshot, so `unshuffle()`
  returns False afterwards rather than resurrecting stale order. `QueueController.set_shuffle`
  changes the flag and the order under one lock and is idempotent for repeated `True`.
- **Repeat** is a boolean: `peek_next()` / `next_track()` / `step_previous()` wrap when it is on.
  The engine has no repeat-one; the three-valued mode lives in `PlayerState` (§10).
- **Change listener.** `QueueController.set_change_listener` is wired by `AudioPlayer` to
  `GaplessPlaybackEngine.on_queue_changed`. The backend edits the queue through the controller
  directly, never through `AudioPlayer`'s wrappers, so every edit re-validates the prebuffer.

`has_next_track()` (not "is the queue empty") gates auto-advance: on the last track the queue is
non-empty but there is nothing to advance to.

---

## 7. Gapless playback

`GaplessPlaybackEngine` keeps one prebuffered next track (`next_track_buffer`,
`next_track_info`, `next_track_sample_rate`) guarded by `update_lock`. The worker lives in
`PrebufferMixin` ([`gapless_prebuffer.py`](../../auralis/player/gapless_prebuffer.py)).

- **Prebuffer worker** (`start_prebuffering`): one non-daemon thread at a time. A request that
  arrives while a pass is running sets `_rearm_requested`, and the worker runs another pass
  rather than dropping it. A pass peeks the next entry, decodes it on an inner I/O thread while
  polling `_shutdown`, re-peeks, and stores the buffer only if the queue's next entry still
  matches (`_entries_match`: equal `id`, or equal path when both carry one).
- **`advance_with_prebuffer(on_swap, abort)`** uses a peek, load, commit order, retried once:
  peek the next entry; use the prebuffer if it matches, else decode (before any lock is taken);
  poll `abort`; commit the queue advance with `advance_if_next_matches`; then, under
  `update_lock` then `_audio_lock`, install `audio_data` / `sample_rate` / `current_file` and run
  `on_swap`. Nothing is mutated until the commit succeeds, so a failure needs no rollback. A
  prebuffer at a different sample rate is installed together with its rate.
- **`on_queue_changed`** keeps the buffer if the next entry still matches, otherwise clears it
  and re-arms prebuffering.
- **`cleanup`** sets `_shutdown` before taking `_thread_lock`, snapshots the thread handle, and
  joins outside the lock (5 s timeout).

---

## 8. The pull loop and auto-advance (`PlayerStreamingMixin`)

`get_audio_chunk(chunk_size)` is the engine's real-time entry point. In one `_audio_lock` hold it
checks that audio is loaded, calls `playback.read_and_advance_if_playing(chunk, total_samples)`
(returns None, so silence, unless `PLAYING`), slices the chunk, and tests for end-of-track. The
chunk is then run through `RealtimeProcessor.process_chunk` **outside** the lock.

At end-of-track:

- With `auto_advance` on and `queue.has_next_track()`, it sets `_auto_advancing`, bumps
  `_advance_generation` and spawns one daemon thread running `_auto_advance_next`. The
  test-and-spawn is inside `_audio_lock`, so concurrent callers cannot spawn duplicates; the
  thread clears the flag with a generation compare-and-clear, also under `_audio_lock`.
- Otherwise `_finish_playback()` runs after the lock is released: `playback.stop()` and, only if
  that transition happened, a `playback_finished` notification.
- `_auto_advance_next` bails if `_stop_requested` or `_cleanup_in_progress` is set, and calls
  `next_track(completed=True)`; only that path increments `tracks_played`
  (`record_track_completion`). If the successor cannot be loaded it finishes once instead of
  being re-spawned every chunk.

`stop()` sets `_stop_requested` and `pause()` sets `_pause_requested`; `next_track` and
`previous_track` resume playback after a blocking transition unless `stop()` is requested, and
re-pause if `pause()` raced in. `play()` clears both flags only after the transition succeeds.

---

## 9. Real-time processing (`realtime/`)

`RealtimeProcessor.process_chunk(audio, sample_rate)`
([`realtime/processor.py`](../../auralis/player/realtime/processor.py)) copies the input and
applies, in order:

1. `RealtimeLevelMatcher` when level matching is enabled **and** a reference is set. RMS
   matching to the reference with a smoothed target and `AdaptiveGainSmoother`; its enabled flag
   turns on in `set_reference_audio`.
2. `AutoMasterProcessor` when it exists (`enable_auto_mastering`, default off) **and** has been
   switched on: it starts with `enabled=False`, so the config flag only constructs it and
   `set_effect_enabled('auto_mastering', True)` activates it. A fingerprint-aware
   chain (stateful gentle compressor, adaptive makeup gain capped to headroom, optional low-mid
   transient enhancement for quiet, dynamic material, adaptive peak ceiling). Its parameters come
   from the track's fingerprint (`set_fingerprint`); without one it applies unity gain. DSP
   objects are rebuilt when a loaded track's sample rate differs from the configured one.
3. `StreamingPeakCeiling` at `PlayerConfig.realtime_safety_peak` (0.95): a zero-latency limiter
   whose gain envelope is carried across chunks, so there are no steps at chunk edges.
4. `validate_audio_finite(..., repair=True)`, then a `PerformanceMonitor` sample.

`set_reference_audio` deliberately does not take `RealtimeProcessor.lock`: measuring a long
reference's RMS under it would stall every `process_chunk`. This chain is separate from
`HybridProcessor` (the mastering engine behind the WebSocket stream); the two share
primitives, not a pipeline. Do not describe `AutoMasterProcessor` as the app's mastering path.

---

## 10. Backend relation: two state models

```
renderer ──REST/WS──> routers ──> services ──> AudioPlayer (engine queue, load, navigation)
                                      │
                                      └──────> PlayerStateManager (PlayerState → "player_state" WS)
```

| | Engine | Backend |
|---|--------|---------|
| Class | `AudioPlayer` + components | `PlayerStateManager` ([`core/state_manager.py`](../../auralis-web/backend/core/state_manager.py)) |
| Model | `PlaybackState`, sample position, queue of dicts | `PlayerState` ([`player_state.py`](../../auralis-web/backend/player_state.py)) |
| Concurrency | `threading.RLock`s | one `asyncio.Lock`; mutate under it, **broadcast outside it** |
| Position | samples, advanced by `get_audio_chunk` | `current_time` seconds, advanced by a 1 Hz ticker while `is_playing` |
| Queue | authoritative (order, index, shuffle, repeat bool) | `TrackInfo` copy, may lag |

`PlayerState` carries a broadcast `seq` (clients drop older snapshots), a per-process
`server_instance_id` (a changed id tells a reconnecting client the in-memory session was reset),
`volume` on a **0–100** scale, `repeat_mode` as `off | one | all`, and `current_track` /
`queue` as `TrackInfo` (the server-side `filepath` is excluded from responses). The session is
in-memory only.

`PlayerStateManager._mutate_state` assigns fields, derives `is_playing` / `is_paused` from
`state`, sets `duration` from the current track, bumps `seq` and returns a shallow copy.
`get_state()` is also a shallow copy; nothing may mutate `queue`, `current_track` or `analysis`
in place, only replace them. The position ticker (`PositionTickerMixin`) advances by measured
wall-clock time, clamps to `duration`, and **holds** at the end: only navigation moves to another
track (`follow_navigation`, matched by `filepath`).

### Services that bridge the two

- **`QueueService`** ([`services/queue_service.py`](../../auralis-web/backend/services/queue_service.py)
  with `queue_set_mixin.py`, `queue_edit_mixin.py`, `queue_order_mixin.py`) is the main bridge.
  `set_queue` resolves track rows, mutates `PlayerState` under a process-wide sequencer
  (`queue_set_sequencer`), then calls the engine (`queue.set_queue`, `load_file`, `play`), then
  broadcasts. Every queue-shape mutation runs inside `_queue_mutation()`, which supersedes any
  in-flight `set_queue` and serialises engine calls; no engine lock ever covers a broadcast.
- **`QueueService.get_queue_info`** is the read-side bridge. The engine queue is the source of
  truth for order and contents but stores only filepaths, so `QueueEnricher` (`queue_enrichment.py`)
  resolves entries to `TrackInfo` (first from `PlayerState.queue` by filepath, then a batched
  `tracks.get_by_paths` library lookup), drops unresolvable entries and re-bases `current_index`
  past them, picks `current_track` by the engine's current filepath, and widens the engine's
  boolean repeat into the state manager's three-valued `repeat_mode`. The same enricher builds the
  `queue_changed` broadcast payload.
- **`NavigationService`** serialises `next` / `previous` behind a process-wide lock, runs the
  engine call in `asyncio.to_thread`, then tells the state manager (`follow_navigation`) which
  track the engine landed on and broadcasts `track_changed` with a monotonic `seq`.
- **`PlaybackService`** (`services/playback_service.py`) wraps engine `play` / `pause` / `stop` /
  `seek` (via the transport executor) plus `set_playing`, behind a process-wide transition lock
  shared with the WebSocket `pause` / `resume` / `stop` handlers
  (`services/playback_event_sequencer.py`). Registered REST routes use its `seek`, `set_volume`
  and `get_status`; no registered route calls its `play` / `pause` / `stop`. The renderer's
  pause, resume and stop arrive as WebSocket messages that gate the stream task and do not
  touch the engine. Queue operations are what start (`set_queue`) and stop (clearing the queue)
  engine playback.

Pitfalls specific to this seam: a new queue mutation must go through `_queue_mutation()` (do not
call the engine queue from a router); anything new that moves "now playing" must call
`follow_navigation` or it will leave `PlayerState` on the old track; never hold an engine lock
across `await`.

---

## 11. Invariants and pitfalls

- `0 <= position <= total_samples` at all times: `seek` clamps (NaN rejected, inf clamped),
  `read_and_advance_position` clamps the stored value, the reported position is
  `min(position / sample_rate, duration)`, and the backend ticker clamps to `duration`.
- State changes are atomic under the controller's `RLock`; callbacks fire after release and carry
  a monotonic `seq`. The loaded audio and the position change together in one `_audio_lock` hold.
- Only one track change runs at a time; a fingerprint is applied only if its generation is current.
- Chunks handed out are stereo `(n, 2)` (mono duplicated, tails zero-padded) and never expose the
  stored buffer for in-place modification.
- **Do not assume the engine is the audible player.** Its position does not advance in the app;
  the state the UI shows is `PlayerState`.
- **Do not read queue entries by key**; use `entry_path()`.
- **Do not fire playback notifications under `_audio_lock`**; open `defer_notifications()` first.
- **Do not add a repeat-one or a second "next" owner to the engine**; navigation is the only
  mover of "now playing". **Do not mutate `PlayerState` containers in place.**
- `get_playback_info()`, `has_prebuffered_track()`, `is_paused()` and
  `QueueManager.snapshot_index()` have no production caller; they are kept for their lock-ordered
  reads and for tests.

---

## 12. Where to start reading

1. [`enhanced_audio_player.py`](../../auralis/player/enhanced_audio_player.py): facade wiring,
   transport, `cleanup`.
2. [`playback_controller.py`](../../auralis/player/playback_controller.py) and
   [`playback_notifier.py`](../../auralis/player/playback_notifier.py): state machine and
   deferred notifications.
3. [`player_file_loading_mixin.py`](../../auralis/player/player_file_loading_mixin.py) and
   [`player_queue_navigation_mixin.py`](../../auralis/player/player_queue_navigation_mixin.py):
   lock choreography around loads and navigation.
4. [`gapless_playback_engine.py`](../../auralis/player/gapless_playback_engine.py) and
   [`components/queue_manager.py`](../../auralis/player/components/queue_manager.py).
5. Backend: [`core/state_manager.py`](../../auralis-web/backend/core/state_manager.py),
   [`services/queue_service.py`](../../auralis-web/backend/services/queue_service.py),
   [`services/navigation_service.py`](../../auralis-web/backend/services/navigation_service.py).
6. Tests: [`tests/auralis/player/`](../../tests/auralis/player/) covers the race cases.

**Related:** [backend-api.md](backend-api.md) · [dsp-engine.md](dsp-engine.md) ·
[fingerprinting.md](fingerprinting.md) · [library.md](library.md) ·
[../architecture/data-flow.md](../architecture/data-flow.md)
