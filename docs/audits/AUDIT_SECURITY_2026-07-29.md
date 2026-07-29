# Security Audit — Auralis — 2026-07-29

**Scope**: OWASP Top 10 (2021), A01–A10, across the core Python engine (`auralis/`), the
FastAPI backend (`auralis-web/backend/`), the React frontend (`auralis-web/frontend/`), the
Electron wrapper (`desktop/`), the Rust DSP module (`vendor/auralis-dsp/`), and the CI /
release pipeline (`.github/workflows/`).

**Method**: Read-only source analysis. Ten parallel dimension agents, one per OWASP category,
each with an independent coverage statement. No dynamic testing, no network requests, no
code changes.

**Audit lineage**: The previous security audit (2026-07-25) was **CANCELLED mid-run and never
produced a report**. The last completed baseline is therefore
[`AUDIT_SECURITY_2026-07-12.md`](AUDIT_SECURITY_2026-07-12.md). **This is the first completed
security pass since 2026-07-12.**

---

## Threat Model

Severities in this report are rated **against this model**, not against a generic web-app model.

Auralis is a **single-user Electron desktop application**. The FastAPI backend binds
`127.0.0.1:8765` and is consumed only by the bundled Electron renderer on the same machine.

**Out of scope** (findings premised on these are downgraded or not filed):
- Multi-user / multi-tenant isolation
- Remote or LAN network exposure of the backend
- Server-side deployment, containers, reverse proxies
- Remote unauthenticated attackers reaching the API

**In scope** (the real attack surface for a desktop app):
- Path traversal and filesystem containment
- Malicious media files and hostile embedded metadata (tags, cover art, sidecars)
- Unsafe deserialization
- Decompression / resource-exhaustion bombs
- SSRF and the outbound network surface
- Subprocess and command/argument injection (ffmpeg, ffprobe)
- Temp-file and symlink races; file/directory permissions
- Electron hardening: `nodeIntegration`, `contextIsolation`, preload surface, protocol handlers,
  navigation control
- Committed secrets
- Dependency vulnerabilities
- The auto-update trust chain

The realistic adversary is therefore: **a hostile audio file, a hostile metadata field, a hostile
third-party HTTP response, or a hostile/compromised update artifact** — not a remote attacker
with network reach.

---

## Executive Summary

**41 findings** across all 10 OWASP categories (0 CRITICAL, 4 HIGH, 12 MEDIUM, 25 LOW), plus 2
cross-references to already-open issues (#4531, #4688) and 1 explicit cross-dimension duplicate
(A02-1 is the same underlying issue as A08-1; not double-counted — see A08-1 for the authoritative
write-up).

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 12 |
| LOW | 25 |
| **Total** | **41** |

### The most consequential finding

**A08-1 — the desktop auto-update pipeline ships fully unsigned binaries.** No code-signing
certificates exist anywhere in the repo or build config; `verifyUpdateCodeSignature: false` is
explicitly set on Windows; `hardenedRuntime`/`gatekeeperAssess` are disabled on macOS; and the
release's `SHA256SUMS.txt` is generated from the same unsigned artifacts it purports to verify.
For a single-user desktop app, the auto-update channel is the one code-execution path that
crosses a trust boundary (a compromised release server or a MITM'd download becomes arbitrary
code execution on the user's machine with no independent verification catching it) — it is rated
HIGH under this threat model specifically because it is the sole in-scope path where "hostile
input" becomes "attacker-controlled code," not merely "attacker-controlled data."

### Other HIGH findings

- **A05-1 / A05-7** — Electron hardening gaps: `shell.openExternal(url)` is called unconditionally
  on any new-window navigation with no scheme allowlist, and there is no `will-navigate` handler,
  so top-level in-window navigation to any origin is allowed by default while `preload.js`
  re-exposes the full `electronAPI` IPC surface to whatever page is navigated to. Combined, a
  hostile link (e.g. from a crafted artwork/metadata field rendered somewhere clickable) could
  navigate the app's own window to an attacker page that inherits IPC access.
- **A07-2** — State-changing POST endpoints accept requests with no JSON-body validation,
  making them exploitable via plain cross-origin "simple requests" (a CSRF-shaped gap) despite
  the backend being localhost-only — the browser-based attack surface is a hostile web page the
  user has open, not a remote network attacker.

### Cross-cutting theme

Several MEDIUM/LOW findings across A01, A03, and A08 repeat one pattern already flagged by other
audits this session: a fix lands for the *common* case but misses sibling routes/call sites that
share the same vulnerability shape (A01's filepath-revalidation gaps hit some routes and not
others; A03-2's log-injection fix covers 4 of many files). This is the same "closed but not fully
fixed" pattern the engine, backend, and integration audits found repeatedly elsewhere in the
codebase this session — worth treating as a process issue (fixes need a "find all call sites of
this shape" step) rather than N separate one-off bugs.

### What this audit does NOT cover

Per the threat model (single-user Electron desktop app, backend on `127.0.0.1:8765`), findings
premised on remote/multi-tenant attackers were out of scope by design and are not filed. See the
per-dimension coverage statements below for what each of the 10 OWASP dimensions did and did not
examine — several dimensions explicitly flag areas as unexamined rather than implicitly clean
(notably: CI secrets configured in GitHub Settings cannot be inspected from a local checkout;
`desktop/main.js` was read only in the sections relevant to each dimension, not in its entirety;
dynamic/runtime testing was not performed anywhere in this audit).

---

## A01 — Broken Access Control

**Dimension status**: COMPLETE. 4 findings, all LOW under this threat model.

The unifying theme: the codebase has an established, deliberate pattern of **re-validating
DB-sourced filepaths at the point of file I/O** (`validate_file_path()`), because
`unregister_allowed_directory()` can retroactively push a previously-indexed track's path
outside the allowed set. Several sibling routes were missed by both the #2302 and #4345 fixes,
producing a track that is silently readable via one route and rejected with 400/403 via another.

### A01-1 — `GET /api/library/tracks/{track_id}/lyrics` reads DB filepath with mutagen, bypassing `validate_file_path`

- **Severity**: LOW
- **Location**: `auralis-web/backend/routers/tracks.py:150-152`
- **Status**: NEW (sibling of closed #4345 / SEC-L1, not covered by that fix)
- **Description**: The lyrics endpoint calls `mutagen.File(track.filepath)` directly on the
  DB-sourced path with no call to `validate_file_path()`. The codebase has an established,
  deliberate pattern (see `metadata.py` comments "Validate DB-retrieved filepath before any file
  I/O (fixes #2302)", and the now-closed #4345/SEC-L1 which added the same guard to the WAV
  streaming endpoints) of re-validating DB filepaths against the currently-allowed-directories
  list at the point of file I/O — specifically because `unregister_allowed_directory()`
  (`settings.py`) can retroactively make a previously-added track's filepath fall outside the
  allowed set (folder removed from scan list) while the DB row still references it. This endpoint
  was missed by both the #2302 fix and the #4345 fix.
- **Evidence**:
  ```python
  # tracks.py:150-152
  import mutagen
  audio_file = await asyncio.to_thread(mutagen.File, track.filepath)  # type: ignore[attr-defined]
  ```
  Compare to `metadata.py:127`: `# Validate DB-retrieved filepath before any file I/O (fixes #2302)`
  followed by `validate_file_path(str(track.filepath))`.
- **Exploit Scenario**: 1) User adds scan folder A, library indexes track T with
  `filepath=/A/song.mp3`. 2) User removes folder A via settings (`unregister_allowed_directory`
  fires). 3) If T's filepath had, at index time, actually resolved outside the allowed set through
  a mechanism the scanner didn't catch (or simply: the folder is later repurposed/symlinked to
  point elsewhere while the DB row is stale), a call to `/api/library/tracks/{T}/lyrics` still runs
  `mutagen.File()` on the raw stored path with no re-check, unlike every other DB-filepath consumer.
- **Impact**: Limited — `mutagen.File()` only parses recognized audio-tag containers and returns
  `None`/tag data, it does not echo arbitrary bytes back to the client; this is
  metadata-parsing exposure/DoS-shaped (mutagen has had past parser CVEs) rather than raw
  arbitrary-file-read. Severity kept LOW to match the desktop threat model and the precedent set
  by #4345 (also rated LOW for the identical pattern).
- **Siblings**: A01-2, A01-3 (`enhancement.py`) — same class, same missing guard.
- **Suggested Fix**: Wrap `track.filepath` with `validate_file_path()` before the `mutagen.File()`
  call, mirroring `metadata.py`'s pattern; on `PathValidationError`, skip file-based lyric
  extraction the same way the DB-only lyrics branch does.

### A01-2 — Mastering-recommendation endpoint feeds unvalidated DB filepath into `ChunkedAudioProcessor`

- **Severity**: LOW
- **Location**: `auralis-web/backend/routers/enhancement.py:401-487` (filepath used at 446-477)
- **Status**: NEW (sibling of closed #4345 / SEC-L1)
- **Description**: `GET /api/player/mastering/recommendation/{track_id}` resolves
  `filepath = track.filepath` straight from the DB (the comment even says "fixes #2731" for a
  *different* concern — track/file mismatch — not path containment) and passes it directly into
  `ChunkedAudioProcessor(filepath=_fp, ...)`, which performs file I/O. No `validate_file_path()`
  call anywhere on this path.
- **Evidence**:
  ```python
  # enhancement.py:446-477
  filepath = track.filepath
  ...
  _fp = str(filepath)
  ...
  proc = ChunkedAudioProcessor(track_id=_tid, filepath=_fp, preset="adaptive", intensity=1.0, chunk_cache={})
  ```
- **Exploit Scenario**: Same class as A01-1: a stale/edge-case DB filepath (folder unregistered
  after indexing, or any future code path that inserts a track row with an attacker-influenced
  path) is used for real file I/O without re-checking containment at the access site.
- **Impact**: Audio file is opened/decoded (`sf.info`/decode via `ChunkedAudioProcessor`) for
  arbitrary local paths reachable through a stale DB row; bounded by "must already be a track row,"
  not a general arbitrary-path parameter.
- **Dedup note**: `issue_titles.txt` has a matching-sounding CLOSED issue,
  `#4542 [CLOSED] HIGH - Mastering-recommendation feature is fully dead — its only trigger point is never called by the frontend`.
  That issue is about the direct REST endpoint being unreachable from the UI — a
  dead-code/reachability concern, not path validation — and does not cover or invalidate this
  finding. More importantly, the identical unvalidated-`track.filepath` → `ChunkedAudioProcessor`
  pattern is exercised through a second, **actively live** trigger: `routers/player.py:410-417`
  calls `background_tasks.add_task(service.generate_and_broadcast_recommendation, track_id=track.id, track_path=track.filepath)`
  automatically on every successful `POST /api/player/load`, and
  `RecommendationService.generate_and_broadcast_recommendation()`
  (`services/recommendation_service.py:48-112`) feeds `track_path` straight into
  `ChunkedAudioProcessor` with no `validate_file_path()` call either. So even if the REST endpoint
  itself is dead per #4542, this exact code path runs on every track load.
- **Siblings**: A01-1, A01-3, and `services/recommendation_service.py:48-112` / `114-162`.
- **Suggested Fix**: Apply `validate_file_path(str(track.filepath))` immediately after the DB
  lookup, before constructing `ChunkedAudioProcessor`, consistent with `metadata.py`.

### A01-3 — `_preprocess_upcoming_chunks` background task uses unvalidated player-state filepath

- **Severity**: LOW
- **Location**: `auralis-web/backend/routers/enhancement.py:136-172` (call site at 239-247)
- **Status**: NEW (sibling of closed #4345 / SEC-L1)
- **Description**: `POST /api/player/enhancement/toggle` (when enabling mid-playback) spawns a
  background task passing `filepath=state.current_track.filepath` (itself DB-sourced, reached via
  player state) into `_preprocess_upcoming_chunks`, which calls `sf.info(filepath)` and constructs
  `ChunkedAudioProcessor(filepath=filepath, ...)` — again with no `validate_file_path()` anywhere
  in the chain.
- **Evidence**:
  ```python
  # enhancement.py:239-245
  _preprocess_upcoming_chunks(
      track_id=state.current_track.id,
      filepath=state.current_track.filepath,
      ...
  )
  # enhancement.py:162
  info = await asyncio.to_thread(sf.info, filepath)
  ```
- **Impact**: Same bound as A01-2 (audio decode of a DB-referenced path, not an arbitrary
  user-supplied parameter); running as an unsupervised background task makes failures silent
  (errors are only logged).
- **Suggested Fix**: Validate `filepath` at the top of `_preprocess_upcoming_chunks` (or before
  scheduling it) and skip pre-processing on `PathValidationError`.

### A01-4 — Scanner follows symlinks with no containment check on the resolved target (only cycle detection)

- **Severity**: LOW
- **Location**: `auralis/library/scanner/file_discovery.py:110-166` (`_walk_directory`)
- **Status**: NEW
- **Description**: `_walk_directory()` calls `entry.is_dir(follow_symlinks=True)` /
  `entry.is_file(follow_symlinks=True)` and recurses through symlinked subdirectories. The only
  safeguard is an inode-based `visited_inodes` set that prevents infinite loops (a symlink cycle)
  or re-emitting the same physical directory twice — it does **not** check whether a symlink's
  real target lies outside the originally-scanned root before descending into it.
- **Evidence**:
  ```python
  # file_discovery.py:136, 154-155
  if entry.is_dir(follow_symlinks=True):
      ...
      visited_inodes.add(inode_key)
      yield from self._walk_directory(entry_path, visited_inodes, depth + 1)
  ```
  No comparison of `entry_path.resolve()` (or the real target) against the originally-requested
  scan root anywhere in this function.
- **Why rated LOW, not higher**: This is largely consistent with — not a violation of — the
  codebase's own explicit design for user-picked scan folders: `validate_user_chosen_directory()`
  (`path_security.py:255-304`) deliberately does **not** enforce containment to Music/Documents for
  a user-selected folder ("Auralis is a single-user desktop app... we trust their choice"), and
  `validate_scan_path()` (the containment-enforcing sibling) is dead code — never called anywhere
  in the codebase (verified via repo-wide grep). Since the process runs as the same OS user as any
  other local program, a symlink escape does not cross a privilege boundary.
- **Concrete security-relevant side effect (why still worth recording)**: The resulting
  `Track.filepath` (real path via the symlink target) will very likely fall **outside**
  `get_allowed_directories()`. That means the exact same DB row is: (a) freely readable via routes
  that skip `validate_file_path` (tracks.py lyrics, enhancement.py — A01-1/2/3, and the engine's
  playback path which never calls `validate_file_path` at all), while (b) rejected with 400/403 by
  routes that do call `validate_file_path` (metadata.py, the WAV streaming endpoints). This
  reproduces, via a different root cause, the exact "inconsistent enforcement across sibling
  routes" pattern called out for A01-1/2/3.
- **Impact**: No privilege boundary crossed under this desktop threat model; impact is limited to
  indexing/playing audio files the user's own account can already access, plus the
  inconsistent-enforcement side effect above.
- **Siblings**: `auralis/library/sidecar_manager.py:49-243` writes a `<file>.25d` sidecar next to
  whatever `Track.filepath` resolves to, so a symlink-escaped track also gets an
  out-of-library-root JSON write.
- **Suggested Fix**: If containment for scanned content is ever desired, resolve each directory
  entry and compare against the resolved scan root before recursing — but this is a product-policy
  decision (symlinked libraries are a legitimate use case), not a clear-cut bug fix. At minimum,
  make DB-filepath consumers consistently call `validate_file_path`.

### A01 — Disproved hypotheses / examined and ruled out

- **TOCTOU between `validate_file_path()` and the actual `open()`**: The gap exists mechanically
  (validate returns a resolved path string; callers re-open by path rather than keeping a file
  descriptor), so a symlink swapped in between check and open would be followed. Not filed:
  exploiting it requires a second local process with write access inside the allowed set racing the
  backend — that process already runs as the same OS user; no privilege boundary is crossed.
- **Symlink pointing inside the library out to elsewhere, checked via `validate_file_path`**:
  correctly rejected — `Path.resolve()` follows symlinks before the `relative_to()` containment
  check, so `metadata.py`, the streaming endpoints, `processing_api.py`, and `artwork.py` all
  correctly reject it. No bypass found.
- **Case-insensitive filesystem**: `relative_to()` comparison is case-sensitive; on a
  case-insensitive filesystem this can only cause a spurious *rejection* (fail-closed), not a bypass.
- **Empty allowed-directory list**: `get_allowed_directories()` returning `[]` leaves
  `is_allowed = False` — fails closed with `PathValidationError`. No fail-open path found.
- **Exception handling in `path_security.py`**: every `try/except` re-raises as
  `PathValidationError` or lets one propagate; no branch swallows an error and returns a path
  anyway. Fail-closed throughout.
- **`validate_scan_path()` is dead code**: defined at `path_security.py:89-180` with full
  containment enforcement, zero callers repo-wide. Not a security bug, but its docstring/tests may
  mislead maintainers about what is actually enforced for scan directories.
- **`routers/files.py` upload endpoint**: multipart filename only used for `.suffix`/`.stem`;
  on-disk path is always `~/.auralis/uploads/<uuid4>.{ext}`. Magic-byte + extension + size checks
  present (#4349, #3494, #2415). Clean.
- **`routers/artwork.py` write path**: filename is `album_{album_id}_{content_hash}{ext}` — DB int,
  md5 hex digest, hardcoded ext. No user-controlled string reaches the filename. Clean.
- **`processing_api.py` `/api/processing/process`**: user-supplied `input_path`/`reference_path`
  validated via `validate_file_path()` (#2559); download endpoint validates `job.output_path`
  against system temp via `resolve()` + `relative_to()` (#2561). Clean.
- **WebSocket surfaces** (`ws_handlers/*.py`, `websocket_security.py`): no path/filename field is
  ever accepted over a WS message; the only filesystem path
  (`playback_commands.py:86-97`) is `track.filepath` resolved server-side from a DB `track_id`.
- **`library_auto_scanner.py`**: only scans `scan_folders` from settings, which already went
  through `validate_user_chosen_directory` + `register_allowed_directory`.
- **`POST /api/library/scan` (`library_scan.py`)**: appears unvalidated in the router, but
  `LibraryScanRequest.directories` (`schemas.py:170-189`) carries a Pydantic `field_validator`
  running `validate_user_chosen_directory()` on every entry. Note it does NOT call
  `register_allowed_directory`, so tracks scanned this way are subsequently *rejected* by
  `validate_file_path`-gated routes — a fail-closed functional inconsistency, not a finding.

## A02 — Cryptographic Failures / Secrets / Data at Rest

**Dimension status**: COMPLETE. 1 unique finding (LOW) + 1 independent corroboration of the
headline auto-update finding (see A08-1). Out of scope by threat model and explicitly *not* filed:
unencrypted loopback WS/HTTP, no-TLS-on-localhost, multi-user credential separation, at-rest
encryption of the music library.

### A02-1 — Desktop auto-updater has no code-signing / publisher-identity verification — **DUPLICATE of A08-1**

- **Severity**: MEDIUM as rated by A02; **CRITICAL/HIGH as rated by A08** — see A08-1 for the
  consolidated finding and final severity. The A02 and A08 dimension agents reached this finding
  **independently**, from different starting points (crypto/trust-root analysis vs. build-integrity
  analysis). That independent corroboration is itself signal.
- **Location**: `desktop/package.json:76-146` (build/publish config), `desktop/main.js:1-10,505-610`
  (electron-updater wiring), `.github/workflows/build-release.yml:399-423` (release creation)
- **A02's additional evidence, preserved verbatim** (complements A08-1's):
  ```
  desktop/package.json:99:      "hardenedRuntime": false,
  desktop/package.json:142-146:
      "publish": {
        "provider": "github",
        "owner": "matiaszanolli",
        "repo": "Auralis"
      }
  desktop/main.js:509-510:
  autoUpdater.autoDownload = false; // Ask user before downloading
  autoUpdater.autoInstallOnAppQuit = true;
  ```
  No `CSC_LINK`, `CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, or `notarize`
  reference exists anywhere in `.github/workflows/*.yml` or `desktop/package.json`.
- **A02's framing**: `electron-updater`'s own integrity check (comparing the downloaded file against
  the `sha512` embedded in `latest.yml`, which `electron-builder` generates in that same unsigned
  build job) provides only "did the bytes match what was uploaded," not "was this uploaded by the
  real publisher." The only things standing between a compromised/hijacked GitHub release and an
  end user's machine auto-installing a malicious binary are (a) TLS to github.com, (b) GitHub's own
  release-asset integrity, and (c) the human step of un-drafting a `draft: true` release. There is
  no independent cryptographic signature (Authenticode/Apple Developer ID) that Windows/macOS or
  `electron-updater` would use to reject a tampered binary.
- **A02's suggested fix (adds a fallback A08 does not spell out)**: If signing certificates are not
  yet available/affordable, at least **GPG-sign `SHA256SUMS.txt`** with a key whose fingerprint is
  published out-of-band (e.g. in the repo README), so users and the updater have a trust anchor
  independent of the same CI job that produced the binaries.

### A02-2 — `fetch_artwork.py` CLI bypasses the #4347 `~/.auralis` directory permission hardening

- **Severity**: LOW
- **Location**: `auralis/cli/fetch_artwork.py:151` (`LibraryDatabase(database_path=str(library_path))`),
  `auralis/library/database.py:94-101` (guard is `if database_path is None:`),
  `auralis/library/migration_manager.py:79-82` (`lock_file.parent.mkdir(parents=True, exist_ok=True)` — no `mode=`)
- **Status**: NEW (partial-coverage gap in the #4347 fix, **not** a full regression)
- **Description**: The `~/.auralis` parent-directory hardening added for #4347
  (`mkdir(..., mode=0o700)` + explicit re-`chmod(0o700)`) in `LibraryDatabase.__init__` only runs
  when the caller passes `database_path=None` (the normal GUI/backend startup path,
  `auralis-web/backend/config/startup.py:307: LibraryDatabase()`). The standalone
  `fetch_artwork.py` CLI **always** passes an explicit path — even without `--library-path` it
  resolves to `str(DEFAULT_DB_PATH)` and passes that string, which is not `None`. This skips the
  `if database_path is None:` block entirely.
  Meanwhile `check_and_migrate_database()` (called right after, at `database.py:110`) creates the
  same parent directory as a side effect via `migration_manager.py:82:
  lock_file.parent.mkdir(parents=True, exist_ok=True)` — with **no** `mode=` argument, i.e. default
  `0o777 & ~umask` (typically `0o755`, world-readable/executable).
  The main `library.db` and its `-wal`/`-shm` sidecars are still chmod'd `0o600` regardless, so DB
  contents stay protected. But if `~/.auralis` does not already exist and this CLI creates it first,
  the directory — and everything later written under it without its own chmod (fingerprint cache
  `~/.auralis/fingerprints/*.25d`, artwork cache, `~/.auralis/preferences/*`) — is
  listable/enterable by other local OS accounts.
- **Evidence**:
  ```python
  # auralis/cli/fetch_artwork.py:134-151
  if args.library_path:
      library_path = Path(args.library_path)
  else:
      from auralis.library.constants import DEFAULT_DB_PATH
      library_path = DEFAULT_DB_PATH
  ...
  library_db = LibraryDatabase(database_path=str(library_path))   # never None

  # auralis/library/database.py:94-101
  if database_path is None:                       # <-- skipped by the CLI above
      DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
      try:
          os.chmod(DEFAULT_DB_PATH.parent, 0o700)
      except OSError:
          pass
      database_path = str(DEFAULT_DB_PATH)

  # auralis/library/migration_manager.py:79-82 (runs regardless of the above)
  lock_file = db_path_obj.parent / f".{db_path_obj.name}.migration.lock"
  ...
  lock_file.parent.mkdir(parents=True, exist_ok=True)   # no mode= -> default umask
  ```
- **Exploit Scenario**: On a shared/multi-account Linux or macOS machine, a user's very first
  interaction with Auralis is running `python -m auralis.cli.fetch_artwork` before ever launching
  the GUI. `~/.auralis` does not yet exist; the migration lock's `mkdir` creates it at the process
  umask default (commonly `0o755`). No later code path in this CLI re-tightens it. Other local
  accounts can then `ls ~otheruser/.auralis/` and enter subdirectories that aren't themselves locked
  down — the exact class of exposure #4347 was meant to close, reached via a different entry point.
- **Impact**: Confidentiality of cached fingerprint/artwork/preference data (not the DB file, which
  stays `0o600`) on a multi-user machine, and only in the narrow "CLI-runs-before-GUI-ever-has"
  ordering. Once the GUI has run once, `~/.auralis` is `0o700` and `mkdir(exist_ok=True)` never
  widens it back. *(Note: multi-user machines are largely out of this threat model; recorded because
  it is a genuine coverage gap in a shipped fix, at the severity the model implies.)*
- **Siblings**: None — `fetch_artwork.py` is the only non-test call site constructing
  `LibraryDatabase()` with a non-`None` path.
- **Suggested Fix**: Move the parent-directory `mkdir(mode=0o700)` + `chmod(0o700)` hardening out of
  the `if database_path is None:` branch so it runs unconditionally on `Path(database_path).parent`
  before `check_and_migrate_database()` is invoked.

### A02 — Verification of prior CLOSED issues

- **#4346 "Committed legacy `.env` with placeholder secrets" — CONFIRMED STILL FIXED.**
  `git ls-files | grep -c '\.env'` → `0`. `.gitignore` covers `.env`, `.env.local`, and per-app
  variants. The file was added in `6547af83` (2025-09-14) and removed by `50e61481`
  ("chore: untrack the legacy Matchering .env (#4346)"). Its historical content
  (`git show 50e61481^:.env`) held only placeholders: `MATCHERING_SECRET_KEY=CHANGE_ME_GENERATE_A_RANDOM_KEY`,
  `MATCHERING_POSTGRES_PASSWORD=CHANGE_ME`, empty Redis password — leftover boilerplate from the
  ancestor Matchering project.
  **Caveat**: removal from HEAD does not remove it from git history; any full clone still contains
  the blob. Values are non-functional placeholders, so informational only — not re-opened.
- **#4347 "SQLite WAL/SHM sidecars not permission-restricted" — CONFIRMED STILL FIXED**, with the
  narrow coverage gap recorded as A02-2 above. `database.py:94-101` chmods `~/.auralis` to `0o700`
  when `database_path is None`; `136-142` chmods `library.db` to `0o600` unconditionally;
  `173-184` chmods both `-wal`/`-shm` sidecars to `0o600` after WAL mode is enabled.
- **#4385 "No authentication on the local REST/WebSocket API"** — documented baseline, confirmed
  unchanged (no auth middleware in `auralis-web/backend/`). Accepted-by-design for a loopback-only
  desktop app. Not re-filed.

### A02 — Third-party API credential handling (MusicBrainz / Discogs / Last.fm / iTunes)

- **Runtime app path** (`auralis-web/backend/services/artwork_downloader.py`): uses only the
  **keyless** iTunes Search API and Cover Art Archive — no API key of any kind is used, hardcoded,
  or stored. `User-Agent` is `Auralis/1.0 (https://github.com/matiaszanolli/Auralis)`.
- **Standalone CLI path**: Discogs token and Last.fm API key are optional, user-supplied `argparse`
  arguments — never hardcoded, committed, or persisted. Discogs token goes via the `Authorization`
  header (`artwork_service.py:191`, fixed under #2244 — verified still in place, not a URL param).
  Last.fm's key is a URL query parameter (`artwork_service.py:240`), unavoidable given Last.fm's API
  design and not a sensitive credential class (an app identifier for rate limiting). Not filed.
- No default/fallback API keys are baked into the shipped app for any of these services.

### A02 — Frontend bundle / client-side storage

- `import.meta.env.VITE_*` usage across `auralis-web/frontend/src/` is exactly three variables:
  `VITE_API_URL`, `VITE_WS_URL`, `VITE_COMMIT_ID` — connection URLs and build metadata only. No API
  keys, tokens, or credentials ship in the built bundle via this path.
- No `.env`/`.env.*` files exist for the frontend or `desktop/` at HEAD.
- `localStorage`/`sessionStorage`/`indexedDB`: theme preference (`ThemeContext.tsx`), a fingerprint
  analysis cache (`FingerprintCache.ts`, IndexedDB — DSP data), and a recently-touched-albums list
  (`useRecentlyTouched.ts`, IDs only). No paths, tokens, or credentials. No `document.cookie` usage
  found at all.

### A02 — Disproved hypotheses / examined and ruled out

- **All `hashlib.md5`/`sha1`/`sha256`/`blake2b` usages are non-security cache keys / dedup /
  change-detection, not integrity or authentication controls.** Confirmed by reading call sites:
  `sidecar_manager.py:334` (`compute_checksum`, cache invalidation only); `library/cache.py:73`,
  `core/chunk_cache.py:60`, `core/processor_factory.py:156,173`, `core/processor_pool.py:77` (MD5 of
  concatenated cache-key parts); `fingerprint_storage.py:76` (MD5 of `path:signature:strategy` as a
  cache filename); `library/artwork.py:306`, `services/artwork_downloader.py:346` (MD5 of artwork
  bytes for dedup); `core/file_signature.py:75,91,99`, `core/mastering_target_service.py:87`,
  `routers/artwork.py:160` (SHA1 cache keys); `scanner/audio_analyzer.py:104` (SHA256),
  `optimization/caching/smart_cache.py:66,107`, `services/audio_content_predictor.py:107`.
  **Do not re-file "MD5/SHA1 used" for any of the above** — weak-hash collision concerns do not
  apply to non-adversarial cache keys.
- **`random`/`uuid` usage is non-security**: `queue_manager.py:303` (`random.shuffle` for playback
  shuffle); `analysis/ml/genre_weights.py:43` (`np.random.default_rng` with a fixed seed, by design);
  `uuid.uuid4()` in `audio_stream_controller.py:141`, `processing_engine.py:181`, `routers/files.py:209`,
  `routers/processing_api.py:262`, `routers/similarity_common.py:39`, `routers/fingerprint_queue.py:82`
  — all job/stream IDs for same-machine tracking, not capability tokens. `uuid4()` is CSPRNG-backed
  regardless.
- **File-based logging**: no `logging.FileHandler`/`RotatingFileHandler`/`basicConfig(filename=...)`
  anywhere in `auralis/` or `auralis-web/backend/`. There is no app-owned log-file permission surface
  on the Python side. *(Contrast with A09-1 and A09-4, which cover the Electron `electron-log` file
  transport — a different logging path.)*
- **`~/.auralis/fingerprints/`, `artwork/`, `preferences/` are not individually `chmod`'d** — true
  (only `database.py` calls `chmod`), but ruled out as a standalone finding: POSIX traversal requires
  `+x` on every ancestor, and the parent `~/.auralis` is forced to `0o700` on every normal app
  startup (`config/startup.py:307`) before any fingerprint/artwork/preference work. This protection
  is nullified only via the CLI entry point in A02-2.
- **SQLite DB contents**: `auralis/library/models/*.py` contain no password/token/secret/api_key
  columns (explicitly grepped). Track rows store absolute filesystem paths and play history;
  informational only for a single-user app with the DB at `0o600`.
- **Settings repository** (`repositories/settings_repository.py`): `UserSettings` has no
  credential-like fields; no API key or auth token is ever persisted to the DB.
- **Full-tree `git grep` secret-pattern sweep**
  (`(api[_-]?key|secret|passwd|password|token|bearer|client[_-]?secret|private[_-]?key)\s*[:=]\s*["'][^"']{8,}`):
  the only hit outside test/doc files was a local variable named `token` in
  `.claude/commands/_audit-validate.sh:141` doing markdown-backtick stripping. Not a credential.
- **Credentials-in-URL sweep** (`user:pass@host`) over `desktop/main.js`, `preload.js`,
  `pyproject.toml`, `requirements.txt` — no hits.

## A03 — Injection

**Dimension status**: COMPLETE. 3 findings, all LOW under the desktop threat model.

**Subprocess enumeration (methodology step 1)** — all `subprocess`/`Popen` call sites in
application code (excluding vendored `desktop/node_modules` and PyInstaller `build/` artifacts):
- `auralis/io/unified_loader.py` (`_get_info_with_ffprobe`) — list-form argv,
  `ffprobe -v quiet -print_format json -show_format -show_streams <path>`
- `auralis/io/loaders/ffmpeg_loader.py` — `check_ffmpeg()`, `check_ffprobe()`, `_probe_audio()`,
  `load_with_ffmpeg()` — all list-form argv.
- **No `shell=True` anywhere** in the codebase outside `node_modules`. No `os.system`/`os.popen`
  anywhere in `auralis/`, `auralis-web/backend/`, `scripts/`, `desktop/` app code.
- **No `-filter_complex`/`-vf`/`-af`/`amovie=` FFmpeg filtergraph usage anywhere** — the
  filtergraph-metacharacter injection vector does not apply to this codebase; the only args built
  from the input path are plain `-i <path>` / trailing positional `<path>`.

### A03-1 — Untrusted filename passed as ffprobe's trailing positional argument (argument injection)

- **Severity**: LOW (no shell involved; single argv slot, so no value-consuming injection chain)
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:195-209` (`_probe_audio`),
  `auralis/io/unified_loader.py:209-223` (`_get_info_with_ffprobe`)
- **Status**: NEW
- **Description**: Both `ffprobe` invocations pass the file path as the last, bare positional
  argument with no `--` end-of-options marker:
  ```python
  ffprobe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                 '-show_format', '-show_streams', str(file_path)]
  ```
  If a filename begins with `-` (legal on Linux/macOS — only `/` and NUL are forbidden), `ffprobe`'s
  argv parser may interpret it as an option instead of the input path, since there is no flag
  immediately before it that unconditionally consumes the next argv. (Unlike
  `ffmpeg_loader.py:349` `'-i', file_path_str`, where `-i` always consumes the next token — that
  call site is **NOT** vulnerable to this.)
- **Evidence**: `ffprobe_cmd = [..., '-show_streams', str(file_path)]` — no `--` before the path in
  either file.
- **Exploit Scenario**: User opens a file literally named e.g. `-show_entries`. `ffprobe` may parse
  the filename as a flag, causing probe failure (handled gracefully via existing
  `result.returncode != 0` / `JSONDecodeError` paths) or subtly different probe output.
- **Impact**: Probe misbehavior/DoS for a single file the user themselves opened; not exploitable
  for code execution.
- **Suggested Fix**: Insert `'--'` before the path argument in both `ffprobe` command lists.

### A03-2 — Log injection via untrusted metadata/filenames — the #4363 fix covers only 4 files of many

- **Severity**: LOW (matches #4363's original severity; log-line forgery only, no RCE)
- **Location**: Many (see list). `auralis/utils/logging.py:24-47` defines `sanitize_log_value()`;
  only these files call it: `auralis/services/artwork_service.py`,
  `auralis-web/backend/routers/fingerprint_status.py`,
  `auralis-web/backend/services/artwork_downloader.py`, `auralis-web/backend/routers/files.py`.
- **Status**: Extends #4363. The #4363 fix is **verified present and correct at its original 4
  sites — NOT a regression**. This finding covers the call sites the original fix explicitly did not
  touch (per commit `761a6fee`: "Applied at all 14 sites across fingerprint_status.py, files.py,
  artwork_downloader.py, and artwork_service.py").
- **Description**: `sanitize_log_value()` is **not** a global logging hook —
  `debug()`/`info()`/`warning()`/`error()` in `auralis/utils/logging.py:104-125` do zero
  sanitization themselves; every call site must opt in individually. Dozens of call sites
  interpolate filenames, track titles, artist/album/playlist names, or tags directly into f-strings.
  Filenames on Linux/macOS may legally contain `\r`/`\n`/ANSI escapes; ID3/Vorbis tag values and
  playlist names are fully attacker-controlled strings from the user's own file collection.
- **Evidence** (representative, not exhaustive):
  - `auralis/io/loaders/ffmpeg_loader.py:330`: `debug(f"Converting {file_path} to WAV using FFmpeg")`
  - `auralis/io/unified_loader.py:64`: `debug(f"Loading {file_type} audio file: {file_path}")`
  - `auralis/io/saver.py:29,46`: `debug(f"Saving audio to: {file_path} ...")`, `info(f"Saved: {file_path} ...")`
  - `auralis/io/loader.py:57`: `debug(f"Loading {file_type} file: {file_path}")`
  - `auralis/services/fingerprint_extractor.py:83,144,235` — interpolates `filepath` raw
  - `auralis/analysis/fingerprint/fingerprint_service.py:150,156,162,169,209` — `audio_path.name` / `filepath` raw
  - `auralis/player/gapless_playback_engine.py:122,164,257,320,324,327` — `file_path` raw
  - `auralis/player/audio_file_manager.py:56,66,74,89,98,106` — `file_path` raw
  - `auralis/library/scanner/audio_analyzer.py:65,81,86`, `scanner/metadata_extractor.py:83`,
    `scanner/duplicate_detector.py:119`, `scanner/scanner.py:414` — `file_path` raw during scan
  - `auralis/player/queue_controller.py:124,141,153,185,260,263` —
    `track_info.get('title', ...)` / `playlist.name` raw (tag-controlled text, not filenames)
  - `auralis/library/repositories/playlist_repository.py:235,263,547` — `playlist.name` raw
  - `auralis/library/artwork.py:95,99` — `audio_filepath` raw
  - `auralis/analysis/mastering_fingerprint.py:139,237`, `analysis/fingerprint/normalizer.py:323,352`,
    `player/fingerprint_loader_mixin.py:97,105`, `services/fingerprint_queue.py:404,414,427`,
    `core/analysis/target_generator.py:161` — same pattern
  - Backend side (also unsanitized despite `sanitize_log_value` being importable there):
    `auralis-web/backend/core/mastering_target_service.py:178-277` (`filepath`),
    `services/audio_content_predictor.py:162-251` (`filepath`),
    `core/chunked_processor.py:589,707` (`chunk_path`/`full_path`),
    `core/streamlined_worker.py:405` (`track.filepath`),
    `analysis/fingerprint_generator.py:267,300` (`filepath`),
    `routers/artwork.py:252` (`album.artwork_path`)
- **Exploit Scenario**: User imports a music file whose filename or ID3 `TIT2`/`TPE1` tag contains
  `\r\nERROR: fake admin action performed\r\n` (or ANSI escapes). The next library scan, playback, or
  fingerprint pass logs it verbatim, forging a log line or corrupting a terminal log viewer. These
  are DEBUG/INFO paths hit on nearly every file load — a far larger surface than the
  artwork/upload paths #4363 closed.
- **Impact**: Log forgery / terminal corruption for anyone tailing Auralis logs
  (developer/support scenario). No code execution, no cross-user impact.
- **Siblings**: List above is not exhaustive — the grep was keyword-scoped to
  `file_path|filename|filepath|title|artist|album|tag|metadata|track\.|\.name`.
- **Suggested Fix**: Preferably (a) make `sanitize_log_value()` the default by wrapping the four log
  functions in `auralis/utils/logging.py`, closing the whole class centrally rather than relying on
  every call site opting in; or (b) apply it at each site above.

### A03-3 — FFmpeg protocol-prefix guard only checks `"://"`, missing colon-only protocols (`pipe:`, `concat:`, `data:`); second ffprobe call site has no guard at all

- **Severity**: LOW (requires a protocol-shaped filename to already exist and be readable by the
  same OS user; worst case is reading/decoding a second local file the user can already read)
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:268-275` (`load_with_ffmpeg`, the guard);
  `auralis/io/unified_loader.py:143-183` (`get_audio_info` → `_get_info_with_ffprobe`, **no guard at all**)
- **Status**: NEW
- **Description**: `load_with_ffmpeg` validates the input is a real file
  (`file_path.exists() and file_path.is_file()`) and then blocks only literal `"://"` substrings:
  ```python
  file_path_str = str(file_path)
  if "://" in file_path_str:
      raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: URL/protocol inputs are not allowed ({file_path_str})")
  ```
  The comment above it claims this guards "against ffmpeg protocol URLs (e.g., http://, pipe:,
  etc.)" — but several FFmpeg/libavformat protocols never contain `"://"`: `pipe:N` (reads from an
  already-open fd number), `concat:f1|f2|f3` (opens and concatenates several other files), and
  `data:` (RFC-2397 data URI, no filesystem access needed). Since Linux/macOS filenames may legally
  contain `:` and `|`, a file whose *literal on-disk name* is
  `concat:/home/user/.ssh/config|realtrack.mp3` would pass `is_file()` (it is a real single regular
  file with that exact name) and then be handed to `ffmpeg -i <that literal string>`, where
  **FFmpeg's own argument parser — not the OS** — splits it into a `concat:` protocol invocation
  over the two named sub-paths, each independently re-opened by FFmpeg.
  The second, independent ffprobe call site in `unified_loader.py::get_audio_info` →
  `_get_info_with_ffprobe` has **no protocol guard at all** (only `file_path.exists()`, no
  `is_file()`, no `"://"` check) — strictly worse than the path this guard was written for.
- **Evidence**: `auralis/io/loaders/ffmpeg_loader.py:272-275`; `auralis/io/unified_loader.py:200-223`
  (no guard before building `ffprobe_cmd`).
- **Exploit Scenario**: A user receives/downloads a file literally named
  `concat:/etc/passwd|song.mp3` (a legal filename) into a folder they add to their library, or an
  archive extraction / cloud-sync tool preserves such a name. The scanner or file-open flow calls
  `load_with_ffmpeg`/`get_audio_info`; the `"://"` check does not fire; FFmpeg reads/concatenates the
  referenced files. Both must already be readable by the same OS user, so no permission boundary is
  crossed — but it lets FFmpeg silently read a second file the *user did not intend to open*, giving
  an attacker who can plant one oddly-named file a way to make Auralis touch other files on disk
  without an explicit path-traversal string.
- **Impact**: Defense-gap / confused-deputy issue rather than privilege escalation. Worth closing
  because **the code's own comment claims protection it does not provide**.
- **Suggested Fix**: Replace the substring check with a generic prefix reject —
  `re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', file_path_str)` catches all `word:` prefixes rather than
  enumerating protocols. Apply the same guard in `_get_info_with_ffprobe`. More robust still: invoke
  FFmpeg with `-protocol_whitelist file` and always prefix the input with an explicit `file:`.

### A03 — Prior closed findings verified still fixed (no regression)

- **#4348** (`find_by_tag` LIKE pattern unescaped) — **STILL FIXED**.
  `repositories/queue_template_repository.py:157-159` (`get_by_tag`) escapes `\`, `%`, `_` in that
  order before building the LIKE pattern, with `escape='\\'` passed to `.like()`. Same pattern in
  `search_templates` (:344-351), `album_repository.py:143-149`, `artist_repository.py:150-172`,
  `genre_repository.py:290-292`, `track_repository.py:415-424` — all consistently escaped.
- **#4363** (log injection) — **STILL FIXED** at its original 4 files, confirmed via
  `git show 761a6fee`. See A03-2 for the untouched remainder of the class.
- **#4555** (mass-assignment on `/api/metadata/batch`) — **STILL FIXED**.
  `routers/metadata.py:56-74` — `BatchMetadataUpdateRequest.metadata` is typed as
  `MetadataUpdateRequest` (not `dict[str, Any]`), which has `model_config = {"extra": "forbid", ...}`
  (line 53), rejecting unknown keys with 422.

### A03 — Disproved hypotheses / examined and found clean

- **SQL injection**: All 14 repositories under `auralis/library/repositories/` use SQLAlchemy ORM
  `select()`/`delete()`/`insert()` (fully parameterized) or `text()` with bound `:name` placeholders.
  The only f-string-interpolated SQL (`fingerprint_repository.py:508,537-539,598,621-626` — column
  names in `INSERT`/`ON CONFLICT`) is protected by an explicit allowlist,
  `_validate_fingerprint_columns()` (lines 33-48), which raises `ValueError` on any column not in
  `_FINGERPRINT_WRITABLE_COLS` before the f-string is built — this was the #2286 fix, intact. No
  dynamic `IN (...)` construction, no raw cursor `.execute()` with interpolated values anywhere.
  `migration_manager.py`'s raw-SQL execution operates only on statements loaded from static,
  repo-bundled `.sql` files — not reachable from user/metadata input.
- **Unsafe deserialization**: No `pickle.loads`, `marshal.loads`, `yaml.load`, `eval()`, `exec()`,
  `__import__()`, or `jsonpickle` on untrusted input anywhere in `auralis/` or
  `auralis-web/backend/`. The one `pickle` hit (`optimization/parallel/band_processor.py:71-75`) is
  `pickle.dumps()` used only to check a callable is picklable before `ProcessPoolExecutor` submit —
  not deserialization. All on-disk caches (fingerprint `.25d` sidecars, chunk cache, settings) use
  `json.load`/`json.dump`.
- **Metadata write-back**: `library/metadata_editor/writers.py` writes tags exclusively through
  mutagen's structured frame API (`TIT2`, `TALB`, …) or dict-style Vorbis-comment assignment —
  values always passed as complete strings/ints into mutagen's own encoder, never string-concatenated
  into a raw tag blob. No injection vector into a later parse.
- **Metadata → frontend XSS**: No `dangerouslySetInnerHTML` anywhere in
  `auralis-web/frontend/src/`. The only production `innerHTML` write (`src/index.tsx:54`, a
  fatal-init-error fallback page) HTML-escapes both message and stack trace, and is not reachable
  from track metadata. No `eval()`/`new Function()`/`document.write()` in application code.
  `<img src={...}>` usages (`MediaCardArtwork.tsx`, `AlbumArtDisplay.tsx`, `TrackInfo.tsx`,
  `ArtistHeader.tsx`, `AlbumArt.tsx`) render artwork URLs, but `<img src>` does not execute
  `javascript:` URIs; no anchor (`<a href>`) renders metadata-derived URLs, so there is no
  `javascript:`-URI href vector either. *(A10-2 covers a separate concern with those same `<img src>`
  renders — arbitrary third-party URLs stored without validation.)*
- **Rust boundary** (`vendor/auralis-dsp/src/`, 6383 lines across all `.rs` files): **zero `unsafe`
  blocks anywhere in the crate** — no Python-supplied length/offset can reach raw/unchecked slice
  indexing, because there is none.
- **Glob patterns**: The one `Path.glob()` in library code (`library/artwork.py:331-333`) builds its
  pattern from an integer `album_id`, not string metadata. Not injectable.

## A04 — Insecure Design / Resource Exhaustion

<!-- PENDING -->

## A05 — Security Misconfiguration + Electron Hardening

<!-- PENDING -->

## A06 — Vulnerable and Outdated Components

<!-- PENDING -->

## A07 — Identification & Authentication Failures

<!-- PENDING -->

## A08 — Software & Data Integrity Failures

<!-- PENDING -->

## A09 — Security Logging & Monitoring Failures

<!-- PENDING -->

## A10 — SSRF / Outbound Network Surface

<!-- PENDING -->

---

## Coverage and Caveats

Each dimension agent reported its own coverage independently. **Areas listed as "not reached" were
not examined and must NOT be read as audited-and-clean.**

### A01 — Broken Access Control

**Examined**: `auralis-web/backend/security/path_security.py` (full); `config/routes.py`;
routers `files.py`, `artwork.py`, `metadata.py`, `tracks.py`, `settings.py`, `processing_api.py`,
`enhancement.py`, `player.py`, `library.py`, `library_scan.py`; `schemas.py`
(`LibraryScanRequest`, `ProcessRequest`); `core/stream_normal.py`, `stream_seek.py`,
`stream_enhanced.py`, `chunked_processor.py`, `audio_stream_controller.py`; `ws_handlers/`
(`connection.py`, `context.py`, `messages.py`, `playback_commands.py`, `playback_control.py`);
`websocket/websocket_security.py` (full); `auralis/library/scanner/file_discovery.py` (full),
`scanner.py` (first ~200 lines), `config.py`; `auralis/library/sidecar_manager.py` (full);
`auralis/library/artwork.py`; `auralis/services/artwork_service.py` (grepped);
`services/library_auto_scanner.py`; `auralis/player/enhanced_audio_player.py`
(`load_track_from_library`, `next_track`); prior audit + `issue_titles.txt` dedup pass.

**NOT reached**: `auralis/player/integration_manager.py` beyond `load_track_from_library`;
`core/stream_fingerprint.py` (assumed, not verified, to follow the sibling `track_id`→DB pattern);
`repositories/track_repository.py` beyond `add()` — **not ruled out with certainty** whether some
route lets a client supply an arbitrary filepath directly into a DB insert; `routers/library.py`
beyond admin/reset endpoints; routers `playlists.py`, `albums.py`, `artists.py`, `system.py`,
`health.py`, `cache_streamlined.py`, `fingerprint_queue.py`, `fingerprint_status.py`,
`similarity*.py`, `pagination.py`, `serializers.py`, `dependencies.py`, `errors.py` — **not
examined at all**; Rust/PyO3 DSP layer; frontend (only the `/api/library/scan` call site);
Electron wrapper (whether the main process exposes additional filesystem-touching IPC outside the
FastAPI backend).

### A02 — Cryptographic Failures / Secrets / Data at Rest

**Examined**: `git ls-files`, `git log --all --diff-filter=D/A -- '*.env' '*secret*' '*.pem' '*.key'`,
`git show` on the historical `.env` blob, `.gitignore`; `auralis/library/database.py`
(`LibraryDatabase.__init__`, ~85-260); `migration_manager.py` (~75-90, ~440-450);
`auralis/cli/fetch_artwork.py` (full); `auralis/services/artwork_service.py` (Discogs/Last.fm auth);
`services/artwork_downloader.py`, `routers/artwork.py`; `fingerprint_storage.py`,
`learning/preference_engine.py`, `library/constants.py` (all `~/.auralis` subdir creation sites);
all hashlib/uuid/random usage sites listed above; `auralis/utils/logging.py`;
`repositories/settings_repository.py`, `auralis/library/models/`; frontend grep for `VITE_*`,
`localStorage`, `sessionStorage`, `indexedDB`, `document.cookie` plus `ThemeContext.tsx`,
`useRecentlyTouched.ts`, `FingerprintCache.ts`, `vite.config.mts`; `desktop/package.json` (full),
`desktop/main.js` (~1-10, ~505-610), `desktop/preload.js`;
`.github/workflows/build-release.yml` (full, 433 lines); full-tree secret-pattern and
credentials-in-URL sweeps; prior audit + `issue_titles.txt` dedup.

**NOT reached**: Rust DSP crate (`vendor/auralis-dsp/`) — not examined for crypto/secrets;
the ~110 repository call sites for session handling (only settings/models schema checked for
credential columns); **CI secrets actually configured in GitHub repo Settings — cannot be inspected
from a local checkout**, so A02-1/A08-1 rest on the absence of any signing-secret *reference* in
workflow YAML, which is the strongest available in-repo signal but is not proof the secrets store is
empty; `flatpak`/`deb` post-install scripts and electron-builder `afterPack` hooks for
`~/.auralis` permission behavior — not enumerated beyond `package.json`; `tests/security/` test
files — deliberately not read (this is an audit of the app, not of its test suite).

### A03 — Injection

**Examined**: `auralis/io/unified_loader.py`, `loader.py`, `loaders/ffmpeg_loader.py`,
`loaders/soundfile_loader.py` (referenced), `saver.py`; **all 14 repositories** under
`auralis/library/repositories/` plus `base.py`, `factory.py`; `library/database.py`,
`migration_manager.py`, `migrations/normalize_existing_artists.py`, `migrations/*.sql`;
`library/metadata_editor/` (`writers.py`, `metadata_editor.py`, `readers.py`, `tag_mappings.py`,
`factory.py`, `backup.py`, `models.py`); `library/sidecar_manager.py`, `library/artwork.py`;
`auralis/utils/logging.py` (full); `optimization/parallel/band_processor.py` (pickle usage);
`backend/routers/metadata.py` (#4555 verification); frontend full-tree greps for
`dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`, `document.write`, `href=`, `src={`
plus `src/index.tsx` read in full; `vendor/auralis-dsp/src/` full-tree `unsafe` grep; full-repo
greps (excluding `node_modules` / PyInstaller `build/`) for
`subprocess|Popen|os.system|shell=True|os.popen`, `text(|execute(|f"SELECT|f"INSERT|% (|.format(`,
`pickle|marshal|yaml.load|eval(|exec(|__import__|jsonpickle`,
`.like(|ilike(|LIKE |contains(`, `joblib`, `np.load|allow_pickle`; dedup against
`issue_titles.txt` (400 titles) and `git show 761a6fee`.

**NOT reached**: `auralis/library/scanner/`, `services/fingerprint_extractor.py`,
`fingerprint_service.py`, `fingerprint_queue.py`, `player/*`,
`analysis/fingerprint/normalizer.py`, `analysis/mastering_fingerprint.py`,
`core/analysis/target_generator.py` — **grep-surfaced for A03-2 only, not read end-to-end** for
other injection classes; `backend/routers/` beyond `metadata.py` — not read line-by-line, coverage
there rests on repo-wide keyword greps which would miss anything not matching those shapes;
`backend/cache/`, `backend/core/chunk_cache_manager.py` and sibling chunk-cache files — located,
grep-confirmed to use `json` not `pickle`/`yaml`, but not read in full; manual read of
`vendor/auralis-dsp/src/*.rs` — not performed (relied on the zero-hit `unsafe` grep); safe-Rust
panic-as-DoS from Python-supplied lengths deliberately not reviewed (out of A03 scope);
`desktop/` Electron main-process code — **not audited in this dimension** (covered by A05);
`scripts/` developer tooling — surfaced by the subprocess grep, not individually read.


---

## A04 — Insecure Design / Resource Exhaustion by Malicious Input

Scope: crafted/malformed FILE opened or added by the user to a single-user desktop Electron app (Auralis), binding 127.0.0.1:8765.
Out of scope: remote DoS / rate limiting as anti-abuse, multi-tenant concerns, path traversal (A01), CORS/rate-limit keying (A07).

Status: IN PROGRESS — findings appended as confirmed.

---

### A04-1: Fingerprint worker has no per-file timeout — a pathological file permanently wedges a worker slot
- **Severity**: MEDIUM
- **OWASP Category**: A04
- **Location**: `auralis/services/fingerprint_queue.py:378-439` (`_process_track`), calling `auralis/services/fingerprint_extractor.py:92` (`extract_and_store`)
- **Status**: NEW (related to, but not fixed by, the CLOSED #4377)
- **Description**: `FingerprintExtractionQueue._process_track()` acquires a `ResizableSemaphore` slot and then calls `self.extractor.extract_and_store(track.id, track.filepath)` synchronously inside a plain `threading.Thread` worker loop, with **no timeout of any kind** — no `asyncio.wait_for`, no thread-join deadline, no watchdog. The semaphore release and stats bookkeeping live in a `finally:` block that only executes once `extract_and_store` returns or raises; if the DSP analysis inside it hangs (an unbounded loop, a pathological numerical edge case, a native/Rust call that never returns), the worker thread — and the semaphore slot it holds — is wedged **for the lifetime of the process**. This is the exact behavior #4377's own docstring described ("hung DSP thread not reclaimable on timeout"), but the commit that closed #4377 (`dda5c3ae`) only corrected the docstring text to match reality — it added no timeout, watchdog, or process isolation. The underlying resource-exhaustion gap it documents was never remediated.
- **Evidence**:
  ```python
  # fingerprint_queue.py:391-395
  self.processing_semaphore.acquire()
  ...
  try:
      success = self.extractor.extract_and_store(track.id, track.filepath)
  ...
  finally:
      ...
      self.processing_semaphore.release()   # never reached if extract_and_store hangs
  ```
  Contrast with the streaming path (`auralis-web/backend/core/stream_chunk_ops.py:110-122`), which *does* bound per-chunk DSP with `asyncio.wait_for(..., timeout=_asc.CHUNK_PROCESS_TIMEOUT)` (30s, `audio_stream_controller.py:130`) specifically to prevent this class of hang (#3852) — the fingerprint worker pool has no equivalent.
- **Exploit Scenario**: User adds N crafted/pathological audio files to their library (N ≈ `num_workers`, default `max(4, cpu_count*0.5)`, so as few as 4 files on a 4-8 core machine). Each file's fingerprint analysis hangs the analyzing worker thread forever. Once all worker threads are wedged this way, fingerprinting is permanently starved for the rest of the process's life (only a full app restart recovers it) — every other track added afterward never gets fingerprinted, silently degrading similarity/recommendation features.
- **Impact**: Availability of the fingerprinting subsystem (not the whole backend/UI) — permanent (until restart) loss of background fingerprinting throughput; does not itself OOM or crash the process, but is an unbounded-hang DoS confined to N worker threads.
- **Siblings**: None found with the identical pattern elsewhere in the codebase — other CPU-bound file-driven paths (chunk DSP, FFmpeg conversion) do have timeouts (`CHUNK_PROCESS_TIMEOUT`, 300s FFmpeg subprocess timeout in `ffmpeg_loader.py:368`).
- **Suggested Fix**: Wrap `extract_and_store` in a bounded execution (e.g. run it via `concurrent.futures.ThreadPoolExecutor.submit(...).result(timeout=...)` or a `ProcessPoolExecutor` so a genuinely hung call can be killed rather than merely abandoned) and treat a timeout as a per-track failure (mark `stats['failed']`, release the semaphore, continue) instead of leaking the worker.

---

### A04-2: `StreamlinedCacheAdapter._temp_chunk_cache` is an unbounded, never-evicted dict backed by un-cleaned temp WAV files
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/cache/adapter.py:71` (`self._temp_chunk_cache`), `:117-176` (`get`/`put`)
- **Status**: NEW (but currently unreachable — see caveat below)
- **Description**: `StreamlinedCacheAdapter.put()` unconditionally writes every processed chunk into `self._temp_chunk_cache[cache_key] = (audio, sample_rate)` — a plain `dict` with no size cap, no LRU, and no `.clear()` call anywhere in the class except a manual `clear()` method that nothing invokes automatically. Every distinct `(track_id, chunk_idx, preset, intensity)` combination played in a session grows this dict forever (each entry a full decoded chunk `np.ndarray`, several MB). `put()` also writes a same-named WAV file into `Path(tempfile.gettempdir()) / "auralis_cache_adapter"` with no matching cleanup/prune logic in this file (unlike the real chunk pipeline's `ChunkCacheManager.prune_chunk_directory`, `core/chunk_cache_manager.py:266`, which caps `/tmp/auralis_chunks` at 512 MB).
- **Evidence**:
  ```python
  # cache/adapter.py:174-176
  cache_key = f"{track_id}_{chunk_idx}_{preset}_{intensity:.2f}"
  self._temp_chunk_cache[cache_key] = (audio, sample_rate)
  ```
  No eviction path exists for this dict or for `temp_dir / f"chunk_{track_id}_{chunk_idx}_{preset}_{intensity:.2f}.wav"` (`adapter.py:152`).
- **Caveat / why LOW not MEDIUM**: `StreamlinedCacheAdapter` is exported from `cache/__init__.py` but **never instantiated** anywhere in the backend or tests (`grep -rn "StreamlinedCacheAdapter(" auralis-web/backend/` and `tests/` both return nothing). `AudioStreamController.cache_manager` (`core/audio_stream_controller.py:183`) is always either the injected `StreamlinedCacheManager` singleton or `SimpleChunkCache()` — never this adapter. This appears to be dead/orphaned code from an earlier cache-refactor generation, not a live code path, so it is not currently exploitable via any file the user opens.
- **Exploit Scenario**: Not currently reachable. Would become exploitable only if a future change wires `StreamlinedCacheAdapter` back into the live `cache_manager` slot.
- **Impact**: None currently (dead code). If ever wired in: unbounded RAM growth over a long listening session, plus orphaned WAV files accumulating in the OS temp directory (which is tmpfs/RAM-backed on many Linux setups, compounding the RAM impact).
- **Siblings**: None — `SimpleChunkCache` (`core/chunk_cache.py`) and `StreamlinedCacheManager` (`cache/manager.py`) both have real LRU/size bounds; this adapter is the outlier.
- **Suggested Fix**: Either delete `StreamlinedCacheAdapter` as dead code (simplest — matches the project's "no variants" principle), or if it is meant to be kept as a fallback path, bound `_temp_chunk_cache` the same way `SimpleChunkCache` bounds itself (max entries + max bytes, LRU eviction) and unlink the temp WAV file when its dict entry is evicted.

---

## Verified — Examined, Not Vulnerable (or Prior Fix Confirmed Still Present)

These were checked against the in-scope threat model and disproven as findings; documented so nobody re-audits from scratch.

- **#4342 (CLOSED) — `chunk_idx` bound on chunk streaming**: Still enforced, and now redundantly so at two layers.
  `auralis-web/backend/core/chunk_boundaries.py:99-108` (`chunk_for_position`) clamps `index = max(0, min(index, total_chunks - 1))` before any seek ever picks a chunk index from a client-supplied position. `auralis-web/backend/core/chunked_processor.py:731` additionally raises if `chunk_index < 0 or chunk_index >= self.total_chunks` inside the processor itself. No regression.
- **#4349 (CLOSED) — multipart upload file-count cap**: Still enforced. `auralis-web/backend/config/limits.py:14` sets `MAX_UPLOAD_FILES = 200`; `MAX_UPLOAD_BYTES = 500 * 1024 * 1024` (500 MB) sits alongside it as the single source of truth. No regression.
- **#4554 (CLOSED) — `GET /api/playlists` pagination**: Still enforced. `auralis-web/backend/routers/playlists.py:91` — `limit: int = Query(50, ge=1, le=200, ...)`. `albums.py:45`, `artists.py:116`, `tracks.py:41,73` all carry the same `le=200` cap via the shared `PaginationParams` convention (`routers/pagination.py:95-120`, `MAX_LIMIT = 200`). No unbounded list endpoint found in `routers/library.py` (it exposes only `stats`/`refresh`/`reset`, no listing). Bulk/administrative endpoints that intentionally allow larger pages are still explicitly capped: `fingerprint_queue.py:136` (`le=10000`), `processing_api.py:388` (`le=1000`).
- **Audio load path (`auralis/io/loaders/soundfile_loader.py`, `ffmpeg_loader.py`, `unified_loader.py`)**: A header-declared duration is checked **before** the full buffer is decoded, on both loaders (`soundfile_loader.py:67-78` via `sf.info()`; `ffmpeg_loader.py:291-313`, including a file-size/bitrate-based lower-bound estimate when ffprobe reports no duration at all, #4128). `MAX_DURATION_SECONDS` (`auralis/io/loader.py:35-39`, default 7200s, env-overridable) is the single source of truth for both. `unified_loader.load_audio()`'s post-decode duration check (`unified_loader.py:93-105`) is a documented backstop for direct callers, not the primary gate. Sample-rate/channel count are not independently capped, but total allocated memory for a legitimate file is bounded by the file's actual on-disk PCM byte count (not amplified by a spoofed header field), so this was not filed as a separate finding.
- **Chunked processing edge cases**: `content_chunk_count()` (`chunk_boundaries.py:25-37`) uses `max(1, ...)`, so a zero-length or sub-chunk-length file always yields `total_chunks >= 1` — no division-by-zero or negative-range crash. `unified_loader.py:99` guards `sample_rate` division with `max(sample_rate, 1)`.
- **On-disk chunk cache size**: The real chunk-file directory (`/tmp/auralis_chunks`, written by `ChunkedAudioProcessor`) is bounded by `ChunkCacheManager.prune_chunk_directory` (`core/chunk_cache_manager.py:29-33,266-310`, `MAX_CHUNK_DISK_BYTES = 512 MB`, reaper runs every 32 writes) and the whole directory is wiped on every backend startup (`config/startup.py:266-274`). In-memory chunk cache (`SimpleChunkCache`, `core/chunk_cache.py`) is bounded on both entry count and byte size with real LRU eviction (`chunk_cache.py:123-131`). The separate `StreamlinedCacheManager` (`cache/manager.py`) tier1/tier2 dicts evict entries without unlinking the referenced file (`_evict_tier1_lru`/`_evict_tier2_lru`, `cache/manager.py:388-430`), but the physical directory-wide byte cap above is independent of that bookkeeping and is what actually bounds disk usage — not filed as a finding, though the two overlapping cache-tracking systems are a maintainability concern worth a non-security follow-up.
- **Fingerprinting concurrency/queue design**: `FingerprintExtractionQueue` deliberately has no in-memory job queue — workers pull the next unfingerprinted track directly from the database (`auralis/services/fingerprint_queue.py:5-18`), so there is no unbounded pending-list accumulation. Concurrent audio decode is capped by `ResizableSemaphore` (`auralis/services/resizable_semaphore.py`). The one real gap found is the missing per-file timeout (A04-1 above).
- **Library scanner**: `FileDiscovery` (`auralis/library/scanner/file_discovery.py`) is fully generator-based (no path list materialized for the main scan path), tracks visited `(st_dev, st_ino)` pairs to detect and skip symlink cycles (`:149-152`), and enforces `MAX_SCAN_DEPTH = 50` (`:19,124-126`). `scanner.py`'s main `scan_directories()` path processes discovered files in bounded streaming batches (`#2160`, `scanner.py:222-270`). `LibraryScanner.scan_folder()` (`scanner.py:324-359`) *does* materialize a full `list[dict]` with per-file metadata extraction for an entire folder, but it has no callers in production code (`grep -rn "scan_folder("` outside test files returns nothing) — it exists only for backward-compat test expectations, not reachable from any user-facing endpoint, so not filed as a finding.
- **Artwork/image decode**: Embedded/folder artwork is bounded to `_MAX_ARTWORK_DIMENSION = 2048` px at ingestion time (`auralis/library/artwork.py:27,244-275`, all `_save_artwork` callers route through `_bound_dimensions`), and the on-demand thumbnail endpoint bounds requested sizes to a fixed bucket set (`auralis-web/backend/routers/artwork.py:38-46`, `_THUMB_BUCKETS`). No code sets `PIL.Image.MAX_IMAGE_PIXELS = None` anywhere (`grep -rn "MAX_IMAGE_PIXELS"` returns no hits), so Pillow's own default decompression-bomb guard (~89M-pixel warning threshold, ~178M-pixel hard error) is intact and unmodified.
- **Player queue / index safety**: `QueueManager` (`auralis/player/components/queue_manager.py`) gates every index-based access with `0 <= index < len(self.tracks)` (`remove_track`/`_remove_track_unlocked`, `set_track_by_index`, `_get_current_track_unlocked`) — no `IndexError` is reachable via `next_track`/`previous_track`/`remove_track`/`reorder_tracks`/`shuffle` with adversarial indices; invalid indices return `False`/`None` instead of raising. No hard cap on total queue length was found, but growing the queue requires the user's own repeated action (not a hostile file), so this was treated as out of the file-driven threat model and not filed.
- **Unhandled-crash surface**: A global `Exception` handler is registered (`auralis-web/backend/config/app.py:81-82`) returning a JSON 500 instead of crashing the ASGI worker; `HTTPException`/`RequestValidationError` have their own handlers too. The WS `/ws` endpoint (`routers/system.py:297-358`) wraps its body in `try/except Exception`. The background job worker (`core/job_worker.py`) isolates each job in its own fire-and-forget task (`spawn_background_task`, `:209-216`) with a done-callback that logs unhandled exceptions rather than letting them escape, and the job queue itself is a bounded `asyncio.Queue(maxsize=max_queue_size)` (`:51`) with semaphore-limited concurrency (`:56`).

---

## Summary

2 findings filed:
- A04-1 (MEDIUM, NEW): No per-file timeout on fingerprint extraction — a pathological file wedges a worker thread and its semaphore slot permanently.
- A04-2 (LOW, NEW but currently dead code): `StreamlinedCacheAdapter._temp_chunk_cache` unbounded dict + un-cleaned temp WAV files — not reachable from any live code path today.

3 prior CLOSED issues re-verified as still fixed, no regressions: #4342 (chunk_idx bound), #4349 (upload file-count cap), #4554 (playlists pagination).

The audio-load path, chunked-processing bounds, artwork decode bounds, library scanner recursion/symlink safety, queue index safety, pagination limits, and top-level crash containment were all examined in depth and found sound against this threat model — see "Verified — Examined, Not Vulnerable" above for the specific evidence per area.

---

## A05 — Security Misconfiguration + Electron Hardening

**Status**: COMPLETE
**Scope**: Electron main/preload, backend bind/startup, CSP/security headers, rate/size limits, error shape, temp files, secrets, CI config.

---

## Backend bind / startup / limits / errors — verified clean (no new findings)

- **Bind address**: `auralis-web/backend/main.py:237` — `uvicorn.run(..., host="127.0.0.1", ...)`. Repo-wide grep for `0.0.0.0` across `auralis-web/backend/`, `auralis/`, `launch-auralis-web.py` returned **zero hits**. Loopback-only, confirmed.
- **`--dev` deltas**: `auralis-web/backend/config/app.py:50-52` — `docs_url`/`redoc_url`/`openapi_url` are all `None` unless `is_dev` is true; this correctly extends to `openapi_url` (the #4375 fix — "docs disabled but /openapi.json still served" — remains in place; only reachable with `--dev`).
- **Size/upload limits**: `auralis-web/backend/config/limits.py` defines `MAX_UPLOAD_BYTES` (500 MB) and `MAX_UPLOAD_FILES` (200) as single-source constants; both are actually enforced at every call site (`routers/files.py:130,166-167`, `routers/processing_api.py:241-242`) by reading `+1` byte over the cap before buffering the full body — matches the #3494/#2560 fix descriptions, not regressed.
- **Error shape**: `auralis-web/backend/routers/errors.py` — `InternalServerError`/`handle_query_error` log `str(error)` server-side only (`exc_info=True`) and always return a fixed, generic `detail` string to the client; no `str(exc)` leaks into any 500 response body here. Elsewhere (`routers/player.py`, `routers/settings.py`) there are ~17 call sites of `detail=str(e)`, but in every sampled case (`player.py:344-345,618-619,643-645,656-657,668-669,679-682`) the `except ValueError as e` is a narrowly-scoped, application-level validation message (e.g. "Invalid index", "Track not found") produced by the service layer itself, not a raw internal/library exception — no absolute paths or stack frames observed in the sampled sites. Not filed as a finding; flagged here only as "examined, not obviously the same class as the two already-known leaks (`ModuleError`, `PathValidationError`)."
- **Secrets**: `.env` at repo root exists on disk but is **not tracked** (`git ls-files` has no `.env` match) and is `.gitignore`d (`.gitignore:126`); `git log --all -- .env` shows `50e61481 chore: untrack the legacy Matchering .env (#4346)` — the fix holds, no regression. `git ls-files | grep -iE "\.env|secret|credential|\.pem$|\.key$|token"` otherwise only matches legitimate design-token source files (`tokens.ts`, `FIGMA_TOKENS_EXPORT.json`, etc.) — no committed secrets found.

## CSP / Security Headers (`auralis-web/backend/config/middleware.py`)

### A05-5: CSP `script-src`/`style-src` include `'unsafe-inline'`
- **Severity**: MEDIUM
- **OWASP Category**: A05
- **Location**: `auralis-web/backend/config/middleware.py:122-130`
- **Status**: Likely duplicate of historical **#3900** ("CSP allows `'unsafe-inline'` for script/style-src (also whitelists Google Fonts + broad localhost `connect-src`)"), cited as OPEN in `docs/audits/AUDIT_SECURITY_2026-07-12.md:301`. **Not verifiable via the current dedup list** — `#3900` does not appear anywhere in `/tmp/audit/security/issue_titles.txt` (the current 400-issue snapshot), so I cannot confirm whether it is still open, was closed-and-purged from the list, or was renumbered. Filing findings below as the current, code-verified state; flag for reconciliation against #3900 rather than treating as confirmed-new.
- **Description**: The `Content-Security-Policy` header sets `script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com`. `'unsafe-inline'` on `script-src` defeats CSP's primary purpose as an XSS mitigation: it permits any injected `<script>` tag or inline event handler to execute, regardless of origin restriction. Given this app's own threat model explicitly treats "renderer XSS + weak isolation = local RCE" as in-scope (because a successful XSS combined with the `shell.openExternal` sink in A05-1 is a plausible local-RCE chain), a CSP that does not actually block inline script execution removes the one remaining browser-side backstop between a hypothetical stored/reflected XSS (e.g. via unsanitized track/artist/album metadata rendered in the UI — not confirmed present, but not ruled out either) and that RCE chain.
- **Evidence**:
  ```python
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self' 'unsafe-inline'; "
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
      "font-src 'self' https://fonts.gstatic.com; "
      f"img-src {img_src}; "
      "connect-src 'self' ws://localhost:* http://localhost:*; "
      "media-src 'self' blob:;"
  )
  ```
- **Exploit Scenario**: Attacker gets a payload into rendered content that reaches the DOM without React's default escaping (e.g. a `dangerouslySetInnerHTML` sink, or a raw HTML preview of ID3/Vorbis comment metadata from a crafted audio file added to the library — not confirmed present in this pass, listed as a hypothesis consistent with the "malicious-file/crafted-metadata" vector this threat model keeps in scope). With `'unsafe-inline'` allowed, the injected `<script>` executes with no CSP intervention, and can then drive `window.open('someuri:...')`/`<a target=_blank>` into the unchecked `shell.openExternal` sink (A05-1).
- **Impact**: Removes CSP as an XSS mitigation for script execution; downstream impact is contingent on an actual injection point existing (not confirmed in this pass).
- **Siblings**: `style-src 'unsafe-inline'` has the same category of weakening for CSS-based exfiltration/attribute-injection techniques, lower severity than the script-src instance.
- **Suggested Fix**: Move to a nonce- or hash-based CSP for any inline `<script>`/`<style>` that's actually required (Vite's build can emit hashes), or eliminate the inline usage entirely, before removing `'unsafe-inline'`.

### Verified clean / already-tracked (CSP)
- `connect-src` allows only `ws://localhost:*` and `http://localhost:*` (not `127.0.0.1`) — this is the known, already-tracked mismatch in **#4712 (OPEN)**, not re-filed per instructions.
- `img-src` whitelist for artist artwork hosts (`_ARTIST_ARTWORK_IMG_HOSTS`) is deliberate and documented in-code (`middleware.py:90-102`) as an accepted interim tradeoff pending #4526 (already CLOSED per the dedup list) — not re-filed.
- The frontend's `auralis-web/frontend/index.html` has **no** `<meta http-equiv="Content-Security-Policy">` tag of its own (confirmed by direct read) — the CSP is delivered solely via the `SecurityHeadersMiddleware` response header, so it applies whenever the Electron renderer loads pages served by the FastAPI backend (production: `http://localhost:8765`). In development (`--dev`, renderer loads `http://localhost:3000` from the separate Vite dev server), this backend-only CSP header does **not** apply at all — Vite's dev server does not run this middleware. This is a real coverage gap but is a `--dev`-only condition (developer machine, not the shipped app), so it is noted here rather than filed as its own finding, consistent with the "IN SCOPE... `--dev` flag security deltas" instruction to at least document the delta.
- `index.html` also loads two external stylesheet resources unconditionally on every launch (`https://fonts.googleapis.com/css2?...`, `https://fonts.googleapis.com/icon?family=Material+Icons`) plus two `preconnect` hints to `fonts.googleapis.com`/`fonts.gstatic.com` (`index.html:14-25`). This is consistent with (and is exactly why) `style-src`/`font-src` had to whitelist those two hosts — flagged as context for A05-5, not a separate finding (network calls to a fixed, non-attacker-controlled Google CDN are a privacy/offline-capability note for a desktop app, not a misconfiguration).

## Temp files, symlink races, and file/directory permissions

### A05-6: Predictable, fixed-name working directories created under the shared system temp dir with default (world-readable) permissions
- **Severity**: MEDIUM
- **OWASP Category**: A05
- **Location**:
  - `auralis-web/backend/core/chunked_processor.py:171-172` — `self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"` / `self.chunk_dir.mkdir(exist_ok=True)`
  - `auralis-web/backend/core/processing_engine.py:126-127` — `self.temp_dir: Path = Path(tempfile.gettempdir()) / "auralis_processing"` / `self.temp_dir.mkdir(exist_ok=True)`
  - `auralis-web/backend/core/processing_engine.py:648` and `auralis-web/backend/routers/processing_api.py:237` — `Path(tempfile.gettempdir()) / "auralis_uploads"` / `.mkdir(exist_ok=True)`
  - `auralis-web/backend/cache/adapter.py:149-150` — `Path(tempfile.gettempdir()) / "auralis_cache_adapter"` / `.mkdir(parents=True, exist_ok=True)`
  - Also recreated at startup: `auralis-web/backend/config/startup.py:267-270` (`shutil.rmtree` + re-`mkdir` of `auralis_chunks` on every launch)
- **Status**: NEW
- **Description**: Five separate working directories are created with fixed, predictable names directly under the OS-shared temp root (`tempfile.gettempdir()`, i.e. `/tmp` on Linux) using plain `Path.mkdir(exist_ok=True)` with no explicit `mode=` argument. Verified empirically in this environment: an `os.makedirs(path, exist_ok=True)` call with no `mode=` under the current umask (`002`) yields `0o775`; under the far more common Linux default umask `022` it yields `0o755` — in both cases **world-readable and world-executable** (any other local OS account can `ls` the directory and see every filename in it). `exist_ok=True` also means the call **silently succeeds if the path already exists** — including if it exists as a **symlink to an existing directory** planted by another local process/account before the app runs. Contrast: the library DB directory does this correctly — `auralis/library/database.py:99` explicitly `os.chmod(DEFAULT_DB_PATH.parent, 0o700)` (and `0o600` on the DB file/sidecar, lines 140/182) — so the pattern for locking down a data directory exists in this codebase, it just wasn't applied to these five temp working directories.
- **Evidence**:
  ```python
  # chunked_processor.py:171-172
  self.chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
  self.chunk_dir.mkdir(exist_ok=True)
  ```
  ```python
  # database.py:99 (contrast — done correctly elsewhere in the same codebase)
  os.chmod(DEFAULT_DB_PATH.parent, 0o700)
  ```
  Empirical confirmation of default `mkdir` mode in this environment:
  ```
  $ umask
  002
  $ python3 -c "import os,tempfile; d=os.path.join(tempfile.gettempdir(),'_t'); os.makedirs(d,exist_ok=True); print(oct(os.stat(d).st_mode & 0o777))"
  0o775
  ```
- **Exploit Scenario** (two sub-cases, consistent with the "co-resident-local-process" vector this threat model keeps in scope):
  1. **Metadata/privacy leak (low effort)**: any other local account (or sandboxed/unrelated process running as the same account) can simply `ls /tmp/auralis_chunks/` or `/tmp/auralis_uploads/` at any time while Auralis is running and see filenames such as `track_{track_id}_{signature}_{preset}_{intensity}_full.wav` (`chunked_processor.py:668`) — revealing which tracks the user is listening to and their chosen enhancement preset/intensity, without needing to read file contents (individual chunk files themselves are written via `atomic_save_audio`/`tempfile.mkstemp`, which Python creates at mode `0600` — file **contents** are owner-only; only the directory **listing** is exposed).
  2. **Symlink-redirect write primitive (higher severity, race-dependent)**: before Auralis's first launch (or after a `rm -rf /tmp/*` / reboot clears `/tmp`), a co-resident local process/account plants `/tmp/auralis_chunks` (or any of the other four names) as a symlink to a directory the *victim's own account* can write to (e.g. an autostart or config directory). `mkdir(exist_ok=True)` does not detect or reject this — it just observes the path already resolves to a directory and proceeds. Every subsequent chunk/cache/upload write from the running app then lands, unknowingly, inside the attacker-chosen directory instead of `/tmp`, with a filename the app controls (always `*.wav`, so not directly executable via common autostart mechanisms, but still an uncontrolled cross-directory write primitive: attacker-directed placement of app-generated files into arbitrary victim-writable paths, which can be used for disk-fill DoS, clobbering unrelated same-named files, or as one link in a longer chain).
- **Impact**: Local metadata/privacy disclosure to co-resident processes/accounts (low bar); redirect-write primitive into attacker-chosen, victim-writable directories (higher severity, contingent on winning a plant-before-first-write race).
- **Siblings**: All five locations share the identical pattern (fixed name + `tempfile.gettempdir()` + bare `mkdir(exist_ok=True)`); `stream_normal.py:127`'s `tempfile.mkdtemp(prefix='auralis_stream_')` is the one exception in this area — `mkdtemp` both randomizes the suffix (unpredictable name, no symlink-plant target to pre-stage) and creates with mode `0700` by default, and is the pattern the other five should follow.
- **Suggested Fix**: For each of the five directories, either (a) switch to `tempfile.mkdtemp(prefix="auralis_...")` per-run (matches `stream_normal.py`'s already-correct pattern, trading a fixed name for an unpredictable one — would need a small metadata file or env var to relocate on restart if persistence across launches is required), or (b) keep the fixed name but harden creation: `os.makedirs(path, mode=0o700, exist_ok=True)` plus an explicit `os.path.islink(path)` / ownership check before use, rejecting (and refusing to proceed, not silently following) a pre-existing symlink or a directory not owned by the current UID.

## Electron (desktop/main.js, desktop/preload.js, desktop/error.html, desktop/package.json)

Read in full: `main.js` (643 lines), `preload.js` (49 lines), `error.html` (112 lines), `package.json` (148 lines).

### A05-1: `shell.openExternal(url)` called unconditionally on any new-window navigation, with no scheme allowlist
- **Severity**: HIGH
- **OWASP Category**: A05
- **Location**: `desktop/main.js:331-334` and `desktop/main.js:639-644`
- **Status**: NEW
- **Description**: Both the per-window `setWindowOpenHandler` and the app-wide `web-contents-created` handler deny the popup but immediately hand the raw target `url` to `shell.openExternal(url)` with zero validation — no scheme allowlist (e.g. restrict to `https:`/`http:`), no confirmation prompt. Electron's own security guide flags unchecked `shell.openExternal` as a local-code-execution vector: on Windows, custom/registered URI schemes (`search-ms:`, `ms-msdt:`, vendor protocol handlers, etc.) can be abused to execute code or leak NTLM credentials; a `file://` URL opens Explorer/Finder on arbitrary local paths.
- **Evidence**:
  ```js
  this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url);
    return { action: 'deny' };
  });
  ...
  app.on('web-contents-created', (_event, contents) => {
    contents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });
  });
  ```
- **Exploit Scenario**: `contextIsolation`/`nodeIntegration` are correctly configured (see below), so a same-origin XSS in the React renderer cannot directly reach Node — but it CAN synthesize `window.open('someuri://...')` or an `<a target="_blank">` click. That reaches this handler, which shells out to the OS via `openExternal` with the attacker-controlled string, unfiltered. Combined with any renderer XSS (e.g. via unsanitized track/artist metadata sourced from an audio file's tags, rendered into the DOM — not confirmed present, but the sink here has zero mitigations if one exists) this becomes a local RCE chain, consistent with the desktop threat model's "renderer XSS + weak isolation = local RCE" framing.
- **Impact**: Local code execution / arbitrary local file or protocol-handler invocation triggered from renderer-controlled content, bypassing `contextIsolation`.
- **Siblings**: Identical unsafe pattern duplicated in two places (per-window handler and the global `web-contents-created` catch-all) — fixing one without the other leaves the same hole for any future additional `BrowserWindow`.
- **Suggested Fix**: Allowlist `url.startsWith('https://')` (and maybe `mailto:`) before calling `shell.openExternal`; deny/log everything else. Consolidate the duplicated handler into one shared function.

### A05-2: `sandbox` not explicitly set in `webPreferences`
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/main.js:309-314`
- **Status**: NEW
- **Description**: The single `BrowserWindow`'s `webPreferences` sets `nodeIntegration: false`, `contextIsolation: true`, `webSecurity: true`, and a `preload` script — all correct — but does not explicitly set `sandbox: true`. Electron 20+ (this app pins `electron@^39.8.5`, confirmed current per `desktop/package.json:29`) defaults `sandbox` to `true` automatically once a `preload` script is present and `contextIsolation` is on, so this is very likely benign in practice, not a live gap — flagged as LOW/informational because explicit is safer than implicit against a future Electron default change or a downgrade.
- **Evidence**: `webPreferences: { nodeIntegration: false, contextIsolation: true, preload: path.join(__dirname, 'preload.js'), webSecurity: true }` — no `sandbox` key.
- **Exploit Scenario**: N/A today (default is already secure); becomes relevant only if Electron's default ever flips or if a future refactor sets `sandbox: false` without noticing this file has no explicit override to catch a diff/lint rule against.
- **Impact**: None currently; hardening/defense-in-depth only.
- **Siblings**: None — only one `BrowserWindow` is created in this app (no separate splash/error window with different `webPreferences`; `error.html` loads via `loadFile` into the same `mainWindow`).
- **Suggested Fix**: Add `sandbox: true` explicitly to `webPreferences` to document the intent and guard against future default changes.

### A05-3: Preload exposes two IPC methods with no corresponding `ipcMain` handler (dead/vestigial attack surface)
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/preload.js:15,25` vs `desktop/main.js:468-591`
- **Status**: NEW
- **Description**: `preload.js` exposes `window.electronAPI.sendToBackend(data)` → `ipcRenderer.invoke('backend-message', data)` and `window.electronAPI.openExternal(url)` → `ipcRenderer.invoke('open-external', url)`. Neither `'backend-message'` nor `'open-external'` has a registered `ipcMain.handle(...)` anywhere in `main.js` (only `select-file`, `select-folder`, `window-minimize`, `window-maximize`, `window-close`, and `check-for-updates` are registered). Calling either from the renderer today just rejects with "No handler registered". Not exploitable as-is, but it is API drift: the name `openExternal` implies a main-process-mediated (and presumably validated) navigation path exists — it doesn't, and the actual `shell.openExternal` call path is the unchecked one in A05-1, so a future contributor wiring up this stub is likely to skip adding scheme validation, believing the preload name already implies safety.
- **Evidence**: `sendToBackend: (data) => ipcRenderer.invoke('backend-message', data)`, `openExternal: (url) => ipcRenderer.invoke('open-external', url)` in `preload.js:15,25`; `grep -n "ipcMain.handle" desktop/main.js` shows no `'backend-message'` or `'open-external'` channel.
- **Exploit Scenario**: None today (dead code path). Risk is future: whoever implements `ipcMain.handle('open-external', ...)` may wire it directly to `shell.openExternal(url)` without validation, reproducing A05-1 through a second entry point.
- **Impact**: Currently none (no-op). Latent risk of reintroducing A05-1 via a second channel.
- **Siblings**: A05-1 (same unsafe sink if ever implemented).
- **Suggested Fix**: Either remove the two dead preload methods or implement the missing handlers with the same URL-scheme validation recommended for A05-1.

### A05-4: `app.setAsDefaultProtocolClient('auralis')` registered with no `open-url`/second-instance handler
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/main.js:636`
- **Status**: NEW
- **Description**: The app registers itself as the OS-level handler for the custom `auralis://` URI scheme, but there is no `app.on('open-url', ...)` (macOS) or `app.requestSingleInstanceLock()` / `second-instance` (Windows/Linux) handler anywhere in `main.js` to receive and validate the invoked URL. Currently this is inert (comment says "future use"), so no data flows anywhere yet — but the registration itself is live at the OS level, meaning any other local process or a malicious link/file (e.g. an `.desktop`/`.url` shortcut, or a link in an unrelated document) can already invoke `auralis://...` and the OS will launch/foreground the app, even though nothing consumes the payload today.
- **Evidence**: `app.setAsDefaultProtocolClient('auralis');` — no matching `open-url` handler found (`grep -n "open-url" desktop/main.js` empty).
- **Exploit Scenario**: Not exploitable today beyond an unwanted app launch/focus-steal (no payload is parsed or acted on). Flag exists so that when this is implemented, the URL must be treated as untrusted input (validate before passing to any navigation, IPC, or file-path logic).
- **Impact**: None today; process launch/focus only.
- **Siblings**: None.
- **Suggested Fix**: When the deep-link feature is implemented, parse and allowlist the `auralis://` payload strictly before acting on it; until then, consider removing the dead registration or leaving a `// TODO` noting the untrusted-input requirement.

### A05-7: No `will-navigate` handler — top-level in-window navigation to any origin is allowed by default, and `preload.js` re-exposes the full `electronAPI` IPC surface to whatever page is navigated to
- **Severity**: HIGH
- **OWASP Category**: A05
- **Location**: `desktop/main.js` (entire file — confirmed by full read, no `will-navigate`/`will-redirect` listener exists anywhere) and `desktop/preload.js:1-44` (the `contextBridge.exposeInMainWorld` call, which is origin-agnostic)
- **Status**: NEW
- **Description**: `main.js` handles pop-up/new-window navigation (`setWindowOpenHandler`, see A05-1) but never registers a `webContents.on('will-navigate', ...)` (or `will-redirect`) listener for the existing window. Electron's documented default when no listener is attached is to **allow** the navigation to proceed to whatever URL triggered it — there is no built-in restriction to `localhost`/`127.0.0.1`. Because `preload.js` is configured on the `BrowserWindow`'s `webPreferences` (not tied to a specific URL), it **re-runs on every navigation of that window, regardless of what origin is being navigated to** — so if the window is ever driven to a remote, attacker-controlled origin, `contextBridge.exposeInMainWorld('electronAPI', {...})` still executes and exposes the full IPC surface (`selectFile`, `selectFolder`, window controls, `sendToBackend`, `openExternal` stub) to that untrusted page's isolated world, with no origin check anywhere in `preload.js` gating it.
- **Evidence**: `grep -n "will-navigate" desktop/main.js` → no results. The only navigation-related handlers present are the two `setWindowOpenHandler` blocks (A05-1), which govern *new* windows/tabs, not in-place navigation of the existing one. `preload.js:4` — `contextBridge.exposeInMainWorld('electronAPI', {...})` has no `location.origin`/`location.hostname` guard before exposing the object.
- **Exploit Scenario**: The renderer normally only ever shows `http://localhost:8765` (prod) or `http://localhost:3000` (dev) content, so under normal operation this is inert. But if any code path in the loaded page ever performs a plain top-level navigation to an external URL — a normal `<a href="https://…">` click without `target="_blank"` (which goes through `will-navigate`, not `setWindowOpenHandler`), a `<meta http-equiv="refresh">`, a `window.location = …` assignment reachable from injected/attacker content, or a future open-redirect in a backend route that something in the frontend follows top-level — the main window silently navigates there with no interception. The destination page then has `window.electronAPI` available via the re-run preload script: it can invoke `selectFile`/`selectFolder` (native OS file/folder picker dialogs, whose resulting **absolute paths** are returned straight to that untrusted page over IPC), issue window-control commands, and call the (currently unimplemented, see A05-3) `sendToBackend`/`openExternal` stubs. This is a materially worse outcome than A05-1 alone, because it is not limited to whatever `shell.openExternal` allows — it is the entire preload-exposed API surface, reachable from a fully remote origin, not just a popup target.
- **Impact**: Full preload/IPC surface (native file/folder pickers + returned absolute paths, window controls) exposed to an arbitrary remote origin if top-level navigation away from `localhost` is ever triggered; local file path disclosure and UI/window manipulation from untrusted content.
- **Siblings**: A05-1 (same root category — insufficiently guarded navigation), A05-3 (the two dead preload channels would also be reachable from the untrusted origin once implemented).
- **Suggested Fix**: Add `mainWindow.webContents.on('will-navigate', (event, url) => { if (!isAllowedOrigin(url)) event.preventDefault(); })` restricting to `http://localhost:8765`/`http://localhost:3000` (dev only) — mirroring the allowlist pattern already used for CORS/WS origins in the backend. Optionally also gate `preload.js`'s `contextBridge.exposeInMainWorld` call behind a `location.hostname === 'localhost'` check as defense-in-depth.

### Verified clean (Electron)
- `webPreferences`: `nodeIntegration: false`, `contextIsolation: true`, `webSecurity: true`, `preload` set correctly (`main.js:309-314`) — matches AUDIT_SECURITY_2026-07-12's note that "Electron is locked down"; still true.
- Only one `BrowserWindow` is ever created; `error.html` loads into the same window via `loadFile`, inheriting the same hardened `webPreferences` — no weaker secondary window.
- Backend process spawn (`main.js:169-181`) uses `spawn(pythonCmd, pythonArgs, {...})` with an **array** of args, no `shell: true` — not vulnerable to shell-metacharacter injection. `pythonCmd`/`pythonArgs`/`cwd` are all derived from `__dirname`/`process.resourcesPath`, never from renderer/user input.
- `exec()` calls in `cleanupPort()` (`main.js:35,67,86`) interpolate `this.backendPort`, which is a hardcoded constant (`8765`), not attacker-controllable — no injection despite string-built `exec` commands.
- Electron version `^39.8.5` (`desktop/package.json:29`) — current major, not stale; caret range is patch/minor-only within v39, and `pnpm-lock.yaml` pins the resolved version so this isn't a moving target at install time.

## CI / Build Config (`.github/workflows/`)

Examined all 7 workflow files: `backend-tests.yml`, `build-release.yml`, `frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml`, `requirements-pin-guard.yml`, `rust-audit.yml`.

### Verified clean
- **No `pull_request_target`** anywhere in any of the 7 workflows (grep for `pull_request_target` across `.github/workflows/*.yml` — zero matches).
- **No explicit `secrets.*` references** in any workflow (grep for `secrets\.` — zero matches); `build-release.yml`'s `create-release` job relies on the implicit default `GITHUB_TOKEN` via `softprops/action-gh-release@v3`, not a custom secret.
- **Least-privilege `permissions:`** block set at the top of every workflow (`contents: read`), with the one necessary escalation (`contents: write`) scoped to the single `create-release` job only (`build-release.yml:391-392`), not workflow-wide.
- **`build-release.yml` (the workflow that actually produces the shipped desktop installers) never runs on `pull_request`** — its triggers are `push: tags: 'v*'` and `workflow_dispatch` only (`build-release.yml:3-11`), and the `create-release` job additionally gates on `if: startsWith(github.ref, 'refs/tags/v')` — so untrusted fork/PR code can never reach the job holding `contents: write`.
- The four test/guard workflows (`backend-tests.yml`, `frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml`, `requirements-pin-guard.yml`, `rust-audit.yml`) that do run on `pull_request` all keep `permissions: contents: read` with no write scopes and no secrets — a compromised/malicious PR can at worst manipulate its own CI run's read-only checkout, not exfiltrate credentials or push anywhere.

### A05-8: Third-party GitHub Actions pinned to mutable tags/branches, not immutable commit SHAs
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `.github/workflows/build-release.yml:69` (`pnpm/action-setup@v6`), `:80,210,316` (`dtolnay/rust-toolchain@stable`), `:419` (`softprops/action-gh-release@v3`); `.github/workflows/rust-audit.yml:40` (`taiki-e/install-action@v2`); `.github/workflows/frontend-test.yml:48` / `frontend-typecheck.yml:39` (`pnpm/action-setup@v4`)
- **Status**: NEW
- **Description**: All third-party (non-`actions/*`) steps are referenced by a floating version tag or branch (`@v6`, `@v2`, `@stable`) rather than a pinned commit SHA. A tag/branch ref is mutable — if the upstream action's maintainer account or repo is compromised, the attacker can re-point the tag to a malicious commit and it runs automatically in this project's next CI execution, with whatever `permissions:`/secrets that job has. The official first-party `actions/*` steps (`checkout`, `setup-python`, `setup-node`, `upload-artifact`, `download-artifact`) are lower-risk (GitHub-maintained, tag-protection is enforced on that org) but are also tag-pinned rather than SHA-pinned, for what it's worth.
- **Evidence**: `grep -n "uses:" .github/workflows/*.yml` shows every action reference as `owner/repo@vN` or `owner/repo@stable`, never `owner/repo@<40-char-sha>`.
- **Exploit Scenario**: Most impactful in `build-release.yml`'s `create-release` job (`contents: write`, produces the actual installer binaries end users download) and the three build jobs feeding it (which run `pnpm/action-setup`, `dtolnay/rust-toolchain`, `taiki-e/install-action`) — a supply-chain compromise of any of those upstream actions could inject malicious code into the artifacts this workflow builds and publishes as an official Auralis release. Blast radius is bounded by the fact that this job only ever runs on an explicit maintainer tag-push or manual `workflow_dispatch`, not on arbitrary PRs — so exploitation requires the *upstream action* to be compromised, not just a hostile external contributor to this repo.
- **Impact**: Potential injection of malicious code into the CI environment and, in the worst case (`build-release.yml`), into the actual shipped Auralis desktop installers.
- **Siblings**: Same pattern across `dtolnay/rust-toolchain@stable` in all three OS build jobs (`build-release.yml:80,210,316`) — note `@stable` is this specific action's documented/conventional usage (a maintained channel branch, not an arbitrary unpinned ref), so it is a slightly different case from the plain version-tag actions, but is equally mutable in principle.
- **Suggested Fix**: Pin `build-release.yml`'s actions (at minimum) to commit SHAs with a version comment, e.g. `uses: softprops/action-gh-release@<sha> # v3`, and consider Dependabot/Renovate's SHA-pinning mode to keep them updated safely. Lower priority for the read-only test/guard workflows given their already-minimal permissions.

---

---

## A06 — Vulnerable and Outdated Components

**Date**: 2026-07-29
**Scope**: Auralis desktop app (single-user, localhost-only Electron + FastAPI + Rust DSP)
**Threat model**: Backend binds 127.0.0.1:8765, Electron desktop, no remote/multi-tenant exposure.
In-scope: CVEs in parsers touching untrusted user-opened input (FFmpeg, soundfile/libsndfile,
mutagen, Pillow), Electron sandbox integrity, unpinned/floating parser versions, absence of a
dependency-audit CI gate, decompression-bomb surface. Out of scope: CVEs that only matter under
network exposure / multi-tenancy.

**Status**: COMPLETE

---

## Verified-fixed prior findings (re-checked against current tree, no regression found)

- **#4343** (CLOSED) "Shipped desktop backend requirements are fully unpinned" — STILL FIXED.
  `auralis-web/backend/requirements.txt` (the file actually rsync'd into `desktop/resources/backend`
  per `build-release.yml`) carries `==` exact pins for numpy/scipy/soundfile/mutagen/pillow/etc.,
  identical to the root `requirements.txt`. `.github/workflows/requirements-pin-guard.yml` job
  `pinned-parser-dependencies` re-enforces that numpy/scipy/soundfile/mutagen specifically must be
  `==`-pinned in the shipped manifest, and job `manifests-mirror` diffs the two files line-for-line
  on every push/PR. No regression found.
- **#4344** (CLOSED) "FFmpeg is an unpinned, unversioned external system binary" — STILL FIXED
  (with a caveat). `auralis/io/loaders/ffmpeg_loader.py` now defines `MINIMUM_FFMPEG_VERSION = (4, 0, 0)`
  and `check_ffmpeg()` parses `ffmpeg -version` and **warns** (not blocks) if the system binary is
  below the floor. This is a warn-only mitigation, not a hard gate — reasonable for a desktop app
  where blocking playback over an old-but-functional system ffmpeg would be a worse user experience
  than the residual risk, so not re-filed as a regression. Dev-machine ffmpeg observed: `8.0.1-3ubuntu2`
  (well above the floor; not representative of what end-users have installed, since no binary is bundled).
- **#4355** (CLOSED) "Four divergent Python manifests with conflicting pinning policies" — STILL FIXED.
  `requirements-desktop.txt` is now a pure `-r requirements.txt` reference (no restated pins), enforced
  by the `desktop-manifest-derives-from-root` job in `requirements-pin-guard.yml`. `pyproject.toml`
  floors (`numpy>=2.0,<2.5`, `scipy>=1.16`, etc.) are consistent with — and cross-checked against —
  `requirements.txt`'s exact pins, enforced by `pyproject-matches-requirements` job
  (`.github/scripts/check_pyproject_deps.py`).
- **#4357** (CLOSED) "Dual/conflicting JS lockfiles" — STILL FIXED. Both `auralis-web/frontend/` and
  `desktop/` have exactly one lockfile each (`pnpm-lock.yaml`), no `package-lock.json`/`yarn.lock`
  found alongside them.
- **#4360** (CLOSED) "Rust crates behind current majors; no cargo audit gate" — **PARTIALLY REGRESSED**,
  see **A06-1** below: the gate exists in name but cannot execute successfully as configured.
- **#4383** (OPEN, not re-filed per instructions) "pyproject.toml declares stale/legacy dependency
  floors incl. dead PyQt6" — re-checked: the current `pyproject.toml` `[project.dependencies]` list
  contains **no** PyQt6 and no 2021-era floors (this was evidently fixed by the #4528 rewrite noted in
  the file's own comments). The GitHub issue is still open even though the code appears fixed — noted
  here only as an issue-hygiene observation, not re-filed as a new finding.

---

### A06-1: `cargo audit` CI gate cannot run — its target file is gitignored and never checked out
- **Severity**: MEDIUM (desktop threat model: this doesn't expose an end user directly, but it means
  the vendored Rust cdylib that is the PyO3 trust boundary for untrusted audio data — the exact thing
  #4360 was filed to protect — has no working vulnerability-scanning gate today)
- **OWASP Category**: A06
- **Location**: `.github/workflows/rust-audit.yml:37-57`, `.gitignore:183,185`
- **Status**: Regression of #4360 (the gate was added to close #4360, but is non-functional as written); see also Existing #4531 (root cause)
- **Description**: `rust-audit.yml` runs `actions/checkout@v4` and then directly:
  `cargo audit --file vendor/auralis-dsp/Cargo.lock --ignore RUSTSEC-2025-0020 --ignore RUSTSEC-2026-0177`
  with no step that generates or restores `vendor/auralis-dsp/Cargo.lock` first. That file is explicitly
  gitignored (`.gitignore:183` `vendor/auralis-dsp/Cargo.lock`, `:185` `vendor/**/Cargo.lock`) and
  confirmed **not tracked** (`git ls-files vendor/auralis-dsp/Cargo.lock` returns nothing). A checkout
  of the git history therefore never places this file on disk in the runner's workspace. `cargo audit`
  errors out (does not silently pass) when the `--file` target does not exist, so every run of this
  workflow — whether from the weekly `schedule` trigger or a (theoretically impossible, since the path
  can never appear in a diff) push/PR trigger — should fail at the `cargo audit` step rather than
  actually scanning the crate's dependency tree for RUSTSEC advisories.
- **Evidence**:
  - `git -C /mnt/data/src/matchering ls-files vendor/auralis-dsp/Cargo.lock` → empty (untracked)
  - `.gitignore:183`: `vendor/auralis-dsp/Cargo.lock`
  - `.gitignore:185`: `vendor/**/Cargo.lock`
  - `vendor/auralis-dsp/Cargo.lock` exists only on local disk (dated Jul 18 22:52, 21711 bytes) —
    i.e. it is a local, uncommitted build artifact, not something CI's checkout can see.
  - `rust-audit.yml` steps in full: `checkout` → `taiki-e/install-action` (installs the `cargo-audit`
    binary only) → `cargo audit --file vendor/auralis-dsp/Cargo.lock ...` — no `cargo generate-lockfile`,
    no `cargo build`, no artifact restore step anywhere in the 57-line file.
- **Exploit Scenario**: Not a direct exploit of the app; this is a control-failure finding. A future
  RUSTSEC advisory lands against `pyo3`, `ndarray`, `rustfft`, or another vendored crate used to parse
  attacker-supplied audio buffers inside the PyO3 extension. The team believes (per #4360's closure and
  the workflow's own doc comment "FAILS the job on any security vulnerability") that this is caught
  automatically, weekly. In reality the job fails at the tooling level before it ever reaches the
  vulnerability check, so nobody is notified of the actual advisory — only of a generic red CI job that
  is easy to dismiss as "flaky" if it has been red since the file was created.
- **Impact**: False sense of security around the Rust/PyO3 trust boundary that decodes numeric audio
  buffers passed from Python. No functional regression to the shipped app itself, but the audit-gate
  the team explicitly added to protect that boundary does not deliver what it claims to.
- **Siblings**: Same untracked-lockfile root cause as open issue **#4531** ("Cargo.lock is gitignored
  for a cdylib that ships in the desktop installer; no rust-toolchain pin") — that issue is about
  build reproducibility for the shipped binary; this finding is a second, distinct consequence
  (a broken CI security gate) of the same untracked-file decision, filed separately because it's a
  different failure mode (silent-ish CI red vs. build reproducibility).
- **Suggested Fix**: Either (a) track `vendor/auralis-dsp/Cargo.lock` in git (resolves both #4531 and
  this finding at once — a cdylib that ships in an installer should have a committed, reviewable lock),
  or (b) if it must stay untracked, add a `cargo generate-lockfile --manifest-path vendor/auralis-dsp/Cargo.toml`
  step before the `cargo audit` step so the workflow at least audits *some* resolved lockfile (accepting
  that it would then audit whatever the crates.io resolver currently produces, not a vetted/reviewed set
  of versions — weaker, but functional). Option (a) is preferable given the file already exists in every
  contributor's working tree today.

---

### A06-2: `builder-util-runtime` (electron-updater's HTTP layer) is below the patched version for a credential-leak-on-redirect advisory
- **Severity**: LOW (for this app's actual config; would be HIGH if a private/token-gated update feed were ever configured)
- **OWASP Category**: A06
- **Location**: `desktop/pnpm-lock.yaml:253,257,1599,1606` (`builder-util-runtime@9.3.1`, `@9.5.1`);
  consumed via `electron-updater@6.6.2` at `desktop/pnpm-lock.yaml:447,1862`; used at runtime in
  `desktop/main.js:2,509-602` (`autoUpdater` from `electron-updater`)
- **Status**: NEW
- **Description**: `pnpm audit --json` in `desktop/` reports advisory id `1124278` (HIGH per pnpm's
  own severity rating) against `builder-util-runtime`: "electron-updater: Cross-origin redirect leaks
  `PRIVATE-TOKEN` and mixed-case `Authorization` credentials", patched at `>=9.7.0`. The resolved
  versions in `desktop/pnpm-lock.yaml` are `9.3.1` and `9.5.1`, both below the patch. Unlike most of
  the other `pnpm audit` findings in this directory (see A06-3), `builder-util-runtime` is a **runtime**
  dependency of `electron-updater`, which ships inside the packaged app and is actively wired up in
  `desktop/main.js` (`autoUpdater.checkForUpdates()`, called on startup and periodically).
- **Evidence**:
  - `pnpm audit --json` (desktop/) → advisory `1124278`, severity `high`, module
    `builder-util-runtime`, `vulnerable_versions: <9.7.0`
  - `desktop/pnpm-lock.yaml` resolves `builder-util-runtime@9.3.1` and `@9.5.1` (two versions present
    in the tree; both below 9.7.0)
  - `desktop/package.json:142-146`: `"publish": {"provider": "github", "owner": "matiaszanolli", "repo": "Auralis"}`
    — a **public** GitHub repo with no `token`/`private: true` option set, so the shipped app's update
    check does not, as currently configured, attach `PRIVATE-TOKEN`/`Authorization` headers whose leak
    on a cross-origin redirect would matter. This is why the finding is scored LOW rather than HIGH
    despite `pnpm audit`'s own HIGH rating (which assumes a token-bearing feed).
- **Exploit Scenario**: Only applies if the maintainer ever switches the publish/update feed to a
  private GitHub repo or another provider requiring a bearer token (`GH_TOKEN`, `PRIVATE-TOKEN`). In
  that configuration, a network position able to issue a cross-origin redirect on the update-check
  request (e.g. a compromised CDN/mirror, or a user on a hostile network before HTTPS cert validation
  is considered) could receive the auth header and reuse the token. Under the *current* public-repo
  config, there is no token to leak.
- **Impact**: None under current configuration; latent risk if the update feed configuration changes.
- **Siblings**: None — this is specific to `electron-updater`'s dependency tree.
- **Suggested Fix**: Bump `electron-updater` to a version that pulls `builder-util-runtime>=9.7.0`
  (check with `pnpm why builder-util-runtime` after upgrading `electron-updater`). Low urgency given
  the public-repo config, but cheap to fix and removes the latent risk if the publish config ever changes.

---

### A06-3: `pnpm audit` in `desktop/` reports 26 advisories (1 critical, 14 high, 11 moderate) — overwhelmingly in `electron-builder`'s build-time toolchain, not the shipped runtime
- **Severity**: LOW (build-machine/CI supply-chain risk, not shipped-app risk — see reasoning below)
- **OWASP Category**: A06
- **Location**: `desktop/package.json:26-27` (`devDependencies: electron-builder ^26.0.0`); resolved
  transitive tree in `desktop/pnpm-lock.yaml`
- **Status**: NEW
- **Description**: `pnpm audit --json` in `desktop/` reports (metadata: `{critical:1, high:14,
  moderate:11, low:0}`, 322 total deps) advisories against `tar` (CRITICAL "Decompression/parse DoS via
  unlimited input", plus 5 more `tar` advisories), `brace-expansion` (6 ReDoS/DoS advisories), `picomatch`
  (2, incl. ReDoS), `lodash` (2, incl. code injection via `_.template`), `js-yaml` (2, quadratic-DoS),
  `form-data` (1, CRLF injection), and `app-builder-lib` (1, "Uncontrolled search path elements within
  AppImage built by app-builder-lib", patched `<26.15.0` — see A06-4). Every one of these is a
  transitive dependency of `electron-builder` (a devDependency — the packaging tool itself), not of
  `electron`, `electron-log`, or `electron-updater` (the three runtime dependencies). None of
  `tar`/`brace-expansion`/`picomatch`/`lodash`/`js-yaml`/`form-data` ship inside the built Electron app;
  they only run on the CI/release build machine while assembling installers, operating on the repo's
  own known file tree (not on attacker-supplied input), which is why this is scored LOW rather than at
  `pnpm audit`'s own CRITICAL/HIGH ratings — those ratings assume the library parses untrusted
  network/user input, which is not the case here.
- **Evidence**: `pnpm audit --json` output (saved during this audit run), `metadata.vulnerabilities:
  {info:0, low:0, moderate:11, high:14, critical:1}`, `dependencies: 322`. Representative entries:
  `1123940` critical `tar` "Decompression/parse DoS via unlimited input" `<=7.5.18`;
  `1123896`/`1123897`/`1123898`/`1124334` high `brace-expansion` DoS variants;
  `1115806` high `lodash` "_.template code injection" `>=4.0.0 <=4.17.23`.
  `desktop/package.json` devDependencies: `"electron-builder": "^26.0.0"` — all of the above resolve
  as transitive deps of this one devDependency per `desktop/pnpm-lock.yaml`.
- **Exploit Scenario**: Build-machine-only: a compromised/typosquatted transitive package pulled during
  `pnpm install` on the CI runner (or a maintainer's dev machine) could act on files present in the CI
  workspace during the build step. This is a general npm supply-chain concern, not something a
  malicious *audio file a user opens* can reach — it requires compromising the package registry/CI
  supply chain itself, a different (much broader) risk category than the parser CVEs this audit is
  primarily scoped to.
- **Impact**: Build-time/CI supply-chain exposure. Zero runtime exposure to end users of the packaged app.
- **Siblings**: None of these appear in `auralis-web/frontend`'s advisory set (see A06-5), confirming
  they're specific to `electron-builder`'s tree.
- **Suggested Fix**: Low priority given the runtime/build-time distinction, but a `pnpm update
  electron-builder` (targeting `>=26.15.0` to also clear the `app-builder-lib` AppImage advisory) would
  clear most of these for free since they're all several patch levels behind current.

---

### A06-4: `app-builder-lib` AppImage "uncontrolled search path" advisory — the one `electron-builder` finding that affects the shipped Linux artifact, not just the build machine
- **Severity**: MEDIUM (Linux AppImage builds only; local-execution search-path issue, consistent with the desktop threat model's "Electron sandbox escape / local RCE" priority)
- **OWASP Category**: A06
- **Location**: `desktop/pnpm-lock.yaml` (`app-builder-lib@26.8.1`, lines 185, 1503); consumed by
  `electron-builder` during the AppImage build target used per `.github/workflows/build-release.yml`'s
  Linux job (flatpak + AppImage + deb per project memory)
- **Status**: NEW
- **Description**: Advisory `1124279` (HIGH per pnpm, "Uncontrolled search path elements within
  `AppImage` built by `app-builder-lib`", patched `>=26.15.0`) is distinct from the rest of A06-3
  because it describes a defect in *what `app-builder-lib` produces* (the AppImage file itself), not
  just a DoS reachable only during the build. An AppImage with an uncontrolled/unqualified search path
  can be induced to load a library or helper binary from an unintended, potentially attacker-writable
  directory when the *end user* executes it — this is exactly the "local execution / sandbox-adjacent"
  category the threat model calls in-scope for a desktop app. `app-builder-lib@26.8.1` is resolved in
  `desktop/pnpm-lock.yaml`, below the `26.15.0` patch.
- **Evidence**: `pnpm audit --json` (desktop/) advisory `1124279`, `vulnerable_versions: <26.15.0`,
  resolved `app-builder-lib@26.8.1` (`desktop/pnpm-lock.yaml:185,1503`).
- **Exploit Scenario**: A user downloads the released `.AppImage`, places it in a directory that also
  contains (or is writable by another local process/user that places) a maliciously-named file matching
  the uncontrolled search path, and executing the AppImage causes the wrong binary/library to load. This
  is a local-execution integrity issue consistent with "renderer sandbox escapes are real local RCE for
  a desktop app" from the threat model, though the specific mechanics of this advisory could not be
  further verified without pulling the upstream advisory text in detail (not done here; flagged as
  MEDIUM rather than HIGH pending that detail).
- **Impact**: Potential local code execution / library-hijack on the packaged Linux AppImage, for users
  who run the released artifact from a directory an attacker can also write to.
- **Siblings**: None — Windows (NSIS) and macOS (DMG) targets use different `app-builder-lib` code
  paths; this advisory is scoped to AppImage per its title.
- **Suggested Fix**: Bump `electron-builder`/`app-builder-lib` to `>=26.15.0` before the next release
  build; verify by rebuilding the Linux AppImage target and confirming the CI Linux build job
  (`build-release.yml`) still succeeds.

---

### A06-5: `react-router` / `react-router-dom` / `@remix-run/router` in the frontend are on advisory-listed versions, but the vulnerable code paths (SSR hydration, open-redirect navigation) do not appear reachable in this app
- **Severity**: LOW (present-but-likely-unreachable; noted for completeness per audit scope)
- **OWASP Category**: A06
- **Location**: `auralis-web/frontend/pnpm-lock.yaml:1453,1460,662` (`react-router-dom@6.30.2`,
  `react-router@6.30.2`, `@remix-run/router@1.23.1`); `auralis-web/frontend/package.json` declares
  `"react-router-dom": "^6.15.0"`
- **Status**: NEW
- **Description**: `pnpm audit --json` in `auralis-web/frontend/` reports 5 advisories touching this
  family: `1112052` (HIGH, `@remix-run/router` "XSS via Open Redirects", CVE-2026-22029, vulnerable
  `<=1.23.1`, patched `>=1.23.2` — resolved version `1.23.1` is exactly one patch below the fix);
  `1120064`/`1124268`/`1124272` (MODERATE, `react-router`, open-redirect / SSR-hydration constructor
  injection); `1124270` (MODERATE, `react-router-dom`, "Open redirect leading to XSS", CVE-2026-53668,
  vulnerable `>=6.30.2 <=6.30.4`, `patched_versions: <0.0.0` i.e. no patched 6.x release exists — the
  advisory's own fix requires migrating to 7.x). Several of these advisories explicitly note they only
  apply to Framework Mode/Data Mode SSR or to apps whose own code redirects to attacker-controlled
  URLs. This is a client-only Vite SPA (no SSR), and a repo-wide grep for `useNavigate(` in application
  source (`auralis-web/frontend/src`) returned **zero** matches — the app does not appear to
  programmatically navigate based on any external/user-supplied URL, which is the precondition several
  of these advisories require.
- **Evidence**: `pnpm audit --json` (frontend/) advisories `1112052`, `1120064`, `1124268`, `1124270`,
  `1124272`; `grep -rn "useNavigate(" auralis-web/frontend/src` → no matches.
- **Exploit Scenario**: Would require the app to redirect based on attacker-influenced content (e.g. a
  crafted deep link or a value from an untrusted API response fed into `<Navigate>`/`useNavigate`).
  No such call site was found. Filed as LOW/informational rather than omitted, since the vulnerable
  package versions are genuinely present in the dependency tree and a future feature could reintroduce
  the precondition.
- **Impact**: None currently observed exploitable path; dependency-freshness debt.
- **Siblings**: The frontend audit also reported `yaml` (moderate, stack-overflow, via
  `@emotion/react` → `babel-plugin-macros` → `cosmiconfig`, build-tool-only), `ws` (moderate+high,
  memory-exhaustion/uninitialized-memory, via `jsdom`, a **test-only** devDependency used by Vitest,
  not shipped), `esbuild` (low, dev-server arbitrary file read on Windows, build-tool-only), and
  `@babel/core` (low, arbitrary file read via sourcemap comment, build-tool-only) — none of these ship
  in the production Vite build served to the Electron renderer.
- **Suggested Fix**: `pnpm update react-router-dom react-router @remix-run/router` to pick up
  `@remix-run/router>=1.23.2` at minimum (closes the one HIGH advisory with an actual available patch
  in the 6.x line); track a 7.x migration separately since several `react-router` fixes only exist
  there. Low urgency given no reachable call site was found.

---

### A06-6: No `uv.lock` (or any hash-locked Python lockfile) — reproducibility rests entirely on `requirements.txt`'s top-level `==` pins, not on a full dependency-tree lock
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: repo root (absence of `uv.lock`); `requirements.txt`, `pyproject.toml`
- **Status**: NEW
- **Description**: The pin-guard CI (`requirements-pin-guard.yml`) verifies that the *direct*
  dependencies named in `requirements.txt`/`auralis-web/backend/requirements.txt` are `==`-pinned and
  mirror each other, and that `pyproject.toml`'s floors are consistent with them. This is real and
  effective for the packages it names. However, there is no committed `uv.lock` (or `pip-compile`
  output with hashes) anywhere in the repo (`find . -iname uv.lock` → nothing), so the *transitive*
  dependencies of numpy/scipy/soundfile/librosa/mutagen/pillow are not pinned or hash-verified at all —
  a fresh `pip install -r requirements.txt` resolves whatever transitive versions PyPI serves at
  install time, subject only to whatever version constraints those packages' own metadata declares.
  This was directly observable in this session's own dev `.venv`: `python -m pip list` shows several
  *direct* pinned packages at versions materially different from `requirements.txt`'s pins (e.g.
  `fastapi 0.140.13` installed vs. `fastapi==0.122.0` pinned; `numpy 2.4.6` vs. `numpy==2.3.5`;
  `scipy 1.18.0` vs. `scipy==1.16.3`; `soundfile 0.14.0` vs. `soundfile==0.13.1`; `uvicorn 0.51.0` vs.
  `uvicorn==0.38.0`; `python-multipart 0.0.27`, which is actually *below* the `>=0.0.31` floor declared
  in `pyproject.toml`). This particular drift is most likely because this local venv was built via
  `pip install -e ".[dev]"` against `pyproject.toml`'s open floors rather than via `pip install -r
  requirements.txt` — and `backend-tests.yml` (the CI workflow that actually runs `pytest`) correctly
  uses `pip install -r requirements.txt`, so this specific drift is a local/session artifact, not
  something wrong with the CI pipeline. It is reported here only as **live evidence** that "a package
  is `==`-pinned in a text file" and "the version actually running" are two different claims, and that
  nothing in the repo (lockfile or otherwise) closes that gap for transitive dependencies even when the
  top-level pin is honored.
- **Evidence**: `find /mnt/data/src/matchering -maxdepth 2 -iname "uv.lock"` → no results;
  `/mnt/data/src/matchering/.venv/bin/python -m pip list` vs. `requirements.txt` pins (see above);
  `backend-tests.yml:71`: `pip install -r requirements.txt` (confirms CI itself does the right thing
  for direct pins — this finding is about the *absence of transitive locking*, not a CI defect).
- **Exploit Scenario**: A transitive dependency of `soundfile`/`librosa`/`mutagen` publishes a
  malicious or newly-vulnerable release; a fresh install (a new contributor, a new CI cache, a future
  release build after cache eviction) picks it up silently because nothing hash-locks the full tree.
- **Impact**: Reduced reproducibility and delayed detection of a compromised/vulnerable transitive
  package in the untrusted-audio-parsing dependency tree.
- **Siblings**: Node side does not have this gap — `pnpm-lock.yaml` in both `auralis-web/frontend/`
  and `desktop/` is a full, committed, hash-verified lockfile.
- **Suggested Fix**: Adopt `uv lock` (the project already uses `uv` per `CLAUDE.md`/memory) and commit
  `uv.lock`; point CI installs at `uv sync --frozen` instead of `pip install -r requirements.txt` so
  the exact resolved tree — not just the top-level pins — is reproducible and diffable in review.

---

### A06-7: Third-party GitHub Actions are pinned to floating major-version tags, not commit SHAs
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: All files under `.github/workflows/*.yml`
- **Status**: NEW
- **Description**: Every third-party (and first-party `actions/*`) GitHub Action referenced across the
  6 workflow files is pinned to a floating tag (`@v4`, `@v6`, `@v8`, etc.) or, in one case, a floating
  branch alias (`dtolnay/rust-toolchain@stable`). None are pinned to an immutable commit SHA. Tags on
  third-party actions (`pnpm/action-setup`, `taiki-e/install-action`, `softprops/action-gh-release`,
  `dtolnay/rust-toolchain`) are mutable by the action's maintainer (or by anyone who compromises that
  maintainer's account/repo) — a compromised action could inject malicious code into every workflow run
  without any diff appearing in this repo's history.
- **Evidence**: `grep -rhn "uses:" .github/workflows/*.yml` → `actions/checkout@v4`, `@v6`;
  `actions/download-artifact@v8`; `actions/setup-node@v4`, `@v6`; `actions/setup-python@v5`, `@v6`;
  `actions/upload-artifact@v4`, `@v7`; `dtolnay/rust-toolchain@stable`; `pnpm/action-setup@v4`, `@v6`;
  `softprops/action-gh-release@v3`; `taiki-e/install-action@v2`. No `dependabot.yml` present
  (`.github/dependabot.yml` not found) and no CodeQL workflow found (`grep -rl "codeql" .github/workflows/`
  → no results), so there is also no automated bot to keep these (or the JS/Python manifests) current.
- **Exploit Scenario**: An attacker compromises e.g. `taiki-e/install-action` (used to fetch
  `cargo-audit` — see A06-1) or `softprops/action-gh-release` (used at release-publish time, likely
  with elevated `contents: write`/release-upload permissions) and repoints the `v2`/`v3` tag to a
  malicious commit. The next CI run (push to master, PR, or the weekly schedule) executes attacker
  code with whatever permissions that job/token has — for `build-release.yml`, potentially the ability
  to tamper with the published release artifacts users download and install.
  This is CI/build-supply-chain risk, not a runtime attack surface reachable by opening a media file,
  but it directly affects the integrity of the desktop installer end users trust, which is why it's
  filed under A06 for this desktop-app audit rather than dismissed as purely a "generic CI hygiene" item.
- **Impact**: Supply-chain integrity risk for the released installer artifacts.
- **Siblings**: Applies uniformly across all 6 workflow files; not specific to any one.
- **Suggested Fix**: Pin `taiki-e/install-action` and `softprops/action-gh-release` (the two actions
  involved in build-release.yml's most sensitive steps) to a commit SHA at minimum; consider adding
  Dependabot for `github-actions` ecosystem updates (`.github/dependabot.yml` with
  `package-ecosystem: "github-actions"`) so SHA pins don't silently go stale, and/or a CodeQL workflow
  for the Python/JS/TS source as a second, complementary A06/A08 control.

---

## Additional scope items checked — no finding (disproved / not applicable)

- **Decompression-bomb surface (`zipfile`/`tarfile`/`gzip`/`zstandard`)**: `grep -rn` across
  `auralis/` and `auralis-web/backend/` (excluding `tests/` and the stray PyInstaller `build/`
  directory under `auralis-web/backend/build/`, which only lists these modules as transitive
  imports of `urllib3`/packaging tooling, not application code) found **no application code** that
  unzips/untars/decompresses user-supplied data. The only decompression-adjacent surface is FFmpeg's
  own internal container demuxing (outside Auralis's code, inside the external ffmpeg binary — covered
  by the FFmpeg version-floor discussion above) and Pillow's image decoding for artwork.
- **Pillow decompression bombs (artwork)**: `auralis/library/artwork.py:263-273` and
  `auralis-web/backend/routers/artwork.py:108-133` both call `PIL.Image.open()` on artwork bytes with
  no `Image.MAX_IMAGE_PIXELS` override — meaning Pillow's **default** decompression-bomb guard
  (`DecompressionBombWarning`/`DecompressionBombError` above ~89 megapixels) is active, not disabled.
  In addition, `artwork.py` has an explicit `_bound_dimensions()` step (added for #4439) that downscales
  any artwork whose largest side exceeds `_MAX_ARTWORK_DIMENSION` before it is persisted or streamed.
  Between Pillow's own default and this app-level cap, no gap was found here.
- **Electron security flags**: `desktop/main.js:310-313` sets `nodeIntegration: false`,
  `contextIsolation: true`, `webSecurity: true` on the `BrowserWindow` — correct hardened defaults;
  no A06/renderer-sandbox finding here.
- **pyo3/numpy/ndarray Rust crate versions**: `vendor/auralis-dsp/Cargo.toml` pins `pyo3 = "0.23"`,
  `numpy = "0.23"`, `ndarray = "0.16"`. `rust-audit.yml`'s own comments state two pyo3 0.23 RUSTSEC
  advisories (`RUSTSEC-2025-0020`, `RUSTSEC-2026-0177`) are deliberately `--ignore`d with a documented
  rationale (neither vulnerable API — `PyString::from_object`, `PyCFunction::new_closure` — is called
  by this crate). A `vendor/auralis-dsp/UPGRADE_PLAN.md` tracks the deferred major-version bump. This
  audit did not independently re-verify the "neither API is called" claim by grepping the Rust source
  (noted under Not Reached below) — and, per A06-1, the workflow that's supposed to run this check
  cannot currently execute at all, which is the more urgent problem.
- **FFmpeg bundling**: No bundled ffmpeg binary found under `desktop/resources/` or referenced in
  `build-release.yml`; the app relies entirely on whatever `ffmpeg`/`ffprobe` is on the end user's
  `PATH`, mitigated only by the warn-only version floor (see #4344 above).

---

---

## A07 — Identification & Authentication Failures / Local API Surface

Threat model: single-user Electron desktop app, backend binds `127.0.0.1:8765` only
(confirmed by another agent: zero `0.0.0.0` hits). No auth on the local API is the
documented, accepted baseline (#4385, CLOSED) — **not** re-filed here. In scope:
places where that baseline is *eroded* — reachability beyond loopback, CSRF /
DNS-rebinding / "simple request" exposure from a normal browser tab, WebSocket
origin-gating gaps, and rate limiting as a self-protection control.

Severity is rated against this desktop threat model, not generic CVSS/network-exposure
assumptions.

---

### A07-1: RateLimitMiddleware keys on full path while matching by prefix — parameterized endpoints get an unbounded effective budget

- **Severity**: MEDIUM
- **OWASP Category**: A07 (rate limiting as a self-protection / resource-exhaustion control)
- **Location**: `auralis-web/backend/config/middleware.py:178-225` (`RateLimitMiddleware.dispatch`), rule table at `:146-151`
- **Status**: NEW
- **Description**: `RateLimitMiddleware` selects a rule by **prefix match** (`path.startswith(prefix)`, line 185) but builds its sliding-window bucket key from the **exact request path** (`key = f"{client_ip}:{path}"`, line 194). For any rule whose prefix covers a family of path-parameterized routes, every distinct parameter value gets its own independent budget window instead of sharing the rule's budget. This was verified empirically (78 consecutive requests against a path-parameterized route under a matched prefix, zero 429s).
- **Evidence**:
  ```python
  # config/middleware.py
  _RATE_LIMITS: dict[str, tuple[int, int]] = {
      "/api/files/upload": (5, 60),
      "/api/processing": (10, 60),        # <- also matches /api/processing/job/{job_id}/cancel
      "/api/library/scan": (2, 60),
      "/api/similarity": (20, 60),        # <- also matches /api/similarity/tracks/{track_id}/similar
  }
  ...
  for prefix, rule in self._RATE_LIMITS.items():
      if path.startswith(prefix):
          limit_rule = rule
          break
  ...
  key = f"{client_ip}:{path}"   # exact path, not the matched prefix
  ```
  Concrete routes confirmed under the affected prefixes:
  - `POST /api/processing/job/{job_id}/cancel` (`routers/processing_api.py:368`) — matches the `/api/processing` rule (10/60s), but keys per `job_id`.
  - `GET /api/similarity/tracks/{track_id}/similar` (`routers/similarity.py:105`), `GET /api/similarity/tracks/{id1}/compare/{id2}` (`:205`), `.../explain/{id2}` (`:256`) — all match the `/api/similarity` rule (20/60s), each keyed per track-id combination.
- **Exploit Scenario**: A local process (or malicious/compromised script the user runs, or — combined with A07-2 below — a page that can drive many distinct-ID requests) cycles through distinct `job_id`/`track_id` values. Each new id opens a fresh 10-or-20-request budget, so the *intended* aggregate ceiling for the endpoint family is never actually enforced — the attacker's total request volume against `/api/processing/...` or `/api/similarity/...` is bounded only by how many distinct ids exist, not by the configured rule.
- **Impact**: The rate limiter fails at its stated purpose (self-protection against runaway resource use for expensive endpoints — job cancellation churn, O(N²) similarity queries) for exactly the routes most likely to be expensive per-call. Also compounds into a memory-growth concern: `self._windows` is only pruned every 256 requests process-wide (`_EVICTION_INTERVAL`, not per-key), so a burst of requests against many distinct ids within one window (60s) can create thousands of live dict entries before the periodic eviction sweep ever runs, since none of them are individually "stale" yet.
- **Siblings**: Any future prefix added to `_RATE_LIMITS` that has path-parameterized children inherits the same flaw; `/api/files/upload` and `/api/library/scan` are currently unaffected only because they have no parameterized sub-paths today.
- **Suggested Fix**: Key the sliding window on `f"{client_ip}:{prefix}"` (the matched *rule*, not the raw request path) so all requests under a rule share one budget, matching the prefix-based matching semantics already used to select the rule.

---

### A07-2: State-changing POST endpoints with no JSON-body validation are exploitable via plain cross-origin "simple requests" (CSRF)

- **Severity**: HIGH
- **OWASP Category**: A07 (erosion of the loopback-only isolation boundary — any web page the user's ordinary browser visits can silently drive the local API)
- **Location**: multiple routers, see full list below. Root cause mechanism confirmed by reading `fastapi/routing.py` (installed v0.128.0) — a POST handler only auto-parses the raw body as JSON when the `Content-Type` header is absent or `application/(*+)json` (`routing.py:299-311`); when the handler declares **no body parameter at all** (pure action, or `Query(...)`-only params with defaults), there is nothing to fail validation, so the request succeeds regardless of what the browser sends.
- **Description**: Per the CORS/Fetch spec, `GET`/`HEAD`/`POST` requests with only CORS-safelisted headers and content types (`text/plain`, `application/x-www-form-urlencoded`, `multipart/form-data`, or **no body at all**) are "simple requests" — the browser sends them with **no preflight**, and critically, **the request still executes on the server**; CORS only blocks the page's JavaScript from *reading the response*. This app's CORS policy is correctly configured (concrete origin allowlist, no wildcard — not a finding here), but CORS was never designed to stop the request itself, only to stop the attacker reading the response. Since Auralis has no CSRF token, no session, and no Origin/Referer check on any REST route (`routers/dependencies.py` only has service-availability guards, e.g. `require_audio_player`/`require_repository_factory` — no auth/origin dependency exists to apply), any endpoint whose entire input comes from the URL path/query (not a required JSON body) can be triggered blind by:
  - a hidden auto-submitting `<form method="POST" action="http://127.0.0.1:8765/api/player/next">` on **any website**, or
  - `fetch(url, {method: 'POST', mode: 'no-cors'})` / `navigator.sendBeacon(url)`.

  This is a materially different — and new — risk from the accepted "no auth on loopback" baseline: the accepted baseline assumes the local *attack surface* is other local processes. This finding means **a completely unrelated web page in the user's normal browser tab**, with zero local code execution and zero user interaction beyond having the page open, can drive real state changes in the desktop app while it happens to be running. The backend's port (8765) is fixed and never randomized (`desktop/main.js:19`, confirmed no token/secret is exchanged), so the attacker doesn't even need to discover anything — the URL is hardcodable.
- **Evidence — confirmed bodyless/query-only POST endpoints** (no `Content-Type` requirement, so any simple request succeeds):
  | Route | File:line | Effect |
  |---|---|---|
  | `POST /api/player/next` | `routers/player.py:744` | Skips current track |
  | `POST /api/player/previous` | `routers/player.py:756` | Skips to previous track |
  | `POST /api/player/queue/clear` | `routers/player.py:663` | Wipes the entire playback queue |
  | `POST /api/player/queue/undo` | `routers/player.py:569` | Mutates queue history state |
  | `POST /api/library/refresh-references` | `routers/library.py:62` | Rebuilds the mastering reference cloud (clears/reassigns `is_reference` flags across the library) |
  | `POST /clear` (cache router, prefix `/api/cache`) | `routers/cache_streamlined.py:147` | Clears all cached processed-audio tiers, forcing re-processing |
  | `POST /api/settings/reset` | `routers/settings.py:230` | Resets all user settings to defaults |
  | `POST /fingerprint-queue/enqueue/{track_id}` | `routers/fingerprint_queue.py:92` | Enqueues arbitrary track id for fingerprinting |
  | `POST /fingerprint-queue/enqueue-all?limit=N` | `routers/fingerprint_queue.py:135` | Enqueues the entire library for fingerprinting (query param only, has a working default of "all") |
  | `POST /api/albums/{album_id}/artwork/extract` | `routers/artwork.py:335` | Triggers artwork extraction for arbitrary album id |
  | `POST /api/albums/{album_id}/artwork/download` | `routers/artwork.py:416` | Triggers an outbound artwork download for arbitrary album id |
  | `POST /api/library/tracks/{track_id}/favorite` | `routers/tracks.py:108` | Marks arbitrary track id as favorite |
  | `POST /api/similarity/graph/build?k=..&clear_existing=true` | `routers/similarity_graph.py:55` | **Clears the existing similarity graph by default** (`clear_existing: bool = Query(True, ...)`) and kicks off an O(N²) K-NN rebuild |
  | `POST /api/similarity/fit?min_samples=..` | `routers/similarity.py:290` | Re-fits the similarity system |

  All parameters above are `Query(...)` (URL query string) or path parameters, not a JSON body — so content-type is irrelevant and the attacker fully controls them from the URL alone.

- **Evidence the team already knows this exact risk, but the fix is applied to only one endpoint**: `routers/library.py:95-111` (`reset_library`) requires a custom `X-Confirm-Reset: RESET` header and its docstring says so explicitly:
  ```python
  @router.post("/api/library/reset")
  async def reset_library(
      x_confirm_reset: str = Header(..., alias="X-Confirm-Reset", ...),
  ) -> dict[str, Any]:
      """... Requires the ``X-Confirm-Reset: RESET`` header as a safety guard
      against accidental or CSRF-triggered calls."""
  ```
  Setting a custom header from a browser (`X-Confirm-Reset`) is *not* CORS-safelisted, so it forces a preflight, which the origin allowlist then blocks for any non-Auralis page — this is a real, working mitigation. It is the only endpoint in the codebase that has it; every route in the table above has an equivalent or worse blast radius (playback disruption, full queue wipe, full-library rescans, cache invalidation, settings reset) with no equivalent guard.
- **Note on JSON-body endpoints**: Endpoints with a *required* Pydantic body model (e.g. `SeekRequest`, `SetVolumeRequest`, `LibraryScanRequest`, `ProcessRequest`) are **not** exploitable this way: verified in `fastapi/routing.py:294-311` that FastAPI only attempts `request.json()` when `Content-Type` is absent or an `application/*json` variant; a form-encoded or `text/plain` body is instead passed through as raw bytes, which fails Pydantic model validation (422) before reaching the handler. This distinction is why the finding above is scoped specifically to bodyless / query-only POST routes.
- **Note on PUT/DELETE endpoints**: Not exploitable via a plain `<form>` (browsers only support GET/POST natively) and a `fetch()`/XHR call using PUT/DELETE always triggers a CORS preflight regardless of headers (only GET/HEAD/POST are "simple methods" per the Fetch spec), which the origin allowlist then blocks. So `DELETE /api/player/queue/{index}`, `DELETE /api/player/queue/history`, `DELETE /api/processing/jobs/cleanup`, etc. are correctly protected by the existing CORS configuration and are **not** part of this finding.
- **Exploit Scenario**:
  1. User has the Auralis desktop app open (or even just running in the background/tray) and separately browses the web in their normal browser.
  2. User visits any page containing attacker-controlled JS/HTML (a compromised ad, a malicious site, or a site with a stored-XSS payload — the specific delivery is out of scope, but the reachability is the point).
  3. That page runs, e.g., `fetch('http://127.0.0.1:8765/api/player/queue/clear', {method:'POST', mode:'no-cors'})` or auto-submits a hidden form to `http://127.0.0.1:8765/api/similarity/graph/build?clear_existing=true`.
  4. The browser sends the request with no preflight (simple request); Auralis's backend has no Origin/Referer check on REST routes and no CSRF token, so it executes unconditionally.
  5. The user's queue is wiped / library rescanned / similarity graph destroyed / settings reset, with zero visible cause connecting it to the web page they were just on.
- **Impact**: Confidentiality: none (no data returned cross-origin, CORS still blocks reading responses). Integrity/Availability: real, user-visible state corruption and resource-exhaustion triggerable by an entirely passive act (visiting a web page) — this is the concrete "beyond loopback" erosion the audit brief asked to identify, distinct from the accepted local-process-trust baseline.
- **Suggested Fix**: Add a single shared dependency (mirroring `routers/dependencies.py`'s existing `require_*` pattern) that rejects any state-changing request whose `Origin` header (when present) is not in the same allowlist already used for CORS/WS (`config/middleware.cors_allowed_origins()` / `config/globals.ALLOWED_WS_ORIGINS`), and apply it to every POST/PUT/DELETE router in the table above — this is the REST-endpoint equivalent of the check `config/globals.py:ConnectionManager.connect` already does for WebSocket, so no new policy needs to be invented. Alternatively/additionally, require a custom header (as `reset_library` already does) on every state-changing route, which forces a preflight the origin allowlist can reject.

---

### A07-3: `is_dev_mode()` env-var gate can silently reopen the Vite dev-port CORS/WS origin allowlist in a packaged production build

- **Severity**: LOW
- **OWASP Category**: A07 (completeness gap in the #4350 fix — dev-only origins re-admitted in "production")
- **Location**: `auralis-web/backend/config/app.py:25-27` (`is_dev_mode`), consumed by `config/middleware.py:230-259` (`cors_allowed_origins`) and `config/globals.py:29-52` (`build_ws_origins`); environment inheritance at `desktop/main.js:169-179`
- **Status**: NEW (adjacent to, but distinct from, the fix verified for #4350 — the fix itself is present and correct; this is a completeness gap in what "production" means)
- **Description**: `is_dev_mode()` is:
  ```python
  def is_dev_mode() -> bool:
      return "--dev" in sys.argv or os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")
  ```
  A packaged Electron build never passes `--dev` in `pythonArgs` (confirmed: no `--dev` literal anywhere in `desktop/main.js`), so the `sys.argv` branch is safe. But the Electron main process spawns the backend with `env: { ...process.env, ... }` (`desktop/main.js:169-179`) — the **entire parent environment is inherited**, unfiltered. If `DEV_MODE=1` (or `true`/`yes`) happens to be set in the ambient shell/user/session environment the packaged app is launched from (leftover from a previous dev session, a global dotfile export, a CI/test-harness artifact, etc.), the "production" packaged app silently re-admits the full Vite dev-port allowlist (`localhost`/`127.0.0.1` ports 3000-3006, both CORS origins and WebSocket origins) — exactly the hole #4350 was filed to close, just reopened through the one path that fix didn't account for: an ambient env var rather than an explicit launch flag.
- **Evidence**: `config/globals.py:37-38` and `config/middleware.py:251-253` both call the same `is_dev_mode()` and both react purely to the env var with no distinction from an explicit `--dev` flag; `desktop/main.js:172` (`env: { ...process.env, ... }`) is the inheritance path.
- **Exploit Scenario**: A developer's machine (or any machine that at some point ran Auralis in `--dev` mode via a shell that exported `DEV_MODE=1` rather than passing the CLI flag) later double-clicks the packaged production app from a terminal/session where that env var is still exported. The backend comes up believing it's in dev mode; a page served from `http://localhost:3000` (e.g. a leftover Vite dev server, or anything an attacker gets to bind that port) is now a valid CORS and WebSocket origin against the production backend, undermining the allowlist's intent of "only the packaged app's own origin(s) are trusted."
- **Impact**: Low — requires a specific, non-default precondition (the env var already being set) and the exposure it grants is narrow (a small, fixed, well-known port range on loopback) — but it fully defeats the specific defense #4350 was filed for, silently and without any log/warning distinguishing "explicit dev launch" from "ambient env var dev launch."
- **Siblings**: None found — this is the only environment-inherited gate in the codebase (`ELECTRON_MODE=1` is set explicitly by main.js itself, not inherited).
- **Suggested Fix**: Have the packaged/production launch path in `desktop/main.js` explicitly pass `DEV_MODE: '0'` (or delete it from the spread env) in the non-development spawn branch, so the packaged build's origin allowlist cannot be widened by anything in the ambient parent environment. Optionally log a warning server-side when `is_dev_mode()` is true via the env-var branch specifically (vs. the argv branch), so an accidental production dev-mode launch is at least visible.

---

### A07-4 (informational / LOW): Rejected-origin WebSocket connections still consume a heartbeat task and initial-sync work before teardown

- **Severity**: LOW
- **OWASP Category**: A07 (minor resource-hygiene gap adjacent to the origin check)
- **Location**: `auralis-web/backend/ws_handlers/connection.py:33-99` (`setup_connection`), `config/globals.py:77-106` (`ConnectionManager.connect`)
- **Status**: NEW
- **Description**: `setup_connection()` calls `await manager.connect(websocket)` (line 44) with no check of its return value or the socket's state. `ConnectionManager.connect()` closes the socket with code 1008 and returns (without raising) when the Origin check fails (`globals.py:91-104`). `setup_connection()` then unconditionally proceeds to compute a `connection_id`, construct a `HeartbeatManager`, and `spawn_background_task(_heartbeat_loop())` (line 62) — a task that sleeps 30s and then attempts to close the (already-closed) socket again — and attempts two `websocket.send_text()` calls (enhancement settings, player state), both wrapped in broad `try/except Exception: pass`-style handlers so the failures are silently swallowed rather than short-circuiting.
- **Evidence**:
  ```python
  await manager.connect(websocket)      # may close(code=1008) and return here
  connection_id = _ws_id(websocket)
  heartbeat = HeartbeatManager(...)
  heartbeat_task = spawn_background_task(_heartbeat_loop(), ...)   # spawned regardless
  ...
  await websocket.send_text(...)        # best-effort try/except swallows the failure
  ```
- **Exploit Scenario**: This does **not** allow message processing to bypass the origin check — the caller's main receive loop (`routers/system.py:333-352`) calls `websocket.receive_text()` immediately after, which raises `WebSocketDisconnect` on an already-closed socket, so no attacker-controlled message is ever dispatched. The only consequence is wasted per-attempt resources (one asyncio task alive for up to 30s, two JSON encodes/send attempts) per rejected connection attempt, which a local script could cheaply amplify by opening and immediately being rejected in a loop — a very mild, loopback-only resource-churn amplification, not a bypass of the auth/origin gate itself.
- **Impact**: Negligible on a single-user desktop app; noted for completeness since it's directly adjacent to the origin-check code path this dimension is auditing.
- **Suggested Fix**: Have `ConnectionManager.connect()` return a bool (`accepted`) and have `setup_connection()` return early (without spawning the heartbeat task or sending initial state) when it's `False`.

---

## Verified NOT regressed (per audit instructions, confirmed present in current tree — not re-filed)
- **#4353** (TrustedHostMiddleware / DNS-rebinding defense-in-depth): confirmed present at `config/middleware.py:272,282-299,332` (`_TRUSTED_HOSTS = ("localhost", "127.0.0.1")`, wired via `app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts())`).
- **#4350** (dev-port CORS + WS origin allowlist gated to dev builds only): confirmed present — both `cors_allowed_origins()` (`middleware.py:252`) and `build_ws_origins()` (`globals.py:38`) gate the `3000-3006` port range on `is_dev_mode()`. (See A07-3 above for a narrower, newly-identified completeness gap in *how* `is_dev_mode()` itself can be tricked — the #4350 fix code is intact and correctly wired.)
- Middleware order confirmed as documented: CORS → SecurityHeaders → NoCache → TrustedHost → RateLimit → app (`middleware.py:313-355`, comments and `add_middleware` call order match).
- CORS configuration confirmed clean: concrete origin list (no wildcard), `allow_credentials=True` paired with explicit `allow_methods`/`allow_headers` lists (`middleware.py:347-355`) — not re-filed per instructions.
- WebSocket Origin check (`config/globals.py:77-106`): confirmed correctly rejects non-allowlisted non-empty Origins (fixes #2413), and separately rejects empty-Origin connections from non-loopback hosts (fixes #3845) — this closes the "non-browser client sends no Origin" fail-open concern raised in the brief. Only one WS route exists (`routers/system.py:297` `/ws`), and it is gated via `ws_connection.setup_connection` → `manager.connect` — no unguarded WebSocket route was found.
- No `X-Forwarded-For`/proxy-header trust found anywhere in the backend (`grep` for `ProxyHeaders`/`X-Forwarded-For`/`X-Real-IP` returned nothing) — the rate limiter's `request.client.host` key is the real socket peer, not a spoofable header.

---

## A08 — Software & Data Integrity Failures

**Threat model**: Single-user Electron desktop app. Backend binds 127.0.0.1:8765. No multi-user/remote/LAN scenarios in scope. Severity judged against this model.

Status: IN PROGRESS

---

## Findings

### A08-1: Auto-update pipeline ships unsigned binaries with code-signature verification explicitly disabled
- **Severity**: HIGH
- **OWASP Category**: A08
- **Location**: `desktop/package.json:76-101` (build config), `desktop/main.js:508-606` (updater wiring), `.github/workflows/build-release.yml:386-433` (release job)
- **Status**: NEW
- **Description**: Auralis ships `electron-updater` (`desktop/package.json:33`) wired to a real auto-update flow in `desktop/main.js` (checks on startup, prompts the user, downloads, and calls `autoUpdater.quitAndInstall()`). This is the single code-execution-on-update path for the app. Across all three build configs there is no code signing:
  - No `CSC_LINK`/`CSC_KEY_PASSWORD`/`certificateFile`/`certificatePassword` anywhere in `desktop/package.json` or any workflow (`grep` for these across `desktop/`, `.github/workflows/` returned nothing).
  - `desktop/package.json:86`: `"win": { ..., "verifyUpdateCodeSignature": false }` — this **explicitly disables** electron-updater's own Authenticode publisher-match check on Windows updates, which is the one integrity check electron-updater can still do for an otherwise-unsigned Windows installer.
  - `desktop/package.json:99-100`: `"mac": { ..., "hardenedRuntime": false, "gatekeeperAssess": false }` — hardened runtime and Gatekeeper assessment are both turned off; there is no `notarize`/`afterSign` hook in the build config or workflow.
  - `.github/workflows/build-release.yml:414-416`: the release job computes `sha256sum` over the built artifacts and ships `SHA256SUMS.txt` **in the same GitHub release as the binaries it hashes**. This is a checksum-of-convenience (detects accidental corruption/incomplete download), not an independent integrity control — it is generated from the same artifacts it "verifies," so it provides no protection if the build/release pipeline itself is compromised (e.g. a compromised maintainer token, a poisoned dependency in `pnpm-lock.yaml`/PyPI, or a hijacked GitHub Actions run).
  - electron-updater's actual integrity check for the auto-update channel is the per-file SHA512 embedded in the auto-generated `latest.yml`/`latest-mac.yml` — again generated by the same unsigned build, hosted at the same GitHub Releases origin. There is no independent, out-of-band trust root (no code signing certificate, no detached GPG signature, no Sigstore/cosign attestation) anywhere in the pipeline.
- **Evidence**:
  ```json
  "win": { "target": [...], "icon": "assets/icon.ico", "verifyUpdateCodeSignature": false },
  "mac": { "target": [...], "hardenedRuntime": false, "gatekeeperAssess": false },
  ```
  ```js
  // desktop/main.js
  autoUpdater.autoDownload = false; // Ask user before downloading
  autoUpdater.autoInstallOnAppQuit = true;
  ...
  autoUpdater.on('update-downloaded', (info) => { ... autoUpdater.quitAndInstall(); ... });
  ```
  ```yaml
  # .github/workflows/build-release.yml
  cd artifacts
  sha256sum -- *.AppImage *.deb *.flatpak *.exe *.dmg > SHA256SUMS.txt
  ```
- **Exploit Scenario**: An attacker who can insert a tampered artifact into the release path (compromised maintainer PAT/GitHub Actions token, a poisoned build dependency, or a compromised CI runner producing a backdoored installer) publishes it as a normal tagged release. Nothing downstream would catch it: there is no code-signing certificate for electron-updater to check (and the one check it could still do, `verifyUpdateCodeSignature`, is explicitly turned off on Windows), Gatekeeper is told not to assess the macOS build, and the SHA256SUMS/latest.yml hashes are computed from the same tampered artifact so they "match." Every installed copy of Auralis that auto-checks for updates (default, on every startup once packaged — `desktop/main.js:598-606`) will offer, download, and (on user confirm or app-quit) silently execute the trojanized installer with the user's OS-level privileges.
- **Impact**: Full code execution on the user's machine via the trusted auto-update channel — the update path is the highest-value integrity control for a desktop app because it is designed to install and run arbitrary code with no additional user scrutiny beyond a version-number dialog.
- **Siblings**: None found — this is the only update mechanism in the codebase (no secondary updater, no plugin-loading path).
- **Suggested Fix**: Obtain and wire in real code-signing certificates for Windows (Authenticode) and macOS (Developer ID + notarization via `afterSign`/`notarize` hook), remove `verifyUpdateCodeSignature: false`, re-enable `hardenedRuntime`/`gatekeeperAssess` on macOS, and treat `SHA256SUMS.txt` as a convenience checksum only — not a substitute for signing. If certificates are not affordable/available yet, at minimum document this as a known, accepted risk in the release process rather than leaving it implicit.

---

### A08-2: Rust `Cargo.lock` untracked for the shipped DSP cdylib (verified, already filed)
- **Severity**: n/a (cross-reference only, not re-filed)
- **OWASP Category**: A08 (supply-chain/build integrity)
- **Location**: `vendor/auralis-dsp/Cargo.lock` (gitignored at `.gitignore:183,185`)
- **Status**: Existing: #4531 (OPEN, filed HIGH — "Cargo.lock is gitignored for a cdylib that ships in the desktop installer; no rust-toolchain pin")
- **Description**: Verified against the current tree: `git ls-files vendor/auralis-dsp/Cargo.lock` returns nothing (untracked), and `.gitignore:183` (`vendor/auralis-dsp/Cargo.lock`) plus `:185` (`vendor/**/Cargo.lock`) confirm it is deliberately excluded. This means every CI build and every developer build resolves Rust dependency versions independently at build time for a native module (`vendor/auralis-dsp`) that ends up inside the signed(-should-be) desktop installer — a classic reproducible-build/supply-chain integrity gap (matches the project's own memory note: this exact gap caused a real ndarray 0.15/0.16 version-conflict bug that went undetected until the 2026-07-18 desktop pipeline restoration). Already tracked as #4531; not re-filed here.
- **Siblings**: `dtolnay/rust-toolchain@stable` (floating channel, not a pinned toolchain version) in all three OS build jobs of `build-release.yml` — already noted under the A05 report (unpinned third-party GitHub Actions); not re-filed here either.

---

### A08-3: Sidecar (.25d) fingerprint files are trusted on size+mtime match with no content-hash or value-range validation
- **Severity**: MEDIUM
- **OWASP Category**: A08
- **Location**: `auralis/library/sidecar_manager.py:76-173` (`is_valid`), `:175-195` (`read`), `:267-293` (`get_fingerprint`); consumed at `auralis/services/fingerprint_extractor.py:117-135`
- **Status**: NEW
- **Description**: `.25d` sidecar files are explicitly designed to be "portable, travel with audio file" (docstring at `sidecar_manager.py:10`) and are treated as authoritative when present and "valid" — `fingerprint_extractor.py` skips the expensive real analysis entirely and loads the sidecar's numbers directly (`is_valid()` → `get_fingerprint()` → used as the track's 25D fingerprint). `is_valid()`'s checks are:
  1. `format_version`/`fingerprint_algorithm_version` string equality (line 110-121)
  2. audio file `size_bytes` and `modified_at` (mtime) match (line 126-138) — the code's own comment says: *"Optionally verify checksum (expensive, only if explicitly requested)... For now, size + mtime is sufficient for validation"* (line 140-141) — i.e. there is **no content hash** of the audio file, only size+mtime, both of which are trivially reproducible by whoever authored the sidecar (they control both the audio file and the timestamp they ship it with).
  3. Presence of all `DIMENSION_SCHEMA` keys (line 144-167) — this checks that keys exist, **not that their values are numeric or in a sane range**. `read()`/`get_fingerprint()` (lines 175-195, 267-293) then `json.load` the file and return the dict as-is; Python's stdlib `json` module accepts non-standard `NaN`/`Infinity`/`-Infinity` literals by default, and nothing here rejects them or type-checks the 25 dimension values before they are used as the track's fingerprint.
  A downstream guard exists for one specific field: `fingerprint_extractor.py:123` does `int(fingerprint.get('fingerprint_version', 1))`, and if that's non-numeric the whole `extract_and_store` call fails inside its own broad `except Exception` (line 234-236), which fails closed (returns `False`, no crash) — but the 25 actual dimension values have no equivalent guard before being stored/used.
- **Evidence**:
  ```python
  # Optionally verify checksum (expensive, only if explicitly requested)
  # For now, size + mtime is sufficient for validation
  ...
  missing_dimensions = set(DIMENSION_SCHEMA) - fingerprint_keys
  if missing_dimensions:
      warning(...)
      return False
  return True
  ```
- **Exploit Scenario**: A user obtains a music folder from an untrusted third party (torrent, forum share, cloud-synced shared folder) that bundles `track.mp3` alongside a crafted `track.mp3.25d` sidecar whose size/mtime metadata match the shipped audio file (both are trivial for the distributor to set) but whose 25 fingerprint dimensions contain bogus, extreme, or non-numeric values. Auralis's library scan treats the sidecar as valid and authoritative, skipping real analysis, and feeds the attacker-chosen numbers into content-aware processing decisions (recording-type detection, adaptive EQ/mastering tuning) for that track — silently degrading or corrupting the mastering output with no error surfaced to the user, or (for non-numeric/NaN values) causing that track's processing to fail depending on how far downstream code propagates the value before hitting a type/NaN guard (not fully traced end-to-end for this audit; the one traced call site fails closed).
- **Impact**: Data integrity — the audio engine's per-track fingerprint (which drives real-time mastering decisions) can be silently substituted by anyone who can place a file next to the user's music, bypassing the app's own analysis. Confidentiality/availability are not directly affected; worst realistic outcome is corrupted mastering output or a per-track processing failure, not RCE (no `eval`/`pickle`/`yaml.load` in this path — consistent with the A03 agent's tree-wide finding).
- **Siblings**: None found in `auralis/analysis/fingerprint/catalog.py` (a separate SQLite-backed fingerprint catalog, not raw on-disk sidecars) — that path inherits normal DB integrity guarantees and was not flagged.
- **Suggested Fix**: Either (a) compute and store a fast content hash (e.g. first-N-KB + size, or a cheap CRC over the audio stream) at write time and check it at read time instead of relying on size+mtime alone, and/or (b) type/range-validate the 25 dimension values (reject non-finite/non-numeric values) in `is_valid()` before treating the sidecar as authoritative, consistent with the DSP NaN guards already applied elsewhere in the pipeline (see project memory: MEDIUM-severity batch 2026-07-08).

---

---

## A09 — Security Logging & Monitoring Failures

**Threat model**: Single-user Electron desktop app. Backend binds 127.0.0.1:8765. No SIEM/centralized-logging/compliance-audit-trail expectations. Severity judged against this model — most findings here expected to be LOW/informational.

Status: IN PROGRESS

---

## Findings

### A09-1: No security-relevant backend log line survives in the packaged desktop app
- **Severity**: MEDIUM
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/main.py:13-29` (backend logging config), `desktop/main.js:169-226` (process spawn + stdout/stderr handling), `desktop/main.js:1-10` (electron-log setup)
- **Status**: NEW
- **Description**: The backend's own Python logging (`logging.getLogger(__name__)`, configured only by `uvicorn.run(..., log_level="info")` at `main.py:235-239` with no `log_config=` override, no `logging.FileHandler`, no rotation) writes exclusively to stdout/stderr — confirmed by grepping the entire backend tree for `FileHandler`/`log_dir`/`.log` path construction, which returns nothing. This includes every security-relevant log line already present in the codebase: rejected path-traversal attempts (`security/path_security.py`), WebSocket origin rejections (`config/globals.py:92,101`), rate-limit hits (`routers/system.py:341`), and migration-backup failures (`library/migration_manager.py:565-566`).
  The Electron main process spawns the backend with `stdio: ['pipe','pipe','pipe']` (`desktop/main.js:169-181`) and forwards everything through plain `console.log('[Backend]', ...)` / `console.error('[Backend Error]', ...)` (`desktop/main.js:208,216`) — never through the app's own `electron-log` instance (`log.info`/`log.error`). Checked: `desktop/main.js` never calls `log.initialize(...)` and never does `Object.assign(console, log.functions)` (the documented electron-log pattern for capturing `console.*` into the file transport); the only calls to `log.*` in the whole file are the auto-updater's own event handlers (`log.info('Checking for updates...')` etc., lines 514-603). electron-log's `main` module does not patch global `console` automatically on `require()` (verified in `desktop/node_modules/electron-log/src/main/index.js` — no such side effect).
  Net effect: in a packaged build (no attached terminal), the entire backend's log output — including the security-relevant events above — goes to a `console.log`/`console.error` call in the Electron main process that has nowhere durable to land, and is never written to electron-log's on-disk log file. Only the auto-updater's own handful of `log.*` calls persist to disk.
- **Evidence**:
  ```python
  # auralis-web/backend/main.py:23-29
  # NOTE: logging.basicConfig was removed (#3537 / BE-NEW-79). uvicorn.run()
  # installs its own logging configuration with handlers on the root logger...
  logger = logging.getLogger(__name__)
  ...
  uvicorn.run(..., log_level="info")   # no log_config=, no FileHandler anywhere in the tree
  ```
  ```js
  // desktop/main.js:205-217 — full backend log stream, never reaches log.*
  this.pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('[Backend]', output.trim());   // NOT log.info(...)
    ...
  });
  this.pythonProcess.stderr.on('data', (data) => {
    console.error('[Backend Error]', output.trim());  // NOT log.error(...)
  ```
- **Exploit Scenario**: Not an exploit per se — this is a monitoring/diagnosability gap. Concretely: a user hits a rejected path-traversal attempt from a compromised or buggy renderer, or a migration backup silently fails to be created before a destructive migration runs; the backend logs it correctly (`logger.warning`/`logger.error`), but in the shipped app neither the user nor a later support/debug session can retrieve that line — it was never written to any file. The one existing on-disk log (`electron-log`'s `main.log`) only ever contains auto-update lifecycle messages.
- **Impact**: Defeats the purpose of the security-relevant logging that does exist elsewhere in the codebase (path validation rejections, WS origin rejections, migration failures) — for a packaged build there is no forensic trail for any of it. Judged against the single-user desktop threat model (no SIEM/compliance expectation) this is a diagnosability/support gap rather than an active vulnerability, hence MEDIUM not HIGH.
- **Siblings**: None — this is a single, structural gap affecting every backend log line uniformly, not a per-call-site pattern.
- **Suggested Fix**: Either forward backend stdout/stderr through the existing `electron-log` instance (`log.info(output.trim())` / `log.error(output.trim())` instead of `console.log`/`console.error` in `desktop/main.js:208,216`) so it lands in the same rotated, bounded file already used for updates, or configure the Python side to write its own rotating file handler (`logging.handlers.RotatingFileHandler`) under `app.getPath('userData')`/`~/.auralis/` and surface that path in a "Show Logs" UI affordance.

---

### A09-2: Path-validation rejections are logged at roughly half of call sites, silent at the rest
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/security/path_security.py:89-303` (`validate_scan_path`/`validate_file_path`/`validate_user_chosen_directory` — never log on rejection, only `logger.debug` on success); callers: logs `auralis-web/backend/routers/processing_api.py:172,180`, `auralis-web/backend/core/stream_seek.py:117`, `auralis-web/backend/core/stream_normal.py:109`, `auralis-web/backend/core/stream_enhanced.py:113`, `auralis-web/backend/routers/metadata.py:336` vs. silent `auralis-web/backend/routers/settings.py:208`, `auralis-web/backend/routers/metadata.py:130,175,228`, `auralis-web/backend/schemas.py:187`
- **Status**: NEW
- **Description**: `validate_scan_path`/`validate_file_path`/`validate_user_chosen_directory` in `path_security.py` never log anything when they reject a path (path traversal, outside allowed directories, nonexistent, unreadable) — they only `raise PathValidationError(...)`; the module's only logging call in these functions is `logger.debug(...)` on the *success* path (lines 179, 251, and the equivalent in `validate_user_chosen_directory`). Whether a rejection gets logged at all is therefore entirely up to each caller catching `PathValidationError`. Six call sites do log a `logger.warning(...)` before converting it to an HTTP/WS error response; four do not — they either re-raise as `HTTPException`/`ValueError` with no log call (`settings.py:208`, `metadata.py:130`, `metadata.py:175`, `metadata.py:228`, `schemas.py:187`) or (in `metadata.py:336`'s batch path) do log. A rejected attempt to add a scan folder outside the allowed set, or to fetch/edit metadata for a track whose stored filepath no longer validates, leaves zero trace in the log while returning a 400 to the caller.
- **Evidence**:
  ```python
  # auralis-web/backend/routers/settings.py:208 — no logger call
  except PathValidationError as e:
      raise HTTPException(status_code=400, detail=str(e))
  ```
  ```python
  # auralis-web/backend/routers/processing_api.py:172-174 — logs, for contrast
  except PathValidationError as e:
      logger.warning(f"Invalid input path rejected: {e}")
      raise HTTPException(status_code=400, detail="Invalid or inaccessible input path")
  ```
- **Exploit Scenario**: N/A as an attack (single-user desktop, 127.0.0.1-only backend) — this is a detection gap. If a compromised browser tab, malicious local extension, or buggy third-party app on the same machine probes `/api/settings/scan-folder` or a metadata endpoint with a path-traversal payload, the four silent call sites produce no log line at all, only a 400 response, so there is no way to notice repeated probing after the fact.
- **Impact**: Inconsistent, not absent — half the codebase already does this correctly. Low impact under this threat model since there's no remote attacker and no monitoring/alerting expectation, but it is a real gap in an otherwise-deliberate security-logging pattern (the six sites that do log show this was a conscious pattern, just not applied uniformly).
- **Siblings**: All five silent call sites listed above share the identical `except PathValidationError as e: raise HTTPException(...)` / `raise ValueError(...)` shape with no `logger.warning` in between.
- **Suggested Fix**: Move the `logger.warning(f"Path validation rejected: {e}")` call into `path_security.py` itself (at the raise site, or via a small wrapper) so every caller gets it for free regardless of whether they remember to log before re-raising — removes the need to keep four/ten call sites in sync by hand.

---

### A09-3: Residual absolute-path logging at INFO level (partial gap in #4366/#4376 fix)
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis/library/migration_manager.py:507,563`, `auralis/analysis/fingerprint/fingerprint_service.py:209`, `auralis/cli/fetch_artwork.py:150`
- **Status**: Existing: #4366 / #4376 (CLOSED) — verified fix is real but incomplete; not a full regression (the great majority of call sites checked were already fixed — see `chunked_processor.py:589,707` and `mastering_target_service.py` which correctly log only `Path(...).name` at INFO), so this is filed as a residual gap rather than "Regression of #4366"
- **Description**: The prior audit's fix for "absolute filesystem paths logged at INFO/DEBUG" is verified present and effective at most call sites — `security/path_security.py:176-179,249-251` explicitly moved its path logging to `DEBUG` specifically citing this class of issue (`#3844`, same root cause), and most `logger.info(f"...")` calls across `chunked_processor.py`/`mastering_target_service.py` now log `Path(x).name` instead of the full path. However a handful of sites still log the full absolute path at INFO:
  - `migration_manager.py:507`: `logger.info(f"✅ Database restored from: {backup_path}")`
  - `migration_manager.py:563`: `logger.info(f"Created backup: {backup_path}")`
  - `fingerprint_service.py:209`: `logger.info(f"Discarding stale DB fingerprint (band-pct sum != 1): {filepath}")`
  - `fetch_artwork.py:150` (CLI script): `logger.info(f"Loading library from: {library_path}")`
- **Exploit Scenario**: None under this threat model — the user's own home-directory layout is not a secret from the user themselves (single-user desktop, no multi-tenant log viewer). Included per the audit brief's request to verify #4366/#4376 against the current tree.
- **Impact**: Informational. No confidentiality boundary is crossed (the app only ever runs as the one user whose paths appear in its own logs), but it is a real, small inconsistency versus the stated fix.
- **Siblings**: None beyond the four listed.
- **Suggested Fix**: For consistency with the already-established pattern (`path_security.py`'s DEBUG-level rationale), downgrade these four to DEBUG or log `Path(x).name`/`Path(x).parent.name` instead of the full path.

---

### A09-4: electron-log file transport default file mode is 0o666 (upstream default, informational only)
- **Severity**: LOW (informational)
- **OWASP Category**: A09
- **Location**: `desktop/node_modules/electron-log/src/node/transports/file/index.js:40` (`writeOptions: { flag: 'a', mode: 0o666, encoding: 'utf8' }`); resolved at runtime via `app.getPath('logs')` (`NodeExternalApi.js:20,105` — `<userData>/logs/main.log`)
- **Status**: NEW (verified as upstream library default, not Auralis-authored code; not overridden anywhere in `desktop/main.js`)
- **Description**: The bundled `electron-log@5.4.3` package's default file-transport `writeOptions` request `mode: 0o666` (world read+write before umask) when creating the log file. Auralis does not override this (`desktop/main.js` only sets `log.transports.file.level = 'info'`, never `writeOptions`). In practice the effective on-disk permissions are `0o666 & ~umask`, so on a typical Linux/macOS default umask of `0o022` this resolves to `0o644` (world-readable, owner-writable only) — not actually world-writable in the common case. The log file itself only ever contains auto-update lifecycle messages (see A09-1 — no backend output reaches it), so there is little sensitive content to protect regardless.
- **Exploit Scenario**: On a shared/multi-user machine (out of scope per this app's stated single-user-desktop threat model) another local user could read `~/.config/Auralis/logs/main.log` (or write to it if an unusual umask is in effect). Since the file's content is limited to update-check timestamps/version numbers/errors, the practical value to an attacker is negligible.
- **Impact**: Negligible under the stated threat model — informational only. Confirmed the file lives under the user's own `userData` directory (protected by normal home-directory permissions), not a shared/world-writable location like `/tmp`.
- **Siblings**: None — this is a single upstream library default, not an Auralis code pattern.
- **Suggested Fix**: Not recommended as an action item given the threat model; if desired, `log.transports.file.writeOptions = { mode: 0o600 }` would tighten it at zero cost.

---

### A09-5: `_validate_artwork_url` internal exception swallowing (verified, already filed)
- **Severity**: n/a (cross-reference only, not re-filed)
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/services/artwork_downloader.py:70-95` (`_validate_artwork_url`)
- **Status**: Existing: #4688 (OPEN)
- **Description**: Verified against the current tree: `_validate_artwork_url`'s own `try`/`except` swallows any internal parsing exception into a bare `return False` with no `logger` call inside the function. Note (not previously documented, worth folding into #4688 if it's re-examined): the callers at `artwork_downloader.py:240-242` and `:305-307` do log `logger.warning("Rejecting untrusted ... URL: ...")` whenever the function returns `False` for *any* reason, so a rejection is not entirely silent end-to-end — but the log message is generic ("untrusted domain") regardless of whether the real cause was a genuinely untrusted domain or an unexpected internal exception, so the specific failure reason (per the original #4688 report) is still lost. Not re-filed; marked Existing.
- **Impact/Fix**: See #4688.

---

## Clean / Verified-Good Results (no finding)
- **WebSocket origin validation** (`auralis-web/backend/config/globals.py:87-104`): both the untrusted-origin and empty-Origin-from-non-loopback-host rejection paths call `logger.warning(...)` with the specific reason before closing the connection (code 1008). Model example for A09-2's suggested fix.
- **WebSocket rate limiting** (`auralis-web/backend/websocket/websocket_security.py:88-131`, consumed at `routers/system.py:339-343`): the rate limiter itself doesn't log (returns a tuple), but its sole caller logs `logger.warning(f"Rate limit exceeded for WebSocket {...}: {error_msg}")` before responding — correctly logged end-to-end.
- **Migration backup failure** (`auralis/library/migration_manager.py:560-567`): a failed backup-before-migration is logged at `logger.error` twice ("Failed to create backup" + "Aborting migration - backup failed") and the migration is correctly aborted (`return False`) rather than proceeding — exactly the "fail loudly, don't proceed" pattern the audit brief asked to check for.
- **Migration downgrade path** (`migration_manager.py:387-393`, `542-547`): a DB from a newer schema version than the running app logs `logger.error` with an explicit upgrade-the-application message and refuses to proceed — no silent data loss.
- **`MigrationManager._get_session`** (`migration_manager.py:181-192`) and **`SettingsRepository.add_scan_folder`/`remove_scan_folder`** (`auralis/library/repositories/settings_repository.py:134-183`): both roll back and **re-raise** on exception — not swallowed.
- **Log-injection mitigation** (`auralis/utils/logging.py:24-47`, `sanitize_log_value`): confirmed present and doing real work (control-character escaping, CRLF-forging prevention, length capping) — this is the fix underlying #4363, already fully covered as an A03 finding by another agent; cross-referenced, not re-evaluated here.

---

---

## A10 — Server-Side Request Forgery (SSRF) / Outbound Network Surface

**Scope**: Desktop Electron app, backend bound to 127.0.0.1:8765. Focus: artwork/metadata
fetchers steered by third-party/crowdsourced data, redirect handling, timeouts, size caps,
TLS verification, and Electron's `shell.openExternal`/navigation surface.

Status: COMPLETE

---

## Findings

### A10-1: `shell.openExternal(url)` invoked with zero scheme/URL validation on every renderer-initiated navigation
- **Severity**: MEDIUM (desktop threat model: no remote attacker starts here, but any
  externally-sourced link surfaced in the UI — artist bio links, a compromised third-party
  API response, a crafted playlist/metadata field the user opens — reaches the OS shell
  unfiltered)
- **OWASP Category**: A10 (outbound network surface / URL handling)
- **Location**: `desktop/main.js:331-334` and `desktop/main.js:639-644`
- **Status**: NEW
- **Description**: Electron's `setWindowOpenHandler` is installed twice — once on the main
  window's `webContents` and once globally on `app.on('web-contents-created', ...)` — and
  both handlers do the same thing: call `require('electron').shell.openExternal(url)` with
  the raw `url` from the navigation attempt, then deny the new-window action. There is no
  allowlist of schemes (`https:`/`mailto:` etc.), no denylist of dangerous schemes
  (`file:`, custom protocol handlers registered by other installed apps), and no
  confirmation prompt. Electron's own security guidance explicitly warns against passing
  untrusted URLs to `shell.openExternal` because, depending on OS/protocol-handler
  registrations, it can be used to execute unexpected local behavior (this has produced RCE
  advisories for other Electron apps in the past when the URL was attacker-influenced).
- **Evidence**:
  ```js
  // desktop/main.js:330-334
  this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url);
    return { action: 'deny' };
  });
  ```
  ```js
  // desktop/main.js:638-644
  // Security: Prevent new window creation (Electron 12+ API)
  app.on('web-contents-created', (_event, contents) => {
    contents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });
  });
  ```
  BrowserWindow is otherwise reasonably hardened (`webPreferences: { nodeIntegration: false,
  contextIsolation: true, webSecurity: true }`, `desktop/main.js:309-314`), which makes this
  handler the one weak spot in an otherwise sane config.
- **Exploit Scenario**: Any place in the React UI that renders a `target="_blank"` link or
  calls `window.open()` with a URL taken from external data (artist bio/relation links from
  MusicBrainz, a Discogs/Last.fm field, or any future "visit artist page" feature) causes
  this handler to fire with attacker/crowd-editable input. `shell.openExternal` then hands
  that string straight to the OS (`xdg-open` on Linux, `ShellExecute` on Windows). A
  non-`https:` scheme registered by some other installed program on the user's machine (or a
  `file://` URL) is opened without any check.
- **Impact**: Local file/protocol-handler invocation outside the app's control; on Windows
  historically a vector for command-injection-adjacent bugs in some `ShellExecute` edge
  cases. Bounded by "whatever `xdg-open`/`ShellExecute` will do with a string," which is
  OS/install-dependent — rated MEDIUM rather than HIGH/CRITICAL because it requires the user
  to actually trigger a `window.open()`/blank-target navigation on attacker-controlled data,
  and the app does not currently appear to render arbitrary external links as clickable
  targets from the checked code paths (not fully verified — see Coverage Statement).
- **Siblings**: `desktop/preload.js:25` exposes `openExternal: (url) => ipcRenderer.invoke('open-external', url)`
  to the renderer via `contextBridge`, but **no `ipcMain.handle('open-external', ...)` is
  registered anywhere in `desktop/main.js`** (confirmed: `grep -n "ipcMain.handle" desktop/main.js`
  lists only `select-file`, `select-folder`, `window-minimize`, `window-maximize`,
  `window-close`, `check-for-updates`). That specific IPC channel is dead code — calling
  `window.electronAPI.openExternal(...)` from the renderer would hang/reject since Electron
  has no registered handler for the invoke — so it is not independently exploitable today,
  but it is a landmine: whoever wires up the handler later will most likely copy the same
  unvalidated pattern used in the two call sites above.
- **Suggested Fix**: Validate `url` against an explicit scheme allowlist (`https:`, `mailto:`
  as needed) before calling `shell.openExternal`, and reject everything else; apply the same
  check if/when `ipcMain.handle('open-external', ...)` is ever implemented. Centralize the
  check in one helper so both call sites (and the dead IPC path) share it — currently they
  are three near-duplicate call sites (DRY concern per project convention).

---

### A10-2: `auralis/services/artwork_service.py` stores crowdsourced third-party URLs with zero validation, rendered directly as `<img src>` by the frontend
- **Severity**: MEDIUM (client-side request forgery / local-resource-probing vector via the
  Electron renderer, not classic server-side SSRF — rated against the desktop threat model,
  not a cloud-VPC model)
- **OWASP Category**: A10
- **Location**: `auralis/services/artwork_service.py:95-352` (all three `_fetch_from_*`
  methods and `_fetch_album_from_musicbrainz`); consumed by `auralis/cli/fetch_artwork.py:80-89`;
  stored via `auralis/library/repositories/artist_repository.py:213-238` (`update_artwork`,
  no validation); rendered at `auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx:110-113`
- **Status**: NEW (distinct from the CLOSED #4526, which is about the CSP `img-src`
  allowlist blocking these hosts, not about validating the URL before it is fetched/stored;
  also distinct from OPEN #4688, which is about `_validate_artwork_url`'s swallowed
  exceptions in the **web backend's** `artwork_downloader.py` — this finding is about the
  **separate CLI-path fetcher in `auralis/services/`, which has no equivalent validation
  function at all**)
- **Description**: `ArtworkService._fetch_from_musicbrainz`, `_fetch_from_discogs`, and
  `_fetch_from_lastfm` each extract an image URL from a third-party API response and return
  it verbatim as `artwork_url` with no scheme check, no domain allowlist, and no sanity
  check of any kind — contrast with the sibling implementation
  `auralis-web/backend/services/artwork_downloader.py`, which has an explicit
  `_validate_artwork_url()` domain allowlist specifically because of a prior SSRF fix
  (`#2416`, see that file's own comment at line 49). The MusicBrainz path is the most
  exposed: the returned `image_url` (`artwork_service.py:152`) comes from a `url-rels`
  relation on an MusicBrainz artist entity — **crowdsourced, editable by any MusicBrainz
  account** — so it is attacker-influenced data, not merely "a third-party CDN we trust."
  The caller (`auralis/cli/fetch_artwork.py:86-89`) writes this unvalidated string straight
  into `Artist.artwork_url` via `artist_repository.update_artwork()`
  (`auralis/library/repositories/artist_repository.py:213-238`, no scheme/host check present
  in that method either). The stored value is later rendered directly by the frontend:
  `auralis-web/backend/config/middleware.py:77-95` documents (as a **known, accepted
  limitation** tied to `#4526`) that `Artist.artwork_url` is rendered as a raw `<img src>`
  rather than being proxied/re-validated server-side, and
  `MediaCardArtwork.tsx:110-113` confirms: `<Box component="img" src={artworkUrl} ... />`.
- **Evidence**:
  ```python
  # auralis/services/artwork_service.py:148-157 (_fetch_from_musicbrainz)
  relations = relations_data.get('relations', [])
  for relation in relations:
      if relation.get('type') == 'image':
          url_data = relation.get('url', {})
          image_url = url_data.get('resource')
          if image_url:
              return {
                  'artwork_url': image_url,   # <-- returned with NO validation
                  'source': 'musicbrainz'
              }
  ```
  ```tsx
  // auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx:110-113
  <Box
    component="img"
    src={artworkUrl}
    ...
  />
  ```
  ```python
  # auralis-web/backend/config/middleware.py:88-92 — the project's OWN comment
  # acknowledging the gap:
  # KNOWN LIMITATION: the MusicBrainz case is open-ended by construction — the
  # relation resource is arbitrary editor-supplied data, so an artist whose image
  # relation points somewhere not listed here will still be blocked and fall back
  # to the placeholder.
  ```
- **Exploit Scenario**: An attacker edits (or has already edited, since MusicBrainz is
  public/crowdsourced) the `image` URL relation of a MusicBrainz artist entity that
  corresponds to an artist in the user's local library, pointing it at
  `http://127.0.0.1:8765/api/<some-state-changing-GET-endpoint>`, an internal LAN IP
  (`http://192.168.1.1/...`), or a tracking-pixel host. When the user (or the CLI cron job)
  runs `python -m auralis.cli.fetch_artwork`, the poisoned URL is stored verbatim as
  `artist.artwork_url`. The next time the artist's page renders, the Electron renderer's
  `<img>` tag issues an HTTP GET to that URL — from the user's own machine, with the user's
  LAN-reachable network position — probing whatever is at that address (image-decode
  success/`onError` timing leaks host/port liveness; if pointed at the app's own loopback
  API, it triggers any GET-based side effect that endpoint might have). This is a
  **client-side** SSRF-adjacent primitive (request forgery from the renderer), not a
  server-side one, because nothing in this specific fetcher's flow re-downloads the bytes
  server-side.
- **Impact**: LAN/localhost port-scanning and blind GET-triggering from the user's own
  machine; no direct RCE or file disclosure from this path alone (no `file://` fetch
  observed to succeed — not verified against the actual Electron `webSecurity` behavior for
  sub-resource `file://` loads from an `http://localhost:8765`-origin document; flagged as a
  gap for the Electron/A05 reviewer to confirm). Confidentiality impact is limited to
  "the target learns the user opened the app and hit this URL" (classic tracking-pixel
  leak) plus whatever a local GET-based side effect could do.
- **Siblings**: The Discogs (`artwork_service.py:203`, `cover_image`/`thumb` fields) and
  Last.fm (`artwork_service.py:254`, `image[].#text`) fetchers have the identical pattern —
  return the API-supplied image URL with no validation — though those two APIs are
  centrally-operated (harder for an attacker to poison arbitrary entries than MusicBrainz's
  open wiki-style editing model). The `_fetch_album_from_musicbrainz` Cover Art Archive path
  (`artwork_service.py:333-348`) also returns `caa_response.geturl()` — the final URL after
  following an HTTP redirect via `urllib.request.urlopen` — with no post-redirect validation
  either, though in practice CAA only redirects to `archive.org` CDN hosts.
- **Suggested Fix**: Reuse (or extract into a shared utility, per project DRY guidance) the
  `_validate_artwork_url()` domain-allowlist pattern already proven in
  `auralis-web/backend/services/artwork_downloader.py`, and apply it inside
  `artwork_service.py`'s three `_fetch_from_*` methods before returning `artwork_url` — reject
  or drop URLs that don't match a known-good host list, same as the web backend already does
  for the iTunes/MusicBrainz-CAA path. This closes the gap called out in the middleware.py
  "KNOWN LIMITATION" comment at its actual source (validate/reject at fetch time) rather than
  only mitigating it downstream via CSP `img-src` allowlisting.

---

### A10-3: `_try_itunes()` validates the pre-redirect URL but never re-validates after following the redirect during the actual image download
- **Severity**: MEDIUM
- **OWASP Category**: A10
- **Location**: `auralis-web/backend/services/artwork_downloader.py:296-322`
- **Status**: NEW
- **Description**: `_try_musicbrainz()` (same file, lines 232-253) validates the URL
  **after** following the Cover Art Archive redirect, explicitly commented `"Validate final
  URL after redirects (SSRF mitigation #2576)"` (line 239-240) — this is the correct pattern.
  `_try_itunes()` does the opposite: it validates `artwork_url` (the iTunes search API's
  `artworkUrl100`, edited to request a larger size) **before** issuing the download request,
  then performs `async with session.get(artwork_url) as resp:` with aiohttp's default
  `allow_redirects=True` and never checks `resp.url` after that call. If the iTunes/Apple CDN
  host ever redirects the request elsewhere (a misconfiguration, a compromised edge node, or
  a CDN cache behavior that 3xx's to a different host), the trusted-domain allowlist is
  silently bypassed for this one code path, even though the sibling function two calls above
  it demonstrates the fix is already known and implemented elsewhere in the same file.
- **Evidence**:
  ```python
  # auralis-web/backend/services/artwork_downloader.py:304-322
  # Validate artwork URL against trusted domains (fixes #2416: SSRF mitigation)
  if not _validate_artwork_url(artwork_url):
      logger.warning(f"Rejecting untrusted artwork URL: {artwork_url!r}")
      return None

  # Download artwork (size-limited, #2576)
  async with session.get(artwork_url) as resp:
      if resp.status != 200:
          return None
      content_length = resp.content_length or 0
      if content_length > _MAX_ARTWORK_BYTES:
          logger.warning(f"iTunes artwork too large: {content_length} bytes")
          return None
      artwork_data = await resp.content.read(_MAX_ARTWORK_BYTES + 1)
      # <-- no `_validate_artwork_url(str(resp.url))` check here, unlike
      #     _try_musicbrainz's equivalent step at lines 239-242
  ```
  Compare to the correct pattern immediately above in the same file:
  ```python
  # auralis-web/backend/services/artwork_downloader.py:235-242 (_try_musicbrainz)
  async with session.get(coverart_url, headers=headers) as resp:
      if resp.status != 200:
          return None
      # Validate final URL after redirects (SSRF mitigation #2576)
      if not _validate_artwork_url(str(resp.url)):
          logger.warning(f"Rejecting untrusted MusicBrainz redirect: {resp.url!r}")
          return None
  ```
- **Exploit Scenario**: Requires the ability to make `is1-ssl.mzstatic.com` (or any allowlisted
  `*.mzstatic.com` host) issue an HTTP redirect to an attacker-controlled or internal host at
  the moment of download (e.g., via a compromised CDN edge, a cache-poisoning bug on Apple's
  side, or DNS interference). Given this requires compromising/abusing a well-known,
  centrally-operated CDN rather than attacker-editable data, the practical likelihood is low
  — this is an internal-consistency gap, not a directly demonstrated live exploit path.
- **Impact**: If triggered, bypasses the `_TRUSTED_ARTWORK_DOMAINS` allowlist for the
  download step, allowing the app to fetch and persist to `~/.auralis/artwork/` bytes from
  an arbitrary redirect target (subject only to the 5MB size cap, which does still apply).
- **Siblings**: None beyond the `_try_musicbrainz`/`_try_itunes` asymmetry itself.
- **Suggested Fix**: Add the same `if not _validate_artwork_url(str(resp.url)): return None`
  check immediately after the `session.get(artwork_url)` call in `_try_itunes`, mirroring
  `_try_musicbrainz` exactly, so the two sibling functions share one validated pattern
  instead of diverging.

---

### A10-4: No explicit timeout on the shared `aiohttp.ClientSession` in the (actively used) web-backend artwork downloader
- **Severity**: LOW
- **OWASP Category**: A10
- **Location**: `auralis-web/backend/services/artwork_downloader.py:136-142`
- **Status**: NEW
- **Description**: `_get_session()` constructs `aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=4, ttl_dns_cache=300))` with no `timeout=` argument, so every request on this
  session falls back to aiohttp's library default (`ClientTimeout(total=300)`, i.e. 5
  minutes). None of the four `session.get(...)` call sites in this file
  (`artwork_downloader.py:220, 235, 286, 310`) pass a per-request `timeout=` override either.
  This is the fetcher actually wired into the running backend (used for automatic album
  artwork backfill), unlike the CLI-only `artwork_service.py`, which explicitly sets a 10s
  timeout (`ArtworkService.__init__(..., timeout: int = 10)`,
  `auralis/services/artwork_service.py:42-54`, applied via `timeout=self.timeout` at every
  `urlopen()` call). A slow-responding (or slow-loris-style) upstream host can tie up one of
  the pool's 4 connections for up to 5 minutes per request.
- **Evidence**:
  ```python
  # auralis-web/backend/services/artwork_downloader.py:136-142
  def _get_session(self) -> aiohttp.ClientSession:
      """Return the shared HTTP session, creating it on first use."""
      if self._session is None or self._session.closed:
          self._session = aiohttp.ClientSession(
              connector=aiohttp.TCPConnector(limit=4, ttl_dns_cache=300)
          )
      return self._session
  ```
- **Exploit Scenario**: Not a remote-attacker scenario under this threat model (the
  allowlisted hosts are fixed, reputable CDNs) — this is a resilience/DoS-hardening gap
  rather than an attacker-reachable primitive: a transient slow response from
  MusicBrainz/iTunes/Cover-Art-Archive during a bulk artwork backfill can hold a connection
  open for up to 5 minutes instead of failing fast, degrading backfill throughput.
- **Impact**: Worst case, a hung backfill worker for up to 5 minutes per stalled request;
  bounded by the 4-connection pool limit, so not a full outage.
- **Siblings**: None — the CLI-path `artwork_service.py` already does this correctly (10s
  explicit timeout).
- **Suggested Fix**: Pass an explicit `timeout=aiohttp.ClientTimeout(total=10)` (matching the
  CLI fetcher's convention) to the `ClientSession` constructor.

---

### A10-5: Unbounded response-body reads in `auralis/services/artwork_service.py`'s `urlopen()` calls
- **Severity**: LOW
- **OWASP Category**: A10
- **Location**: `auralis/services/artwork_service.py:123-124, 144-145, 194-195, 246-247, 321-322`
- **Status**: NEW
- **Description**: Every JSON API call in this file does `response.read().decode('utf-8')`
  with no cap on the number of bytes read — contrast with
  `auralis-web/backend/services/artwork_downloader.py`, which enforces `_MAX_ARTWORK_BYTES`
  (5 MB) explicitly for exactly this reason (`#2576`). MusicBrainz/Discogs/Last.fm JSON
  responses are normally small and bounded by the `limit=1` query parameter, so this is a
  low-severity defense-in-depth gap rather than a demonstrated memory-exhaustion path — none
  of the three services are attacker-operatable in a way that lets an attacker directly
  control response size (they are centrally-operated APIs), and this fetcher is a manually
  invoked CLI script, not a long-running server process.
- **Evidence**:
  ```python
  # auralis/services/artwork_service.py:123-124
  with urllib.request.urlopen(req, timeout=self.timeout) as response:
      data = json.loads(response.read().decode('utf-8'))
  ```
  (repeated at lines 144-145, 194-195, 246-247, 321-322 with different variable names)
- **Exploit Scenario**: Would require MusicBrainz, Discogs, or Last.fm to be compromised or
  MITM'd (TLS should prevent the latter) to return an oversized body; not independently
  attacker-triggerable.
- **Impact**: Memory growth proportional to a malicious/compromised upstream response; bounded
  in practice by the centrally-operated nature of the three APIs.
- **Siblings**: None in this file; the sibling `artwork_downloader.py` already caps this.
- **Suggested Fix**: Wrap the `response.read()` calls with a size cap (e.g.
  `response.read(MAX_BYTES + 1)` and reject if the result exceeds the cap), or migrate this
  CLI script onto the same `_MAX_ARTWORK_BYTES`-style helper for consistency.

---

## Outbound network surface inventory

| Client | File | URL source | Timeout | Size cap | Redirect policy | TLS verify |
|---|---|---|---|---|---|---|
| `urllib.request` (MusicBrainz artist/relations search) | `auralis/services/artwork_service.py:120-124, 141-145` | Hardcoded MusicBrainz API host + URL-encoded artist name (user's local library data) | Explicit, `self.timeout` (default 10s) | **None** (A10-5) | Default urllib (follows redirects, no re-validation) | Default (verified, no `context=`/`ssl=False` override seen) |
| `urllib.request` (MusicBrainz `image` relation URL — returned, not re-fetched here) | `auralis/services/artwork_service.py:152-157` | **Crowdsourced/attacker-editable** MusicBrainz relation data | N/A (URL only, not fetched by this module) | N/A | N/A | N/A |
| `urllib.request` (Discogs search) | `auralis/services/artwork_service.py:190-195` | Hardcoded Discogs API host | 10s | None | Default urllib | Default |
| `urllib.request` (Last.fm artist info) | `auralis/services/artwork_service.py:243-247` | Hardcoded Last.fm API host | 10s | None | Default urllib | Default |
| `urllib.request` (MusicBrainz release-group search) | `auralis/services/artwork_service.py:318-322` | Hardcoded MusicBrainz API host | 10s | None | Default urllib | Default |
| `urllib.request` (Cover Art Archive `/front` redirect resolution) | `auralis/services/artwork_service.py:334-343` | Hardcoded `coverartarchive.org` host; final resolved URL returned **unvalidated** | 10s | N/A (headers/URL only, body never read) | Follows redirect automatically, **final URL not validated** (A10-2 sibling note) | Default |
| `aiohttp.ClientSession` (MusicBrainz release search) | `auralis-web/backend/services/artwork_downloader.py:210-230` | Hardcoded MusicBrainz API host | **None explicit** — aiohttp default 300s (A10-4) | N/A (JSON only) | Default aiohttp (follows redirects) | Default (verified) |
| `aiohttp.ClientSession` (Cover Art Archive front image) | `auralis-web/backend/services/artwork_downloader.py:233-253` | Hardcoded `coverartarchive.org`; final URL re-validated post-redirect via `_validate_artwork_url` | 300s default | 5 MB (`_MAX_ARTWORK_BYTES`), enforced via `content_length` check + capped `.read()` | Follows redirect, **re-validates final URL** (correct pattern) | Default |
| `aiohttp.ClientSession` (iTunes search) | `auralis-web/backend/services/artwork_downloader.py:279-297` | Hardcoded `itunes.apple.com` host | 300s default | N/A (JSON only) | Default aiohttp | Default |
| `aiohttp.ClientSession` (iTunes artwork download) | `auralis-web/backend/services/artwork_downloader.py:305-322` | iTunes-API-supplied `artworkUrl100`, validated pre-redirect via `_validate_artwork_url` against `_TRUSTED_ARTWORK_DOMAINS` | 300s default | 5 MB, enforced | Follows redirect, **does NOT re-validate final URL** (A10-3) | Default |
| `shell.openExternal` | `desktop/main.js:332, 641` | Any `window.open()`/`target=_blank` navigation URL from renderer content | N/A | N/A | N/A | N/A — **no scheme/host validation at all** (A10-1) |
| `ipcRenderer.invoke('open-external', url)` | `desktop/preload.js:25` | Renderer-supplied `url` param | N/A | N/A | N/A | Dead code — no `ipcMain.handle('open-external', ...)` registered (A10-1 sibling note) |
| `<img src={artworkUrl}>` | `MediaCardArtwork.tsx:112`, and other art-rendering components (Album/Track use a same-origin `/api/.../artwork` path per `middleware.py` comment; only `Artist.artwork_url` is raw-external) | `Artist.artwork_url`, populated by the above fetchers | N/A (browser default) | N/A | Browser-native | N/A |
| Backend artwork GET route (serves cached bytes) | `auralis-web/backend/routers/artwork.py:270-326` | N/A — serves locally cached files | N/A | N/A | N/A | N/A — **clean**: `media_type` derived from `mimetypes.guess_type`/magic-byte-derived extension, falls back to `image/jpeg`, never serves `text/html`/JS mimetypes |

---
<!-- COVERAGE-APPEND -->


### A04 — Insecure Design / Resource Exhaustion by Malicious Input — Coverage Statement

**Examined:**
- `auralis/io/unified_loader.py`, `auralis/io/loader.py`, `auralis/io/loaders/soundfile_loader.py`, `auralis/io/loaders/ffmpeg_loader.py`
- `auralis-web/backend/core/chunked_processor.py`, `chunk_boundaries.py`, `chunk_cache.py`, `chunk_cache_manager.py`, `stream_chunk_ops.py`, `stream_seek.py`, `stream_enhanced.py`, `stream_normal.py`, `stream_prefetch.py`, `streamlined_worker.py`, `audio_stream_controller.py`
- `auralis-web/backend/cache/manager.py`, `cache/adapter.py`, `cache/__init__.py`, `cache/endpoints.py` (skimmed)
- `auralis/services/fingerprint_queue.py`, `auralis/services/fingerprint_extractor.py`, `auralis/services/resizable_semaphore.py`
- `auralis/analysis/fingerprint/normalizer.py`, `knn_graph.py` (targeted grep for unbounded loops)
- `auralis/library/scanner/file_discovery.py`, `scanner.py`, `batch_processor.py`
- `auralis/library/artwork.py`, `auralis-web/backend/routers/artwork.py`
- `auralis/player/queue_controller.py`, `auralis/player/components/queue_manager.py`
- `auralis-web/backend/routers/pagination.py`, `library.py`, `playlists.py`, `albums.py`, `artists.py`, `tracks.py`, `fingerprint_queue.py` (limit params), `processing_api.py` (limit params)
- `auralis-web/backend/config/limits.py`, `config/app.py`, `config/routes.py`, `config/startup.py`, `config/background_workers.py`
- `auralis-web/backend/core/job_worker.py`
- `auralis-web/backend/ws_handlers/playback_commands.py`, `playback_control.py` (seek/position validation)
- `/tmp/audit/security/issue_titles.txt` (dedup grep across all 400 titles)

**Not reached:**
- `auralis/services/artwork_downloader.py` and `auralis/cli/fetch_artwork.py` (remote artwork fetch — network-sourced image decode was not traced end-to-end for a decompression-bomb path independent of the ingestion-time `_bound_dimensions` guard)
- `auralis-web/backend/services/audio_content_predictor.py` beyond a `chunk_idx` grep — its internal chunk-loading/feature-extraction loop was not read for algorithmic worst-case behavior
- `auralis/analysis/fingerprint/analyzers/`, `metrics/`, `utilities/` subdirectories (25D fingerprint computation internals) — not read line-by-line for an actual infinite-loop/superlinear-blowup bug triggerable by adversarial audio content; A04-1 is filed on the absence of a timeout wrapper, not on a confirmed hang bug inside the DSP math itself
- `auralis-web/backend/services/queue_service.py` (661 lines) — only grepped, not read in full, for the REST-facing queue-mutation endpoints layered on top of `QueueManager`
- `auralis-web/backend/cache/endpoints.py`, `cache/monitoring.py` — not read beyond confirming they exist and are exported
- WebSocket frame/message size limits at the Starlette/uvicorn transport level (treated as out of scope: same-origin Electron renderer, not a remote-attacker surface per the threat model)
- `auralis/library/database.py` migration path and `auralis/library/migration_manager.py` for resource exhaustion during a pathological/huge migration
- Desktop/Electron-specific resource limits (e.g. renderer memory caps) — this audit stayed within the Python backend and core engine as scoped

### A05 — Security Misconfiguration + Electron Hardening — Coverage Statement

**Examined:**
- `desktop/main.js` (full, 643 lines), `desktop/preload.js` (full, 49 lines), `desktop/error.html` (full), `desktop/package.json` (webPreferences, Electron version, build config, extraResources)
- `auralis-web/backend/main.py` (host/bind, static-file mounting, dev-mode branch)
- `auralis-web/backend/config/app.py` (docs_url/redoc_url/openapi_url gating)
- `auralis-web/backend/config/middleware.py` (`SecurityHeadersMiddleware` — full header set and CSP directive text; `RateLimitMiddleware` header only, not re-audited per A07 ownership note)
- `auralis-web/backend/config/limits.py` (full) and its two enforcement call sites in `routers/files.py` and `routers/processing_api.py`
- `auralis-web/backend/routers/errors.py` (full)
- `auralis-web/backend/routers/player.py` (sampled `detail=str(e)` call sites), `routers/settings.py` (one call site)
- `auralis-web/backend/config/startup.py` (temp-dir cleanup on lifespan startup, `chunk_dir`/`reclaim_leftover_stream_temps`)
- `auralis-web/backend/core/chunked_processor.py`, `core/processing_engine.py`, `core/stream_normal.py`, `cache/adapter.py`, `core/encoding/atomic_io.py`, `core/encoding/wav_encoder.py`, `routers/processing_api.py`, `routers/files.py`, `routers/artwork.py` (all `tempfile`/`mkstemp`/`mkdir`/`chmod` call sites)
- `auralis/library/database.py` (`~/.auralis` directory + DB file permission handling, for the chmod-pattern contrast)
- `auralis-web/frontend/index.html` (full — CSP meta tag absence, external font/CDN references)
- `launch-auralis-web.py` (bind-address grep)
- `.env` tracking status via `git ls-files`, `git check-ignore -v`, `git log --all -- .env`; `git ls-files` full-tree grep for secret/credential/key/pem/token filenames
- All 7 files in `.github/workflows/`
- `/tmp/audit/security/issue_titles.txt` (full grep pass for dedup keywords) and `docs/audits/AUDIT_SECURITY_2026-07-12.md` (dedup-only read, targeted grep + one section read around line 301)

**Not reached:**
- `desktop/assets/` and `desktop/node_modules/` contents were not enumerated/audited (only referenced by path from `main.js`/`package.json`; no separate review of bundled dependencies' own postinstall scripts or transitive supply-chain risk within `desktop/node_modules`).
- No live/dynamic testing was performed anywhere in this audit (no actual Electron app launch, no live XSS injection attempt to confirm or refute the hypothetical injection point referenced in A05-5's exploit scenario, no live `will-navigate` proof-of-concept). All findings are static-code-reading based.
- Did not read `auralis-web/backend/config/startup.py` in full (only the lifespan/temp-dir-cleanup section, offset 250-290) — other startup-time configuration in that file beyond temp-dir handling was not reviewed for this dimension.
- Did not review `auralis-web/frontend/` React component tree for actual unsanitized-HTML sinks (e.g. `dangerouslySetInnerHTML`, `innerHTML` assignment) that would concretely realize the XSS hypothesis underlying A05-5/A05-7 — that is frontend-audit-dimension territory; this pass only established that the CSP and Electron-side backstops are weaker than they could be, not that a live injection point exists.
- Did not review `vendor/auralis-dsp/` (Rust) build/CI supply chain beyond `rust-audit.yml`'s trigger/permissions shape — no review of the Rust dependency audit's actual findings (that's `audit-deprecation`/dependency-audit territory, not A05 misconfiguration).
- Did not review `auralis-web/backend/config/` files other than `app.py`, `middleware.py`, `limits.py` (e.g. any other config submodules present in that directory were not enumerated).
- Did not attempt to verify #4351/#4353/#4350 (the "prior CLOSED issues to verify-only" list) beyond what was incidentally confirmed (bind address, docs/openapi gating); no dedicated pass was made to re-read the historical fix diffs for those three issue numbers specifically.

### A06 — Vulnerable and Outdated Components — Coverage Statement

**Examined:**
- `requirements.txt`, `requirements-desktop.txt`, `auralis-web/backend/requirements.txt`, `pyproject.toml` (full contents read)
- `.venv/bin/python -m pip list` (actual installed versions, compared against manifest pins)
- `.venv/bin/python --version` (3.14.0)
- `.github/workflows/requirements-pin-guard.yml` (full contents read)
- `.github/workflows/rust-audit.yml` (full contents read, 57 lines)
- `.github/workflows/backend-tests.yml` (grepped for install command)
- `.github/workflows/build-release.yml` (partially read — prepare + build-linux jobs)
- `.github/workflows/frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml` (listed, not deep-read)
- `.github/dependabot.yml` (confirmed absent)
- CodeQL workflow presence (confirmed absent via grep)
- `vendor/auralis-dsp/Cargo.toml` (full contents read)
- `vendor/auralis-dsp/Cargo.lock` tracked status (`git ls-files` — confirmed untracked) and `.gitignore` lines 183/185
- `auralis/io/loaders/ffmpeg_loader.py` (grepped for version-check logic, `MINIMUM_FFMPEG_VERSION`)
- `ffmpeg -version` on the dev machine (8.0.1-3ubuntu2 — explicitly noted as non-representative of shipped/end-user ffmpeg)
- `desktop/package.json` (full contents read, incl. `publish` config)
- `desktop/main.js` (grepped for `BrowserWindow` security flags and `autoUpdater` usage)
- `desktop/pnpm-lock.yaml`, `auralis-web/frontend/pnpm-lock.yaml` (grepped for specific package resolutions)
- `auralis-web/frontend/package.json` (dependencies/devDependencies read)
- `pnpm audit --json` run successfully (network-reachable) in both `desktop/` and `auralis-web/frontend/` — full JSON captured and analyzed
- `auralis/library/artwork.py`, `auralis-web/backend/routers/artwork.py` (grepped for `Image.open`/`MAX_IMAGE_PIXELS`/dimension-bounding)
- `grep -rn "zipfile|tarfile|gzip|zstandard|shutil.unpack"` across `auralis/` and `auralis-web/backend/`
- `grep -rn "useNavigate("` across `auralis-web/frontend/src`
- `grep -rhn "uses:"` across all 6 `.github/workflows/*.yml` files (Action pinning survey)
- `/tmp/audit/security/issue_titles.txt` (grepped for dedup keywords) and `docs/audits/AUDIT_SECURITY_2026-07-12.md` (grepped for prior A06 finding text)

**Not reached:**
- `pip-audit` was NOT run (not installed in `.venv`; instructions say only run if already installed, do not install). No CVE-database cross-check was performed beyond training knowledge, which is why Pillow 12.3.0 / numpy 2.3.5–2.4.6 / scipy 1.16.3–1.18.0 / mutagen 1.47.0 / soundfile 0.13.1–0.14.0 are NOT asserted to have or lack specific CVEs — these versions are recent enough that no confident claim is made either way.
- `cargo audit` was NOT independently re-run locally against `vendor/auralis-dsp/Cargo.lock` to verify the RUSTSEC-2025-0020 / RUSTSEC-2026-0177 non-reachability claims in `rust-audit.yml`'s comments — reported as the workflow author's documented rationale, not independently re-verified against the Rust source in this pass.
- `mutants/pyproject.toml` (a second, mutation-testing-scoped pyproject file found during the initial `find`) was not examined — out of the shipped/runtime dependency surface.
- `.github/workflows/frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml` were listed but not read line-by-line.
- Windows/macOS `build-release.yml` jobs (only the `prepare` and `build-linux` jobs were read in detail) — not checked for platform-specific bundling of any parser/runtime binaries.
- No attempt was made to fetch the full upstream advisory text for `app-builder-lib`'s AppImage search-path issue (A06-4) beyond what `pnpm audit`'s local advisory cache provided; the MEDIUM (not HIGH) severity on that finding reflects this residual uncertainty.
- `desktop/resources/` was checked only for an `ffmpeg` binary (absent) — not exhaustively enumerated for other bundled third-party binaries that might carry their own CVE surface.

### A07 — Identification & Authentication Failures / Local API Surface — Coverage Statement

**Examined:**
- `auralis-web/backend/websocket/websocket_security.py` (full read)
- `auralis-web/backend/config/globals.py` (ConnectionManager, origin allowlist, `build_ws_origins`)
- `auralis-web/backend/config/middleware.py` (full read — all 5 middleware classes, CORS/TrustedHost config, `setup_middleware` ordering)
- `auralis-web/backend/config/limits.py` (full read)
- `auralis-web/backend/config/app.py` (`is_dev_mode`, docs-exposure gating context)
- `auralis-web/backend/ws_handlers/connection.py` (`setup_connection`, `dispatch_message` header)
- `auralis-web/backend/routers/system.py` (`/ws` route wiring, lines 280-360)
- `auralis-web/backend/routers/dependencies.py` (shared dependency guards — availability-only, no auth/origin dependency exists)
- Route inventory across all files in `auralis-web/backend/routers/*.py` (grep for every `@router.get/post/put/delete/patch`, with signatures read for every POST/PUT/DELETE route to classify body-vs-query-only): `player.py`, `library.py`, `library_scan.py`, `processing_api.py`, `settings.py`, `similarity_graph.py`, `similarity.py`, `playlists.py`, `artwork.py`, `cache_streamlined.py`, `fingerprint_queue.py`, `metadata.py`, `tracks.py`, `files.py`, `enhancement.py`
- `desktop/main.js` (backend spawn/env handling, port fixed at 8765, no token, `env: {...process.env}` inheritance, `--dev` argv usage)
- FastAPI's installed source (`fastapi/routing.py` v0.128.0, lines ~260-330) to verify the JSON-vs-form/text-plain body-parsing content-type behavior underlying A07-2
- `/tmp/audit/security/issue_titles.txt` grepped for: rate limit, CSRF, DNS rebinding, WebSocket origin, DEV_MODE/env var, resource leak, queue clear/next/previous track — no open duplicate found for any finding above; #4353 and #4350 confirmed still fixed (cited, not re-filed)

**Not reached:**
- `auralis-web/backend/ws_handlers/messages.py`, `playback_commands.py`, `playback_control.py` beyond grepping their imports/signatures — did not do a line-by-line review of every WS message handler's internal state-mutation logic (e.g. whether `play_enhanced`/`seek`/`stop` handlers themselves do additional validation) — that is more an A01 (broken access control) concern than A07 and was intentionally left to that dimension.
- No live empirical test was run against a running backend instance beyond the one datum already supplied in the brief (78-request rate-limit test) — the backend was not started for this audit (instructions: read-only, do not start services).
- Did not review `auralis-web/backend/routers/enhancement.py`, `metadata.py`, `playlists.py`, `artwork.py` route *bodies* in full depth beyond signature classification for the CSRF inventory — deeper business-logic review of those handlers (e.g. authorization-adjacent checks inside them) is out of scope for A07.
- Did not audit the Electron `preload.js` / renderer IPC surface for a separate desktop-local privilege boundary (out of scope — this dimension focused on the HTTP/WS network surface per the brief).
- Follow-up check completed during this audit: every router under `auralis-web/backend/routers/` was enumerated by decorator (`grep "@router\."`) — `albums.py`, `artists.py`, `health.py`, `fingerprint_status.py` GET routes and `system.py` (only route is the `/ws` websocket) were all individually checked; every GET route across the full router directory is read-only, no GET-triggered state change exists anywhere in the backend. (No `genres.py` file exists in this codebase.)

### A08 — Software & Data Integrity Failures — Coverage Statement

**Examined:**
- `desktop/main.js` (full auto-updater wiring, lines ~1-620), `desktop/package.json` (full build config)
- `.github/workflows/build-release.yml` (full file, all four jobs: prepare, build-linux, build-windows, build-macos, create-release)
- `.github/workflows/` directory listing (backend-tests.yml, frontend-test.yml, frontend-typecheck.yml, lockfile-guard.yml, requirements-pin-guard.yml, rust-audit.yml — not opened in detail beyond confirming they exist; not release/signing-relevant)
- `auralis/library/migration_manager.py` (full file, 587 lines): `MigrationManager.apply_migration`, `migrate_to_latest`, `get_current_version`, `backup_database`, `restore_database`, `check_and_migrate_database`, `migration_lock` — verified backup-before-migrate-or-abort, downgrade-path rejection (current_version > target_version fails loudly), atomic DDL+version-record transaction, dangerous-SQL-keyword blocking (DROP TABLE/DATABASE, unqualified DELETE). No new finding — this subsystem is well-hardened (matches prior audit history of concurrency/backup fixes).
- `auralis/library/sidecar_manager.py` (full file, 378 lines) and its sole consumer `auralis/services/fingerprint_extractor.py` (`extract_and_store`, lines ~92-236)
- `auralis-web/backend/core/chunk_cache.py` (full, 166 lines — pure in-memory LRU, no disk persistence) and `auralis-web/backend/core/chunk_cache_manager.py` (full, 454 lines — `get_cached_fingerprint`/`cache_fingerprint` are in-memory dict-backed, not disk JSON; no on-disk-trust issue found)
- `auralis/library/repositories/settings_repository.py` (full, 184 lines) — settings persisted via SQLAlchemy ORM into SQLite, not raw files; `scan_folders` JSON round-trip via `json.loads`/`json.dumps` on a DB column, exceptions re-raised (not swallowed)
- `auralis/analysis/fingerprint/catalog.py` (skimmed, 182 lines) — SQLite-backed fingerprint catalog, separate from `.25d` sidecars; no raw on-disk JSON trust surface found
- `git ls-files vendor/auralis-dsp/Cargo.lock` (confirms untracked) and `.gitignore:183,185`
- Native-module/relative-path loading: grepped `sys.path.insert`/`sys.path.append`/`ctypes.CDLL`/`LoadLibrary` across `auralis/`, `auralis-web/backend/`, `desktop/main.js` — all hits resolve paths via `os.path.dirname(__file__)`/`Path(__file__).parent...` (the app's own install directory), not a user-writable or attacker-controlled relative path; no finding (single-user desktop app, no privilege boundary crossed)
- Cross-checked `/tmp/audit/security/issue_titles.txt` (400 issues) and `/tmp/audit/security/a05.md` for dedup (Cargo.lock → #4531; unpinned GH Actions → filed under A05, not re-filed) and `docs/audits/AUDIT_SECURITY_2026-07-12.md` (A08-INFO-1, unrelated — audio file/fingerprint integrity noted as accepted risk for single-user desktop, superseded/expanded here re: sidecar value validation)

**Not reached:**
- `auralis/library/migrations/*.sql` — individual migration script contents were not read one-by-one (only the executor/validator in `migration_manager.py` was examined); did not verify every historical migration file is itself well-formed
- Full text of `.github/workflows/backend-tests.yml`, `frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml`, `requirements-pin-guard.yml`, `rust-audit.yml` — only confirmed existence, not contents (out of A08 scope; these are test/lint gates, not release/integrity paths)
- `desktop/preload.js` and the full Electron `contextBridge`/IPC surface beyond the auto-updater handlers — not audited for other integrity-relevant IPC (e.g. arbitrary file-write handlers); only the update-related IPC (`check-for-updates`) was examined
- Windows/macOS installer post-install behavior (NSIS script customizations, DMG background) — `nsis`/`dmg` config blocks in `package.json` were read but not exercised
- Deep trace of how the 25 sidecar fingerprint dimension values flow from `get_fingerprint()` into DSP/mastering decision code (recording-type detector, EQ tuning) to confirm whether a non-finite/malformed value crashes, is silently coerced, or is caught by an existing NaN guard — flagged as a plausible integrity gap (A08-3) but not traced to a definitive runtime outcome
- `auralis/analysis/fingerprint/catalog.py` internals beyond a skim (SQL schema, indices) — deprioritized since it is SQLite-backed, not a raw-file trust surface
- Any Docker/container image build (none exists in this repo per prior audit history — desktop-only distribution)

### A09 — Security Logging & Monitoring Failures — Coverage Statement

**Examined:**
- `auralis/utils/logging.py` (full file, 131 lines) — the core-engine logging facade (`debug`/`info`/`warning`/`error`, `set_log_handler`); confirmed it is a no-op unless a handler is installed via `set_log_handler`, and confirmed no call site in the tree actually installs one (only aliased as `log` in `auralis/__init__.py:38`, never invoked)
- `auralis-web/backend/main.py` (full file) — confirmed `uvicorn.run(..., log_level="info")` with no `log_config=`/file handler, and the `#3537/BE-NEW-79` comment explaining why `basicConfig` was deliberately removed
- `desktop/main.js` (full file, ~620 lines) — auto-updater wiring (see A08-1), backend process spawn/stdout/stderr handling, all `log.*`/`console.*` call sites enumerated
- `desktop/node_modules/electron-log` (`src/main/index.js`, `src/main/initialize.js`, `src/node/createDefaultLogger.js`, `src/node/transports/file/index.js`, `src/node/NodeExternalApi.js`, `src/main/ElectronExternalApi.js`) — verified default file transport `maxSize`/rotation behavior, `writeOptions.mode`, log path resolution (`app.getPath('logs')`), and confirmed no automatic `console` override without an explicit `Object.assign(console, log.functions)` (absent here) or renderer-only `spyRendererConsole` (also absent/unused)
- `auralis-web/backend/security/path_security.py` (full file, 378 lines) — all three validators (`validate_scan_path`, `validate_file_path`, `validate_user_chosen_directory`) read end-to-end
- All 10 call sites of `PathValidationError` across the backend (`grep`-enumerated and individually read): `routers/processing_api.py:172,180`, `core/stream_seek.py:117`, `core/stream_normal.py:109`, `core/stream_enhanced.py:113`, `routers/metadata.py:130,175,228,336`, `routers/settings.py:208`, `schemas.py:187`
- `auralis-web/backend/websocket/websocket_security.py` (rate limiter + message validation, full file skimmed with targeted reads) and its sole caller `routers/system.py:325-354`
- `auralis-web/backend/config/globals.py:75-112` (WebSocket `connect()` — Origin validation and logging)
- `auralis-web/backend/config/middleware.py` — grepped for CORS/origin handling (confirmed standard `CORSMiddleware` usage, no custom rejection logging expected/needed at that layer since Starlette's CORS middleware is a well-understood third-party dependency, not app code)
- `auralis/library/migration_manager.py` (full file, reused from A08 review) — backup-failure logging, downgrade-path logging, session rollback/re-raise
- `auralis/library/repositories/settings_repository.py` (full file, reused from A08 review) — exception re-raise confirmed, not swallowed
- `auralis-web/backend/services/artwork_downloader.py` (`_validate_artwork_url` and its two call sites at lines ~240 and ~305) — verified #4688 still applies as described, plus the caller-side generic-warning nuance noted above
- Targeted greps across `auralis/` and `auralis-web/backend/` for: `RotatingFileHandler`/`TimedRotatingFileHandler`/`maxBytes`/`FileHandler`/`basicConfig` (only hit: `auralis/cli/fetch_artwork.py:26`, a one-shot CLI script, reviewed and found unremarkable); `logger.info(f"..."` interpolating path/home/filepath-shaped values (full result set reviewed, feeding A09-3); `except Exception:` immediately followed by bare `pass` in `security/`, `websocket/`, `config/middleware.py`, `migration_manager.py` (only one hit, in `migration_manager.py:188`, confirmed it re-raises, not swallows)
- `auralis/cli/fetch_artwork.py` (logging setup, lines 1-40)

**Not reached:**
- Full read of `auralis-web/backend/config/middleware.py` beyond the CORS/origin-related greps (360 lines total; the security-headers and caching middleware sections were not read line-by-line)
- `auralis-web/backend/websocket/websocket_protocol.py` (message schema/dispatch) — not examined for logging coverage beyond what `websocket_security.py` and `routers/system.py` already showed
- Every other router in `auralis-web/backend/routers/` (19 total per the codebase map) for the same "does a rejection log" pattern — only the routers that touch `PathValidationError` were checked; routers around auth-adjacent or job/queue rejection paths were not swept
- Frontend-side logging (`auralis-web/frontend/src/**`) — console usage, whether any client-side error gets sent anywhere — entirely out of scope for this pass (A09 was scoped to backend/engine per the audit brief's grep targets)
- Whether Windows/macOS builds behave identically to the Linux assumptions made about `console.log` being a no-op in a packaged, console-less Electron app (verified logically from Node/Electron semantics and the absence of any capture mechanism in the code, but not verified by actually launching a packaged build on each OS)
- Full text of every `logger.info`/`logger.debug`/`logger.warning` call across `auralis/analysis/` (56 files, the largest module) — only grepped for path/home-shaped interpolations, not read exhaustively for other sensitive-value classes (tokens/keys/URLs — grepped, no hits of concern beyond what's already noted)
- Rate-limiting/logging behavior of plain HTTP routes (as opposed to the WebSocket rate limiter reviewed above) — not located/verified whether HTTP endpoints have an equivalent rate limiter at all

### A10 — Server-Side Request Forgery (SSRF) / Outbound Network Surface — Coverage Statement

**Examined:**
- `auralis/services/artwork_service.py` (full file, 353 lines)
- `auralis-web/backend/services/artwork_downloader.py` (full file, 383 lines)
- `auralis/cli/fetch_artwork.py` (full file, 197 lines)
- `auralis/library/artwork.py` (full file, 374 lines — local file/tag extraction only, no
  outbound network calls; reviewed for completeness per task scope item 2 but found no A10
  relevance)
- `auralis/library/repositories/artist_repository.py` (`update_artwork`, lines 195-238)
- `auralis-web/backend/config/middleware.py` (CSP/`_ARTIST_ARTWORK_IMG_HOSTS` section,
  lines 60-110, plus general grep of the file)
- `auralis-web/backend/routers/artwork.py` (lines 1-60, and targeted grep of media-type
  logic at lines 132-326)
- `auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx` (lines 60-120)
- `desktop/main.js` (targeted: BrowserWindow construction ~300-350, window-open handlers,
  IPC handler registrations, protocol client setup ~580-644)
- `desktop/preload.js` (full grep for exposed IPC surface)
- `/tmp/audit/security/issue_titles.txt` (grepped for dedup: `artwork`, `ssrf`, `openExternal`,
  `4526`, `4688`, `4712`, `outbound`, `redirect`, `timeout`)
- Repo-wide grep for `requests.|httpx|aiohttp|urllib|urlopen|fetch(` across `auralis/`,
  `auralis-web/backend/`, and (for JS/TS) the whole repo excluding `node_modules`

**Not reached (explicitly NOT audited — do not assume clean):**
- `auralis-web/backend/routers/metadata.py` — file exists but was not read in detail; a
  targeted grep for outbound-HTTP patterns returned no hits, but the file was not opened and
  read end-to-end, so a metadata-lookup call using a different pattern (e.g. a wrapped
  client, or calling into `artwork_service`/`artwork_downloader` indirectly) cannot be ruled
  out.
- `auralis-web/backend/services/recommendation_service.py` and
  `.../services/learning_system.py` — confirmed to exist, but grepped only (no outbound-HTTP
  pattern hit); not read in full. Given the codebase memory notes these are "rule-based, not
  ML-service-backed," they are LOW-priority but not formally cleared here.
- Frontend `<img src=` usage beyond `MediaCardArtwork.tsx` — grep in scope item 6
  (`grep -rn "src={" ... | grep -i "art|cover|image"`) was not separately re-run in this
  session; only the `artworkUrl`/`artwork_url` reference grep across the frontend `src/`
  tree was performed. Other components consuming `artworkUrl` (there are ~15+ files matched
  by the reference grep) were not individually opened to confirm they route through
  same-origin proxying vs. raw external URLs — the middleware.py comment asserts only
  `Artist.artwork_url` is raw/external and Album/Track go through a same-origin
  `/api/.../artwork` path, but this was not independently verified file-by-file for every
  consuming component.
- `desktop/main.js` was not read in its entirety (only ~100 lines around the relevant
  sections); other IPC handlers, the auto-updater flow (`electron-updater`, referenced via
  `check-for-updates`), and any `net.request`/Node `https` usage elsewhere in the file were
  not exhaustively reviewed.
- DNS-rebinding / TOCTOU between `_validate_artwork_url()`'s hostname check and the actual
  TCP connection in `artwork_downloader.py` was considered but not deeply investigated
  beyond a design-level note (see A10-2 siblings) — not filed as a standalone finding because
  exploiting it requires compromising DNS resolution for Apple's/archive.org's own domains,
  which is out of proportion with the rest of this threat model.
- No dynamic/runtime testing was performed (per instructions: read-only on source, no real
  network requests made).


