# Security Audit (OWASP Top 10) — 2026-09-13

- **Scope**: all 10 OWASP categories, depth `deep`, no limit
- **Tree**: `master` @ `ce119be1`
- **Method**: one dimension agent per category (max 3 concurrent). Each read the current source fresh and deduplicated against GitHub issues (all states, every `security`-labeled issue). The orchestrator re-checked every HIGH/CRITICAL claim and each merged finding's key evidence against the code before merging.
- **Threat model**: single-user Electron desktop app; the FastAPI backend binds `127.0.0.1:8765`. Attacker models in scope:
  - a malicious web page in the user's browser reaching localhost
  - another local process
  - a malicious audio file or its metadata
  - a compromised or on-path third-party service (artwork APIs, update feed)
- **Out of scope**: multi-tenant authz and "no login" (baseline, closed #4385).
- **Not a regression**: enhancement presets narrowed to `'adaptive'` (2026-09-13).

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 |
| LOW | 12 |
| **Total** | **16** (all NEW) |

This surface has been hardened over many audit cycles, and the fresh pass found no remotely exploitable access-control, injection, or SSRF path. The dimension agents re-checked about 60 closed security issues (CSRF origin middleware, WS origin-before-accept, TrustedHost for HTTP and WS, path containment, artwork SSRF, FFmpeg argument/protocol guards, log sanitizer, Electron navigation/openExternal/sandbox, dependency gates). None has regressed.

**Two HIGH claims were downgraded after verification.**
- **FFmpeg HLS SSRF (now LOW, SEC-06).** Tested empirically against the installed FFmpeg 8.0.1:
  - A text HLS playlist saved as a `.mp3` or `.m4a` file is refused ("Not detecting m3u8/hls with non standard extension and non standard mime type").
  - Even a genuine `.m3u8` input cannot open `http` segments ("Protocol 'http' not on whitelist 'file,crypto,data'").
  - A local HTTP listener received zero requests.
  - What remains is hardening: Auralis relies on FFmpeg defaults instead of pinning them, and `MINIMUM_FFMPEG_VERSION` is 4.0.
- **Streaming duration-bomb DoS (now MEDIUM, SEC-01).** It is real, but the impact is per-stream, not app-wide:
  - chunks past real EOF degrade to 100 ms of silence;
  - a new play or skip cancels the stream;
  - it is not reachable over the network.

**Key themes**
1. **Container-reported metadata is trusted on the streaming path** (SEC-01). The engine loaders enforce `MAX_DURATION_SECONDS` / `oversize_decode_detail()`, but the backend's fast probe (`unified_loader.get_audio_info`) does not. Two independent ffprobe code paths drift apart; SEC-06 is the same duplication.
2. **Backup / recovery guarantees that are not enforced** (SEC-02, SEC-03, SEC-08). The metadata-editor single-file write ignores a failed backup. A failed multi-step migration leaves the DB half-migrated although a restorable backup exists. That backup also skips the `0o600` hardening the live DB gets.
3. **Rate limiting can be turned against the user** (SEC-04, SEC-14). Method-blind prefix buckets let an un-origin-checked cross-origin GET use up the budget for `POST /api/library/scan`, and nothing is logged.
4. **Uneven `validate_file_path` coverage** (SEC-05). A background cache worker opens DB filepaths unvalidated. This is a new sibling of OPEN #5303 and is blocked by the same #4823 symlink policy question.
5. **Defense-in-depth drift in guards whose comments claim more than the code does**: log sanitizer (SEC-16), Electron preload/navigation (SEC-12), CSP (SEC-13), artwork redirects/scheme (SEC-07, SEC-09).

**Most exploitable**: SEC-04 (any open web page can lock the user out of library scans for as long as the tab stays open) and SEC-01 (a single crafted or corrupt MP3 with a forged Xing duration).

---

## Data Flow Security Matrix

| Flow | Status | Validated at | Gaps |
|------|--------|--------------|------|
| **1. File paths** (router → `path_security` → repositories → loader → FFmpeg; cache keys) | Mostly safe | `auralis-web/backend/core/stream_track_resolution.py` (normal/enhanced/seek), `routers/metadata.py`, `routers/tracks.py` (lyrics), `routers/enhancement.py`, `routers/processing_api.py`, `services/recommendation_service.py`. Containment uses `resolve()` + `is_relative_to()`. Uploads are written to UUID names. Thumbnail keys are hashes, and symlinked cache roots are refused. | Player load path (OPEN #5303). Streamlined cache worker (**SEC-05**). Scanner follows symlinks (OPEN #4823). Predictable temp dirs (OPEN #4855). `_probe_audio` has no protocol guard (**SEC-06**). |
| **2. Audio metadata** (file → parser → DB → API → render) | Mostly safe | SQL is parameterized, with column allowlists and escaped LIKE. The frontend has no `dangerouslySetInnerHTML` / HTML sink. Artwork URLs are domain-allowlisted before storage. The log sink sanitizes string args. | Container duration trusted by the streaming path (**SEC-01**). Non-str log args and tracebacks bypass the sanitizer (**SEC-16**). Latent M3U line injection in dead exporter code (**SEC-11**). |
| **3. WebSocket messages** (handshake → handler → stream controller → engine) | Safe | Origin/loopback check before `accept()` (`auralis-web/backend/config/globals.py`). TrustedHost covers the websocket scope. Size (64 KB), JSON depth, Pydantic schema allowlist, per-connection + per-IP rate limits (`auralis-web/backend/websocket/websocket_security.py`). `math.isfinite` / non-negative checks on seek positions. | `file://` WS vs REST origin split (OPEN #5066). Unmetered ping (OPEN #5079). No cap on total WS connections (informational, needs a trusted origin). |
| **4. Library scan paths** (settings → `library_scan` → scanner → DB) | Mostly safe | `validate_user_chosen_directory`. `register_allowed_directory`/`unregister_allowed_directory` paired on all three settings write paths. FIFOs and device files are never opened (`is_file` → `S_ISREG`). | Symlink escape (OPEN #4823). Scan-failure absolute paths broadcast to every WS client (**SEC-10**). |

---

## Findings

### MEDIUM

### SEC-01: Streaming path trusts container-reported duration — a forged/corrupt header drives a runaway chunk loop and log flood
- **Severity**: MEDIUM (claimed HIGH by the A04 agent; downgraded, see Calibration)
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/core/chunk_metadata.py:56-65`, `auralis/io/unified_loader.py:167-264` (`get_audio_info` → `_get_info_with_ffprobe` / `_get_info_with_soundfile`), `auralis-web/backend/core/stream_enhanced_chunks.py:76-143`, `auralis-web/backend/core/stream_seek_chunks.py:77`, `auralis-web/backend/core/chunk_operations.py:175-184`
- **Status**: NEW (distinct from closed #4342, which clamps client positions; closed #3671/#4220/#4875/#5104 added duration and byte guards only on the *decode* loaders)
- **Description**: `load_audio_metadata()` takes `duration_seconds` straight from `get_audio_info()` and computes `total_chunks = content_chunk_count(total_duration)` with no ceiling. Neither `_get_info_with_ffprobe` nor `_get_info_with_soundfile` applies `MAX_DURATION_SECONDS` or `oversize_decode_detail()`. Those checks live only in `load_audio()` (post-decode, `unified_loader.py:112-128`) and the `ffmpeg_loader` / `soundfile_loader` pre-decode paths. `grep MAX_DURATION_SECONDS auralis-web/backend/` returns nothing, and the scanner (`auralis/library/scanner/audio_analyzer.py:60-70`) stores the probed duration uncapped as well. The enhanced/seek pumps then iterate `range(processor.total_chunks)`. Each chunk past the real end of the file returns 100 ms of silence and logs an ERROR plus a WARNING (`chunk_operations.py:176-184`). Because 100 ms chunks rarely fill the frontend buffer, flow control barely paces the loop.
- **Evidence**:
  ```python
  # chunk_metadata.py
  meta = get_audio_info(filepath)
  total_duration = float(meta['duration_seconds'])
  total_chunks = content_chunk_count(total_duration)   # no cap
  # chunk_operations.py (every chunk past real EOF)
  logger.error(f"Chunk {chunk_index} resulted in empty audio ...")
  audio = np.zeros((int(0.1 * sample_rate), num_channels), dtype=np.float32)
  logger.warning(f"Returning 100ms of silence for chunk {chunk_index}")
  ```
- **Exploit Scenario**:
  1. An MP3 whose Xing/VBRI frame count claims years of audio lands in a scanned folder (a crafted download, or simply a corrupt VBR header).
  2. The scanner indexes it with the forged duration.
  3. The user plays it. `stream_start` advertises the absurd duration.
  4. The pump loops through millions of silent chunks, each running DSP, a WS send and two log lines, until the user skips.
- **Impact**: Availability. CPU burn on the streaming executor, a garbage duration in the UI, and unbounded log growth: electron-log persists backend stdout/stderr to disk (#4920), so this also fills the disk. A new play or stop cancels the stream, so it is not app-wide or persistent.
- **Suggested Fix**: Consolidate the two ffprobe paths so every probe applies `MAX_DURATION_SECONDS` and `oversize_decode_detail()`, and reject the track before any stream starts. As an independent backstop, clamp `total_chunks`, or end the stream after N consecutive empty-after-EOF chunks.

### SEC-02: Single-file metadata write proceeds after its backup silently failed
- **Severity**: MEDIUM
- **OWASP Category**: A04 / A08
- **Location**: `auralis/library/metadata_editor/metadata_editor.py:154-194` (`write_metadata`), `auralis/library/metadata_editor/backup.py:20-38` (`create_backup` returns `False` on any exception); reached from `auralis-web/backend/routers/metadata.py` (PUT track metadata)
- **Status**: NEW (closed #2407 made the backup non-suppressible by the client; nothing checks whether the backup succeeded)
- **Description**: `write_metadata()` calls `self.backup_manager.create_backup(filepath)` and discards the return value (`metadata_editor.py:156`), then rewrites the user's media file in place with mutagen `.save()`. `create_backup()` swallows every exception and returns `False`. If the save then fails, `restore_backup()` finds no `.bak` and also returns `False` silently. The sibling `batch_update()` in the same module checks the return value and aborts. The single-file path breaks the project's "fail-fast on backup failure" invariant.
- **Evidence**: `metadata_editor.py:155-156` — `if backup:\n    self.backup_manager.create_backup(filepath)`; `backup.py:36-38` — `except Exception as e: ... return False`.
- **Exploit Scenario**: A tag edit runs while the disk is nearly full, or while the backup location is unwritable (read-only mount, AV lock on Windows). The backup fails unnoticed, the in-place tag rewrite is interrupted, and the audio file is left corrupted with no `.bak`.
- **Impact**: Permanent corruption of a user's audio file despite a documented backup guarantee.
- **Suggested Fix**: If `create_backup()` returns `False`, abort before touching the file (raise), mirroring `batch_update()`.

### SEC-03: Pre-migration backup is taken but never auto-restored when a multi-step migration fails midway
- **Severity**: MEDIUM
- **OWASP Category**: A08
- **Location**: `auralis/library/migration_manager.py:187-198` (`migrate_to_latest` loop), `auralis/library/migration_manager.py:257-277` (`check_and_migrate_database`), `auralis/library/migration_backup.py:70-116` (`restore_database`, no production caller)
- **Status**: NEW
- **Description**: `check_and_migrate_database()` backs up the DB and then applies versions one step at a time. Each step is transactional. If step k of n fails, the loop returns `False` and `check_and_migrate_database()` only logs "Database migration failed" (`:274-277`). The DB stays at an intermediate schema version that no shipped app version targets. `restore_database()` exists and is correct but is only re-exported; `grep -rn restore_database auralis/ auralis-web/backend/` finds no call site. The backup path is logged at DEBUG only (`:263`).
- **Evidence**: `migration_manager.py:270-277` — `success = manager.migrate_to_latest()` … `else: logger.error("❌ Database migration failed")` / `return success`, with no restore.
- **Exploit Scenario**: An upgrade needs v15→v18. v15→v16 and v16→v17 apply; v17→v18 fails (disk full, crash, or a faulty script). The app fails closed on every later start, and the on-disk library sits at v17 with no in-app recovery.
- **Impact**: Data integrity and availability of the user's library (playlists, play stats, fingerprints) until manual intervention. This matches the severity table's "Migration that lacks rollback / backup verification" → MEDIUM.
- **Suggested Fix**: When `migrate_to_latest()` returns `False` or raises, call `restore_database(backup_path, db_path)` and log the outcome and the backup path at WARNING/ERROR.

### SEC-04: RateLimitMiddleware buckets are method-blind — un-origin-checked cross-origin GETs exhaust the budget of the state-changing POST
- **Severity**: MEDIUM
- **OWASP Category**: A07 (also A04)
- **Location**: `auralis-web/backend/config/middleware.py:209-214` (`_RATE_LIMITS`), `auralis-web/backend/config/middleware.py:276-277` (`path.startswith(prefix)`, no method check), `auralis-web/backend/config/limits.py:98-104`
- **Status**: NEW (distinct from closed #4728/#4804, which covered keying and eviction, and from OPEN #5069, which covers missing rules)
- **Description**: Buckets are keyed on `client_ip:matched_prefix` regardless of HTTP method. `OriginCheckMiddleware` intentionally gates only POST/PUT/DELETE/PATCH, so GETs from any origin reach the limiter and count against the same bucket as the guarded POST. Affected pairs:
  - `GET /api/library/scan/status` shares a bucket with `POST /api/library/scan` (2 req / 60 s)
  - GET job, queue and parameter routes under `/api/processing` share a bucket with `POST /api/processing/process` (10 / 60 s)
  - GET similar/compare/explain under `/api/similarity` share a bucket with `POST /api/similarity/fit` (20 / 60 s)

  A GET that loses the origin check still consumes budget: blocked POSTs are rejected earlier, but GETs pass that check.
- **Evidence**: `routers/library_scan.py:47` — `@router.get("/api/library/scan/status", ...)`; `middleware.py:276-277` — `for prefix, rule in self._RATE_LIMITS.items(): if path.startswith(prefix):`.
- **Exploit Scenario**: A hostile tab runs `setInterval(() => fetch('http://localhost:8765/api/library/scan/status', {mode: 'no-cors'}), 20000)`. The request is a simple GET with no preflight, and the response is never read. The user's "Scan library" click returns 429 for as long as the tab is open. Browsers without Local Network Access prompts do not block this.
- **Impact**: Availability. An unauthenticated remote page can persistently deny scanning, processing-job submission and similarity re-fit. No data is exposed.
- **Suggested Fix**: Key rules on `(method, prefix)`, or scope each rule to the exact state-changing route, so read-only siblings do not share the POST budget.

### LOW

### SEC-05: Streamlined proactive cache worker opens `track.filepath` without `validate_file_path`
- **Severity**: LOW (claimed MEDIUM; downgraded because it only touches the current track, which the player already opens unvalidated per OPEN #5303, and a fix is blocked by the same #4823 policy question)
- **OWASP Category**: A01
- **Location**: `auralis-web/backend/core/streamlined_worker.py:210-221` (`_process_chunk`), `auralis-web/backend/core/streamlined_processor_cache.py:149-198` (`get_or_build_processor` → `ChunkedAudioProcessor(filepath=...)`), `auralis-web/backend/core/streamlined_tiers.py:54,118`
- **Status**: NEW (sibling of OPEN #5303; the worker is not among the consumers listed in #5303's body)
- **Description**: Every request-driven stream path re-validates the stored path (`core/stream_track_resolution.py`, and the #4814/#4817/#4818 fixes). The background worker does not: it checks `Path(track.filepath).exists()` and passes the raw path into `ChunkedAudioProcessor`, which opens the file with no validation of its own. After the user removes a scan folder (`unregister_allowed_directory`), this worker keeps decoding and caching the current track from that folder while REST/WS paths reject it.
- **Evidence**: `streamlined_worker.py:221` — `processor = await get_or_build_processor(self, cache_key, track.filepath)`; `grep validate_file_path` over the three `streamlined_*.py` files returns nothing.
- **Exploit Scenario**: The user plays a track from `/media/usb`, then removes that folder from scan folders. The worker keeps reading the file and writing Tier-1/2 chunk caches from it on its next ticks.
- **Impact**: Folder revocation is not enforced uniformly. No arbitrary-path primitive: no API sets `track.filepath` to an attacker string.
- **Suggested Fix**: Fold this into #5303. Once the symlink policy (#4823) is settled, call `validate_file_path(track.filepath, context="streamlined worker")` at the top of `_process_chunk` and treat a rejection like file-not-found.

### SEC-06: FFmpeg/ffprobe invocations rely on FFmpeg's default protocol/demuxer restrictions instead of pinning them; `_probe_audio` lacks the protocol guard
- **Severity**: LOW (claimed HIGH + MEDIUM by the A10 agent; downgraded after an empirical test, see Calibration)
- **OWASP Category**: A10 / A03
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:232-293` (`_probe_audio` ffprobe argv, no `reject_protocol_path`), `auralis/io/loaders/ffmpeg_loader.py:426-443` (ffmpeg decode argv), `auralis/io/unified_loader.py:238-246` (second ffprobe copy), direct `_probe_audio` callers `auralis/analysis/fingerprint/windowed_compute.py:255` and `auralis/library/scanner/audio_analyzer.py:68`
- **Status**: NEW (adjacent to closed #4834 / #4826)
- **Description**:
  - **No pinned restrictions.** None of the three call sites passes `-protocol_whitelist file` or forces the container with `-f`. Safety against the classic content-sniffed HLS/concat SSRF and local-file-read therefore rests on FFmpeg's own defaults: the HLS probe's non-standard-extension refusal (recent FFmpeg), and the `file,crypto,data` nested-protocol whitelist that file inputs inherit.
  - **Old FFmpeg is still accepted.** `MINIMUM_FFMPEG_VERSION = (4, 0, 0)` only warns, and 4.x predates the extension check, so an old system FFmpeg would content-sniff an `.mp3`-named playlist as HLS. Local media-extension segments only; http is still blocked by the whitelist.
  - **Guard coverage gap.** `reject_protocol_path()` runs in `load_with_ffmpeg()` (`:340`) and in the `unified_loader` copy (`:235`), but not inside `_probe_audio()` itself. `windowed_compute.py:255` calls it with no prior guard.
- **Evidence**: The orchestrator reproduced this on the installed FFmpeg 8.0.1 with a local HTTP listener. HLS text saved as `.mp3`/`.m4a` gave `Not detecting m3u8/hls with non standard extension and non standard mime type`. The same text as `.m3u8` gave `Protocol 'http' not on whitelist 'file,crypto,data'!`. The listener saw zero requests.
- **Exploit Scenario**: Not exploitable on current FFmpeg. With an old FFmpeg, or a future caller that passes a non-absolute or protocol-shaped path to `_probe_audio`, the app's own guard would not catch it.
- **Impact**: Defense-in-depth only.
- **Suggested Fix**: Add `-protocol_whitelist file` to all three argv builders and move `reject_protocol_path()` inside `_probe_audio()`. Better still, merge the two ffprobe copies; that also fixes SEC-01's guard drift.

### SEC-07: Artwork downloads follow redirect chains automatically and allowlist-check only the final URL
- **Severity**: LOW (claimed MEDIUM; downgraded because it needs a compromised or MITM'd fixed first-party API host, and the SSRF is blind)
- **OWASP Category**: A10
- **Location**: `auralis-web/backend/services/artwork_downloader.py:200-221` (`_try_musicbrainz`), `auralis-web/backend/services/artwork_downloader.py:282-300` (`_try_itunes`), `auralis/services/artwork_service.py:352-365`
- **Status**: NEW (residual of closed #4940 / #2576, which added the final-URL check that is present)
- **Description**: aiohttp (`allow_redirects` defaults to True) and `urllib.request.urlopen` follow every hop before `_validate_artwork_url(str(resp.url))` runs. An intermediate hop pointing at a loopback or LAN address has already received the request by the time the result is rejected.
- **Evidence**: `artwork_downloader.py:203-210` — `async with session.get(coverart_url, ...) as resp:` … `if not _validate_artwork_url(str(resp.url)):`.
- **Exploit Scenario**: A compromised or MITM'd `coverartarchive.org` response 302s to `http://127.0.0.1:8765/api/...` or a router admin page, then back to an allowlisted host. The internal GET fires; the body is discarded.
- **Impact**: Blind GET-only SSRF against loopback/LAN, gated on a supply-chain-level compromise.
- **Suggested Fix**: Disable automatic redirects and follow `Location` manually, validating each hop before requesting it.

### SEC-08: Pre-migration DB backups skip the `0o600` hardening applied to the live DB and its WAL/SHM
- **Severity**: LOW
- **OWASP Category**: A02
- **Location**: `auralis/library/migration_backup.py:59-66` (`backup_database`), called from `auralis/library/migration_manager.py:262`
- **Status**: NEW (sibling gap of closed #2577 / #4347)
- **Description**: `LibraryDatabase` chmods the main DB and its `-wal`/`-shm` sidecars to `0o600` unconditionally (`auralis/library/database.py:147-153,191-197`). The full backup copy written next to the DB on every migration keeps the umask default, usually `0o644`. For the default location this is masked by the `0o700` `~/.auralis` directory. For a supported custom `database_path` it is not.
- **Evidence**: `migration_backup.py` — `src.backup(dst)` with no `os.chmod` in the module.
- **Exploit Scenario**: With a custom DB path in a shared directory, another local account reads the backup file and gets the library metadata and absolute paths.
- **Impact**: Local confidentiality of library metadata in a non-default configuration. The backup is never cleaned up automatically.
- **Suggested Fix**: `os.chmod(backup_file, 0o600)` after the backup completes.

### SEC-09: Artwork URL validator accepts plaintext `http://` for trusted domains
- **Severity**: LOW
- **OWASP Category**: A02
- **Location**: `auralis/utils/artwork_security.py:24-37` (`validate_artwork_url`, line 28)
- **Status**: NEW (closed #4936 added the validator; the scheme set was not tightened)
- **Description**: `parsed.scheme not in ("https", "http")` also permits http. The validator gates URLs returned by third-party APIs (MusicBrainz relations, Discogs, Last.fm) and post-redirect URLs, whose scheme Auralis does not control. All URLs Auralis builds itself use https.
- **Evidence**: `artwork_security.py:28`.
- **Exploit Scenario**: An on-path attacker downgrades or injects an `http://` artwork URL for a trusted host. They observe which albums the user browses and substitute image bytes, which are then size-capped and magic-byte sniffed.
- **Impact**: Privacy leak of listening habits; limited integrity (attacker-chosen image in the local cache).
- **Suggested Fix**: Allow `https` only.

### SEC-10: Scan-failure absolute filepaths are broadcast to every WS client and returned in REST, contrary to the filepath-is-server-only rule
- **Severity**: LOW
- **OWASP Category**: A02
- **Location**: `auralis/library/scan_models.py:24-36` (`ScanFailure.to_dict`), `auralis-web/backend/routers/library_scan.py:233-236` (`scan_complete` broadcast), `auralis-web/backend/routers/library_scan.py:267` (`ScanResultResponse.failures`)
- **Status**: NEW (sibling of closed #2300 / #2479 / #2483 / #5283; introduced with #4841)
- **Description**: `TrackResponse` deliberately omits `filepath` (#3205), but `ScanFailure` serializes the raw absolute path (up to 50 per scan). It goes into the REST response and into a `scan_complete` broadcast to all WS subscribers.
- **Evidence**: `scan_models.py` — `return {'filepath': self.filepath, 'reason': self.reason}`; `library_scan.py:233-236` — `"failures": [... failure.to_dict() for failure in result.failures]`.
- **Exploit Scenario**: A local process on loopback (empty Origin is allowed from loopback) subscribes to `/ws` and learns the OS username and library layout whenever a scan hits a bad file.
- **Impact**: Local filesystem-layout and username disclosure.
- **Suggested Fix**: Send a library-relative path or basename plus the reason. If the UI needs the full path, keep it in the requester's REST response only.

### SEC-11: M3U/XSPF exporters interpolate tag values without stripping CR/LF (latent — no live caller)
- **Severity**: LOW
- **OWASP Category**: A03
- **Location**: `auralis/utils/queue/m3u_handler.py:58-79` (`M3UHandler.export`), `auralis/utils/queue/xspf_handler.py:67-116`
- **Status**: NEW
- **Description**: `#EXTINF` lines are built from `title`/`artists`/`filepath` via f-strings and joined with `\n`. A tag containing a newline becomes a separate line, which `import_from_string()` treats as a file path. XSPF is safe structurally because ElementTree escapes text. There are currently zero callers of `QueueExporter`/`M3UHandler`/`XSPFHandler` outside the package.
- **Evidence**: `m3u_handler.py` — `extinf = f'{M3UHandler.EXTINF_PREFIX}{duration},{artist_str} - {title}'`.
- **Exploit Scenario**: Once export is wired up, a crafted title injects an extra path or UNC entry into exported playlists, which is opened on re-import.
- **Impact**: Playlist-file integrity; latent only.
- **Suggested Fix**: Strip or escape control characters in exported fields, reusing `sanitize_log_value`-style handling. Alternatively, delete the unused exporter.

### SEC-12: Electron navigation/IPC trust guards are looser than documented (any `file:` URL; hostname-only preload check)
- **Severity**: LOW
- **OWASP Category**: A05 / A07
- **Location**: `desktop/url-safety.js:45-55` (`isAllowedAppNavigation`, `file:` branch at line 52), `desktop/preload.js:13-17`, consumed by `desktop/main.js:679-711`
- **Status**: NEW (residual of closed #4858)
- **Description**:
  - **(a) Any local file is a legal destination.** `isAllowedAppNavigation` returns true for any `file:` URL, although it exists to permit only the bundled offline error page. Any local file becomes a legal in-window navigation target.
  - **(b) Preload checks hostname, not origin.** The preload backstop, documented as ensuring "the remote document still gets no IPC surface at all", checks `window.location.hostname !== 'localhost'`. Hostname ignores the port, so a document on `http://localhost:<any port>` receives `electronAPI`. The primary guard compares the full origin.
- **Evidence**: `url-safety.js:52` — `if (parsed.protocol === 'file:') return true;`; `preload.js:13` — `if (window.location.hostname !== 'localhost') {`.
- **Exploit Scenario**: Suppose an unknown navigation vector bypasses `will-navigate` (none is currently known). Then (a) the window can display arbitrary local files, and (b) a page served by another local process on a different localhost port gets the native file/folder-picker and window-control IPC.
- **Impact**: Defense-in-depth. Neither is reachable without a separate navigation bypass.
- **Suggested Fix**: Match the exact packaged error-page URL instead of the whole `file:` scheme. Check `window.location.origin` against the shared `APP_ORIGIN`/`DEV_ORIGIN`.

### SEC-13: CSP lacks `form-action` and `base-uri` (not covered by `default-src`)
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `auralis-web/backend/config/middleware.py:180-191` (`SecurityHeadersMiddleware` CSP string)
- **Status**: NEW (closed #2628 / #3900 / #4712 cover other directives)
- **Description**: Per the CSP spec, `default-src` does not fall back to `form-action` or `base-uri`, so both are unrestricted. `frame-ancestors` is also absent, but `X-Frame-Options: DENY` covers it.
- **Evidence**: The CSP string at `middleware.py:181` starts with `default-src 'self'` and contains no `form-action` / `base-uri` token (grep).
- **Exploit Scenario**: If an HTML-injection sink is ever introduced, an injected `<form action>` can post data off-origin, or `<base href>` can re-point relative URLs.
- **Impact**: Hardening only; no current sink.
- **Suggested Fix**: Append `form-action 'self'; base-uri 'self';`.

### SEC-14: RateLimitMiddleware never logs its 429 rejections
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/config/middleware.py:255-329` (`RateLimitMiddleware.dispatch`)
- **Status**: NEW
- **Description**: Every other rejection path logs a WARNING: `OriginCheckMiddleware`, the WS origin check, WS validation and rate limits, and path validation via `_logs_rejections`. The HTTP rate limiter builds and returns the 429 with no log call.
- **Evidence**: The 429 `JSONResponse` branch has no preceding `logger.*` call; the only log calls in the class are in its error handler.
- **Exploit Scenario**: SEC-04's lockout leaves no trace in the persisted log, so the user cannot find out why scans fail.
- **Impact**: Local DoS and probing cannot be detected.
- **Suggested Fix**: Emit a sampled or throttled WARNING with the client IP and matched rule before returning 429.

### SEC-15: js-yaml 4.3.1 in the desktop runtime tree is affected by GHSA-2883-xcg3-v3hh (CPU-exhaustion DoS)
- **Severity**: LOW (claimed MEDIUM; downgraded because the only input is the TLS-fetched update manifest, and an attacker who controls that feed can already ship an unsigned binary per OPEN #4905)
- **OWASP Category**: A06
- **Location**: `desktop/package.json:44` (`pnpm.overrides.js-yaml: "^4.3.1"`), `desktop/pnpm-lock.yaml:619,1837` (resolved `js-yaml@4.3.1`); reached via `electron-updater` → `autoUpdater.checkForUpdates()` in `desktop/main.js`
- **Status**: NEW (not among the 26 advisories in closed #4879; published 2026-09-08)
- **Description**: Verified by the orchestrator: `pnpm audit --prod --json` in `desktop/` reports advisory 1193727, GHSA-2883-xcg3-v3hh / CVE-2026-84375, severity high. `maxTotalMergeKeys` does not limit CPU use for empty merge sources. Vulnerable range `>=4.0.0 <4.3.2`; path `.>electron-updater>js-yaml`; installed 4.3.1. The patched 4.3.2 already satisfies the repo's own override range, so this is a stale lockfile.
- **Evidence**: `pnpm audit` metadata `{'high': 1}`; `pnpm-lock.yaml:619` — `js-yaml@4.3.1:`.
- **Exploit Scenario**: A malicious `latest.yml` with repeated empty-mapping merge keys, served from a compromised release feed, pegs a CPU core during the automatic update check shortly after launch.
- **Impact**: App startup hang or CPU exhaustion. Strictly weaker than what feed control already permits.
- **Suggested Fix**: Raise the override to `^4.3.2` (or drop it) and regenerate `desktop/pnpm-lock.yaml`.

### SEC-16: Log-injection sanitizer skips non-`str` args and exception tracebacks
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis/utils/logging.py:165-183` (`_sanitizing_log_record_factory`). Reachable via `auralis-web/backend/routers/artwork.py:270` (`logger.exception("Thumbnail generation failed for %s", src)` with a `Path`), several `auralis-web/backend/core/thumbnail_cache.py` `%s`-with-`Path` sites, and `exc_info=True` in `auralis-web/backend/routers/errors.py:44-49`
- **Status**: NEW (coverage gap in the central fix for closed #4363 / #4828)
- **Description**: The factory sanitizes `record.msg` only when it is a `str`, and each `record.args` element only when it is a `str`. `Path` and `Exception` args pass through untouched and are `str()`-formatted later in `getMessage()`, after sanitization has run. Traceback text from `exc_info` is rendered by the Formatter and never sanitized; the factory's docstring says so. Loader exceptions embed raw paths in their message, e.g. `auralis/io/loader.py:205` and `auralis/io/loaders/soundfile_loader.py:87`, so a CR/LF in a filename reaches the persisted log verbatim.
- **Evidence**: `logging.py:176-179` — `sanitize_log_value(arg) if isinstance(arg, str) else arg`.
- **Exploit Scenario**: A cover-art file named `cover\r\n<fake log line>.jpg` in a scanned folder fails thumbnail generation, and the forged line lands in the electron-log file.
- **Impact**: Log integrity for post-incident review.
- **Suggested Fix**: Sanitize `str(arg)` for non-`str` args. Install a Formatter subclass that sanitizes `formatException()` output, or have internal exceptions carry the path in the structured `.path` attribute rather than their message.

---

## Existing Issues (verified, not re-reported)

| Issue | State | Re-check result |
|-------|-------|-----------------|
| #5303 | OPEN | Player load path still opens DB filepaths unvalidated (`services/queue_service.py`, `routers/player.py`); SEC-05 is a new sibling |
| #4823 | OPEN | Scanner still follows symlinks without containment (`auralis/library/scanner/file_discovery.py:136,157`) |
| #4855 | OPEN | Fixed-name temp dirs under the system temp root are still present |
| #5066 | OPEN | `file://` is in the WS origin allowlist but not REST — unchanged |
| #5277 | OPEN | Temp-cleanup failure logs an absolute path at WARNING — unchanged |
| #4905 | OPEN | Unsigned auto-update (context for SEC-15) |
| #5069 / #5079 | OPEN | Rate-limit table omissions; unmetered WS ping |
| #5275 | OPEN | Comment-only middleware-order mismatch; actual order verified correct |

**Closed issues verified still fixed (no regressions)**, grouped by area:

| Area | Issues |
|------|--------|
| Cross-origin requests and headers | #4893 (CSRF — method+path based, covers multipart and no-body routes), #2413/#3845 (WS origin), #3810/#3811 (WS rate limit), #4353 (TrustedHost, HTTP and websocket scopes), #4728/#4804/#2630 (rate-limit keying and bounds), #3843, #4712, #2418/#4375 (docs/openapi dev-only), #4802/#4898/#4350 (dev-mode gating) |
| File paths and uploads | #2559/#2561/#2562 (processing path validation), #4814/#4817/#4818, #3842/#5259 (allowlist revocation), #2415/#4349 (upload magic bytes and caps), #4342 (chunk index clamp), #4837 (fingerprint timeout) |
| SQL and input validation | #2286/#3772 (fingerprint SQL allowlist), #2405/#4348 (LIKE escaping), #4555 (metadata mass-assignment), #5283 (batch filepath leak) |
| FFmpeg arguments | #4826/#4834 |
| Artwork fetching | #2416/#2576/#4688/#4936/#4940/#4944 |
| Logging | #4363/#4828 (string-arg path), #4366/#4376/#4778/#4929 (path logging), #4920/#4932 (packaged log file, `0o600`), #4925 (rejection logging, now a decorator) |
| Files on disk and integrity | #2577/#4347 (DB permissions), #4910/#5103 (non-finite fingerprints), #2419 (SRI rationale unchanged) |
| Electron | #4844/#4848/#4851/#4853/#4858 |
| Dependencies and CI | #4878 (Electron 43 supported), #4876 (builder-util-runtime 9.7.0), #4882/#4872 (Cargo.lock tracked, cargo audit clean apart from 2 reachability-verified pyo3 ignores), #4868 (all 40 action refs SHA-pinned, dependabot present), #4889 (hash-locked requirements), #4346 (no secrets or `.env` tracked) |

---

## Relationships

- **SEC-01 ↔ SEC-06 ↔ SEC-16.** One root cause: duplicated ffprobe code paths in `auralis/io/unified_loader.py` and `auralis/io/loaders/ffmpeg_loader.py` have drifted, so each guard (duration cap, protocol guard) lives in one copy and not the other. Consolidating into one guarded probe fixes SEC-01's missing cap and SEC-06's guard gap in one change. SEC-01's per-chunk ERROR/WARNING flood also multiplies SEC-16's log-integrity exposure and disk growth.
- **SEC-04 + SEC-14.** The lockout is also invisible in the logs. Fix them together.
- **SEC-02 + SEC-03 + SEC-08.** The backup lifecycle is enforced nowhere: a failed backup is not checked (metadata), a good backup is not used (migration), and the backup file is not protected (permissions).
- **SEC-05 ↔ #5303 ↔ #4823.** `validate_file_path` cannot be applied to playback-side consumers until the symlinked-library policy is decided. Handle them as one change.
- **SEC-07 + SEC-09.** Both belong to the artwork fetch trust boundary (`auralis/utils/artwork_security.py`). Tighten the scheme and add per-hop validation together.
- **SEC-12 + SEC-13 + SEC-11.** Each needs an injection or navigation sink that does not exist today. They matter together if one is ever added: CSP `form-action`/`base-uri`, the navigation `file:` branch, and the preload origin check are the layers such a sink would test.
- **SEC-15 ⊂ #4905.** Signing the update pipeline shrinks the update-feed attack surface far more than the js-yaml bump.

## Prioritized Fix Order

1. **SEC-02.** A one-line fail-fast check that prevents irreversible audio-file corruption. Smallest change with the highest data-loss impact.
2. **SEC-01 (+ SEC-06).** Consolidate the ffprobe paths behind one guarded probe that enforces `MAX_DURATION_SECONDS` and `-protocol_whitelist file`, and cap `total_chunks` or stop after consecutive empty chunks. Covers a crafted or corrupt-file DoS and a guard-drift root cause.
3. **SEC-03 (+ SEC-08).** Auto-restore on migration failure and chmod the backup, both in the migration module.
4. **SEC-04 (+ SEC-14).** Method-aware rate-limit rules plus a 429 log line. Closes the only remotely triggerable issue in this report.
5. **SEC-15.** Regenerate the desktop lockfile. Trivial, and it clears the `pnpm audit` high.
6. **SEC-05.** Fold into #5303 once the #4823 policy decision is made.
7. **SEC-10, SEC-09, SEC-07, SEC-16.** Local-info and fetch-trust hardening.
8. **SEC-12, SEC-13, SEC-11.** Latent defense-in-depth; do them opportunistically, or delete the dead exporter.

## Calibration Notes (claims changed during verification)

| Claim | Agent severity | Final | Reason |
|-------|----------------|-------|--------|
| FFmpeg content-sniffed HLS SSRF/LFI (A10-1) | HIGH | LOW (SEC-06) | Refuted on installed FFmpeg 8.0.1 by a local test: HLS text saved as `.mp3`/`.m4a` was refused by the probe, http segments were blocked by the inherited `file,crypto,data` whitelist even for a real `.m3u8`, and the listener saw 0 requests. Remains as hardening for old FFmpeg (minimum 4.0 only warns). |
| `_probe_audio` missing protocol guard (A10-2) | MEDIUM | merged into SEC-06 | All current callers pass absolute scanner-derived paths, which cannot match the protocol regex. |
| Streaming duration bomb (A04-1) | HIGH | MEDIUM (SEC-01) | Confirmed in code, but past-EOF chunks become 100 ms of silence, new play or skip cancels the stream, it needs a file in the library, and it is not network-reachable. The "app-wide until restart" claim is overstated. |
| Redirect hops before allowlist (A10-3) | MEDIUM | LOW (SEC-07) | Requires compromise of a fixed first-party API host; blind GET only. |
| Streamlined worker unvalidated path (A01-1) | MEDIUM | LOW (SEC-05) | Only touches the current track, which the player already opens unvalidated (#5303, LOW); blocked by the same #4823 policy question. |
| js-yaml advisory (A06-1) | MEDIUM | LOW (SEC-15) | Advisory confirmed via `pnpm audit`, but feed control already implies code execution via unsigned updates (#4905). |
| A05-1 + A07-2 | LOW + LOW | merged (SEC-12) | Same Electron navigation/IPC trust guard family. |
| A09-2 + A09-3 | LOW + LOW | merged (SEC-16) | Same sanitizer-coverage root cause. |

**Informational notes (not filed):**
- No cap on total concurrent WS connections; opening one requires a trusted origin or loopback.
- Validate-then-open TOCTOU in `path_security` needs write access to the library path.
- `GenreRepository.create/update` and `fingerprint_crud_mixin.update` use `hasattr` guards rather than allowlists; there are no external callers.
- `auralis/core/stages/safety_limiter.py` `apply()` appears to have no pipeline caller (tech-debt, for the engine audit); the output peak is still bounded by `normalize()` in the continuous branch.
