# Backend Audit — Auralis FastAPI Backend

**Date**: 2026-07-29
**Commit**: `master` @ `9e03236c`
**Scope**: `auralis-web/backend/` (109 `.py` files, ~28.2k LOC) — routers, WebSocket streaming, chunked processing, processing engine, schemas, middleware, error handling, performance, test coverage. Frontend and `auralis/` engine internals were read only where needed to verify a cross-layer contract.
**Method**: fresh read of current source by nine dimension agents plus a Dimension 5 completion pass. No findings were carried over from `docs/audits/AUDIT_BACKEND_2026-07-25.md` — that report was consulted for deduplication only. Every finding was deduplicated against 400 GitHub issues (`gh issue list --state all`) and prior audit finding titles. No tests were executed beyond narrowly-scoped collection; the full pytest suite was deliberately not run.

---

## Executive summary

**89 findings** after cross-dimension deduplication (95 raw, 6 collapsed).

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 9 |
| MEDIUM | 31 |
| LOW | 48 |
| **Total** | **89** |

### Read this first: the regression gate has never worked

**BE9-01** is the context for every other finding in this report. `.github/workflows/backend-tests.yml` delegates its pass/fail decision entirely to `scripts/check_pytest_baseline.py`, which reads a `pytest-baseline.json` that **was never committed** — so the script `sys.exit(1)`s on `FileNotFoundError` and the deciding step has failed on every run since it was added. 341 tests are failing on master right now, 225 of them backend-scoped, and nothing surfaces that. `_audit-common.md` states the backend baseline is "checked in and CI-enforced"; it is neither. This is the mechanism by which the rest of this report reached master unnoticed.

### Most impactful issues

1. **BE3-07 (CRITICAL)** — `LevelManager.smooth_transition()` computes an unbounded gain correction. `calculate_rms()` floors digital silence at −200 dB, so one silent chunk produces a ≈ −188 dB correction and a ramp *from* the previous chunk's stored +188 dB gain: a **50 ms full-scale burst** followed by ~10 s of digital silence, with a poisoned RMS history that destroys the remainder of the track. Executed against the real class: `peak_out = 2.6e9` on input peaking at 1.0. Three reachable triggers, including one the backend manufactures itself on every track (BE3-08). This is a **listener-safety** issue on a desktop app.
2. **BE2-01 (HIGH, Regression of #3763)** — `handle_play_enhanced` dedupes on `track_id` alone, so every mid-playback preset change, intensity change, and enhancement toggle-ON is silently discarded. The shared `enhancement_settings` dict is written *before* the guard, so the status endpoint and the UI report success while the audio keeps rendering the old settings. Confirmed independently by the integration audit with a live repro. Highest-confidence user-facing finding in this report.
3. **BE8-06 (HIGH)** — libsndfile cannot open `.m4a`/`.aac`/`.wma`, so `load_chunk_from_file`'s `except` branch falls back to a **full-file FFmpeg decode per chunk**. A 10-minute M4A costs ~60 full decodes to play once — roughly 60× CPU/IO amplification with a ~200 MB transient allocation each, on a path that runs concurrently with playback.
4. **BE7-1 (HIGH)** — the 300 s processing timeout returns a still-running `HybridProcessor` to the shared pool, so the orphaned thread and the next job mutate the same object concurrently, and one slot of the *default* `ThreadPoolExecutor` is leaked permanently. The timeout exists precisely for the case where the thread does not come back.

### Key themes

- **Failure paths report success.** Four independent places convert data loss into silence: a swallowed frame send (BE2-02), a half-sent meta/PCM pair (BE2-03), the chunk-skip recovery branch (BE2-06 + BE7-5), and the `#4659` `stopped_early` accounting that misses the `continue` branch. A stream that dropped 10 s of audio still terminates with `reason: "completed"` and the full track duration.
- **Fixes that stopped one call site short.** BE1-2 (a defect *introduced by* the #4555 allowlist fix), BE3-09 (#4557 not propagated to two other position→chunk derivations), BE4-5 (#3716/#3554 missed `NavigationService`), BE6-5 (#4366/#4376 missed three sites in the same file), BE8-06 (#4497 fixed metadata but not chunk loading), BE7-5 (#4659 fixed early-exit but not skip-and-continue).
- **Tested-but-unwired subsystems.** `monitoring/` (936 lines, BE6-3), `services/learning_system.py` + `audio_content_predictor.py` (1,062 lines, BE4-14), `validate_scan_path`/`is_safe_filename` (BE6-7), `cache/endpoints.py` (BE1-7), 15 orphan models in `schemas.py` (BE5B-N1). Passing tests actively mask the fact that none of it runs. #4379 was a real fix spent on unreachable code.
- **Documentation that describes a system the code does not implement.** Two "backpressure" guards are inert under uvicorn's sans-io WebSocket protocol (BE2-04); the "equal-power" crossfade is linear-equivalent and its regression test is vacuous (BE3-14); `HybridProcessor.close()` is a no-op behind five call sites that cite a leak it no longer prevents (BE4-7); the `setup_middleware` docstring contradicts the correct comment four lines below it (BE6-6).
- **Security posture is sound.** No path traversal, no injection, no auth bypass. `path_security.py`'s containment uses `relative_to()` on fully symlink-resolved paths — the `/music-evil` vs `/music` prefix bypass was specifically attempted and does not work. CORS never pairs `allow_credentials=True` with a wildcard. The one CRITICAL is an audio-integrity defect, not a security one.

### Conflict to resolve before fixing (do not apply blindly)

**BE3-14** reports the backend chunk crossfade (`auralis-web/backend/core/chunk_crossfade.py:53-56`, `cos²`/`sin²`) as mislabelled "equal-power" — it is amplitude-complementary and dips −3.01 dB at the midpoint for uncorrelated content. The **engine audit's Dimension 1 independently concluded that the engine-side chunk-loop crossfade is correctly equal-gain and explicitly warned against changing it to `sin`/`cos`.** These are different files and different call sites, and the backend copy currently has **zero production call sites** — which is why BE3-14 is LOW. Reconcile the two before touching either; do not apply BE3-14's curve change to the engine path.

---

## Route coverage matrix

All 20 routers registered by `auralis-web/backend/config/routes.py`, verified against the live file.

| Router | # endpoints | Pydantic body models | Validation status | Findings |
|---|---|---|---|---|
| `player.py` | 17 | Yes (10 request models) | `SeekRequest` guards NaN/Inf; `RepeatModeRequest` is a `Literal`; route order correct (`/queue/history`, `/queue/undo` precede `/queue/{index}`). List bodies unbounded (#4681, open). | BE4-13, BE5B-N5 |
| `library.py` | 3 | N/A | `POST /reset` gated on `X-Confirm-Reset` header. | BE6-2 (indirect) |
| `library_scan.py` | 1 | Yes (`LibraryScanRequest`) | Per-entry `field_validator` → `validate_user_chosen_directory`. Terminal WS frames on cancel and timeout. | BE6-7, BE7-7 |
| `tracks.py` | 6 | N/A | `order_by` is a `Literal`; limit/offset bounded; `/favorites` correctly precedes `/{track_id}`. | **BE1-1**, BE1-3 |
| `albums.py` | 4 | N/A | limit/offset bounded, `order_by` `Literal`, eager-load + `expunge_all`. | BE8-09, BE5-N3 |
| `artists.py` | 3 | N/A | limit/offset bounded, `order_by` `Literal`. | BE5-N2 |
| `artwork.py` | 4 | N/A | `size` bounded `ge=16, le=2048`; containment via `resolve()` + `is_relative_to()` **before** the existence check; DELETE idempotent (#3563). Clean. | — |
| `metadata.py` | 4 | Yes (3, `extra="forbid"`) | All DB-sourced filepaths through `validate_file_path`. | **BE1-2** |
| `playlists.py` | 9 | Yes (4) | Positions bounded `ge=0`; route order safe. `track_ids` lists unbounded. | BE1-5 |
| `enhancement.py` | 6 | Yes (3) | `preset` → `EnhancementPresetLiteral`; `intensity` bounded 0–1; recommendation cache TTL + FIFO-capped. | BE3-09, BE8-15 |
| `settings.py` | 5 | Yes (2, `extra="forbid"`) | `scan-folders` route validates + registers; `PUT /api/settings` does neither. | BE1-4, BE5-N1 |
| `files.py` | 2 | N/A (multipart) | File-count cap, size cap at read time, magic-byte allowlist, UUID filenames. | BE5B-N6 |
| `processing_api.py` | 8 | Yes (2) | Paths through `validate_file_path`; upload uses `open(..., "xb")`; download confined to tempdir. | BE1-6, BE4-1, BE4-9 |
| `similarity.py` | 4 | N/A | Query params bounded; `require_similarity_system` → 503 (#4656 verified fixed). | BE5B-N3, BE6-1 |
| `similarity_graph.py` | 3 | N/A | `k` bounded 1–50. No prefix collision with the other two `/api/similarity` routers. | — |
| `fingerprint_queue.py` | 4 | N/A | `limit: int = Query(None, ...)` type/default mismatch (prior BE1-07). | BE6-1 |
| `fingerprint_status.py` | 2 | N/A | Sync `queue.enqueue()` on the loop (prior BE1-08). | BE6-11 |
| `cache_streamlined.py` | 5 | N/A | `_require_cache` → 503 before lifespan init; errors redacted. | BE5B-N1, BE5B-N4 |
| `health.py` | 2 | N/A | Typed response models. Clean. | — |
| `system.py` | 1 (WebSocket `/ws`) | N/A | Rate-limited + size/structure-validated messages. | BE2-05, BE2-08, BE2-11 |

Non-router HTTP surface: `cache/endpoints.py` registers **zero** endpoints and has no importers (BE1-7).

**Cross-router prefix-collision check** — `/api/similarity` (×3 routers), `/api/processing` (×2), `/api/albums` (×2), `/api/library` (×4), `/api/player` (×2): no literal path is shadowed by a parameterised one. Starlette scans in registration order and treats a path-match/method-miss as `Match.PARTIAL`, continuing the scan. Verified explicitly for `PUT /api/player/queue/reorder` vs `DELETE /api/player/queue/{index}` and `PUT /api/playlists/{id}/tracks/reorder` vs `DELETE /api/playlists/{id}/tracks/{track_id}`. **No route-conflict finding.**

---

## Middleware order (computed empirically)

Derived by calling the real `config.middleware.setup_middleware()` on a bare `FastAPI()` and reading `app.user_middleware` (Starlette 1.3.1 / FastAPI 0.140.13):

```
Request-inbound: ServerErrorMiddleware → CORS → SecurityHeaders → NoCache
                 → TrustedHost → RateLimit → ExceptionMiddleware → router
```

This **matches** the documented intent in the load-bearing comment at `config/middleware.py:318-320`; the `#3843` reordering achieves what it claims. Verified behaviourally: a `429` from `RateLimitMiddleware` and a `400` from `TrustedHostMiddleware` both carry full CORS *and* security headers. Only the function *docstring* four lines above is stale (BE6-6).

Caveat worth recording: `BaseHTTPMiddleware.__call__` short-circuits on `scope["type"] != "http"`, so `NoCache`, `SecurityHeaders` and `RateLimit` do **not** run for WebSocket upgrades. Only `TrustedHostMiddleware` covers `websocket` scopes. WebSocket origin enforcement lives entirely in `ConnectionManager.connect()` (`config/globals.py:87-104`), which does implement it — by design, not a gap.

---

## Coverage and caveats — what was NOT audited

**Do not read any area below as audited-and-clean.**

### Dimension 2 (WebSocket Streaming) — not reached
`core/stream_fingerprint.py` (read only via its call sites), the internals of `core/chunk_cache.py` / `chunk_cache_manager.py` / `chunk_crossfade.py`, `auralis-web/backend/WEBSOCKET_API.md` (doc-vs-code drift not checked), the `ws_handlers/__init__.py` re-export surface, and the backend WebSocket test suite. No findings in this dimension are test-confirmed.

### Dimension 4 (Processing Engine) — six areas not reached
`core/proactive_buffer.py` beyond lines 30-90; `core/chunk_mastering.py`, `core/chunk_cache_manager.py`, `core/file_signature.py`, `core/env_config.py` (not opened); `services/audio_content_predictor.py` internals; the three learner classes in `services/learning_system.py` and their module-level singletons (**thread-safety of those singletons is unverified**); `services/artwork_downloader.py` beyond a method inventory; `services/queue_service.py` lines 290-661 (surveyed by signature/grep only). Whether enhancement `preset`/`intensity` mutations are ever persisted back to `UserSettings` was not resolved — `routers/settings.py` was not read in this dimension.

### Dimension 5 (Schema Consistency) — PARTIAL even after the completion pass
Dimension 5 ran in two halves (`dim_5` + `dim_5b`). A **residual gap remains that neither half covered**:
- `auralis-web/frontend/src/types/ws/queue.ts` and `types/ws/system.ts` were skipped by **both** halves. WebSocket registry drift is *partially* covered by open **#4680**, so the gap is narrowed but not closed.
- The inline Pydantic models defined in the 8 routers that the first half read were **never cross-checked for duplication against `schemas.py`** — the duplication that BE5B-N1/N2 found in `cache_streamlined.py` and `pagination.py` may have siblings elsewhere.

Positive coverage note: the second half confirmed that **all** of `src/types/api.ts` is consumer-less and correctly left it to open **#4398**/**#4460** rather than re-filing.

### Dimension 8 (Performance) — PARTIAL
This dimension ran out of context before completing. **BE8-16 is explicitly provisional and not fully verified** — treat it as a lead, not a confirmed finding.

### Dimension 9 (Test Coverage) — PARTIAL
The per-router table is complete, but the test-quality sweep (stale mocks, tautological assertions) was not exhaustive.

### Global
- **No tests were executed.** Every finding is static-analysis based, except where a dimension explicitly states it ran a snippet against the real class in the venv (BE3-07's `peak_out = 2.6e9` measurement, BE3-08's chunk geometry, BE6-1's live middleware probe, BE6-6's `app.user_middleware` read, BE8-06's `sf.available_formats()` check).
- Rust/PyO3 internals, DSP correctness inside `auralis/`, SQLAlchemy repository internals, and the React frontend beyond contract-checking are out of scope by charter.

### Skill-file correction
`.claude/commands/audit-backend.md` and `_audit-common.md` both claim **two live `WAVEncoderError` classes** exist and instruct auditors to check every `except WAVEncoderError` resolves correctly. **This premise is false.** `auralis-web/backend/core/encoding/wav_encoder.py` defines `WAVEncoder` but **no** `WAVEncoderError`; the only such class is at `auralis-web/backend/encoding/wav_encoder.py:31`, and the single `except WAVEncoderError` (`core/chunked_processor.py:794`) imports it from that same module three lines earlier. No cross-module mismatch exists. The skill files should be corrected.

---

# Findings

## Critical severity (1)

### BE3-07: Unbounded level-smoothing gain — one silent chunk emits a full-scale burst and then mutes the rest of the track

- **Severity**: CRITICAL
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/level_manager.py:144-204`; reached from `/mnt/data/src/matchering/auralis-web/backend/core/chunked_processor.py:489-499`
- **Status**: NEW
- **Description**:
  `LevelManager.smooth_transition()` forces each chunk's RMS to within
  `MAX_LEVEL_CHANGE_DB` (1.5 dB) of the previous chunk's, and computes the
  correction as `required_adjustment_db = target_diff - level_diff_db` with **no
  clamp on the magnitude of the correction**. `calculate_rms()` floors digital
  silence at `20*log10(1e-10) = -200 dB`. So a chunk of digital silence followed
  by a normal chunk yields `level_diff_db ≈ +190` and a correction of ≈ `-188 dB`.
  Worse, `_gain_envelope()` ramps from the *previous* chunk's stored gain
  (`+188 dB` → linear `2.5e9`) to the new gain over `GAIN_RAMP_SECONDS` (50 ms),
  then holds the new gain flat for the remaining ~10 s. Result: a 50 ms
  full-scale garbage burst at the chunk boundary followed by ~10 s of digital
  silence — and the poisoned RMS it records propagates to every later chunk.
- **Evidence**:
  `core/level_manager.py:162-187`
  ```python
  target_diff = (self.max_level_change_db if level_diff_db > 0 else -self.max_level_change_db)
  required_adjustment_db = target_diff - level_diff_db          # <- unbounded
  new_gain = float(10 ** (required_adjustment_db / 20))
  prev_gain_db = self.gain_history[-1] if self.gain_history else 0.0
  prev_gain = float(10 ** (prev_gain_db / 20))                  # <- can be 2.5e9
  env = self._gain_envelope(n_samples=len(chunk), prev_gain=prev_gain, new_gain=new_gain, ...)
  chunk_adjusted = chunk * (env[:, None] if chunk.ndim == 2 else env)
  ```
  Executed against the real class (venv, numpy 2, `SR=44100`, 10 s chunks):
  ```
  after silent chunk : gain_db=+188.04  rms_hist=[-10.5, -200.0]
  next real chunk    : gain_db=-188.04  peak_out=2.600e+09
  chunk3             : gain_db=+158.78  peak_out=1.368e+08
  rms history        : [-10.5, -200.0, 149.8, 148.3]     # permanently corrupt
  ```
  `peak_out = 2.6e9` on input that peaked at ~1.0. `encode_to_wav` clips to
  ±full-scale, so the client receives 50 ms of full-scale square-wave noise.
- **Impact**:
  Three distinct exercise paths, all reachable:
  1. **Any digitally-silent ~10 s stretch inside a track** (hidden-track gaps,
     inter-movement silence, silent lead-in on a rip) triggers it directly on the
     live enhanced stream.
  2. `_process_chunk_core` has an explicit degradation path that *manufactures*
     the trigger: `core/chunked_processor.py:489-495` replaces an empty
     post-trim chunk with `np.zeros(...)` (100 ms of silence) and then feeds it
     straight into `_smooth_level_transition` at line 499. So a single failed
     chunk poisons the *next* chunk — the exact "does a failed chunk corrupt
     subsequent chunks?" question (check 8): **yes, catastrophically.**
  3. BE3-08 below manufactures a full 10 s all-zero chunk on every track.
  Because the corrupted RMS is written back into `rms_history`, every subsequent
  chunk keeps oscillating between ±150 dB corrections — the rest of the track is
  destroyed, and any chunk WAV written while poisoned is cached to disk under the
  canonical cache path and served verbatim later.
  This is a listener-safety issue on a desktop app: a 50 ms full-scale burst at
  whatever monitoring level the user has set.
- **Siblings**:
  - `record_cached_level()` (`level_manager.py:238-254`) has the same
    `calculate_rms` floor and will happily record `-200 dB` for a cached silent chunk.
  - The unbounded correction is not only a silence problem: a legitimate quiet
    passage 40 dB below the previous chunk gets a `+38.5 dB` boost across the
    whole chunk. Normal operation hides this only because the upstream loudness
    normalisation usually keeps inter-chunk diffs under 1.5 dB.
  - `tests/backend/test_level_manager_smoothing.py` covers dtype, non-mutation
    and ramp continuity but has no silence / extreme-diff case.
- **Suggested Fix**:
  1. Clamp `required_adjustment_db` to a sane band (e.g. ±6 dB) before converting
     to linear gain, and clamp `prev_gain_db` the same way when building the ramp.
  2. Gate the whole smoothing branch on a silence floor: if either
     `current_rms` or `previous_rms` is below e.g. `-60 dB`, record the RMS but
     apply no gain (`return chunk, 0.0, False`) — a silent chunk carries no level
     information to smooth against.
  3. Do not feed the manufactured-silence fallback at
     `chunked_processor.py:495` into `_smooth_level_transition` at all.

---


## High severity (9)

### BE1-1: `GET /api/library/tracks/{id}/lyrics` calls `TrackRepository.update()` with a signature that cannot exist — every file-extracted lyric is discarded and the endpoint returns `lyrics: null`

- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/tracks.py:133-190` (call at :176); repository at `/mnt/data/src/matchering/auralis/library/repositories/track_repository.py:743-802`
- **Status**: NEW
- **Description**: When a track has no `lyrics` column value, the handler extracts lyrics from the audio
  file with mutagen and then tries to persist them. The persist call passes `lyrics` as a **keyword**
  argument, but `TrackRepository.update()` takes a single positional `track_info: dict`. The call raises
  `TypeError` before the repository body ever runs. That `TypeError` is raised inside the inner
  `try:` block, is caught by the broad `except Exception` at :182, is logged at ERROR, and then control
  falls straight through to the terminal `return` at :185 — which reports `lyrics: None`. The
  successfully-extracted lyrics text is thrown away in the same frame it was produced.
  Even if the signature matched, `update()` only writes the fields in its hardcoded list
  (`title, duration, bitrate, sample_rate, year, track_number, disc_number`) — `lyrics` is not among
  them, so the write would still be a silent no-op. The correct target is
  `update_metadata(track_id, lyrics=...)`, whose allowlist does contain `lyrics`.
- **Evidence**:
```python
# routers/tracks.py:175-185
                if lyrics_text:
                    await asyncio.to_thread(repos.tracks.update, track_id, lyrics=lyrics_text)
                    return {
                        "track_id": track_id,
                        "lyrics": lyrics_text,
                        ...
            except Exception as e:
                logger.error(f"Failed to extract lyrics from file: {e}")

            return {"track_id": track_id, "lyrics": None, "format": None}
```
```python
# auralis/library/repositories/track_repository.py:743
    def update(self, track_id: int, track_info: dict[str, Any]) -> Track | None:
        ...
            for field in ['title', 'duration', 'bitrate', 'sample_rate', 'year', 'track_number', 'disc_number']:
```
- **Impact**: The lyrics feature is non-functional for every track whose lyrics live only in the file
  (i.e. every track that has not had lyrics written through `PUT /api/metadata/tracks/{id}`). The
  failure is invisible to the client: HTTP 200 with `lyrics: null`, indistinguishable from "this track
  genuinely has no lyrics". Because the exception is caught, no 500 is ever raised and no monitoring
  signal fires; only an ERROR log line records it. Every request re-does the mutagen file read, so the
  intended cache is also never populated.
- **Siblings**: Same broad-`except`-swallows-a-real-defect shape in `enhancement.py:196-198`
  (per-chunk pre-processing) and `fingerprint_status.py:109-110` (enqueue failure), but those degrade a
  best-effort path rather than discarding a computed result.
- **Suggested Fix**: Call `repos.tracks.update_metadata(track_id, lyrics=lyrics_text)` (its allowlist
  already contains `lyrics`), and narrow the `except Exception` so a persistence failure still returns
  the extracted lyrics instead of falling through to the `None` branch.

---

### BE1-2: Metadata edits to track number / disc number / comment are written to the audio file but silently dropped from the database — the allowlist is keyed on ORM column names while the router sends tag names

- **Severity**: HIGH
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/metadata.py:36-53, 216-275, 319-345`; allowlist at `/mnt/data/src/matchering/auralis/library/repositories/track_repository.py:50-76`
- **Status**: NEW (defect introduced by the #4555 fix, which is otherwise still in place — not a regression of it)
- **Description**: `MetadataUpdateRequest` names its fields after **mutagen tag names**
  (`track`, `disc`, `comment`) and exposes the DB column names only as aliases
  (`Field(None, alias="track_number")`). Both `PUT /api/metadata/tracks/{track_id}` and
  `POST /api/metadata/batch` build their update dict with `request.model_dump()`, which by default emits
  **field names, not aliases** — so the dict carries `{'track': 5, 'disc': 1, 'comment': '...'}`.
  That is exactly right for `MetadataEditor.write_metadata()` (see
  `auralis/library/metadata_editor/tag_mappings.py:15`, which lists `'track', 'disc', 'comment'`), and
  the file write succeeds. The very same dict is then forwarded to
  `repos.tracks.update_metadata(track_id, **metadata_updates)`, whose `#4555` allowlist contains the
  **column** names `track_number`, `disc_number`, `comments`. `_filter_metadata_fields` therefore drops
  all three, logs them at ERROR as "non-metadata field(s)", and commits nothing. `title`, `year` and
  `lyrics` happen to have identical tag and column names, so they do go through — which is why the bug
  looks like it works.
- **Evidence**:
```python
# routers/metadata.py:44-45  (field name != column name)
    track: int | None = Field(None, alias="track_number")
    disc: int | None = Field(None, alias="disc_number")
    comment: str | None = None

# routers/metadata.py:217-220 + 244-246  (model_dump() -> field names)
            metadata_updates = {
                k: v for k, v in request.model_dump().items()
                if v is not None
            }
            ...
            updated_track = await asyncio.to_thread(
                lambda: repos.tracks.update_metadata(track_id, **metadata_updates)
            )
```
```python
# auralis/library/repositories/track_repository.py:50-57  (column names)
_METADATA_WRITABLE_COLUMNS: frozenset[str] = frozenset({
    'title', 'year', 'track_number', 'disc_number', 'comments', 'lyrics',
})
```
- **Impact**: The file on disk and the library database permanently diverge after any track-number,
  disc-number or comment edit. The route returns `{"success": true, "updated_fields": ["track", ...]}`
  and broadcasts `metadata_updated` with those field names, so the UI believes the edit landed; the
  library list, album track ordering (`serialize_tracks` → `track_number`) and the album-detail sort in
  `albums.py:143` keep showing the old values until a full rescan re-reads the file. Album track
  ordering is the most visible casualty — reordering an album by fixing its track numbers appears to
  work and then reverts on the next page load. Every such edit also emits a misleading
  `error(...)`-level log line claiming the caller tried to write a non-metadata field.
- **Siblings**: `POST /api/metadata/batch` (`metadata.py:323-326` → `update_metadata_batch`) has the
  identical mismatch. `artist`, `album`, `albumartist`, `genre`, `bpm`, `composer`, `publisher`,
  `copyright` are also reported in `updated_fields` but are not Track columns at all — same
  "reported-as-updated, never persisted" class, though for those the DB write was never intended.
- **Suggested Fix**: Translate tag names to column names at the router boundary before the repository
  call (e.g. `model_dump(by_alias=True)` plus a `comment → comments` mapping), keeping the untranslated
  dict for `MetadataEditor`. Add a test that asserts every key in `MetadataUpdateRequest.model_fields`
  is either in `_METADATA_WRITABLE_COLUMNS` or explicitly documented as file-only.

---

### BE2-01: `play_enhanced` same-track dedup silently discards every mid-stream stream re-issue

- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/playback_commands.py:192-198`; callers at `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:276,351,417` and `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/websocket/useWebSocketConnection.ts:321-355`
- **Status**: **Regression of #3763** (with #3759). Independently confirmed by the integration audit (INT3-04) with a live repro. **Contradicts OPEN #4425**, whose premise (a teardown+reissue that costs a re-buffer) is wrong — no teardown occurs at all; do not work #4425 from its current description.
- **Description**: `handle_play_enhanced` drops any `play_enhanced` whose `track_id` matches the currently-streaming track, comparing **only** `track_id` — never `preset`, `intensity`, or `start_position`. The frontend's `reissueActiveStreamAs('play_enhanced', {preset, intensity})` is invoked from exactly three places (preset change, intensity change, enhancement toggle-ON) and always sends the same `track_id`. All three are silently swallowed.
- **Evidence**:
```python
# playback_commands.py:192-198
    # Deduplicate: if the same track is already streaming, skip
    async with state.active_tasks_lock:
        existing_track = state.active_track_ids.get(ws_id)
        existing_task = state.active_tasks.get(ws_id)
        if (existing_track == track_id and existing_task is not None and not existing_task.done()):
            logger.info(f"Ignoring duplicate play_enhanced for track {track_id} (already streaming on ws {ws_id})")
            return
```
`handle_play_normal` (same file, line 234+) has **no** such dedup, so the reverse direction (enhanced→normal) works — the asymmetry is what hides the bug. Note `handle_play_normal` sets `state.active_track_ids[ws_id] = track_id` at line 279, so the toggle-ON case (`play_normal` running → re-issue as `play_enhanced`) also hits the dedup and is dropped: audio keeps playing **unenhanced** while the UI reports enhancement on.
- **Impact**: Mid-playback preset change, intensity change, and enhancement toggle-on have **no effect on audio** for the entire remainder of the track. The comment at `useEnhancementControl.ts:158-163` ("so live changes actually affect the audio path") documents an intent the backend defeats. Reconnect-resume is unaffected (new socket ⇒ new `ws_id`).
- **Cross-audit corroboration (integration audit, Flow 3 / INT3-04)**: reproduced empirically — calling `handle_play_enhanced` twice for the same `track_id` (2nd call with a new preset/intensity, 1st task still running) leaves the running `asyncio.Task` object identical; no restart. **Worse than 'silently dropped'**: the shared `enhancement_settings` dict IS overwritten, because the write-back at `playback_commands.py:154-155` runs BEFORE the dedup guard at `:192-198`. So `/api/player/enhancement/status`, `/api/processing/parameters` and the UI enhancement panel all report the change as successful while the audio stream keeps rendering the old preset/intensity — the user-visible symptom is a UI that lies, not merely a control that does nothing. Git archaeology: the #3763 fix (closed May 27) was purely frontend (`WebSocketContext.tsx`, `useEnhancementControl.ts`); the track-id-only dedup guard predates it by two months (commit 04d5b816, Mar 23) and was never accounted for. Of the three scenarios that fix named, only toggle-OFF works today (it routes to `play_normal`, which has no dedup guard).
- **Siblings**: `handle_play_normal` lacks dedup entirely; `handle_seek` (line 290) does not dedup either.
- **Suggested Fix**: Include `preset`, `intensity`, and `start_position` in the dedup comparison, or drop the dedup and rely on `_cancel_prior_task`.

---

### BE2-02: `send_pcm_chunk` swallows a failed frame send — a whole content chunk is dropped while the stream still reports `reason: "completed"`

- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_protocol.py:234-259`, `96-114`; consumers `/mnt/data/src/matchering/auralis-web/backend/core/stream_enhanced.py:235-236`, `/mnt/data/src/matchering/auralis-web/backend/core/stream_seek.py:271-272`
- **Status**: NEW
- **Description**: `safe_send`/`safe_send_bytes` convert every send failure into `return False`. `send_pcm_chunk`'s consumer reacts by setting `abort_event`, draining the queue, and `break`ing — then `send_pcm_chunk` returns **normally, with no exception and no return value**. The caller cannot tell a delivered chunk from a dropped one; it unconditionally credits the chunk.
- **Evidence**:
```python
# stream_protocol.py:241-252
            sent: bool = await controller._safe_send(websocket, metadata)
            if not sent:
                abort_event.set()
                while not queue.empty():
                    queue.get_nowait()
                break
            sent = await controller._safe_send_bytes(websocket, pcm_bytes)
            if not sent:
                abort_event.set()
                ...
                break
```
```python
# stream_enhanced.py:235-236
                await controller._stream_processed_chunk(pcm_samples, chunk_idx, processor, websocket)
                delivered_samples += int(pcm_samples.shape[0])
```
`safe_send_bytes` returns `False` not only on disconnect but on the generic `except Exception` branch (line 112-114, "Unexpected error sending WebSocket binary") while `client_state` may still read `CONNECTED` — so the loop's `_is_websocket_connected` guard at `stream_enhanced.py:208` does not break, and the next chunk is sent as if nothing happened.
- **Impact**: Up to `CHUNK_INTERVAL` (10 s) of audio vanishes from the middle of the stream with no `audio_stream_error`, no retry, `delivered_samples` over-counted, and a terminal `audio_stream_end` with `reason="completed"` and the **full** track duration. The client concatenates into `pcmBufferRef` and simply jumps forward. This is the exact class of defect #4659 fixed for the *early-exit* case but left open for the *per-frame* case.
- **Siblings**: `stream_normal.py:304-309` has the identical shape.
- **Suggested Fix**: Have `send_pcm_chunk` return a bool (or raise `ConnectionError`) on abort and have the three loops treat it as a chunk failure (`_send_error` + `stopped_early`) rather than a success.

---

### BE3-08: `StreamlinedCacheWorker` prefetches chunk index `total_chunks` on every track — caches a 10 s all-silence WAV and poisons the LevelManager

- **Severity**: HIGH
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/streamlined_worker.py:231-233`; enabled by the missing bound in `/mnt/data/src/matchering/auralis-web/backend/core/chunked_processor.py:503-591`
- **Status**: NEW
- **Description**:
  `_process_priorities()` computes `next_chunk_idx = current_chunk + 1` and calls
  `_ensure_tier1_chunk()` with it **without ever comparing against
  `status.total_chunks`** (contrast `_build_tier2_cache`, line 354, which is
  correctly bounded by `range(..., status.total_chunks)`). `current_chunk` itself
  comes from the naive `int(position // CHUNK_INTERVAL)` (see BE3-09), which
  already over-counts by one for half of every emitted chunk window, so the
  overflow starts well before the true end of the track.
  `_ensure_tier1_chunk` → `_process_chunk` → `processor.process_chunk_safe(idx)`
  → `ChunkedAudioProcessor.process_chunk()`, which — unlike `get_wav_chunk_path`
  (`chunked_processor.py:731-735`, the #4342 guard) — has **no range check at all**.
- **Evidence**:
  `core/streamlined_worker.py:231-233`
  ```python
  # Priority 1: Ensure next chunk is cached (Tier 1)
  next_chunk_idx = current_chunk + 1
  await self._ensure_tier1_chunk(track, track_id, next_chunk_idx, preset, intensity)
  ```
  Geometry executed against the real `ChunkBoundaryManager` / `ChunkOperations`
  for a 35.0 s track (`content_chunk_count(35.0) == 3`, valid indices 0..2):
  ```
  chunk 3: load[25.0,35.0] core[30.0,35.0] trim=(220500, 0)
     -> trim_context leaves 220500 samples (5 s of REAL audio, source [30,35])
     -> extract_chunk_segment takes [220500 : 220500+441000] of a 220500-sample
        buffer  ==  EMPTY, then pads 441000 samples of silence
     -> extracted len: 441000 (10.0 s), all-zero: True
  chunk 4: load[35.0,35.0] -> empty window -> 100 ms silence -> same 10 s of zeros
  ```
  For a 35 s track this begins at playback position **20 s** (`floor(20/10)+1 = 3 >= 3`),
  i.e. the last 43 % of the track; for longer tracks it is the last 10-15 s.
  It fires on the 1 Hz worker tick, so it repeats every second until the track ends.
- **Impact**:
  - Runs a full DSP pass and writes a **10 s all-silence PCM_16 WAV** to the shared
    `/tmp/auralis_chunks` directory on every track, repeatedly. Those files count
    against `ChunkCacheManager.MAX_CHUNK_DISK_BYTES` (512 MB) and push *real*
    chunks out via the mtime-ordered reaper (`chunk_cache_manager.py:265-316`).
  - The silent chunk is entered into `StreamlinedCacheManager` Tier 1 under a
    normal-looking key.
  - It records `-200 dB` into the shared per-processor `LevelManager` history —
    directly arming BE3-07. The processor survives in `_processor_cache`
    (LRU 8, keyed `(track_id, preset, intensity)`), so a later replay/seek that
    misses cache reuses the poisoned history and writes a corrupted chunk WAV to
    the canonical path (`WAVEncoder.get_chunk_path`, identical filename to the
    one `get_wav_chunk_path` reads back).
  - `ChunkBoundaryManager.trim_context` logs a
    `"start trim clamped to avoid emptying the buffer … DSP may have shrunk the
    chunk unexpectedly"` WARNING every tick, which is a false alarm that will mask
    the real DSP-shrink condition that warning exists to catch.
- **Siblings**: `trigger_immediate_processing()` (`streamlined_worker.py:527-564`)
  is likewise unbounded — it forwards any caller-supplied `chunk_idx` to
  `_process_chunk` with no ceiling.
- **Suggested Fix**:
  1. In `_process_priorities`, clamp: `if next_chunk_idx >= status.total_chunks: skip`
     (the `TrackCacheStatus` is already fetched by `_build_tier2_cache`).
  2. Move the #4342 range guard from `get_wav_chunk_path` down into
     `process_chunk`/`_process_chunk_core` so **all** entry points are protected,
     matching what the #4342 fix comment claims ("every caller is protected").
  3. Make `extract_chunk_segment` raise rather than silently pad when the
     requested window lies entirely past the buffer.

---

### BE4-1: `mode="reference"` processing jobs are guaranteed to fail — `create_job` drops the reference path for every mode except `hybrid`

- **Severity**: HIGH
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:196-197`, `auralis-web/backend/core/processing_engine.py:388-413`, `auralis/core/hybrid_processor.py:283-290`
- **Status**: NEW
- **Description**:
  `POST /api/processing/process` accepts `mode: "reference"` together with a `reference_path`
  (`routers/processing_api.py:61` documents `"adaptive", "reference", "hybrid"` and
  `:176-182` validates the reference path through `validate_file_path`). But
  `ProcessingEngine.create_job()` only persists the reference into the job when the mode is
  *hybrid*. In reference mode the validated path is silently discarded, `_execute_job` takes
  its "fall back to adaptive" branch and calls `processor.process(audio)` with
  `reference=None` — while `_create_processor_config()` has already put the config into
  **reference** mode. `HybridProcessor._process_impl` then matches none of its three
  dispatch arms and raises `ValueError`.
- **Evidence**:
  ```python
  # core/processing_engine.py:195-197  — reference_path is stored for hybrid ONLY
  # Store reference path if hybrid mode
  if mode == "hybrid" and reference_path:
      job.settings["reference_path"] = reference_path
  ```
  ```python
  # core/processing_engine.py:388-413
  if job.mode == "reference" or job.mode == "hybrid":
      reference_path = job.settings.get("reference_path")     # always None for mode="reference"
      if reference_path and Path(reference_path).exists():
          ...
      else:
          # Fall back to adaptive mode if no reference
          result = await asyncio.wait_for(
              asyncio.to_thread(processor.process, audio),      # reference=None
              timeout=timeout,
          )
  ```
  ```python
  # core/processing_engine.py:286-291  — config IS switched to reference mode
  elif job.mode == "reference":
      config.set_processing_mode("reference")
  ```
  ```python
  # auralis/core/hybrid_processor.py:283-290
  if self.config.is_reference_mode() and reference is not None:   # False: reference is None
      return self._process_reference_mode(...)
  elif self.config.is_adaptive_mode():                            # False: mode == "reference"
      ...
  elif self.config.is_hybrid_mode():                              # False
      ...
  else:
      raise ValueError(f"Invalid processing mode: {self.config.adaptive.mode}")
  ```
  `UnifiedConfig.is_adaptive_mode()` is `self.adaptive.mode == "adaptive"`
  (`auralis/core/config/unified_config.py:200-202`), so the comment's "fall back to adaptive"
  is not what happens — the config was never moved back.
- **Impact**:
  Every reference-mastering job fails 100% of the time, even with a perfectly valid reference
  file. `_safe_error_message` maps the `ValueError` to the generic
  `"Invalid audio data or parameters"` (`core/processing_engine.py:61`), so the API reports a
  bad-input error for a backend wiring bug — the user is told their audio is invalid. One of
  the three advertised processing modes is entirely non-functional.
- **Siblings**:
  `mode` is not validated anywhere (`routers/processing_api.py:61` is a bare `str = "adaptive"`),
  so an unknown mode also skips `set_processing_mode()` entirely and silently runs adaptive.
  `mode="hybrid"` *without* a reference has the same "fall back" comment but does reach
  `_process_hybrid_mode(target, None, ...)`, a different (unaudited here) path.
- **Suggested Fix**:
  Store `reference_path` for both `reference` and `hybrid` modes in `create_job`, and make the
  no-reference case in `_execute_job` actually restore adaptive mode on the config (or reject
  the job at submit time with a 422 when `mode="reference"` and no reference is supplied).

---

### BE7-1: Processing timeout hands a still-in-use `HybridProcessor` back to the pool and permanently leaks the executor thread

- **Severity**: HIGH
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/processing_engine.py:404-419`, `:518-529`, `:553-576`; `/mnt/data/src/matchering/auralis-web/backend/core/processor_pool.py:99-135`
- **Status**: NEW
- **Description**:
  `_execute_job` bounds the DSP call with `asyncio.wait_for(asyncio.to_thread(processor.process, audio), timeout=self.processing_timeout)` (300 s default). `wait_for` can only cancel the *asyncio-side* wrapper future — the OS thread running `processor.process` cannot be interrupted and keeps running. `process_job` then treats the `TimeoutError` as a terminal failure and its `finally` block unconditionally calls `self._return_processor(job.mode, config, processor)`, which puts that exact `HybridProcessor` instance back into `ProcessorPool.processors` where the *next* job with the same cache key will pop and use it.
  Two consequences: (a) the orphaned thread and a subsequent job mutate the same processor concurrently (`reset_realtime_eq()` / `reset_dynamics()` / `reset_psychoacoustic_eq()` are called on it at `processing_engine.py:380-382` while the old thread is still inside `process()`), and (b) the thread is never reclaimed, permanently consuming one slot of the event loop's **default** `ThreadPoolExecutor`.
- **Evidence**:
  ```python
  # core/processing_engine.py:416-419
  result = await asyncio.wait_for(
      asyncio.to_thread(processor.process, audio),
      timeout=timeout,
  )
  # core/processing_engine.py:518-525
  except TimeoutError:
      job.status = ProcessingStatus.FAILED
      job.error_message = (f"Processing timed out after {self.processing_timeout:.0f}s")
  # core/processing_engine.py:563-565  (finally, runs for the timeout branch too)
  if processor is not None and config is not None:
      try:
          await self._return_processor(job.mode, config, processor)
  ```
  `ProcessorPool.return_to_cache` simply does `self.processors[key] = processor` (`processor_pool.py:103-105`) with no liveness check, and `get_or_create` pops and returns it to the next caller (`processor_pool.py:88-97`).
  The timeout comment itself states the intent — "Wrap with wait_for so a hung DSP/Rust call cannot hold the semaphore slot indefinitely (fixes #2747)" — i.e. the branch exists precisely for the case where the thread does *not* come back.
- **Impact**:
  The exact failure this timeout was added for (a hung Rust/PyO3 DSP call) produces a shared-mutable-state race between an orphan thread and the next job, so job N+1 can silently produce wrong audio or crash. Because `asyncio.to_thread` uses the *default* executor, repeated timeouts starve every other `to_thread` user in the backend — the streaming track lookups (`stream_enhanced.py:101`), the WAV chunk reads (`stream_normal.py:287`), `validate_file_path`, `queue_enrichment._lookup` — leading to a backend-wide stall that never recovers without a restart.
- **Siblings**:
  Same shape (uncancellable thread behind a `wait_for`) at `core/stream_enhanced.py:126-135` (`ChunkedAudioProcessor` construction, 30 s) and `core/stream_chunk_ops.py` (`CHUNK_PROCESS_TIMEOUT`), and the already-CLOSED `#4377` (FingerprintGenerator hung DSP thread). Only the `processing_engine` case additionally *recycles* the object into a shared pool.
- **Suggested Fix**:
  On the `TimeoutError` branch, do not return the processor to the pool — drop it and call `processor.close()` instead (or mark it poisoned so `return_to_cache` discards it). Longer term, thread the existing per-job `threading.Event` cancel token (`self._cancel_events`, already used for the FFmpeg decode) into `HybridProcessor.process` so the DSP loop can bail cooperatively, and run job DSP on a dedicated bounded executor rather than the shared default one.

---

### BE8-06: Every enhanced chunk of an M4A/AAC/WMA track triggers a **full-file FFmpeg decode** — the #4497 bounded-decode fix stopped at metadata


- **Severity**: HIGH
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:106-141`, reached from `/mnt/data/src/matchering/auralis-web/backend/core/chunked_processor.py:331-356` and `/mnt/data/src/matchering/auralis-web/backend/core/streamlined_worker.py:445-457`
- **Status**: NEW (sibling of #4497 [CLOSED], which fixed only `_load_metadata`; **not** a regression of it — the metadata path is still fixed)
- **Description**:
  `ChunkOperations.load_chunk_from_file()` is the single loader for every chunk on
  the enhanced/processing path. It opens the **original** track file with
  `sf.SoundFile(filepath)`. libsndfile cannot open `.m4a`, `.aac`, or `.wma` at all
  (verified in this venv: libsndfile 1.2.2, `sf.available_formats()` =
  `AIFF, AU, AVR, CAF, FLAC, HTK, IRCAM, MAT4, MAT5, MP3, MPC2K, NIST, OGG, PAF,
  PVF, RAW, RF64, SD2, SDS, SVX, VOC, W64, WAV, WAVEX, WVE, XI` — no MPEG-4/ADTS/ASF).
  The `except` clause then falls back to a **whole-file decode**, per chunk.
- **Evidence**:
  `core/chunk_operations.py:106-126`
  ```python
          # Load audio segment
          try:
              import soundfile as sf
              ...
              with sf.SoundFile(filepath) as f:
                  f.seek(start_frame)
                  audio = f.read(frames_to_read)
                  ...
          except Exception as e:
              logger.warning(f"Soundfile loading failed, using fallback: {e}")
              # Fallback: load entire audio and slice
              from auralis.io.unified_loader import load_audio
              full_audio, _ = load_audio(filepath, target_sample_rate=sample_rate)
  ```
  The filepath is never pre-converted. `core/streamlined_worker.py:445-457` builds the
  processor straight off the library row:
  ```python
                              processor = await asyncio.to_thread(
                                  ChunkedAudioProcessor,
                                  track_id=track_id,
                                  filepath=track.filepath,
  ```
  and `chunked_processor.load_chunk()` passes `filepath=self.filepath` unchanged
  (`core/chunked_processor.py:347-356`).
  `auralis/io/unified_loader.py:86-89` routes `.m4a/.aac/.wma/.ogg/.opus/.mp3` to
  `load_with_ffmpeg()` — a subprocess spawn + temp-WAV write + full read, with **no
  memoisation of any kind** (`load_audio` has no cache; see
  `/mnt/data/src/matchering/auralis/io/unified_loader.py:32-140`).
  Contrast the *normal* streaming path, which does exactly the right thing once
  per stream (`core/stream_normal.py:122-138`): it converts FFmpeg formats to a temp
  WAV **once**, then chunk-reads that WAV.
- **Impact**:
  A 10-minute `.m4a` produces `content_chunk_count(600) ≈ 60` chunks. Each chunk
  currently costs one FFmpeg process spawn, a full decode of the whole track, a
  temp-WAV write/read, and a ~200 MB float64 allocation — to extract 25 s of audio.
  That is roughly a 60x CPU/IO amplification and a per-chunk ~200 MB transient
  allocation on a path that runs concurrently with playback (up to
  `MAX_CONCURRENT_STREAMS = 10`). It also converts a bounded-memory design into an
  unbounded one under the exact conditions #2185's semaphore was added to prevent.
  `.mp3`, `.flac`, `.wav`, `.ogg` are unaffected (libsndfile handles them), which is
  likely why this went unnoticed on a test library.
- **Siblings**:
  - `core/chunked_processor.py:539-541` and `:691` load whole cached-chunk files —
    correct, those files are one chunk each.
  - `core/chunked_processor.py:289-303` — the `_load_metadata` full-decode fallback
    is now genuinely last-resort (#4497 fix verified still in place).
  - `services/recommendation_service.py:82,142` and `routers/enhancement.py:475`
    construct `ChunkedAudioProcessor` off raw library paths too, so they inherit
    the same amplification.
- **Suggested Fix**:
  Hoist `stream_normal.py`'s once-per-track temp-WAV conversion into
  `ChunkedAudioProcessor.__init__` (guarded by `Path(filepath).suffix.lower() in
  FFMPEG_FORMATS`), store the converted path as the chunk-read source, and delete
  it when the processor is evicted. Failing that, make the `except` branch in
  `load_chunk_from_file` raise instead of silently amplifying — a per-chunk
  full-file decode should never be a silent fallback.

---

### BE9-01: The backend pytest CI gate has never passed — `pytest-baseline.json` was never committed

- **Severity**: HIGH
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/.github/workflows/backend-tests.yml:100-102`, `/mnt/data/src/matchering/scripts/check_pytest_baseline.py:100-110`
- **Status**: NEW
- **Description**: `.github/workflows/backend-tests.yml` runs pytest (always exit 0 via `|| true`) and then delegates the pass/fail decision entirely to `python scripts/check_pytest_baseline.py pytest-results.xml`. That script reads `REPO_ROOT / "pytest-baseline.json"` and, on `FileNotFoundError`, calls `_die(...)` → `sys.exit(1)`. **The file does not exist in the working tree and has never been committed** (`git log -- pytest-baseline.json` is empty; `git ls-files | grep baseline` returns only the frontend baseline and the script itself). So the job's deciding step fails on every single run.
- **Evidence**:
  - `scripts/check_pytest_baseline.py:100-110`
    ```python
    def load_baseline() -> set[str]:
        try:
            payload = json.loads(BASELINE_PATH.read_text())
        except FileNotFoundError:
            _die(
                f"No baseline at {BASELINE_PATH}.\n"
                "  Generate one with: python scripts/check_pytest_baseline.py <junit.xml> --update"
            )
    ```
  - `gh run list --workflow=backend-tests.yml --limit 8` → **8 of 8 `completed failure`**, every run on `master`.
  - `gh run view 30480450048 --log-failed` (latest, the commit whose subject is literally "fix: run backend CI on Python 3.14 so the suite can collect at all"):
    ```
    ✖ No baseline at /home/runner/work/Auralis/Auralis/pytest-baseline.json.
      Generate one with: python scripts/check_pytest_baseline.py <junit.xml> --update
    ##[error]Process completed with exit code 1.
    ```
  - The workflow's own `paths:` trigger list includes `pytest-baseline.json` — a file that does not exist.
- **Impact**: The single mechanism that would catch a *new* backend test regression is inoperative. Worse than absent: it is a permanently-red required-looking check, which trains reviewers to ignore the Backend Tests status entirely. The ratchet cannot ratchet — the baseline can never shrink because it was never established. Every one of the 341 current failures, and any new one added tomorrow, is indistinguishable to CI.
- **Siblings**: The frontend counterpart `auralis-web/frontend/test-baseline.json` **is** committed, so this is a one-sided omission, not a design choice. Note the workflow was landed by `43c983ad` and last touched by `9e03236c`, meaning at least two commits went in without anyone observing the job go green.
- **Suggested Fix**: Generate and commit `pytest-baseline.json` from a full CI run (`--update`), or make `load_baseline()` treat a missing baseline as an empty set with a loud warning so the gate degrades to "fail on any failure" rather than "fail always". Prefer the former given the 341-failure reality.

---


## Medium severity (31)

### BE1-3: `POST`/`DELETE /api/library/tracks/{track_id}/favorite` return 200 for a nonexistent track and for a failed write

- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/tracks.py:107-131`; repository at `/mnt/data/src/matchering/auralis/library/repositories/track_repository.py:622-635`
- **Status**: NEW
- **Description**: Both handlers call `repos.tracks.set_favorite(track_id, bool)` and unconditionally
  return a success body. `set_favorite` is declared `-> None`: when no row matches `track_id` it simply
  does nothing, and its `except Exception` branch rolls back, logs, and returns normally. There is no
  return value for the route to inspect, so the route has no way to distinguish "favorited",
  "track does not exist", and "the commit failed". Every other single-entity mutation in the codebase
  (`playlists.update`/`delete`/`remove_track`, `albums.delete_artwork`, `tracks.update_metadata`) returns
  a truthy/falsy result and the corresponding route raises `NotFoundError` on falsy — these two routes
  are the outlier.
- **Evidence**:
```python
# routers/tracks.py:107-118
    @router.post("/api/library/tracks/{track_id}/favorite")
    async def set_track_favorite(track_id: int) -> dict[str, Any]:
        """Mark track as favorite."""
        try:
            repos = require_repository_factory(get_repository_factory)
            await asyncio.to_thread(repos.tracks.set_favorite, track_id, True)
            logger.info(f"Track {track_id} marked as favorite")
            return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
```
```python
# auralis/library/repositories/track_repository.py:622-635
    def set_favorite(self, track_id: int, favorite: bool = True) -> None:
        ...
            if track:                      # silently no-ops when the track is gone
                track.favorite = favorite
                session.commit()
        except Exception as e:
            session.rollback()
            error(f"Failed to set favorite: {e}")   # swallowed — caller never learns
```
- **Impact**: `useBatchOperations` (frontend) fires `del(ENDPOINTS.TRACK_FAVORITE(trackId))` per selected
  track and treats 200 as success. If a track was deleted by a concurrent library scan/reset, or if the
  SQLite write fails (locked DB during a scan is the realistic case), the UI keeps the heart toggled and
  the state silently reverts on the next `GET /api/library/tracks/favorites`. A batch favorite over a
  large selection can report full success while having persisted nothing.
- **Siblings**: `set_favorite`'s swallow-and-log is the only mutation in `TrackRepository` that neither
  returns a status nor re-raises; `update_metadata` (:835-838) re-raises, `update` (:797-800) returns
  `None`.
- **Suggested Fix**: Make `set_favorite` return `bool` (False when no row matched) and re-raise on
  commit failure, then have both routes raise `NotFoundError("Track", track_id)` on a falsy result.

---

### BE1-4: `PUT /api/settings` sets `scan_folders` with no path validation and no allowed-directory registration, unlike the dedicated scan-folder route

- **Severity**: MEDIUM
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/settings.py:63, 183-198` vs `:200-214`
- **Status**: NEW
- **Description**: `POST /api/settings/scan-folders` does two things before persisting: it runs the path
  through `validate_user_chosen_directory()` (rejects `..` segments, non-existent paths, non-directories,
  unreadable directories) and then calls `register_allowed_directory(validated)` so that
  `validate_file_path()` will subsequently accept files underneath it. `PUT /api/settings` can write the
  *same* `scan_folders` column — `SettingsUpdateRequest.scan_folders: list[str] | None` has no validator,
  and `SettingsRepository.update_settings` special-cases the key and JSON-dumps the list verbatim — but
  performs **neither** step. The two write paths to one column therefore have completely different
  contracts.
- **Evidence**:
```python
# routers/settings.py:63  — no field_validator, unlike LibraryScanRequest.directories
    scan_folders: list[str] | None = None

# routers/settings.py:195-198  — straight through to the repository
        payload = updates.model_dump(exclude_unset=True)
        settings = await asyncio.to_thread(_repo().update_settings, payload)
        await _notify_scanner()
```
```python
# routers/settings.py:206-213  — the validated sibling path
        try:
            validated = validate_user_chosen_directory(body.folder.strip())
        except PathValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        settings = await asyncio.to_thread(_repo().add_scan_folder, str(validated))
        register_allowed_directory(validated)
```
```python
# auralis/library/repositories/settings_repository.py:63-68
            if 'scan_folders' in updates:
                if isinstance(updates['scan_folders'], list):
                    settings.scan_folders = json.dumps(updates['scan_folders'])
```
- **Impact**: Two concrete effects. (1) Correctness: `_notify_scanner()` makes `LibraryAutoScanner`
  reload immediately and start walking the new folders, but because `register_allowed_directory` was
  never called, `validate_file_path()` rejects everything underneath them — so the tracks get imported
  and then `GET/PUT /api/metadata/tracks/{id}`, `POST /api/processing/process` and the lyrics path all
  return 400 "Invalid track filepath" for those tracks until the backend is restarted (startup re-reads
  `scan_folders` from the DB and registers them). (2) Robustness: an unvalidated entry such as `""`,
  `"/"`, a file path, or a path containing `..` is persisted and handed to the scanner, where
  `validate_user_chosen_directory` would have rejected it with a clean 400. Localhost-only binding keeps
  this out of remote-attacker territory, so it is scoped as a correctness/consistency defect rather than
  a security one.
- **Siblings**: `LibraryScanRequest.directories` (`schemas.py:176-189`) is the model that gets this
  right — a `field_validator` that runs `validate_user_chosen_directory` per entry. `file_types` on the
  same `PUT` is likewise unconstrained but harmless.
- **Suggested Fix**: Add the same `field_validator` to `SettingsUpdateRequest.scan_folders`, and have
  `update_settings` on that key perform the `unregister`/`register_allowed_directory` diff so the
  in-session allowlist tracks the persisted list.

---

### BE2-03: The `audio_chunk_meta` + binary PCM pair is not atomic — a half-sent pair permanently desyncs the client's frame pairing

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_protocol.py:234-257`; client pairing at `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/websocket/websocketConnectionCore.ts:126-207`
- **Status**: NEW
- **Description**: The wire protocol is a JSON text frame immediately followed by its binary frame; the client stores the meta in `connState.pendingMeta` and clears it only when a binary frame arrives. If the meta send succeeds and the binary send fails (BE2-02's second `if not sent` branch), the client is left holding a stale `pendingMeta` that will be fused with the **next** chunk's PCM. Nothing in the protocol re-syncs it: there is no per-pair nonce and `pendingMeta` is never invalidated by a subsequent text frame.
- **Evidence**:
```ts
// websocketConnectionCore.ts:133-149
    if (event.data instanceof ArrayBuffer) {
      if (connState.pendingMeta) {
        const combined: AudioChunkMessage = {
          type: 'audio_chunk',
          data: { ...connState.pendingMeta.data, pcm_binary: event.data },
        };
        connState.pendingMeta = null;
        dispatch(combined);
```
Every subsequent chunk then carries the previous frame's `seq`, `chunk_index`, `frame_index` and `sample_count`. `decodeAudioChunkMessage` validates `samples.length !== data.sample_count` (`/mnt/data/src/matchering/auralis-web/frontend/src/utils/audio/pcmDecoding.ts:314-316`) and throws — so the stream then fails loudly *on the wrong chunk*, or, when the counts happen to match (all full 76800-sample frames do), it silently mis-attributes epoch/track_id/chunk_index for the rest of the stream, defeating the #4563 epoch guard and the #4434 track guard.
- **Impact**: Mis-attributed chunk metadata; the #4563 stale-epoch discard and #4434 stale-track discard can drop *good* frames or admit *stale* ones after a single dropped binary frame.
- **Siblings**: The Blob path (`websocketConnectionCore.ts:153-175`) has the same single-slot assumption.
- **Suggested Fix**: On a failed binary send, emit a `audio_chunk_meta_abort`-style frame (or reuse `audio_stream_error`) that clears `pendingMeta`; or move `seq` into the binary frame header so pairing is self-describing.

---

### BE2-04: There is no transport-level backpressure — `_SEND_QUEUE_MAXSIZE` and `BROADCAST_SEND_TIMEOUT` are both inert

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_protocol.py:43-47,168-174`; `/mnt/data/src/matchering/auralis-web/backend/config/globals.py:59-62,146-166`; server selected at `/mnt/data/src/matchering/auralis-web/backend/main.py:235-240`
- **Status**: NEW
- **Description**: `main.py` calls `uvicorn.run(app, host="127.0.0.1", port=8765)` with the default `ws="auto"`. With `websockets` installed (16.0 here) `auto.py` unconditionally selects `WebSocketsSansIOProtocol`. That protocol creates `self.writable = asyncio.Event()`, **sets it once at construction, and never clears it** — it implements neither `pause_writing` nor `resume_writing`, so `asyncio`'s transport high-water mark has no effect.
- **Evidence** (`.venv/.../uvicorn/protocols/websockets/websockets_sansio_impl.py`):
```python
 96        self.writable = asyncio.Event()
 97        self.writable.set()
...
372    async def send(self, message: ASGISendEvent) -> None:
373        await self.writable.wait()
...
441                    output = self.conn.data_to_send()
442                    self.transport.write(b"".join(output))
```
`grep -n "pause_writing|resume_writing|drain"` over that file returns **nothing**. Therefore `websocket.send_bytes()` never suspends. Two guards depend on it suspending and are dead:
```python
# stream_protocol.py:168-174 — "backpressure for issue #2122"
    queue: asyncio.Queue[...] = asyncio.Queue(maxsize=_SEND_QUEUE_MAXSIZE)
```
```python
# globals.py:157-160 — the #4581 stall guard
                await asyncio.wait_for(
                    connection.send_text(message_json),
                    timeout=BROADCAST_SEND_TIMEOUT,
                )
```
The producer never blocks on the bounded queue (the consumer always drains instantly), and `broadcast()`'s 2 s timeout can never fire, so its stale-connection eviction path is unreachable.
- **Impact**: The only real flow control is the cooperative client `buffer_full`/`buffer_ready` signal (`useAudioStreamingCore.ts:286,289`), checked only at the *top* of each chunk iteration (`stream_enhanced.py:204-206`). Against a half-open TCP peer (suspended renderer, sleeping laptop) no `buffer_full` ever arrives and `client_state` stays `CONNECTED`, so the backend pushes chunks at DSP speed into an unbounded transport write buffer (~3.5 MB per 10 s stereo chunk) for the ~30-60 s until the heartbeat evicts it — tens to ~100 MB of RSS growth. The comments claiming otherwise are misleading to future maintainers.
- **Siblings**: `ConnectionManager.broadcast` stale-eviction (#4581's fix) is inert for the same reason.
- **Suggested Fix**: Either pin `ws="wsproto"`, or add an explicit application-level ack/credit, or at minimum correct the comments and stop relying on `wait_for` around `send_text` as a stall guard.

---

### BE2-05: A rate-limited `pong` is dropped silently, causing a spurious heartbeat force-close

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/system.py:338-343`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/connection.py:46-62`; `/mnt/data/src/matchering/auralis-web/backend/websocket/websocket_protocol.py:35-53,77-83`
- **Status**: NEW (not #4406 — that was "client never sends pong at all", since fixed)
- **Description**: The rate-limit check runs **before** dispatch and applies uniformly to every inbound type, including the protocol-critical `pong`. A dropped `pong` never reaches `heartbeat.mark_pong`, so `pending_pongs[connection_id]` stays armed and the next heartbeat tick force-closes the socket.
- **Evidence**:
```python
# routers/system.py:338-343
                allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
                if not allowed:
                    logger.warning(...)
                    await send_error_response(websocket, "rate_limit_exceeded", error_msg)
                    continue      # ← pong never dispatched
```
```python
# ws_handlers/connection.py:51-55
            await asyncio.sleep(heartbeat.interval_seconds)
            if heartbeat.is_stale(connection_id):
                logger.warning(f"WebSocket {connection_id} stale — closing")
                await websocket.close(code=1001, reason="Heartbeat timeout")
```
`is_stale` returns True whenever `pending_pongs` holds an entry older than `timeout_seconds` (10 s), and the ping interval is 30 s — so one dropped pong guarantees a close 30 s later. The limiter is 10 msg/s per connection and 30 msg/s per IP (`websocket_security.py:64-70,121-132`); a seek-bar drag or a burst of `buffer_full`/`buffer_ready` toggles can exceed that inside the one-second window that contains the server's ping.
- **Impact**: Spurious disconnect during exactly the interaction (scrubbing) most likely to burst messages. The client then reconnects and `replayQueueAndResume` re-issues the stream, producing an audible re-buffer.
- **Siblings**: `handle_ping` (`messages.py:29-30`) replies `pong` but never calls `mark_alive`, so client-initiated pings do not count as liveness either.
- **Suggested Fix**: Exempt `ping`/`pong`/`heartbeat` from the rate limiter (parse `type` before the check), or have `check_rate_limit` return a "throttle, don't drop" result for control frames.

---

### BE2-06: Per-chunk error recovery silently deletes 10 s of audio and still terminates with `reason: "completed"`

- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_enhanced.py:255-290,309-318`; `/mnt/data/src/matchering/auralis-web/backend/core/stream_seek.py:287-312,330-338`; `/mnt/data/src/matchering/auralis-web/backend/core/stream_normal.py:316-331`
- **Status**: NEW
- **Description**: The `#3190` "skip failed chunk and continue" branch sends an `audio_stream_error` with a `recovery_position` and then `continue`s. Because the loop completes, `stopped_early` stays `False` and the terminal message is the success-shaped one reporting the **full** track duration and `int(processor.duration * processor.sample_rate)` samples — even though one or more chunks were never delivered.
- **Evidence**:
```python
# stream_enhanced.py:283-290
                await controller._send_error(
                    websocket, track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=recovery_position,
                )
                # Skip failed chunk and continue with remaining chunks (#3190)
                continue
...
# stream_enhanced.py:310-318 (stopped_early is still False here)
            await controller._send_stream_end(
                websocket, track_id=track_id,
                total_samples=int(processor.duration * processor.sample_rate),
                duration=processor.duration, reason="completed",
            )
```
The client-side counterpart never acts on the gap: `recovery_position` has no consumer (already tracked as #4655 OPEN), and `useAudioStreamingCore`'s out-of-sequence guard only trips on `incomingChunkIndex < lastChunk - 1` — a forward skip of exactly one chunk passes through.
- **Impact**: The user hears a 10 s jump; `total_samples`/`duration` in `audio_stream_end` are wrong; anything keying off `reason === 'completed'` (auto-advance, scrobbling) treats a lossy stream as a clean one. The #4659 accounting was applied to the early-exit path but not to the skip-and-continue path.
- **Siblings**: `stream_normal.py:340-347` explicitly asserts in a comment that it has "no early-break-with-partial-content case" and hardcodes `reason="completed"` — but its `except Exception … continue` at 316-331 is exactly that case.
- **Suggested Fix**: Track skipped chunks and report `reason="stopped"` (or a new `"degraded"`) with the true delivered sample count.

> **Merged duplicate — BE7-5.** Independently found by Dimension 7 on the **processing-error** trigger path (Dimension 2 found it on the **send-failure** path). Two independent discoveries of one defect; Dimension 7 confirms it affects all three stream paths. Dimension 7's write-up follows.

<details><summary>BE7-5 (merged): A stream in which every chunk fails still ends with `reason: "completed"` and the FULL track duration — the `#4659` fix does not cover the error-`continue` branch</summary>

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_enhanced.py:255-318`; `/mnt/data/src/matchering/auralis-web/backend/core/stream_seek.py:287-337`; `/mnt/data/src/matchering/auralis-web/backend/core/stream_normal.py:316-347`
- **Status**: NEW (uncovered branch of the CLOSED `#4659` fix, not a regression of the branches it did fix)
- **Description**:
  `#4659` added a `stopped_early` flag so a truncated stream reports `reason: "stopped"` with the bytes actually delivered. The flag is set on all four `break` paths (enhancement toggled off, WS disconnected, `ConnectionError` from look-ahead, `ConnectionError` in the body). It is **not** set on the per-chunk failure path, which logs, emits an `audio_stream_error`, and `continue`s. If chunk processing fails for every chunk — a file deleted or truncated mid-playback, a corrupt region, a DSP crash — the loop runs to completion having delivered nothing, `stopped_early` stays `False`, and the terminal frame is the success-shaped one built from `processor.duration`.
- **Evidence**:
  ```python
  # core/stream_enhanced.py:255-290
  except Exception as chunk_error:
      ...
      await controller._send_error(websocket, track_id, f"Failed to process audio chunk {chunk_idx}", recovery_position=recovery_position)
      # Skip failed chunk and continue with remaining chunks (#3190)
      continue          # <-- stopped_early is NOT set, delivered_samples not incremented
  ...
  # core/stream_enhanced.py:309-318
  else:
      logger.info(f"Audio stream complete: track={track_id}")
      await controller._send_stream_end(
          websocket, track_id=track_id,
          total_samples=int(processor.duration * processor.sample_rate),
          duration=processor.duration,
          reason="completed",
      )
  ```
  `stream_normal.py` is worse: its `#4659` comment asserts the case cannot arise — "this loop has no early-break-with-partial-content case — both of its breaks are disconnect-driven" (`stream_normal.py:334-339`) — and then unconditionally sends `reason="completed"` with `total_samples=total_frames, duration=duration`. The `continue` at `stream_normal.py:331` is exactly the missing case.
- **Impact**:
  Per the `#4659` rationale, clients treat `audio_stream_end` with `reason: "completed"` as "track finished" — auto-advance, scrobble, progress completion. A track that delivered zero audio therefore counts as fully played and auto-advances, while the user hears silence. The client did receive `audio_stream_error` frames, but the terminal frame contradicts them and arrives last.
- **Siblings**: All three streaming entry points share the shape; `stream_seek.py:287+` has the identical `continue`.
- **Suggested Fix**:
  Set `stopped_early = True` in the chunk-failure handler (or track a `failed_chunks` count and choose the reason from `delivered_samples == 0` / `failed_chunks > 0`), and add a third `reason` value such as `"errored"` so the client can distinguish "stopped by the user/backend" from "aborted by failures". Remove the now-false comment in `stream_normal.py:334-339`.

</details>

---

### BE3-09: Position→chunk mapping still uses the *core* timeline in the cache manager and the enhancement pre-fetcher (the #4557 fix was not propagated)

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/cache/manager.py:176-179`; `/mnt/data/src/matchering/auralis-web/backend/routers/enhancement.py:154-157`
- **Status**: NEW
- **Description**:
  `chunk_boundaries.py` documents (lines 46-63) that chunk 0 emits `[0,15)` and
  chunk N emits `[N*10+5, N*10+15)`, and provides `chunk_for_position()` as the
  single mapping from a source-time position onto the chunk that actually emits
  it. `stream_seek.py:166` uses it. Two other position→chunk derivations still
  use the pre-#4557 core-timeline formula `floor(position / CHUNK_INTERVAL)`,
  which is **one too high for the first half of every emitted chunk window**
  (`p ∈ [20,25) → naive 2, correct 1`; `p ∈ [30,35) → naive 3, correct 2`; …).
- **Evidence**:
  `cache/manager.py:176-179`
  ```python
  def _get_current_chunk(self, position: float) -> int:
      """Calculate chunk index from playback position.
      Uses CHUNK_INTERVAL (10s) since chunks start every 10s."""
      return int(position // CHUNK_INTERVAL)
  ```
  `routers/enhancement.py:154-157`
  ```python
  # Use CHUNK_INTERVAL (not CHUNK_DURATION) to match ChunkedAudioProcessor
  # indexing — chunks start every CHUNK_INTERVAL seconds (fixes #2607).
  current_chunk_idx = int(current_time / CHUNK_INTERVAL)
  chunks_to_process = [current_chunk_idx + i for i in range(1, 4)]  # Next 3 chunks
  ```
- **Impact**:
  - `_preprocess_upcoming_chunks` exists specifically to "prevent audio stopping
    while waiting for on-demand processing" when enhancement is toggled on
    mid-playback. For roughly half of all positions it warms chunks *2, 3, 4*
    ahead and **skips the immediately-next chunk** — i.e. it misses precisely the
    chunk whose absence causes the stall it was written to prevent.
  - `_get_current_chunk` feeds `PlaybackSnapshot.chunk_idx`, which drives Tier-1
    warming and the `add_chunk` "auto" tier decision (`cache/manager.py:349-354`),
    so the hot tier is systematically one chunk ahead of the live position and the
    genuinely-current chunk is demoted to Tier 2.
  - It is also the direct cause of BE3-08 firing at 57 % of a short track rather
    than at its very end.
- **Siblings**: `services/audio_content_predictor.py:210-216` uses
  `start_sec = chunk_idx * chunk_interval` for its analysis window — same core-timeline
  assumption, but there it is a self-consistent analysis grid, not a mapping from a
  playback position, so it is not affected.
- **Suggested Fix**: replace both with
  `chunk_for_position(position, total_chunks)[0]`, importing from
  `core.chunk_boundaries`. Add a lint/regression test asserting no
  `// CHUNK_INTERVAL` or `/ CHUNK_INTERVAL` position→index derivation survives
  outside `chunk_boundaries.py` (the existing
  `tests/backend/test_enhanced_seek_accuracy.py:167` source-grep guard covers only
  `stream_seek.py`).

---

### BE3-10: `process_chunk()` never consults the on-disk WAV cache, so the disk tier is write-only for the streaming path

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunked_processor.py:528-591` vs `:739-799`
- **Status**: NEW
- **Description**:
  `get_wav_chunk_path()` implements a two-level lookup: the in-memory
  `_cache_manager` dict **and** an on-disk `wav_chunk_path.exists() +
  is_wav_complete()` check (lines 756-764). `process_chunk()` — the method the
  live enhanced stream actually uses, via `process_chunk_safe` →
  `stream_chunk_ops.process_chunk_only` — checks **only** the in-memory dict
  (line 532) and then unconditionally re-runs the full DSP, finally overwriting
  the very file it declined to read (line 575, same `WAVEncoder.get_chunk_path`
  filename).
  Every `ChunkedAudioProcessor` on the streaming path is constructed with the
  default `chunk_cache=None → {}` (`chunked_processor.py:155`; `stream_enhanced.py:126-135`
  passes no cache), and `AudioStreamController` gets a fresh `SimpleChunkCache`
  per stream (`audio_stream_controller.py:183`; see the #3513 note at
  `stream_enhanced.py:243-246`). So both memory tiers start empty on every play.
- **Evidence**:
  `chunked_processor.py:528-541` — the entire cache check:
  ```python
  cache_key = ChunkCacheManager.get_chunk_cache_key(...)
  cached_path = self._cache_manager.get_cached_chunk_path(cache_key)
  if cached_path is not None:
      ...
  logger.info(f"Processing chunk {chunk_index}/{self.total_chunks} ...")
  ```
  No `Path.exists()` / `is_wav_complete()` branch, unlike lines 756-764.
- **Impact**: replaying a track re-runs the complete DSP pipeline for every chunk
  even though byte-identical, atomically-written, signature-and-preset-keyed WAVs
  are sitting on disk. The 512 MB on-disk chunk cache, its reaper, its atomicity
  work (#4576) and its truncation gate are all maintained for a tier that the
  dominant consumer never reads. Also asymmetric with the `_chunk_`/`_wav_` cache
  keys, which map to the *same* file — a hit under one key is invisible under the other.
- **Siblings**: `ChunkCacheManager.get_chunk_cache_key` and `get_wav_cache_key`
  (`chunk_cache_manager.py:52-111`) produce two different keys for one file, which
  is what allows the two methods to diverge silently.
- **Suggested Fix**: hoist the disk-existence + `is_wav_complete` check out of
  `get_wav_chunk_path` into a shared `_lookup_cached_chunk(chunk_index)` used by
  both, and collapse the `_chunk_`/`_wav_` key pair to one key since they address
  the same artifact.

---

### BE3-11: Tier-2 size accounting assumes every chunk is `CHUNK_DURATION` long (1.5× over), and the Tier-2 budget cannot actually evict

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/cache/manager.py:45-58, 365-372, 401-437`
- **Status**: NEW (the float32→PCM_16 half of this was #4238 and is correctly fixed; the duration factor is not)
- **Description**:
  Two independent defects in the same accounting:
  1. `CHUNK_SIZE_MB` is derived from `CHUNK_DURATION` (15 s), but only chunk 0
     emits 15 s. `ChunkOperations.extract_chunk_segment` emits exactly
     `CHUNK_INTERVAL` (10 s) for every regular chunk and a short remainder for the
     last one. So every cached chunk except the first is over-accounted by 50 %
     (2.52 MB assumed vs 1.68 MB actual at the nominal 44.1 kHz stereo PCM_16 baseline).
  2. `_evict_tier2_lru()` protects `self.current_track_id` and returns without
     evicting anything when it is the only track present (lines 419-420) — while
     `add_chunk` inserts the new entry regardless (line 371). For a single long
     track the 240 MB budget is therefore never enforced at all.
- **Evidence**:
  `cache/manager.py:48-50`
  ```python
  CHUNK_SIZE_MB = (
      _NOMINAL_CHANNELS * _NOMINAL_SAMPLE_RATE * CHUNK_DURATION * _PCM16_BYTES_PER_SAMPLE
  ) / (1024 * 1024)
  ```
  `cache/manager.py:365-372`
  ```python
  else:  # tier2
      tier2_size_mb = len(self.tier2_cache) * CHUNK_SIZE_MB
      if tier2_size_mb >= TIER2_MAX_SIZE_MB:
          await self._evict_tier2_lru()      # may be a no-op
      self.tier2_cache[cache_key] = chunk    # inserted either way
  ```
  `CachedChunk` already holds `chunk_path`, so the real size is available as
  `chunk_path.stat().st_size` — no estimate is needed.
- **Impact**: `GET /api/cache/*` reports Tier-1/Tier-2/total MB that are ~50 %
  high (`cache/monitoring.py:116-118`, `routers/cache_streamlined.py:194-198`),
  and `CacheMonitor`'s 250/260 MB alert thresholds fire on phantom usage. In the
  other direction, a single long track's Tier-2 map grows without bound. Actual
  disk is still bounded by `ChunkCacheManager`'s independent 512 MB reaper, so
  this is accounting/alerting rather than resource exhaustion.
- **Siblings**: `TIER2_MAX_TRACKS = 2` (`cache/manager.py:57`) is exported through
  `cache/__init__.py:29,53` and never read — the "keep last 2 tracks" policy the
  class docstring advertises is not implemented.
- **Suggested Fix**: sum real `st_size` values (cache them on `CachedChunk` at
  insert), and make `_evict_tier2_lru` fall back to per-chunk LRU eviction within
  the current track once no other track is evictable.

---

### BE3-12: Chunk DSP runs at float64 on the primary load path and float32 on every fallback — inside the same function

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:107-154`
- **Status**: NEW
- **Description**:
  `load_chunk_from_file` reads via `sf.SoundFile.read(frames_to_read)` with no
  `dtype=` argument. `soundfile`'s default is `'float64'`, verified in this venv:
  ```
  SoundFile.read() dtype: float64 (44100, 2)
  load_audio      dtype: float32 (88200, 2) 44100
  ```
  So the same function returns **float64** on the normal path (line 115),
  **float32** from `load_audio` on the FFmpeg/exception fallback (line 126), and
  explicit **float32** zeros on both silence paths (lines 103, 139, 151).
- **Evidence**: `core/chunk_operations.py:113-119`
  ```python
  with sf.SoundFile(filepath) as f:
      f.seek(start_frame)
      audio = f.read(frames_to_read)      # dtype defaults to float64
  ```
- **Impact**:
  - Every chunk of every natively-decodable file (WAV/FLAC/AIFF/…, plus MP3 via
    modern libsndfile) is DSP-processed at double precision: a 25 s stereo chunk
    with context is 17.6 MB instead of 8.8 MB, doubling both the working set and
    the bandwidth of the whole pipeline for a final PCM_16 output.
  - `SimpleChunkCache` accounts `audio.nbytes`, so the 512 MB in-memory budget
    holds half as many chunks as intended.
  - dtype can *flip mid-track* if one chunk falls back to `load_audio` (e.g. a
    transient seek/read failure), which then flips
    `LevelManager._gain_envelope`'s envelope dtype (`level_manager.py:104-107`)
    and `extract_chunk_segment`'s padding dtype (`chunk_operations.py:268`) with
    it. Both correctly follow `chunk.dtype`, so nothing breaks — but the
    inconsistency defeats the deliberate float32-preservation work of #3831/#4125/#4134.
- **Siblings**: `chunked_processor.py:495` correctly derives the fallback dtype
  from `audio_chunk.dtype`, which only works because the loader's dtype is
  whatever it happens to be.
- **Suggested Fix**: pass `dtype='float32'` to `f.read(...)` so the primary path
  matches `load_audio` and the declared engine dtype.

> **Merged duplicate — BE8-07.** Independently found by Dimension 8 with an added memory-bandwidth quantification. Dimension 8's write-up follows.

<details><summary>BE8-07 (merged): Chunk reads use soundfile's default `float64`, doubling audio memory and DSP bandwidth on the enhanced path</summary>

- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:113-115`
- **Status**: NEW
- **Description**:
  `SoundFile.read()` defaults to `dtype='float64'`. The enhanced path's chunk read
  omits the `dtype=` argument, so every processing chunk is materialised at 8
  bytes/sample and stays float64 through the entire `AudioProcessingPipeline`.
  The normal streaming path passes `dtype='float32'` explicitly, so the two paths
  disagree on the audio dtype for the same file.
- **Evidence**:
  `core/chunk_operations.py:113-115`
  ```python
              with sf.SoundFile(filepath) as f:
                  f.seek(start_frame)
                  audio = f.read(frames_to_read)
  ```
  vs `core/stream_normal.py:236-238`
  ```python
                  return audio_file.read(
                      frames=frames, dtype='float32', always_2d=True
                  )
  ```
- **Impact**:
  A chunk load is `CHUNK_DURATION + 2 * CONTEXT_DURATION = 25 s`
  (`core/chunk_operations.py:87-89` with the constants from `core/chunk_boundaries.py`).
  At 44.1 kHz stereo that is 25 x 44100 x 2 x 8 = **17.6 MB per chunk load** instead
  of 8.8 MB, and every intermediate the pipeline allocates (copies, EQ buffers,
  crossfade temporaries) inherits float64. With `MAX_CONCURRENT_STREAMS = 10` plus
  the `StreamlinedCacheWorker` prefetching, this is a straight 2x on the hottest
  memory path, plus ~2x memory bandwidth in the NumPy DSP.
- **Siblings**:
  `core/chunk_operations.py:103` and `:151` build their silence fallbacks as
  `float32`, so the same function already returns mixed dtypes depending on which
  branch fires.
- **Suggested Fix**:
  Add `dtype='float32', always_2d=True` to the `f.read()` call (the `always_2d`
  also makes the `audio.ndim == 1` fix-up at `:118-119` redundant). Confirm with
  `dsp-specialist` that no pipeline stage relies on float64 precision.

</details>

---

### BE3-13: The sample-count invariant is only enforced when `intensity < 1.0` — at the default intensity a length violation is silently padded with silence

- **Severity**: MEDIUM
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/audio_processing_pipeline.py:236-253`; masked by `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:262-280`
- **Status**: NEW
- **Description**:
  The `len(processed) != len(audio)` check added by #4371 lives **inside** the
  `if intensity < 1.0:` blending branch. At `intensity == 1.0` — the default for
  every construction site (`chunked_processor.py:138`, `stream_enhanced.py:132`,
  `streamlined_worker.py:456`) — the processor output is returned with no length
  check at all.
- **Evidence**: `core/audio_processing_pipeline.py:236-253`
  ```python
  if intensity < 1.0:
      ...
      if len(processed) != len(audio):
          raise ValueError("Processed audio length ... does not match input ...")
      processed = audio * (1.0 - intensity) + processed * intensity
  return processed
  ```
- **Impact**: a DSP stage that drops or adds samples at intensity 1.0 flows into
  `trim_context` (which clamps and logs a "DSP may have shrunk the chunk"
  warning) and then into `extract_chunk_segment`, which **pads the shortfall with
  silence** (`chunk_operations.py:262-272`) or trims the excess. The result is an
  audible gap/click at the chunk boundary reported only as a WARNING, in exactly
  the configuration used by 100 % of production playback. This is the project's
  headline invariant (`assert len(output) == len(input)`) going unchecked on the
  default path.
- **Siblings**: `trim_context`'s clamp (`chunk_boundaries.py:350-378`) is
  explicitly documented as a "hard safety net only … does not bind in normal
  operation" — but combined with the silence pad it converts a hard invariant
  violation into a soft, audible one.
- **Suggested Fix**: hoist the length check out of the `intensity < 1.0` branch
  to immediately after `apply_enhancement` returns, unconditionally.

---

### BE4-2: All three telemetry fields in a completed job's `result_data` are permanently `null` — `_finalize_job` reads keys and attributes the engine never produces

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:465-498`
- **Status**: NEW
- **Description**:
  `_finalize_job` pulls `processing_time`, `lufs` and `genre_detected` out of
  `processor.get_processing_info()` and `processor.last_content_profile`. Neither source
  exposes any of those. `get_processing_info()` returns a fixed 7-key dict that contains none
  of `last_processing_time` / `processing_time` / `last_lufs` / `lufs`, and
  `last_content_profile` is a **dict**, so `getattr(content_profile, "genre", None)` can never
  be anything but `None`. The lookups do not raise, so the surrounding
  `try/except Exception: pass` never fires and there is no log line — the failure is completely
  silent.
- **Evidence**:
  ```python
  # core/processing_engine.py:470-478
  proc_info = processor.get_processing_info() if hasattr(processor, "get_processing_info") else None
  if isinstance(proc_info, dict):
      processing_time = proc_info.get("last_processing_time") or proc_info.get("processing_time")
      lufs_val = proc_info.get("last_lufs") or proc_info.get("lufs")
      ...
  content_profile = getattr(processor, "last_content_profile", None)
  if content_profile is not None:
      genre_detected = getattr(content_profile, "genre", None) or genre_detected
  ```
  ```python
  # auralis/core/hybrid_processor.py:541-551 — the actual return shape
  return {
      "mode": ..., "sample_rate": ..., "fft_size": ...,
      "adaptation_strength": ..., "enable_genre_detection": ...,
      "available_genres": ..., "current_targets": ...,
  }
  ```
  ```python
  # auralis/core/hybrid_processor.py:158 — it is a dict, not an object
  self.last_content_profile: dict[str, Any] = {}
  # :341-345 — its keys are 'fingerprint' / 'coordinates' / 'parameters'
  ```
- **Impact**:
  `GET /api/processing/jobs/{job_id}` (`routers/processing_api.py:318`,
  `JobStatusResponse.result_data`) always reports
  `"processing_time": null, "genre_detected": null, "lufs": null`. The #3489 comment block at
  `core/processing_engine.py:430-436` explicitly promises "Pull richer telemetry from the
  processor's `last_content_profile` / `get_processing_info()` in `_finalize_job`" — that
  promise is unmet, and because it is silent, the fields read as "the engine had nothing to
  report" rather than "the plumbing is wrong".
- **Siblings**:
  `getattr(dict_instance, "<key>")` as a stand-in for `dict.get` is a shape confusion worth
  grepping for elsewhere in `core/`.
- **Suggested Fix**:
  Read `last_content_profile` with `.get()`, and source LUFS / elapsed time from something
  that actually measures them (wall-clock around the `asyncio.wait_for` call for the time;
  the mastering target / quality analyser for LUFS), or drop the three fields from
  `result_data` and from the response contract.

---

### BE4-3: `process_job`'s processor return is an unshielded `await` inside `finally` — a cancelled job leaks its exclusively-owned processor when the pool lock is contended

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/processing_engine.py:553-580`, `auralis-web/backend/core/processor_pool.py:99-105`
- **Status**: NEW (the #4567 fix it completes is CLOSED and still present; this is the
  remaining hole on the cancellation path, not a regression of it)
- **Description**:
  `ProcessorPool.get_or_create()` **pops** the processor from the cache, so whoever takes it
  owns it and must return it (#3201). `process_job`'s `finally` does that — but with a plain
  `await`. When the job task is cancelled (`cancel_job()` → `task.cancel()`), the coroutine
  unwinds through this `finally` with `_must_cancel` pending. `asyncio.Lock.acquire()` has a
  non-suspending fast path, so an *uncontended* pool lock is fine; a *contended* one suspends,
  `CancelledError` is delivered at that suspension point, and because `CancelledError` is a
  `BaseException` the `except Exception as return_err` handler below does not catch it. The
  processor is neither returned nor closed, and the two statements after the handler —
  including `self._cancel_events.pop(job.job_id, None)` — never run.
- **Evidence**:
  ```python
  # core/processing_engine.py:563-580
  if processor is not None and config is not None:
      try:
          await self._return_processor(job.mode, config, processor)   # <- unshielded await
      except Exception as return_err:                                  # <- misses CancelledError
          ...
          processor.close()
      ...
  self._cancel_events.pop(job.job_id, None)                            # <- skipped on that path
  ```
  The sibling code in the same subsystem already knows this hazard and shields against it:
  ```python
  # core/job_worker.py:100-115
  # #4543: an `await` in a finally on an already-cancelled task
  # re-raises CancelledError at the await point ...
  await asyncio.shield(self._engine.cleanup_old_jobs(...))
  ```
  Contention on `ProcessorPool._lock` is not hypothetical: `get_or_create` holds it across the
  200-500 ms `await self._create_processor(config)` (that is exactly open issue **#4689**),
  and `max_concurrent_jobs` defaults to 2 (`config/startup.py:570`).
- **Impact**:
  Cancelling job A while job B is inside `get_or_create` leaks a warm `HybridProcessor` — the
  pool's own docstring puts these at ~200 MB each (`core/processor_pool.py:7-8`) — and leaves
  a `threading.Event` in `_cancel_events` forever, re-opening the registry leak #4496's fix
  closed. It also silently defeats the #4567 fix's stated goal ("Hoisting it means a future
  branch cannot reintroduce the same omission") for the one exit path that is *most* likely to
  hit a contended lock.
- **Siblings**:
  Same shape as #4543 (`JobWorker`) and the `_run_job` finally; `stream_enhanced` /
  `stream_normal` semaphore releases should be re-checked for unshielded awaits in `finally`
  (not examined in this dimension).
- **Suggested Fix**:
  Wrap the return in `asyncio.shield(...)` and catch `BaseException` (or explicitly
  `asyncio.CancelledError`) around it, mirroring `job_worker.py:110-115`; move the
  `_cancel_events.pop` above the return so it cannot be skipped.

---

### BE4-4: The processing engine's temp directories are never swept — `auralis_processing` outputs and `auralis_uploads` inputs survive every crash, forever

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/config/startup.py:266-277`, `auralis-web/backend/core/processing_engine.py:126-127`, `auralis-web/backend/core/processing_engine.py:631-680`
- **Status**: NEW
- **Description**:
  The lifespan startup deliberately sweeps two temp roots — `auralis_chunks` (rmtree) and
  `auralis_stream_*` (`reclaim_leftover_stream_temps`, added by #3877 precisely because "a
  crash ... can leave one behind"). It does **not** sweep `auralis_processing` (job outputs)
  or `auralis_uploads` (uploaded inputs, up to 500 MB each per `config/limits.py:12`). The
  only reclamation path for those is `ProcessingEngine.cleanup_old_jobs()`, which iterates
  `self.jobs` — an **in-memory-only** dict. After a crash or a hard kill the dict is empty, so
  the files on disk become permanently unreferenced.
- **Evidence**:
  ```python
  # config/startup.py:266-277
  chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
  if chunk_dir.exists():
      shutil.rmtree(chunk_dir); chunk_dir.mkdir(exist_ok=True)
  reclaim_leftover_stream_temps(Path(tempfile.gettempdir()))
  # -- no equivalent for auralis_processing / auralis_uploads
  ```
  ```python
  # core/processing_engine.py:650-657 — reclamation is driven off the in-memory registry
  async with self._jobs_lock:
      for job_id, job in self.jobs.items():
          ...
          candidate_paths.append((Path(job.output_path), Path(job.input_path)))
  ```
  `grep -rn "auralis_processing\|auralis_uploads"` over the backend returns exactly three
  hits, all inside `processing_engine.py` / `processing_api.py` — no startup sweeper.
- **Impact**:
  Unbounded disk growth in the system temp root across the app's lifetime, in the two
  directories that hold the *largest* artefacts the backend writes (full processed WAVs and
  up-to-500 MB uploads). On a desktop install with `/tmp` on tmpfs this consumes RAM.
- **Siblings**:
  Prior finding BE6-06 flags the *opposite* hazard for `auralis_stream_*` (the sweep is too
  broad). The right shape is one sweeper covering all four roots with consistent ownership
  checks.
- **Suggested Fix**:
  Extend `reclaim_leftover_stream_temps` (or add a sibling) to age-sweep
  `auralis_processing` and `auralis_uploads` at startup, and call it from the same place.

> **Merged duplicate — BE7-4.** Independently found by Dimension 7. Dimension 7's write-up follows.

<details><summary>BE7-4 (merged): Upload inputs and processed outputs under `/tmp` are only reclaimable from in-memory job state — a restart orphans them forever</summary>

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/startup.py:266-277`; `/mnt/data/src/matchering/auralis-web/backend/core/processing_engine.py:126`, `:185`, `:631-680`; `/mnt/data/src/matchering/auralis-web/backend/routers/processing_api.py:237-264`
- **Status**: NEW
- **Description**:
  Startup sweeps exactly two temp locations: `auralis_chunks` (rmtree, `startup.py:267-274`) and `auralis_stream_*` (`reclaim_leftover_stream_temps`, `startup.py:215-234`). It sweeps neither `/tmp/auralis_uploads` (uploaded job inputs, up to 500 MB each) nor `/tmp/auralis_processing` (rendered job outputs). Those two directories are cleaned only by `ProcessingEngine.cleanup_old_jobs()`, which derives its delete list by iterating `self.jobs` — a plain in-memory dict rebuilt empty at every process start. Any job whose TTL (`completed_job_ttl_hours`, default 1.0 h) had not yet elapsed when the backend exited leaves both its input and its output on disk with no record that could ever name them again.
- **Evidence**:
  ```python
  # config/startup.py:266-277  — the only two sweeps
  chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
  ...
  reclaim_leftover_stream_temps(Path(tempfile.gettempdir()))
  ```
  ```python
  # core/processing_engine.py:650-660 — reclaim list comes from in-memory jobs only
  async with self._jobs_lock:
      for job_id, job in self.jobs.items():
          if job.status in [...COMPLETED, FAILED, CANCELLED]:
              ...
              candidate_paths.append((Path(job.output_path), Path(job.input_path)))
  ```
  Both directories are created but never enumerated: `self.temp_dir = Path(tempfile.gettempdir()) / "auralis_processing"` (`:126`), `temp_dir = Path(tempfile.gettempdir()) / "auralis_uploads"` (`processing_api.py:237`).
- **Impact**:
  Unbounded disk growth across restarts, in the one place the project already decided needs bounding for the sibling caches (`chunk_cache_manager.py:29` enforces a 512 MB cap on `auralis_chunks`). On a desktop app that is restarted constantly during development and after crashes, each 500 MB upload plus its rendered output can persist indefinitely. It also means the "recovery from restart" story for jobs is: queued/running jobs are silently lost with no client-visible signal, and their disk footprint is not.
- **Siblings**:
  `cache/adapter.py:149` (`auralis_cache_adapter`) is likewise never swept at startup. `routers/artwork.py:111` uses `mkstemp` for thumbnails; those are unlinked on the success path but a hard kill mid-write leaks them too.
- **Suggested Fix**:
  Extend the startup sweep to age-out `auralis_uploads` / `auralis_processing` / `auralis_cache_adapter` (delete anything older than the job TTL) alongside the existing `reclaim_leftover_stream_temps` call, and log the reclaimed count the same way. Optionally persist the job registry so an interrupted job can be reported as FAILED rather than vanishing.

</details>

---

### BE4-5: `NavigationService` calls blocking `AudioPlayer` engine methods directly on the event loop — the only playback service that was never offloaded

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/navigation_service.py:75`, `:121`, `:183`, `:190`, `:194`
- **Status**: NEW
- **Description**:
  `PlaybackService` (#3716) and `QueueService` (#3554) both went through an explicit fix pass
  to run every synchronous `AudioPlayer` call through `asyncio.to_thread`, with comments
  naming the exact hazard ("it acquires `file_manager._audio_lock`, which a concurrent
  `load_file()` can hold for hundreds of ms to seconds while decoding a large file. Running
  this synchronously on the event loop froze the FastAPI worker").
  `NavigationService` — a sibling service constructed from the same globals — was not
  included and still calls the same class of methods inline from `async def` handlers.
- **Evidence**:
  ```python
  # services/navigation_service.py:74-75
  if hasattr(self.audio_player, 'next_track'):
      success = self.audio_player.next_track()          # sync, on the loop
  # :120-121
      success = self.audio_player.previous_track()      # sync, on the loop
  # :182-194
      queue_manager.set_current_index(track_index)      # sync
      self.audio_player.load_file(track_path)           # sync full decode
      self.audio_player.play()                          # sync
  ```
  vs. the offloaded siblings:
  ```python
  # services/playback_service.py:270-278
  async with self._playback_lock:  # #3734
      await asyncio.to_thread(self.audio_player.seek, position)
  # services/queue_service.py:273-274
  await asyncio.to_thread(self.audio_player.load_file, current_track.filepath)
  await asyncio.to_thread(self.audio_player.play)
  ```
  `AudioPlayer.next_track()` is documented as holding `_audio_lock` "across the entire
  swap-and-reset sequence" with nested `PlaybackController._lock`
  (`auralis/player/enhanced_audio_player.py:310-331`), i.e. exactly the lock #3716 says can be
  held for hundreds of ms to seconds.
- **Impact**:
  Every next/previous/jump command stalls the whole event loop for the duration of the
  gapless swap (and, on the `jump_to_track` fallback path, a full `load_file` decode) —
  freezing all in-flight HTTP requests **and** every WebSocket audio stream on the same loop.
  This is the exact regression #3716/#3554 were filed to eliminate, surviving in the one
  service they missed.
- **Siblings**:
  `jump_to_track` also calls `queue_manager.get_queue_size()` / `get_queue()` inline; these are
  cheap but sit behind the same engine locks.
- **Suggested Fix**:
  Wrap each engine call in `asyncio.to_thread`, matching `PlaybackService`/`QueueService`.

---

### BE4-6: `LibraryAutoScanner._stop_watchdog()` blocks the event loop on `Observer.join(timeout=5)` — from both `stop()` and the periodic scan cycle

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:421-430`, called from `:130` (async `stop`) and `:404` via `_sync_watchdog` (called from async `_run_cycle`, `:182`)
- **Status**: NEW
- **Description**:
  `_stop_watchdog()` is a synchronous method that calls `self._observer.stop()` followed by
  `self._observer.join(timeout=5)` — a blocking `threading.Thread.join`. It is invoked
  directly (no `to_thread`) from two `async def` contexts: the lifespan shutdown path
  (`stop()`) and, more importantly, `_sync_watchdog()`, which runs on **every scan cycle**
  whenever the configured folder set has changed.
- **Evidence**:
  ```python
  # services/library_auto_scanner.py:421-430
  def _stop_watchdog(self) -> None:
      if self._observer is not None:
          try:
              self._observer.stop()
              self._observer.join(timeout=5)      # blocking join, no to_thread
  ```
  ```python
  # :126-130 (async)                       # :390-414 (sync, called from async _run_cycle)
  async def stop(self) -> None:            def _sync_watchdog(self, scan_folders):
      ...                                      ...
      self._stop_watchdog()                    self._stop_watchdog()
                                               ...
                                               self._observer.start()
  ```
  The rest of this module is scrupulous about the boundary — `_settings_repo.get_settings`,
  `scan_directories` and `cleanup_missing_files` are all `to_thread`'d (`:175`, `:274`, `:325`).
  The watchdog teardown is the outlier.
- **Impact**:
  Up to 5 s of total event-loop stall (all HTTP + all WebSocket audio streams) whenever the
  user edits their scan folders, and again during shutdown. In the shutdown case it also
  delays every subsequent teardown step in `_shutdown_components`.
- **Siblings**:
  `Observer.start()` at `:414` spawns threads on the loop thread — cheap, but the whole
  start/stop pair belongs in a thread.
- **Suggested Fix**:
  Make `_stop_watchdog` awaitable (`await asyncio.to_thread(self._observer.stop_and_join)`) or
  wrap both call sites; keep the 5 s bound.

---

### BE4-13: `add_track_to_queue` and `move_track_in_queue` rebuild the queue by hand and re-write the OLD `current_index` — the queue pointer silently detaches from the playing track

- **Severity**: MEDIUM
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/queue_service.py:320-324`, `:495-509`; contrast `auralis/player/components/queue_manager.py:265-290` (`reorder_tracks`)
- **Status**: NEW
- **Description**:
  Both methods bypass the engine's index-aware mutators. They read the queue out
  (`get_queue()`), mutate a plain Python list, then push it back with
  `set_queue(current_queue, queue_manager.current_index)` — passing the *pre-mutation* index
  verbatim. `QueueController.set_queue` clears the queue and re-adds every track, then writes
  `current_index = min(start_index, track_count - 1)`. Any mutation that shifts the currently
  playing track's position therefore leaves `current_index` pointing at a **different** track.
- **Evidence**:
  ```python
  # services/queue_service.py:320-324 (add, positional insert)
  if position is not None:
      current_queue = queue_manager.get_queue()
      current_queue.insert(position, track.filepath)
      queue_manager.set_queue(current_queue, queue_manager.current_index)   # stale index
  ```
  ```python
  # services/queue_service.py:505-509 (drag-and-drop move)
  track = current_queue.pop(from_index)
  current_queue.insert(to_index, track)
  queue_manager.set_queue(current_queue, queue_manager.current_index)       # stale index
  ```
  The engine solves exactly this, by track identity, and says so:
  ```python
  # auralis/player/components/queue_manager.py (reorder_tracks)
  current_track_id = self.tracks[self.current_index].get('id')
  self.tracks = [self.tracks[i] for i in new_order]
  # Update current_index to point to the same track (#2159)
  for i, track in enumerate(self.tracks):
      if track.get('id') == current_track_id:
          self.current_index = i
  ```
  `_remove_track_unlocked` likewise adjusts `current_index` on removal
  (`queue_manager.py:200-209`), and `QueueService.reorder_queue` (`:453`) correctly delegates
  to `reorder_tracks`. Only the add-at-position and move paths hand-roll it.
  Worked example — queue `[A,B,C]`, `current_index=1` (B playing), insert X at 0:
  new list `[X,A,B,C]`, index still `1` → the queue now reports **A** as current while **B** is
  audible.
- **Impact**:
  Reachable from two live routes: `POST` add-to-queue with a `position`
  (`routers/player.py:675-679`) and the drag-and-drop move (`routers/player.py:692`). After
  either, `get_current_track()`, the `queue_changed` broadcast's `current_index`, and
  next/previous navigation all key off a wrong track — the same metadata/audio desync class
  that #2403 was filed for on the removal path and #2159 on the reorder path. Skipping "next"
  from a desynced pointer plays the wrong track.
- **Siblings**:
  Both methods also call the engine's queue mutators (`get_queue`, `set_queue`,
  `add_to_queue`, `remove_track`, `reorder_tracks`, `shuffle`) inline on the event loop, while
  `_set_queue_impl:259-263` offloads the *identical* `queue.set_queue` call with the comment
  "sync engine call, offload". These are cheap in-memory list operations so it is an internal
  inconsistency rather than a stall, but it is the same divergence as BE4-5.
  Neither method takes `_set_queue_lock`, unlike `set_queue` (#3721).
- **Suggested Fix**:
  Route the move through `queue_manager.reorder_tracks(new_order)` (which already preserves
  the current track by id) and, for positional add, recompute
  `new_index = current_index + 1 if position <= current_index else current_index` before
  calling `set_queue` — or add an index-aware `insert_track(index, track)` to `QueueManager`
  and delegate.

---

### BE5-N1: `settingsService.updateSettings()` is typed as returning `UserSettings`, but `PUT /api/settings` returns a `{message, settings}` envelope


- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**:
  - Backend: `/mnt/data/src/matchering/auralis-web/backend/routers/settings.py:131-137` (`SettingsUpdateResponse`), `:183-198` (`PUT /api/settings`, `response_model=SettingsUpdateResponse`)
  - Frontend: `/mnt/data/src/matchering/auralis-web/frontend/src/services/settingsService.ts:113-115`
  - Consumer: `/mnt/data/src/matchering/auralis-web/frontend/src/components/settings/useSettingsDialog.ts:65-68`
  - Factory: `/mnt/data/src/matchering/auralis-web/frontend/src/utils/serviceFactory.ts:136-150` (`update()` returns the raw body as `T`)
- **Status**: NEW
- **Description**:
  `PUT /api/settings` declares `response_model=SettingsUpdateResponse`, whose shape is
  `{message: str, settings: SettingsResponse}` — the settings object is *nested*. Every
  sibling mutating settings endpoint (`/reset`, `/scan-folders`, `/scan-folders/delete`)
  uses the same envelope, and the frontend correctly unwraps `result.settings` for all
  three of those. The `update` path does not: `settingsService.updateSettings()` declares
  `Promise<UserSettings>` and returns `crudService.update(...)` unchanged, and
  `useSettingsDialog.handleSave` then calls `setSettings(result)` with the envelope.
  `GET /api/settings` returns a *flat* `SettingsResponse` (no envelope), so the round trip
  is genuinely asymmetric — the TS type describes the GET shape and is applied to the PUT
  response.
- **Evidence**:
  Backend — `routers/settings.py:183-198`:
  ```python
  @router.put("/api/settings", response_model=SettingsUpdateResponse)
  async def update_settings(updates: SettingsUpdateRequest) -> dict[str, Any]:
      ...
      return {"message": "Settings updated", "settings": settings.to_dict()}
  ```
  with `routers/settings.py:131-137`:
  ```python
  class SettingsUpdateResponse(BaseModel):
      model_config = ConfigDict(extra="forbid")
      message: str
      settings: SettingsResponse
  ```
  Frontend — `services/settingsService.ts:113-115`:
  ```ts
  export async function updateSettings(updates: SettingsUpdate): Promise<UserSettings> {
    return crudService.update(0, updates);
  }
  ```
  Consumer — `components/settings/useSettingsDialog.ts:65-68`:
  ```ts
  const result = await settingsService.updateSettings(pendingChanges);
  setSettings(result);
  setPendingChanges({});
  onSettingsChange?.(result);
  ```
  Contrast with the correct unwrap at `useSettingsDialog.ts:85-87`, `:113-114`, `:135-136`:
  ```ts
  const result = await settingsService.resetSettings();
  setSettings(result.settings);
  ```
- **Impact**:
  After a save, the dialog's `settings` state holds `{message, settings}` instead of the
  settings object. `getValue()` (`useSettingsDialog.ts:157-165`) reads
  `settings[key as keyof UserSettings]`, which is `undefined` for every key, so:
  - the scan-folder list renders empty (`getValue('scan_folders') ?? []` at
    `components/settings/SettingsDialog.tsx:54` and
    `components/settings/SettingsDialogContent.tsx:37`),
  - every other control falls back to its null/default rendering.
  `handleSave` calls `onClose()` immediately after, so the corruption is usually hidden
  until the dialog is reopened without a remount, and `onSettingsChange` only feeds a
  `console.log` + toast at `ComfortableApp.tsx:337-340`. That caps this below HIGH — no
  crash, no wrong audio, no data loss — but the stored client state is genuinely wrong and
  the declared TS type does not match the wire format.
- **Siblings**: The same envelope is handled correctly by `resetSettings`,
  `addScanFolder`, and `removeScanFolder`; `update` is the lone straggler. The generic
  `createCrudService.update()` has no envelope awareness, so any future service pointed at
  an enveloped PUT will repeat this.
- **Suggested Fix**:
  Change `settingsService.updateSettings` to declare the real contract and unwrap it:
  `const { settings } = await crudService.update<{message: string; settings: UserSettings}>(...)`
  — or, symmetrically, have `useSettingsDialog.handleSave` read `result.settings` the way
  its three siblings already do. Do not change the backend: the envelope is consistent
  across all four mutating settings endpoints.

---

### BE5B-N4: `GET /api/cache/stats` puts `tracks_cached` under `tier2`, but the Pydantic model, the TS type, and three Redux selectors all read `overall.tracks_cached` — and per-track entries omit the `track_id` the dashboard renders


- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**:
  - Producer: `/mnt/data/src/matchering/auralis-web/backend/cache/manager.py:475-508` (`StreamlinedCacheManager.get_stats`)
  - Backend contract: `/mnt/data/src/matchering/auralis-web/backend/schemas.py:365-372` (`OverallCacheStats`)
  - Frontend contract: `/mnt/data/src/matchering/auralis-web/frontend/src/services/api/standardizedAPIClient.ts:61-74`, `/mnt/data/src/matchering/auralis-web/frontend/src/types/api.ts:327-339`
  - Consumers: `/mnt/data/src/matchering/auralis-web/frontend/src/store/selectors/cache.ts:31`, `/mnt/data/src/matchering/auralis-web/frontend/src/store/slices/cacheSlice.ts:198-199`, `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/shared/useReduxState.ts:277`, `/mnt/data/src/matchering/auralis-web/frontend/src/components/shared/CacheStatsDashboard.tsx:153-156`, `/mnt/data/src/matchering/auralis-web/frontend/src/components/shared/CacheStatsDashboard/TrackCacheList.tsx:27-31`, `:115`
- **Status**: NEW
- **Description**:
  Two field-placement mismatches in the same payload:
  1. `get_stats()` emits `tracks_cached` inside the **`tier2`** sub-dict
     (`cache/manager.py:489`). The `overall` sub-dict has five keys and does not
     include it (`:491-497`). Every declared contract on both sides puts it under
     `overall`: `schemas.OverallCacheStats.tracks_cached` (required),
     `standardizedAPIClient.CacheStats.overall.tracks_cached` (required),
     `types/api.ts CacheStatsResponse.overall.tracks_cached` (required). Neither TS
     type declares `tier2.tracks_cached` at all.
  2. Each entry of the `tracks` map carries `completion_percent`, `fully_cached`,
     `total_chunks`, `cached_original`, `cached_processed` — but **not** `track_id`
     (the id is the map key, `cache/manager.py:498-507`). `TrackCacheInfo` declares
     `track_id: number` required and `TrackCacheList` renders it directly.
- **Evidence**:
  `cache/manager.py:483-497`:
  ```python
  "tier2": {
      "chunks": len(self.tier2_cache),
      ...
      "tracks_cached": len({c.track_id for c in self.tier2_cache.values()})
  },
  "overall": {
      "total_chunks": ...,
      "total_size_mb": ...,
      "total_hits": ...,
      "total_misses": ...,
      "overall_hit_rate": ...
  },
  ```
  `cache/manager.py:498-507`:
  ```python
  "tracks": {
      track_id: {
          "completion_percent": status.get_completion_percent(),
          "fully_cached": status.is_fully_cached(),
          "total_chunks": status.total_chunks,
          "cached_original": len(status.cached_chunks_original),
          "cached_processed": len(status.cached_chunks_processed)
      }
      for track_id, status in self.track_status.items()
  }
  ```
  `components/shared/CacheStatsDashboard.tsx:153-156`:
  ```tsx
  Tracks Cached
  ...
  {cacheStats.overall.tracks_cached}
  ```
  `components/shared/CacheStatsDashboard/TrackCacheList.tsx:115`:
  ```tsx
  Track {trackInfo.track_id}
  ```
  Route path confirmed live: `routers/cache_streamlined.py:80-98` returns
  `CacheStatsResponse(**stats)` with `tier1/tier2/overall` typed `dict[str, Any]`,
  so nothing on the backend rejects the misplacement.
- **Impact**:
  User-visible and live — `CacheStatsDashboard` is rendered from
  `components/settings/AdvancedSettingsPanel.tsx:77`, which
  `components/settings/SettingsDialogContent.tsx:86` mounts (this was deliberately
  wired up as part of the #4579 cleanup, so it is no longer dead). Settings →
  Advanced shows a "Tracks Cached" tile that is blank/`undefined`, and every
  per-track row reads `Track ` with no number. Two selectors mask it as `0`
  (`cacheSlice.ts:199`, `useReduxState.ts:277` both use `?? 0`), while
  `store/selectors/cache.ts:31` has no fallback and propagates `undefined`.
  Second-order: adopting the typed `schemas.CacheStatsResponse` (which the cache
  router's own docstring proposes as a follow-up — see BE5B-N1) would make
  `/api/cache/stats` return 500, because `OverallCacheStats.tracks_cached` and
  `CacheTierStats.tier_name` are required and the live dict supplies neither.
- **Siblings**: `CacheTierStats.tier_name` (`schemas.py:357`) is the same class of
  drift — a required model field no producer emits.
- **Related**: #4440 (CLOSED) fixed the *envelope* for this endpoint but did not
  compare the payload's internal field placement. BE5B-N1 (the duplicate cache
  models).
- **Suggested Fix**: Move `tracks_cached` from `tier2` to `overall` in
  `StreamlinedCacheManager.get_stats()` (the name is already aggregate-flavoured
  and both contracts expect it there), and add `"track_id": track_id` to each
  `tracks` entry. Then add a test asserting `get_stats()` validates against
  `schemas.CacheStatsResponse`, which is what would have caught both.

---

### BE5B-N5: `useQueueFetch` reads `is_shuffled` from `GET /api/player/queue`, which only ever emits `shuffle_enabled` — the shuffle flag is reset to `false` on every mount


- **Severity**: MEDIUM
- **Dimension**: Schema Consistency
- **Location**:
  - Frontend: `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/player/useQueueFetch.ts:42-59`
  - Backend contract: `/mnt/data/src/matchering/auralis-web/backend/routers/player.py:165-187` (`QueueInfoResponse`), producer `/mnt/data/src/matchering/auralis/player/components/queue_manager.py:357-377`
  - Correct sibling: `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts:160-180`
- **Status**: NEW
- **Description**:
  `QueueManager.get_queue_info()` emits `shuffle_enabled` (and `repeat_enabled`);
  `QueueInfoResponse` declares `shuffle_enabled: bool | None` and
  `model_config = ConfigDict(extra='allow')`. Nothing anywhere renames it to
  `is_shuffled`. `useQueueFetch` reads
  `(response.is_shuffled) ?? (response.isShuffled) ?? false` — both keys are always
  `undefined`, so it unconditionally dispatches `setIsShuffled(false)`.
  The response is typed `Record<string, unknown>` and every field is read through
  an `as` cast, so TypeScript cannot flag the phantom key.
  The WebSocket path in the same app reads the right key
  (`usePlayerStateSync.ts:178-180`: `if ('shuffle_enabled' in state …)`), which is
  what makes this survivable — and also what makes it a race.
- **Evidence**:
  `auralis/player/components/queue_manager.py:368-377`:
  ```python
  return {
      'tracks': tracks_copy,
      'current_index': idx,
      'current_track': current,
      'track_count': len(tracks_copy),
      'has_next': idx < len(tracks_copy) - 1,
      'has_previous': idx > 0,
      'shuffle_enabled': self.shuffle_enabled,
      'repeat_enabled': self.repeat_enabled,
  }
  ```
  `hooks/player/useQueueFetch.ts:50-52`:
  ```ts
  dispatch(reduxSetIsShuffled(
    (response.is_shuffled as boolean) ?? (response.isShuffled as boolean) ?? false
  ));
  ```
  Reachability: `components/player/Player.tsx:22,317` renders `QueuePanel`, which
  calls `usePlaybackQueue()` (`QueuePanel.tsx:3,30`), which calls `useQueueFetch()`
  (`usePlaybackQueue.ts:41,172`). This is the live player path.
- **Impact**:
  On every mount the client asserts "shuffle is off". The WS connect-time
  `player_state` snapshot sets it correctly, but the two are unordered — if the
  REST GET resolves after the snapshot (entirely plausible: the WS pushes state
  immediately on connect, the REST call goes through `useRestAPI`), the wrong value
  wins. The desync is user-visible and actionable: `useQueueMutations.toggleShuffle`
  computes `newShuffle = !stateRef.current.isShuffled`
  (`hooks/player/useQueueMutations.ts:228`), so a stale `false` makes the next
  toggle send "enable shuffle" to a backend that is already shuffled.
- **Siblings**:
  - Same file, same cast: `dispatch(reduxSetQueue(response.tracks as (Track | QueueTrack)[]))`
    (`useQueueFetch.ts:46`) pushes the backend's **snake_case** `TrackInfo` objects
    straight into a Redux slice whose element type is the **camelCase** domain
    `QueueTrack` (`types/domain.ts:56`, `artworkUrl`). The WS path maps it properly
    (`usePlayerStateSync.ts:161-168`: `artworkUrl: t.artwork_url`), so the same
    slice holds differently-shaped objects depending on which writer ran last.
    No current queue renderer reads artwork, so this half is latent today.
  - `services/queueService.ts:17-24` types the same endpoint's tracks with
    `filepath: string` **required** — a field `TrackInfo` marks `Field(exclude=True)`
    and therefore never sends (#3205) — while marking `artist?`/`album?` optional,
    which the backend declares required. The optionality is inverted on three of
    six fields.
- **Related**: #4441 (CLOSED) — the previous `GET /api/player/queue` shape bug;
  #3586 added the correct `shuffle_enabled` read on the WS side but did not fix the
  REST side.
- **Suggested Fix**: Read `response.shuffle_enabled` in `useQueueFetch` (keep
  `is_shuffled` only if a legacy payload must be tolerated), and reuse the same
  `TrackInfo → QueueTrack` mapping `usePlayerStateSync` already has rather than
  casting. Extend `isQueueResponseShape` (`api/responseGuards.ts:84-91`) to assert
  `shuffle_enabled` so this class of drift fails at the boundary.

---

### BE6-1: `RateLimitMiddleware` keys its window on the full request path, so every per-resource endpoint gets an unlimited budget

- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/middleware.py:146-151, 182-194`
- **Status**: NEW
- **Description**: `_RATE_LIMITS` is a map of **path prefixes** to budgets, and the dispatch matches a rule by `path.startswith(prefix)` — but the bucket key is built from the **full concrete path**, not the matched prefix:

  ```python
  # middleware.py:184-194
  for prefix, rule in self._RATE_LIMITS.items():
      if path.startswith(prefix):
          limit_rule = rule
          break
  ...
  client_ip = request.client.host if request.client else "unknown"
  key = f"{client_ip}:{path}"        # <-- full path, not `prefix`
  ```

  Every rate-limited prefix except `/api/files/upload` and `/api/library/scan` fans out over path parameters, so each distinct id gets its own fresh budget. The docstring's stated contract — *"20 similarity queries per minute"*, *"10 processing jobs per minute"* — is not what the code enforces.
- **Evidence**: Live probe against the real `setup_middleware()` stack (`Origin: http://localhost:8765`, `Host: localhost:8765`):

  ```
  GET /api/similarity/tracks/1 x25   -> 20 x 200, 5 x 429     # limit works for one fixed path
  GET /api/similarity/tracks/{2..79} -> 78 x 200, 0 x 429     # limit completely absent across ids
  POST /api/library/scan x4          -> [200, 200, 429, 429]  # fixed path, works
  POST /api/library/scanXYZ x4       -> [404, 404, 429, 429]  # prefix match also bills non-routes
  ```

  The affected real routes, all matched by a rate-limit prefix and all carrying path parameters:
  - `routers/similarity.py:105` `GET /api/similarity/tracks/{track_id}/similar` (the expensive one — k-NN over the fingerprint set)
  - `routers/similarity.py:205` `/tracks/{id1}/compare/{id2}`, `:256` `/tracks/{id1}/explain/{id2}`
  - `routers/fingerprint_queue.py:90` `POST /api/similarity/fingerprint-queue/enqueue/{track_id}`
  - `routers/processing_api.py:158` `/process` and `:217` `/upload-and-process` each get a *separate* 10/min budget (so 20 job submissions/min, not 10)
  - `routers/processing_api.py:302,322,367` `/job/{job_id}...` — one budget per job id
- **Impact**: The rate limit protects only three fixed paths (`/api/files/upload`, `/api/library/scan`, `/api/similarity/graph/build`, `/api/similarity/fit`). The single most expensive REST surface in the app — per-track similarity search — is effectively unlimited. A frontend render loop that fires `similar` for every visible row (or a runaway retry) can saturate the thread pool with no backpressure and no 429 signal, which is precisely the failure `#2575` was filed to prevent. Downgraded from HIGH to MEDIUM per the localhost-only rule: the realistic trigger is the app's own client, not a remote attacker.
- **Siblings**: The prefix match also bills 404 paths (`/api/library/scanXYZ`), which is harmless but shows the key and the rule are derived from different things. `#4525`/`#4541` are unrelated.
- **Suggested Fix**: Key on the matched prefix, not the path: `key = f"{client_ip}:{prefix}"` (capture `prefix` from the match loop). If per-resource granularity is ever wanted for a specific rule, make that explicit in `_RATE_LIMITS` rather than implicit in the key format. Add a regression test that walks 40 distinct `track_id`s and asserts a 429 appears.

---

### BE6-2: Startup rollback drops `library_manager` and `audio_player` without shutting them down — SQLite engine and audio device leak, and lifespan shutdown then skips them

- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/startup.py:53-57, 82-83` (and the skip at `:127-136`, `:158-163`)
- **Status**: NEW
- **Description**: `_rollback_partial_startup()` correctly `await`s `.stop()` on the three background workers, but every other component is handled by a bare null-out loop:

  ```python
  # startup.py:53-57
  _ROLLBACK_COMPONENTS_TO_NULL: tuple[str, ...] = (
      'library_manager', 'repository_factory', 'settings_repository',
      'audio_player', 'player_state_manager',
      'streamlined_cache', 'similarity_system', 'graph_builder',
  )
  # startup.py:82-83
  for _component in _ROLLBACK_COMPONENTS_TO_NULL:
      globals_dict[_component] = None
  ```

  Two of these own OS resources and have explicit teardown that the *shutdown* path knows about but the *rollback* path does not:
  - `library_manager` is a `LibraryDatabase` constructed at `:307`. `_shutdown_components` calls `.shutdown()` on it at `:158-163` specifically for the "WAL checkpoint + engine dispose (#3210)" reason. Rollback does not.
  - `audio_player` is an `AudioPlayer` constructed at `:450`. `_shutdown_components` calls `.stop()` + `.cleanup()` at `:127-136` to "release hardware resources (#3210)". Rollback does not.

  Worse, the null-out makes the later shutdown path a no-op for them, because both shutdown steps are guarded by `if globals_dict.get(...)`. So once rollback runs, those resources are **unreachable for the rest of the process lifetime**.
- **Evidence**: The rollback is reached from `startup.py:556-561` — any exception in the ~275-line `if HAS_AURALIS:` block after `LibraryDatabase()` succeeds at `:307`. Reachable triggers inside that window that are *not* individually guarded: `globals_dict['library_manager'].repositories` (`:315`), `PlayerConfig(...)`/`AudioPlayer(...)` (`:440-454`, e.g. no audio device present in a headless/container run — a documented `#3210` scenario), `PlayerStateManager(manager)` (`:458`). After rollback the process keeps running and serving 503s (that is the intended behaviour per the docstring at `:61-72`), with an open SQLAlchemy engine, an un-checkpointed WAL, and possibly an open PortAudio stream, until the user quits.
- **Impact**: A `-wal` file that is never checkpointed after a failed boot; a held audio device that blocks a subsequent retry; connection-pool file descriptors held for the process lifetime. This is the same class of defect `#4569` fixed for the shutdown path, in the sibling function that `#3812` extracted at the same time.
- **Siblings**: `analysis.fingerprint_queue._fingerprint_queue` has the mirror-image problem — see BE6-11. `#4682` (unjoined autofit thread) is the third member of this family.
- **Suggested Fix**: Give `_rollback_partial_startup` the same per-component teardown `_shutdown_components` has — ideally by extracting the teardown steps into named helpers and calling them from both, so the two can never diverge again (the `WORKER_STOP_KWARGS`/`BACKGROUND_WORKER_KEYS` pattern from `#4569` applied to non-worker components).

---

### BE6-3: The entire `monitoring/` package (936 lines) is unreachable — memory-pressure degradation and metrics collection are never wired into the app

- **Severity**: MEDIUM
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/monitoring/memory_monitor.py` (361 lines), `/mnt/data/src/matchering/auralis-web/backend/monitoring/metrics_collector.py` (575 lines), `/mnt/data/src/matchering/auralis-web/backend/monitoring/__init__.py`
- **Status**: NEW
- **Description**: `MemoryPressureMonitor`, `DegradationManager`, `get_memory_monitor()`, `MetricsCollector` and `get_metrics_collector()` have **zero importers anywhere in the repository outside their own test file**. Nothing in `config/startup.py`, `config/app.py`, `config/routes.py`, any router, any service, or any `core/` module constructs or consults them.
- **Evidence**:
  ```
  $ grep -rn --include='*.py' -e 'from monitoring' -e 'import monitoring' \
      -e 'get_memory_monitor' -e 'get_metrics_collector' \
      -e 'MemoryPressureMonitor' -e 'DegradationManager' . \
      | grep -v '/.venv/' | grep -v 'auralis-web/backend/monitoring/'
  tests/backend/test_memory_monitor.py:20: from monitoring.memory_monitor import DegradationManager, MemoryPressureMonitor, MemoryStatus
  ... (all remaining hits are inside that same test file)
  ```
  `monitoring/memory_monitor.py:344-360` defines process-wide singletons (`_memory_monitor_instance`, `_degradation_manager_instance`) that are only ever materialised by the tests.
- **Impact**: Two things: (a) ~936 lines of `psutil`-based logic with a passing test suite that gives a false impression the backend degrades gracefully under memory pressure and exports metrics — it does neither; (b) the chunk cache (`cache.manager.TIER1_MAX_SIZE_MB`, logged at `startup.py:603`) sizes itself without any input from the memory monitor that exists precisely to recommend cache sizes (`memory_monitor.py:37`). The subsystem is either dead code to delete or an unfinished wiring task; either way the current state is misleading. Rated MEDIUM rather than LOW because passing tests actively mask it.
- **Siblings**: Same shape as `#4684` (`HAS_AURALIS` gate whose fallback is unreachable) and BE6-7 (`validate_scan_path` dead) — a recurring "tested but unwired" pattern in this backend.
- **Suggested Fix**: Decide and act: either instantiate `get_memory_monitor()`/`get_metrics_collector()` in the lifespan and consult `DegradationManager` from the cache sizing and streaming-semaphore paths, or delete the package with its tests. Do not leave it half-alive.

> **Merged duplicate — BE8-08.** Independently found by Dimension 8, which additionally establishes that `DegradationManager.apply_degradation()` targets a `buffer_manager` with `l1/l2/l3_cache` attributes no live object exposes — so it could not be wired up as written — and that `degradation_history` is an unbounded list. Dimension 8's write-up follows.

<details><summary>BE8-08 (merged): The entire `monitoring/` package — memory-pressure monitoring and cache degradation — is dead; no cache ever shrinks under memory pressure</summary>

- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/monitoring/memory_monitor.py` (361 lines), `/mnt/data/src/matchering/auralis-web/backend/monitoring/metrics_collector.py` (575 lines), `/mnt/data/src/matchering/auralis-web/backend/monitoring/__init__.py:7-10`
- **Status**: NEW
- **Description**:
  `MemoryPressureMonitor` / `DegradationManager` implement a 4-level graceful
  degradation policy (shrink L1/L2/L3 caches, then pause the background worker).
  Nothing in the backend ever constructs or calls them. A repo-wide grep for
  `from monitoring` / `import monitoring` returns exactly one hit, and it is a test.
- **Evidence**:
  ```
  $ grep -rn "from monitoring\|import monitoring\|backend.monitoring" --include="*.py" .
  tests/backend/test_memory_monitor.py:20:from monitoring.memory_monitor import DegradationManager, MemoryPressureMonitor, MemoryStatus
  ```
  `monitoring/__init__.py` only lists module names in `__all__`; it imports nothing:
  ```python
  __all__ = [
      'metrics_collector',
      'memory_monitor',
  ]
  ```
  `config/startup.py` never references it (grep for `memory_monitor` in
  `auralis-web/backend/` outside the package returns only `metrics_collector.py`'s
  own constructor parameter). `DegradationManager.apply_degradation()` also targets a
  `buffer_manager` with `l1_cache/l2_cache/l3_cache` attributes that no live object in
  the backend exposes — so it could not be wired up as written.
- **Impact**:
  The backend's memory ceiling is entirely static: `SimpleChunkCache` 512 MB
  (`core/chunk_cache.py:32`), `TIER2_MAX_SIZE_MB = 240` (`cache/manager.py:58`), SQLite
  page cache up to 640 MB (see BE8-09), plus up to 10 concurrent streams. Under
  real memory pressure nothing backs off, and the test suite gives false confidence
  that a degradation policy exists. Secondary: ~936 lines of unmaintained code that
  reads as live infrastructure.
- **Siblings**:
  `DegradationManager.degradation_history` (`monitoring/memory_monitor.py:214`, appended
  at `:279`) is an unbounded list, unlike its sibling `status_history` (capped at 100 at
  `:149-150`) and `worker_latency_samples` (capped at 100 at `:256-257`) — latent, since
  the class is dead.
- **Suggested Fix**:
  Either wire `get_memory_monitor()` into the lifespan and give `DegradationManager` a
  real target (the `StreamlinedCacheManager` tier sizes and `SimpleChunkCache.max_chunks`
  / `_max_memory_bytes`), or delete `monitoring/` and its test. Do not leave it in the
  middle.

</details>

---

### BE7-2: Every audio-load failure collapses into "An unexpected error occurred" — `_ERROR_CATEGORIES` never matches the exception the loader actually raises

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/processing_engine.py:55-81`; raise sites in `/mnt/data/src/matchering/auralis/io/unified_loader.py:68,73,81,101` and `/mnt/data/src/matchering/auralis/io/loaders/ffmpeg_loader.py:373,398-407`
- **Status**: NEW
- **Description**:
  `_safe_error_message()` maps exception types to user-safe strings and is the *only* thing the client ever sees for a failed job (`routers/processing_api.py:317` returns `job.error_message`) and for a failed upload (`routers/files.py:251,268`) and for three WebSocket streaming error frames (`routers/system.py:142,191,263`). Its table keys on `FileNotFoundError`, `PermissionError`, `OSError`, `ValueError`, `MemoryError`. But `auralis/io/unified_loader.load_audio()` — the single entry point for all decoding — raises `ModuleError` (a bare `Exception` subclass, `auralis/utils/logging.py:73`) for *every* failure mode: missing file, empty file, unsupported extension, over-duration, FFmpeg non-zero exit, FFmpeg timeout, truncated file. `ModuleError` matches none of the five categories, so all of them fall through to the catch-all.
- **Evidence**:
  ```python
  # core/processing_engine.py:57-63
  _ERROR_CATEGORIES: list[tuple[type[BaseException], str]] = [
      (FileNotFoundError, "Audio file not found"),
      (PermissionError, "Permission denied accessing audio file"),
      (OSError, "Audio file could not be read"),
      (ValueError, "Invalid audio data or parameters"),
      (MemoryError, "Insufficient memory to process audio"),
  ]
  ```
  ```python
  # auralis/io/unified_loader.py:67-81
  if not file_path.exists():
      raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")
  ...
  if file_ext not in SUPPORTED_FORMATS:
      raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: {file_ext}")
  ```
  The `FileNotFoundError` entry — the most specific and most reassuring message in the table — is therefore unreachable from the job path: `load_audio` checks `exists()` itself and raises `ModuleError` before Python could raise `FileNotFoundError`.
- **Impact**:
  A user who drops in a corrupt MP3, an unsupported format, or a file whose FFmpeg decode failed sees exactly the same opaque string as a genuine internal defect: "An unexpected error occurred during processing". There is no way for the frontend to distinguish a user-fixable input problem (4xx-class) from a server defect (5xx-class), and the same string is used for the WS `audio_stream_error.error` field, so streaming has the same blind spot. It also hides real regressions: an `AttributeError` in the pipeline is indistinguishable from a bad input file.
- **Siblings**:
  `routers/files.py:251` and `:268`; `routers/system.py:142`, `:191`, `:263` — all five consume `_safe_error_message` and inherit the collapse.
- **Suggested Fix**:
  Add `ModuleError` handling that reads the `Code.*` prefix already embedded in the message (`ERROR_FILE_NOT_FOUND`, `ERROR_EMPTY_FILE`, `ERROR_UNSUPPORTED_FORMAT`, `ERROR_FFMPEG_TIMEOUT`, `ERROR_TRUNCATED_FILE`, `ERROR_CORRUPTED`) and map each to a distinct safe message. Do **not** pass the raw `ModuleError` text through — see BE7-3, it embeds absolute paths and raw FFmpeg stderr.

---

### BE7-6: An exception in any WebSocket message handler tears down the whole connection and sends the client nothing

- **Severity**: MEDIUM
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/system.py:332-364`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/connection.py:102-139`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/playback_commands.py:234`, `:290`
- **Status**: NEW
- **Description**:
  The `/ws` receive loop dispatches each message via `ws_connection.dispatch_message(...)` with no per-message guard. `dispatch_message` itself has none, and `handle_play_normal` / `handle_seek` / `handle_pause` / `handle_resume` / `handle_buffer_*` / `handle_stop` have no top-level try/except either. Any exception raised inside a handler unwinds all the way to `except Exception as e:` at `system.py:358`, which logs and falls into `finally: teardown_connection(...)` — and `teardown_connection` never sends anything on the socket. The client observes an abrupt close with no `error` or `audio_stream_error` frame.
- **Evidence**:
  ```python
  # routers/system.py:350-364
                  await ws_connection.dispatch_message(
                      websocket, message, state, deps, heartbeat, connection_id, subscribed_job_ids
                  )
          except WebSocketDisconnect:
              logger.info("WebSocket client disconnected normally")
          except RuntimeError as e:
              logger.warning(f"WebSocket runtime error: {e}")
          except Exception as e:
              logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
          finally:
              await ws_connection.teardown_connection(...)
  ```
  Compare the *validation* failures, which are correctly contained and reported: rate limit (`system.py:342` `send_error_response(...)` then `continue`), malformed payload (`:346-348`), unknown type (`messages.py:88`), bad `job_id` (`messages.py:52`), bad `track_id` (`playback_commands.py:114`). Only the *unexpected* failures lose both the frame and the connection.
- **Impact**:
  Every failure mode that is not an anticipated validation error degrades from "one command failed" to "the whole session died silently". Because the streaming tasks are keyed on `ws_id`, teardown cancels the active stream too, so a transient handler bug stops playback with no explanation on the wire. The frontend's reconnect path treats this as a network drop, which is the wrong diagnosis and hides the defect.
- **Siblings**:
  `setup_connection` runs *before* the `try` (`system.py:307-309`); if `manager.connect()` or the two initial sync pushes raise after `accept()`, `teardown_connection` never runs at all and the spawned `heartbeat_task` leaks for the process lifetime.
- **Suggested Fix**:
  Wrap the `dispatch_message` call in its own `try/except Exception`, emit `send_error_response(websocket, "internal_error", "Command failed")` (never the raw exception text), and `continue` the loop. Keep the outer handler for genuinely fatal transport errors. Separately, move `setup_connection` inside the `try` (or give it its own `try/except` that cancels `heartbeat_task`).

> **Merged duplicate — BE2-09.** Same root cause found from the other angle by Dimension 2: `dispatch_message` has no per-handler try/except (this finding), AND the control handlers emit via bare `websocket.send_text` with no `safe_send` guard, which is the most likely *source* of the exception (Dimension 2's write-up follows). One fix addresses both.

<details><summary>BE2-09 (merged): Control handlers use raw `websocket.send_text` with no guard, so a send failure kills the receive loop</summary>

- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/playback_control.py:34,44,81`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/messages.py:30`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/playback_commands.py:341-344`; dispatcher `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/connection.py:102-139`
- **Status**: NEW
- **Description**: `dispatch_message` has no per-handler try/except. `handle_pause`, `handle_resume`, `handle_stop`, `handle_ping`, and `handle_seek`'s `seek_started` emit via bare `websocket.send_text(...)`, unlike the streaming layer which routes everything through `safe_send`. Any `RuntimeError` from those propagates out of the `while True` loop into `except RuntimeError` at `system.py:356` and terminates the connection.
- **Evidence**:
```python
# playback_control.py:81
    await websocket.send_text(json.dumps({"type": "playback_stopped", "data": {"state": "stopped"}}))
```
```python
# playback_commands.py:341-344
    await websocket.send_text(json.dumps({
        "type": "seek_started",
        "data": {"track_id": track_id, "position": position},
    }))
```
- **Impact**: In `handle_seek` the failure occurs *after* the prior task was cancelled and *before* the new task is created (lines 321-339 vs 353-373), so the connection dies with playback stopped and no stream. Mostly overlaps a genuine disconnect, hence LOW.
- **Suggested Fix**: Route these through `stream_protocol.safe_send`, and wrap the `dispatch_message` call in a per-message try/except.

</details>

---

### BE8-09: `GET /api/albums` eager-loads every Track row of every album on the page only to `SUM(duration)` and `len()` them


- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis/library/repositories/album_repository.py:94-100` (also `:38`, `:56`, `:116`, `:168`), consumed at `/mnt/data/src/matchering/auralis-web/backend/routers/serializers.py:204-224`
- **Status**: NEW — the last un-migrated sibling of #4553 (artists, CLOSED) and #4554 (playlists, CLOSED)
- **Description**:
  The album list endpoint pages 50 albums and `selectinload`s each album's full
  `tracks` collection. The serializer never uses a Track for anything except
  `sum(track.duration)` and `len(album.tracks)`. `ArtistRepository.get_all` and
  `PlaylistRepository.get_all` were both converted to correlated `COUNT`/`SUM`
  scalar subqueries for exactly this reason; `AlbumRepository` was not.
- **Evidence**:
  `auralis/library/repositories/album_repository.py:94-100`
  ```python
              albums = session.execute(
                  select(Album)
                  .options(joinedload(Album.artist), selectinload(Album.tracks))
                  .order_by(order_column.asc())
                  .limit(limit)
                  .offset(offset)
              ).scalars().unique().all()
  ```
  `routers/serializers.py:204-224` — the only two reads of `album.tracks`:
  ```python
      if hasattr(album, 'tracks') and album.tracks:
          try:
              total_duration = sum(
                  track.duration for track in album.tracks
                  ...
      if 'track_count' not in album_dict or album_dict['track_count'] == 0:
          try:
              album_dict['track_count'] = len(album.tracks) if hasattr(album, 'tracks') else 0
  ```
  Compare the already-fixed peer, `playlist_repository.py:163-189`, which builds
  `track_count` / `total_duration` as `scalar_subquery()` + `with_expression(...)`
  and loads no Track rows at all.
- **Impact**:
  A 50-album page on a library averaging 12 tracks/album pulls ~600 **full** Track
  rows across the wire from SQLite — including the `Text` columns `comments` and
  `lyrics` (`auralis/library/models/core.py:123-124`), which can be kilobytes each.
  Cost scales with tracks-per-album rather than page size, and the rows are then
  discarded. This is the album grid, i.e. the app's default landing view.
- **Siblings** (same repository, same pattern):
  - `album_repository.py:38` `get_by_id`, `:56` `get_by_name` — justified there (detail view reads tracks).
  - `album_repository.py:116` `get_recent`, `:168` `search` — same waste as `get_all`; `search` backs `GET /api/albums?search=`.
  - `album_repository.py:194` `selectinload(Album.tracks)` — check the caller before changing.
- **Suggested Fix**:
  Port the `playlist_repository.get_all` pattern: two correlated scalar subqueries
  (`COUNT` over `Track.album_id == Album.id`, `COALESCE(SUM(Track.duration), 0)`)
  surfaced via `with_expression`, and drop `selectinload(Album.tracks)` from the
  list/search/recent paths. Then teach `serialize_album` to prefer the expression
  values (it already prefers a pre-set `track_count`).

---

### BE8-10: SQLite is configured for a 64 MB page cache **per connection** across a 10-connection pool — a 640 MB ceiling on a desktop app


- **Severity**: MEDIUM
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis/library/database.py:127-164`
- **Status**: NEW
- **Description**:
  `PRAGMA cache_size=-65536` sets a 64 MiB page cache. SQLite applies that
  **per connection**, and the pool is `pool_size=5, max_overflow=5` = up to 10
  connections, each of which gets the pragma from the `connect` event listener.
  The inline comment ("reasonable for up to 10 connections") reads as if 64 MB were
  the aggregate; it is the per-connection figure, so the true worst case is 640 MB
  of retained page cache, held for the process lifetime because pooled connections
  are not recycled.
- **Evidence**:
  `auralis/library/database.py:127-134`
  ```python
          self.engine: Engine | None = create_engine(
              f"sqlite:///{database_path}",
              echo=False,
              connect_args=connect_args,
              pool_pre_ping=True,  # Verify connections before use
              pool_size=5,  # Sufficient for SQLite with WAL concurrent readers
              max_overflow=5,  # Up to 10 total connections
          )
  ```
  `auralis/library/database.py:154-155`
  ```python
              # 64MB page cache per connection (reasonable for up to 10 connections)
              cursor.execute("PRAGMA cache_size=-65536")  # 64MB cache per connection
  ```
  No `pool_recycle` is set, so overflow connections above `pool_size` are returned
  and closed, but the 5 pooled ones retain their caches indefinitely (≥ 320 MB
  steady-state after a full scan touches enough pages).
- **Impact**:
  Stacked on the other static ceilings — `SimpleChunkCache` 512 MB
  (`auralis-web/backend/core/chunk_cache.py:32`), `TIER2_MAX_SIZE_MB = 240`
  (`auralis-web/backend/cache/manager.py:58`), up to 10 concurrent streams each
  holding a `ChunkedAudioProcessor` — and with no live memory-pressure feedback
  (BE8-08), the process can comfortably sit at well over 1 GB RSS on a machine
  where the user only wanted a music player. A library scan is the reliable way to
  fill the page caches.
- **Siblings**:
  `auralis/analysis/fingerprint/fingerprint_service.py:47-63` creates a **second**
  engine with `pool_pre_ping=True` but *no* `pool_size`/`max_overflow` (so SQLAlchemy
  defaults: 5 + 10 = 15 more connections) — it does not set `cache_size`, so it
  avoids this specific problem, but it does add to the connection count against the
  same SQLite file.
- **Suggested Fix**:
  Drop to something like `PRAGMA cache_size=-8192` (8 MiB/conn, 80 MB worst case),
  or scale it by `pool_size` so the documented aggregate is the real aggregate.
  Either way, fix the comment so the next reader is not misled.

---

### BE9-02: The only two tests asserting the streaming-semaphore release invariant are dead — they reference `AudioStreamController.active_streams`, which does not exist

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/backend/test_audio_stream_lifecycle.py:250-262`, `:321-334`, `:443-458`
- **Status**: NEW
- **Description**: Check 9 (stale mocks/attributes after a refactor). Three tests assert `TRACK_ID not in ctrl.active_streams`. `grep -rn "active_streams" auralis-web/backend/` returns **nothing** — the attribute was removed and never re-added. Because the `active_streams` assert is placed *before* the semaphore assert, the `AttributeError` means the semaphore check on the line below never executes.
- **Evidence**:
  - `tests/backend/test_audio_stream_lifecycle.py:250-262`
    ```python
    async def test_cleanup_on_success(self):
        """On success: active_streams entry removed, semaphore returned."""
        ...
            initial_value = ctrl._stream_semaphore._value
            await ctrl.stream_enhanced_audio(...)

        assert TRACK_ID not in ctrl.active_streams        # AttributeError here
        assert ctrl._stream_semaphore._value == initial_value   # never reached
    ```
  - Identical shape at `:333-334` (`test_chunk_failure_cleans_up`) and `:457-458` (normal path).
  - CI confirms: `FAILED tests/backend/test_audio_stream_lifecycle.py::TestStreamEnhancedAudioLifecycle::test_cleanup_on_success - AttributeError: 'AudioStreamController' object has no attribute 'active_streams'`.
  - `auralis-web/backend/core/audio_stream_controller.py:160-208` — the full `__init__`; the only stream-tracking state is `self._stream_semaphore = _global_stream_semaphore` at `:208`.
- **Impact**: Backend invariant #7 ("the enhanced and normal streaming paths release their semaphores in `finally` blocks; all early-exit paths must remain accounted for") has **no working test on either the success path or the chunk-failure path**. A semaphore leak on either path would exhaust `MAX_CONCURRENT_STREAMS` and wedge all playback, and nothing in the suite would catch it. `test_stream_semaphore_cancel_leak.py` covers only the cancellation path.
- **Siblings**: Same file, `test_happy_path_message_order` (`TestStreamEnhancedAudioLifecycle`) asserts `"audio_chunk" in types` while the controller now emits `audio_chunk_meta` — the WebSocket message-order contract test is stale in the same refactor. `TestStreamNormalAudioLifecycle::test_stream_start_has_preset_none` fails with `RuntimeError: coroutine raised StopIteration` (a mock exhausted by a changed call count). 8 of this file's tests are red.
- **Suggested Fix**: Reorder so the semaphore assertion runs first, then either delete the `active_streams` assertion or replace it with the real post-condition. Update the message-type expectations to `audio_chunk_meta` + binary frame.

---

### BE9-03: The entire WebSocket-endpoint test suite (42 tests) is excluded from CI, and the version that *does* run is assertion-free and sends the wrong payload shape

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/backend/test_main_api.py:714-723`; `/mnt/data/src/matchering/.github/workflows/backend-tests.yml:104-107`; `/mnt/data/src/matchering/tests/backend/test_system_api.py:753-770`
- **Status**: NEW
- **Description**: `tests/backend/test_system_api.py` — the only file that exercises the `/ws` endpoint end-to-end through `TestClient.websocket_connect` — is `--ignore`d by the workflow because it hangs. `pytest --collect-only -q tests/backend/test_system_api.py` reports **42 tests collected**; none of them ever run in CI. The `/ws` tests that *do* run live in `test_main_api.py`, and the job-progress one has **zero assertions** while sending a payload the handler cannot read.
- **Evidence**:
  - `tests/backend/test_main_api.py:714-723`:
    ```python
    def test_websocket_subscribe_job_progress(self, client):
        """Test subscribing to job progress updates"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "type": "subscribe_job_progress",
                "job_id": "test-job-123"
            })

            # Test passes if no exception is raised
            # The WebSocket remains open and functional
    ```
    No `assert` in the body. And `auralis-web/backend/ws_handlers/messages.py:45-52` reads the id from the **nested** envelope:
    ```python
    data = message.get("data", {})
    job_id = data.get("job_id")
    if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
        await send_error_response(websocket, "invalid_job_id", ...)
        return
    ```
    A top-level `job_id` yields `data == {}` → `job_id is None` → the handler takes the **rejection** branch. So the test named "subscribe to job progress updates" actually only ever exercises `invalid_job_id`, and cannot fail either way.
  - `tests/backend/test_system_api.py:741-742` shows someone already diagnosed exactly this — *"the original top-level `job_id`: ... was never read by the handler either"* — and fixed it in `test_system_api.py:753-770` with a real `mock_engine.register_progress_callback.assert_awaited_once()`. That corrected test is in the CI-excluded file.
- **Impact**: The `/ws` endpoint is the transport for **all** playback in this app (there is no REST streaming router). Its connect/dispatch/disconnect lifecycle, `subscribe_job_progress` registration, and the `#3826` self-unregister-after-disconnect fix are verified by exactly zero CI-executed assertions. Two separate WS behaviours are covered only by the stale, vacuous copy.
- **Siblings**: Same exclusion hides `tests/concurrency/test_thread_safety.py` (25 collected tests). Per-handler grep shows `handle_ping`, `handle_pong`, `handle_heartbeat` and `handle_subscribe_job_progress` in `ws_handlers/messages.py` have **no** test importing them directly — only `handle_unknown` does (`tests/security/test_websocket_security.py`).
- **Suggested Fix**: Fix the hang in `test_system_api.py` (likely an un-drained WS receive) so the 42 tests re-enter CI, and delete or repair `test_main_api.py:714`. Until then the file's exclusion should be treated as a coverage hole, not a workaround.

---

### BE9-04: ~70 endpoint assertions accept 3-5 different status codes, including the 500 they are meant to rule out

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/backend/test_player_api_comprehensive.py` (20 sites), `test_metadata_api.py` (13), `test_artists_api.py` (8), `test_similarity_api_new.py` (8), `test_files_api.py` (3), `test_main_api.py` (3), and others
- **Status**: NEW
- **Description**: Check 8 (assertions that cannot fail). A large block of the router tests assert membership in a set that spans success *and* server error, so the endpoint can 500 and the test still passes. This is the mechanism by which a router can rot silently while its test file stays green.
- **Evidence** (exact lines):
  - `tests/backend/test_player_api_comprehensive.py:382` — `assert response.status_code in [200, 400, 422, 500]` — no realistic response is excluded.
  - `tests/backend/test_artists_api.py:84,99,110,121,131,141,147,463` — eight consecutive `assert response.status_code in [200, 500, 503]`. A router that unconditionally raised would pass all eight.
  - `tests/backend/test_metadata_api.py:112,143,219,243,381,398,418,433,450,472,473,499` — twelve `assert ... in [400, 404, 500]`, i.e. "any error is fine".
  - `tests/backend/test_files_api.py:356` — `assert response.status_code in [400, 403, 404, 422, 500]` (five-way).
  - `tests/backend/test_similarity_api_new.py:124` — `assert response.status_code in [200, 400, 404, 500]`.
  - `tests/backend/test_main_api.py:605` — `assert response.status_code in [200, 404, 500, 503]`.
  - Empirically this is not theoretical: `tests/backend/test_albums_api.py::TestGetAlbumFingerprint::test_fingerprint_success` uses a tight `assert 500 == 200` and *does* catch the regression, while the loose neighbours in the same tree hide theirs.
- **Impact**: Roughly 70 assertions across 11 router test files provide no regression signal. Combined with BE9-01 (the gate never runs), the practical coverage of the REST surface is materially lower than the 188-file `tests/backend/` tree suggests. This directly weakens the audit's other dimensions: several defects reported elsewhere in this audit (e.g. BE1-03 "similarity routes 500 instead of 503") sit under assertions that explicitly allow both codes — `test_similarity_api_new.py:81` is `in [400, 404, 500]`.
- **Siblings**: The pattern is copy-pasted; `test_metadata_api.py` and `test_artists_api.py` each use a single tuple throughout the file.
- **Suggested Fix**: Split each into the specific expected code per scenario. At minimum, mechanically strip `500` and `503` from every membership list that also contains `200` — an endpoint under test should never be permitted to 500.

---

### BE9-05: Six pagination-invariant tests are structurally guaranteed to skip — they request an empty fixture and then skip when it is empty

- **Severity**: MEDIUM
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/backend/test_library_pagination_invariants.py:387-397`, `:421-428`, `:450-458`, `:552-568`, `:777-795`, `:819-837`
- **Status**: NEW
- **Description**: Check 8 (tests that cannot fail). The file defines a `populated_db` fixture that inserts 100 tracks (`:81-119`), and separate bare `album_repo` / `artist_repo` fixtures that wrap a **fresh empty in-memory SQLite** (`:54-78`). Three album/artist tests request the *bare* fixture and then `pytest.skip` on `total == 0` — a condition that is always true. Three more request `populated_db`, but `populated_db` never sets `is_favorite` or `play_count`, so their "no favorites"/"no popular tracks" guards are also always true.
- **Evidence**:
  - `:54-61` — `test_db` is `create_engine('sqlite:///:memory:')` + `Base.metadata.create_all`; nothing inserted.
  - `:69-72` — `album_repo(test_db)` → `AlbumRepository(test_db)`; still empty.
  - `:387-397`:
    ```python
    def test_album_pagination_completeness(album_repo):
        _, total = album_repo.get_all(limit=1, offset=0)
        if total == 0:
            pytest.skip("No albums in test database")
    ```
  - `:101-113` — the `populated_db` track dicts carry `filepath/title/artists/album/duration/sample_rate/channels/format/track_number/year` and **no** `is_favorite` or `play_count`, so `:568` ("No favorites to test"), `:795` ("No popular tracks to test") and `:837` ("Need at least 2 popular tracks") always fire.
- **Impact**: Six tests whose names claim to guard the *critical* pagination invariants (completeness, ordering, total-count consistency) report as `skipped`, i.e. neither green nor red, and contribute to the 269 skips in the CI run. Off-by-one errors in album/artist/favorites/popular pagination — exactly what `tracks.py`, `albums.py` and `artists.py` do on every browse request — are unguarded.
- **Siblings**: `:923` `pytest.skip("Known limitation: offset-based pagination not consistent with concurrent writes")` is an unconditional skip at the top of a test body — a documentation comment wearing a test's clothes. `tests/backend/test_api_endpoint_integration.py` has ten `pytest.skip("No tracks available...")` guards with the same structure.
- **Suggested Fix**: Point the album/artist tests at `populated_db` (which does create 20 albums / 10 artists) and extend the fixture to flag some tracks favorite and give some a non-zero play count. Convert `:923` to `@pytest.mark.xfail(strict=True, reason=...)` or delete it.

---


## Low severity (48)

### BE1-5: Playlist `DELETE` routes are not idempotent — a repeated delete 404s, contrary to the convention the artwork router was explicitly fixed to follow

- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/playlists.py:238-267, 391-422`
- **Status**: NEW
- **Description**: `DELETE /api/playlists/{playlist_id}` and
  `DELETE /api/playlists/{playlist_id}/tracks/{track_id}` raise `NotFoundError` whenever the repository
  returns falsy, which includes the "already deleted" case. Per RFC 7231 §4.3.5 a repeat DELETE should
  leave the resource absent and report success. `artwork.py:378-412` was explicitly changed for this
  reason (#3563) and now only 404s when the *parent* album is missing. The playlist routes were not
  brought along, so the two DELETE surfaces in the same backend behave differently.
- **Evidence**:
```python
# routers/playlists.py:253-257
        repos = require_repository_factory(get_repository_factory)
        success = await asyncio.to_thread(repos.playlists.delete, playlist_id)

        if not success:
            raise NotFoundError("Playlist")
```
```python
# routers/artwork.py:394-403  — the convention this should match
        # Idempotent DELETE per RFC 7231 §4.3.5 — a repeat call after a
        # successful delete should NOT 404 (#3563 / BE-NEW-105).
        album = await asyncio.to_thread(repos.albums.get_by_id, album_id)
        if album is None:
            raise NotFoundError("Album", album_id)
        success = await asyncio.to_thread(repos.albums.delete_artwork, album_id)
```
- **Impact**: A double-click on a playlist delete button, or a retry after a network timeout where the
  first request actually succeeded, surfaces a spurious "Playlist not found" error toast even though the
  user's intent was fully satisfied. Same for removing a track from a playlist twice.
  `DELETE /api/playlists/{id}/tracks` (clear) is already idempotent because `PlaylistRepository.clear`
  returns `True` for an already-empty existing playlist — so the three sibling routes are mutually
  inconsistent.
- **Siblings**: `DELETE /api/cache/track/{track_id}` (`cache_streamlined.py:135-144`) and
  `DELETE /api/similarity/graph` (`similarity_graph.py:107-122`) are both correctly idempotent.
- **Suggested Fix**: Mirror the artwork pattern — 404 only when the playlist itself does not exist, and
  return success when the target was already absent.

---

### BE1-6: Five `processing_api` handlers have no error handling at all, so an engine-layer exception escapes as an unhandled 500 instead of an `HTTPException`

- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/processing_api.py:302-319, 322-364, 367-382, 385-413, 416-423`
- **Status**: NEW
- **Description**: `get_job_status`, `download_result`, `cancel_job`, `list_jobs` and `get_queue_status`
  guard only the "engine is None" case with a 503 and then call into `ProcessingEngine` unprotected. The
  two sibling routes in the same file (`process_audio`, `upload_and_process`) do wrap their bodies in
  `try/except HTTPException: raise / except Exception: → 500`, and every other router in the backend uses
  either that shape or the `@with_error_handling` / `@_with_similarity_error_handling` decorator. A
  concrete reachable path: `download_result` does `Path(job.output_path).resolve()` with no `None` guard —
  a job that reached `COMPLETED` through any path that did not set `output_path` raises `TypeError`
  rather than a typed 4xx/5xx.
- **Evidence**:
```python
# routers/processing_api.py:332-339 — no try/except anywhere in this handler
        job = await engine.get_job(job_id)
        if not job:
            raise NotFoundError("Job")

        if job.status != ProcessingStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Job not completed (status: {job.status.value})")

        output_path = Path(job.output_path).resolve()
```
- **Impact**: Inconsistent error contract — these five endpoints produce Starlette's bare
  `Internal Server Error` with no logged operation context, while the rest of the API produces a
  `{"detail": "..."}` body and an `exc_info` log line. Low user impact because the failure modes are
  narrow, but it defeats the error-handling convention the rest of the backend follows and makes
  incident triage harder.
- **Siblings**: `cache_streamlined.py` covers all five of its handlers; `fingerprint_queue.py` and
  `similarity*.py` cover all of theirs via the shared decorator.
- **Suggested Fix**: Apply `@with_error_handling("...")` to all five handlers (it already re-raises
  `HTTPException` untouched, so the existing 404/400/503 paths are preserved), and add an explicit
  `if not job.output_path` guard in `download_result`.

---

### BE1-7: `cache/endpoints.py` is in the routed surface but registers zero endpoints and has no importers

- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/cache/endpoints.py:1-344`
- **Status**: NEW
- **Description**: The module is named and documented as "Cache-Aware Endpoint Helpers" and is the only
  non-`routers/` file in the HTTP surface, but it defines no `APIRouter` and no route decorator. Its four
  public symbols — `CacheAwareEndpoint`, `CacheQueryBuilder`, `EndpointMetrics`,
  `create_cache_aware_handler` — have no importer anywhere in the repository. All real cache endpoints
  live in `routers/cache_streamlined.py`, which does not reference this module.
- **Evidence**: `grep -rn "CacheAwareEndpoint\|create_cache_aware_handler\|CacheQueryBuilder\|EndpointMetrics"`
  over the repo returns hits only inside `cache/endpoints.py` itself. The module contains no
  `@router.` decorator and no `APIRouter(` construction.
- **Impact**: No runtime effect. It is 344 lines of dead cross-layer surface that reads as live HTTP
  plumbing — it invents a second response envelope
  (`{"data", "cache_source", "cache_hit", "processing_time_ms"}`) that no backend route emits, which is
  the shape the frontend's `CacheAwareAPIClient.getChunk()` still parses against the equally
  non-existent `/api/chunks/{trackId}/{chunkIndex}`. Anyone reading either side concludes a chunk REST
  API exists.
- **Siblings**: Frontend counterpart `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:413-432`
  (`CacheAwareAPIClient.getChunk`, no caller). Both are residue of the retired REST/MSE chunk surface
  (`routers/wav_streaming.py`, removed in #4435).
- **Suggested Fix**: Delete `cache/endpoints.py` and `CacheAwareAPIClient.getChunk` together, as the
  #4435 retirement did for the router itself.

> **Merged duplicate — BE5B-N7.** Independently found by Dimension 5b from the frontend contract side. Dimension 5b's write-up follows.

<details><summary>BE5B-N7 (merged): `CacheAwareAPIClient.getChunk()` and `cache/endpoints.py` describe a `{data, cache_source, cache_hit, processing_time_ms}` contract on `/api/chunks/{id}/{idx}` — a route that exists on neither side</summary>

- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Frontend: `/mnt/data/src/matchering/auralis-web/frontend/src/services/api/standardizedAPIClient.ts:415-432`, envelope type at `:23-30` (`SuccessResponse`)
  - Backend: `/mnt/data/src/matchering/auralis-web/backend/cache/endpoints.py:45-84` (`CacheAwareEndpoint.track_request`), `:298-344` (`create_cache_aware_handler`)
- **Status**: NEW
- **Description**:
  Both sides of a cache-aware chunk API were written and neither was ever wired up.
  Server side: `cache/endpoints.py` builds exactly
  `{"data": …, "cache_source": …, "cache_hit": …, "processing_time_ms": …}`. Its four
  public symbols are re-exported from `cache/__init__.py:17-20,63-66` and imported by
  nothing except `tests/backend/test_cache_endpoints.py`. No router imports the
  module.
  Client side: `getChunk()` requests `/api/chunks/${trackId}/${chunkIndex}` and reads
  `response.cache_source` / `response.processing_time_ms` off the `SuccessResponse`
  envelope. `grep -rn "api/chunks" auralis-web/backend --include='*.py'` returns
  nothing — there is no such route (live playback is WebSocket-only since the
  `/api/stream/*` REST surface was retired in #4435). `getChunk` itself is called
  only from `services/api/__tests__/standardizedAPIClient.test.ts:412`.
- **Evidence**:
  `cache/endpoints.py:72-77`:
  ```python
  return {
      "data": data,
      "cache_source": cache_source,
      "cache_hit": cache_source != "miss",
      "processing_time_ms": round(processing_time_ms, 2)
  }
  ```
  `services/api/standardizedAPIClient.ts:419-427`:
  ```ts
  const endpoint = `/api/chunks/${trackId}/${chunkIndex}`;
  const response = await this.apiClient.get(endpoint, { cache: true });
  if (isSuccessResponse(response)) {
    return {
      data: response.data,
      cacheSource: response.cache_source ?? 'miss',
      ...
  ```
- **Impact**:
  No runtime effect — the call is unreachable from production code. The cost is that
  `SuccessResponse<T>` (`status`/`data`/`timestamp`/`cache_source`/`processing_time_ms`)
  still reads as "the shape this backend returns", which is precisely the wrong
  mental model that produced #4440; the fix for #4440 added `unwrapCachePayload` for
  the two *live* cache endpoints and left `getChunk` and the envelope type standing.
  `tests/backend/test_cache_endpoints.py` and the `getChunk` spec both pass, so the
  contract looks covered.
- **Siblings**: `CacheQueryBuilder` and `EndpointMetrics` in the same module are dead
  by the same measure; `EndpointMetrics.get_tier_stats()` emits a `hit_rate` key its
  own docstring does not mention and nothing reads.
- **Related**: #4440 (CLOSED, the live half of this envelope problem); #4435
  (the retired REST streaming surface); BE5B-N1 (the `schemas.py` orphan cluster).
- **Suggested Fix**: Delete `getChunk()` and the `cache_source` /
  `processing_time_ms` fields from `SuccessResponse`, and delete
  `cache/endpoints.py` with its `cache/__init__.py` re-exports and test — or, if a
  chunk endpoint is genuinely planned, implement it and wire the helper into it.
  Do not leave a two-sided contract for a route that does not exist.

</details>

---

### BE1-8: `ENDPOINTS.PLAYER_PLAY` / `PLAYER_PAUSE` / `PLAYER_STOP` / `ENHANCEMENT_SETTINGS` name backend routes that do not exist

- **Severity**: LOW
- **Dimension**: Route Handlers
- **Location**: `/mnt/data/src/matchering/auralis-web/frontend/src/config/api.ts:62, 84-86`
- **Status**: NEW
- **Description**: The centralized endpoint registry — explicitly documented as "Use these constants
  instead of hardcoding endpoint strings" — declares `/api/player/play`, `/api/player/pause`,
  `/api/player/stop` and `/api/settings/enhancement`. None of these are registered by any router:
  `player.py` exposes only `status`, `load`, `seek`, `volume`, the queue family, `next` and `previous`
  (transport play/pause/stop is WebSocket-only, per the module docstring), and the enhancement settings
  live under `/api/player/enhancement/*`, not `/api/settings/enhancement`.
- **Evidence**:
```typescript
// frontend/src/config/api.ts:84-86
  PLAYER_PLAY: '/api/player/play',
  PLAYER_PAUSE: '/api/player/pause',
  PLAYER_STOP: '/api/player/stop',
```
  `grep -rn "api/player/play\|api/player/pause\|api/player/stop\|api/settings/enhancement"` over
  `auralis-web/backend/` returns nothing.
- **Impact**: No live 404 today — I verified none of these four constants has a call site outside
  `src/test/mocks/handlers.ts` (which even mocks `POST /api/player/pause`, reinforcing the illusion).
  The risk is prospective: the file is the sanctioned place to look up an endpoint, so the next
  transport-control change is likely to reach for `ENDPOINTS.PLAYER_PAUSE` and ship a 404. This is the
  same failure mode as #4658, where the frontend called two playlist endpoints the backend never
  registered.
- **Siblings**: `src/test/mocks/handlers.ts:43, 1212-1213` mock the non-existent pause route;
  `hooks/api/useRestAPI.ts:9-10, 141` use `/api/player/state`, `/api/player/play` and `/api/queue` in
  doc-comment examples, none of which exist (`/api/player/status` and `/api/player/queue` are the real
  paths).
- **Suggested Fix**: Delete the four dead constants and correct the `useRestAPI` doc examples, or add a
  contract test that asserts every literal in `ENDPOINTS` resolves against the generated OpenAPI paths.

---

### BE2-07: `subscribe_job_progress` is a single-slot global registry — one client's subscription evicts another's, and one client's disconnect unregisters it for everyone

- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/processing_engine.py:224-232`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/messages.py:43-78`; `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/connection.py:202-211`
- **Status**: NEW
- **Description**: `progress_callbacks` is a `dict[job_id, callback]`, not a set of subscribers.
- **Evidence**:
```python
# processing_engine.py:224-232
    async def register_progress_callback(self, job_id: str, callback: ...) -> None:
        async with self._jobs_lock:
            self.progress_callbacks[job_id] = callback      # ← overwrite, not append

    async def unregister_progress_callback(self, job_id: str) -> None:
        async with self._jobs_lock:
            self.progress_callbacks.pop(job_id, None)       # ← removes whoever owns it
```
`teardown_connection` unregisters every `job_id` in this connection's `subscribed_job_ids` unconditionally (`connection.py:204-211`), including ones now owned by a different live socket.
- **Impact**: With two clients, the second subscriber steals the first's `job_progress` stream, and either client's disconnect kills it for both. Single-client desktop deployment makes this near-unreachable in practice, hence LOW.
- **Suggested Fix**: Key on `(job_id, ws_id)` or store a set of callbacks per job.

---

### BE2-08: A single client-sent binary frame tears down the WebSocket with a `KeyError`

- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/system.py:336,358-364`
- **Status**: NEW
- **Description**: The receive loop calls `websocket.receive_text()` exclusively. Starlette's implementation does `return cast(str, message["text"])` with no type check, so a binary frame — which uvicorn queues as `{"type": "websocket.receive", "bytes": ...}` with no `"text"` key — raises `KeyError`, which falls to the endpoint's generic `except Exception`, logs "Unexpected WebSocket error", and runs teardown.
- **Evidence**: `starlette/websockets.py:116-121`:
```python
    async def receive_text(self) -> str:
        ...
        message = await self.receive()
        self._raise_on_disconnect(message)
        return cast(str, message["text"])
```
- **Impact**: Connection dropped with no `error` frame; the client only sees a close. No production exercise path (the frontend never sends binary), so LOW.
- **Suggested Fix**: Use `receive()` and branch on `"text" in message`, rejecting binary with `send_error_response`.

---

### BE2-10: Runtime `enhancement_settings` is process-global, so a second client's `play_enhanced` retargets the first client's seeks

- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/ws_handlers/playback_commands.py:154-155,312-315`; `/mnt/data/src/matchering/auralis-web/backend/config/routes.py:107`
- **Status**: NEW (adjacent to #4677 OPEN, which is about client-vs-stored precedence within one connection, not cross-connection clobbering)
- **Description**: `get_enhancement_settings` is `lambda: enhancement_settings` — one dict for the whole process. `handle_play_enhanced` **writes** the accepted preset/intensity into it, and `handle_seek` **reads** preset/intensity back out of it.
- **Evidence**:
```python
# playback_commands.py:154-155
        settings["preset"] = preset
        settings["intensity"] = intensity
```
```python
# playback_commands.py:312-315
    if deps.get_enhancement_settings is not None:
        settings = deps.get_enhancement_settings()
        preset = settings.get("preset", preset)
        intensity = settings.get("intensity", intensity)
```
- **Impact**: Client B starting a "punchy" stream rewrites the global; client A's next seek re-renders A's track with B's preset, and the mid-stream `get_enhancement_enabled` gate is likewise shared. Desktop-only single-client deployment makes this effectively unreachable, hence LOW — but the streaming state is otherwise correctly per-`ws_id`, so this is the one genuine cross-connection clobber.
- **Suggested Fix**: Carry preset/intensity on the stream task (already passed as kwargs) and stop round-tripping them through the global for `seek`.

---

### BE2-11: `/ws` is registered on a module-level `APIRouter` from inside a factory

- **Severity**: LOW
- **Dimension**: WebSocket Streaming
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/system.py:47,283-297,366`
- **Status**: NEW
- **Description**: `router = APIRouter(tags=["system"])` is module-level, but `@router.websocket("/ws")` is applied inside `create_system_router(...)`. A second call appends a second `/ws` route to the same shared object; the first registration wins at dispatch, so the second factory's `manager`, `get_enhancement_settings`, `get_cache_manager` etc. are captured in a closure that is never invoked.
- **Evidence**:
```python
# system.py:47
router = APIRouter(tags=["system"])
...
# system.py:283-297
def create_system_router(manager, get_processing_engine, HAS_AURALIS, ...) -> APIRouter:
    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
```
`config/routes.py:102-113` calls it exactly once in production, so this is latent — but it silently mis-wires tests and any future multi-app construction.
- **Impact**: Silent, hard-to-diagnose mis-wiring; route table grows on each call.
- **Suggested Fix**: Construct the `APIRouter` inside the factory.

---

### BE3-14: The "equal-power" chunk crossfade is not equal-power (it is linear-equivalent), and its #2080 regression test cannot detect the difference

- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_crossfade.py:53-56`; duplicated verbatim at `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:319-323`; guarded by `/mnt/data/src/matchering/tests/backend/test_equal_power_crossfade.py:20-70`
- **Status**: NEW
- **Description**:
  Both copies use `fade_out = cos(t)**2`, `fade_in = sin(t)**2`. That satisfies
  `fade_out + fade_in = 1` (amplitude-complementary — identical to a linear
  crossfade for correlated content) but `fade_out² + fade_in² = 0.5` at the
  midpoint, i.e. exactly the **−3.01 dB energy dip for uncorrelated content**
  that the comment claims it avoids. True equal-power is `cos(t)`/`sin(t)`.
- **Evidence**: measured on the actual curves —
  ```
  cos^2/sin^2 : fo+fi mid = 1.0000   fo^2+fi^2 mid = 0.5000 (-3.01 dB)
  linear      : fo+fi mid = 1.0000   fo^2+fi^2 mid = 0.5000 (-3.01 dB)
  true eq-pwr : fo+fi mid = 1.4142   fo^2+fi^2 mid = 1.0000 ( 0.00 dB)
  ```
  `core/chunk_crossfade.py:53-56`
  ```python
  # Create equal-power fade curves (sin²/cos²) to avoid energy dip at midpoint (fixes #2080)
  t = np.linspace(0.0, np.pi / 2, actual_overlap)
  fade_out = np.cos(t) ** 2
  fade_in = np.sin(t) ** 2
  ```
  The regression test's docstring states the equal-power invariant
  (`fade_out² + fade_in² ≈ 1`) but the assertion checks the *sum* is ~1.0, and its
  comment — `"Linear: at midpoint fade_out=fade_in=0.5 → sum = 0.5 (6 dB loss!)"`
  — is arithmetically wrong (linear also sums to 1.0). The test passes identically
  for linear, cos²/sin², and true equal-power: it is a vacuous guard.
- **Impact**: Currently **latent** — this is why the severity is LOW, not HIGH.
  `stream_chunk_ops.stream_processed_chunk` (lines 165-173) documents that no
  boundary crossfade is applied on the live path (#3514/#4642), and a repo-wide
  grep shows `apply_crossfade_between_chunks` / `ChunkOperations.apply_crossfade`
  have **zero production call sites** — only tests. The risk is that the
  mislabelled curve plus a green "equal-power" test invites a future re-enable
  under a false guarantee. Also a DRY/no-variants violation: two byte-identical
  implementations of the same function in two modules.
- **Siblings**: `chunk_operations.py:319-323` (identical body);
  `chunk_crossfade.py:13-16` already flags a third, unreconciled boundary
  implementation in `audio_stream_controller.py`.
- **Suggested Fix**: delete `ChunkOperations.apply_crossfade` (keep the
  `chunk_crossfade` module as the single copy); either switch to `cos(t)`/`sin(t)`
  or relabel the comment as "constant-amplitude (raised-cosine)"; and fix the test
  to assert `fade_out² + fade_in² ≈ 1` at several points, not just the sum at the midpoint.

---

### BE3-15: `ChunkBoundaryManager.get_segment_boundaries()` is dead code that encodes a chunk model contradicting the live one

- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_boundaries.py:259-303`
- **Status**: NEW
- **Description**:
  `get_segment_boundaries()` has no callers anywhere in `auralis-web/` or `tests/`
  (verified by grep). It also contradicts the model that `ChunkOperations.
  extract_chunk_segment` — the method actually used — implements: it offsets by
  `CONTEXT_DURATION` (assuming context is still attached, which `trim_context` has
  already removed) and emits `CHUNK_DURATION` (15 s) per regular chunk instead of
  `CHUNK_INTERVAL` (10 s) of new content. Its last-chunk arm also omits the
  `+ OVERLAP_DURATION` that `extract_chunk_segment:217` applies.
  Line 278 is a bare `self.get_overlap_samples()` whose return value is discarded —
  a leftover from a partially removed calculation.
- **Evidence**: `core/chunk_boundaries.py:277-297`
  ```python
  is_last = self.is_last_chunk(chunk_index)
  self.get_overlap_samples()                    # <- result discarded
  context_samples = round(CONTEXT_DURATION * self.sample_rate)
  ...
  else:
      segment_start = context_samples           # context already trimmed by trim_context
  ...
  else:
      # Regular chunk: extract CHUNK_DURATION
      segment_end = segment_start + chunk_duration_samples   # 15 s, not 10 s
  ```
- **Impact**: none at runtime. It is a trap: it lives in the file that is the
  declared single source of truth for chunk geometry, is named as though it were
  the canonical extractor, and would produce 1.5× overlapping output with a
  double-counted context offset if any future caller reached for it instead of
  `extract_chunk_segment`.
- **Siblings**: `ChunkOperations.get_chunk_time_range` (`chunk_operations.py:370-393`)
  is also uncalled and also returns the *core* (`start + chunk_duration`) window
  rather than the emitted one — same class of trap.
- **Suggested Fix**: delete both, or reimplement `get_segment_boundaries` by
  delegating to the same arithmetic `extract_chunk_segment` uses.

---

### BE3-16: `ChunkOperations` re-declares the chunk geometry as `int` defaults in four signatures

- **Severity**: LOW
- **Dimension**: Chunked Processing
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/chunk_operations.py:43-48, 161-165, 349, 373-374`
- **Status**: NEW (sibling of prior BE3-06, which covers only the `context_duration = 5.0` literal at line 87 — not re-filed here)
- **Description**:
  Four `ChunkOperations` signatures carry `chunk_duration: int = 15`,
  `chunk_interval: int = 10`, `overlap_duration: int = 5` as defaults. These are
  a fourth copy of the values `chunk_boundaries.py` declares as the SoT, and the
  `int` annotations contradict the SoT's `float` constants — every real call site
  (`chunked_processor.py:351-353, 566-568, 776-778`) passes the `float`
  `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION`, so the annotation is wrong
  at 100 % of call sites.
- **Evidence**: `core/chunk_operations.py:43-48`
  ```python
  chunk_duration: int = 15,
  chunk_interval: int = 10,
  overlap_duration: int = 5,
  ```
  and `chunk_operations.py:349` `chunk_interval: int = 10` on
  `calculate_total_chunks`, whose body ignores the parameter entirely (it
  delegates to `content_chunk_count(total_duration)`).
- **Impact**: cosmetic today — a caller relying on the defaults silently gets the
  right numbers. It is a drift hazard: changing `CHUNK_INTERVAL` in the SoT would
  leave four stale defaults behind, and the `int` annotations mislead mypy about
  the real types flowing through the chunk path.
- **Siblings**: the dead `chunk_interval` parameter on `calculate_total_chunks`
  (documented as "kept for back-compat") and on `get_chunk_time_range`.
- **Suggested Fix**: drop the defaults entirely (make the geometry parameters
  required, or import the SoT constants as the defaults) and correct the
  annotations to `float`.

---

### BE4-7: `HybridProcessor.close()` is a no-op, so every "release the 5-thread executor" eviction path in the backend releases nothing

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis/core/hybrid_processor.py:162-174`, `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:33-34`; callers at `auralis-web/backend/core/processor_pool.py:128-135`, `auralis-web/backend/core/processor_factory.py:261`, `:350`, `:384`, `auralis-web/backend/config/startup.py:141-146`
- **Status**: NEW
- **Description**:
  Five separate call sites in the backend invoke `processor.close()` on cache eviction /
  shutdown, each with a comment citing #3746: "its `fingerprint_analyzer` owns a 5-thread
  executor that is never reclaimed otherwise". `HybridProcessor.close()` forwards to
  `AudioFingerprintAnalyzer.close()`, which is now literally documented as a no-op — the class
  was rewritten as a thin façade over the in-process Rust engine and no longer owns an
  executor at all.
- **Evidence**:
  ```python
  # auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:30-34
  def __init__(self) -> None:
      pass

  def close(self) -> None:
      """No-op. The Rust engine holds no Python-side executor; kept for API compat."""
  ```
  ```python
  # auralis/core/hybrid_processor.py:172-174 — the only thing close() does
  close_fn = getattr(self.fingerprint_analyzer, "close", None)
  if callable(close_fn):
      close_fn()
  ```
- **Impact**:
  No runtime leak today (there is nothing left to release), but the whole eviction-hygiene
  story in `processor_pool.py` / `processor_factory.py` / `startup.py` is now fiction. The
  next resource added to `HybridProcessor` will silently inherit a no-op release path, and the
  `try/except` + warning scaffolding around these `close()` calls implies a guarantee the code
  no longer provides. It also means the shutdown step "✅ Processor factory cache cleared" is
  purely a dict clear.
- **Siblings**:
  `ProcessorPool.return_to_cache`'s eviction and `ProcessorFactory.cleanup_track` /
  `clear_cache` carry the same stale rationale.
- **Suggested Fix**:
  Either give `HybridProcessor.close()` real content (dispose whatever its sub-components
  actually own today) or delete it and the five call sites' misleading comments.

---

### BE4-8: `RecommendationService` mutates `sys.path` on every analysis call, from a worker thread

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/recommendation_service.py:79`, `:139`
- **Status**: NEW
- **Description**:
  Both `_analyze()` closures begin with `sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))`.
  These closures run inside `asyncio.to_thread`, are invoked once per track load (wired to
  `play_enhanced` **and** `play_normal` via `ws_handlers/playback_commands.py:228` and `:284`),
  and never remove the entry. `sys.path` is process-global and unguarded.
- **Evidence**:
  ```python
  # services/recommendation_service.py:78-82  (identical at :138-142)
  def _analyze() -> dict[str, Any] | None:
      sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
      from core.chunked_processor import ChunkedAudioProcessor
  ```
- **Impact**:
  One duplicate `sys.path` entry per track played, unbounded for the process lifetime; every
  subsequent import walks a longer path list. Concurrent `list.insert` from multiple worker
  threads is not a correctness hazard in CPython but is a shared-state mutation from a thread
  with no lock. The insert is also unnecessary — the module already imported successfully
  from the same package.
- **Siblings**: none found elsewhere in `services/`.
- **Suggested Fix**: Delete both lines; the backend directory is already on `sys.path`
  (`core/processing_engine.py:28` does it once, at import time).

---

### BE4-9: `output_format` / `bit_depth` are unvalidated free values that reach `soundfile` as a filename extension and a subtype

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/routers/processing_api.py:62-63`, `auralis-web/backend/core/processing_engine.py:183-185`, `:424-451`
- **Status**: NEW
- **Description**:
  `ProcessingSettings.output_format` is a bare `str = "wav"` whose docstring advertises
  `"wav", "flac", "mp3"`, and `bit_depth` a bare `int = 16` advertising `16, 24, 32`. The
  format string is interpolated straight into the output filename; the bit depth is mapped to
  a libsndfile subtype. Several advertised combinations cannot be written by libsndfile
  (`mp3` with `PCM_16`; `flac` with `PCM_32`), and an arbitrary string produces a format
  libsndfile cannot infer at all.
- **Evidence**:
  ```python
  # core/processing_engine.py:183-185
  output_format = settings.get("output_format", "wav")
  output_path = str(self.temp_dir / f"{job_id}_processed.{output_format}")
  # :427-451
  subtype_map: dict[int, str] = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
  subtype = subtype_map.get(bit_depth, 'PCM_16')
  await asyncio.to_thread(save, file_path=job.output_path, ..., subtype=subtype)
  ```
- **Impact**:
  A documented-as-supported request fails as a generic job failure with
  `"Audio file could not be read"` / `"An unexpected error occurred during processing"` — the
  error category is actively misleading about the cause. No security impact:
  `f"{job_id}_processed.{output_format}"` cannot escape `temp_dir` because the traversal
  component would have to be an existing directory named `<uuid>_processed.<prefix>`
  (see "Disproved hypotheses").
- **Siblings**: `mode` is likewise an unvalidated `str` (see BE4-1 Siblings).
- **Suggested Fix**: Make both `Literal[...]` fields on `ProcessingSettings` and reject
  unsupported (format, bit_depth) pairs at submit time with a 422.

---

### BE4-10: `PlayerStateManager`'s 1 Hz position task is never cancelled during shutdown

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/state_manager.py:215-237`, `auralis-web/backend/config/startup.py:100-165`
- **Status**: NEW
- **Description**:
  `_position_update_loop` is spawned by `_start_position_updates()` and cancelled only by
  `_stop_position_updates()`, which is reached exclusively from `set_playing(False)`.
  `_shutdown_components` tears down the background workers, the streamlined worker, the
  processing engine, the audio player, the processor factory, the artwork session and the
  library database — but never touches `player_state_manager`, and
  `_ROLLBACK_COMPONENTS_TO_NULL` only nulls the reference.
- **Evidence**:
  ```python
  # config/startup.py:53-57 — rollback nulls it, never stops it
  _ROLLBACK_COMPONENTS_TO_NULL: tuple[str, ...] = (
      'library_manager', 'repository_factory', 'settings_repository',
      'audio_player', 'player_state_manager', ...
  )
  ```
  `grep -n "player_state_manager" config/startup.py` shows no `stop`/`cancel` call in
  `_shutdown_components`.
- **Impact**:
  Shutting down while playing leaves a live task that keeps calling
  `ws_manager.broadcast(...)` against a manager whose sockets are closing, and produces a
  "Task was destroyed but it is pending" warning at loop teardown. Minor, but it is the only
  long-lived task in the lifespan with no symmetric stop.
- **Siblings**: The similarity auto-fit daemon thread has the same asymmetry — already open as
  **#4682**, not re-filed.
- **Suggested Fix**: Add `await player_state_manager._stop_position_updates()` (or a public
  `shutdown()`) to `_shutdown_components`.

---

### BE4-11: `_DebounceHandler._schedule()` cancels an `asyncio.TimerHandle` from the watchdog thread — the very thing its own comment says it avoids

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/library_auto_scanner.py:60-75`
- **Status**: NEW
- **Description**:
  `_schedule()` runs on a watchdog observer thread. It correctly routes `call_later` through
  `call_soon_threadsafe` — the comment explains exactly why — but the line immediately above
  calls `self._pending.cancel()` on the `TimerHandle` directly from that same non-loop thread,
  and `self._pending` is also read/written from `_schedule_on_loop()` on the loop thread. Both
  the handle and the attribute are unsynchronised across threads.
- **Evidence**:
  ```python
  # services/library_auto_scanner.py:60-75
  def _schedule(self) -> None:
      # Use call_soon_threadsafe because watchdog callbacks run on a
      # background thread, and call_later is not thread-safe (#2863).
      if self._pending is not None:
          self._pending.cancel()          # <- still done from the watchdog thread
      self._loop.call_soon_threadsafe(self._schedule_on_loop)

  def _schedule_on_loop(self) -> None:
      if self._pending is not None:
          self._pending.cancel()
      self._pending = self._loop.call_later(0.5, lambda: self._loop.create_task(...))
  ```
- **Impact**:
  Benign in practice under CPython (`TimerHandle.cancel` only flips a flag and drops
  references, and `_schedule_on_loop` re-cancels correctly), so the debounce still works. But
  it is a documented-unsafe cross-thread call that contradicts the fix note two lines below
  it, and the redundant cancel serves no purpose.
- **Siblings**: none.
- **Suggested Fix**: Delete the two lines in `_schedule()`; `_schedule_on_loop` already
  cancels the pending handle on the correct thread.

---

### BE4-12: `get_mastering_target_service()` — the `#3836`-wired singleton — has zero production callers; every `ChunkedAudioProcessor` builds its own service and its own cache

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/core/mastering_target_service.py:455-482`, `auralis-web/backend/core/chunked_processor.py:184-186`
- **Status**: NEW
- **Description**:
  `get_mastering_target_service()` exists as a double-checked-locking singleton whose whole
  reason for existing (per its inline comment) is to wire the Tier-1 DB lookup so the
  singleton "isn't a latent Tier-1-dead trap (#3836 / BE-PE-3)". A repo-wide grep finds no
  caller: `ChunkedAudioProcessor.__init__` constructs a **fresh** `MasteringTargetService` per
  instance, with the same repository accessor.
- **Evidence**:
  ```
  $ grep -rn "get_mastering_target_service" --include="*.py" .
  tests/auralis/core/test_content_analysis_facade_locking.py:15:   (docstring mention only)
  auralis-web/backend/core/mastering_target_service.py:460:        (definition)
  auralis/core/analysis/content_analysis_facade.py:281:            (comment mention only)
  ```
  ```python
  # core/chunked_processor.py:184-186
  self._mastering_target_service: Any = MasteringTargetService(
      get_fingerprints_repository=_default_get_fingerprints_repository,
  )
  ```
- **Impact**:
  The 256-entry LRU fingerprint/target cache (`_max_cache_entries = 256`, "plenty for a
  typical listening session") is per-`ChunkedAudioProcessor`, so it is thrown away on every
  processor construction and never amortises anything — the caching that the class documents
  is effectively dead. Meanwhile the singleton is dead code that reads as the intended entry
  point.
- **Siblings**:
  `ProcessorFactory` uses the singleton pattern correctly (`chunked_processor.py:183` calls
  `get_processor_factory()`), which makes the inconsistency easy to mistake for intent.
- **Suggested Fix**: Have `ChunkedAudioProcessor` use `get_mastering_target_service()`, or
  delete the singleton accessor.

---

### BE4-14: `services/learning_system.py` and `services/audio_content_predictor.py` (1,062 lines, 3 singletons) have zero production importers

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/learning_system.py` (483 lines), `auralis-web/backend/services/audio_content_predictor.py` (579 lines)
- **Status**: NEW
- **Description**:
  A repo-wide grep for every public name these modules export
  (`LearningSystem`, `AdaptiveWeightTuner`, `AffinityRuleLearner`, `AudioContentPredictor`,
  `AudioContentAnalyzer`, `get_learning_system`, `get_weight_tuner`, `get_affinity_learner`,
  `get_audio_content_predictor`) finds importers only in `tests/backend/test_learning_system.py`
  and `tests/backend/test_audio_content_predictor.py`. No router, service, ws_handler or core
  module imports either file.
- **Evidence**:
  ```
  $ grep -rn "learning_system|audio_content_predictor|AudioContentPredictor|
             AdaptiveWeightTuner|AffinityRuleLearner|LearningSystem" --include="*.py" .
    (excluding the two modules themselves)
  -> only tests/backend/test_audio_content_predictor.py and tests/backend/test_learning_system.py
  ```
  ```
  $ grep -rn "get_learning_system|get_weight_tuner|get_affinity_learner|
             get_audio_content_predictor|get_artwork_downloader" auralis-web/
  -> routers/artwork.py:443-444 (get_artwork_downloader) and nothing else
  ```
- **Impact**:
  1,062 lines of ML/prediction code presented in the services layer — and in this audit's own
  charter — as live infrastructure. It is not. Consequences: (a) any behaviour reasoned about
  through these modules is fiction; (b) fix effort has already been spent on unreachable code —
  **#4379** ("`AudioContentPredictor._load_chunk_fast`/`_extract_features` perform blocking
  file I/O and full-file decode on the event loop", CLOSED) hardened a path production never
  executes; (c) the three `learning_system` singletons are entirely unsynchronised
  (`grep -n "Lock" services/learning_system.py` → no matches), which would be a real
  thread-safety finding if anything called them.
- **Siblings**:
  Same class as open **#4592** ("4 engine modules, 1,491 lines, imported only by test/validation
  files") and **#4565** ("`auralis/optimization/parallel/` — 5 fix commits spent on unreachable
  code"), but those cover `auralis/`, not `auralis-web/backend/services/`.
- **Suggested Fix**: Wire them up or delete them; either way, remove them from the "live
  services" inventory so future audits don't budget for them.

---

### BE4-15: `PlaybackService` still holds `_playback_lock` across a WebSocket broadcast — via `set_playing()` — and the residual hold scales with the number of wedged clients

- **Severity**: LOW
- **Dimension**: Processing Engine
- **Location**: `auralis-web/backend/services/playback_service.py:153-170` (and the same shape at `:195-206`, `:229-247`), `auralis-web/backend/core/state_manager.py:87`, `auralis-web/backend/config/globals.py:146-169`
- **Status**: NEW (**not** a regression of #4581 — that fix is present and correct for the call
  it moved; this is the second broadcast it did not move)
- **Description**:
  #4581 moved the explicit `connection_manager.broadcast(...)` out of the `_playback_lock`
  block. But `await self.player_state_manager.set_playing(...)` remains *inside* the block, and
  that call chain reaches `PlayerStateManager.update_state` → `_broadcast_state` →
  `ConnectionManager.broadcast`. So a broadcast is still performed under the lock. The
  in-file comment acknowledges this and argues it is bounded — but describes the bound as a
  single timeout, whereas `ConnectionManager.broadcast` iterates connections **sequentially**,
  applying `BROADCAST_SEND_TIMEOUT` per client.
- **Evidence**:
  ```python
  # services/playback_service.py:153-161
  async with self._playback_lock:  # #3734
      await asyncio.to_thread(self.audio_player.play)
      # Update state (broadcasts automatically)          <- the comment says it out loud
      await self.player_state_manager.set_playing(True)
  ```
  ```python
  # core/state_manager.py:85-87
  # Broadcast outside the lock (#3732) ...
  await self._broadcast_state(state_snapshot)            # -> ws_manager.broadcast(...)
  ```
  ```python
  # config/globals.py:146-160 — sequential, per-client timeout
  for connection in connections_snapshot:
      await asyncio.wait_for(connection.send_text(message_json),
                             timeout=BROADCAST_SEND_TIMEOUT)   # 2.0 s each
  ```
  vs. the claim at `playback_service.py:112-114`: "Its broadcast is instead bounded by
  `ConnectionManager.BROADCAST_SEND_TIMEOUT`, so the worst-case hold is a short timeout".
- **Impact**:
  Worst-case `_playback_lock` hold is `2.0 s × (number of stalled clients)`, not 2.0 s. On the
  intended desktop deployment (1-2 clients) this is a few seconds of frozen transport controls
  rather than the "short timeout" documented — real but small. Filed mainly because the
  comment's reasoning is what a future reader will trust.
- **Siblings**: `pause()` (`:195`), `stop()` (`:229`) have the identical structure.
- **Suggested Fix**: Either correct the comment to state the `N × timeout` bound, or move
  `set_playing()` outside the lock and rely on `PlayerState.seq` for ordering — which is
  exactly the mechanism #3732 introduced in `state_manager.py` for this purpose.

---

### BE5-N2: `ArtistDetailApiResponse.albums` is typed as full `AlbumApiResponse[]`, but `GET /api/artists/{id}` emits a 5-field `AlbumInArtist` and `response_model` strips the rest


- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Backend: `/mnt/data/src/matchering/auralis-web/backend/routers/artists.py:69-76` (`AlbumInArtist`), `:78-87` (`ArtistDetailResponse`), `:176-215` (`GET /api/artists/{artist_id}`, `response_model=ArtistDetailResponse`)
  - Frontend: `/mnt/data/src/matchering/auralis-web/frontend/src/api/transformers/types.ts:153-161` (`ArtistDetailApiResponse`), `:15-24` (`AlbumApiResponse`)
  - Consumer: `/mnt/data/src/matchering/auralis-web/frontend/src/components/library/Details/useArtistDetailsData.ts:44-58`
- **Status**: NEW
- **Description**:
  The frontend declares the nested albums of the artist-detail response as
  `AlbumApiResponse[]`, which marks `artist: string`, `artist_id: number | null` and
  `artwork_url: string | null` as **required, non-optional** fields. The backend's nested
  model is `AlbumInArtist`, which has only `id`, `title`, `year`, `track_count`,
  `total_duration`. Because the route declares `response_model=ArtistDetailResponse`,
  FastAPI strips anything else — those three fields can never appear on the wire.
- **Evidence**:
  Backend — `routers/artists.py:69-76`:
  ```python
  class AlbumInArtist(BaseModel):
      """Album information in artist context"""
      id: int
      title: str
      year: int | None = None
      track_count: int
      total_duration: float
  ```
  Frontend — `api/transformers/types.ts:153-161`:
  ```ts
  export interface ArtistDetailApiResponse {
    id: number;
    name: string;
    albums: AlbumApiResponse[];
    total_albums: number;
    total_tracks: number;
    artwork_url?: string | null;
    artwork_source?: string | null;
  }
  ```
  and `api/transformers/types.ts:15-24`:
  ```ts
  export interface AlbumApiResponse {
    id: number;
    title: string;
    artist: string;
    artist_id: number | null; // FK to artists table (snake_case)
    year: number | null;
    artwork_url: string | null; // Backend field name
    track_count: number; // Backend field name (snake_case)
    total_duration: number; // Backend field name (snake_case)
  }
  ```
- **Impact**:
  No runtime break today: the only consumer
  (`useArtistDetailsData.ts:50-56`) reads exactly the five fields the backend does send,
  and its local `Album` interface (`useArtistDetailsData.ts:12-18`) has no artwork field.
  The cost is latent — TypeScript will silently accept `album.artwork_url` /
  `album.artist_id` in artist-detail code and hand back `undefined` at runtime with no
  compile error, which is precisely the failure class of the already-closed #4568/#4571.
  Secondary consequence: album tiles on the artist-detail page have no artwork URL
  available at all, because the backend model does not carry one.
- **Siblings**: None found in the routers I examined; `AlbumApiResponse` is otherwise used
  against `/api/albums` (`routers/albums.py:79-85`), where all eight fields really are
  present via `Album.to_dict()` (`auralis/library/models/core.py:273-289`).
- **Suggested Fix**:
  Add a dedicated `AlbumInArtistApiResponse` in `api/transformers/types.ts` mirroring
  `AlbumInArtist`'s five fields and use it for `ArtistDetailApiResponse.albums`. If artist-
  detail tiles are meant to show artwork, add `artwork_url` to the backend `AlbumInArtist`
  model instead — but do not leave the two shapes disagreeing.

---

### BE5-N3: Orphan `AlbumDetailApiResponse` type describes a snake_case + `tracks` contract that no endpoint implements


- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Frontend: `/mnt/data/src/matchering/auralis-web/frontend/src/api/transformers/types.ts:141-147`
  - Backend: `/mnt/data/src/matchering/auralis-web/backend/routers/albums.py:87-116` (`GET /api/albums/{album_id}`) and `/mnt/data/src/matchering/auralis-web/backend/routers/serializers.py:227-248` (`serialize_album_detail`)
- **Status**: NEW
- **Description**:
  `AlbumDetailApiResponse extends AlbumApiResponse` (all snake_case) and adds
  `tracks: TrackApiResponse[]`. No backend endpoint produces that shape:
  `GET /api/albums/{id}` returns the **camelCase** album shape from
  `serialize_album_detail` (`id, title, artist, artistId, year, artworkUrl, genre,
  trackCount, totalDuration, dateAdded`) and carries **no** `tracks` array; the tracks live
  behind the separate `GET /api/albums/{id}/tracks`, which returns a different envelope
  (`album_id`, `album_title`, `artist`, `year`, `artwork_url`, `tracks`, `total_tracks` —
  `routers/albums.py:145-153`). A repo-wide grep found zero importers of
  `AlbumDetailApiResponse` outside its own declaration.
- **Evidence**:
  Frontend — `api/transformers/types.ts:141-147`:
  ```ts
  export interface AlbumDetailApiResponse extends AlbumApiResponse {
    tracks: TrackApiResponse[];
  }
  ```
  Backend — `routers/serializers.py:236-248`:
  ```python
  snake = serialize_album(album)
  return {
      'id': snake.get('id'),
      'title': snake.get('title'),
      'artist': snake.get('artist'),
      'artistId': snake.get('artist_id'),
      ...
      'trackCount': snake.get('track_count', 0),
      'totalDuration': snake.get('total_duration', 0),
      'dateAdded': snake.get('date_added') or snake.get('created_at'),
  }
  ```
  Grep for `AlbumDetailApiResponse` across `auralis-web/frontend/src` returns only
  `api/transformers/types.ts:145`.
- **Impact**:
  Dead contract documentation that contradicts the live one. Anyone reaching for
  "the album-detail response type" gets a snake_case shape with a `tracks` array and will
  write code that reads `undefined` from both. This is the same trap that produced #4568
  (closed) and #4423 (closed). No runtime effect today.
- **Siblings**: Adjacent to the known-open #4398 (33 unused REST-contract types in
  `types/api.ts`) but distinct — this one lives in `api/transformers/types.ts`, the file
  that *is* the live transformer contract, so it is more likely to be trusted.
- **Suggested Fix**: Delete `AlbumDetailApiResponse`, or replace it with two accurate
  types: a camelCase `AlbumDetail` matching `serialize_album_detail`, and an
  `AlbumTracksApiResponse` matching the `{album_id, album_title, artist, year,
  artwork_url, tracks, total_tracks}` envelope.

---

### BE5B-N1: 15 Pydantic models in `schemas.py` are orphans — including a typed cache-stats family that the live cache router shadows with an untyped local copy


- **Severity**: LOW
- **Dimension**: Schema Consistency (dim_5 check #7 — duplicate / orphan Pydantic models)
- **Location**:
  - `/mnt/data/src/matchering/auralis-web/backend/schemas.py:67-95` (`ErrorResponse`), `:97-110` (`ErrorType`), `:237-258` (`TrackBase`, `ArtistBase`, `AlbumBase`), `:265-269` (`PaginationParams`), `:271-274` (`CursorPaginationParams`), `:277-282` (`SearchRequest`), `:289-295` (`ResponseStatus`), `:323-338` (`CacheSource`, `ChunkCacheMetadata`), `:341-352` (`TrackCacheStatusResponse`), `:355-372` (`CacheTierStats`, `OverallCacheStats`), `:375-386` (`CacheHealthResponse`), `:390-395` (`CacheStatsResponse`)
  - Shadowing copies: `/mnt/data/src/matchering/auralis-web/backend/routers/cache_streamlined.py:23-36` (local `CacheStatsResponse`), `:39-47` (local `TrackCacheStatus`)
- **Status**: NEW
- **Description**:
  A grep of every `class` in `schemas.py` against the whole backend tree shows 15 models
  with **zero production references** — their only importer is
  `tests/backend/test_schemas_and_middleware.py` or `tests/backend/test_cache_integration_b2.py`,
  i.e. tests that instantiate the model and assert it round-trips. No route declares them
  as `response_model=`, and no handler constructs one.
  The cache family is the sharp case: `schemas.py` defines a fully-typed
  `CacheStatsResponse` (nested `CacheTierStats` / `OverallCacheStats`) and
  `TrackCacheStatusResponse`, but `routers/cache_streamlined.py` — the only module that
  serves `/api/cache/*` — declares its **own** same-named `CacheStatsResponse` with
  `dict[str, Any]` fields and uses that as the `response_model`. The router's own docstring
  admits this ("Migrating to the schemas.py version is a follow-up"). Net effect: the typed
  contract exists, is tested, and is not what goes on the wire.
  `CacheHealthResponse` is the same shape as the literal dict that `GET /api/cache/health`
  returns (`cache_streamlined.py:192-202` emits exactly its nine fields) — but that route
  is annotated `-> dict[str, Any]`, so the model is not enforced and the response is
  unmodelled in the OpenAPI schema.
- **Evidence**:
  Only-consumer check (run against `auralis-web/backend/` and `tests/`, excluding
  `schemas.py` itself) — every hit for `ErrorResponse`, `ErrorType`, `TrackBase`,
  `ArtistBase`, `AlbumBase`, `CursorPaginationParams`, `SearchRequest`, `ResponseStatus`,
  `ChunkCacheMetadata`, `CacheSource`, `TrackCacheStatusResponse`, `CacheTierStats`,
  `OverallCacheStats`, `CacheHealthResponse` lands in a test file.
  Live route vs typed model — `routers/cache_streamlined.py:23-36`:
  ```python
  class CacheStatsResponse(BaseModel):
      """... This local copy uses dict[str, Any] to absorb the
      StreamlinedCacheManager.get_stats() return shape verbatim."""
      tier1: dict[str, Any]
      tier2: dict[str, Any]
      overall: dict[str, Any]
      tracks: dict[int, dict[str, Any]]
  ```
  vs `schemas.py:390-395`:
  ```python
  class CacheStatsResponse(BaseModel):
      tier1: CacheTierStats = Field(description="Tier 1 (memory) statistics")
      tier2: CacheTierStats = Field(description="Tier 2 (disk) statistics")
      overall: OverallCacheStats = Field(description="Aggregate statistics")
      tracks: dict[int, Any] = Field(default_factory=dict, ...)
  ```
- **Impact**:
  Two same-named models in one process is the failure mode #4372/#4460 were filed for on
  the TypeScript side: an IDE autocompletes whichever it indexes first, and a future
  `response_model=CacheStatsResponse` edit can silently change the wire format depending on
  which import line is present. The tests around the `schemas.py` copies pass while
  exercising nothing the server actually emits — false coverage of the cache contract in
  particular. `CacheTierStats.tier_name` is a field the live payload never carries, so
  adopting the typed model as-is would 500 the endpoint (`ValidationError` on a missing
  required field) — the "follow-up" the router docstring proposes is not a drop-in.
  No runtime effect today.
- **Siblings**: `routers/cache_streamlined.py:39-47` `TrackCacheStatus` vs
  `schemas.TrackCacheStatusResponse` is the same duplication one field apart
  (`estimated_cache_time_seconds` exists only on the schemas.py version and no producer
  computes it). `PaginationParams` is a third collision — see BE5B-N2.
- **Related**: #4372 / #4460 / #4398 (the TypeScript-side equivalents, all filed);
  #4606 (CLOSED — the same class of finding for `helpers.py`'s "5 schema models"). This is
  the `schemas.py` counterpart and was not covered by any of them.
- **Suggested Fix**: For each orphan, either wire it into the route it documents or delete
  it with its test. For the cache family specifically: verify
  `StreamlinedCacheManager.get_stats()` field-for-field against `CacheTierStats` /
  `OverallCacheStats` (note `tier_name` is absent from the live dict), then point
  `routers/cache_streamlined.py` at the `schemas.py` models and delete the local copies —
  do not leave two `CacheStatsResponse` classes importable in one process.

---

### BE5B-N2: Two live classes named `PaginationParams` disagree about the maximum page size (500 vs 200), and neither is what the routes enforce


- **Severity**: LOW
- **Dimension**: Schema Consistency (dim_5 check #7)
- **Location**:
  - `/mnt/data/src/matchering/auralis-web/backend/schemas.py:265-269`
  - `/mnt/data/src/matchering/auralis-web/backend/routers/pagination.py:95-121`
- **Status**: NEW
- **Description**:
  `schemas.PaginationParams` is a Pydantic model with `limit: int = Field(default=50, ge=1, le=500)`.
  `routers.pagination.PaginationParams` is a plain constants class with
  `DEFAULT_LIMIT = 50`, `MAX_LIMIT = 200`, `MIN_LIMIT = 1`. They are unrelated types with
  the same name and a contradictory cap. Neither is used by any route: every paginated
  handler inlines `limit: int = Query(50, ge=1, le=200)` by hand
  (e.g. `routers/playlists.py:91-92`). Both classes have their own test file asserting
  their own cap — `tests/backend/test_schemas_and_middleware.py:112` asserts `limit=500`
  is valid, `tests/backend/test_pagination.py:123` asserts `MAX_LIMIT == 200`.
- **Evidence**:
  `schemas.py:265-269`:
  ```python
  class PaginationParams(BaseModel):
      """Standard pagination query parameters."""
      limit: int = Field(default=50, ge=1, le=500, description="Items per page (1–500)")
      offset: int = Field(default=0, ge=0, description="Number of items to skip")
  ```
  `routers/pagination.py:95-121`:
  ```python
  class PaginationParams:
      """Standard pagination parameters with validation. ... limit: Maximum number of
      items to return (1-200, default 50)"""
      DEFAULT_LIMIT = 50
      MAX_LIMIT = 200
      ...
  ```
  The `routers/pagination.py` docstring even shows the intended usage as a hand-written
  `Query(50, ge=1, le=200)` — i.e. the class is documentation, not a dependency.
- **Impact**:
  `from schemas import PaginationParams` and `from routers.pagination import PaginationParams`
  are both valid and produce incompatible objects (one is instantiable with kwargs, the
  other is a namespace of ints). Anyone adopting "the" pagination params to stop
  hand-copying `Query(...)` has a 50/50 chance of silently raising the public cap from 200
  to 500 — which is exactly the unbounded-read class of bug #4554 fixed for
  `GET /api/playlists`. No runtime effect today because neither is wired in.
- **Siblings**: The same "documented but not enforced" split exists for
  `PaginatedResponse` (`routers/pagination.py:60-93`) — routes build the
  `{items…, total, offset, limit, has_more}` envelope by hand instead of calling
  `PaginatedResponse.create()`; see `routers/playlists.py:121-127`.
- **Related**: BE5B-N1 (same class of duplication in the cache models); #4554.
- **Suggested Fix**: Delete `schemas.PaginationParams` / `CursorPaginationParams` (nothing
  reads them) and keep the `routers/pagination.py` constants as the single source, then
  actually reference `PaginationParams.MAX_LIMIT` from the `Query(...)` declarations so the
  cap has one definition.

---

### BE5B-N3: `similarityService.SimilarTrack` declares a `duration` field the endpoint can never return, and marks three nullable backend fields as required


- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - Frontend type: `/mnt/data/src/matchering/auralis-web/frontend/src/services/similarityService.ts:21-30`
  - Consumer: `/mnt/data/src/matchering/auralis-web/frontend/src/components/features/discovery/SimilarTracksListItem.tsx:93-94`
  - Backend model: `/mnt/data/src/matchering/auralis-web/backend/routers/similarity.py:41-51`, route at `:105-203`
- **Status**: NEW
- **Description**:
  The backend `SimilarTrack` Pydantic model has exactly seven fields
  (`track_id, distance, similarity_score, rank, title, artist, album`) and the route
  declares `response_model=list[SimilarTrack]`, so FastAPI strips anything else. There is
  no `duration` on the model and no producer sets one — `get_similar_tracks` populates
  details from `repos.tracks.get_by_ids()` and copies only `title`, `artist`, `album`
  (`similarity.py:196-201`). The frontend type declares `duration?: number`, and
  `SimilarTracksListItem` renders `{track.duration && ` • ${formatDuration(track.duration)}`}`
  — a branch that is unreachable at runtime.
  Separately, the TS type marks `title: string; artist: string; album: string` as
  **required non-nullable**, while the backend declares all three `str | None = None`.
  They are null whenever `include_details=false`, whenever the batch lookup misses (a stale
  K-NN graph edge pointing at a deleted track), and — for `artist`/`album` — whenever the
  track has no artist rows or no album (`similarity.py:200-201` yields `None`).
- **Evidence**:
  `routers/similarity.py:41-51`:
  ```python
  class SimilarTrack(BaseModel):
      track_id: int = Field(..., description="ID of the similar track")
      distance: float = ...
      similarity_score: float = Field(..., ge=0.0, le=1.0, ...)
      rank: int | None = Field(None, ...)
      # Optional track details
      title: str | None = None
      artist: str | None = None
      album: str | None = None
  ```
  `services/similarityService.ts:21-30`:
  ```ts
  export interface SimilarTrack {
    track_id: number;
    distance: number;
    similarity_score: number;
    title: string;
    artist: string;
    album: string;
    duration?: number;
    rank?: number;
  }
  ```
- **Impact**:
  Mitigated to near-zero today: every consumer of this type
  (`components/features/discovery/SimilarTracks.tsx`, `SimilarTracksList.tsx`,
  `SimilarTracksListItem.tsx`, `useSimilarTracksLoader.ts`, `SimilarityVisualization.tsx`)
  is reachable **only from its own test files** — `grep -rn "features/discovery"` outside
  that directory returns two `__tests__` imports and nothing else. The live similar-tracks
  path is `components/shared/SimilarTracksModal` → `hooks/fingerprint/useSimilarTracks.ts`,
  which declares `title?/artist?/album?` correctly and has no `duration`. So the cost is a
  wrong contract plus passing tests for a duration row that could never render.
- **Siblings**: `hooks/fingerprint/useSimilarTracks.ts:193-201` declares its private
  `RawSimilarTrack.title/artist/album` as required `string` too, but immediately widens
  them to optional on the mapped `SimilarTrack`, so the mistake does not escape.
- **Related**: #4579 catalogues two *other* dead component subtrees but does **not**
  list `components/features/discovery/` — that subtree is a third one, found here.
  #4372 removed the api.ts `SimilarTrack` for the same class of divergence.
- **Suggested Fix**: Drop `duration` and widen `title/artist/album` to
  `string | null` in `similarityService.ts` to match `routers/similarity.py`; delete the
  unreachable `formatDuration` plumbing in `SimilarTracksListItem`. If the discovery
  subtree is genuinely dead, deleting it resolves this outright.

---

### BE5B-N6: `GET /api/audio/formats` advertises a hardcoded list that contradicts `auralis/io/formats.py`, the declared single source of truth the same router uses to validate uploads


- **Severity**: LOW
- **Dimension**: Schema Consistency
- **Location**:
  - `/mnt/data/src/matchering/auralis-web/backend/routers/files.py:273-289`
  - Single source of truth: `/mnt/data/src/matchering/auralis/io/formats.py:15-42`
  - Same router's upload validator: `/mnt/data/src/matchering/auralis-web/backend/routers/files.py:142`
- **Status**: NEW
- **Description**:
  `auralis/io/formats.py` opens with "Single source of truth for the audio
  extensions Auralis can decode. The scanner, the unified loader, the file-type
  checker, and the upload allowlist all derive their extension sets from here so
  the lists never drift apart again (#4109)." `POST /api/files/upload` honours that
  — `supported_extensions = tuple(SUPPORTED_FORMATS.keys())` at `files.py:142`.
  `GET /api/audio/formats`, 130 lines below in the same file, returns a hardcoded
  literal that omits five of the eleven accepted extensions.
- **Evidence**:
  `routers/files.py:284-289`:
  ```python
  return {
      "input_formats": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
      "output_formats": [".wav", ".flac", ".mp3"],
      "sample_rates": [44100, 48000, 88200, 96000, 192000],
      "bit_depths": [16, 24, 32]
  }
  ```
  vs `auralis/io/formats.py:15-34` — `SUPPORTED_FORMATS` =
  `{.wav, .flac, .aiff, .aif, .au, .mp3, .m4a, .aac, .ogg, .wma, .opus}`.
  Missing from the advertised list: `.aiff`, `.aif`, `.au`, `.wma`, `.opus`.
  The upload path's own magic-byte table (`files.py:49-72`) explicitly recognises
  AIFF, AU and WMA/ASF, so those really are accepted — the advertised contract is
  the thing that is wrong, not the validator.
- **Impact**:
  No production consumer today: a repo-wide grep for `audio/formats` across
  `auralis-web/frontend/src` returns nothing, and the only callers are
  `tests/backend/test_files_api.py` and `tests/backend/test_main_api.py`. So this is
  a wrong-but-unread contract rather than a live bug. If a file picker is ever built
  from this endpoint it will refuse five formats the server accepts. `bit_depths`
  including `32` is also unverified against `auralis/io/results.py`, which exposes
  `pcm16`/`pcm24` only.
- **Siblings**: None — `routers/processing_api.py:353-357` derives its media-type
  map locally but only for the three output formats it actually writes.
- **Related**: #4109 (the issue that created the single source of truth this
  endpoint bypasses).
- **Suggested Fix**: Return `sorted(SUPPORTED_FORMATS)` (or `AUDIO_EXTENSIONS`) for
  `input_formats` instead of the literal, and derive `output_formats` / `bit_depths`
  from the saver/`results.py` capabilities rather than hardcoding them.

---

### BE6-4: Every INFO/DEBUG log emitted at import time is silently discarded, including all router-registration confirmations

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/main.py:23-29, 232-240`; `/mnt/data/src/matchering/auralis-web/backend/config/routes.py:85-278`
- **Status**: NEW
- **Description**: `#3537` deliberately removed `logging.basicConfig` from `main.py` so that `uvicorn.run()` owns the root logger. But `uvicorn.run()` is at the *bottom* of `main.py` (line 235), and the whole application graph — `create_app`, `setup_middleware`, `setup_routers`, the StaticFiles mount — is built in the module body above it (lines 141-229). At that point the root logger has **no handlers**, so Python falls back to `logging.lastResort`, whose level is `WARNING`.
- **Evidence**:
  ```
  $ python -c "import logging; print(logging.getLogger().handlers, logging.lastResort.level)"
  [] 30
  $ python -c "import logging; l=logging.getLogger('x'); print(l.isEnabledFor(logging.INFO)); l.info('X'); l.warning('Y')"
  False
  Y
  ```
  So all 20 `logger.debug("✅ … router registered")` lines in `config/routes.py`, the `logger.info("✅ Streamlined cache router registered")` at `:243`, `logger.info("✅ Similarity router family registered")` at `:268`, and the summary `logger.info("✅ All routers configured and registered")` at `:278` never reach a handler. Same for `middleware.py:357` and `main.py:37/45/50/157/162/169/204/205/208`.
- **Impact**: An operator diagnosing a 404 gets no positive record of which routers registered. **The failure path is unaffected** — `routes.py:90/245/270` log at WARNING with `exc_info=True`, which `lastResort` does emit (with a full traceback, though unformatted: no timestamp, level or logger name). So this does **not** cause a router to vanish silently, which is why this is LOW and not MEDIUM. The latent hazard is that the codebase's own convention ("confirmations at debug, failures at warning") is only accidentally safe here: demoting any of those three failure logs to INFO would make a missing router completely invisible.
- **Siblings**: BE6-5 depends on this (it is what currently masks the path disclosure).
- **Suggested Fix**: Configure logging explicitly *before* the module body builds the app — e.g. a `configure_logging()` call at the top of `main.py` that installs a single handler and that `uvicorn.run(log_config=...)` is told not to duplicate — rather than relying on uvicorn to configure a logger that is needed 200 lines earlier. Add a comment at `routes.py:90/245/270` recording that WARNING is load-bearing there.

---

### BE6-5: `main.py` still logs the absolute install path at INFO in three places the `#4366`/`#4376` demotion missed

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/main.py:37, 45, 50`
- **Status**: NEW (incomplete fix of `#4376` / `#4366`, both CLOSED)
- **Description**: `#4366` demoted absolute-path logging in this exact file to DEBUG — visible at `main.py:169` (`logger.debug(f"Looking for frontend at: {frontend_path}")`), `:205`, `:225`, and in `startup.py:298`/`:309`. The three `sys.path` bootstrap lines above were not included:

  ```python
  # main.py:37
  logger.info(f"Running as PyInstaller bundle, adding to sys.path: {auralis_parent}")
  # main.py:45
  logger.info(f"Running in Electron mode (unfrozen), adding to sys.path: {auralis_parent}")
  # main.py:50
  logger.info(f"Running in development mode, adding to sys.path: {auralis_parent}")
  ```

  `auralis_parent` is `/home/<username>/...` (dev/Electron-unfrozen) or the PyInstaller `_MEIPASS`-adjacent temp dir — the same OS-username-and-layout disclosure `#4351` and `#4366` were about, and the comment at `main.py:167-168` explicitly states the policy: *"INFO stays free of it so it's safe to paste into a public bug report"*.
- **Evidence**: Contrast `main.py:167-169` (the fixed site) with `main.py:37/45/50` (unfixed), three lines of the same variable class in one file.
- **Impact**: Currently masked — per BE6-4 these fire before any handler exists, so under `python main.py` they go nowhere. They *do* emit under `uvicorn main:app` / `uvicorn --factory`, and they will start emitting the moment BE6-4 is fixed. So this is a latent re-leak that the BE6-4 fix would activate. LOW because the disclosure surface is a local log file on a single-user desktop.
- **Siblings**: BE6-4 (masking mechanism). `#4649` OPEN tracks a different regrowth pattern in the same spirit.
- **Suggested Fix**: `logger.info("Running as PyInstaller bundle")` + `logger.debug(f"... adding to sys.path: {auralis_parent}")`, matching the split already used at `main.py:204-205`.

---

### BE6-6: `setup_middleware()` docstring documents a two-item order that contradicts the actual five-middleware stack four lines below it

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/middleware.py:303-311`
- **Status**: NEW
- **Description**: The function docstring still describes the pre-`#2575`/`#3843`/`#4353` world:

  ```python
  """
  Add middleware to FastAPI application.

  Configures middleware in the correct order:
  1. NoCacheMiddleware - for frontend assets
  2. CORSMiddleware - for cross-origin requests
  ...
  """
  ```

  The stack actually registers five middlewares, and the ordering that matters is the *reverse* of registration — which the inline comment at `:313-320` gets exactly right. The docstring names two of five, in registration order, and calls it "the correct order", which reads as the inbound order and is wrong on both counts.
- **Evidence**: Docstring at `:306-309` vs. correct comment at `:313-320` vs. verified live stack (see "Middleware Order (computed)" above).
- **Impact**: Documentation only — but this is the first thing a reader of `setup_middleware` sees, and the LIFO ordering here is genuinely subtle (`#3843` and `#4353` are both bugs caused by getting it wrong). A wrong docstring on exactly this function is a repeat-bug invitation.
- **Siblings**: None.
- **Suggested Fix**: Replace the docstring body with the inbound order from `:318-320` and a one-line note that `add_middleware` is LIFO, or just point the docstring at the comment.

---

### BE6-7: `validate_scan_path()` — the only allowlist-enforcing directory validator — has zero call sites; every scan entry point uses the unrestricted `validate_user_chosen_directory()` instead

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/security/path_security.py:89-180` (dead), `:339-378` (`is_safe_filename`, dead); call sites at `schemas.py:180-189`, `routers/settings.py:207-212`
- **Status**: NEW
- **Description**: `path_security.py` exposes two directory validators. `validate_scan_path()` enforces containment within `get_allowed_directories()` (`~/Music`, `~/Documents`, `$XDG_MUSIC_DIR`, registered scan folders). `validate_user_chosen_directory()` deliberately enforces **no allowlist at all** — its docstring says so: *"we trust their choice and only enforce basic safety checks … without restricting to predefined allowed directories."* A repo-wide grep shows `validate_scan_path` is called by nothing; both directory entry points use the unrestricted one:
  - `schemas.py:185` — `LibraryScanRequest.validate_directory_paths` -> `validate_user_chosen_directory(path)`
  - `routers/settings.py:207-212` — `POST /api/settings/scan-folders` -> `validate_user_chosen_directory(...)` then `register_allowed_directory(validated)`

  `is_safe_filename()` (`:339-378`) likewise has no call sites; `routers/files.py:147-165` and `routers/processing_api.py:259-262` each do their own extension/suffix checks instead.
- **Evidence**: `grep -rn --include='*.py' -e 'validate_scan_path' -e 'is_safe_filename' .` returns only the definitions, the docstring examples, and no call sites.
- **Impact**: Two consequences. (1) `path_security.py` presents a stronger containment story than the app implements — a reader (or an auditor) sees an allowlist-enforced scan validator and reasonably assumes scanning is contained. It is not; `POST /api/library/scan` accepts any existing readable directory (`/etc`, `/`), and `POST /api/settings/scan-folders` then *widens* the global `_extra_allowed_dirs` allowlist that `validate_file_path()` consults, so adding `/` as a scan folder makes `validate_file_path` accept the whole filesystem for the rest of the session. (2) The 422 body from `LibraryScanRequest` echoes the `PathValidationError` text, which contains the resolved absolute path and distinguishes "does not exist" / "not a directory" / "not readable" — a filesystem-probing oracle. Both are LOW and **not** a containment bypass: this is the documented, deliberate posture for a single-user desktop app where the path comes from the user's own file picker. Filed so the dead-code/documentation mismatch is on record, not as a traversal finding.
- **Siblings**: BE6-3 (`monitoring/`) — same "present, tested-looking, unreachable" shape.
- **Suggested Fix**: Delete `validate_scan_path` and `is_safe_filename`, or wire them. If deleting, move the "user-chosen directories are deliberately unrestricted, and registering one widens `validate_file_path`" statement to the module docstring so the trust model is stated once, at the top.

---

### BE6-8: In production, the `/` StaticFiles mount captures WebSocket scopes for any unregistered `/ws*` path and raises `AssertionError`

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/main.py:203-206`
- **Status**: NEW
- **Description**: `app.mount("/", StaticFiles(directory=..., html=True))` installs a Starlette `Mount`, and `Mount.matches()` does not filter on `scope["type"]` — it matches `websocket` scopes as readily as `http` ones. The only registered WebSocket route is `routers/system.py:297` `@router.websocket("/ws")`, so any other `/ws...` upgrade falls through to the mount, and `StaticFiles.__call__` begins with `assert scope["type"] == "http"`.
- **Evidence**: Synthetic reproduction with the same mount shape:
  ```
  /ws       -> WebSocketDisconnect   (correct: reaches the WebSocketRoute)
  /ws/nope  -> AssertionError        (StaticFiles asserting on a websocket scope)
  ```
  This path exists only in the non-dev branch; `main.py:207-208` skips the mount under `--dev`, which is why it has never been seen in development.
- **Impact**: A client that connects to a stale or mistyped WS path in the shipped Electron build gets an unhandled `AssertionError` in the ASGI stack (traceback in the log, abrupt socket teardown) instead of a clean 404/close. `_middleware_error_response` does not cover it — `BaseHTTPMiddleware` short-circuits non-http scopes. Low impact because the frontend only ever connects to `/ws`, but it is a dev/prod behavioural divergence in exactly the area `main.py:200` warns about.
- **Siblings**: BE6-10 (other `--dev` divergences).
- **Suggested Fix**: Register a catch-all `@app.websocket("/{path:path}")` that closes with 1008 before the mount, or mount the SPA under an explicit sub-application whose `Mount` is `http`-only.

---

### BE6-9: The lifespan `yield` is not inside `try/finally`, so a cancelled lifespan task skips all of `_shutdown_components` — including the WAL checkpoint

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/startup.py:637-640`
- **Status**: NEW
- **Description**:
  ```python
  # startup.py:637-640
          yield

          # === Shutdown ===
          await _shutdown_components(globals_dict)
  ```
  In Starlette 1.3.1, `Router.lifespan()` runs `await receive()` *inside* the `async with self.lifespan_context(app)` block. If that `receive()` raises — the canonical case being `CancelledError` when the lifespan task is cancelled (forced exit, second SIGINT, an ASGI server that tears the task down rather than sending `lifespan.shutdown`) — the exception is thrown into this generator at the `yield`. Because there is no `try/finally`, the generator propagates it and **`_shutdown_components` is never entered**.
- **Evidence**: `inspect.getsource(starlette.routing.Router.lifespan)` confirms `await receive()` is inside the `async with`, and that a `BaseException` there is re-raised after sending `lifespan.shutdown.failed`. `_shutdown_components` is the only caller of `LibraryDatabase.shutdown()` (`:158-163`), `close_artwork_downloader()` (`:151-155`), `get_processor_factory().clear_cache()` (`:141-146`) and `stop_background_workers()` (`:107`).
- **Impact**: On an unclean-but-not-SIGKILL exit, the SQLite WAL is not checkpointed, the shared `aiohttp` session is not closed, and the cached `HybridProcessor` thread pools (`#3746`, 5 threads each) are not released. `#4569` hardened *every step inside* this function against individual failure; the structural gap is that the function may not run at all. LOW rather than MEDIUM because the normal uvicorn SIGINT/SIGTERM path does send `lifespan.shutdown` and works correctly — I could not construct a routine trigger, only forced-exit ones.
- **Siblings**: BE6-2 (the rollback path bypasses the same teardown for a different reason). `#4569` CLOSED.
- **Suggested Fix**: `try: yield` / `finally: await _shutdown_components(globals_dict)`. `_shutdown_components` is already fully guarded internally, so it is safe to run from a `finally` under a pending cancellation (add a `shield` if the cleanup must survive the cancellation).

---

### BE6-10: `DEV_MODE` is an unnamespaced environment variable that silently re-enables Swagger, the OpenAPI schema, and the dev CORS/WebSocket origins in a packaged build

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/app.py:25-27`
- **Status**: NEW
- **Description**:
  ```python
  def is_dev_mode() -> bool:
      return "--dev" in sys.argv or os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")
  ```
  The argv half is tight (exact `in` on the token list — `--devtools` will not false-positive). The env half keys on the bare, extremely common name `DEV_MODE`, with no `AURALIS_` prefix. Electron launches the backend as a child process inheriting the user's environment, so any developer or power user with `DEV_MODE=1` exported for an unrelated project runs the shipped Auralis backend in dev mode.

  Full enumeration of what `--dev`/`DEV_MODE` changes (this is the answer to check 7):
  | Behaviour | Location | Dev | Prod |
  |---|---|---|---|
  | Swagger UI `/api/docs` | `config/app.py:50` | enabled | disabled |
  | ReDoc `/api/redoc` | `config/app.py:51` | enabled | disabled |
  | OpenAPI schema `/api/openapi.json` | `config/app.py:52` | enabled | disabled |
  | CORS origins | `config/middleware.py:252` | + ports 3000-3006 x {http,https} x {localhost,127.0.0.1} (24 extra origins) | 8765 only |
  | WebSocket origin allowlist | `config/globals.py:38` | + ports 3000-3006 x {http,https,ws,wss} x {localhost,127.0.0.1} (48 extra origins), frozen at import | 8765 + `file://` |
  | SPA StaticFiles mount at `/` | `main.py:203-208` | not mounted; `/` returns an HTML stub | mounted |
  | CSP applied to the SPA document | `middleware.py:105-134` (see comment at `:73-75`) | not applied (Vite serves the document) | applied |

  Note the `TrustedHostMiddleware` allowlist is **not** dev-gated (correctly), so DNS-rebinding defence survives regardless.
- **Evidence**: `grep -rn -e 'DEV_MODE' -e '"--dev"'` across the repo (excluding `node_modules`) finds exactly three non-test sites: the definition at `config/app.py:27`, `launch-auralis-web.py:69` (`env["DEV_MODE"] = "1"`), and `launch-auralis-web.py:106` (the argparse flag). Nothing validates or namespaces it.
- **Impact**: Three security controls (`#2418`, `#4375`, `#4350`) silently disengage from an inherited env var. Downgraded one level per the localhost-only rule — the widened origins are all loopback and the leaked artifact is an API schema for a local single-user app.
- **Siblings**: `#4350` CLOSED (which introduced the dev gating being widened here).
- **Suggested Fix**: Rename to `AURALIS_DEV_MODE` (keep `DEV_MODE` as a deprecated alias for one release if the launcher contract matters), and log at WARNING when dev mode is active so it is visible in the Electron log.

---

### BE6-11: `set_fingerprint_queue()`'s module global survives rollback, so eight call sites keep enqueueing into a stopped queue

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/startup.py:496`, `/mnt/data/src/matchering/auralis-web/backend/analysis/fingerprint_queue.py:239-250`
- **Status**: NEW
- **Description**: Startup installs the on-demand queue in two places — the component registry (`globals_dict['ondemand_fingerprint_queue']`, `startup.py:497`) and a module global (`set_fingerprint_queue(ondemand_queue)`, `startup.py:496`). Teardown only knows about the first: `_ROLLBACK_SERVICES_TO_STOP` / `stop_background_workers` resolve by registry key and null the registry entry, but nothing ever calls `set_fingerprint_queue(None)`. Every consumer reads the module global, not the registry.
- **Evidence**: All 8 consumers go through `get_fingerprint_queue()`, none through `globals_dict`:
  ```
  services/library_auto_scanner.py:314   routers/fingerprint_status.py:97
  core/stream_fingerprint.py:176         routers/library_scan.py:157
  routers/fingerprint_queue.py:66,118,169   routers/similarity.py:140
  ```
  `analysis/fingerprint_queue.py:242-244` `get_fingerprint_queue()` returns `_fingerprint_queue` unconditionally.
- **Impact**: After `_rollback_partial_startup` (a failed boot) the queue is stopped and the registry says "unavailable", but `get_fingerprint_queue()` still returns the stopped object — so `routers/similarity.py:140` and `core/stream_fingerprint.py:176` enqueue work that will never run instead of taking their `None` branch, and `GET /api/similarity/fingerprint-queue/status` reports on a dead queue. The `POST /api/library/reset` path is unaffected because it restarts the same objects. LOW: the rollback state is already a degraded 503 mode.
- **Siblings**: BE6-2 — same root cause (rollback knows about a subset of what startup installed).
- **Suggested Fix**: Have the rollback/shutdown path call `set_fingerprint_queue(None)`, or better, delete the module global and route the eight consumers through `config.globals.get_component_registry()`, which `#4578` established as the single process-wide registry for exactly this reason.

---

### BE6-12: `RateLimitMiddleware._windows` is only bounded *between* windows, not within one

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/middleware.py:153-154, 167-176, 200-204`
- **Status**: NEW
- **Description**: `_evict_stale_keys` runs every 256 rate-limited requests and removes only keys whose newest timestamp is at least `max_window` (60 s) old:
  ```python
  stale_keys = [k for k, ts in self._windows.items() if not ts or now - ts[-1] >= max_window]
  ```
  Keys created inside the current 60 s window are never evicted, so N distinct keys seen in 60 s means N live dict entries regardless of how often eviction fires. Because the key embeds the full path (BE6-1), N grows with the number of distinct track ids / job ids touched, not with the number of clients.
- **Evidence**: `middleware.py:171-174` (the `>= max_window` cutoff) combined with `key = f"{client_ip}:{path}"` at `:194`. The `#2630` comment at `:153` claims the eviction "bound[s] memory", which is true asymptotically but not within a window.
- **Impact**: A UI that fires `/api/similarity/tracks/{id}/similar` across a 50k-track library within a minute leaves ~50k `{str: [float]}` entries live (~10 MB) until they age out. Not a crash, and it self-heals after 60 s of quiet — but it is a growth path the current comment says does not exist. Fixing BE6-1 (key on the prefix) removes this entirely, since the key space collapses to `clients x 4`.
- **Siblings**: BE6-1 (same root cause).
- **Suggested Fix**: Fixing BE6-1 is sufficient. If per-path keys are ever kept deliberately, add a hard cap on `len(self._windows)` with LRU-style eviction, and correct the `#2630` comment.

---

### BE6-13: `launch-auralis-web.py::start_backend()` ignores its `port` argument and shells out to `npm` in a pnpm-only repo

- **Severity**: LOW
- **Dimension**: Middleware & Config
- **Location**: `/mnt/data/src/matchering/launch-auralis-web.py:52-76, 79-99`
- **Status**: NEW
- **Description**: `start_backend(port=8765, dev_mode=False)` accepts a `port` but never uses it — it launches `[sys.executable, "main.py"]`, and `main.py:235-239` hardcodes `host="127.0.0.1", port=8765`. So `python launch-auralis-web.py --port 9000` (argparse at `:106`) starts the backend on 8765 while the launcher reports 9000. Separately, the frontend branch runs `npm install` and `npm start` (`:88`, `:96`) although `auralis-web/frontend/package.json` declares `"packageManager": "pnpm@10.20.0"` and `CLAUDE.md` states pnpm is the only supported JS package manager (`#4357`).
- **Evidence**: `launch-auralis-web.py:52` signature vs `:71-75` `Popen` — `port` appears nowhere in the body. `main.py:235-239` has no port parameterisation. Frontend `package.json` scripts include both `start` and `dev`, and `packageManager` is `pnpm@10.20.0`.
- **Impact**: `--port` is a silent no-op (the user gets a backend on 8765 and a launcher message claiming otherwise); `npm install` against a pnpm lockfile produces a divergent `node_modules` and can generate a stray `package-lock.json`. Both are developer-workflow papercuts on a documented entry point.
- **Siblings**: `#4357` (pnpm-only policy).
- **Suggested Fix**: Pass the port through (`main.py` reading `--port` / `AURALIS_PORT`, or `uvicorn` invoked with it) or drop the `--port` flag; switch the launcher to `pnpm install` / `pnpm run dev`.

---

### BE7-3: `ModuleError` messages embed absolute filesystem paths and raw FFmpeg stderr; nothing in the backend strips them before logging (and one path is one refactor away from client exposure)

- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis/io/loaders/ffmpeg_loader.py:373`, `:300-313`; `/mnt/data/src/matchering/auralis/io/unified_loader.py:68,73,103,226`
- **Status**: NEW
- **Description**:
  `raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {result.stderr}")` puts the entire FFmpeg stderr — which always begins by echoing the full input path and the build configuration of the local FFmpeg — into the exception message. `load_audio` similarly interpolates `{file_path}` (an absolute path under the user's music library or `/tmp`). The backend currently protects itself by never forwarding these strings (`_safe_error_message` discards the exception text, BE7-2), but it *does* log them at ERROR with `exc_info=True` in eight places, and those logs are persisted by the Electron log sink.
- **Evidence**:
  ```python
  # auralis/io/loaders/ffmpeg_loader.py:372-373
  if result.returncode != 0:
      raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {result.stderr}")
  ```
  This is the same class of leak that `#3844`/`#4376` demoted absolute paths to DEBUG for, and that `#3322`/`#3848` sanitised out of `job.result_data` (`processing_engine.py:486-490` deliberately uses `Path(job.output_path).name`).
- **Impact**:
  Low on its own — desktop-only, and the text does not currently reach the client. The real risk is fragility: BE7-2's natural fix ("surface a more specific message for `ModuleError`") is exactly the change that would start reflecting raw FFmpeg stderr and absolute paths into an HTTP `detail` / WS `audio_stream_error.error`.
- **Siblings**:
  `auralis/io/unified_loader.py:226` (`f"FFprobe failed: {result.stderr}"`), `ffmpeg_loader.py:300-313` (interpolates `{file_path}` twice).
- **Suggested Fix**:
  Truncate/redact stderr at the raise site (keep the last line, drop the banner), and carry the path as a structured attribute on `ModuleError` rather than inside the message so callers can choose to log it without risking reflection.

---

### BE7-7: `PathValidationError` text — the resolved absolute path plus the complete allowed-directory list — is reflected verbatim into HTTP 400 bodies

- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/security/path_security.py:159-162`, `:235-238`; reflected at `/mnt/data/src/matchering/auralis-web/backend/routers/settings.py:207-209` and `/mnt/data/src/matchering/auralis-web/backend/routers/metadata.py:131`, `:176`, `:229`
- **Status**: NEW
- **Description**:
  `validate_user_chosen_directory` / `validate_file_path` build their rejection message from the resolved path *and* an enumeration of every registered allowed directory. Four routes then interpolate that exception straight into an `HTTPException.detail`.
- **Evidence**:
  ```python
  # security/path_security.py:159-162
  raise PathValidationError(
      f"Path '{resolved_path}' is outside allowed directories. "
      f"Allowed directories: {allowed_dirs_str}"
  )
  ```
  ```python
  # routers/settings.py:206-209
  try:
      validated = validate_user_chosen_directory(body.folder.strip())
  except PathValidationError as e:
      raise HTTPException(status_code=400, detail=str(e))
  ```
  Trivially exercisable: `POST /api/settings/scan-folders {"folder": "/etc"}` returns a 400 whose `detail` enumerates the user's entire configured library layout. `routers/metadata.py:131` does the same with `detail=f"Invalid track filepath: {e}"`.
- **Impact**:
  Low in absolute terms — the backend binds `127.0.0.1` and the requester is the user's own renderer, and the value lands in a JSON field that React escapes, so this is not XSS. It is nonetheless the same class the project has repeatedly closed elsewhere (`#3844`, `#3848`, `#3322`, `#4376` all demoted or stripped absolute paths), and it is inconsistent: `startup.py:298` logs the very same directory list at DEBUG "because absolute home/database paths are sensitive and persist to the on-disk electron-log", while this route puts them in a response body.
- **Siblings**: `routers/metadata.py:176`, `:229` (same interpolation); `routers/settings.py:214` echoes `body.folder` back on success.
- **Suggested Fix**:
  Give `PathValidationError` a structured `reason` code plus a `path` attribute, log the full text server-side, and return a fixed message ("Folder is outside the allowed directories") to the client. At minimum drop the `Allowed directories: ...` half from the reflected string.

---

### BE7-8: The registered global `Exception` handler never fires for route exceptions — `RateLimitMiddleware`'s catch-all shadows it, and misattributes every 500

- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/config/app.py:81-87`; `/mnt/data/src/matchering/auralis-web/backend/config/middleware.py:28-38`, `:178-227`, `:302-338`
- **Status**: NEW
- **Description**:
  `config/app.py` registers `@app.exception_handler(Exception)`, which Starlette installs as `ServerErrorMiddleware`'s handler at the **outermost** position (`Starlette.build_middleware_stack`: `[ServerErrorMiddleware] + user_middleware + [ExceptionMiddleware]`). `setup_middleware` adds `RateLimitMiddleware` **first**, making it the innermost user middleware, and its `dispatch` wraps the *entire* body — including the pass-through `return await call_next(request)` for non-rate-limited paths — in `except Exception as exc: return _middleware_error_response(exc, "RateLimitMiddleware")`. Starlette's `BaseHTTPMiddleware.call_next` re-raises the downstream app exception (`raise app_exc from ...`), so an unhandled route exception is caught there and never propagates to `ServerErrorMiddleware`.
- **Evidence**:
  ```python
  # config/middleware.py:178-190, 225-227
  async def dispatch(self, request, call_next):
      try:
          path = request.url.path
          ...
          if limit_rule is None:
              return await call_next(request)
          ...
          return await call_next(request)
      except Exception as exc:
          return _middleware_error_response(exc, "RateLimitMiddleware")
  ```
  ```python
  # config/app.py:81-87 — unreachable for route exceptions
  @app.exception_handler(Exception)
  async def unhandled_exception_handler(request, exc):
      logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
  ```
  Verified against the installed Starlette 0.50.0 / FastAPI 0.128.0 (`build_middleware_stack` order and the `raise app_exc` in `BaseHTTPMiddleware`).
- **Impact**:
  Client-visible behaviour is unchanged (both paths emit `{"detail": "Internal server error"}` with status 500 — no stack trace, no path leak; **check 1 passes on the response side**). The damage is diagnostic: every 500 in the backend is logged as `Unhandled exception in RateLimitMiddleware`, attributing route bugs to a middleware that had nothing to do with them, and dropping the request method and path that `unhandled_exception_handler` was written to record. `#4378`'s justification comment (`middleware.py:31-35`) is also now inaccurate — with an `Exception` handler registered, `ServerErrorMiddleware` would have produced the correct JSON shape, not a plaintext body.
- **Siblings**: `NoCacheMiddleware.dispatch` (`:62`) and `SecurityHeadersMiddleware.dispatch` (`:133`) have the same catch-all; they are outer, so they only see exceptions RateLimit did not already absorb.
- **Suggested Fix**:
  Narrow each middleware's `try` to the code the middleware itself owns (the rate-limit bookkeeping / header mutation), leaving `await call_next(request)` outside it so downstream exceptions reach `ServerErrorMiddleware` and the registered handler. If the belt-and-braces catch is kept, at least log `request.method` and `request.url.path` in `_middleware_error_response`.

---

### BE7-9: Grouped — broad `except` blocks that swallow with no signal

- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: see sibling list
- **Status**: NEW (grouped; the artwork-downloader instance is already tracked OPEN as `#4688` and is excluded)
- **Description**:
  An AST scan of all 118 backend modules found 16 broad handlers (`except Exception` / `except BaseException`) whose body neither logs nor re-raises. Most are defensible best-effort guards; the ones below can hide a real defect indefinitely.
- **Evidence**:
  - `services/audio_content_predictor.py:233-234` — `except Exception: pass  # Fall through to unified loader for MP3/OGG/etc.` The `try` wraps an entire `soundfile` open + seek + read + mono-downmix block, so an indexing bug or a NumPy error in the downmix is indistinguishable from "this format needs FFmpeg", and silently costs a full second decode of the whole file.
  - `core/chunked_processor.py:103` — `except Exception: return None` around the component-registry lookup for the fingerprint repository. This is the exact lookup whose silent failure was `#4578`/`#3836` ("Tier-1 fingerprint lookup is still dead"); a `return None` here reproduces that symptom with no log.
  - `ws_handlers/playback_commands.py:54`, `:338`, `ws_handlers/playback_control.py:78` — `except (asyncio.CancelledError, Exception): pass` around `await old_task`. Correct for the *awaited task's* cancellation, but it also swallows a `CancelledError` targeting the **current** task (shutdown / client disconnect), so the receive loop keeps running one more iteration after it was told to stop.
  - `core/chunked_processor.py:655-657` — per-chunk `except Exception: logger.error(...)` inside `process_all_chunks_async`, followed unconditionally by `logger.info("Background chunk processing complete")` even when every chunk failed.
  - `core/processing_engine.py:479-481` — telemetry `except Exception: pass` (documented and genuinely non-critical; listed for completeness).
  - `core/mastering_target_service.py:255` — Mutagen duration probe falls back to a computed duration with no log.
  - `services/queue_enrichment.py:74-75`, `:124-125` — `except Exception: state = None` on `player_state_manager.get_state()`; a broken state manager degrades the queue response to "engine order only" invisibly.
  - `routers/system.py:132`, `:148`, `:197`, `:269` — `except Exception: pass  # WebSocket may be closed` around the error-frame send. Acceptable, but it also swallows a `json.dumps` failure, which would mean the client got no error frame for a reason unrelated to the socket.
- **Impact**:
  Individually small; collectively these are the places where a future regression will produce a silent behavioural downgrade (no fingerprints, no enrichment, a second full decode per chunk) rather than a diagnosable failure.
- **Siblings**: listed above. `services/artwork_downloader.py:92` is the same shape but already OPEN as `#4688` — do not re-file.
- **Suggested Fix**:
  Add `logger.debug(..., exc_info=True)` to each (the pattern `#4368` already established elsewhere in this codebase), and narrow `except (asyncio.CancelledError, Exception)` to re-raise when `asyncio.current_task().cancelling()` is set.

---

### BE8-11: `asyncio.to_thread`'s default executor is 32 workers on this machine, against a 10-connection DB pool


- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis/library/database.py:127-134` vs. the ~90 `asyncio.to_thread(...)` call sites across `/mnt/data/src/matchering/auralis-web/backend/routers/` and `/mnt/data/src/matchering/auralis-web/backend/services/`
- **Status**: NEW
- **Description**:
  Nothing calls `loop.set_default_executor(...)`, so every `asyncio.to_thread` runs
  on CPython's default `ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4))`
  — 32 on this 32-core box. Nearly every one of those off-loaded calls is a
  repository method that checks out a SQLAlchemy connection. The pool tops out at 10
  (`pool_size=5 + max_overflow=5`) with SQLAlchemy's default `pool_timeout=30`.
- **Evidence**:
  ```
  $ nproc
  32
  $ grep -rn "set_default_executor" auralis-web/backend --include="*.py"   # (no hits)
  ```
  Only two bounded executors exist and neither is the default one:
  `auralis-web/backend/analysis/fingerprint_generator.py:57-73`
  (`_FINGERPRINT_WORKERS = max(1, min(2, cpu_count // 2))`) and
  `core/job_worker.py:56` (`asyncio.Semaphore(max_concurrent_jobs)`).
- **Impact**:
  If more than 10 `to_thread` workers hold a session simultaneously, the 11th blocks
  for up to 30 s and then raises `TimeoutError: QueuePool limit of size 5 overflow 5
  reached`, surfacing as a 500 rather than back-pressure. **Rated LOW deliberately**:
  Auralis is single-user desktop (localhost only), repository methods are
  session-per-method and short-lived, and I could not construct a realistic request
  pattern that keeps 11 sessions open at once — a burst of parallel list requests plus
  a running scan is the closest, and the scan holds one session per batch. It is a
  latent mismatch, not a demonstrated failure.
- **Siblings**: none — this is a global-configuration observation.
- **Suggested Fix**:
  Either cap the default executor in the lifespan
  (`loop.set_default_executor(ThreadPoolExecutor(max_workers=8, thread_name_prefix="auralis"))`)
  or raise `max_overflow` so the pool cannot be starved by the executor. Capping is
  preferable: it also bounds peak audio-buffer memory, since chunk decodes run on the
  same pool.

---

### BE8-12: Small unwrapped filesystem syscalls on the event loop — grouped, with the full sibling list


- **Severity**: LOW
- **Dimension**: Performance
- **Location**: see sibling list below
- **Status**: NEW (excludes the already-filed #4653 / BE1-02 upload write and #4702 / BE1-08 sync enqueue)
- **Description**:
  An AST sweep of every `async def` in `auralis-web/backend/` (109 files) for blocking
  primitives (`open`, `sf.*`, `subprocess`, `requests`/`urllib`, `time.sleep`, `os.walk`,
  `shutil`, `.stat()`, `.exists()`, `glob`, `json.load`, `Path.mkdir/unlink`) found the
  code to be in **good** shape overall: 90+ heavy calls are correctly wrapped in
  `asyncio.to_thread`. What remains is a residue of single-syscall `stat`/`exists`/
  `mkdir`/`resolve` calls made directly on the loop. Each is sub-millisecond on a local
  SSD; on a network-mounted or spun-down music drive they are not, and they run on the
  request-serving loop.
- **Evidence** (each verified as NOT inside a nested sync helper and NOT wrapped):
  - `routers/artwork.py:242` `artwork_dir.mkdir(parents=True, exist_ok=True)` — on every artwork request
  - `routers/artwork.py:250` `Path(album.artwork_path).resolve(strict=False)`
  - `routers/artwork.py:266` `if not requested_path.exists():`
  - `routers/artwork.py:307` `stat = serve_path.stat()`
  - `routers/enhancement.py:190` `if os.path.exists(wav_chunk_path):` — inside a 3-iteration loop
  - `routers/processing_api.py:238` `temp_dir.mkdir(exist_ok=True)`
  - `routers/processing_api.py:292` `input_path.unlink(missing_ok=True)`
  - `routers/processing_api.py:349` `if not output_path.exists():`
  - `routers/files.py:259` `Path(temp_path).unlink(missing_ok=True)`
  - `core/processing_engine.py:391` `Path(reference_path).exists()`
  - `core/processing_engine.py:667-676` `output_path.exists()` / `input_path.exists()` / `file_path.unlink()` — inside `cleanup_old_jobs`'s per-job loop, the worst of the set
  - `core/proactive_buffer.py:78` `if chunk_path.exists():` — per preset, per prefetch
  - `core/stream_prefetch.py:87` `Path(next_track.filepath).exists()`
  - `core/streamlined_worker.py:404` `if not Path(track.filepath).exists():` — per chunk
  - `core/chunked_processor.py:672` `if full_path.exists():`
  - `cache/adapter.py:150` `temp_dir.mkdir(parents=True, exist_ok=True)` (dead code — see BE8-14)
  - `config/startup.py:268-271, 294` `chunk_dir.exists()` / `shutil.rmtree(chunk_dir)` / `mkdir` — **`shutil.rmtree` of the whole chunk-cache dir runs on the loop during lifespan startup**; up to 512 MB of WAVs. Startup-only, so no request is blocked, but it delays readiness.
  - `core/stream_normal.py:370` `shutil.rmtree(temp_dir, ...)` in a `finally` — removes a temp dir holding a full decoded WAV (can be hundreds of MB) on the loop at the end of every compressed-format normal stream.
- **Impact**:
  Individually negligible on local storage. The two `shutil.rmtree` sites
  (`config/startup.py:270`, `core/stream_normal.py:370`) are the only ones with a
  plausibly multi-hundred-millisecond cost, and `cleanup_old_jobs` is the only one in
  an unbounded loop.
- **Suggested Fix**:
  Wrap the two `shutil.rmtree` calls and the `cleanup_old_jobs` loop body in
  `asyncio.to_thread`. The single `stat`/`exists` calls are not worth churning
  unless someone is already editing the function.

---

### BE8-13: The fingerprint `ThreadPoolExecutor` is torn down only by `atexit`, never by the lifespan


- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/analysis/fingerprint_generator.py:61-88`, vs. `/mnt/data/src/matchering/auralis-web/backend/config/startup.py:100-165`
- **Status**: NEW
- **Description**:
  `_shutdown_components()` explicitly tears down the background workers, the cache
  worker, the processing engine, the audio player, the `ProcessorFactory` thread pools
  (#3746), the aiohttp session (#3915), and the database. It does **not** call
  `shutdown_fingerprint_executor()`. That function is reached only through
  `atexit.register(...)` at `fingerprint_generator.py:88`.
- **Evidence**:
  `analysis/fingerprint_generator.py:77-88`
  ```python
  def shutdown_fingerprint_executor() -> None:
      """Shutdown the fingerprint executor gracefully."""
      global _fingerprint_executor
      if _fingerprint_executor is not None:
          logger.info("🛑 Shutting down fingerprint ThreadPoolExecutor...")
          _fingerprint_executor.shutdown(wait=False, cancel_futures=True)
          _fingerprint_executor = None

  # Register cleanup on exit
  atexit.register(shutdown_fingerprint_executor)
  ```
  `grep -rn "shutdown_fingerprint_executor" auralis-web/backend/config/` → no hits.
- **Impact**:
  Two consequences, both mild. (1) `atexit` runs after the ASGI lifespan, so up to
  `_FINGERPRINT_WORKERS` threads (default `max(1, min(2, cpu//2))` = 2) survive the
  documented shutdown sequence and can still be executing Rust DSP while the library
  database is being WAL-checkpointed and disposed at `startup.py:160`. (2)
  `concurrent.futures.thread` also registers its own interpreter-exit hook that
  *joins* worker threads, so `cancel_futures=True` cannot preempt a fingerprint
  already running inside the PyO3 call — process exit waits for it.
  I could not demonstrate a concrete corruption from (1): `FingerprintStorage` uses
  its own session factory and SQLite WAL tolerates a late writer. Rated LOW on that basis.
- **Siblings**:
  - The `similarity-autofit` daemon thread (`config/startup.py:546-550`) is likewise unjoined — **already filed as #4682, skipped**.
  - `auralis/analysis/fingerprint/fingerprint_service.py:47-63` creates a private engine; #4501 (CLOSED) added its disposal path — verified still present, not re-filed.
- **Suggested Fix**:
  Add a guarded `shutdown_fingerprint_executor()` step to `_shutdown_components()`
  (before the database step), and switch it to `shutdown(wait=True)` with a bounded
  timeout so the checkpoint cannot race an in-flight writer.

---

### BE8-14: `StreamlinedCacheAdapter` is dead code carrying an unbounded in-memory audio cache


- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/cache/adapter.py:72,175-176`
- **Status**: NEW
- **Description**:
  `StreamlinedCacheAdapter._temp_chunk_cache` is a plain `dict[str, tuple[np.ndarray, int]]`
  that `put()` writes to on every call and that only the (never-called) `clear()`
  drains. No size cap, no byte cap, no LRU — unlike its live counterpart
  `SimpleChunkCache`, which caps at 50 chunks / 512 MB (`core/chunk_cache.py:32,123-130`).
- **Evidence**:
  `cache/adapter.py:72`
  ```python
          self._temp_chunk_cache: dict[str, tuple[np.ndarray, int]] = {}  # Temporary in-memory cache for current session
  ```
  `cache/adapter.py:174-176`
  ```python
          # Also store in temporary in-memory cache for fast access
          cache_key = f"{track_id}_{chunk_idx}_{preset}_{intensity:.2f}"
          self._temp_chunk_cache[cache_key] = (audio, sample_rate)
  ```
  **Disproved as an active leak**: the class is never instantiated. Its only
  references are its own definition and the `__init__.py` re-export:
  ```
  cache/__init__.py:15:from .adapter import StreamlinedCacheAdapter
  cache/__init__.py:56:    "StreamlinedCacheAdapter",
  ```
  `routers/cache_streamlined.py:16` imports `StreamlinedCacheManager`, not the adapter.
  Severity is therefore LOW (dormant hazard), not HIGH.
- **Impact**:
  None today. If anyone ever wires the adapter in — which the `__init__` export
  invites — every processed chunk of every track played in the session is retained
  in RAM at ~5 MB each, with no ceiling.
- **Siblings**:
  `monitoring/memory_monitor.py:214` `degradation_history` (also unbounded, also dead — see BE8-08).
- **Suggested Fix**:
  Delete `cache/adapter.py` and its export (it duplicates `SimpleChunkCache`'s role,
  which the No-variants principle disallows), or give `_temp_chunk_cache` the same
  `OrderedDict` + byte-budget eviction `SimpleChunkCache` already implements.

---

### BE8-15: Enhancement toggle rebuilds a throwaway `ChunkedAudioProcessor` with an isolated chunk-cache dict


- **Severity**: LOW
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/routers/enhancement.py:162-176`
- **Status**: NEW
- **Description**:
  `_preprocess_upcoming_chunks` — invoked whenever enhancement is toggled mid-playback —
  probes the file with `sf.info`, then constructs a **new** `ChunkedAudioProcessor` with
  `chunk_cache={}`, ignoring the two processor caches that already exist for exactly
  this track/preset/intensity key (`core/streamlined_worker.py:85` `_processor_cache`
  and `core/processor_factory.py:100`).
- **Evidence**:
  `routers/enhancement.py:162-176`
  ```python
              info = await asyncio.to_thread(sf.info, filepath)
              ...
              processor = await asyncio.to_thread(
                  ChunkedAudioProcessor,
                  track_id=track_id,
                  filepath=filepath,
                  preset=preset,
                  intensity=intensity,
                  chunk_cache={},
              )
  ```
- **Impact**:
  One redundant `sf.info` probe plus one redundant `ChunkedAudioProcessor.__init__`
  (documented at `core/streamlined_worker.py:438-444` as "a sync SoundFile open for
  metadata, a sync fingerprint/DB lookup, and sync HybridProcessor construction
  (200-500 ms CPU-bound)") per toggle. It is correctly off-loaded to a thread, so the
  loop is not blocked, and the empty `chunk_cache` does **not** cause reprocessing —
  `get_wav_chunk_path` falls back to an on-disk existence + completeness check
  (`core/chunked_processor.py:756-760`), so already-cached chunks are still hit.
  That disproof is why this is LOW rather than MEDIUM.
  Also note `sf.info` will raise for `.m4a/.aac/.wma` (see BE8-06), so on those formats
  this whole prefetch silently no-ops via the outer `except` at `:202`.
- **Siblings**:
  `services/recommendation_service.py:82,142` also build ad-hoc `ChunkedAudioProcessor`s.
- **Suggested Fix**:
  Route through `StreamlinedCacheWorker.trigger_immediate_processing` (which owns the
  keyed processor cache) instead of constructing a processor here.

---

### BE8-16: `StreamlinedCacheManager` holds its asyncio lock across awaited work — PARTIAL, not fully verified


- **Severity**: LOW (provisional — see caveat)
- **Dimension**: Performance
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/cache/manager.py:236` (awaits at `:262`, `:267`), `:336` (awaits at `:360`, `:369`), `:530` (await at `:547`)
- **Status**: NEW — **PARTIAL, not fully verified**
- **Description**:
  An AST sweep for `async with <lock>:` blocks containing an inner `await` flagged
  three sites in the streamlined cache manager. This is the same shape as the
  already-filed #4689 (`ProcessorPool.get_or_create` holds its asyncio lock across
  a 200-500 ms construction) and #4675 (`ProcessorFactory` RLock).
- **Evidence**:
  Scan output only — I did **not** read the bodies of these three methods, so I do not
  know what the awaited calls are, how long they take, or whether the lock is genuinely
  required for the whole critical section. **Do not act on this without reading
  `cache/manager.py:230-280`, `:330-375`, and `:525-555` first.**
- **Impact**: Unknown. If the awaited calls are disk I/O via `to_thread`, this
  serialises all cache reads/writes across all concurrent streams; if they are cheap
  in-memory coroutines, it is a non-issue.
- **Siblings** (same scan, all deliberately NOT flagged as findings — each looked
  intentional or is already filed):
  - `services/playback_service.py:153,195,229,270` — `_playback_lock` across awaits; the broadcast-inside-lock variant is #4581 (CLOSED).
  - `core/processor_pool.py:88` — **already filed as #4689, skipped.**
  - `core/streamlined_worker.py:433` — `build_lock` across the processor build; this is the *intended* single-flight behaviour added by #4369/#4521.
  - `services/queue_service.py:216` — `_set_queue_lock` across `_set_queue_impl`; intentional per #3721.
- **Suggested Fix**: Read the three sites; if the awaited work is I/O, narrow the lock
  to the dict mutation only (the #4689 remediation pattern applies verbatim).

---

### BE9-06: Two `assert True` placeholder tests stand in for the streaming/mastering integration flows they name

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/integration/test_priority4_streaming_integration.py:218-236`, `:239-254`
- **Status**: NEW
- **Description**: Check 8. Two tests in a file named `test_priority4_streaming_integration.py` consist of a comment block describing what should be asserted, followed by `assert True`.
- **Evidence**:
  - `:218-236`, `TestEnhancementRouterEndpoint::test_mastering_recommendation_endpoint_parameters`:
    ```python
        # Expected responses:
        #   - 400: Missing filepath parameter
        #   - 404: Track not found
        #   - 500: Analysis failed
        #   - 200: Returns MasteringRecommendation JSON

        assert True  # Placeholder for integration test
    ```
  - `:239-254`, `TestPlayerRouterTrackLoading::test_load_track_generates_recommendation` — same shape, and it even builds `mock_broadcast = AsyncMock()` that is never used.
  - The endpoint they describe is real (`auralis-web/backend/routers/enhancement.py:402`, `GET /api/player/mastering/recommendation/{track_id}`), and is separately covered by `tests/backend/test_enhancement_api.py:182-290` — so the placeholders are pure noise inflating the pass count.
- **Impact**: Two always-green tests in the integration suite. Low, because the underlying endpoint does have real coverage elsewhere; the harm is a misleading test inventory.
- **Siblings**: `tests/security/test_input_validation.py:94` `assert True, "Homograph handled without crash"`; `:167` `assert True, "LDAP injection handled safely"`; `tests/regression/test_version_compatibility.py:421` `assert True, "Import attempt should not crash"`. All three are "did not raise" tests with the assertion written as a tautology instead of just letting the call stand.
- **Suggested Fix**: Delete the two placeholders (the real coverage exists), and rewrite the three `assert True, "..."` sites as bare calls or real assertions.

---

### BE9-07: `core/stream_prefetch.py` and `core/stream_chunk_ops.py` (360 lines of the streaming path) have zero test references

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/auralis-web/backend/core/stream_prefetch.py` (129 lines), `/mnt/data/src/matchering/auralis-web/backend/core/stream_chunk_ops.py` (231 lines)
- **Status**: NEW
- **Description**: Every other member of the `stream_*` family is referenced by between 2 and 14 test files. These two are referenced by none — `grep -rl --include="*.py" "stream_prefetch" tests/` and the same for `stream_chunk_ops` both return empty.
- **Evidence**: per-module reference counts across `tests/`: `stream_enhanced` 11, `stream_normal` 14, `stream_seek` 9, `stream_protocol` 3, `stream_messages` 2, `stream_fingerprint` 1, **`stream_prefetch` 0**, **`stream_chunk_ops` 0**. `stream_prefetch` backs `AudioStreamController._prefetch_next_track` (`core/audio_stream_controller.py:293`); `stream_chunk_ops` backs `_process_chunk_only` / `_stream_processed_chunk` / `_process_and_stream_chunk` (`:271-291`).
- **Impact**: Prefetch of the next track and the per-chunk process/stream helpers are exercised only transitively, if at all. LOW because the code appears to work in practice and the enclosing paths do have tests — but a prefetch bug (wrong track, leaked task, double-processing) has no direct guard.
- **Siblings**: `ws_handlers/messages.py` handlers `handle_ping`/`handle_pong`/`handle_heartbeat`/`handle_subscribe_job_progress` similarly have no test that imports them by name.
- **Suggested Fix**: Add a focused test per module: prefetch triggers once per track transition and is cancelled on stop; `stream_chunk_ops` returns the expected sample count and honours the cache path.

---

### BE9-08: No test anywhere exercises a locked/busy SQLite database

- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `/mnt/data/src/matchering/tests/backend/`, `tests/integration/`, `tests/concurrency/`, `tests/regression/`
- **Status**: NEW
- **Description**: Check 6 (error scenarios). `grep -rln --include="*.py" "database is locked\|OperationalError\|SQLITE_BUSY"` across all four directories returns **nothing**. "Database locked" is a documented, recurring operational failure for this project (it has its own row in the `CLAUDE.md` troubleshooting table, with "delete `~/.auralis/library.db`" as the remedy), yet no test asserts how a router behaves when a write contends with the background scanner or the fingerprint worker.
- **Evidence**: the grep above; contrast with `tests/backend/test_concurrent_operations.py`, `test_concurrent_streaming.py`, `test_rate_limit_middleware_concurrency.py`, which cover in-process concurrency but never DB-level contention.
- **Impact**: The behaviour of every repository-backed router under `OperationalError` is unspecified and untested — it may surface as a bare 500 rather than a retry or a 503. LOW because this audit found no evidence the handling is currently wrong, only that it is unverified.
- **Siblings**: Corrupt-file handling *is* covered (16 files); timeouts *are* covered (12 files). DB contention is the one missing member of the error-scenario triad.
- **Suggested Fix**: One integration test that holds an exclusive transaction on `library.db` while issuing a write through a router, asserting the mapped status code and that the connection is returned to the pool.

---

## Relationships and shared root causes

### Cluster A — the level-smoothing catastrophe (BE3-07 ← BE3-08 ← BE3-09)
This is a three-finding chain, not three independent bugs.
- **BE3-09** makes `_get_current_chunk` return an index one too high for the first half of every emitted chunk window (the #4557 fix was never propagated out of `stream_seek.py`).
- That makes **BE3-08**'s unbounded `next_chunk_idx = current_chunk + 1` overflow past `total_chunks` starting at ~57 % of a short track instead of at its very end, so the prefetch worker manufactures a **10 s all-zero chunk** on the 1 Hz tick, every second, on every track.
- That all-zero chunk records −200 dB into the shared `LevelManager` history, which **arms BE3-07** — the unbounded gain correction that produces the 50 ms full-scale burst and then destroys the rest of the track.

`chunked_processor.py:489-495` provides a *second*, independent trigger: it replaces an empty post-trim chunk with 100 ms of `np.zeros(...)` and feeds it straight into `_smooth_level_transition`. So the answer to "does a failed chunk corrupt subsequent chunks?" is yes, catastrophically. **Fixing BE3-07's clamp alone stops the audible damage; fixing BE3-09 and BE3-08 stops the wasted DSP, the cache pollution, and the false `trim_context` warnings.** Fix all three.

### Cluster B — lossy streams that report success (BE2-02, BE2-03, BE2-06 + BE7-5, BE2-04)
`safe_send`/`safe_send_bytes` convert every send failure into `return False`, and `send_pcm_chunk` then returns *normally* with no return value — so the caller credits a chunk it never delivered (BE2-02). If the meta frame lands and the binary frame does not, the client's single-slot `pendingMeta` fuses stale metadata onto the next chunk, permanently desyncing frame pairing and defeating the #4563 epoch guard and #4434 track guard (BE2-03). Separately, the `#3190` skip-and-continue branch leaves `stopped_early` False, so `audio_stream_end` reports `reason="completed"` and the full duration after dropping chunks (BE2-06 + BE7-5 — found independently on two different trigger paths). Underneath all of it, the two documented backpressure guards are **inert** because uvicorn's sans-io WebSocket protocol implements no write flow control (BE2-04), so the only real flow control is the cooperative client `buffer_full` signal — which a half-open peer never sends.

**Shared root cause: the streaming layer has no failure channel.** Every one of these converts a data-loss event into a success-shaped terminal message. Fix `send_pcm_chunk` to return a bool (or raise) and thread that through the three stream loops, and BE2-02, BE2-03 and BE2-06 all become reportable.

### Cluster C — startup/shutdown asymmetry (BE6-2, BE6-9, BE6-11, BE4-10, BE4-4, BE7-4)
Three different teardown paths know about three different subsets of what startup installed. `_rollback_partial_startup` nulls `library_manager`/`audio_player` **without** calling the `.shutdown()`/`.cleanup()` that `_shutdown_components` calls for exactly those objects — and the null-out then makes the later shutdown a no-op, leaving the SQLite engine and audio device unreachable for the process lifetime (BE6-2). The lifespan `yield` is not in `try/finally`, so a cancelled lifespan task skips **all** teardown including the WAL checkpoint (BE6-9). `set_fingerprint_queue()`'s module global survives rollback, so eight call sites keep enqueueing into a stopped queue (BE6-11). `PlayerStateManager`'s 1 Hz task has no symmetric stop (BE4-10). And `auralis_processing`/`auralis_uploads` are reclaimable only from in-memory job state, so a crash orphans them forever (BE4-4 + BE7-4). **#4569 hardened every step *inside* `_shutdown_components`; the structural gap is which paths reach it at all.** The right fix is to extract per-component teardown into named helpers called from both rollback and shutdown, so the two cannot diverge again.

### Cluster D — tested but unwired (BE6-3 + BE8-08, BE4-14, BE6-7, BE1-7 + BE5B-N7, BE5B-N1, BE8-14, BE4-12)
Roughly 3,000 lines of the backend are reachable only from their own tests: `monitoring/` (936 lines — so no cache ever shrinks under memory pressure), `services/learning_system.py` + `audio_content_predictor.py` (1,062 lines, with three entirely unsynchronised singletons), `validate_scan_path`/`is_safe_filename` (the only allowlist-enforcing validators, both dead), `cache/endpoints.py` (344 lines, zero routes), 15 orphan models in `schemas.py`, `StreamlinedCacheAdapter`, and the `get_mastering_target_service()` singleton. **Passing tests are what makes this invisible** — and fix effort has already been spent on it: #4379 hardened a blocking-I/O path in `AudioContentPredictor` that production never executes. Same family as open #4592 and #4565, which cover `auralis/` rather than the backend.

### Cluster E — incomplete fixes (BE1-2, BE3-09, BE4-5, BE6-5, BE8-06, BE7-5, BE2-01)
Seven findings are the un-migrated tail of a fix that landed elsewhere. BE1-2 is the sharpest: the #4555 mass-assignment allowlist is keyed on **ORM column names** while the router sends **mutagen tag names**, so `track_number`/`disc_number`/`comments` are written to the file and silently dropped from the DB — and the route still reports `success: true` with those field names. **Suggested process fix:** when a fix introduces an allowlist or moves a constant, add a test that asserts the two sides agree (e.g. every key in `MetadataUpdateRequest.model_fields` is in `_METADATA_WRITABLE_COLUMNS` or explicitly documented as file-only), rather than relying on the next audit to find the gap.

### Cluster F — frontend/backend contract drift with no test to catch it (BE5-N1, BE5B-N4, BE5B-N5, BE5B-N3, BE1-8)
`useQueueFetch` reads `is_shuffled` from an endpoint that only ever emits `shuffle_enabled`, so the shuffle flag resets to `false` on every mount (BE5B-N5). This **cross-references the completed frontend audit**, which independently found that the queue hooks send wrong payload shapes and that their tests mock `useRestAPI` wholesale without asserting URL or body — the same root pattern. `settingsService.updateSettings()` is typed as returning `UserSettings` but the endpoint returns a `{message, settings}` envelope, and the dialog stores the envelope as state (BE5-N1). `GET /api/cache/stats` puts `tracks_cached` under `tier2` while the model, the TS type and three Redux selectors all read `overall.tracks_cached` (BE5B-N4). **Shared root cause: no contract test asserts the wire format.** A generated-OpenAPI-vs-TS check would catch all of these at once, and would also catch BE1-8 (four `ENDPOINTS` constants naming routes that do not exist).

---

## Prioritized fix order

### 1 — Stop the audible damage (do first)
| # | Finding | Why first |
|---|---|---|
| 1 | **BE3-07** (CRITICAL) | Full-scale 50 ms burst at whatever monitoring level the user has set, plus permanent destruction of the rest of the track. Listener-safety. The clamp is a few lines. |
| 2 | **BE3-08** (HIGH) | Manufactures BE3-07's trigger on **every track**, once per second. Fixing it removes the most common path into the CRITICAL. Two-line bound against `status.total_chunks`. |
| 3 | **BE3-09** (MEDIUM) | Makes BE3-08 fire at 57 % of a track instead of at its end, and makes the enhancement pre-fetcher skip the one chunk it exists to warm. Propagating `chunk_for_position()` is mechanical. |

These three are one chain; land them together with a regression test covering a digitally-silent chunk.

### 2 — Stop lying to the user
| # | Finding | Why |
|---|---|---|
| 4 | **BE2-01** (HIGH, regression of #3763) | Mid-playback preset/intensity/toggle-ON are silent no-ops **and the UI reports success**. Two independent confirmations, one empirical. Also: close or rewrite #4425, whose premise is wrong. |
| 5 | **BE1-2** (HIGH) | Track/disc/comment edits diverge file from DB while returning `success: true`. Album track ordering visibly reverts on reload. |
| 6 | **BE1-1** (HIGH) | Lyrics feature is non-functional for every track whose lyrics live only in the file; fails as HTTP 200 `lyrics: null`, indistinguishable from "no lyrics". Wrong method + wrong signature. |
| 7 | **BE2-02 → BE2-03 → BE2-06** | One fix (`send_pcm_chunk` returns a bool) makes all three reportable instead of silent. |

### 3 — Resource and correctness under load
| # | Finding | Why |
|---|---|---|
| 8 | **BE7-1** (HIGH) | Orphan thread + next job mutate the same pooled processor; leaks a default-executor slot permanently. Repeated timeouts stall the whole backend. Do not return the processor on the timeout branch. |
| 9 | **BE8-06** (HIGH) | ~60× CPU/IO amplification on M4A/AAC/WMA. Hoist `stream_normal.py`'s once-per-track temp-WAV conversion into `ChunkedAudioProcessor.__init__`. |
| 10 | **BE4-1** (HIGH) | `mode="reference"` fails 100 % of the time and reports it as bad user input. One of three advertised modes is dead. |
| 11 | **BE4-5, BE4-6** (MEDIUM) | Event-loop stalls of hundreds of ms to 5 s that freeze all HTTP **and** all WebSocket audio. Both are the un-migrated tail of #3716/#3554. |

### 4 — Restore the safety net (do before or alongside everything above)
| # | Finding | Why |
|---|---|---|
| 12 | **BE9-01** (HIGH) | Commit `pytest-baseline.json`. Until this lands, none of the fixes above are protected against regression and the CI signal stays meaningless. Arguably item 0. |
| 13 | **BE9-02 – BE9-05** (MEDIUM ×4) | The tests that *do* run include ~70 assertions accepting the 500 they are meant to rule out, six structurally-guaranteed skips, and two dead tests for the streaming-semaphore invariant. Fixing the gate without fixing these just ratchets in a false baseline. |

### 5 — Then the remaining MEDIUMs, then LOWs
Take Cluster C (startup/shutdown symmetry) as one work item rather than six — the extract-shared-teardown-helpers refactor closes BE6-2, BE6-9, BE6-11, BE4-10 and BE4-4/BE7-4 together. Take Cluster D as a single decision (wire it or delete it) rather than seven separate cleanups. Take Cluster F as one contract test rather than five schema edits.

**Do not** apply BE3-14's crossfade curve change until the conflict with the engine audit's Dimension 1 conclusion is resolved (see Executive summary).

---

## Deduplication ledger

Findings observed but **not filed** because an OPEN issue already covers them:

`#4361` (module-level shared `APIRouter` in 8 routers) · `#4647` (enhancement response types looser than request types) · `#4681` / prior BE5-05 (player/queue bodies lack numeric range constraints) · `#3838` (~28 endpoints missing `response_model=` — known, do-not-refile) · `#4703` (`manager.connect()` rejection not propagated) · `#4704` (`handle_seek` re-implements `_cancel_prior_task`) · `#4677` (seek preset precedence) · `#4680` (WS message-type registry drift) · `#4655` (`recovery_position` unread) · `#4654` (`preset: "none"`) · `#4431` (`total_duration` divergence) · `#4666` (chunk cache not keyed on mastering targets) · `#4669` (disk-cache hit skips LevelManager recording) · `#4705` (cache re-derives `content_chunk_count` — **verified already fixed**, duplicate of closed #4620) · `#4675` (`ProcessorFactory` RLock across construction) · `#4689` (`ProcessorPool` lock across `_create_processor`) · `#4707` (`intensity` in cache key but not a processor parameter) · `#4706`, `#4543` (`JobWorker.stop()` semantics) · `#4359`, `#4690` (queue broadcast N+1) · `#4682` (similarity autofit thread never joined) · `#4671` (439-line `lifespan()`) · `#4653` (500 MB synchronous upload write) · `#4684` (`HAS_AURALIS` hardcoded) · `#4712` (CSP omits `127.0.0.1`) · `#4713` (`reclaim_leftover_stream_temps` too broad) · `#4678` (`Track.to_dict()` omits 6 fields) · `#4708`, `#4709`, `#4710`, `#4711` · `#4676` (`artwork_updated` untyped) · `#4651` (scan broadcasts absolute paths) · `#4398`, `#4372`, `#4460` (unused TS contract types) · `#4381` (playlist tests module-skipped) · `#4715` (`refresh-references` unreferenced) · `#4716`, `#4717` (similarity test gaps) · `#4234` (`test_repositories.py` pre-existing broken).

Closed issues **re-verified as still fixed** (no regression): `#4656`, `#4658`, `#4424`, `#4557`, `#4576`, `#4124`/`#4356`, `#4238`, `#4342`, `#4569`, `#4375`, `#4378`, `#4350`, `#4351`/`#4366`, `#4567`, `#4497` (metadata path only — see BE8-06), `#2327`, `#3192`, `#3513`, `#4358`, `#4563`, `#4434`, `#4620`, prior BE1-04, prior BE8-05.

Notable exception: **BE2-01 is a genuine regression of closed `#3763`.** It is the only regression found in this audit.

---

## Disproved hypotheses (investigated and ruled out — do not re-file)

- **Two `WAVEncoderError` classes** — false; only one exists (see Skill-file correction above).
- **Concurrent WebSocket send corrupting frames** — no send lock exists, but uvicorn's sans-io protocol serialises each frame with a single synchronous `transport.write`, so frames cannot interleave byte-wise. A heartbeat `ping` landing between an `audio_chunk_meta` and its binary frame is harmless.
- **Producer/consumer deadlock in `send_pcm_chunk`** — the consumer drains the queue before breaking, so the producer's `finally: await queue.put(None)` always has room.
- **`output_format` path traversal** — `f"{job_id}_processed.{output_format}"` cannot escape `temp_dir`; the traversal component would have to exist as a directory named `<uuid>_processed.<prefix>`.
- **`path_security.py` prefix-match bypass** (`/music-evil` vs `/music`) — containment uses `relative_to()` on `.resolve()`d paths, i.e. path-component matching. `Path('/music-evil/x').relative_to(Path('/music'))` raises `ValueError`. Case-insensitive filesystems fail *closed*.
- **Static mount shadowing API routes** — verified live: `/api/unknown` returns a JSON 404, not an SPA 200 fallback; `html=True` only serves `index.html` for *directory* requests. `/ws` still reaches its WebSocketRoute.
- **Chunk boundary truncation drift** — `round()` is used throughout and all chunk starts are integer seconds, so the boundary/trim/extract chain reconstructs the source timeline exactly. Verified for durations 3, 12, 15.0, 15.2, 16, 25.0, 25.5, 31, 35, 36 s. **No drift accumulates.**
- **Stale chunk written into a new track's cache slot** — keys and on-disk filenames embed `track_id`, `file_signature`, `preset`, `intensity`, `chunk_index` and `CACHE_VERSION`; worst case a superseded task rewrites its own byte-identical file.
- **`cancel_job()` racing `_prepare_job`'s `setdefault`** — `_prepare_job` runs atomically between awaits; no window exists.
- **`ProcessorPool` exhaustion/deadlock** — `get_or_create` constructs on miss rather than blocking; `submit_job` raises `QueueFull`, mapped to 503.
- **`asyncio.wait_for(semaphore.acquire())` permit leak** — CPython 3.14's `Semaphore.acquire` re-releases on cancel-after-wake.
- **`AudioProcessingPipeline`'s unlocked "normal processing" branch** — `HybridProcessor.process()` takes `_process_lock` itself.
- **Engine call-site signature mismatches** — `load_audio`, `resample_audio` and `save` all verified against the real engine signatures. The only integration mismatch is the return-shape one in BE4-2.
- **`PlaybackState` enum leaking as `"PlaybackState.STOPPED"`** — it subclasses `str`, so the C encoder serialises the underlying buffer.
- **`filepath` leaking to clients** — `Track.to_dict()` omits it, `DEFAULT_TRACK_FIELDS` omits it, `TrackInfo.filepath` is `Field(exclude=True)`, `Album.to_dict()` rewrites `artwork_path` to an API URL. No leak found on any examined path.
- **`scan_progress.phase` enum drift** and **`audio_chunk_meta` / `audio_stream_start` / `audio_stream_end` / `audio_stream_error` / `fingerprint_progress` / `enhancement_settings_changed` field drift** — all verified to match their frontend types exactly.
- **`LibraryStats` shape drift** — every field the TS interface declares is produced.

---

## Next step

```
/audit-publish docs/audits/AUDIT_BACKEND_2026-07-29.md
```

Suggested labels when publishing: severity label (`critical` / `high` / `medium` / `low`) + `backend` + `bug`, plus `websocket`, `streaming`, `audio-integrity`, `performance`, `concurrency`, `tech-debt` as applicable per finding.
