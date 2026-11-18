# Security Audit (OWASP Top 10, 2021) - 2026-11-17

**Scope**: Auralis backend (`auralis-web/backend/`), engine and library (`auralis/`), frontend, and the Electron shell (`desktop/`), audited fresh against the current tree on 2026-11-17 (HEAD `7029fa50a`). Depth: deep, all ten categories, no finding limit.
**Method**: ten category agents (A01-A10) read the live source, ran read-only probes under a scratch `HOME` (the real `~/.auralis` library was never used), and de-duplicated against the full GitHub issue dump (6090 issues, highest #6346, no truncation).
**Baseline**: Auralis is a desktop app bound to `127.0.0.1:8765` with no authentication by design. "No auth" is not reported; only violations of that baseline are.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 34 |
| **Total** | **38** |

By status: 32 NEW, 5 Existing (open issues: #4905, #5484, #6169, #6171, #6187), 1 Regression (of #6178).

**Key themes**

1. **The network perimeter held.** The WebSocket Origin check, REST `OriginCheckMiddleware` (including the `Sec-Fetch-Site` GET filter), TrustedHost, CORS, middleware order, the `127.0.0.1` bind with `proxy_headers=False`, path containment on every file route and every stream path, the scan-root validators, Electron IPC and navigation gates, and SQL parameterisation all survived live probes. No path traversal, command injection, SQL injection, XSS sink or SSRF was found. Closed hardening issues spot-checked this run (e.g. #4826, #5326, #5733, #6154, #6157, #6159, #6160, #6182, #6184, #6185, #6188-#6191) are all still in place.
2. **The one HIGH is a supply-chain risk, already tracked.** Auto-update ships unsigned binaries with `win.verifyUpdateCodeSignature: false` (#4905, A02-1). A related stale manual release script (A08-5) bypasses the CI release controls as well.
3. **Untrusted-file resource abuse is the main residual attack surface.** A crafted audio file can exhaust disk or CPU: the FFmpeg decode guards trust the container's declared duration (A04-1, reproduced, a 5 GB temp WAV in 4 s from a "30 s" file), repeated ARTIST/GENRE tags have no count cap and a quadratic dedup (A03-1, measured), and embedded lyrics are uncapped (A03-2). The bundled libsndfile 1.2.2 has open memory-corruption CVEs reachable from the scanner (A06-1).
4. **Logging and evidence integrity is the largest cluster (10 LOW).** #6184/#6185/#6188/#6189 fixes are intact, but sibling gaps remain: unthrottled WebSocket-handshake and uvicorn access logs (A05-1, A09-1), unsanitised raw stderr (A09-6), SQLAlchemy parameter leakage (A09-5), HOME-symlink redaction (A09-4), and others.
5. **Residuals of closed fixes.** Several closed issues have unfixed siblings: #6157 (port-cleanup identity pattern, A05-2), #6178 (`uv.lock` stale pins, A06-2, a regression against the issue's acceptance criterion), #4910/#6175 (forgeable `.25d` sidecar, A08-1), #4765 (persisted scan folders, A08-3), #6174 (asar integrity, A08-4), #5330/#5069/#6182 (CLI artwork client redirect and throttling gaps, A10-1/2).

**Most exploitable**: A04-1 (a crafted M4A needs only to be scanned or played to fill `/tmp`, reproduced), A03-1 (a crafted tagged file freezes the scan worker), and A01/A07 findings only on shared multi-user hosts. Nothing found is remotely exploitable from a web page.

## Data Flow Security Matrix

| Flow | Verdict | Gaps |
|---|---|---|
| 1. File paths (frontend -> router -> `path_security` -> repositories -> loader -> FFmpeg) | Safe | Every route validates or takes only a DB id; chunk/thumbnail cache keys are hex/enum/numeric only; FFmpeg uses list argv, `-protocol_whitelist file`, scheme guard. Gaps: uploaded tracks sit outside the allowlist and fail closed (A01-1); persisted scan folders are re-trusted at startup without write-time validation (A08-3); the decode size guards trust declared duration (A04-1); the upload-and-process route has no disk quota (A04-2). |
| 2. Audio metadata (file -> loader -> tag parser -> DB -> API -> render) | Mostly safe | Frontend has no unsafe HTML sinks and tag text is length-bounded, but the ARTIST/GENRE count is not (A03-1) and lyrics are uncapped (A03-2); tag text is unescaped in MusicBrainz Lucene queries (A03-3); `.25d` sidecars are forgeable by anyone who controls a music folder (A08-1/2/6). |
| 3. WebSocket messages (Origin -> rate limit/validation -> handlers -> stream controller) | Safe | Origin, cap, size/depth limits and per-message validation hold. Gaps are availability and logging only: paused connections can hold all stream slots (A07-3, #6171), handshake rejections and uvicorn access lines are unthrottled (A05-1, A09-1). |
| 4. Library scan paths (folder -> `library_scan` -> scanner -> DB) | Safe | Scan-root validators present on every entry point; symlink following is intentional. Residual: startup re-registration of persisted roots (A08-3) and tag-count abuse (A03-1). |
| 5. Outbound HTTP (artwork) | Safe in the backend | Backend providers refuse redirects, allowlist hosts, bound reads and throttle per host. The CLI artwork client follows redirects unvalidated and bypasses `HostThrottle` (A10-1/2). |
| 6. Updates and release | Gap | Unsigned binaries, signature verification off (A02-1/#4905); stale local release script (A08-5); asar integrity fuse off (A08-4); libsndfile and lock-file drift (A06-1/2/3). |
| 7. Local trust boundary (desktop) | Safe for one user | Cross-OS-user access on shared hosts is unauthenticated (A07-1); port cleanup can kill unrelated services (A05-2); macOS backend outlives quit (A07-2). |

## Findings

Grouped by severity. Findings were not duplicated across categories: A02-2 is an A05-class issue reported once, and the uvicorn access-log finding (A09-1) is distinct from the handshake-log finding (A05-1).

### CRITICAL

None.

### HIGH

### A02-1: Auto-update pipeline ships unsigned binaries with update code-signature verification disabled
- **Severity**: HIGH
- **OWASP Category**: A02 (also A08 Software and Data Integrity)
- **Location**: `desktop/package.json:100` (`build.win.verifyUpdateCodeSignature: false`), `desktop/package.json:156-160` (github publish provider), `desktop/main.js:514-515,562-580` (autoUpdater), `.github/workflows/build-release.yml:592-648`
- **Status**: Existing: #4905
- **Description**: electron-updater is the shipped update channel. On Windows the Authenticode publisher check of a downloaded update is explicitly turned off, and the release binaries are not code-signed (no Developer ID or notarization: `hardenedRuntime: false`, `gatekeeperAssess: false` for mac). The only integrity anchor left is the sha512 in `latest.yml` served from the same GitHub release as the installer. The optional GPG signature over `SHA256SUMS.txt` is skipped with a warning when `RELEASE_GPG_PRIVATE_KEY` is not set, and the updater does not consume it anyway. `autoInstallOnAppQuit = true` means a downloaded update installs on quit.
- **Evidence**: `"win": { ..., "verifyUpdateCodeSignature": false }`; `autoUpdater.autoInstallOnAppQuit = true;` The workflow step "Warn if checksums are unsigned" runs when the GPG secret is not configured.
- **Exploit Scenario**: An attacker who gets write access to the GitHub release (stolen maintainer token, compromised CI) replaces the installer and `latest.yml` with a matching sha512. Installed clients download and install it, since no publisher signature is checked. Without a signing cert the updater has no signer identity to pin.
- **Impact**: Code execution as the user on every installed client that takes the update.
- **Suggested Fix**: Obtain Authenticode and Developer ID certificates, sign and notarize the builds, remove `verifyUpdateCodeSignature: false`, and make the GPG-signed checksum mandatory in the release job.

### MEDIUM

### A03-1: Repeated ARTIST/GENRE tag values have no count cap and are de-duplicated in O(n^2)
- **Severity**: MEDIUM
- **OWASP Category**: A03 (crafted-metadata resource abuse; adjacent A04)
- **Location**: `auralis/library/scanner/metadata_extractor.py:134-140,160-166` (`_distinct`), `auralis/library/scanner/metadata_extractor.py:247-259`, `auralis/library/repositories/track_repository_lifecycle.py:84-91,192`
- **Status**: NEW (adjacent closed #6165 capped genre count only; #6154 closed the artist regex; #5732 introduced keep-all-values)
- **Description**: Since #5732 `extract_metadata` keeps every value of a repeated ARTIST/GENRE tag (Vorbis, multi-valued ID3, MP4 list) via `_distinct`, a list-membership dedup (`value not in seen`) that is quadratic in the number of distinct values. Nothing bounds the number of values before it. Downstream, `_validate_and_normalize_track_info` truncates each artist to 200 chars and caps genres at `MAX_GENRES_PER_TRACK=20`, but there is NO cap on the number of artists, so `_get_or_create_artists` runs 2-3 queries and creates one `Artist` row plus one `track_artist` link per value. #6165's own issue text predicted this ("once #5732 keeps full lists") and only the genre half was fixed.
- **Evidence**: `kept = self._distinct(self._normalize_field_value(field, v) for v in values if v)` with
  `for value in values: if value is not None and value not in seen: seen.append(value)`. Measured against the current code with a mock tag object holding N distinct ARTIST values: N=2,000 -> 0.01 s, N=10,000 -> 0.29 s, N=40,000 -> 4.6 s (quadratic; N=500k extrapolates to roughly 10+ minutes). `track_info['artists'] = [a[:200] for a in ...]` has no `[:N]` slice (contrast `[:MAX_GENRES_PER_TRACK]` three lines below).
- **Exploit Scenario**: A user scans a folder containing a downloaded FLAC/OGG whose Vorbis comment block (up to 16 MiB, so several hundred thousand `ARTIST=` entries) or a many-valued TPE1 frame holds a huge number of distinct values. The scan worker spends minutes in pure-Python dedup holding the GIL (the same freeze class as #6154), then inserts one Artist row per value; the Artists view and that track's payload are flooded with fake artists, and removing the file leaves the orphan sweep to delete them one by one.
- **Impact**: Local denial of service (backend stall during scan, same blast radius as #6154), library/DB pollution, oversized track/artist payloads.
- **Suggested Fix**: Slice `values` (e.g. `values[:MAX_TAG_VALUES]`, ~20) before `_distinct`, use a `dict`/set based dedup, and cap `track_info['artists']` in `_validate_and_normalize_track_info` next to `MAX_GENRES_PER_TRACK` so non-scanner callers (metadata edit, upload) are covered too.

### A04-1: FFmpeg decode guards trust the container's declared duration; a crafted file bypasses `MAX_DURATION_SECONDS`, the 6 GiB decode cap and the free-space check
- **Severity**: MEDIUM
- **OWASP Category**: A04
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:124-170` (`_probe_or_fail`, `_decode_wav`), `auralis/io/loaders/ffmpeg_stream_decode.py:20-39` (`decode_to_wav`), `auralis/io/loaders/ffmpeg_command.py:19-67` (`build_ffmpeg_cmd`, no `-t`/`-fs`), `auralis/io/loaders/ffmpeg_space.py:19-35`, `auralis-web/backend/core/seekable_source.py:142-185`
- **Status**: NEW (related closed hardening: #3671, #4875, #5734, #6166 all assume the probed duration is honest; none covers a header that under-reports)
- **Description**: For the FFmpeg-routed formats (`.m4a .aac .mp3 .ogg .opus .wma`) every size guard is computed from `ffprobe`'s `format.duration` before the decode: the 7200 s cap, `oversize_decode_detail` (6 GiB), and `require_decode_space` (free space for the float32 WAV). The decode itself is run with no `-t` and no `-fs` output limit, and nothing compares the decoded length against those limits afterwards. `decode_to_wav` (the path used by `SeekableSource` for every playback/chunked render of a non-natively-seekable file, and by `SimpleMastering`) only calls `check_truncation_frames`, which rejects a decode that is too SHORT (<10% of expected) and never one that is too long. In an MP4/M4A the duration ffprobe reports comes from the `mvhd`/`mdhd` header fields, which are independent of the sample table, so a crafted file can report 30 s and still contain hours of (very small, silent) AAC frames. An MP3 with a short Xing frame count behaves the same way. The only remaining bound is `FFMPEG_DECODE_TIMEOUT_S = 300`, and silent AAC decodes at several thousand times real time.
- **Evidence**: Reproduced in a scratch dir (no repo files touched, scratch HOME): a 6.2 MB `.m4a` made with `ffmpeg -f lavfi -i anullsrc -t 14400 -c:a aac -b:a 16k`, with the `mvhd`/`mdhd` duration fields patched to 30 s.
  ```
  get_audio_info(p)['duration_seconds']  -> 30.0
  decode_to_wav(Path(p), tmpdir)         -> OK, no rejection: decoded 14400 s, 5.08 GB WAV, in 3.9 s   (MAX_DURATION_SECONDS = 7200)
  load_audio(p, "audio", tmpdir)         -> rejected only AFTER the full 5 GB was written: "exceeds maximum duration (14400s > 7200s)"
  ```
  A 1.5 MB m4a (3600 s real, 30 s declared) decoded to a 1.27 GB WAV and loaded into RAM via `load_audio` because the post-decode check (3600 s < 7200 s) also passed. Throughput observed: ~1.3 GB of WAV per second, so the 300 s timeout is not a meaningful bound.
  Call path: scan stores the lie as `Track.duration` -> user plays/enhances the track -> `ChunkedAudioProcessor` / `stream_normal.acquire_conversion` -> `SeekableSource.resolve()` -> `convert_to_temp_wav()` -> `decode_to_wav()` -> `_decode_wav()`: `_probe_or_fail` passes on the declared 30 s, `require_decode_space(window=30 s)` passes, FFmpeg writes the real length to the temp dir.
- **Exploit Scenario**: A user adds a downloaded album folder containing a crafted `track.m4a` (about 100-500 MB of near-empty AAC frames, or a few MB for several GB). The library shows a 30 s track. On play (or when the streamlined cache worker pre-renders it) FFmpeg writes tens to hundreds of GB of float32 WAV into `/tmp` for up to 300 s: on a tmpfs `/tmp` this is RAM and ends in an OOM kill or a frozen desktop, on disk it exhausts free space for every other application (ENOSPC), and `sanitize_wav_in_place` then re-reads the whole result. The same decode runs again on every play.
- **Impact**: Availability of the host (disk/RAM exhaustion) from a single untrusted media file, bypassing three separate explicit guards.
- **Suggested Fix**: Bound the decode by the policy, not by the header: pass `-t min(declared_duration * k + slack, MAX_DURATION_SECONDS)` and an output size limit (`-fs`, derived from `MAX_DECODED_BYTES`) in `build_ffmpeg_cmd`, and in `_decode_wav`/`decode_to_wav` re-check the written WAV's actual frames/duration against `MAX_DURATION_SECONDS` and `oversize_decode_detail` (delete and raise on excess), so an over-long decode is stopped while writing rather than after.

---

### A06-1: soundfile 0.14.0 wheel bundles libsndfile 1.2.2, with open memory-corruption CVEs, and it parses untrusted files in-process
- **Severity**: MEDIUM
- **OWASP Category**: A06
- **Location**: `requirements.txt` (`soundfile==0.14.0`), `requirements-lock.txt`; reached from `auralis/library/scanner/audio_analyzer.py:66`, `auralis/io/loaders/soundfile_loader.py:85,118`, `auralis/io/audio_probe.py:99`, `auralis/analysis/fingerprint/track_audio.py:87`
- **Status**: NEW
- **Description**: The pinned soundfile wheel carries its own libsndfile, not a distro copy. Confirmed in the dev venv: `soundfile.__libsndfile_version__ == '1.2.2'`. The NVD lists unfixed-in-1.2.2 memory-safety CVEs for exactly that version:
  - CVE-2025-52194 (CVSS 7.5): heap buffer overflow in `ircam_read_header`, `src/ircam.c:164`.
  - CVE-2026-37555 (CVSS 7.5): 32-bit overflow of `samplesperblock * blocks` in the IMA ADPCM WAV path, causing heap overflow or DoS. It is attacker-controlled from the WAV header and an incomplete fix of CVE-2022-33065.
  - CVE-2024-50612 (out-of-bounds read in the Vorbis writer) and CVE-2024-50613 / CVE-2025-56226 (encoder-side, not reachable from read paths). Only the first two are reachable.

  pip-audit and `pnpm audit` cannot see these, because the vulnerable code is a bundled native library, not a PyPI package. soundfile 0.14.0 is the newest PyPI release, so there is no upstream wheel to bump to. The loader never restricts libsndfile to a format. `sf.info(path)` and `sf.read(path)` auto-detect by content, not by extension. The extension allowlist (`auralis/io/formats.py`: wav/flac/aiff/au) only gates which files the scanner picks up. A file named `x.wav` containing an IRCAM or crafted IMA-ADPCM header is still parsed by the vulnerable code.
- **Evidence**: `auralis/library/scanner/audio_analyzer.py:66`: `sf_info = sf.info(file_path)` (also the fallback for `.mp3/.ogg/...` when ffprobe yields nothing, so any scanned file can reach it). `soundfile_loader.py:85,118`: `sf.info(str(file_path))` then `sf.read(...)` with no `format=` / subtype restriction. `.venv/bin/python -I -c "import soundfile; print(soundfile.__libsndfile_version__)"` gives `1.2.2`.
- **Exploit Scenario**:
  1. The attacker distributes a crafted music file (a "free album" download, a shared folder).
  2. The user adds the folder in Auralis, or plays the file.
  3. The scanner calls `sf.info()` in the backend process; the in-process C library hits the heap overflow.
  4. The backend crashes (DoS) or, with a tuned file, memory corruption in the backend process. That process has full access to the user's library and files, and is a localhost HTTP server.

  Unlike FFmpeg, this decode runs in-process and not in a subprocess.
- **Impact**: Backend process crash at minimum, and potential code execution as the user. Needs one user action (scan or play of a hostile file). Exploitability is uncertain: the CVEs are published, but I did not build a PoC.
- **Suggested Fix**: Pass an explicit `format=` and subtype allowlist (derived from the extension via `soundfile_format_name`) to `sf.info`/`sf.SoundFile`/`sf.read`, so IRCAM/MAT/PAF/etc. are never opened. Magic-check IMA-ADPCM WAV and refuse it, or route it through FFmpeg. Add an advisory note and watch for a soundfile or libsndfile release (>=1.2.3 or a git fix of CVE-2026-37555 / 9a82911). Optionally add a CI step that reports the bundled `__libsndfile_version__`.

### LOW

### A01-1: Files stored by `POST /api/files/upload` land outside the path allowlist, so every path-validated route rejects the tracks it just created
- **Severity**: LOW
- **OWASP Category**: A01 (an allowlist that is inconsistent with the app's own storage location; fails closed)
- **Location**: `auralis-web/backend/routers/files_upload.py:67,155-161` (storage dir), `auralis-web/backend/security/path_allowlist.py:19-23,90-115` (allowlist), `auralis-web/backend/core/stream_track_resolution.py:67-84` (consumer)
- **Status**: NEW (the related closed issues #2392, #5865 and #5968 cover other defects: temp-file deletion, manual scan not registering a folder, and orphaned uploads)
- **Description**: The upload route moves each accepted file to `Path.home()/".auralis"/"uploads"/<uuid><ext>` and inserts a `Track` row with that `filepath`. `get_allowed_directories()` is only `~/Music`, `~/Documents`, `XDG_MUSIC_DIR` and registered scan folders. Nothing registers the uploads directory, in the route or at startup (`_register_scan_folders` registers only the configured scan folders). Every path-validated consumer therefore refuses these tracks as "outside allowed directories". Those consumers are: WS `play_normal` / `play_enhanced` / `seek` (reported to the client as "Audio file not found"), metadata read and write, lyrics extraction, and the mastering recommendation. Only the unvalidated playback and queue load path (#5303) would still serve them.
- **Evidence**: Running `get_allowed_directories()` in this checkout returns `[/home/matias/Music, /home/matias/Documents]`, while the upload destination is `/home/matias/.auralis/uploads`. In `stream_track_resolution.py`, `validate_file_path(str(track.filepath))` raises `PathValidationError`, and the client gets `_send_error(..., "Audio file not found")`. A grep for `register_allowed_directory` shows callers only in `routers/settings.py` and `config/startup/components.py` (scan folders).
- **Exploit Scenario**: There is no attacker gain. The mismatch is fail-closed. A client (a script or a future UI) that uploads a file gets `status: success` and a `track_id`, then every streaming, metadata and lyrics request for that track is denied. The current frontend does not call `/api/files/upload` (no consumer found), so the effect is dormant today. The endpoint still accepts up to 500 MB per file into `~/.auralis`, so it exposes write surface without a working read path.
- **Impact**: Availability and consistency only. The failure is silent and invites someone to "fix" it by widening the allowlist (for example, adding the whole data dir), which would weaken #2562.
- **Suggested Fix**: Either register the uploads directory (`get_data_dir()/uploads`, one fixed location) as an allowed directory at startup, or remove the library-ingesting upload route if no client needs it. Also derive the upload directory from `auralis.library.data_dir` rather than `Path.home()/".auralis"`, so it follows `AURALIS_DATA_DIR`.

### A02-2: Chunk-cache owner marker is a fixed-name file in the shared temp root, written without symlink or ownership protection
- **Severity**: LOW
- **OWASP Category**: A05 (insecure temp file; cross-listed under A02 because it is the one fixed-name file left outside the `create_secure_temp_dir` hardening)
- **Location**: `auralis-web/backend/config/startup/tempfiles.py:140-179` (`claim_chunk_cache`), caller `:226-231`; name from `auralis-web/backend/config/limits.py:62`
- **Status**: NEW
- **Description**: The sibling directories `auralis_chunks` and `auralis_processing` get `create_secure_temp_dir` (0700, symlink refusal, owner check, #4855/#6155). The marker `<tempdir>/auralis_chunks.owner` gets none of that. It is read with `Path.read_text()` and written with `Path.write_text(str(os.getpid()))` (plain `open(..., "w")`, which follows symlinks and truncates), and it is created at the umask default (observed 0664 on this host). Its contents are trusted: a numeric value naming a live PID makes `claim_chunk_cache` return False, so the startup wipe is skipped.
- **Evidence**: `owner_marker.write_text(str(os.getpid()))` and `recorded = owner_marker.read_text().strip()` at lines 162 and 176, with `owner_marker = temp_root / CHUNK_TEMP_OWNER_FILENAME` and `temp_root = Path(tempfile.gettempdir())`. `/tmp/auralis_chunks.owner` on this host is mode 664.
- **Exploit Scenario**: On a multi-user Linux host another local account pre-creates `/tmp/auralis_chunks.owner` before the victim first launches Auralis. (a) As a regular file owned by the attacker containing `1`: the victim's `write_text` fails with PermissionError, which is swallowed at debug level, and the marker keeps naming a live PID forever. The "wipe stale chunks on start" invariant (#4666/#4713) then never runs for the victim. (b) As a symlink to a file the victim owns: `write_text` truncates and overwrites it with a PID, but only if `fs.protected_symlinks` is 0. It is 1 by default on current Linux, which mitigates this, and macOS and Windows use per-user temp roots.
- **Impact**: Low. Local, multi-user-host only, no secret exposed, and the chunk directory itself stays 0700. The result is a defeated cleanup invariant (stale cached chunks survive restarts) or, with protected_symlinks off, a clobbered user-owned file.
- **Suggested Fix**: Put the marker inside the 0700 `auralis_chunks` directory, or open it with `os.open(..., O_WRONLY|O_CREAT|O_NOFOLLOW, 0o600)` after an `lstat` ownership check, and treat a marker not owned by the current user as absent.

### A03-2: Embedded lyrics read from the file are persisted and returned with no length bound
- **Severity**: LOW
- **OWASP Category**: A03 (untrusted tag content) / A04
- **Location**: `auralis-web/backend/services/lyrics_extraction.py:30-36,39-71`, `auralis-web/backend/routers/tracks.py:156-171`, `auralis/library/models/track.py:84`
- **Status**: NEW
- **Description**: Every other string tag is capped at ingest (`MAX_TAG_TEXT_CHARS=1000`, title/album 500, artists 200, genres 100) and the metadata PUT caps lyrics at `_LYRICS_TAG=100_000`. The lyrics fallback in `GET /api/library/tracks/{id}/lyrics` takes `_first_text()` of a USLT / `LYRICS` / `\xa9lyr` value with no cap, writes it to `Track.lyrics` (unbounded `Text`) via `update_metadata`, and returns it. `_apply_metadata_fields` does not truncate either.
- **Evidence**: `text = str(value).strip(); return text or None` then `repos.tracks.update_metadata(track_id, lyrics=lyrics_text)` and `return result` with the full text.
- **Exploit Scenario**: A crafted MP3 carries a multi-MB (ID3v2 frames can be up to 256 MB) USLT frame. Opening the lyrics panel for that track loads it through mutagen, stores it in the SQLite library permanently and ships it to the UI on every later lyrics fetch (and the metadata GET returns the file's tags unbounded).
- **Impact**: DB bloat, memory/bandwidth/UI cost; low because it requires a hostile file in the library plus a lyrics request, and lyrics are excluded from list payloads (#5906).
- **Suggested Fix**: Truncate extracted lyrics to the same `_LYRICS_TAG` (100,000) used by the write path, in `extract_embedded_lyrics`, so the cap is shared by both paths.

### A03-3: Lucene query injection through album/artist tag text in the MusicBrainz lookups
- **Severity**: LOW
- **OWASP Category**: A03
- **Location**: `auralis-web/backend/services/artwork_providers/musicbrainz.py:48-52`, `auralis/services/artwork_sources/musicbrainz.py:81-88`
- **Status**: NEW
- **Description**: The artist and album strings (tag-derived, up to 500 chars) are interpolated into a MusicBrainz Lucene query as `artist:"{artist}" AND release:"{album}"` (and `artist:{name}` unquoted in the artist-image service) with no escaping of `"`, `\`, `:`, `(`, `AND/OR`. URL encoding (aiohttp `params`, `urllib.parse.quote`) protects the HTTP layer but the server decodes it back into query syntax.
- **Evidence**: `"query": f'artist:"{artist}" AND release:"{album}"'`.
- **Exploit Scenario**: A file tagged album `x" OR release:"Some Famous Album` (or an artist crafted likewise) makes `POST /api/albums/{id}/artwork/download` search a different release and store that release's cover (from the trusted Cover Art Archive host) as the album's artwork.
- **Impact**: Integrity only: wrong or chosen cover art; host, size, pixel and image-type checks (`validate_artwork_url`, `_get_trusted_artwork`, `open_bounded_image`) still apply, so there is no SSRF, file or code impact.
- **Suggested Fix**: Escape Lucene special characters (backslash, quotes and `+ - && || ! ( ) { } [ ] ^ ~ * ? : /`) in a shared helper before interpolation, in both MusicBrainz call sites.

---

### A04-2: `upload-and-process` has no aggregate disk quota, and a failed job keeps its (up to 500 MB) input until the 1 h TTL
- **Severity**: LOW
- **OWASP Category**: A04
- **Location**: `auralis-web/backend/routers/processing_upload.py:88-124`, `auralis-web/backend/core/job_cleanup.py:55-65`, `auralis-web/backend/core/job_execution.py` / `job_finalize.py` (no input removal on failure), `auralis-web/backend/config/limits.py:28-43` (quotas exist only for `/api/files/upload`)
- **Status**: NEW (sibling of #6167 and #5968, closed: they added `UploadBudget` and failure cleanup to `/api/files/upload` only)
- **Description**: `/api/files/upload` is capped per request (2 GiB) and on disk (20 GiB, `UploadBudget`). `/api/processing/upload-and-process` writes each upload (limit 500 MB, magic-byte sniff only) to `<tmp>/auralis_uploads/<uuid><ext>` with no directory budget. When the job fails (a file with a valid magic prefix and garbage body fails at decode within seconds) nothing deletes the input: only `cleanup_expired_jobs` removes it, once `completed_at` is more than `completed_job_ttl_hours` (1 h) old. The queue bound (20) only limits QUEUED jobs, not terminal ones, and the rate limit (`/api/processing` prefix, 10/min) is the only brake. Each upload is also read fully into RAM (`file.read(MAX+1)`).
- **Evidence**: `content = await file.read(_MAX_UPLOAD_BYTES + 1)` then `_write_upload(...)`; `submit_job` only raises `QueueFull` for queued jobs; `cleanup_expired_jobs` deletes `input_path` only for jobs in `TERMINAL_STATUSES` older than the TTL; no `unlink` of `job.input_path` anywhere in `job_execution.py`, `job_finalize.py`, `job_lifecycle.py`.
- **Exploit Scenario**: A local process (or a buggy client loop) posts 500 MB files with a `RIFF`/`ID3` prefix at the allowed 10/min: each becomes a FAILED job whose input stays on disk for an hour, about 5 GB/min, up to hundreds of GB per hour, in the OS temp dir (often tmpfs).
- **Impact**: Disk/RAM exhaustion on the host by a local client; requires local access (cross-origin pages are stopped by `OriginCheckMiddleware`), hence LOW. Inconsistent with the quota the sibling upload route already has.
- **Suggested Fix**: Reuse `UploadBudget`/`MAX_UPLOAD_DIR_BYTES` for the `auralis_uploads` directory in `upload_and_process`, and remove an upload-owned input as soon as its job reaches FAILED/CANCELLED (the TTL sweep can keep only outputs).

### A05-1: WebSocket handshake rejections are logged one WARNING per attempt, with the attacker-supplied Origin
- **Severity**: LOW
- **OWASP Category**: A05 (overlaps A09: log flooding)
- **Location**: `auralis-web/backend/config/globals.py:138`, `:145-147`, `:160`
- **Status**: NEW (the same defect #6188 closed for the REST origin check, Host/CORS refusals and per-message WebSocket validation; the handshake path was never converted to `warn_throttled`)
- **Description**: `ConnectionManager.connect()` rejects an untrusted Origin, an empty Origin from a non-loopback peer, and a full connection table (`WS_MAX_CONNECTIONS`) with a plain `logger.warning(...)`. Every other page-triggerable rejection goes through `warn_throttled()` (`origin_check.py`, `logged_rejections.py`, `websocket_security.py`, `routers/system.py:135`) precisely because electron-log keeps only 1 MiB plus one archive and a flood evicts earlier security entries (#6188). The handshake rejection is the cheapest of all for a hostile page to trigger, and the Origin it embeds is attacker-controlled (up to the 16 KiB header limit).
- **Evidence**: `config/globals.py:136-147`: `if origin not in ALLOWED_WS_ORIGINS: logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")`. Reproduced against the real app: 25 handshakes with `Origin: http://evil.example...` produced 25 WARNING lines (`rejection warnings: 25`), each carrying the full origin string. `grep warn_throttled` shows no use in `config/globals.py`, and `tests/backend/test_rejection_logs_throttled_6188.py` covers only the REST POST flood.
- **Exploit Scenario**: A web page the user has open runs `for(;;) new WebSocket("ws://localhost:8765/ws")`. The `Host` header is `localhost:8765`, so TrustedHost passes, and the Origin check refuses each socket after a bare `accept()`. The backend writes one WARNING per attempt to the Electron-captured log until the 1 MiB / one-archive retention has rotated out earlier entries (for example prior path-traversal or origin-rejection evidence).
- **Impact**: Loss of security-log evidence and log-disk churn; no data exposure.
- **Suggested Fix**: Use `warn_throttled(logger, "ws.untrusted_origin", ...)` (and sibling keys for the non-loopback and connection-limit cases) in `ConnectionManager.connect`, and add the handshake case to the #6188 test module.

### A05-2: `cleanupPort()` still stops any listener whose command line contains `/backend/main.py`
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `desktop/port-cleanup.js:23` (`BACKEND_COMMAND_PATTERN`), used by `findListeners()` and `AuralisApp.cleanupPort()` at `desktop/main.js:74-95`
- **Status**: NEW (residual gap in the #6157 fix, which is closed: it narrowed the target to LISTEN-state processes but kept an identity test that is not specific to Auralis)
- **Description**: The test for "this listener is the Auralis backend" is `/auralis-backend|[\\/]backend[\\/]main\.py/i`. The second alternative matches the path of any project's `backend/main.py`, and the first matches any command line containing `auralis-backend` anywhere. 8765 is a popular local dev port. Any process the user owns that listens on 8765 and was started as `python …/backend/main.py` is SIGTERMed, then SIGKILLed after 3 s, every time Auralis launches.
- **Evidence**: `node -e "require('./port-cleanup').isAuralisBackendCommand(...)"` returned `true` for `python /home/u/otherapp/backend/main.py --port 8765`, `/usr/bin/python3 /srv/shop/backend/main.py`, and `node /x/auralis-backend-viewer.js`. The unit tests only exercise `node vite`, `python -m http.server` and a chrome helper as negatives.
- **Exploit Scenario**: The user runs an unrelated FastAPI app (`python backend/main.py`, port 8765) and starts Auralis; the other app is killed without warning (data loss for anything unsaved). A hostile same-user process can also get a victim process killed by sharing that name pattern, though that user could kill it directly anyway.
- **Impact**: Availability or data loss in an unrelated local service; bounded to the same OS user.
- **Suggested Fix**: Anchor the match on the exact binary or script paths Auralis spawns: compare the listener's executable or argv path with `path.join(process.resourcesPath, 'backend', ...)` (packaged) or the repository `auralis-web/backend/main.py` (dev), or drop the generic `backend/main.py` alternative and match on a marker argument or environment value the spawn adds.

### A05-3: CSP keeps `script-src 'unsafe-inline'`
- **Severity**: LOW
- **OWASP Category**: A05
- **Location**: `auralis-web/backend/config/middleware/security_headers.py:106-130`
- **Status**: Existing: #5484 (OPEN)
- **Description**: With `'unsafe-inline'` in `script-src` the CSP does not stop injected inline script if an HTML-injection bug ever appears in the renderer. The source documents why it is kept (Vite's build ships a per-build inline loader and there is no browser-driven test to validate a hash/nonce). No new evidence beyond the open issue; the rest of the CSP (`default-src 'self'`, `form-action`, `base-uri`, `media-src`, no `frame-ancestors` but `X-Frame-Options: DENY`) is sound.
- **Evidence**: `f"script-src 'self' 'unsafe-inline'{script_cdn}; "` in `SecurityHeadersMiddleware.dispatch`; header observed on every response in the live probe.
- **Exploit Scenario**: Requires a separate injection bug; none found in this category.
- **Impact**: Defence-in-depth gap only.
- **Suggested Fix**: As tracked in #5484.

### A05-4: Electron loads and trusts `http://localhost:8765` while the backend binds only `127.0.0.1`
- **Severity**: LOW
- **OWASP Category**: A05 (A07 adjacent)
- **Location**: `desktop/url-safety.js:36-38` (`APP_ORIGIN`), `desktop/main.js:322-327`, `auralis-web/backend/main.py:122`
- **Status**: Existing: #6169 (OPEN)
- **Description**: The privileged window (preload exposes `electronAPI` to exactly this origin) is loaded from the hostname `localhost`, which a browser engine may resolve to `::1` first, whereas the backend listens on IPv4 loopback only. On a multi-user host another account that binds `[::1]:8765` before Auralis starts could be what the window connects to, and it would receive the IPC-bearing origin. Backend-side defences (Host, Origin, rate limit) do not apply because the request never reaches the backend. I could not verify Chromium's address-order choice here, so exploitability is unconfirmed; the issue already tracks the mismatch.
- **Evidence**: `APP_ORIGIN = http://localhost:${APP_PORT}`; `uvicorn.run(..., host="127.0.0.1")`; `hosts.py` comment states the v6 loopback "never reaches this process".
- **Exploit Scenario**: Hostile local account on a shared machine squats `[::1]:8765`; user launches Auralis; the window may render attacker content with `electronAPI` (native file/folder pickers, window controls).
- **Impact**: UI spoofing / limited IPC exposure on shared hosts only.
- **Suggested Fix**: As tracked in #6169 (use the literal `127.0.0.1` for load, trust and health check, or bind both families).

---

### A06-2: uv.lock still pins advisory-listed packages (certifi, urllib3, msgpack, multidict); the dev venv runs them (incomplete fix of #6178)
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: `uv.lock:242-243` (certifi 2026.7.22), `:852-853` (msgpack 1.2.1), `:882-883` (multidict 6.7.1), `:1676-1677` (urllib3 2.7.0); `.github/workflows/dependency-audit.yml:53-62`
- **Status**: Regression of #6178 (CLOSED). The issue's own acceptance criterion "uv.lock no longer pins certifi/urllib3 below the fixed versions" is not met. The new gate only audits `requirements-lock.txt`.
- **Description**: `pip-audit` on `uv export --frozen --no-hashes` of the tracked `uv.lock` reports 7 vulnerabilities in 4 packages:
  - certifi PYSEC-2026-4320 (fix 2026.10.18)
  - urllib3 PYSEC-2026-4175, -4176, -4177 (fix 2.8.0)
  - msgpack CVE-2026-114613 (fix 1.2.3)
  - multidict PYSEC-2026-4244 (fix 6.9.1)

  `requirements-lock.txt` already has the fixed versions (certifi 2026.10.19, urllib3 2.8.0, msgpack 1.2.4, multidict 6.9.1). The user's dev `.venv` is installed at the stale versions (`certifi 2026.7.22, urllib3 2.7.0, msgpack 1.2.1, multidict 6.7.1`). `uv.lock` was last touched 2026-11-17 (`87fa329aa`, #6283) without refreshing these. Nothing audits it.
- **Evidence**: `uv export --frozen --no-hashes` then `pip-audit --no-deps --disable-pip` gives the 7 results above. `dependency-audit.yml` runs `pip-audit -r requirements-lock.txt` only. The packages come in transitively via librosa/pooch/requests and aiohttp, not through app code.
- **Exploit Scenario**: Limited. Developer or CI machine using the lock, for example urllib3 handling hostile redirects during a pooch/librosa dataset download. The shipped binary is built from `requirements-lock.txt`, not `uv.lock`.
- **Impact**: Developer-environment exposure only; the stale lock can also be re-introduced into a build by someone who runs `uv sync`.
- **Suggested Fix**: Run `uv lock --upgrade-package certifi --upgrade-package urllib3 --upgrade-package msgpack --upgrade-package multidict`. Extend `dependency-audit.yml` to audit `uv export --frozen`, or stop tracking `uv.lock`.

### A06-3: Electron is locked to 43.8.3, seven patch releases behind and on the oldest supported major; version-update PRs are disabled for /desktop
- **Severity**: LOW
- **OWASP Category**: A06
- **Location**: `desktop/pnpm-lock.yaml:396,1597` (electron@43.8.3), `desktop/package.json` (`"electron": "^43.8.3"`), `desktop/electron-version.test.js:1-10`, `.github/dependabot.yml` (`/desktop`, `open-pull-requests-limit: 0`)
- **Status**: NEW (the closed advisory-based #6152 is fixed; this is the follow-on drift)
- **Description**: npm now offers Electron 43.8.10 on the same major (released 2026-11-12) and 45.3.4 as latest. 43.8.4 to 43.8.10 are Chromium/V8 backport releases. There is no published advisory against 43.8.3, but the repo's own test comment requires >=43.8.3 "for the Chromium/V8 security backports in between", which shows that patch lag matters here. Electron supports the latest three majors (43, 44, 45), so 43 reaches EOL when 46 ships (about 8 weeks after 45.0.0, 2026-10-21). The only guard, `MIN_43 = [43,8,3]`, is a manual floor that has to be raised by hand. Dependabot is set to security-updates-only for this directory, and GitHub advisories are not issued per Chromium patch, so nothing prompts a refresh.
- **Evidence**: `npm view electron time` (43.8.4 to 43.8.10 published after the lock); `gh api /advisories?...affects=electron@43.8.3` returned nothing today.
- **Exploit Scenario**: A Chromium renderer or V8 bug fixed in 43.8.4+ is exploited through content in the BrowserWindow. Exposure is reduced because navigation is confined to the app origin by `url-safety.js`, but the update channel (electron-updater) and the localhost backend are in the same process family.
- **Impact**: A window of unpatched-Chromium exposure for packaged installs.
- **Suggested Fix**: Bump to the latest 43.8.x (or 44/45 after a smoke test) and refresh the lock. Enable Dependabot version updates for `/desktop` (grouped, reviewed), or a scheduled "electron behind latest patch" check.

### A06-4: Backend/slow CI installs unpinned and unhashed test tooling (`pip --upgrade`, pytest-asyncio, pytest-timeout, httpx2, pip-audit)
- **Severity**: LOW
- **OWASP Category**: A06 (supply chain)
- **Location**: `.github/workflows/backend-tests.yml:111,128`, `.github/workflows/slow-tests.yml:34,36`, `.github/workflows/dependency-audit.yml:57`
- **Status**: NEW (sibling of closed #6151, which fixed only the release build tooling)
- **Description**: The runtime lock is installed with `--require-hashes`, but the same jobs then run `python -m pip install --upgrade pip` and `pip install 'pytest==9.0.1' pytest-asyncio pytest-timeout httpx2` with no versions or hashes. The `pip-audit` job also installs `pip-audit` unpinned. A hijacked release of any of these runs arbitrary code on the runner. The test jobs have `permissions: contents: read` and do not build the release artifacts (that path is hash-locked), so the blast radius is limited to CI. A compromised test dependency could however falsify the pytest ratchet, and `pip-audit` could report a pass for a bad lock.
- **Evidence**: See the lines cited above.
- **Exploit Scenario**: A malicious `pytest-timeout` or `httpx2` release is uploaded to PyPI. The next CI run executes it with the job's token and cache.
- **Impact**: CI integrity only; it does not reach release binaries.
- **Suggested Fix**: Add a hash-locked `requirements-test.txt` (like `requirements-build.txt`) and install it with `--require-hashes`. Pin pip and pip-audit.

### A07-1: Loopback API is unauthenticated across OS users; the documented residual-risk argument does not hold for that actor
- **Severity**: LOW (borderline design decision; shared multi-user hosts only)
- **OWASP Category**: A07
- **Location**: `docs/security/SECURITY_MODEL.md` (Residual risk), `auralis-web/backend/main.py:120-130`, `auralis-web/backend/config/globals.py:106-121`, `auralis-web/backend/config/middleware/origin_check.py:117-131`
- **Status**: NEW. Related to #4385 (closed, covers only same-user processes) and #6169 (open, mentions the multi-user premise for a different symptom).
- **Description**: `SECURITY_MODEL.md` accepts "no auth" because a co-resident process "already holds the user's filesystem privileges". That is true for the same OS user. On a shared Linux or macOS host, a different local account can also reach `127.0.0.1:8765`; loopback is machine-wide. It needs no Origin (empty Origin from a loopback client is accepted by both the WS and REST gates), so every gate passes. The other account then acts with the victim's privileges through the app.
- **Evidence**: With no Origin header, against the scratch instance:
  ```
  POST /api/library/scan {"directories":["<any dir the app user can read>"]}
    -> 200 {"files_added":1,...}
  GET /api/library/tracks -> the tracks appear
  ```
  The files are then streamable through the WS `play_normal` path. In my test, a directory under the scratch `$HOME/Music` could be streamed. A directory outside the allowlist (`/tmp/...`) was ingested but blocked at streaming by `path_security`. Other no-credential, state-changing routes: `PUT /api/metadata/tracks/{id}` (tag writes into the victim's files), `POST /api/settings/scan-folders` (persists across restarts), `POST /api/library/reset`, uploads.
- **Exploit Scenario**: On a shared workstation or terminal server, user B runs `curl -X POST 127.0.0.1:8765/api/library/scan` pointing at a directory user A can read but B cannot. B then lists and streams A's audio, rewrites tags in A's files, or resets A's library.
- **Impact**: Cross-account data disclosure of audio files and metadata, tag tampering, and library destruction on multi-user hosts. None of this applies to the single-user desktop model.
- **Suggested Fix**: Cheapest: state in `SECURITY_MODEL.md` that multi-user hosts are unsupported, and why. Real fix: have Electron mint a per-launch random token, pass it to the backend via env and to the renderer, and require it (a header on REST mutations and the WS connect query or subprotocol); empty-Origin loopback clients without the token are refused. The doc already describes this as optional hardening.

### A07-2: Backend outlives the Electron app on macOS after window close and reopen; `isQuitting` is never reset
- **Severity**: LOW
- **OWASP Category**: A07 (session lifecycle and termination)
- **Location**: `desktop/main.js:441-454` (`cleanup`), `:630-634` (`window-all-closed`), `:638-643` (`activate`), `:655-661` (`before-quit`), `:159` (`detached: true`)
- **Status**: NEW (no matching issue)
- **Description**: `cleanup()` sets `this.isQuitting = true` permanently. On macOS, closing the last window calls `cleanup()`, which stops the backend. A later dock `activate` calls `initialize()`, which spawns a new detached backend, but `isQuitting` stays `true`. At Cmd+Q, `before-quit` checks `if (!auralisApp.isQuitting)`, which is false, so it does not call `cleanup()`. Electron exits without terminating the new backend. The same stale flag means a backend crash after reactivation is no longer treated as an error (`main.js:233`). More generally, `detached: true` ties no backend lifetime to the parent. A crash or SIGTERM of Electron also orphans the backend, though that case is the generic one.
- **Evidence**:
  ```js
  cleanup() { this.isQuitting = true; ... }      // :443, never reset in initialize()
  app.on('before-quit', (event) => { if (!auralisApp.isQuitting) { event.preventDefault(); ... } });  // :656
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) auralisApp.initialize(); }); // :638
  ```
  No `will-quit`, `process.on('exit')` or `SIGTERM` handler exists (`grep isQuitting` returns only these sites).
- **Exploit Scenario**: A macOS user closes the window, reopens from the dock, then quits. The unauthenticated API (see A07-1) keeps listening on 127.0.0.1:8765 with a hot library DB until the next launch's `cleanupPort()` reaps it.
- **Impact**: An API the user believes is stopped stays live after quit (local actors only), and the backend is not shut down cleanly, so the WAL checkpoint is skipped. Not remotely exploitable.
- **Suggested Fix**: Reset `isQuitting = false` at the start of `initialize()`, or track backend state per spawn instead. Also kill the backend on `will-quit`, `SIGTERM` and `process.on('exit')`, or give the child a lifetime tie, such as exiting when its stdin pipe closes (the pipe is already open).

### A07-3: Existing: #6171 remainder. A local WS client can hold every stream slot with paused connections (verified live)
- **Severity**: LOW
- **OWASP Category**: A07 / A04
- **Location**: `auralis-web/backend/core/stream_gates.py:45-47` (unbounded pause wait), `core/stream_normal.py:73` and `core/stream_enhanced_lifecycle.py:84` (semaphore held for the stream's lifetime), `core/audio_stream_controller.py:112-132`
- **Status**: Existing: #6171 (OPEN). Parts 1, 2, 3 and 5 are fixed in source: `ws_max_size`, invalid-frame charging, the `WS_MAX_CONNECTIONS` cap and IP-bucket sweeping. Part 4 is still present.
- **Description**: `wait_for_stream_gates` bounds the flow gate (30 s) but deliberately leaves the pause gate unbounded. A paused stream still holds one of the 10 `MAX_CONCURRENT_STREAMS` slots.
- **Evidence**: Against the scratch instance (a 120 s library file under an allowlisted dir). 10 WS connections each sent `play_normal`, waited for `audio_stream_start`, then sent `pause`. An 11th connection's `play_normal` returned `{"type":"audio_stream_error","data":{"error":"Server busy - too many active streams",...}}`, and no audio arrived. The 10 sockets cost 20 messages and need only the app-level heartbeat pongs to stay alive.
- **Exploit Scenario**: A local process (no Origin needed) parks 10 sockets. The user's player cannot start playback until those sockets close or the backend restarts. Cross-origin pages cannot do this (the Origin gate rejects them).
- **Impact**: Local denial of playback.
- **Suggested Fix**: Release the stream semaphore while paused (re-acquire on resume), or add a pause-gate timeout that ends the stream. Count paused streams per connection.

### A07-4: `SECURITY_MODEL.md` has drifted from the code it calls authoritative
- **Severity**: LOW (documentation accuracy; misleads reviewers of this exact category)
- **OWASP Category**: A07 / A05
- **Location**: `docs/security/SECURITY_MODEL.md` ("Boundaries that bound the risk", "Deployment shape")
- **Status**: NEW
- **Description**: The doc is the stated threat model for the no-auth decision, but it is stale in four ways:
  - It says the WS allowlist includes "`file://` for the Electron renderer". `file://` was removed in #5066, and `ALLOWED_WS_ORIGINS` is now the loopback host x port x scheme matrix from `config/origins.py`.
  - It cites `main.py:210` for the bind, but the bind is at `main.py:123`.
  - It lists three boundaries and omits the ones added since: `OriginCheckMiddleware` for REST (POST, PUT, DELETE and PATCH, plus the `Sec-Fetch-Site` GET gate from #6158), `TrustedHostMiddleware` (DNS rebinding, #4353), `proxy_headers=False` (#6168), and the Electron IPC and navigation gates.
  - It does not list "another OS account on the same machine" as an actor, which is the gap in A07-1.
- **Evidence**: `docs/security/SECURITY_MODEL.md` boundary 2 text vs. `config/globals.py:25-47` and `config/middleware/__init__.py:99-103`.
- **Exploit Scenario**: A reviewer or contributor relies on the doc, concludes `file://` pages may connect, or misses that REST has its own origin gate, and either re-widens the allowlist or skips a REST check on a new route.
- **Impact**: Wrong security assumptions; no direct runtime exposure.
- **Suggested Fix**: Rewrite the boundary list from the code, add the multi-user actor and its accepted or unaccepted status (see A07-1), and drop the line-number links (or point at symbols).

### A08-1: A `.25d` sidecar from an untrusted music folder still forges stored fingerprints (validation is attacker-satisfiable and skips `band_pct_valid`)
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/library/sidecar_validation.py:47-73`, `auralis/library/sidecar_fingerprint_check.py:16-71`, `auralis/services/fingerprint_extractor.py:84-100,119-152`, `auralis/learning/reference_seeder.py:100-170`
- **Status**: NEW (residual of closed #4910 / #6175 / #4405: the range and finiteness checks they added are present, but the trust model is unchanged)
- **Description**: The extractor treats a `<audio>.25d` file beside the track as authoritative and skips analysis. It is "valid" when format/algorithm version match, `size_bytes` equals the file size, `modified_at` equals the file mtime, and 25 numeric dimensions each have `abs(v) <= 10000`. Every one of those inputs is chosen by whoever authored the sidecar. A music folder obtained from outside (downloaded or shared archive, NAS share, a friend's drive) can ship `track.mp3.25d` next to `track.mp3`; the attacker knows the file size, and zip/tar/7z extraction restores the archive's mtime (zip has 2 s granularity so the isoformat has no sub-second part, which `modified_at_stamp` reproduces). The legacy naive-local-time spelling is also accepted (`mtime_matches`). The 10 000 bound is deliberately not the schema range (comment at `sidecar_fingerprint_check.py:16-19`). Two further gaps: the sidecar path never calls `band_pct_valid()` (every other source does: `FingerprintService._load_from_database`, `_load_from_file_cache`, `windowed_compute`), so a row whose seven band shares do not sum to 1 is stored; DB readers then discard it as "stale" while the coverage/similarity queries (`_current_fingerprint_clause`: only `lufs != sentinel` and version) still count and use it.
- **Evidence**: `FingerprintExtractor._load_sidecar_fingerprint` returns `get_fingerprint()` after `is_valid()`; `extract_and_store` then calls `fingerprint_repo.upsert(track_id, fingerprint, ...)` and skips `_write_sidecar` because `cached` is true. `score_fingerprint` (reference_seeder.py:100-134) is a pure function of `lufs`, `crest_db` and the seven band shares: a forged fingerprint with `lufs=-14, crest_db=18` and seven shares of 0.1428 scores exactly 1.0 (the maximum). `select_references` caps at `max(1, 5% of library)` (at most 50) and sorts by score, so a handful of such sidecars take every reference slot in a small or medium library; the cloud feeds `ContinuousMode._derive_target_spectrum` (continuous_mode.py:131-190) on the per-chunk fingerprint path.
- **Exploit Scenario**: 1) Attacker publishes an album archive containing audio files plus crafted `.25d` files (size and mtime set to match). 2) User extracts it into a scan folder; the scan enqueues fingerprinting. 3) The extractor loads the forged vector instead of analysing the audio and stores it as the current-version fingerprint for those tracks. 4) The next reference-cloud refresh (after every scan and queue drain) ranks the forged rows first and flags them as references with weight; playback of the user's other tracks that use the per-chunk path is steered toward the forged spectrum, and the forged tracks themselves are mastered and similarity-matched on fake data.
- **Impact**: Integrity of derived analysis only: wrong mastering EQ/loudness on the affected tracks (gain bounded to +/-24 dB, EQ bounded by clamps), poisoned similarity and reference cloud. No code execution, no file access, no data loss. Requires the user to add an untrusted folder, so LOW.
- **Suggested Fix**: Treat sidecars from the music folder as untrusted input: run `band_pct_valid()` and the real `DIMENSION_SCHEMA` ranges on load, and either bind the sidecar to the audio with a cheap content digest (for example the same first/last-64 KiB hash `FileSignatureService` already computes) or only trust sidecars Auralis wrote (a per-install HMAC key kept in `~/.auralis`). Keep reference selection out of rows whose provenance is a sidecar (or require `is_reference` candidates to have been computed locally).

### A08-2: A sidecar with `lufs = -100.0` collides with the in-band fingerprint-claim sentinel
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/library/repositories/fingerprint_shared.py:39,55-73`, `auralis/library/repositories/fingerprint_scheduler_repository.py:28-57,152-166`, `auralis/library/sidecar_fingerprint_check.py:55-71`
- **Status**: NEW
- **Description**: "Claimed, extraction in progress" is represented by an ordinary fingerprint row with `lufs == -100.0` (`PLACEHOLDER_LUFS_SENTINEL`). Readers exclude that value everywhere, and `release_claims()` (called at every backend start, `cleanup_incomplete_fingerprints`, and on a failed extraction) deletes every such row. A sidecar is allowed to carry `lufs: -100.0` (it satisfies `abs(v) <= 10000`), and `upsert()` writes it with the current `fingerprint_version`, so a forged sidecar plants a row that looks like a permanent in-flight claim.
- **Evidence**: `sidecar_fingerprint_check.py` range test only; `upsert()` validates column names only (`_validate_fingerprint_columns`); `_current_fingerprint_clause` then hides the row. `claim_next_unfingerprinted_track` selects tracks with no row, `claim_next_outdated_fingerprint` selects `fingerprint_version < current`: neither re-selects it.
- **Exploit Scenario**: Same delivery as A08-1 with `lufs: -100.0`. The track gets a row that every reader ignores, so it never has a usable fingerprint until the next backend start deletes the placeholder; the re-extraction then trusts the same sidecar again and recreates it. Net effect: the track is permanently "unfingerprinted" and excluded from similarity and mastering Tier 1.
- **Impact**: Targeted denial of fingerprint features for chosen tracks plus a delete/recreate loop at each startup. Low.
- **Suggested Fix**: Reject `lufs == PLACEHOLDER_LUFS_SENTINEL` (and anything below the meter's real floor, which is -70) in `fingerprint_block_is_valid`; longer term mark claims with a dedicated column rather than a magic dimension value.

### A08-3: Persisted `scan_folders` are re-trusted at every startup without the validation applied at write time
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis-web/backend/config/startup/components.py:93-106`, `auralis-web/backend/security/path_allowlist.py:70-76`, `auralis-web/backend/services/library_auto_scanner.py:272-287`, vs `auralis-web/backend/security/path_security.py:183-243`
- **Status**: NEW (residual of closed #4765; the scratch-root check was added today in `01bb6478a`, so it also only guards new writes)
- **Description**: `validate_user_chosen_directory` (write path) refuses OS directories (`_is_system_directory`, since 2026-08-26) and, since today, the system temp root and the Auralis data dir. The read path does none of this: `_register_scan_folders` does `json.loads(settings.scan_folders)` then `register_allowed_directory(Path(folder))` for every entry, and `register_allowed_directory` only resolves and appends. The auto-scanner `_parse_scan_folders` likewise scans whatever the column holds. A library whose settings were written before those checks existed (before 4765's fix, via `PUT /api/settings`, or when a user once chose `/` or a data dir) keeps that entry trusted on every launch, which widens the file-access allowlist that `validate_file_path` enforces to the whole of that tree.
- **Evidence**: `register_allowed_directory` (path_allowlist.py:70-76) contains no `_is_system_directory` call; the only users of that function are in `path_security.py:224` on the write path.
- **Exploit Scenario**: A pre-existing row such as `["/"]` or a legacy `~/.auralis` scan root survives upgrade; each start re-registers it, so any later path-containment decision that relies on the allowlist (stream path resolution, metadata/lyrics reads, uploads) treats everything under it as allowed. This is not remotely triggerable; it removes the defense-in-depth the newer write-time checks were meant to add.
- **Impact**: Allowlist silently weaker than designed for upgraded profiles. Low (needs historical bad data or local DB write).
- **Suggested Fix**: Run `validate_user_chosen_directory` (or at least the system/scratch checks) in `_register_scan_folders` and `_parse_scan_folders`, drop and log entries that fail, and optionally rewrite the column once.

### A08-4: Electron fuses omit asar-integrity validation; the privileged backend binary and bundled Python sources sit outside the asar and are launched on existence alone
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `desktop/package.json` (`build.electronFuses`, `build.extraResources`), `desktop/main.js:109-130,148-171`
- **Status**: NEW (residual of closed #6174, which added the four fuses present now)
- **Description**: `electronFuses` sets `runAsNode`, `enableNodeOptionsEnvironmentVariable`, `enableNodeCliInspectArguments` and `onlyLoadAppFromAsar`, but not `enableEmbeddedAsarIntegrityValidation` (supported on Windows and macOS), so a swapped `app.asar` is not detected. The part that matters more is that the Python backend (`resources/backend/auralis-backend`, plus `resources/auralis`, `resources/frontend`) is shipped as `extraResources`, outside the asar and unprotected by any fuse; `main.js` spawns it if `fs.existsSync(backendExe)` and has no hash or signature check. On non-Windows, if the binary is absent it falls back to `python3 resources/backend/main.py` and appends the ambient `PYTHONPATH`.
- **Evidence**: package.json fuse block lists four keys only; `main.js:112-127` selects binary by existence; line 152 `fullPythonPath = pythonPath + delimiter + process.env.PYTHONPATH`.
- **Exploit Scenario**: Per-user installs (default Windows NSIS under `%LOCALAPPDATA%`, AppImage in a user dir) are writable by any process running as the user, which can replace the backend binary or `app.asar` with a trojan that runs with the user's rights at next launch and survives updates until reinstall. A process already running as the user has simpler options, which is why this is hardening, not a vulnerability.
- **Impact**: Persistence and tamper-evidence gap for same-user malware. Low.
- **Suggested Fix**: Add `enableEmbeddedAsarIntegrityValidation: true` (and `cookieEncryption`); ship the backend inside the signed package where the OS signature covers it, or verify its SHA-256 (recorded at build time) before spawn; drop the `python3` script fallback and the inherited `PYTHONPATH` in packaged mode.

### A08-5: A stale manual release script publishes locally built, unsigned artifacts and updater manifests, bypassing the CI release controls
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `scripts/gh-release-command.sh` (lines ~1-70), compare `.github/workflows/build-release.yml` `create-release`
- **Status**: NEW (related to open #4905)
- **Description**: The tracked script hard-codes `cd /mnt/data/src/matchering`, `v1.0.0-beta.1`, and runs `gh release create` uploading `dist/*.exe`, `dist/*.AppImage`, `dist/*.deb`, `dist/latest.yml`, `dist/latest-linux.yml` and `dist/SHA256SUMS.txt` from the maintainer's workstation. That path has none of the CI properties (SHA-pinned actions, hash-locked build tooling, GPG-signed checksums, draft release): the checksums are produced on the same machine as the binaries, and `latest*.yml` are exactly the files electron-updater trusts. The CI workflow deliberately does not upload those manifests (artifact list names only the installers), so this script is the only path in the repo that would publish a working update feed.
- **Evidence**: `build-release.yml` upload steps list explicit installer files and `files: artifacts/*` only contains those plus `SHA256SUMS.txt(.asc)`; no `latest*.yml`. The script's `gh release create ... "dist/latest.yml" "dist/latest-linux.yml" "dist/SHA256SUMS.txt"`.
- **Exploit Scenario**: Not an exploit by itself. If the script (or its pattern) is reused for a real release, the signed-checksum provenance the README documents does not apply, and a compromised dev machine ships both artifacts and the update manifest. It also documents a release procedure that contradicts the CI pipeline.
- **Impact**: Release-process integrity; undermines the #4905 mitigation story.
- **Suggested Fix**: Delete the script (the version it targets is long gone) and state in the release docs that CI is the only publisher.

### A08-6: Two `.25d` readers, two validators: the central `FingerprintStorage.load` skips the value checks `SidecarManager` enforces
- **Severity**: LOW
- **OWASP Category**: A08
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:162-225`, `auralis/utils/atomic_write.py:63-72`, `auralis/analysis/fingerprint/fingerprint_service.py:244-259`, `auralis-web/backend/core/fingerprint_loading.py:123-160`
- **Status**: NEW (hardening; local-only reach)
- **Description**: `FingerprintStorage.load` checks version, `cache_key`, presence of the 25 dimension keys and `fingerprint_version`, and nothing about the values. `write_json_atomic` writes with `allow_nan=True` and documents that "non-finite fingerprint dimensions are already rejected on read by #4910", which is true only for `SidecarManager`. `FingerprintService._load_from_file_cache` adds only `band_pct_valid`; `fingerprint_loading.load_from_file` hands the dict to `derive_targets` with no finiteness or type check, and `FingerprintService` then `upsert`s the dict into the DB. A bit-flipped, hand-edited or foreign `~/.auralis/fingerprints/*.25d` (the stored `cache_key` is just the file name, so it is self-attesting) containing `NaN`, `Infinity` or a string is therefore accepted and flows into target derivation and the library DB. Reach is limited to a writer of `~/.auralis` (0700), so this is integrity robustness rather than an attack path.
- **Evidence**: `load()` ends with `return (fingerprint, targets or {})` after `set(DIMENSION_SCHEMA).issubset(fingerprint)`; no `math.isfinite`.
- **Exploit Scenario**: Disk corruption that leaves valid JSON, or a manually edited cache entry, yields NaN mastering parameters (the failure class #5505) until the cache is cleared.
- **Impact**: Wrong or silent masters from a damaged cache file. Low.
- **Suggested Fix**: Move `fingerprint_block_is_valid` (plus `band_pct_valid`) into a shared validator used by both readers, as the streamlining notes already suggest for the two `.25d` systems.

---

### A09-1: uvicorn's per-request access log (and per-WebSocket lines) are unthrottled INFO output that a hostile page can use to evict the persisted security log
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/main.py:120-130` (`uvicorn.run(..., log_level=_log_level, log_config=None)`, no `access_log=False`); `desktop/main.js:204-220` (all backend output persisted via electron-log)
- **Status**: NEW (adjacent to closed #6184 / #6188; same defect is also described as D6-03 in the untracked docs/audits/AUDIT_BACKEND_2026-11-17.md, so dedup in the merge)
- **Description**: #6188 throttled every app-level rejection log so a flood cannot evict earlier security entries from electron-log's 1 MiB + one-archive file. But the uvicorn access logger is left enabled. With `log_config=None` it has no handler of its own and propagates to the root handler at INFO (the packaged default), so every HTTP request writes one line, and each WebSocket upgrade (including the origin-rejected ones, which are accepted then closed with 1008) writes `"WebSocket /ws" [accepted]` and `connection open/closed` from `uvicorn.error`. None of this goes through `warn_throttled`. Requests rejected by OriginCheck/RateLimit/TrustedHost still produce their access line even though the rejection warning is throttled. The access line also persists every query string (library search terms) at INFO.
- **Evidence**: `uvicorn.Config.configure_logging` (0.52.1) only calls `setLevel` on `uvicorn.error/access/asgi` and sets `propagate=False` only `if self.access_log is False`. Reproduced with `uvicorn.run(app, log_config=None, log_level="info")` + root `basicConfig(INFO)`: `uvicorn.access - INFO - 127.0.0.1:52724 - "GET /api/a HTTP/1.1" 200` per request. `desktop/main.js:216` sends Python's stderr stream (basicConfig default) to `log.error('[Backend Error]', ...)`.
- **Exploit Scenario**: The user has any web page open. The page loops `new Image().src = "http://127.0.0.1:8765/api/library/tracks?x="+i` (or no-cors fetch; Firefox and Safari have no local-network prompt). Each request, though answered 403 by OriginCheck, writes ~120 bytes at INFO. About 16k requests (seconds) fill the 1 MiB file plus the single archive, evicting earlier "Rejected ..."/"Path validation rejected"/"Allowed directory registered" lines before anyone reads them.
- **Impact**: Loss of the persisted forensic trail the throttling work was meant to protect; also ordinary traffic (polling) consumes the same budget.
- **Suggested Fix**: Pass `access_log=False` to `uvicorn.run` (the app already logs its own rejections) and raise `uvicorn.error` per-connection lines to DEBUG or filter them; keep `log_config=None`.

### A09-2: SanitizingFormatter drops the sub-exceptions of an ExceptionGroup, so the real failure never reaches the log
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis/utils/logging.py:239-276` (`SanitizingFormatter._format_chain`)
- **Status**: NEW (same class as closed #6161, which rebuilt the traceback by hand)
- **Description**: `_format_chain` follows `__cause__`/`__context__` only. A `BaseExceptionGroup` (asyncio.TaskGroup, anyio task groups, `except*`) keeps its leaves in `.exceptions`; those are never rendered, and the stdlib formatter's group rendering was replaced. The log shows only `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)` with the group's own frames.
- **Evidence**: Running the real middleware stack (`create_app` + `setup_middleware` + `install_log_sanitizer`) with a route that does `async with asyncio.TaskGroup() as tg: tg.create_task(boom())`: the persisted ERROR ends with `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)` and no trace of `ValueError: inner detail`. No code in `auralis/` or `backend/` uses TaskGroup today, so this is latent until a route, library (anyio) or future refactor raises a group.
- **Exploit Scenario**: A failure that an attacker induces inside a task group (e.g. a malformed file during parallel analysis) is logged with no cause, so it cannot be diagnosed or recognised after the fact.
- **Impact**: Incomplete error evidence for exactly the 500s that the middleware logs once (#5986).
- **Suggested Fix**: In `_format_chain`, when `isinstance(exc, BaseExceptionGroup)`, render each of `exc.exceptions` (sanitized, indented) after the group's own traceback, mirroring `traceback.TracebackException`.

### A09-3: sanitize_log_value does not escape Unicode line separators or bidi controls
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-117)
- **Location**: `auralis/utils/logging.py:20-22` (`_LOG_UNSAFE_CHARS`), used by `sanitize_log_value`
- **Status**: NEW (hardening gap in the #4363/#4828/#5393 fix)
- **Description**: The unsafe set is C0 (minus tab), DEL and C1. U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR are treated as line breaks by many viewers (VS Code, anything using `str.splitlines()`/ECMAScript line terminators) and U+202A-202E / U+2066-2069 reorder displayed text (Trojan-Source style). Track tags and filenames are attacker-controlled and are logged through this function.
- **Evidence**: `sanitize_log_value("a b c‮d​x")` returns the string unchanged (verified).
- **Exploit Scenario**: A downloaded track has a title containing ` <timestamp> - auralis - INFO - Allowed directory registered: ...`. When the user opens `main.log` in an editor that honours LS, a forged-looking line appears; or an RLO character visually reverses the rest of the line.
- **Impact**: Cosmetic log forging / misleading display only (the file itself has no extra `\n`).
- **Suggested Fix**: Add U+2028, U+2029 and the bidi embedding/override/isolate controls (and optionally U+200B-200F) to `_LOG_UNSAFE_CHARS`; desktop `escapeControlChars` needs the same set.

### A09-4: Home-directory redaction compares against the unresolved `~`, but the app logs resolved paths
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-532)
- **Location**: `auralis/utils/logging.py:29-35,55-56` (`_HOME_PREFIX = os.path.expanduser("~")`); logged resolved paths at `auralis-web/backend/security/path_security.py:157,160,236,239`
- **Status**: NEW (gap in the closed #6189 fix, whose redaction is present and works for the common case)
- **Description**: `_HOME_PREFIX` is `$HOME` as spelled. Path validators log `resolved_path` (`Path.resolve()`), and `File is not readable`, `Path is not a directory`, `Directory is not readable` use the base `PathValidationError.log_text()` (full text, not file name). When HOME is reached through a symlink (Fedora Silverblue/Kinoite: `/home -> /var/home`; any bind/symlinked home), the resolved path starts with the real target, so the prefix never matches and the OS username plus library layout reach the persisted log, which is exactly what #6189 set out to prevent.
- **Evidence**: With `HOME=/tmp/.../sh/home/alice` where `sh/home -> var/home`: `sanitize_log_value(Path.home()/'Music'/'x.flac')` -> `~/Music/x.flac`, but `sanitize_log_value((Path.home()/'Music'/'x.flac').resolve())` -> `/tmp/.../sh/var/home/alice/Music/x.flac` (unredacted, verified).
- **Exploit Scenario**: A user on a symlinked-home distro pastes `main.log` into a public issue; the "not readable" WARNING discloses `/var/home/<username>/Music/...`.
- **Impact**: Information exposure of username and layout in logs (LOW).
- **Suggested Fix**: Also redact `os.path.realpath(os.path.expanduser("~"))` (compute both once, replace the longer first) and make the non-missing `PathValidationError` messages carry `Path.name` like `PathMissingError.log_text()`.

### A09-5: Logged SQLAlchemy exceptions embed the bound SQL parameters (library metadata and paths) at ERROR
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-532)
- **Location**: `auralis-web/backend/routers/errors.py:143` (`logger.error(f"Query error during {operation}: {error}", exc_info=True)`); `auralis/library/database_engine.py:57-64` (`create_engine` without `hide_parameters=True`); many `error(f"... {e}")` repository/scanner sites (e.g. `auralis/library/scanner/batch_processor.py:93,221`)
- **Status**: NEW
- **Description**: A DBAPI error stringifies as `(...Error) msg\n[SQL: ...]\n[parameters: (<values>)]`. The values are the row being written: track filepath, title, artist, scan folder. The message and the traceback's final line are persisted at ERROR on the default INFO level. #4366/#4376/#6189 deliberately keep absolute paths and layout out of persisted INFO/WARNING output, but this channel (a `database is locked`/IntegrityError during a scan or settings write) bypasses that policy; only the HOME prefix is redacted.
- **Evidence**: Reproduced with a SQLAlchemy engine: a UNIQUE violation prints `[parameters: ('/home/alice/Music/Secret/a.flac', 'Private Title')]`. `grep hide_parameters` finds nothing in `auralis/` or `backend/`.
- **Exploit Scenario**: Not attacker-driven: a transient lock during a scan writes the track row into `main.log`; the user shares the log.
- **Impact**: Library contents (titles, artists, non-home paths) disclosed through logs.
- **Suggested Fix**: `create_engine(..., hide_parameters=True)`; the default message then omits the parameter tuple while keeping the SQL and error class.

### A09-6: Raw backend stderr bypasses the sanitizer, and the Electron pipe persists it unescaped, labelled "error"
- **Severity**: LOW
- **OWASP Category**: A09 (CWE-117)
- **Location**: `desktop/main.js:204-220` (`log.info('[Backend]', output.trim())`, `log.error('[Backend Error]', output.trim())`); no `threading.excepthook`, `sys.excepthook` or `logging.captureWarnings(True)` anywhere in `auralis/` or `auralis-web/backend/`
- **Status**: NEW (neighbour of open #6187, whose scope is the main-process console.* sites; this is the backend pipe it does not cover)
- **Description**: The whole sanitizing design is the logging record factory plus the root formatter. Anything the backend writes to stderr without going through `logging` reaches the persisted log verbatim: a traceback from an uncaught exception in a bare `threading.Thread` (several exist: fingerprint workers, gapless prebuffer, resource monitor), `warnings.warn` output, faulthandler/C-extension/Rust output. `main.js` then logs those chunks with no escaping (unlike every other `log.*` call there, which uses `escapeControlChars`). Separately, Python's logging writes to stderr, so every backend line, INFO included, is persisted as `[error] [Backend Error]`, making severity useless for triage.
- **Evidence**: With the sanitizer installed, `threading.Thread(target=lambda: raise ValueError("bad tag\n2026-11-17 20:00:00 - auralis - INFO - Allowed directory registered: /etc"))` printed the forged line on its own line; `warnings.warn("tag \x1b[2J\nforged")` printed the ESC sequence and newline raw (verified, both bypass the formatter).
- **Exploit Scenario**: A crafted tag/filename reaches an exception message in an uncaught thread exception; the traceback's last line is written raw into main.log and forges an entry.
- **Impact**: Log forging and a weaker audit trail; requires an uncaught exception or warning that carries attacker text, which current code mostly catches, so it is a defence-in-depth gap.
- **Suggested Fix**: Install `threading.excepthook`/`sys.excepthook` that log via `logger.critical(..., exc_info=...)`, call `logging.captureWarnings(True)`, and in `main.js` run backend output through `escapeControlChars` per line (keep `\n` as the line splitter), classifying stderr lines by their leading Python level.

### A09-7: The rejection throttle keeps only the first event per reason and never flushes the suppressed count
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis-web/backend/config/log_throttle.py:29-44` (also `RateLimitMiddleware._log_rejection`, `config/middleware/rate_limit.py:99-113`)
- **Status**: NEW (design weakness in the #6188/#5375 throttle)
- **Description**: A key is a rejection reason, so within a 60 s window only the first origin/path/host is recorded; every later distinct one is counted, not identified. The count is only emitted on the next call after the window expires: if the burst stops, the "N more like it" line is never written, so the log shows one rejection for what may have been thousands, and a second, different hostile origin in the same minute leaves no trace.
- **Evidence**: `warn_throttled` returns False and bumps `_state[key]` inside the window; the `suppressed` text is built only on the next logged call.
- **Exploit Scenario**: A benign-looking first probe (or the app's own dev tab) consumes the window; the real attacker origin arrives second and is invisible.
- **Impact**: Incomplete evidence; trade-off the throttle intentionally made, but the flush gap is avoidable.
- **Suggested Fix**: Emit the suppressed count when the window rolls over (a timer, or on shutdown), and log the first rejection per distinct value from a small bounded set (e.g. LRU of 32 origins) as well as per reason.

### A09-8: Failures of the file-permission hardening steps are swallowed with no log
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `auralis/library/database_engine.py:36-39,70-73,131-134`; `auralis/library/migration_backup.py:73-76`
- **Status**: NEW
- **Description**: `os.chmod(...0o700/0o600)` on `~/.auralis`, the library DB, its `-wal/-shm` sidecars and the migration backup is a security control (#2577, #4347, #4824, #5333) but every failure is `except OSError: pass`. On a filesystem that rejects chmod (FAT/exFAT, some network mounts) or a directory owned by another user, the library silently stays group/world readable with no signal.
- **Evidence**: `try: os.chmod(db_path, 0o600) \n except OSError: pass` at the sites above.
- **Exploit Scenario**: A user keeps the library DB on an exFAT drive; the hardening no-ops and nothing says so.
- **Impact**: Silent weakening of a documented protection (LOW).
- **Suggested Fix**: Log one WARNING (file name only) when a hardening chmod fails.

### A09-9: Remaining console-only security/failure events in the Electron shell
- **Severity**: LOW
- **OWASP Category**: A09
- **Location**: `desktop/main.js:232` (`console.log("Backend process exited with code ...")`), `desktop/preload.js:27` (`console.warn("...refusing to expose electronAPI on non-local origin ...")`)
- **Status**: Existing: #6187 (still open; the navigation/openExternal/permission/IPC sites were already moved to `log.warn` with `escapeControlChars`, these two items remain)
- **Description**: A backend crash after startup and the preload's refusal on an unexpected origin are not in the persisted log. The preload line also interpolates `window.location.origin` unescaped, and `electron-log` is unavailable in the preload.
- **Evidence**: See lines above; `grep console. desktop/main.js` shows only startup/progress logs otherwise.
- **Exploit Scenario / Impact**: A renderer navigated to a foreign origin, or a backend crash, leaves nothing in main.log.
- **Suggested Fix**: As in #6187: `log.error` for the exit event (non-zero code, not quitting); send the preload refusal to main over IPC.

### A09-10: sanitize_log_value truncates a format string before its args are applied, which loses the record
- **Severity**: LOW (latent)
- **OWASP Category**: A09
- **Location**: `auralis/utils/logging.py:199-205` (`_sanitizing_log_record_factory` -> `sanitize_log_value(record.msg)` with the 500-char cap)
- **Status**: NEW
- **Description**: `record.msg` is the %-format template when `args` are present. Truncating it at 500 characters can cut off the `%s` placeholders while the args remain, so `getMessage()` raises `TypeError: not all arguments converted`, the handler prints `--- Logging error ---` to stderr and the intended record is dropped (including any security warning built that way).
- **Evidence**: `logging.getLogger("y").warning("a"*600 + " %s", "x")` produces the logging error and no record (verified). An AST scan of `auralis/` and `backend/` found no current call whose constant format string with args exceeds ~380 characters, so this is not triggered today.
- **Exploit Scenario**: A future long multi-placeholder message silently disappears from the log.
- **Impact**: Latent audit-trail loss.
- **Suggested Fix**: Only sanitize/truncate `record.msg` when `record.args` is empty; when args exist, sanitize the args (and escape control characters in the template without truncating it).

### A10-1: CLI artwork metadata calls follow redirects to any host unvalidated; the redirect-checking opener is dead code
- **Severity**: LOW
- **OWASP Category**: A10
- **Location**: `auralis/services/artwork_sources/musicbrainz.py:93,114`, `discogs.py:59`, `lastfm.py:57` (plain `urllib.request.urlopen`); `auralis/services/artwork_service.py:30-55` (`_TrustedArtworkRedirectHandler`, `_artwork_opener`)
- **Status**: NEW (sibling gap of closed #5330/#5529, which hardened only the backend downloader; #6182 closed without making the CLI metadata calls refuse cross-host redirects, which its own acceptance criteria asked for)
- **Description**: The four CLI metadata requests use the default urllib opener, which follows redirects to any `http`/`https`/`ftp` target with no host or scheme validation, including loopback/LAN. The hardened `_artwork_opener` (a per-hop validator) has no production caller. `grep -rn _artwork_opener` finds only `tests/regression/test_artwork_service.py`, because the CLI never downloads images. Its own comment says "Metadata API calls still use plain urlopen". The backend equivalent (`allow_redirects=False`) is already fixed.
- **Evidence**: `with urllib.request.urlopen(req, timeout=service.timeout) as response:` in all four provider modules. A loopback test (redirector on one port, target on another, default `urlopen`) showed the 302 to `http://127.0.0.1:<port>/internal` was followed and the target received the GET with the User-Agent. The Authorization header did not arrive, because it was added with `add_unredirected_header`.
- **Exploit Scenario**: Needs a compromised or MITM'd provider endpoint (musicbrainz.org, api.discogs.com or ws.audioscrobbler.com; all hardcoded https). It answers the metadata call with `302 Location: http://192.168.x.x/...`. The user runs `python -m auralis.cli.fetch_artwork` and the CLI issues a blind GET to the internal address. The JSON response is only parsed and the result is discarded unless it matches, so there is no read-back.
- **Impact**: Blind GET to an attacker-chosen internal host. Not reachable from any HTTP/WS route and requires provider compromise, so low.
- **Suggested Fix**: Build the metadata opener with a redirect handler that refuses redirects, or allowlists the same provider hosts, and use it for all four sites (or pass `urllib.request.HTTPRedirectHandler` subclass returning None). Delete `_artwork_opener` or wire it in so it stops being dead code with a misleading comment.

### A10-2: CLI fetch_artwork bypasses per-host outbound spacing: tight loop of un-throttled MusicBrainz/Discogs/Last.fm requests
- **Severity**: LOW
- **OWASP Category**: A10 (outbound-request abuse; same class as closed #5069)
- **Location**: `auralis/cli/fetch_artwork.py:78-110` (loop over all artists), `auralis/services/artwork_sources/musicbrainz.py:85-117` (2 requests per artist)
- **Status**: NEW (sibling of closed #5069; the fix, `HostThrottle`, was wired only into the backend `ArtworkDownloader`)
- **Description**: The checklist asks whether any provider bypasses `host_throttle.py`. The CLI stack does. `fetch_artwork_for_all_artists` iterates the whole library with no `sleep`/throttle/429 handling. Each artist costs two back-to-back MusicBrainz requests (search plus url-rels), then Discogs and Last.fm if configured. MusicBrainz asks clients for at most 1 request per second and blocks violators by User-Agent/IP. The CLI sends `Auralis/1.2.0 (https://github.com/matiaszanolli/Auralis)`, the project-identifying UA the backend also uses.
- **Evidence**: grep for `sleep|throttle|rate` in `fetch_artwork.py`, `artwork_service.py` and `artwork_sources/*.py` returns no throttling. All errors are swallowed at `logger.debug` and counted as "not found".
- **Exploit Scenario**: A user with thousands of artists runs the CLI. Requests go out at network speed, MusicBrainz starts returning 503, and the remaining artists silently come back "not found" at DEBUG level. It risks a block of the shared project UA, which also affects other Auralis users. No attacker is needed, though a poisoned library with many fake artists makes it deliberate.
- **Impact**: Availability and abuse of a third-party service, silent partial results. No data compromise.
- **Suggested Fix**: Reuse `artwork_providers.host_throttle.HostThrottle` (or the same interval table: musicbrainz 1.1 s, Discogs about 1 s) in the CLI sources, treat 429/503 as a back-off signal and log at WARNING.

## Relationships

- **A04-1 + A03-1 + A06-1** (all triggered by a hostile audio file in a scanned folder): resource exhaustion at decode (A04-1), at tag ingest (A03-1), and a memory-safety risk in the in-process parser (A06-1). Fixing only one leaves the same attacker input effective through the others. A08-1 (forged sidecar next to the audio) uses the same entry point.
- **A02-1 + A08-5 + A08-4 + A06-3** (release and update integrity): the updater's signature check is off, the stale manual release script can publish unsigned artifacts and manifests, asar integrity is not enforced, and the shipped Electron is behind. Any single weak link undermines the sha512-only trust anchor.
- **A05-1 + A09-1 + A09-7 + A09-6** (log eviction): a hostile page can flood unthrottled handshake and access-log lines to rotate out earlier security entries, and the throttle that exists never reports its suppressed count, so the flood is also invisible. A05-1 and A09-1 should be fixed together.
- **A01-1 + A08-3** (allowlist consistency): the uploads directory is outside the allowlist while persisted scan folders are inside it without validation; both are allowlist-registration paths and should be reviewed together, taking care not to "fix" A01-1 by widening the data dir (#2562).
- **A07-1 + A05-4 (#6169) + A05-2**: on a shared host, the unauthenticated loopback API, an IPv6 listener squat, and the over-broad port-cleanup pattern are all consequences of treating port 8765 as private to the user.
- **A06-2 -> A06-1**: lock-file drift (uv.lock vs requirements-lock.txt) is the same supply-chain hygiene gap that hides the libsndfile exposure from `pip-audit`.

## Prioritized Fix Order

1. **A04-1** (MEDIUM, reproduced): add `-t` and `-fs` limits to the FFmpeg decode and reject over-long output, so the declared-duration lie cannot fill the temp directory. Highest practical exploitability.
2. **A03-1** (MEDIUM): cap artist-value count at ingest (mirror `MAX_GENRES_PER_TRACK`) and make `_distinct` O(n) with a set. Cheap, and it also closes A03-2 if lyrics are capped in the same pass.
3. **A02-1 / #4905** (HIGH, tracked): obtain signing identities and enable update signature verification; retire `scripts/gh-release-command.sh` (A08-5) in the same effort.
4. **A06-1** (MEDIUM): track a soundfile/libsndfile build with the CVE fixes; consider passing an explicit `format=` allowlist to libsndfile in the scanner and loader to shrink the reachable parsers.
5. **Logging cluster** (A05-1, A09-1, A09-7, A09-6): route handshake rejections through `warn_throttled`, set `access_log=False`, flush suppressed counts, and install `threading.excepthook` / `captureWarnings`.
6. **A06-2** (regression of #6178): refresh `uv.lock` and extend the audit gate to cover it.
7. **A05-2, A07-2**: tighten the port-cleanup identity test; reset `isQuitting` on reactivation.
8. **A08-1/2/3/4/6, A10-1/2, A04-2, A03-3, A01-1**: hardening backlog; each is local-only or integrity-only.
9. **A09-2/3/4/5/8/10, A06-3/4, A07-4, A02-2**: low-risk polish and documentation (SECURITY_MODEL.md drift).

## Verified Intact (spot-checks of prior fixes)

#4826, #5326, #5733, #6317, #4834, #6159, #6154, #4363/#4828/#5393, #6165 (genre part), #6182, #6184, #6185, #6188, #6189, #6190, #6191, #5330, #5337, #5529, #2416, #2576, #4686, #6157 (core), #6160, #6174 (fuses), #5307, #6176, #6177. No regression found except the `uv.lock` criterion of #6178 (A06-2).

## Labels for publishing

Severity label + `security` + `bug`.
