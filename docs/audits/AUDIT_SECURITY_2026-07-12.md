# Security Audit — Auralis — 2026-07-12

**Scope**: OWASP Top 10 (2021), full stack — FastAPI backend (`auralis-web/backend/`), audio engine + library (`auralis/`), React frontend (`auralis-web/frontend/`), Rust DSP (`vendor/auralis-dsp/`), Electron shell (`desktop/`), dependency manifests.
**Method**: 10 parallel category agents, each tracing data flows from untrusted entry points (uploaded/scanned files, ID3/metadata, request bodies, WS messages) to sinks (SQL, subprocess, filesystem, DOM, outbound HTTP). Every finding re-read and adversarially checked before inclusion.
**Threat model**: Auralis is a **desktop-only Electron app**, backend bound to **`127.0.0.1` loopback only**, single local user. There is no remote/multi-user/LAN surface by design. Findings whose only vector requires a remote attacker are downgraded per `_audit-severity.md`; malicious-**file** / crafted-**metadata** / co-resident-**local-process** vectors are kept at full severity.
**Dedup basis**: `gh issue list` (142 open/closed issues) + `docs/audits/`. Existing issues referenced, not re-reported.

---

## Executive Summary

| Severity | NEW findings |
|----------|-------------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 16 |
| **Total NEW** | **19** |
| Informational (below LOW) | 1 |
| Existing issues referenced | 6 (#3900, #3901, #3902, #3905, #3906, #3910) |

**Overall posture: strong.** The high-value OWASP categories are actively hardened, in most cases by prior audit fixes verified still present:

- **A01 / A03 (Access Control / Injection)**: No path traversal, SQL injection, command injection, or XSS. All client-supplied paths flow through `validate_file_path()` (`..` reject → `resolve()` → allowed-dir containment); artwork uses `is_relative_to`; all FFmpeg calls use list-argv with no `shell=True` and reject protocol URLs; all SQL is ORM/parameterized; the frontend has **zero** `dangerouslySetInnerHTML`, so crafted ID3 tags cannot inject markup or SQL.
- **A07 (Auth)**: Backend binds **loopback-only** (verified `main.py:210`, no `0.0.0.0` anywhere), so "no authentication" correctly stays defense-in-depth LOW rather than HIGH. WebSocket enforces an Origin allowlist on the single `/ws` route; there are **no tokens/sessions/cookies at all** — nothing to mishandle.
- **A08 (Data Integrity)**: Migration safety is hardened and **not regressed** (inter-process `fcntl`/`msvcrt` lock, SQLite Online-Backup snapshot with fail-fast abort, atomic DDL+version). **Zero** insecure deserialization (no `pickle.load`, no unsafe `yaml.load`, no `eval`/`exec`, no pickled ML artifacts). Electron is locked down (`nodeIntegration:false`, `contextIsolation:true`, `webSecurity:true`).
- **A10 (SSRF)**: The one server-reachable outbound downloader (`artwork_downloader.py`) already enforces a trusted-domain allowlist + 5 MB size cap on API-supplied/redirect URLs. No route fetches a user-controllable host.

**Most actionable NEW items** (all MEDIUM):
1. **A04-1** — `GET /api/stream/{track_id}/chunk/{chunk_idx}` has no upper bound on `chunk_idx`; out-of-range indices trigger an uncached full-file decode → small-request→large-work amplifier.
2. **A06-1** — the requirements file **actually bundled into the shipped desktop app** (`desktop/resources/backend/requirements.txt`) leaves untrusted-audio parsers (`soundfile`, `mutagen`, `numpy`) fully unpinned; the well-pinned root `requirements.txt` does **not** govern the distributed build.
3. **A06-2** — FFmpeg (the untrusted-audio decoder) is an unpinned, unversioned external system binary; the app inherits whatever (possibly years-old, CVE-bearing) FFmpeg the user has on PATH.

No finding rises to HIGH/CRITICAL because the loopback bind, decode barrier, path-validation layer, and ORM parameterization remove the network/injection/traversal preconditions that would elevate them.

---

## Data Flow Security Matrix

| Flow | Boundary controls | Verdict |
|------|-------------------|---------|
| **File paths**: frontend → router → LibraryManager → `unified_loader` → FFmpeg | `validate_file_path()` on client paths; DB filepaths re-validated in `metadata.py`; FFmpeg list-argv + protocol-URL reject; upload → server UUID name | **Safe**, with one defense-in-depth gap: streaming router omits `validate_file_path` on DB filepath (**A01-1**, LOW — no injection sink today) |
| **Audio metadata**: file → `metadata_extractor` (mutagen) → DB (ORM) → API → React | Parameterized ORM persist; React auto-escape on render; no `dangerouslySetInnerHTML` | **Safe** for SQL/XSS. Gap: raw metadata interpolated into **log lines** (**A09-1**, LOW log-forging) |
| **WebSocket messages**: frontend → `/ws` → controller → processing → engine | Single `.accept()` behind Origin allowlist; message-size + schema validation; rate limiting | **Safe** on transport/origin. No per-message auth (by design, loopback) |
| **Library scan paths**: user folder → `scanner/file_discovery` → DB | inode-based symlink-cycle detection; `MAX_SCAN_DEPTH=50`; audio-extension filter | **Safe** from cycles; trusts any readable dir (**#3905**, by design) |
| **Chunk streaming**: `chunk_idx` → `chunked_processor` → `chunk_operations` | `ge=0` only, **no upper bound** vs `total_chunks` | **Gap** — out-of-range → full-file decode fallback (**A04-1**, MEDIUM) |
| **Outbound artwork fetch**: metadata → `artwork_downloader` → CDN | hardcoded API hosts; `_validate_artwork_url` allowlist + 5 MB cap on redirect/result URLs | **Safe** (no SSRF) |
| **DB migration**: startup → `migration_manager` | file-lock + backup-before-migrate + fail-fast + atomic DDL | **Safe** (hardened, not regressed) |

---

## Findings — MEDIUM

### SEC-M1 (A04-1): `stream_chunk` accepts unbounded `chunk_idx`, triggering an uncached full-file decode per request
- **Severity**: MEDIUM
- **OWASP Category**: A04 (Insecure Design)
- **Location**: `auralis-web/backend/routers/wav_streaming.py:338-341,478-482` → `auralis-web/backend/core/chunked_processor.py:767-807` → `auralis-web/backend/core/chunk_operations.py:95-130`
- **Status**: NEW
- **Description**: `GET /api/stream/{track_id}/chunk/{chunk_idx}` validates only `chunk_idx >= 0` (`PathParam(..., ge=0)`) with **no upper bound** against the track's `total_chunks`. The sibling pre-buffer path in `routers/enhancement.py:159` explicitly guards `if chunk_idx >= total_chunks: break` before calling the exact same `processor.get_wav_chunk_path()` — asymmetric validation of one downstream method reachable from two callers. For any out-of-range index, `get_chunk_boundaries()` produces `load_start > load_end`; `chunk_operations.load_chunk_from_file()` then seeks past EOF, the `except Exception` fallback **re-decodes the entire file** via `load_audio(filepath)` just to return 100 ms of silence.
- **Evidence**:
  ```python
  # wav_streaming.py:341 — only a lower bound
  chunk_idx: int = PathParam(..., ge=0, ...)
  # chunk_operations.py:102-115 — seek fails, fallback full-decodes
  try:
      f.seek(start_frame)             # beyond EOF -> raises
      audio = f.read(frames_to_read)  # negative
  except Exception:
      full_audio, _ = load_audio(filepath, ...)  # FULL FILE DECODE, uncached
  ```
- **Exploit Scenario**: A local page/script issues repeated requests with distinct large indices (`.../chunk/999999?intensity=0.11`, `.../chunk/999998?intensity=0.12`, …). Each distinct `(preset, intensity, chunk_idx)` key misses the cache and hits the fallback that decodes the whole file (bounded only by `MAX_DURATION_SECONDS=7200`, i.e. multi-GB PCM), all to produce silence.
- **Impact**: Availability — CPU/RAM amplification and event-loop pressure; a small-request → large-work amplifier and an inconsistent state-machine contract. Not a crash (handled gracefully).
- **Suggested Fix**: In `stream_chunk`, resolve `total_chunks` (as `enhancement.py` already does) and return `404`/`400` when `chunk_idx >= total_chunks`; or enforce the ceiling inside `get_wav_chunk_path()` so every caller is protected. Also bail out of the `load_chunk_from_file` fallback when `load_start >= load_end` instead of full-decoding.

### SEC-M2 (A06-1): Shipped desktop backend requirements are fully UNBOUNDED (untrusted-audio parsers unpinned)
- **Severity**: MEDIUM
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `desktop/resources/backend/requirements.txt` (and identical `auralis-web/backend/requirements.txt`)
- **Status**: NEW
- **Description**: The requirements file bundled into the distributed desktop artifact (`extraResources: resources/backend` in `desktop/package.json`) declares the audio/metadata parsing stack with **no version constraint**: `numpy`, `scipy`, `soundfile`, `mutagen`, `websockets`, `aiofiles`, `python-multipart` are bare names; `fastapi`/`uvicorn` carry only lower bounds. `soundfile` (libsndfile) and `mutagen` parse untrusted audio/metadata — exactly the A06 attack surface. The well-pinned root `requirements.txt` is **not** the file that governs the shipped backend, so a build resolves to whatever is on PyPI at build time with no floor excluding known-vulnerable parser versions and no reproducibility.
- **Evidence**:
  ```
  numpy
  scipy
  soundfile
  mutagen
  fastapi>=0.104.0
  uvicorn[standard]>=0.24.0
  ```
- **Exploit Scenario**: A build/install resolves an outdated `soundfile`/`mutagen`; a crafted FLAC/ID3 tag then reaches a known libsndfile/mutagen parsing bug that a floor constraint would have excluded.
- **Impact**: Non-reproducible builds; silent inclusion of a vulnerable audio/metadata parser in the distributed app.
- **Suggested Fix**: Make the desktop/backend manifests mirror or `pip-compile` from the pinned root `requirements.txt` (single source of truth); pin all entries `==` with floors excluding known-vulnerable versions. Ideally generate `desktop/resources/backend/requirements.txt` rather than hand-maintaining it.

### SEC-M3 (A06-2): FFmpeg untrusted-audio parser is an unpinned external system binary
- **Severity**: MEDIUM
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:32-58`; invoked from `auralis/io/unified_loader.py:80,206`
- **Status**: NEW
- **Description**: Non-native formats (MP3/AAC/OGG/OPUS/M4A) are decoded by shelling out to the system `ffmpeg`/`ffprobe` on PATH. FFmpeg is neither bundled nor version-checked — the loader only probes `['ffmpeg', '-version']` for presence. FFmpeg has a large historical volume of demuxer/decoder memory-corruption CVEs reachable purely by decoding a malicious media file, which is the core untrusted input for a music player. The app inherits whatever (possibly years-old) FFmpeg the user installed.
- **Evidence**: `ffmpeg_loader.py` enforces no minimum version; `desktop/package.json` `extraResources` bundles backend/frontend/auralis but **no** ffmpeg binary.
- **Exploit Scenario**: User adds a crafted `.m4a`/`.ogg`; the scanner/loader invokes the system FFmpeg; an outdated FFmpeg hits a known demuxer overflow → crash or potential code execution in the decode subprocess.
- **Impact**: Untrusted-file parsing delegated to an unversioned third-party binary; severity bounded by the user's FFmpeg patch level. Existing pre-decode duration/size guards (#3671) limit resource exhaustion but not memory-corruption bugs.
- **Suggested Fix**: Parse `ffmpeg -version` at startup and warn/refuse below a minimum; consider bundling a pinned, hardened FFmpeg build in the desktop package so the decode surface is controlled rather than ambient.

---

## Findings — LOW

### SEC-L1 (A01-1): Streaming endpoints serve DB `track.filepath` without `validate_file_path` (inconsistent with metadata router)
- **Severity**: LOW
- **OWASP Category**: A01 (Broken Access Control)
- **Location**: `auralis-web/backend/routers/wav_streaming.py:246-336,338-582,583-648`
- **Status**: NEW
- **Description**: Both streaming endpoints do file I/O on `track.filepath` straight from the DB (`os.path.exists`, `get_audio_info`, `ChunkedAudioProcessor(filepath=...)`) with **no** path validation, whereas `routers/metadata.py:161-165` deliberately runs `validate_file_path(str(track.filepath))` on the same DB-sourced value "before any file I/O (fixes #2302)". The highest-traffic consumer of `track.filepath` omits the guard.
- **Evidence**: `wav_streaming.py:399-405` calls `os.path.exists(track.filepath)` / `ChunkedAudioProcessor(filepath=track.filepath)` with no `validate_file_path`; `metadata.py:161` wraps the identical value.
- **Exploit Scenario**: Requires first landing an arbitrary path into `tracks.filepath`. Writers are upload (server UUID name), scanner (existing audio-extension files under a user root), and processing (validated) — none client-injectable. Even then the decoder rejects non-audio files, so `/etc/passwd` cannot be exfiltrated. Residual risk is only a future feature adding a client-controlled filepath writer.
- **Impact**: Defense-in-depth inconsistency; no confirmed arbitrary-file read today (decode barrier + no injection sink).
- **Suggested Fix**: Route `track.filepath` through `validate_file_path()` (or a shared helper) in `stream_metadata`, `stream_chunk`, and `_get_original_wav_chunk` before any I/O, so one policy governs all DB-filepath access.

### SEC-L2 (A02-1): `.env` with placeholder secrets is committed and defeats its own `.gitignore` rule
- **Severity**: LOW
- **OWASP Category**: A02 (Cryptographic Failures)
- **Location**: `.env` (tracked); `.gitignore` (`.env` rule present but ineffective for an already-tracked file)
- **Status**: NEW
- **Description**: A legacy Matchering `.env` (declares `MATCHERING_SECRET_KEY`, `MATCHERING_POSTGRES_PASSWORD`, JWT `ALGORITHM=HS256`, etc.) is checked into git despite a `.gitignore` `.env` rule. Because it was committed before the rule takes effect on tracked files, any future edit inserting a real key commits silently. All current values are placeholders (`CHANGE_ME...`), and none of the variables are read anywhere in Auralis (no `load_dotenv`/`BaseSettings`/`os.environ['MATCHERING_*']`) — Auralis uses SQLite and has no auth/JWT layer. Dead legacy config.
- **Evidence**: `git ls-files` lists `.env`; `grep -rE "BaseSettings|load_dotenv|environ\[.MATCHERING" auralis auralis-web` → no matches.
- **Exploit Scenario**: A contributor treats the committed `.env` as live config, replaces `CHANGE_ME` with a real Last.fm key / DB password, and commits — publishing the secret to history because the file is already tracked.
- **Impact**: No current exposure (placeholders); latent future secret-leakage risk plus developer confusion.
- **Suggested Fix**: `git rm --cached .env` (the gitignore rule then applies); delete the unused legacy vars; commit a `.env.example` template if desired.

### SEC-L3 (A02-2): SQLite WAL/SHM sidecar files are not permission-restricted like the main DB
- **Severity**: LOW
- **OWASP Category**: A02 (Cryptographic Failures)
- **Location**: `auralis/library/manager.py:135-141,149`
- **Status**: NEW
- **Description**: The main `library.db` is `chmod 0o600` and the default parent dir is created `mode=0o700`, but WAL mode (`PRAGMA journal_mode=WAL`) creates `library.db-wal`/`-shm` sidecars with the process umask (often `0o644`) and never `chmod`s them. On the default path they inherit the `0o700` dir's protection transitively; the gap is exposed only if `~/.auralis` pre-existed with looser perms (mkdir `mode=` is ignored for an existing dir) or the DB is pointed at a custom path. The DB holds library metadata/fingerprints — no credentials.
- **Evidence**: `manager.py:139` chmods only `db_path`; no chmod of `db_path + "-wal"`/`-shm`; WAL enabled at `:149`.
- **Exploit Scenario**: On a multi-account machine where `~/.auralis` was pre-created with default perms, another local account reads `library.db-wal` and recovers recently-played/library data.
- **Impact**: Local information disclosure of non-sensitive library data; low likelihood on single-user desktop.
- **Suggested Fix**: After enabling WAL, chmod `-wal`/`-shm` to `0o600` when present, or re-chmod the parent dir to `0o700` even when it pre-exists.

### SEC-L4 (A03-1): `find_by_tag` builds a LIKE pattern without escaping wildcard/JSON metacharacters
- **Severity**: LOW
- **OWASP Category**: A03 (Injection)
- **Location**: `auralis/library/repositories/queue_template_repository.py:155-157`
- **Status**: NEW
- **Description**: Tag search interpolates the caller-supplied `tag` into a LIKE pattern (`.like(f'%"{tag}"%')`) without escaping LIKE metacharacters (`%`, `_`) or the JSON delimiter `"`. Sibling repos (`artist_repository.py:146`, `album_repository.py:148`, `queue_template_repository.py:347`) correctly use `.ilike(search_term, escape='\\')`. **Not SQL injection** — SQLAlchemy still binds `tag` as a parameter — but a tag containing `%`/`_`/`"` alters matching semantics (tag `%` matches every template).
- **Evidence**: `QueueTemplate.tags.like(f'%"{tag}"%')` — no `escape=`, no metachar sanitization.
- **Exploit Scenario**: A tag literally `%` returns unrelated templates. No data-boundary crossing (single-user local DB).
- **Impact**: Incorrect search results only.
- **Suggested Fix**: Escape LIKE metacharacters and pass `escape='\\'`, matching the other repositories.

### SEC-L5 (A04-2): File-upload endpoint places no cap on the number of files per multipart request
- **Severity**: LOW
- **OWASP Category**: A04 (Insecure Design)
- **Location**: `auralis-web/backend/routers/files.py:89-116`
- **Status**: NEW
- **Description**: `upload_files(files: list[UploadFile])` caps each file at 500 MB (`_MAX_UPLOAD_BYTES`, streamed) and validates magic bytes, but there is **no limit on how many files** a single request may contain. The handler loops over every element synchronously, decoding audio and inserting a DB row per file.
- **Evidence**: `for file in files:` with no `len(files)` cap; `content = await file.read(_MAX_UPLOAD_BYTES + 1)` is per-file only.
- **Exploit Scenario**: A local script POSTs one multipart body with, e.g., 50,000 tiny valid-magic WAVs; each is decoded and inserted, monopolising the upload path and bloating the library DB.
- **Impact**: Availability — a single request occupies the backend and grows the DB. Low weight on desktop-only single-user.
- **Suggested Fix**: Reject requests above a sane `len(files)` ceiling (e.g. a few hundred) with `413`/`400`, and/or cap cumulative bytes per request. (`_MAX_UPLOAD_BYTES` duplication tracked separately as #4033.)

### SEC-L6 (A05-1 + A07-3): Dev-port CORS + WebSocket origin allowlist is always active and broad
- **Severity**: LOW
- **OWASP Category**: A05 (Security Misconfiguration) / A07 (Auth)
- **Location**: `auralis-web/backend/config/middleware.py:198-224` (CORS), `auralis-web/backend/config/globals.py:29-38` (`ALLOWED_WS_ORIGINS`)
- **Status**: NEW (merges A05-1 and A07-3 — same allowlist)
- **Description**: The CORS `allow_origins` and `ALLOWED_WS_ORIGINS` are built unconditionally as `{http,https,ws,wss}://{localhost,127.0.0.1}:{3000..3006, 8765}` (`_DEV_PORTS = range(3000,3007)`), not gated on `is_dev_mode()`. In a packaged Electron build the renderer is served from `file://` or `127.0.0.1:8765`, so the Vite dev ports 3000-3006 are never legitimately used — yet the backend still accepts credentialed CORS requests and WS upgrades from any of them. If the user runs another local web app on one of those ports and it is compromised (XSS), the page can drive the Auralis WS/API.
- **Evidence**: `_DEV_PORTS = list(range(3000, 3007)); _ALL_PORTS = _DEV_PORTS + [8765]` used verbatim in production middleware wiring with no dev-mode branch; expanded over 4 schemes × 2 hosts.
- **Exploit Scenario**: In a shipped build, a compromised/malicious local page on `http://localhost:3002` issues credentialed `fetch` to `127.0.0.1:8765/api/...` or opens the Auralis WS; its origin is in the always-on allowlist. Requires a coincidental local app on those exact ports.
- **Impact**: Marginally broadened cross-origin/cross-app attack surface in production builds; no data is protected by credentials, so real impact is minimal.
- **Suggested Fix**: When `is_dev_mode()` is false, restrict both allowlists to `http://127.0.0.1:8765`, `http://localhost:8765`, and `file://`; include the 3000-3006 range only in dev mode. Ideally pass the resolved frontend port from the launcher so only the port actually in use is trusted.

### SEC-L7 (A05-2): "Frontend not found" root handler discloses the absolute server filesystem path
- **Severity**: LOW
- **OWASP Category**: A05 (Security Misconfiguration)
- **Location**: `auralis-web/backend/main.py:190-202`
- **Status**: NEW
- **Description**: When not in dev mode and the built frontend dir is missing, the fallback `GET /` handler renders the absolute expected path (`frontend_path`) into the HTML body. It is HTML-escaped (no XSS) but still discloses an absolute filesystem path (PyInstaller `_MEIPASS` temp dir or home layout) to any client hitting `/`. Triggers only on a broken/misconfigured install.
- **Evidence**: `<p>Frontend not found at: {html_module.escape(str(frontend_path))}</p>`.
- **Exploit Scenario**: On a mispackaged build, any local browser tab (or DNS-rebind page) reads the backend's absolute install path from `/`, aiding path-targeted local attacks.
- **Impact**: Minor internal path disclosure; no direct compromise.
- **Suggested Fix**: Return a generic message ("Frontend assets not found — reinstall") and log the absolute path server-side only.

### SEC-L8 (A05-3 + A07-2): No Host-header / TrustedHost validation (DNS-rebinding defense-in-depth)
- **Severity**: LOW (downgraded from MEDIUM per desktop-only threat model)
- **OWASP Category**: A05 (Security Misconfiguration) / A07 (Auth)
- **Location**: `auralis-web/backend/config/middleware.py:190-224` (no `TrustedHostMiddleware`), `auralis-web/backend/main.py:210` (loopback bind)
- **Status**: NEW (merges A05-3 and A07-2 — same missing middleware)
- **Description**: No `TrustedHostMiddleware`, so the HTTP `Host` header is not validated. A DNS-rebinding page (attacker domain rebound to `127.0.0.1`) can make the victim browser send state-changing requests the browser executes without reading the response. The WebSocket is protected (Origin allowlist) and JSON POSTs force a CORS preflight; the residual window is CORS-"simple" requests (GET, or form/text POST) whose responses are unreadable cross-origin.
- **Evidence**: `setup_middleware()` adds RateLimit, NoCache, SecurityHeaders, CORS — no `TrustedHostMiddleware`; no `request.headers["host"]` check anywhere.
- **Exploit Scenario**: User visits `attacker.com` which rebinds DNS to `127.0.0.1`; the page fires no-preflight GETs at the local backend. No confirmed data exfiltration or state change under current JSON content-types.
- **Impact**: Defense-in-depth gap; no confirmed exploit given JSON content-type + CORS + loopback bind.
- **Suggested Fix**: Add `TrustedHostMiddleware(allowed_hosts=["127.0.0.1","localhost","[::1]", "127.0.0.1:8765","localhost:8765"])`, and ensure state-changing endpoints require `Content-Type: application/json` (forcing a preflight).

### SEC-L9 (A06-3): Four divergent Python manifests with conflicting pinning policies
- **Severity**: LOW
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `requirements.txt`, `requirements-desktop.txt`, `auralis-web/backend/requirements.txt`, `desktop/resources/backend/requirements.txt`
- **Status**: NEW
- **Description**: Four Python dependency lists with incompatible policies: root fully pinned/modern; `requirements-desktop.txt` floats with old floors and still lists `statsmodels>=0.13.2` which the root explicitly documents as removed/unused; the two backend files are unbounded (SEC-M2). No single source of truth, so patching one leaves the others stale and it is ambiguous which governs a given install.
- **Evidence**: `requirements-desktop.txt` → `statsmodels>=0.13.2`, `numpy>=1.23.4`; root → `numpy==2.3.5` + "# statsmodels ... not used".
- **Impact**: Drift and inconsistent security posture across install paths; dead `statsmodels` broadens footprint.
- **Suggested Fix**: Consolidate to one pinned manifest (via `pip-compile`, as the root header prescribes) and have desktop/backend reference it; drop `statsmodels`.

### SEC-L10 (A06-4): Dual/conflicting JS lockfiles
- **Severity**: LOW
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `auralis-web/frontend/package-lock.json` + `auralis-web/frontend/pnpm-lock.yaml`; `desktop/package-lock.json` + `desktop/yarn.lock`
- **Status**: NEW
- **Description**: Both the frontend and desktop packages carry two lockfiles from two different package managers, committed on different dates. Which is authoritative is undefined, so the resolved (and audited) dependency graph depends on which tool the builder uses; divergent lockfiles can silently pin different, unpatched transitive versions.
- **Evidence**: `ls` shows both `package-lock.json` + `pnpm-lock.yaml` (frontend) and `package-lock.json` + `yarn.lock` (desktop).
- **Exploit Scenario**: `npm audit` reports clean against `package-lock.json`, but the build uses `pnpm`/`yarn` whose lockfile resolves a vulnerable transitive dep.
- **Impact**: Supply-chain ambiguity; audit results may not reflect the shipped graph.
- **Suggested Fix**: Pick one package manager per package, delete the other lockfile, add a CI check failing on a stray lockfile, and gate `npm/pnpm audit` on the retained one.

### SEC-L11 (A06-5): `pyproject.toml` declares stale/legacy dependency floors (incl. dead PyQt6)
- **Severity**: LOW
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `pyproject.toml:22-34`
- **Status**: NEW
- **Description**: `[project].dependencies` lists very old floors (`numpy>=1.20.0`, `scipy>=1.7.0`, `fastapi>=0.68.0`, `librosa>=0.9.0`) and `PyQt6>=6.2.0` labeled "For development UI" even though the project moved to a web frontend. Installing via package metadata (`pip install .`) rather than `requirements.txt` gets these loose floors, permitting long-outdated CVE-bearing versions, and declares an unused heavyweight GUI dependency. (Project memory already flags the pyproject version as stale.)
- **Evidence**: `"fastapi>=0.68.0"`, `"numpy>=1.20.0"`, `"PyQt6>=6.2.0",  # For development UI`.
- **Impact**: Metadata-based installs can pull ancient FastAPI/Starlette/numpy; unused PyQt6 enlarges attack surface.
- **Suggested Fix**: Raise floors to match the pinned `requirements.txt` (or reference it); remove the unused `PyQt6` runtime dependency.

### SEC-L12 (A06-6): Rust crates behind current majors; no `cargo audit` gate
- **Severity**: LOW
- **OWASP Category**: A06 (Vulnerable & Outdated Components)
- **Location**: `vendor/auralis-dsp/Cargo.toml:6-13`
- **Status**: NEW
- **Description**: `pyo3 = "0.23"` (0.25/0.26 available), `numpy = "0.23"`, `ndarray = "0.15"` (0.16 available) trail current releases. No known serious RUSTSEC advisory applies to these pinned numeric/FFI crates as of the Jan 2026 cutoff, and `Cargo.lock` (86 crates) makes resolution reproducible, so exposure is low — but `cargo-audit` is not installed and there is no CI advisory scan, so future RUSTSEC advisories go unnoticed. PyO3 is the trust boundary between untrusted audio data and native code. (Not verified against live RUSTSEC DB — "verify".)
- **Evidence**: `pyo3 = { version = "0.23", ... }`, `ndarray = "0.15"`; `which cargo-audit` → not found.
- **Impact**: DSP crates could accumulate unpatched advisories silently.
- **Suggested Fix**: Add `cargo audit` to CI; plan a PyO3/ndarray/numpy bump on the next maintenance pass.

### SEC-L13 (A07-1 + A01-2): No authentication on the local REST/WebSocket API (defense-in-depth)
- **Severity**: LOW
- **OWASP Category**: A07 (Auth) / A01 (Broken Access Control)
- **Location**: `auralis-web/backend/main.py` (no auth dependency anywhere); `auralis-web/backend/config/globals.py:58-92`; `auralis-web/backend/security/path_security.py:255-304`
- **Status**: NEW for the "no API auth" facet; the *directory-trust* facet (`validate_user_chosen_directory` trusting any readable dir) is **Existing: #3905**
- **Description**: Neither REST nor WebSocket enforces caller identity — any local process, or any browser page whose Origin is in the loopback allowlist, can invoke every endpoint (control playback, scan library, edit metadata, launch processing). This is intentional for a single-user desktop app and is bounded by the loopback-only bind. `validate_user_chosen_directory` additionally trusts any readable directory for scanning (only audio-extension files are indexed) — tracked as #3905. Browser CSRF is mitigated by the strict CORS allowlist + WS Origin check; the residual actor is a **co-resident local process** already running at the user's privilege.
- **Evidence**: No `Depends(...)` auth guard on any router (grep for `HTTPBearer`/`OAuth2`/`Security(`/`get_current_user` → none); `ConnectionManager.connect` allows empty-Origin WS connections from loopback so non-browser local processes can drive the WS.
- **Exploit Scenario**: A malicious/compromised local process opens `ws://127.0.0.1:8765/ws` (no Origin, allowed as loopback) and issues `play_enhanced`/`stop`/`seek`/scan commands, or calls REST directly. No LAN peer (loopback bind) or remote page (Origin allowlist) can.
- **Impact**: A co-resident local process can control playback and trigger scans/processing — but it already has the user's filesystem privileges, so marginal impact is minimal.
- **Suggested Fix**: Accept as designed and document the single-user/loopback assumption in a security model doc; optionally mint a per-launch loopback capability token in the Electron main process, required on WS connect and REST mutations, if defense against co-resident processes is ever desired.

### SEC-L14 (A09-1): Log injection via unsanitized track metadata and upload filenames
- **Severity**: LOW
- **OWASP Category**: A09 (Logging Failures)
- **Location**: `auralis-web/backend/routers/fingerprint_status.py:84`; `auralis-web/backend/routers/files.py:211,220,237`; `auralis-web/backend/services/artwork_downloader.py:144,150,153`; `auralis/services/artwork_service.py:90,160,212,262,287`
- **Status**: NEW (same class as OPEN #3910 — the `system.py` `message_type` instance; these are siblings, not the same site)
- **Description**: Multiple `logger` calls interpolate attacker-influenceable strings — ID3/Vorbis tag values (title/artist/album) parsed from arbitrary audio files, and client-supplied upload filenames — directly into the message with no sanitization. An embedded `\r\n` forges additional log lines; terminal control sequences can corrupt a log viewer. (`files.py:141` correctly uses `!r`.)
- **Evidence**:
  ```python
  logger.info(f"✓ Track found: {track.title} by {track.artists}")   # fingerprint_status.py:84
  logger.info(f"Successfully uploaded and processed: {file.filename}")  # files.py:211
  ```
- **Exploit Scenario**: A track whose `TITLE` tag contains `Foo\n2026-07-12 WARNING Fingerprint DB wiped` forges a log line on scan; if the user later attaches the log to a bug report it misleads triage.
- **Impact**: Log integrity / forged audit trail; cosmetic corruption. No confidentiality or RCE.
- **Suggested Fix**: Add one sanitizer (strip/escape `\r\n` and non-printables) applied to metadata/filenames before interpolation, and reuse it at the #3910 site to fix the whole class once. `!r` is the cheapest per-call mitigation.

### SEC-L15 (A09-2): Absolute filesystem paths logged at INFO/DEBUG
- **Severity**: LOW
- **OWASP Category**: A09 (Logging Failures)
- **Location**: pervasive; representative: `auralis-web/backend/main.py:38,46,51,161,169,188`; `auralis-web/backend/core/chunked_processor.py:598,762`; `auralis-web/backend/services/audio_content_predictor.py:112,120,130,182`; `auralis-web/backend/security/path_security.py:179,251,303`
- **Status**: NEW
- **Description**: Full absolute paths (which embed the OS username via `/home/<user>/...` and the user's library layout) are logged at INFO/DEBUG throughout. Not a boundary crossing on single-user desktop, but these logs are exactly what a user pastes into a public bug report, leaking username and directory structure.
- **Evidence**: `logger.info(f"Full audio saved to {full_path}")`; `logger.info(f"Serving frontend from: {frontend_path}")`.
- **Impact**: Minor incidental information disclosure if logs are shared externally.
- **Suggested Fix**: Log basenames or library-relative paths for routine INFO lines; keep absolute paths in DEBUG / explicit error diagnostics. Low priority.

### SEC-L16 (A09-3): Silent exception swallowing hides best-effort failures (cluster)
- **Severity**: LOW
- **OWASP Category**: A09 (Logging Failures)
- **Location** (one finding, representative): `auralis-web/backend/ws_handlers/connection.py:78,92`; `auralis-web/backend/services/library_auto_scanner.py:402`; `auralis-web/backend/core/proactive_buffer.py:102`; `auralis-web/backend/config/startup.py:369`
- **Status**: NEW (distinct from OPEN #3906, which is the `system.py` WS finally-block silent catch)
- **Description**: A handful of broad `except Exception: pass` blocks discard the exception with no log, so genuine failures (failed initial-state WS sync, failed watchdog teardown, failed resource release) leave no trace. For a single-user desktop this is a debuggability/reliability gap, not a security gap. (Cancellation catches like `except asyncio.CancelledError: pass` after `await old_task` are idiomatic and NOT flagged.)
- **Evidence**:
  ```python
  except Exception:
      pass  # connection.py:91 — "Best-effort: don't fail the connection"
  ```
- **Impact**: Reduced observability of failures; no direct security impact.
- **Suggested Fix**: Downgrade the genuinely-broad handlers to `logger.debug("...", exc_info=True)` instead of bare `pass`; leave the cancellation/commented-best-effort DSP catches as-is.

---

## Informational (below LOW threshold)

- **A08-INFO-1 — Audio files and fingerprint data are not integrity-checked** (`auralis/io/unified_loader.py`, `auralis/analysis/fingerprint/*`). No checksum/signature on loaded files or stored fingerprints. For a single-user desktop media player the user owns their own files and local DB — no trust boundary is crossed; corruption degrades playback quality, not security. Optional: store a content hash per track for library-hygiene (not as a security control).
- **A10-INFO — CLI-only `artwork_service.py`** lacks the allowlist/size-cap its server-reachable twin (`artwork_downloader.py`) has, but it *returns* URLs as data rather than fetching bytes, runs only as a local operator CLI, and is unreachable from the web backend — no server SSRF vector today. If ever wired into the backend, adopt `_validate_artwork_url` + size cap.

---

## Existing Issues Referenced (not re-reported)

| Issue | State | Summary | Related finding |
|-------|-------|---------|-----------------|
| #3900 | OPEN | CSP allows `'unsafe-inline'` for script/style-src (also whitelists Google Fonts + broad localhost `connect-src`) | A05 — fold Fonts/connect-src observations into #3900 |
| #3901 | OPEN | Rate-limit windows are magic numbers with no env override | A05/A07 |
| #3902 | OPEN | `_EVICTION_INTERVAL = 256` and other middleware magic numbers | A05 |
| #3905 | OPEN | `validate_user_chosen_directory` trusts any readable dir | Directory-trust facet of SEC-L13 |
| #3906 | OPEN | `system.py` WS finally-block errors caught silently | Distinct site from SEC-L16 |
| #3910 | OPEN | `system.py` reflects/logs unsanitized `message_type` | Parent instance of the SEC-L14 log-injection class |

---

## Relationships & Chaining

- **SEC-L6 (dev-port allowlist) + SEC-L8 (no TrustedHost) + SEC-L13 (no auth)** form the browser-mediated attack chain: a malicious local page (coincidental dev port) or DNS-rebound page can *send* requests the backend executes. Each link is individually LOW because the loopback bind + CORS-preflight-on-JSON + unreadable cross-origin responses + no-secrets-to-steal cap the realized impact. Fixing SEC-L8 (TrustedHost) and SEC-L6 (dev-mode-gate the allowlist) closes most of the chain cheaply.
- **SEC-M2 (unpinned shipped parsers) + SEC-M3 (unpinned FFmpeg)** together mean the entire untrusted-audio decode surface of the *distributed* app is governed by ambient, unversioned components — the highest-leverage supply-chain exposure. Both feed the same threat: a crafted audio file reaching a known parser CVE.
- **SEC-L14 (log injection) + SEC-M2** — a malicious file's metadata both forges log lines and is parsed by an unpinned parser; the file is the common untrusted input.

---

## Prioritized Fix Order

1. **SEC-M2 + SEC-M3** (supply chain of the shipped app) — pin the desktop backend requirements to the root manifest and enforce/bundle a minimum FFmpeg. Highest real-world leverage: controls the untrusted-audio decode surface of every distributed copy.
2. **SEC-M1** (unbounded `chunk_idx`) — add the `total_chunks` ceiling in `stream_chunk` and a `load_start >= load_end` early-out. Small, self-contained, removes a work-amplification DoS.
3. **SEC-L8 + SEC-L6** (TrustedHost + dev-mode-gated allowlist) — two small middleware changes that close the DNS-rebinding / cross-app-origin chain.
4. **SEC-L14** (one shared log sanitizer) — also resolves the #3910 class in the same change.
5. **SEC-L2** (`git rm --cached .env`), **SEC-L1** (route streaming filepath through `validate_file_path`), **SEC-L4** (LIKE escape), **SEC-L5** (upload count cap) — quick, low-risk hardening.
6. **SEC-L9–L12** (manifest/lockfile consolidation, `cargo audit`) — maintenance sweep, best done together.
7. **SEC-L3, L7, L13, L15, L16** — opportunistic defense-in-depth / observability polish.

---

*Report generated by the security audit suite (OWASP Top 10 2021). No GitHub issues were created. To publish:*

```
/audit-publish docs/audits/AUDIT_SECURITY_2026-07-12.md
```
