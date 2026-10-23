# Security Audit (OWASP Top 10, 2021) — 2026-10-22

**Scope**: `auralis-web/backend/` (routers, middleware, WebSocket, streaming), `auralis/` (io, library, scanner, services, logging), `auralis-web/frontend/`, `desktop/` (Electron), `.github/workflows/`, dependency locks.
**Method**: Fresh read of the current tree (HEAD `44e4d433`), one category agent per OWASP category (A01–A10, `--depth deep`, no limit), deduplicated against `gh issue list --state all` (5,613 issues, max #5859) and against each other. Every MEDIUM was spot-re-verified by the orchestrator against the source (temp-dir ownership, artwork fail-open, engine logging facade, `cleanupPort`, uvicorn call, Electron advisory range).
**Baseline**: No authentication by design (desktop app, uvicorn bound to `127.0.0.1`). Per `_audit-severity.md`, findings reachable only by a local process are downgraded one level.

---

## Executive Summary

| Severity | Count |
|----------|------:|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 9 |
| LOW | 41 |
| **Total** | **50** |

No path traversal, SQL injection, command injection, SSRF, XSS, WebSocket origin bypass or CSRF gap on state-changing routes was found. The perimeter controls added over the last audit cycles still work and were re-checked:
- TrustedHost (including the WS upgrade).
- The OriginCheck middleware on POST/PUT/DELETE/PATCH.
- The WS origin check before `accept()`.
- `validate_file_path` on every stream path.
- The ffmpeg `-protocol_whitelist file` in all five subprocess sites (it survived the #5835 split).
- Per-hop artwork redirect validation.
- CSP `form-action` / `base-uri`.

None of the #5831/#5832 router splits dropped a validation call.

**Key themes**
1. **Supply chain around the shipped binary** (SEC-01, SEC-02, plus open #4905):
   - The release jobs hash-lock runtime dependencies but install `pyinstaller` / `maturin` / `setuptools` / `wheel` floating.
   - The Electron runtime (43.7.6) is below the fix for a high-severity advisory about compromised TLS intermediates.
   - The only network path in the packaged app is the unsigned auto-update channel.
3. **Crafted media files as the attack vector** (SEC-03, SEC-04, SEC-13, SEC-20, SEC-33):
   - A decompression-bomb cover passes the guard that exists to stop it.
   - A quadratic regex on the artist tag freezes the whole backend (it holds the GIL).
   - Folder `cover.jpg` symlinks are copied into the served artwork directory.
   - Genre tags and `.25d` sidecars are trusted without size or range limits.
4. **Resource exhaustion on the shared I/O executor** (SEC-07, SEC-08, SEC-21): graph builds and per-play recommendation analyses pin `IO_EXECUTOR` workers that every repository call also needs.
5. **Audit-trail gaps** (SEC-06, SEC-43..SEC-48): the engine-level `auralis.utils.logging.warning()/error()` facade discards every message in production (59 modules, including scan aborts and migration failures). uvicorn's own handlers bypass the #5393 sanitizer.
6. **Local-trust assumptions in the desktop shell** (SEC-09, SEC-24, SEC-25, SEC-26):
   - `cleanupPort()` SIGKILLs any process with a socket on 8765.
   - Electron trusts the hostname `localhost:8765` while the backend binds `127.0.0.1:${AURALIS_PORT}`.
   - uvicorn's default `proxy_headers=True` lets local clients spoof `request.client`.

**Most exploitable**:
- SEC-03 (one crafted file → persistent UI DoS).
- SEC-04 (one crafted file → backend hang on every rescan).
- SEC-10 (any web page the user visits can make the backend run multi-second analyses in a loop via `<img src>`).

---

## Data Flow Security Matrix

| # | Flow | Status | Notes |
|---|------|--------|-------|
| 1 | **File paths** — router → `path_security.py` → repositories → `unified_loader` → FFmpeg | **Safe (containment)**, minor gaps | `validate_file_path` is called on every REST/WS consumer of DB- or request-supplied paths: stream_track_resolution, metadata, lyrics, recommendation, prewarm, processing. `resolve()` runs before `relative_to`, `..` is rejected on the raw parts, and symlinks are resolved. ffmpeg/ffprobe use argv lists with `-protocol_whitelist file`, `reject_protocol_path` and `--`. Cache keys are built from ints and hex hashes only. Thumbnail, chunk and artwork paths cannot escape their directories. Gaps: NUL byte gives a 500 instead of a 400 (SEC-12); fixed-name `/tmp/auralis_*` dirs have no owner check (SEC-05). |
| 2 | **Audio metadata** — file → tag parser → DB → API → React | **Partial** | No XSS: there is no `dangerouslySetInnerHTML`, and artwork is only an `<img src>` built same-origin. Log injection is blocked by the record factory. Gaps: ReDoS in the artist split (SEC-04); genre has no length or count cap (SEC-20); embedded cover art has no byte cap and fails open on bombs (SEC-03); folder `cover.jpg` symlinks are followed (SEC-13); `.25d` values are not range-checked (SEC-33). |
| 3 | **WebSocket messages** — `websocket_security.py` → `ws_handlers` → stream controller | **Safe (auth)**, DoS gaps | The origin check runs before `accept()`. Every frame is checked for size, depth, schema and type enum, and binary frames are rejected. `ws_id` and `job_id` are uuid4, and each handler touches only its own `ws_id`. Gaps: the 64 KiB cap applies only after uvicorn has buffered up to 16 MiB; invalid frames are never rate-limited; connection count is unbounded and paused streams hold global slots (SEC-27); a null `data` field gives an internal_error traceback (SEC-28). |
| 4 | **Library scan paths** — settings / library_scan → scanner → DB | **Safe (entry)**, one route gap | Every add-folder entry point goes through `validate_user_chosen_directory` or `validate_directory_list`, including the `LibraryScanRequest` validator. Symlink following is the #4823 decision. Gaps: `POST /api/settings/scan-folders/delete` accepts any path and prunes it (SEC-11). `scan_interval` has no lower bound, and the watcher rescans on every event under broad roots (SEC-19). Allowlist changes are not logged (SEC-44). |
| 5 | **Outbound HTTP** (artwork download, CLI artwork service, Electron updater) | **Safe (SSRF)** | Hosts are fixed, HTTPS only, every redirect hop is validated, and no request field carries a URL. Gaps: the aiohttp `content.read(n)` size cap does not work (SEC-49); JSON responses have no cap (SEC-50); the CLI service forwards its `Authorization` header across redirects (SEC-40). The update channel is unsigned (#4905) and runs on an old Electron (SEC-02). |

---

## Findings

### MEDIUM

### SEC-01: Release binaries are built with unpinned, unhashed build tooling (PyInstaller, maturin, setuptools, wheel, pip)
- **Severity**: MEDIUM
- **OWASP Category**: A08 (also A06)
- **Location**: `.github/workflows/build-release.yml:147,205,306,370,452,510`
- **Status**: NEW (adjacent to closed #4871 / #4868, which hash-locked runtime deps and SHA-pinned actions only)
- **Description**: Runtime deps are installed with `pip install --require-hashes -r requirements-lock.txt`, but the tools that build the shipped artifacts are not pinned:
  - All three build jobs (Linux, Windows, macOS) run `pip install --upgrade pip setuptools wheel maturin`, which builds the bundled PyO3 wheel, and then `pip install pyinstaller`, which freezes `auralis-backend` and embeds its bootloader.
  - Neither tool is in any lockfile or the pin guard.
  - Because `pip install pyinstaller` runs after the hashed install, its floating transitives can also replace hash-verified packages.
  - The workflow comment says the shipped set is "byte-identical to what backend-tests.yml tested". That is false for this layer.
- **Evidence**: `build-release.yml:147  pip install --upgrade pip setuptools wheel maturin` … `:205  pip install pyinstaller` … `:207  pyinstaller --clean --noconfirm auralis-backend.spec`.
- **Exploit Scenario**:
  1. A hijacked or malicious PyPI release of pyinstaller, pyinstaller-hooks-contrib, pefile, altgraph or maturin is published.
  2. The next tag build bakes it into all three installers.
  3. `SHA256SUMS.txt` (and its optional GPG signature) is generated from the already-compromised artifacts, so it cannot detect the change.
- **Impact**: Code execution as the user on every machine that installs or auto-updates to that release.
- **Suggested Fix**: Hash-lock the build tools in a `requirements-build.txt` (`uv pip compile --generate-hashes`), install them with `--require-hashes` before the runtime lock, add them to `requirements-pin-guard.yml`, and drop the second unconstrained `pip install`.
- **Source**: SEC-A06-2 + SEC-A08-1 (merged).

### SEC-02: Electron pinned at 43.7.6, below the fix for GHSA-jr5w-w6x2-84p9 (high)
- **Severity**: MEDIUM
- **OWASP Category**: A06
- **Location**: `desktop/package.json:32` (`"electron": "^43.7.6"`), `desktop/pnpm-lock.yaml` (`electron@43.7.6`)
- **Status**: NEW (amplifies open #4905)
- **Description**:
  - GHSA-jr5w-w6x2-84p9 ("Mitigation for compromised eMudhra intermediate certificates", severity high) affects `>=43.0.0-alpha.1 <43.8.1`. The orchestrator re-confirmed this range via `gh api`.
  - The lock resolves 43.7.6, nine patch releases behind 43.8.3. Several of those releases are Chromium/V8/ANGLE/Skia security backports, and 43.8.1 also fixes the window-opener session/webPreferences inheritance.
  - `.github/dependabot.yml` covers github-actions only, so nothing flags this.
- **Evidence**: The `gh api repos/electron/electron/security-advisories/GHSA-jr5w-w6x2-84p9` range is listed above; the lock has `electron@43.7.6`.
- **Exploit Scenario**:
  1. The packaged app's only network path is electron-updater to GitHub releases.
  2. An on-path attacker holding a certificate chained to the compromised intermediates impersonates the update host and serves a malicious `latest.yml` and installer.
  3. Update code-signing is off (#4905), so TLS is the only authentication.
  4. User consent is still required (`autoDownload=false`).
- **Impact**: An update-channel MITM leads to code execution. The renderer also carries unpatched Chromium n-days.
- **Suggested Fix**: Bump the lock to >=43.8.3 (or 44.x/45.x), and add a security-updates-only npm entry for `/desktop` (electron, electron-updater) to dependabot.
- **Cross-audit overlap**: AUDIT_DEPRECATION / AUDIT_FRONTEND 2026-10-22 mention the Electron version in passing; neither records the advisory.

### SEC-03: `bound_artwork_dimensions` fails open on a decompression bomb, so the image it exists to stop is stored and served unchanged
- **Severity**: MEDIUM
- **OWASP Category**: A04
- **Location**: `auralis/utils/artwork_security.py:77-118`, `auralis/library/artwork.py:187-205`, `auralis/library/artwork_tags.py:28-90`, `auralis-web/backend/routers/artwork_thumbnails.py:80-125`, `auralis-web/backend/routers/artwork.py:183-200`
- **Status**: NEW (bypass of the closed #4439 / #5522 fixes, which are present but do not cover this case)
- **Description**:
  - Embedded covers (APIC, FLAC picture, MP4 `covr`) are extracted at scan time with no byte cap. The 5 MiB cap only applies to downloads.
  - `bound_artwork_dimensions` wraps `Image.open` in `except Exception: return data` ("artwork is never dropped"). Pillow raises `DecompressionBombError` above about 179 Mpx, which is exactly the oversized case the function exists for, and the original bytes are returned and stored.
  - The thumbnail route hits the same error, swallows it, and falls back to serving the original file to the renderer.
  - Images between about 89 and 179 Mpx only warn, so they are fully decoded (hundreds of MB) in both the scan path and the thumbnail path.
- **Evidence**: A 1.2 MB, 1-bit 100000×100000 PNG reproduced it: `returned unchanged: True`, while a plain `Image.open` raises `DecompressionBombError`. The `except Exception: return data` is at line 117-118.
- **Exploit Scenario**:
  1. A crafted MP3/FLAC/M4A with that PNG as its cover sits in a scanned folder (download, torrent, USB).
  2. Every grid or list view requests the album artwork and gets the bomb back at full size.
  3. The Electron renderer OOMs or hangs, and does so again each time the album is shown.
- **Impact**: Persistent denial of service of the desktop UI from one file, plus backend memory spikes.
- **Suggested Fix**: Treat `DecompressionBombError`/`Warning` as "reject" and drop the artwork instead of returning the original. Cap the embedded picture bytes before decoding. Never fall back to the original in the thumbnail path after a bomb error.

### SEC-04: Quadratic-time regex (ReDoS) on the artist tag freezes the whole backend during a scan
- **Severity**: MEDIUM (HIGH impact, downgraded because the malicious file must be in a folder the user scans)
- **OWASP Category**: A03 (ReDoS) / A04
- **Location**: `auralis/library/utils/artist_normalizer.py:16-23,109-124,137`; caller `auralis/library/scanner/metadata_extractor.py:215-225`
- **Status**: NEW
- **Description**:
  - `parse_featured_artists()` runs patterns that begin with `\s+` (`\s+x\s+`, `\s+with\s+`, `\s+feat\.?\s+`, `\s+&\s+|\s+and\s+`) over the raw artist tag. On a long whitespace run these degrade to O(n²).
  - The 200-character truncation in `track_repository_lifecycle` happens after the split.
  - Python `re` holds the GIL, so the event loop, streaming and REST all stall.
- **Evidence**: `parse_featured_artists('a' + ' '*n + 'b')` took 0.4 s at n=5k, 6.4 s at n=20k and 25.9 s at n=40k. ID3 TPE1 and Vorbis ARTIST frames can be megabytes.
- **Exploit Scenario**:
  1. A file's artist tag is `a` followed by hundreds of thousands of spaces and then `b`.
  2. The user or the auto-scanner scans the folder, and the backend hangs for minutes to hours.
  3. Every rescan re-triggers it.
- **Impact**: Persistent backend unavailability until the file is removed.
- **Suggested Fix**: Truncate the tag (for example to 500 characters) before parsing, and/or collapse whitespace first (`re.sub(r'\s+', ' ', s)`) so the patterns become linear.
- **Cross-audit overlap**: AUDIT_ENGINE_2026-10-22 E4-03 touches the same call (NUL-joined multi-value tags reach `parse_featured_artists`), but it is a different defect.

### SEC-05: Fixed-name `/tmp/auralis_*` dirs adopt a pre-existing directory owned by another local account
- **Severity**: MEDIUM
- **OWASP Category**: A01
- **Location**: `auralis-web/backend/config/limits.py:69-108` (`create_secure_temp_dir`); callers `core/chunked_processor.py:107`, `core/processing_engine.py:107-108`, `routers/processing_upload.py:48`, `config/startup/tempfiles.py:236`
- **Status**: NEW (incomplete fix of closed #4855, which added the symlink refusal and chmod)
- **Description**:
  - `create_secure_temp_dir` refuses a symlink, then calls `mkdir(mode=0o700, exist_ok=True)` and `os.chmod(path, 0o700)` inside `except OSError: pass`.
  - `mkdir(exist_ok=True)` accepts any existing directory, and the `chmod` on a directory owned by someone else raises `PermissionError`, which is silently swallowed.
  - There is no `st_uid` check anywhere in `auralis/` or `auralis-web/backend/`.
- **Evidence**: The function body was re-read by the orchestrator. The names are fixed (`auralis_uploads`, `auralis_chunks`, `auralis_processing`) under `tempfile.gettempdir()`.
- **Exploit Scenario**:
  1. On a shared host, a second account runs `mkdir -m 777 /tmp/auralis_chunks` (and the `_processing` / `_uploads` dirs) after `/tmp` is cleared.
  2. The victim's backend uses the directories. The attacker can read the enhanced chunk WAVs, processed masters and uploads.
  3. As owner, the attacker can also plant or swap cached chunk files, which are served on a cache hit.
- **Impact**: Disclosure of audio content and listening activity, and integrity of the cached stream. Only affects multi-account hosts.
- **Suggested Fix**: After `mkdir`, `lstat` the path and require `S_ISDIR` and `st_uid == os.getuid()`, and raise instead of swallowing the chmod failure. Alternatively, move these dirs under `~/.auralis/` (already 0700) or use a per-process `mkdtemp`.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 mentions `auralis_chunks` only as the size of the unreported cache, not ownership.

### SEC-06: Engine-level `warning()`/`error()` from `auralis.utils.logging` are discarded because `set_log_handler()` is never called
- **Severity**: MEDIUM
- **OWASP Category**: A09
- **Location**: `auralis/utils/logging.py:96-125`, `auralis/__init__.py:37` (the only export of `set_log_handler`); consumers in about 59 non-test modules, including `auralis/library/scanner/*`, `auralis/library/database.py:89,199,206,215,260`, `auralis/library/metadata_editor/backup.py:98,116,123`, `auralis/io/loaders/*`, `auralis/player/*`, `auralis/services/fingerprint_*`
- **Status**: NEW (an earlier audit noted it in a coverage statement; no issue was ever filed)
- **Description**:
  - `debug/info/warning/error` in the facade do nothing unless the module-global `_log_handler` is set, and no production code calls `set_log_handler` (verified by grep: definition plus re-export only).
  - The facade is not bridged to stdlib `logging`, so every event it carries is lost in the running app, including the failure paths of the scanner, database, loader and metadata backup.
- **Evidence**:
  ```python
  _log_handler: Callable[[str], None] | None = None
  def warning(message: str) -> None:
      if _log_handler:
          _log_handler(f"WARNING: {sanitize_log_value(message)}")
  ```
  Events that vanish include:
  - `scanner.py:241 warning(f"Library scan failed: {e}")`, after which the scan returns a normal-looking result.
  - `file_discovery.py` permission-denied, symlink-loop and max-depth warnings.
  - `database.py:89 error("Database migration failed!")`.
  - WAL checkpoint failures.
  - Metadata backup and restore failures.
- **Exploit Scenario**: A hostile or corrupt library (symlink loop, unreadable dir, failed tag write with failed restore) causes a scan abort or data-integrity event. The persisted electron-log, the only durable log (#4920), has no trace of it.
- **Impact**: The audit trail for the whole engine and library layer is lost. The "failed operations are logged" assumption behind #4920/#4925 only holds for backend stdlib loggers.
- **Suggested Fix**: Have the facade delegate to `logging.getLogger("auralis")` when no handler is installed, or install a bridging handler in `config/bootstrap.py`, keeping `sanitize_log_value`.

### SEC-07: `POST /api/similarity/graph/build` has no single-flight guard; overlapping builds pin the shared I/O executor and duplicate edges
- **Severity**: MEDIUM
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/similarity_graph.py:62-91`, `auralis/analysis/fingerprint/knn_graph.py:81-196`, `auralis/library/models/fingerprint.py:237-247`, `auralis-web/backend/core/executors.py:94,202`
- **Status**: NEW (distinct from #5747, which is about paging within one build, and #4845, the frontend timeout)
- **Description**:
  - A multi-minute `build_graph` runs via `asyncio.to_thread` on the 8-worker `IO_EXECUTOR`, which also serves every repository call.
  - There is no lock or in-progress flag in the route or in `KNNGraphBuilder`.
  - `SimilarityGraph` has no unique constraint, so overlapping builds insert duplicate edges, and one build's `clear_all()` deletes the other's output.
  - The 20 POST/min limit bounds how fast builds start, not how many run concurrently.
- **Evidence**: `stats = await asyncio.to_thread(graph_builder.build_graph, k=k, clear_existing=clear_existing)`; `__table_args__` contains only `Index(...)`.
- **Exploit Scenario**:
  1. Eight build requests are sent, from a local client or from the user re-clicking after the 30 s frontend timeout.
  2. All `IO_EXECUTOR` workers are pinned for minutes, and library, queue and settings calls queue behind them.
  3. The graph returns duplicated neighbours afterwards.
- **Impact**: The whole backend becomes unavailable, and the precomputed graph loses integrity.
- **Suggested Fix**: Add a process-wide in-progress guard that returns 409 on re-entry, run the build on a dedicated single-worker executor, and add a unique index on `(track_id, similar_track_id)` or build into a staging table and swap.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D1-09 (same defect, functional framing). Publish once.

### SEC-08: Every WS `play_*` spawns an un-coalesced, un-cancellable recommendation analysis on the shared I/O executor
- **Severity**: MEDIUM
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:319-322,374-377`, `auralis-web/backend/services/recommendation_service.py:62-101`, `auralis-web/backend/core/executors.py:94,202`
- **Status**: NEW (residual of closed #5248, which added the timeout; the full-file decode cost is open #5713)
- **Description**:
  - `handle_play_enhanced` and `handle_play_normal` each spawn `_generate_mastering_recommendation`, which runs a full decode plus fingerprint in `asyncio.to_thread` on `IO_EXECUTOR`.
  - The task is not cancelled when the stream is superseded, and there is no per-track in-flight dedup.
  - `asyncio.wait_for(..., 30)` abandons the awaiting coroutine but not the OS thread.
- **Evidence**: `spawn_background_task(_generate_mastering_recommendation(track_id, deps), …)`; `await asyncio.wait_for(asyncio.to_thread(_analyze), timeout=…)`.
- **Exploit Scenario**: The user holds "next" through 50 un-fingerprinted tracks, or a local client sends `play_normal` at the allowed 10 msg/s. Analyses pile up on the repository pool, and REST calls wait tens of seconds to minutes.
- **Impact**: Self-inflicted or local-actor denial of service of backend responsiveness.
- **Suggested Fix**: Make the analysis single-flight per track_id, cancel it when the owning stream is superseded, and run it on a small dedicated bounded executor.
- **Cross-audit overlap**: AUDIT_CONCURRENCY_2026-10-22 CONC-D3-03 and AUDIT_INTEGRATION_2026-10-22 INT-F5-9 (which also notes the broadcast has no frontend consumer). Publish once.

### SEC-09: Electron `cleanupPort()` SIGKILLs every process with any socket on port 8765, and there is no single-instance lock
- **Severity**: MEDIUM
- **OWASP Category**: A04 / A07
- **Location**: `desktop/main.js:57-130` (find at :65, kill at :99), call site `:142`; `requestSingleInstanceLock` is absent
- **Status**: NEW
- **Description**:
  - Before spawning the backend, `cleanupPort()` runs `lsof -ti:8765` (on Windows, `netstat -ano | findstr :8765`) and then `kill -9` or `taskkill /F` on every PID returned.
  - `lsof -i :PORT` matches either end of a connection, so it also returns clients: a browser tab on `localhost:8765`, the Vite dev proxy, curl, or a client of some remote :8765 service.
  - On Windows, `findstr :8765` is a substring match that also hits `:87650` and the foreign-address column.
  - Nothing checks that a PID is the Auralis backend.
  - Without `app.requestSingleInstanceLock()`, a second launch SIGKILLs the first instance's live backend.
- **Evidence**: `const findCommand = isWindows ? \`netstat -ano | findstr :${this.backendPort}\` : \`lsof -ti:${this.backendPort}\``; `kill -9 ${pid}`. A local test confirmed that `lsof -ti:<port>` returns both the listener and a connected client.
- **Exploit Scenario**: The user has the UI open in Chrome or runs `pnpm run dev`, then launches the desktop app. Chrome's network process or the dev server is SIGKILLed. A double launch kills playback in the first window.
- **Impact**: Data loss in unrelated same-user processes and an unexpected kill of a running instance. No privilege boundary is crossed.
- **Suggested Fix**: Add `requestSingleInstanceLock()`. Restrict discovery to `lsof -ti tcp:PORT -sTCP:LISTEN`, or to a PID file recorded at spawn, and verify the command line before killing. Anchor the Windows match to the local-address column, and send SIGTERM before SIGKILL.
- **Source**: SEC-A05-1 + SEC-A07-1 + SEC-A08-6 (merged).

---

### LOW

#### A01 — Broken Access Control

### SEC-10: Cross-origin-reachable GET routes with side effects or expensive work sit outside OriginCheck and RateLimit
- **Severity**: LOW
- **OWASP Category**: A01 (A04 overlap)
- **Location**: `auralis-web/backend/config/middleware/origin_check.py:60,72`; `config/middleware/rate_limit.py:50-55`; `routers/enhancement_recommendation.py:25-35,85-120`; `cache/recommendations_mixin.py:59,87`; `routers/fingerprint_status.py:93-134`; `routers/tracks.py:166-235`
- **Status**: NEW (#4893 closed the hole for state-changing methods; #3865 / #4657 covered other aspects)
- **Description**: OriginCheck gates only POST/PUT/DELETE/PATCH, but some GET routes are not safe:
  - `GET /api/player/mastering/recommendation/{id}?confidence_threshold=x` builds a fresh `ChunkedAudioProcessor` and runs a full analysis. The cache key includes the float threshold, and `/api/player` is not rate-limited.
  - `GET /api/tracks/{id}/fingerprint` enqueues fingerprinting.
  - The lyrics and thumbnail GETs write to the DB and to disk.

  A hostile page can fire these blind with `<img src>` or `no-cors` fetch.
- **Evidence**: `cache_key = (track_id, confidence_threshold)`; `_STATE_CHANGING_METHODS = frozenset({"POST","PUT","DELETE","PATCH"})`.
- **Exploit Scenario**: A page loops `new Image().src = 'http://127.0.0.1:8765/api/player/mastering/recommendation/'+id+'?confidence_threshold='+Math.random()`.
- **Impact**: Local CPU and I/O exhaustion with no disclosure. Recent Chromium prompts for local-network access; Firefox and Safari do not.
- **Suggested Fix**: Reject `/api` requests carrying an untrusted `Origin` or `Sec-Fetch-Site: cross-site` regardless of method. Add `/api/player/mastering` and `/api/tracks` to `_RATE_LIMITS`, and quantise the threshold in the cache key.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D6-03 covers the recommendation route (rate limit and free-float key); the cross-origin aspect and the other GETs are new here.

### SEC-11: `POST /api/settings/scan-folders/delete` takes an unvalidated path and prunes the library for any folder
- **Severity**: LOW
- **OWASP Category**: A01
- **Location**: `auralis-web/backend/routers/settings.py:180-194`, `routers/settings_models.py:25-26`, `services/missing_tracks.py:64-100`, `auralis/library/repositories/track_repository_maintenance.py:198-250`
- **Status**: NEW (behaviour added by closed #5467 / #5523)
- **Description**: `_ScanFolderRequest.folder` is a bare `str`, and the route prunes every track under it even if the folder was never configured. `{"folder":"/"}` wipes the library index without the `X-Confirm-Reset: RESET` header that `POST /api/library/reset` requires.
- **Evidence**: `await _revoke_folder(deps, body.folder)` → `remove_tracks_under_folder(folder)` → `Path(folder).resolve()` / `is_relative_to`.
- **Exploit Scenario**: A local process, or the app UI, sends `{"folder":"/"}`. All tracks, fingerprints and playlist memberships are deleted. Files on disk are untouched.
- **Impact**: Library metadata loss that bypasses the reset confirmation guard. Recoverable by rescanning, but playlists, favourites and play counts are lost.
- **Suggested Fix**: Require `body.folder` to be a member of the stored `scan_folders` (404 otherwise), and reject NUL bytes and relative paths.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D1-04 (same defect). Publish once.

### SEC-12: Path validators let a NUL byte escape as a bare `ValueError` instead of `PathValidationError`
- **Severity**: LOW
- **OWASP Category**: A01 / A03
- **Location**: `auralis-web/backend/security/path_security.py:244-249` (`validate_file_path`) and `:338-343` (`validate_user_chosen_directory`)
- **Status**: NEW
- **Description**:
  - Both validators catch only `(OSError, RuntimeError)` around `Path.resolve()`, and on Python 3.14 an embedded `\x00` raises `ValueError`.
  - It fails closed (no bypass), but the 44 `except PathValidationError` callers do not catch it. The result is a 500 with an ERROR traceback.
  - The `_logs_rejections` wrapper does not record it (#4925 audit trail).
- **Evidence**: `validate_file_path('/home/u/Music/a\0b')` raises `ValueError: lstat: embedded null character in path`, confirmed by a snippet.
- **Exploit Scenario**: `POST /api/processing/process {"input_path":"/x\u0000.mp3"}` or `POST /api/settings/scan-folders {"folder":"..\u0000"}` returns a 500 instead of a logged 400.
- **Impact**: Wrong status code and a missing audit line.
- **Suggested Fix**: Add `ValueError` to both `except` clauses (or reject `"\0"` up front) and raise `PathValidationError`.
- **Source**: SEC-A01-4 + SEC-A03-3 (merged).

#### A03 — Injection

### SEC-13: Folder-artwork lookup follows symlinks and special files with an unbounded read, and copies arbitrary content into the served artwork directory
- **Severity**: LOW
- **OWASP Category**: A03 (also A04)
- **Location**: `auralis/library/artwork.py:146-159` (`_find_folder_artwork`), `:214-226` (`_save_artwork`); served by `auralis-web/backend/routers/artwork.py:126-217`
- **Status**: NEW (#4823 accepted symlink following for audio discovery only)
- **Description**:
  - `cover.jpg` and about 25 sibling names are checked with `exists()` only, then `read()` runs with no `S_ISREG`, no symlink check and no size cap.
  - Non-image content survives the fail-open dimension bound (SEC-03) and is saved as `album_<id>_<md5>.jpg`.
  - The result passes the artwork route's containment check and is served as `image/jpeg`.
- **Evidence**: Reproduced: a `cover.jpg` symlinked to a text file was copied verbatim into the artwork dir. A FIFO blocks the scan forever, and a symlink to `/dev/zero` grows memory without bound.
- **Exploit Scenario**: An archive carries `cover.jpg -> /dev/zero` (scan OOM) or `cover.jpg -> ~/.ssh/id_ed25519`. In the second case the target is duplicated under `~/.auralis/artwork` and served to any same-origin client.
- **Impact**: Local DoS of the scan, and a confined copy of readable files. There is no cross-origin read channel.
- **Suggested Fix**: `lstat` the candidate and require `S_ISREG` (or a resolved target inside `album_dir`), cap `st_size` (for example 20 MB), and require Pillow to recognise the bytes as an image.

### SEC-14: `SanitizingFormatter._format_chain` escapes the newlines inside traceback frames, collapsing every traceback into one line
- **Severity**: LOW
- **OWASP Category**: A03 / A09
- **Location**: `auralis/utils/logging.py:~211-216`
- **Status**: NEW (side effect of the closed #5393; log forging is still prevented)
- **Description**: The structural `traceback.format_tb` frames are run through `sanitize_log_value`, which escapes `\n` as a literal `\x0a` and truncates at 500 characters. Every persisted traceback becomes one unreadable line.
- **Evidence**: The test output was `Traceback …\n  File "<string>", line 10, in <module>\x0a    try: a()\x0a …`.
- **Exploit Scenario**: None. This affects defenders triaging the persisted log.
- **Impact**: Degraded forensic value of production logs.
- **Suggested Fix**: Sanitize only the attacker-controllable `{Type}: {exc}` summary line, or sanitize per line and keep the real line breaks.

#### A04 — Insecure Design

### SEC-15: `POST /api/player/queue` accepts any `start_index`; the state manager stores it raw while the engine clamps it
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/player_models.py:23`, `services/queue_set_mixin.py:52-130`, `core/state_manager.py:145-162`, `auralis/player/queue_loading.py:129-134`
- **Status**: NEW
- **Description**:
  - `start_index` has `ge=0` but no upper bound.
  - The state manager broadcasts `queue_index=start_index` verbatim while the engine uses `min(start_index, count-1)`.
  - The index is applied to the id-filtered list, so a dropped id shifts which track starts.
- **Evidence**: `{"tracks":[1,2,3],"start_index":9999}` returns 200; the broadcast is `queue_index: 9999, current_track: null` while the engine index is 2.
- **Exploit Scenario**: A buggy or local client sends an out-of-range index. The two stores diverge, and next, previous and remove act on different indices.
- **Impact**: Breaks the "queue index valid" invariant. Integrity only.
- **Suggested Fix**: Validate against the resolved queue length, return 422, and clamp identically in both stores.
- **Cross-audit overlap**: AUDIT_INTEGRATION_2026-10-22 INT-F9-3 (same defect). Publish once.

### SEC-16: `SetVolumeRequest` maps NaN / Infinity / 1e999 to volume 100
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/player_models.py:99-102`
- **Status**: NEW (same class as closed #4600, which fixed intensity)
- **Description**: `max(0.0, min(100.0, v))`, and `min(100.0, nan)` is `100.0`. Pydantic floats accept JSON `NaN` and `Infinity`.
- **Evidence**: Reproduced: `NaN → 100.0`, `Infinity → 100.0`, `1e999 → 100.0`.
- **Exploit Scenario**: A loopback client, or a buggy slider producing NaN, triggers a broadcast of `volume_changed: 100`.
- **Impact**: Unexpected full-volume jump (hearing safety).
- **Suggested Fix**: Reject non-finite values with `math.isfinite` before clamping, as `SeekRequest` already does.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D1-05 (same defect). Publish once.

### SEC-17: Integer parameters have a lower bound but no upper bound, so values above 2^63 reach SQLite as 500s with logged tracebacks
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/schemas/request_bounds.py:33-45`; `routers/tracks.py:62`, `albums.py:101`, `artists.py:81`, `playlists_crud.py:24` (`offset` has no `le`); `Path(ge=1)` ids throughout
- **Status**: Regression of #3893 (closed; only `ge=1` was added)
- **Description**: Values above 2^63-1 raise `OverflowError` in the SQLite binding. `handle_query_error` turns that into a 500 and logs it with `exc_info`. The WS `play_normal` with a huge `track_id` does the same.
- **Evidence**: Reproduced: `tracks.get_all(offset=10**30)` and `get_by_id(10**30)` raise `OverflowError`.
- **Exploit Scenario**: Repeated `GET /api/library/tracks?offset=1e30` requests flood the log with tracebacks.
- **Impact**: Error noise and log flooding. No exposure.
- **Suggested Fix**: Give ids, offsets and queue indices a shared `le=2**63-1` (or a realistic maximum).

### SEC-18: The declared id-list cap (50,000) exceeds SQLite's bound-variable limit (32,766)
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/schemas/request_bounds.py:33,42`, `auralis/library/repositories/playlist_crud_mixin.py:68-71`
- **Status**: NEW
- **Description**: `create()` resolves ids with a single `Track.id.in_(...)`. Above 32,766 ids SQLite raises `too many SQL variables`, the repository returns `None`, and the route answers 400 "Failed to create playlist".
- **Evidence**: Reproduced at 32,767 and 40,000 ids.
- **Exploit Scenario**: Saving a 40k-track library as a playlist fails with no explanation.
- **Impact**: Functional failure at a documented-valid input size.
- **Suggested Fix**: Batch with `_iter_in_batches`, or lower `MAX_TRACK_ID_LIST` to the real limit.

### SEC-19: Auto-scan cadence has no lower bound, and the watcher rescans recursively on every event under broad scan roots
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/settings_models.py:45,82`, `services/library_auto_scanner.py:142-153`, `services/scanner_watchdog.py:25-60,96-105`, `security/path_security.py:50-74`
- **Status**: NEW
- **Description**:
  - `scan_interval` has `ge=0` (an interval of 1 means a full rescan every second), and `max_concurrent_scans` has no upper bound.
  - The watchdog reacts to any file event (0.5 s debounce, `recursive=True`).
  - `$HOME`, `/home`, `/mnt` and `/tmp` are accepted as scan roots, and with `/tmp` the app's own chunk WAVs trigger rescans.
- **Evidence**: `validate_user_chosen_directory('/tmp')` returns the path unchanged; `self._observer.schedule(handler, folder, recursive=True)`.
- **Exploit Scenario**: A typo ("5", meant as minutes) or a loopback PUT makes the library rescan itself every 5 s. A home-folder root never goes idle.
- **Impact**: Sustained CPU and disk load, inotify watch exhaustion, and possible self-ingestion of temp WAVs.
- **Suggested Fix**: Enforce `scan_interval >= 60` and an upper bound on concurrent scans, filter watchdog events to audio extensions, and refuse roots that contain `tempfile.gettempdir()` or `~/.auralis`.

### SEC-20: The genre tag is stored with no length or count cap
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis/library/scanner/metadata_extractor.py:229-235`, `auralis/library/repositories/track_repository_lifecycle.py:44-56,98-112`
- **Status**: NEW (adjacent to open #5732 and #5266)
- **Description**: Title, album and artists are truncated, but `genres` goes straight to `Genre(name=…)` with unbounded length and count, and it is serialised in every track payload.
- **Evidence**: `track_info['genres'] = [str(g) for g in genres]`; the normaliser's field list omits genres.
- **Exploit Scenario**: A crafted MP3 with a 50 MB TCON frame is scanned. Every library page that includes the track returns 50 MB.
- **Impact**: Memory, bandwidth and UI denial of service, and DB bloat.
- **Suggested Fix**: Truncate each genre (for example to 100 characters) and cap the list length in `_validate_and_normalize_track_info`.

### SEC-21: Decode budgets are per file, with no aggregate memory or disk budget
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis/io/loader.py:25-100`, `auralis-web/backend/core/seekable_source.py:79-100,141-160`, `core/stream_normal.py:122-136`, `core/executors.py:94`
- **Status**: NEW (the per-file guards from #3671/#4220/#4875 are sound)
- **Description**:
  - Each `normal` stream of a compressed file may decode up to 6 GiB of float32 into RAM and write it to `/tmp` as a float WAV, which is often tmpfs.
  - Up to 8 conversions can run at once, and there is no `disk_usage` check.
- **Evidence**: `sf.write(wav_path, audio, sample_rate, format="WAV", subtype="FLOAT")`; there is no `disk_usage`/`statvfs` call in `core/`.
- **Exploit Scenario**: Several long hi-res files are started in quick succession, and RAM or `/tmp` is exhausted.
- **Impact**: Backend or host OOM.
- **Suggested Fix**: Add a global byte budget or semaphore around full-file decodes, check free space first, and prefer windowed conversion.

### SEC-22: `POST /api/files/upload` has no aggregate quota, and each file is fully decoded just to read its duration
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/files_upload.py:34-146`, `config/limits.py:20-24`
- **Status**: NEW (related to open #5270)
- **Description**:
  - A request may carry up to 200 files of up to 500 MB each, and each is read fully into memory.
  - `load_audio` decodes each whole file only to compute its duration.
  - Files are kept permanently in `~/.auralis/uploads`, with no dedup and no quota.
  - The route has no frontend consumer.
- **Evidence**: `content = await file.read(_MAX_UPLOAD_BYTES + 1)`; `audio_data, sample_rate = await asyncio.to_thread(load_audio, temp_path)`.
- **Exploit Scenario**: A local client posts 5 requests/min and fills `$HOME`.
- **Impact**: Disk and memory exhaustion.
- **Suggested Fix**: Probe the duration with `sf.info`/ffprobe, add a per-request byte budget, dedup by hash and enforce a quota, or unregister the unused route.

#### A05 — Security Misconfiguration

### SEC-23: Unhandled-exception 500 responses bypass SecurityHeadersMiddleware and CORSMiddleware
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `auralis-web/backend/config/app.py:112-118`, `config/middleware/__init__.py:54-106`
- **Status**: NEW
- **Description**: Starlette serves the `Exception` handler from `ServerErrorMiddleware`, which sits outside all user middleware. As a result, 500s carry no `nosniff`, `X-Frame-Options`, Referrer-Policy, CSP or ACAO header.
- **Evidence**: A TestClient run returned a 200 with all five headers and a raising route's 500 with none of them.
- **Exploit Scenario**: Low value on its own. The JSON body is generic, but a dev-origin page sees a CORS failure instead of the 500.
- **Impact**: The header guarantee is inconsistent.
- **Suggested Fix**: Apply the same headers in the catch-all handler through a shared helper, or add an outermost pure-ASGI layer that converts exceptions inside the CORS and header layers.

### SEC-24: uvicorn runs with the default `proxy_headers=True`, so `request.client.host` is spoofable via `X-Forwarded-For`
- **Severity**: LOW
- **OWASP Category**: A05 / A07
- **Location**: `auralis-web/backend/main.py:124-130`
- **Status**: NEW
- **Description**:
  - Every peer is a loopback peer, so every peer counts as a trusted proxy (`forwarded_allow_ips` defaults to 127.0.0.1).
  - `X-Forwarded-For` therefore rewrites `scope["client"]`, which feeds the RateLimit keys, the WS per-IP bucket and the empty-Origin loopback checks.
  - No reverse proxy exists in this architecture.
- **Evidence**: `uvicorn.run(app, host="127.0.0.1", port=_port, log_level=_log_level)` with no `proxy_headers=False`.
- **Exploit Scenario**: A local non-browser process rotates `X-Forwarded-For` to get a fresh rate-limit bucket on every request. Browsers cannot do this, because the header is not in the CORS `allow_headers`.
- **Impact**: Rate-limit bypass and unreliable peer identity in the origin checks.
- **Suggested Fix**: Pass `proxy_headers=False` (and `server_header=False`).

### SEC-25: Clients address the backend as `localhost`, which may resolve to `::1`, while it binds only `127.0.0.1`
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/main.js:361-366`, `desktop/preload.js:19`, `desktop/url-safety.js` (`APP_ORIGIN`), `auralis-web/backend/main.py:126`
- **Status**: NEW
- **Description**: Electron loads `http://localhost:8765`, and the preload exposes `electronAPI` to any document with that origin. Nothing guarantees the listener on `[::1]:8765` is Auralis.
- **Evidence**: Bind literal `127.0.0.1` versus origin literal `http://localhost:8765`.
- **Exploit Scenario**: On a multi-user host, another account binds `[::1]:8765` first. Electron renders its page, which receives `electronAPI` and is trusted by the CORS and OriginCheck string match.
- **Impact**: Trust is bound to a hostname instead of the actual listener. Outside the single-user threat model.
- **Suggested Fix**: Load and trust `http://127.0.0.1:<port>` in Electron, or also bind `::1`.

### SEC-26: `AURALIS_PORT` is honoured by the backend only; Electron, the Vite proxy and the frontend hard-code 8765
- **Severity**: LOW
- **OWASP Category**: A07
- **Location**: `desktop/main.js:51,265,301,371,419`, `desktop/url-safety.js:28`, `desktop/preload.js:20`, `auralis-web/frontend/src/config/api.ts:18,21`, `auralis-web/frontend/src/contexts/WebSocketContext.tsx:142-148`, `auralis-web/frontend/vite.config.mts:107,111`, `auralis-web/backend/config/origins.py:34`
- **Status**: NEW (closed #5796 / f637c53e fixed only the backend half)
- **Description**:
  - Electron spawns the backend with the inherited environment, so an exported `AURALIS_PORT` moves the backend.
  - Electron still health-checks, loads and trusts `http://localhost:8765`. The health failure is only a warning, so startup "succeeds".
  - Whatever listens on 8765 is rendered in the privileged window and gets `electronAPI`.
  - With `--port N`, `API_BASE_URL` and the `port >= 3000` "dev" branch also send REST and WS traffic to 8765.
- **Evidence**: `startUrl = 'http://localhost:8765'`; `const APP_ORIGIN = 'http://localhost:8765'`; `BACKEND_PORT = get_int_env("AURALIS_PORT", 8765)`.
- **Exploit Scenario**: With `AURALIS_PORT=9000` set in the shell, a local process binds 8765. Electron loads it, and it can drive the native file and folder pickers.
- **Impact**: The wrong peer is trusted in a non-default configuration, and the configuration is also functionally broken.
- **Suggested Fix**: Make Electron the single owner of the port, pass it to the backend and the preload, and derive every URL and origin from it. In the frontend, use same-origin `API_BASE_URL` in production and `import.meta.env.DEV` for the WS dev branch.
- **Cross-audit overlap**: AUDIT_INTEGRATION_2026-10-22 INT-F5-8 and INT-F7-7 cover the frontend functional half. The Electron trust half is new here.

### SEC-27: WebSocket resource limits apply only per message: 16 MiB frames are buffered before the 64 KiB check, invalid frames are never rate-limited, connections are unbounded, paused streams hold global slots, and the per-IP limiter never evicts
- **Severity**: LOW
- **OWASP Category**: A07 / A04
- **Location**: `auralis-web/backend/routers/system.py:113-153`, `websocket/websocket_security.py:97-161,218-226`, `config/globals.py:100-148`, `core/stream_gates.py:34-46`, `core/stream_normal.py:62-74`, `main.py:124-130`
- **Status**: NEW (open #5079 covers only the ping amplifier)
- **Description**:
  1. `uvicorn.run` has no `ws_max_size`, so frames up to 16 MiB are fully buffered before `WS_MAX_MESSAGE_SIZE` (64 KiB) is checked.
  2. `validate_and_parse_message` runs before `check_rate_limit`, so malformed, oversized and unknown frames are never throttled, and each logs a WARNING and sends an error frame.
  3. `ConnectionManager.active_connections` is unbounded.
  4. `MAX_CONCURRENT_STREAMS` (10) is held for a stream's lifetime, and `wait_for_stream_gates` waits on pause/flow with no timeout, so 10 paused connections block all playback.
  5. `ip_message_log` keys are never deleted. With SEC-24, each spoofed IP adds a permanent key.
- **Evidence**: `system.py:136` validate precedes `:143` `check_rate_limit`; `stream_gates.py:43-46 await pause_evt.wait(); await flow_evt.wait()`; `websocket_security.py:132-133` has no deletion path.
- **Exploit Scenario**: A local process opens 10 sockets and sends `play_normal` then `pause` on each, and the user's player can no longer start a stream. Alternatively it streams 16 MiB frames.
- **Impact**: Local denial of playback and slow memory growth.
- **Suggested Fix**: Pass `ws_max_size` to uvicorn, count every frame against the limiter before parsing, cap connections, release the stream semaphore while paused (or time out), and evict empty `ip_message_log` keys behind an LRU cap.
- **Source**: SEC-A07-3 + SEC-A07-4 + SEC-A04-9 (merged).
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D2-05 (64 KB cap after receipt) and AUDIT_INTEGRATION_2026-10-22 INT-F5-11 (invalid frames unmetered). The connection cap, paused-slot and eviction parts are new here.

### SEC-28: A WebSocket command with `data` omitted or `null` raises `AttributeError` in every playback handler
- **Severity**: LOW
- **OWASP Category**: A04 (input validation at the message boundary)
- **Location**: `auralis-web/backend/ws_handlers/playback_commands.py:185,327,376`, `auralis-web/backend/schemas/websocket.py:84`
- **Status**: NEW (closed #2393 / #4771 are adjacent)
- **Description**: `model_dump()` yields `"data": None`, so `message.get("data", {})` returns `None` and `data.get(...)` raises. A non-numeric `start_position` raises `ValueError`. The result is an `internal_error` reply and an ERROR traceback per message.
- **Evidence**: `WebSocketMessageBase.model_validate({"type":"play_enhanced"}).model_dump()` gives `{'type': ..., 'data': None}`.
- **Exploit Scenario**: A local client loops `{"type":"seek","data":null}` and the log fills with tracebacks.
- **Impact**: Log noise and misleading errors.
- **Suggested Fix**: Use `data = message.get("data") or {}` in one shared helper, and validate `start_position` the way `handle_seek` validates `position`.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D2-04 (same defect). Publish once.

### SEC-29: `PUT /api/metadata/tracks/{id}` reflects the absolute file path in a 400 body
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `auralis-web/backend/routers/metadata_tracks.py:226-228`; message source `auralis/library/metadata_editor/metadata_editor.py:106,175`
- **Status**: NEW (siblings #3849, #5283, #5341 are closed; this site was missed; contrary to #3205)
- **Description**: `BadRequestError(f"Invalid metadata: {e}")` wraps the editor's `ValueError(f"Unsupported or invalid audio file: {filepath}")`.
- **Evidence**: The client receives `{"detail":"Invalid metadata: Unsupported or invalid audio file: /home/<user>/Music/…"}`.
- **Exploit Scenario**: Editing a corrupt file discloses the OS username and library layout.
- **Impact**: Server path disclosure, same-origin only.
- **Suggested Fix**: Return a fixed message and log the detail server-side.
- **Cross-audit overlap**: AUDIT_BACKEND_2026-10-22 BE-D7-03 (same leak). Publish once.

### SEC-30: The stale `mse-test.html` debug page ships in the production frontend bundle
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `auralis-web/frontend/public/mse-test.html` (served at `/mse-test.html`)
- **Status**: NEW
- **Description**: It is a manual harness for the retired MSE design, with inline script and a hard-coded `http://localhost:8765`, calling non-existent `/api/mse/*` routes. Vite copies it into `dist/` and Electron resources. Nothing references it.
- **Evidence**: `dist/mse-test.html` is present; `rg mse-test` finds no consumer.
- **Exploit Scenario**: None directly. It is an extra same-origin page with inline script.
- **Impact**: Hygiene and attack surface.
- **Suggested Fix**: Delete it, or move it out of `public/`.

### SEC-31: `launch-auralis-web.py` auto-installs unpinned `fastapi` / `uvicorn[standard]` via pip at launch
- **Severity**: LOW
- **OWASP Category**: A05 / A06
- **Location**: `launch-auralis-web.py:32-38`
- **Status**: NEW
- **Description**: On ImportError the launcher runs `pip install fastapi "uvicorn[standard]"` against whatever interpreter launched it, with no pins, no hashes and no prompt.
- **Evidence**: `subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])`.
- **Exploit Scenario**: Run with the wrong interpreter, it installs the latest releases unattended into the system or user Python.
- **Impact**: Bypasses the hash-lock supply-chain controls.
- **Suggested Fix**: Print the `uv pip install -r requirements.txt` instruction and exit.

### SEC-32: Electron hardening gaps: no fuses, no session permission handler, no IPC sender validation
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/package.json` (`build`: no `electronFuses`, `mac.hardenedRuntime:false`), `desktop/main.js:351-361,690-714`
- **Status**: NEW (unsigned updates are the separate open #4905)
- **Description**:
  - Defaults remain: `RunAsNode` enabled, `NODE_OPTIONS`/`--inspect` honoured, no ASAR integrity check.
  - Nothing calls `setPermissionRequestHandler` or `setPermissionCheckHandler`.
  - `ipcMain.handle` callbacks do not check `event.senderFrame.url`.
- **Evidence**: `grep "setPermission\|senderFrame\|fuses"` over `desktop/main.js` and `package.json` finds nothing.
- **Exploit Scenario**: A local process uses `ELECTRON_RUN_AS_NODE=1` to run code under the signed app identity, or an unexpected frame on the app origin is auto-granted media or notification permissions.
- **Impact**: Defence-in-depth gaps, local only.
- **Suggested Fix**: Configure fuses (RunAsNode off, NodeOptions off, Inspect off, ASAR integrity on, OnlyLoadAppFromAsar on), deny permissions by default, and check `senderFrame.url` against `APP_ORIGIN`.

#### A08 — Software and Data Integrity

### SEC-33: `.25d` sidecar validation gaps: mtime is skipped when absent, finite out-of-range values are accepted, and malformed fields raise instead of falling back
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/library/sidecar_validation.py:50-53,90-103`, `auralis/services/fingerprint_extractor.py:141`, `auralis/library/repositories/fingerprint_upsert_mixin.py:40-100`
- **Status**: NEW (residual of closed #4910; #4405 accepted size+mtime)
- **Description**:
  - `if expected_mtime and …` lets a sidecar without `modified_at` pass on file size alone.
  - Any finite dimension value (for example 1e30) is stored verbatim.
  - A non-numeric `fingerprint_version` raises `ValueError`, and a non-object `audio_file` raises `AttributeError`. Both are swallowed, so the track is marked failed with no fallback to real analysis.
- **Evidence**: Reproduced: 1e30 dims give `is_valid True`; `audio_file: []` raises `AttributeError`.
- **Exploit Scenario**: An untrusted album folder ships crafted `.25d` files, producing per-track wrong mastering parameters, poisoned similarity results, or a permanently unfingerprintable track.
- **Impact**: Per-track data-integrity loss.
- **Suggested Fix**: Make `modified_at` mandatory, check each dimension against the quantizer bounds, type-check the fields, and return "invalid" from the whole validation so the caller re-analyses.
- **Cross-audit overlap**: AUDIT_ENGINE_2026-10-22 E7-05 covers the `AttributeError` on wrong-shape JSON. The missing-mtime and range parts are new here.

### SEC-34: Metadata-edit rollback replaces a symlinked track with a regular file and leaves the real target corrupted
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/library/metadata_editor/backup.py:94,119`; callers `metadata_editor.py` (write_metadata except-branch), `batch.py:148`
- **Status**: NEW (the #5307 fix is sound for regular files)
- **Description**: `create_backup` copies through the link, mutagen writes the target in place, and `restore_backup` calls `os.replace(backup, filepath)`, which replaces the link itself. The real file keeps the half-written tags. Hard links break the same way.
- **Evidence**: Reproduced: after restore, the link is a regular file holding ORIGINAL and the real target still holds CORRUPT.
- **Exploit Scenario**: A NAS or Syncthing library made of symlinks hits a mid-write failure. The app reports a rollback while the audio file stays corrupted.
- **Impact**: Silent corruption of the user's audio file in the exact case the backup exists for.
- **Suggested Fix**: Resolve `realpath` once and use it for the backup, the save and the restore.

### SEC-35: Batch metadata rollback reports `rolled_back=True` regardless of restore success, and orphaned hidden `.bak` copies are never swept
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/library/metadata_editor/batch.py:146-150`, `backup.py:88-100`
- **Status**: NEW
- **Description**: The boolean returned by `restore_backup` is ignored. A crash between backup and cleanup leaves a hidden full-size `.<name>.XXXX.bak` in the music folder forever.
- **Evidence**: An unconditional `rolled_back = True` follows the restore loop, and there is no `.bak` sweeper anywhere.
- **Exploit Scenario**: A filesystem error during rollback leaves the file and the DB diverged while the user is told "rolled back". Interrupted edits accumulate hidden copies.
- **Impact**: Misreported state and unbounded hidden disk use.
- **Suggested Fix**: Report per-file restore results, and sweep or surface stale backups at startup or scan time.

#### A06 — Vulnerable Components

### SEC-36: No dependency-advisory gate for Python or npm in CI (Rust only), and the dev lock is already stale against advisories
- **Severity**: LOW
- **OWASP Category**: A06 / A08
- **Location**: `.github/workflows/` (only `rust-audit.yml` scans), `.github/dependabot.yml` (github-actions only), `uv.lock`
- **Status**: NEW (advisories so far, such as #5382, #4879, #4883 and #4876, were each found by hand-run audits)
- **Description**:
  - There is no `pip-audit`, `pnpm audit` or OSV step.
  - Drift is already visible: SEC-02 (Electron) and SEC-37 (multidict).
  - `uv.lock` has certifi 2026.7.22 (PYSEC-2026-4320) and urllib3 2.7.0 (PYSEC-2026-4175/4176/4177) while `requirements-lock.txt` already has the fixed versions. These are dev-only and not imported by app code.
- **Evidence**: The workflow list contains no audit job other than `cargo audit`. These are the `pip-audit` results on `uv export --frozen`.
- **Exploit Scenario**: An advisory against a runtime parser (pillow, mutagen, starlette) ships unnoticed.
- **Impact**: Slow detection of known-vulnerable components.
- **Suggested Fix**: Add a scheduled job (weekly and on lockfile change) running `pip-audit -r requirements-lock.txt` and `pnpm audit --prod` for `desktop/` and `auralis-web/frontend/`, ratcheted like the test gates, and reconcile `uv.lock`.
- **Source**: SEC-A06-4 + SEC-A08-5 (merged).

### SEC-37: multidict 6.7.1 (PYSEC-2026-4244 / CVE-2026-104874) is in the shipped lock; fixed in 6.9.1; not reachable
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: `requirements-lock.txt:814`
- **Status**: NEW
- **Description**: The advisory is a reference leak in the items-view `|` and `-` operators. multidict comes in transitively through aiohttp, which is used only as a client in `artwork_downloader.py`, and no code evaluates those operators. It is the only advisory against the hash-locked runtime set.
- **Evidence**: `pip-audit -r requirements-lock.txt` → `multidict 6.7.1 PYSEC-2026-4244 fix 6.9.1`.
- **Exploit Scenario**: None found.
- **Impact**: Theoretical memory growth.
- **Suggested Fix**: Bump to 6.9.1 or later at the next lock refresh.

### SEC-38: The FFmpeg version floor is 4.0 (2018) and only warns; no FFmpeg is bundled for Windows/macOS
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: `auralis/io/loaders/ffmpeg_probe.py:30,116-145`; `desktop/package.json` `extraResources`
- **Status**: Residual of closed #4344 (the warn-only decision is documented in code)
- **Description**: Untrusted compressed files are decoded by whatever system ffmpeg is on PATH. Every 4.x–6.x line is out of support and carries demuxer and decoder memory-corruption CVEs, and none of them triggers the warning. The protocol hardening is good but does not address codec bugs.
- **Evidence**: `MINIMUM_FFMPEG_VERSION = (4, 0, 0)`; `check_ffmpeg()` returns True after a warning.
- **Exploit Scenario**: A crafted .m4a or .ogg is scanned with an old ffmpeg, giving code execution in the subprocess.
- **Impact**: Code execution for users with unpatched FFmpeg.
- **Suggested Fix**: Raise the floor to a supported branch (for example 7.1+) and surface the warning in the UI, or bundle a pinned build.

### SEC-39: Dev and build-time npm trees carry 30+ advisories (21 high); none ship, but nothing gates them
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: `desktop/pnpm-lock.yaml` (electron-builder tree), `auralis-web/frontend/pnpm-lock.yaml`, root `pnpm-lock.yaml`
- **Status**: NEW (this class was filed as closed #4879 / #4883 and has re-accumulated; js-yaml is open #5382)
- **Description**:
  - Desktop build tree: fast-uri 3.1.5 (needs ≥3.1.8; the `^3.1.5` override permits it but the lock was not refreshed), @xmldom/xmldom 0.8.13 (needs ≥0.8.15), brace-expansion, http-cache-semantics.
  - Frontend dev tree: source-map-js (high), @vitest/mocker 4.1.11 (dev-server WebSocket advisory; needs 4.1.12), esbuild, build-time yaml.
  - Root: lodash via `concurrently`.
- **Evidence**: `pnpm audit --json`; `pnpm why` places all of them under devDependencies.
- **Exploit Scenario**: Developer exposure, for example a local web page reaching the vitest mocker WebSocket while `vitest --ui` runs.
- **Impact**: Developer and CI machines only.
- **Suggested Fix**: Bump vitest to ≥4.1.12, refresh the desktop lock, and cover it with the SEC-36 job.
- **Cross-audit overlap**: AUDIT_DEPRECATION_2026-10-22 DEP-02 flags `@xmldom/xmldom@0.8.13`. Publish once.

#### A02 — Cryptographic Failures / Sensitive Data Exposure

### SEC-40: The CLI `ArtworkService` takes Discogs and Last.fm credentials via argv and forwards them across redirects
- **Severity**: LOW
- **OWASP Category**: A02
- **Location**: `auralis/services/artwork_service.py:240-248,286-297`, `auralis/cli/fetch_artwork.py:121-130,162-164`
- **Status**: NEW (sibling gap of closed #5330 / #5529 / #2244, which covered the backend downloader and the image opener)
- **Description**:
  - Tokens are visible in `/proc/<pid>/cmdline` and shell history.
  - The metadata calls use plain `urlopen`. urllib's `HTTPRedirectHandler` copies the `Authorization` header to a different-host redirect target.
  - The Last.fm key is in the query string.
- **Evidence**: `HTTPRedirectHandler().redirect_request(req, …, "https://other.example/x")` keeps `Authorization: Discogs token=SECRET`.
- **Exploit Scenario**: A local user polls `ps` while the CLI runs, or an upstream redirect sends the token elsewhere.
- **Impact**: Disclosure of the user's own API credentials. CLI only; the backend never instantiates this service.
- **Suggested Fix**: Read credentials from environment variables or a 0600 config file, and use a redirect-refusing opener for the metadata calls.

### SEC-41: The renderer loads CSS and fonts from Google on every launch
- **Severity**: LOW
- **OWASP Category**: A02 / A08
- **Location**: `auralis-web/frontend/index.html:15-26`; CSP `auralis-web/backend/config/middleware/security_headers.py:110-111`
- **Status**: NEW (closed #2419 deferred self-hosting as a future enhancement; nothing tracks it now)
- **Description**:
  - The privileged window fetches Asap and Material Icons CSS from `fonts.googleapis.com` and the fonts from `fonts.gstatic.com`, which leaks the IP and usage on each start.
  - The remote CSS is user-agent-varying and cannot carry SRI.
  - The CSP comment says "no remote content", which is inaccurate.
- **Evidence**: `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Asap...">`; CSP `style-src … https://fonts.googleapis.com; font-src … https://fonts.gstatic.com`.
- **Exploit Scenario**: A passive observer or Google learns the user runs Auralis. An active CSS injection would need a TLS compromise.
- **Impact**: Minor privacy leak and an offline-start degradation.
- **Suggested Fix**: Self-host the fonts (`@fontsource/asap`, `material-icons`) and drop both hosts from the CSP.
- **Cross-audit overlap**: AUDIT_FRONTEND_2026-10-22 DS-09 (fonts via Google CDN, from the design-system angle).

### SEC-42: Developer-machine artifacts are tracked in the public repo (home paths and username; no secrets)
- **Severity**: LOW
- **OWASP Category**: A02 / A05
- **Location**: `.tmp-pytest/` (151 files, commit 17f1124b), `appimage-log.txt`, `auralis-web/frontend/frontend-test-output.txt`, the stray nested `auralis-web/frontend/auralis-web/` tree (commit 76e8ce40), `.codebase-memory/graph.db.zst`
- **Status**: NEW (same class as #4562 and #4346, different files)
- **Description**: These files expose `/home/matias/...` and `/mnt/data/src/...`, the scan roots and the username. None of them is gitignored. A secret-pattern scan found only the placeholder `ghp_your_token_here`.
- **Evidence**: `git ls-files .tmp-pytest | wc -l` returns 151; `git check-ignore` matches nothing.
- **Exploit Scenario**: Information for targeted path guessing or social engineering.
- **Impact**: Low disclosure and repo clutter.
- **Suggested Fix**: `git rm -r --cached` these files, and add `.tmp-pytest/`, `*.log` and `*-test-output.txt` to `.gitignore`.

#### A09 — Logging and Monitoring

### SEC-43: uvicorn's own log handlers are created after `install_log_sanitizer()` and never get `SanitizingFormatter`
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-117)
- **Location**: `auralis-web/backend/main.py:25-37,124-130`, `auralis-web/backend/config/bootstrap.py:143-155`
- **Status**: NEW (related to closed #5393)
- **Description**:
  - `uvicorn.run()` applies `LOGGING_CONFIG` later and adds `uvicorn` and `uvicorn.access` handlers with `propagate: False` and stock formatters.
  - Every unhandled exception is logged twice; the second copy, uvicorn's "Exception in ASGI application", has a raw multi-line traceback.
  - Electron forwards stderr into the persisted `main.log`.
- **Evidence**: A stub reproducing the wiring logged a `ValueError("bad\n… FORGED LINE")`. The root handler escaped it; uvicorn's output contained a real line break and the forged line.
- **Exploit Scenario**: A filename or tag embedded in a third-party exception reaches an unhandled path and forges entries in the persisted log.
- **Impact**: Integrity of the only durable log.
- **Suggested Fix**: Pass a `log_config` whose formatters subclass `SanitizingFormatter`, or `log_config=None` so `uvicorn.*` propagates to the sanitized root handler.

### SEC-44: Changes to the file-access allowlist (scan folders) are never logged
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/routers/settings.py:109-143,157-216`, `auralis-web/backend/security/path_security.py:77-102`
- **Status**: NEW
- **Description**: `register_allowed_directory`, `unregister_allowed_directory` and `clear_extra_allowed_directories` are the only runtime widening of `validate_file_path`, and none of their success paths logs anything. Only rejections are logged (#4925).
- **Evidence**: `grep -n logger routers/settings.py` finds only the module declaration.
- **Exploit Scenario**: A local process adds a sensitive directory as a scan folder, and the persisted log shows nothing.
- **Impact**: No audit trail for the backend's only security-policy mutation.
- **Suggested Fix**: Log at INFO (basename or count, per #4366) inside the three `path_security` helpers.

### SEC-45: Host-header (DNS rebinding) and CORS-preflight rejections leave no app-level log
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/config/middleware/__init__.py:63-70,98-105`
- **Status**: NEW
- **Description**: Stock `TrustedHostMiddleware` (400) and `CORSMiddleware` preflight (400) log nothing. Only the uvicorn access line remains, and it carries neither the Host nor the Origin. OriginCheck 403s, by contrast, are logged.
- **Evidence**: Reproduced with TestClient: `Host: attacker.example` and a foreign-Origin `OPTIONS` each returned 400 with no record.
- **Exploit Scenario**: A DNS-rebinding probe is blocked and leaves no evidence.
- **Impact**: Detection gap for the attacks #4353 exists to stop.
- **Suggested Fix**: Wrap both middlewares to log a throttled WARNING with the sanitized Host or Origin.

### SEC-46: Electron main-process security events are console-only and lost in a packaged build
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `desktop/main.js:38,271,278,285,413,467,707`; `desktop/preload.js:27`
- **Status**: NEW (sibling of the fixed #4920)
- **Description**: The navigation-guard block, the `openExternal` block and backend exit and start failures use `console.*`. electron-log does not patch `console`, so these lines have no destination in an installed app.
- **Evidence**: `console.warn(\`Blocked in-window navigation to non-app origin: ${url}\`)`; the only `log.*` calls are the updater and the two backend pipes.
- **Exploit Scenario**: A renderer compromise attempt is blocked silently from the point of view of any later investigation.
- **Impact**: Forensics only.
- **Suggested Fix**: Use `log.warn` / `log.error`, with control characters escaped, at these sites.

### SEC-47: Attacker-triggerable log volume is unbounded against a 1 MiB / one-archive retention
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/config/middleware/origin_check.py:80-90`, `routers/system.py:142-146`, `websocket/websocket_security.py:221-254`, `desktop/main.js:219,239-260`
- **Status**: NEW (#5375 throttled only the 429 line; open #5273 is a different site)
- **Description**:
  - Every OriginCheck rejection logs an unthrottled WARNING, and any web page can trigger these with `no-cors` POSTs.
  - Invalid WS frames are logged before the rate limiter runs.
  - `electron-log` rotates at 1 MiB with a single archive, using synchronous writes.
  - `startupOutput` accumulates all backend output for the app's lifetime.
- **Evidence**: See the locations above. The throttling pattern already exists in `rate_limit.py:74-91`.
- **Exploit Scenario**: A visited page floods rejections and evicts earlier security entries from both log files within minutes.
- **Impact**: Anti-forensic log eviction and memory growth in Electron.
- **Suggested Fix**: Reuse the #5375 per-key throttle, stop appending to `startupOutput` after readiness, and raise retention.

### SEC-48: Absolute filesystem paths are still logged at WARNING/ERROR in persisted output
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-532)
- **Location**: `auralis-web/backend/security/path_security.py:288,291,294,340,351,353`, `core/fingerprint_loading.py:241`, `core/chunk_metadata.py:51`, `core/file_signature.py:100-110`, `core/streamlined_worker.py:154`, `core/stream_normal_chunks.py:252`, `analysis/fingerprint_generator.py:309`, `routers/artwork.py:143,150-152`, `routers/processing_jobs.py:88`, `services/missing_tracks.py:69,73`, `core/chunk_cache_manager.py:186,210,215`, `core/job_cleanup.py:93`, `cache/clearing_mixin.py:118`
- **Status**: NEW (extends closed #4366 / #4376 / #4929 / #5277, which fixed INFO and startup sites)
- **Description**:
  - The `bootstrap.py` policy keeps absolute paths at DEBUG only.
  - `PathMissingError` (the most common desktop failure: a moved file or unplugged drive) puts the full path into the WARNING that the #4925 wrapper emits.
  - About 15 other WARNING/ERROR sites do the same.
- **Evidence**: `raise PathMissingError(f"File does not exist: {resolved_path}")` → `logger.warning("Path validation rejected%s: %s", …, e)`.
- **Exploit Scenario**: A user pastes `main.log` into a public issue and discloses their username and library layout.
- **Impact**: Information exposure through logs.
- **Suggested Fix**: Put `Path(x).name` (or a scan-folder-relative path) into the message, and keep the full path in a DEBUG line, as `path_security.py:271-281` already does.

#### A10 — SSRF / outbound response handling

### SEC-49: The artwork download size cap does not work: `content.read(N)` returns a partial buffer, so large covers are saved truncated
- **Severity**: LOW
- **OWASP Category**: A10 / A04
- **Location**: `auralis-web/backend/services/artwork_downloader.py:259-267,332-340`
- **Status**: NEW
- **Description**:
  - aiohttp's `StreamReader.read(n)` returns whatever is buffered (up to n bytes), so `len(data) > _MAX_ARTWORK_BYTES` can never fire for a body larger than the first buffered chunk. The over-limit branch is dead.
  - The bytes saved are a truncated image, and success is logged.
  - The only real cap is the `Content-Length` pre-check, which chunked responses skip.
  - The unit tests mock `content.read`, so they cannot catch this.
- **Evidence**: Against a local aiohttp server, a 1,048,579-byte body came back as 127,857 bytes (same on 3 runs).
- **Exploit Scenario**: No attacker is needed. Any Cover Art Archive image over about 128 KB is stored truncated, permanently.
- **Impact**: Silent corruption of cached artwork; the stated size defence is unverified. This is also a user-visible functional bug.
- **Suggested Fix**: Read in a bounded `iter_chunked` loop through one shared helper, and test it against a real local server.

### SEC-50: The downloader parses MusicBrainz and iTunes JSON with no body-size cap
- **Severity**: LOW
- **OWASP Category**: A10 / A05
- **Location**: `auralis-web/backend/services/artwork_downloader.py:240,311`
- **Status**: NEW (sibling of closed #4944, which bounded only `artwork_service.py`)
- **Description**: `await resp.json()` buffers the whole body. Only the 15 s timeout bounds it.
- **Evidence**: There is no `Content-Length` check or bounded read on these two calls.
- **Exploit Scenario**: It requires a hostile TLS peer on a fixed host.
- **Impact**: Transient memory pressure.
- **Suggested Fix**: Share a `read_json_capped(resp, limit)` helper with `artwork_service.py`.

---

## Existing / Known (verified, not re-reported)

| Issue | State | Note |
|---|---|---|
| #4905 | OPEN (HIGH) | Unsigned auto-update binaries. SEC-02 and SEC-01 amplify it. |
| #5382 | OPEN | js-yaml 4.3.1 confirmed in the packaged runtime tree via electron-updater 6.8.9. |
| #5498 | OPEN | `TrackResponse.recommended_reference` raw path (also AUDIT_INTEGRATION INT-F2-11). |
| #5270 | OPEN | No wire-level request-body cap; upload caps run after Starlette spools the body. |
| #5069 | OPEN | Rate-limit table omits expensive routes. Additional uncovered prefixes: `refresh-references`, `metadata/batch`, `settings/scan-folders`, artwork `download`/`extract`, `cache/clear`. Fold these into #5069. |
| #5079 | OPEN | `ping` is exempt from the WS rate limit. |
| #5484 | OPEN | CSP `script-src 'unsafe-inline'` (deliberate, #3900). |
| #5275 | OPEN | OriginCheck ordering comment. |
| #5713 | OPEN | Full-file decode inside each recommendation analysis (feeds SEC-08). |
| #5733 / #5731 | OPEN | ffmpeg protocol-prefix false positive / `-nostdin`. Not exploitable. |
| #5266 / #5732 | OPEN | Unbounded metadata-edit values / multi-valued tag handling. |
| #5597, #5851, #5750, #5718, #5753, #5697, #5719, #5747 | OPEN | Migration version stamping, backup pruning, schema drift, fingerprint caches, graph paging. No `PRAGMA integrity_check` exists anywhere, which is a common root cause. |
| #4823 / #5303 / #5322 | Decisions | Scanner symlink following; playback and cache-worker paths deliberately skip `validate_file_path`. Consistent with the docstring, and no caller is missing from both lists. |

**Closed fixes re-verified as still in place**:
- #4893 (CSRF on state-changing methods), #5066 (one origin set for REST and WS), #5796 (backend half), #4898 (dev mode in packaged builds), #4351 (frontend-missing page discloses no install path).
- #5363 (CSP `form-action` / `base-uri`), #5356 (Electron navigation guards), #5326 (ffmpeg protocol pinning, across the #5835 split), #5330 / #5529 / #4940 (per-hop redirect validation), #5337 (HTTPS-only artwork).
- #5375 (429 logging), #4925 (path-rejection logging), #4920 (packaged backend logs persist), #5393 (record-factory sanitizer; see SEC-14 / SEC-43 for residuals).
- #5316 (restore on migration failure), #5333 (0600 backups), #4523, #2905, #5307, #4576.
- #4868 (actions SHA-pinned), #4871 (runtime hash lock), #4855 (symlink refusal; see SEC-05 for the residual).

**Incidental, non-security** (already filed by another audit): `core/fingerprint_loading.py:84-103` builds a 7-field `MasteringFingerprint` from 25 columns, so the Tier-1 load never succeeds. This is AUDIT_BACKEND_2026-10-22 BE-D4-01.

---

## Relationships

- **SEC-24 → SEC-27, SEC-10, rate limits generally.** `proxy_headers=True` turns every per-IP control into a per-request choice for a local client. That makes the `ip_message_log` growth (SEC-27) reachable and lets the HTTP rate limiter be evaded. Fixing SEC-24 first collapses part of SEC-27.
- **SEC-02 + SEC-01 + #4905 → release-channel compromise.** Any one of them lets an attacker influence what the user installs: an Electron TLS-intermediate MITM, a floating build tool, or no update signature. Together they leave the update path with a single control. Treat them as one remediation track.
- **SEC-03 + SEC-13 → artwork pipeline trust.** Both write unvalidated bytes into `~/.auralis/artwork` and rely on the fail-open `bound_artwork_dimensions`. Fixing SEC-03's "reject on failure" also stops SEC-13's non-image copy from being served as `image/jpeg`.
- **SEC-04 / SEC-20 / SEC-33 → crafted-library inputs.** These are the same threat (an untrusted album folder) hitting different tag and sidecar fields. One "bound every tag field at extraction" pass in `metadata_extractor` / `_validate_and_normalize_track_info` covers SEC-04 and SEC-20.
- **SEC-07 + SEC-08 (+ #5713) → IO_EXECUTOR starvation.** Both pin the 8-worker pool that serves every repository call. Moving long work to dedicated bounded executors fixes both.
- **SEC-06 + SEC-43 + SEC-46 + SEC-47 → audit trail.** The engine facade drops events, uvicorn bypasses the sanitizer, Electron events go nowhere, and floods evict what remains. Investigating any incident above currently depends on luck.
- **SEC-09 + SEC-25 + SEC-26 → port ownership.** The desktop shell never establishes the identity of the process on the port. It kills whatever is there (SEC-09) and trusts whatever answers (SEC-25, SEC-26). A single "Electron owns the port and the child PID" design fixes all three.
- **SEC-10 + SEC-47.** The same cross-origin `no-cors` channel that drives expensive GETs also floods OriginCheck warnings. Rejecting cross-site `/api` requests regardless of method closes both.

---

## Prioritized Fix Order

1. **SEC-02** (bump Electron to ≥43.8.3) and **SEC-01** (hash-lock the build tools). These are cheap, mechanical, and protect every user's installer. Pair them with progress on #4905.
2. **SEC-03** (fail closed on decompression bombs and cap embedded art) and **SEC-04** (truncate or collapse the artist tag before the regex). One crafted file currently causes a persistent UI or backend DoS; both are fixes of a few lines.
3. **SEC-24** (`proxy_headers=False`). A one-line change that restores the meaning of every per-IP control and de-risks SEC-27.
4. **SEC-06** (bridge the engine logging facade to stdlib). It restores visibility for every later investigation, and **SEC-43** (uvicorn `log_config`) belongs in the same change.
5. **SEC-07 / SEC-08** (single-flight plus dedicated executors for graph build and recommendation). These are shared with the BACKEND, CONCURRENCY and INTEGRATION audits, so publish once.
6. **SEC-09** (single-instance lock, LISTEN-only and PID-verified cleanup), followed by **SEC-26 / SEC-25** (Electron owns the port and the origin).
7. **SEC-05** (owner check on the `/tmp/auralis_*` dirs, or move them under `~/.auralis`).
8. **SEC-10** (cross-site rejection for all `/api` methods), then **SEC-11** (scan-folders/delete membership check) and **SEC-12** (NUL → `PathValidationError`).
9. **SEC-49** (artwork truncation). It is LOW for security but a user-visible correctness bug on every cover over 128 KB.
10. The remaining LOW items, opportunistically. Group them as follows:
    - Logging: SEC-44..SEC-48.
    - Request bounds: SEC-15..SEC-22.
    - Electron hardening: SEC-32.
    - Repo hygiene: SEC-30, SEC-31, SEC-42.
    - Advisory gate: SEC-36, which would have caught SEC-02, SEC-37 and SEC-39 automatically.

---

*Next step*: `/audit-publish docs/audits/AUDIT_SECURITY_2026-10-22.md`. Where a finding carries a "Cross-audit overlap" line marked "Publish once", file a single issue and reference both reports.
