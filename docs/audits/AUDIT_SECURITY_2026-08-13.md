# Security Audit — Auralis — 2026-08-13

OWASP Top 10 (2021) aligned. Fresh read of the current working tree at `master` (`188db72a`).
The most recent *complete* prior security audit was 2026-07-29 (the 2026-07-25 run was
cancelled mid-way). Prior reports were used **only** for deduplication, never as a source of
findings.

## Threat model (severity is calibrated to this)

Auralis is a **single-user Electron desktop app**: React frontend + FastAPI backend + Rust
DSP, bundled together, bound to `127.0.0.1:8765`. There is no multi-user, remote, LAN, or
Docker deployment. Therefore:

- "No authentication on the API" is the **documented baseline**, not a finding. It is reported
  only where that baseline is *violated*.
- A finding whose only exploit path is "a remote attacker reaches :8765" is not CRITICAL here.
- A local process already runs with the user's privileges; "a local process can call the API"
  is at most LOW unless it enables something that process could not already do.
- **In scope and genuinely important**: local-file-path escapes, **malicious media files**
  (crafted ID3/metadata, decompression bombs, pathological containers), **dependency
  supply-chain**, Electron hardening, update integrity, world-readable secrets.

## Coverage — inline vs delegated

| Category | Source | Notes |
|---|---|---|
| A01 Broken Access Control | Delegated + inline | Agent `a01_a03` (returned late, after the first draft); orchestrator covered it inline meanwhile and verified the agent's claims |
| A02 Cryptographic Failures | Delegated + inline | Agent `a02_a05_a07_a10`; orchestrator did the secrets sweep |
| A03 Injection | Delegated + inline | Agent `a01_a03`; orchestrator covered SQL, subprocess, and frontend HTML sinks inline. Rust FFI **partially** reached — see Coverage Gaps |
| A04 Insecure Design | Delegated | Agent `a04`; orchestrator independently confirmed the PIL path and corrected its own draft against the agent's finer result |
| A05 Security Misconfiguration | Delegated + inline | Agent `a02_a05_a07_a10`; orchestrator verified middleware order, Electron, CI |
| A06 Vulnerable Components | Delegated + inline verification | Agent `a06`; **orchestrator independently re-verified all three structural claims** |
| A07 Auth Failures | Delegated + inline | Agent `a02_a05_a07_a10`; orchestrator verified bind, origin checks, WS security |
| A08 Data Integrity | Delegated | Agent `a08_a09` |
| A09 Logging & Monitoring | Delegated | Agent `a08_a09` |
| A10 SSRF | Delegated + inline | Agent `a02_a05_a07_a10`; orchestrator traced all outbound HTTP surfaces |

The **A01+A03 agent returned late**, after the first draft of this report was written. Its
findings are merged here (SEC-11, SEC-12, and a material strengthening of SEC-04), and the
orchestrator independently verified each of its claims against the live source before
adopting them. Its router-by-router path-security table closed the largest coverage gap the
first draft had to declare.

---

## Executive Summary

**Total findings: 12** — CRITICAL 0 · **HIGH 1** · **MEDIUM 4** · **LOW 7**.

This is a mature, well-hardened codebase, and its posture has improved materially since
2026-07-29: **nine** prior findings are fixed and closed (all Electron hardening gaps, Rust
`Cargo.lock` tracking, the `cargo audit` gate, the missing Python lockfile, and the entire
`desktop/` advisory set — 26 advisories → **0**). Twenty-two separate prior fixes were
re-verified as still present. No new access-control, injection, SSRF, or authentication
defect was found; the entire network perimeter is correct.

### Key themes

1. **The one HIGH is a supply-chain structural gap, not a code defect.** `requirements.txt`
   pins `fastapi==0.122.0` but never pins Starlette, which arrives transitively. Release
   builds run `pip install -r requirements.txt` (**not** the hash-locked
   `requirements-lock.txt`) on all three platforms, so every release does a fresh,
   unconstrained transitive resolution. The CI gate that exists specifically to catch manifest
   drift only diffs *direct* dependencies, so transitive exposure is structurally invisible to
   it, and no advisory scanner runs against Python deps at all.

2. **The remaining code-level attack surface is the malicious media file.** The *audio*
   decode path is exemplary — ffprobe runs first and both a duration ceiling and a
   decoded-size ceiling are enforced *before* FFmpeg allocates. But the two **non-audio**
   parsers fed by the same untrusted file are weaker: the **image** decoder fails *open*
   (SEC-03) and the **tag** parser's length clamp covers only the insert path, not the update
   paths (SEC-04).

3. **Defence-in-depth is one layer thinner than the comments claim.** Two independent
   findings converge here: the middleware registration comment asserts `OriginCheckMiddleware`
   sees an "already known-good" Host header, but it demonstrably runs *before*
   `TrustedHostMiddleware` (verified below); and the CSP omits the three directives that do
   *not* inherit from `default-src`. Neither is exploitable today. Both remove a precondition
   permanently for a one-line cost.

4. **Supply chain is otherwise genuinely clean.** `requirements.txt` is 19/19 `==`-pinned,
   `uv.lock` and `Cargo.lock` are tracked, `desktop/` reports zero advisories, and two new CI
   guards exist. The nine remaining frontend advisories are all dev/build-only.

### Most exploitable issue

**SEC-03** — a single crafted audio file with an oversized embedded cover makes the backend
allocate hundreds of megabytes during a library scan and persists an unbounded image to
`~/.auralis/artwork` that is then served at full resolution into the Electron renderer. No
network access and no interaction beyond "add this album to my library."

---

## Data Flow Security Matrix

| # | Flow | Status | Notes |
|---|---|---|---|
| 1 | **File paths** — frontend → router → `path_security` → repositories → loader → FFmpeg | **Safe** | Client-supplied paths validated; DB-sourced paths validated on the streaming path; artwork reads confined to `~/.auralis/artwork`; both caches key on a full hash. |
| 2 | **Audio metadata** — disk → mutagen → DB → API JSON → React | **Gap** | Length clamp covers `add()` only, and never covers lyrics/comments/genre (**SEC-04**). Rendering itself is safe — React escapes and there is no HTML sink. |
| 3 | **Embedded cover art** — disk → mutagen → PIL → `~/.auralis/artwork` → PIL → renderer | **Gap** | Bomb guard fails open at both PIL call sites (**SEC-03**). |
| 4 | **WebSocket messages** — frontend → origin check → `ws_handlers` → controller → engine | **Safe** | Validated per-message (64 KB cap → JSON guard → Pydantic schema), not merely at handshake. Rate limited per-connection *and* per-IP. |
| 5 | **Library scan paths** — user folder → `library_scan` → scanner → DB | **Safe by design** | Depth-capped at 50. The #4799 trust model deliberately trusts a user-chosen folder; symlink containment is the already-open #4823. |
| 6 | **Outbound artwork fetch** (SSRF) | **Safe** | Host allowlist applied pre-request *and* re-applied to the final URL after redirects, with a 5 MB cap. Cleartext scheme still accepted (**SEC-10**). |
| 7 | **Audio decode** — container header → bounds check → decode | **Safe** | Pre-decode probe + duration *and* decoded-size ceilings + VBR fallback. |
| 8 | **Python dependency resolution** — manifest → release build → installer | **Gap** | Release builds resolve transitives fresh, unpinned, unscanned (**SEC-01**, **SEC-02**). |

---

## Findings

### SEC-01: Shipped backend pins FastAPI but not Starlette; release builds resolve the transitive range fresh, and no CI gate can see it

- **Severity**: HIGH
- **OWASP Category**: A06 (Vulnerable and Outdated Components)
- **Location**: `requirements.txt:18` · `auralis-web/backend/requirements.txt:25` ·
  `requirements-lock.txt:1806` · `.github/workflows/requirements-pin-guard.yml` ·
  `.github/workflows/build-release.yml:148,291,423`
- **Status**: NEW (root cause adjacent to open **#4871**, "Pinned manifests don't describe the
  environment anything is verified against; Starlette is pinned nowhere" — that issue frames it
  as hygiene/traceability; this adds the concrete release-path exposure)
- **Description**: `requirements.txt` pins `fastapi==0.122.0` exactly, but **Starlette is
  pinned nowhere** — it is pulled in transitively through FastAPI's own metadata range. Three
  structural facts compound this, **all three independently verified by the orchestrator**:

  1. **Release builds do not use the hash-locked file.** `build-release.yml` runs
     `pip install -r requirements.txt` on all three platforms (lines 148, 291, 423), never
     `requirements-lock.txt`. Every release therefore performs a fresh, unconstrained
     transitive resolution at build time — whatever Starlette satisfies FastAPI's range on
     that day ships.
  2. **The pin-guard gate is blind to transitives.** `requirements-pin-guard.yml` extracts
     and diffs only lines matching `^[a-zA-Z]` from the manifests (lines 56, 94-95) — i.e.
     *direct* dependency names. It has no visibility into resolved transitive versions, and
     no advisory scanner (`pip-audit`, `safety`) runs against Python dependencies anywhere in
     CI. The gap is invisible by construction.
  3. **The hash-locked file resolves to a much older Starlette than the tree actually runs.**
     `requirements-lock.txt:1806` hash-locks `starlette==0.50.0`, while the repo's actual
     `.venv` runs `starlette==1.3.1` (see SEC-02). Nothing reconciles them.

  The delegated A06 agent additionally reports — from out-of-repo package metadata and
  advisory sources — that `fastapi==0.122.0` declares `Requires-Dist: starlette<0.51.0,>=0.40.0`,
  and that a disclosed Starlette Host-header/`request.url` reconstruction vulnerability
  (reported as **CVE-2026-48710 / "BadHost"**) is fixed only in Starlette ≥ 1.0.1 — meaning
  no Starlette satisfying FastAPI 0.122.0's cap is patched.

  > **Verification caveat, stated deliberately:** the orchestrator verified every *in-repo*
  > claim above but **could not independently confirm the CVE identifier, its affected range,
  > or the wheel metadata**, which depend on out-of-repo sources. Confirm the advisory before
  > citing the CVE number in a changelog or issue. **The structural finding does not depend on
  > it**: an unpinned, unscanned, freshly-resolved-at-release transitive dependency that parses
  > every inbound HTTP request is a HIGH-severity supply-chain gap on its own terms.

- **Evidence**:
  ```
  requirements.txt:18                 fastapi==0.122.0        # starlette: not pinned anywhere
  requirements-lock.txt:1806          starlette==0.50.0       # via fastapi
  .venv                               starlette 1.3.1         # what actually runs
  build-release.yml:148,291,423       pip install -r requirements.txt   # not the locked file
  requirements-pin-guard.yml:56,94    grep -E '^[a-zA-Z]'     # direct deps only
  ```
- **Exploit Scenario**: The relevant class of Starlette bug lets a crafted `Host` header
  poison `request.url.path`. That matters here because `OriginCheckMiddleware`
  (`config/middleware.py:294`) makes a **path-based security decision** —
  `request.url.path.startswith("/api")` — to decide whether to enforce the CSRF/Origin check.
  A poisoned path would skip that check on a request the ASGI router still dispatches to a
  real `/api` handler.

  **This chain is very likely not exploitable today**, and the reason is worth recording
  precisely. `TrustedHostMiddleware` validates the **raw** header via
  `headers.get("host","").split(":")[0]` against exact matches `("localhost","127.0.0.1")`, so
  any Host value carrying an injected `/`, `?`, or `#` fails that comparison. But this backstop
  is **incidental**, not designed: it exists for DNS-rebinding (#4353), and — verified against
  the live source — the inline comment at `config/middleware.py:433-436` claims
  `OriginCheckMiddleware` "wraps TrustedHost (**so the Host header is already known-good**)".
  Because `add_middleware` composes LIFO, wrapping means running **first**: the true inbound
  order is `CORS → SecurityHeaders → NoCache → OriginCheck → TrustedHost → RateLimit → app`
  (correctly stated in the docstring at lines 397-404). OriginCheck therefore reads
  `request.url.path` **before** any Host validation has occurred. The parenthetical rationale
  is factually inverted, and it is the sentence a future maintainer would rely on when
  reordering or loosening `trusted_hosts()`.
- **Impact**: Availability and integrity of the shipped dependency set. Every release build
  resolves transitives afresh with no advisory gate; a future loosening of `trusted_hosts()`
  or any other path-based middleware decision would convert the latent bypass into a real one.
- **Suggested Fix**: Three separable changes, in order of value:
  1. Make release builds install from `requirements-lock.txt --require-hashes`, not
     `requirements.txt`.
  2. Add a `pip-audit --require-hashes -r requirements-lock.txt` step to CI so transitive
     advisories fail the build.
  3. Bump the `fastapi` pin toward `0.141.1` — the version `uv.lock` and the working `.venv`
     have already been running successfully — which moves Starlette to a patched line and
     simultaneously closes SEC-02.

  Separately, fix the inverted comment at `middleware.py:433-436` and add a regression test
  asserting that no path-based security decision runs before `TrustedHostMiddleware`.

---

### SEC-02: `uv.lock` and `requirements-lock.txt` have diverged by 19 FastAPI minor versions — developers test against different majors than ship

- **Severity**: MEDIUM
- **OWASP Category**: A06 (Vulnerable and Outdated Components)
- **Location**: `uv.lock` · `requirements.txt:18` · `requirements-lock.txt:435` ·
  `auralis-web/backend/requirements.txt:25` · `pyproject.toml`
- **Status**: NEW (adjacent to open **#4871**; this documents the concrete realized drift)
- **Description**: The repo runs two independent Python resolution pipelines that are supposed
  to describe the same project and currently do not agree. `requirements.txt` — which
  describes itself as the reproducible pin set, is hash-locked by CI, and is rsync'd into the
  shipped installer — says `fastapi==0.122.0`. `pyproject.toml` floors it only
  (`fastapi>=0.115`, no ceiling), and `uv.lock`, generated from `pyproject.toml` and the basis
  for the repo's single `.venv`, resolved to `fastapi==0.141.1` / `starlette==1.3.1`.
  **Verified directly against the live environment.**
- **Evidence**:
  ```
  $ grep fastapi requirements.txt                     fastapi==0.122.0
  $ grep -A1 'name = "fastapi"' uv.lock               version = "0.141.1"
  $ grep -A1 'name = "starlette"' uv.lock             version = "1.3.1"
  $ .venv/bin/python -c "import fastapi, starlette; print(fastapi.__version__, starlette.__version__)"
  0.141.1 1.3.1
  ```
- **Exploit Scenario**: Not directly exploitable. It is an integrity/reproducibility failure
  with a security consequence: a contributor verifying a dependency-related fix locally is
  silently testing against a different dependency major than what ships, which is precisely
  why SEC-01's exposure would not surface in a local spot-check.
- **Impact**: Undermines confidence in every pin/lock-based assertion about this project —
  "the lockfile says X" no longer implies "the shipped app runs X."
- **Related**: SEC-01 (same root cause; one bump fixes both), #4871.
- **Suggested Fix**: Pick one manifest as authoritative and generate the other mechanically
  (`uv export` from `pyproject.toml` into `requirements.txt`) rather than hand-maintaining
  both, or add a CI check that fails when a shared package's resolved version differs between
  `uv.lock` and `requirements-lock.txt`.

---

### SEC-03: Artwork pipeline fails *open* to unbounded bytes when the decompression-bomb guard fires

- **Severity**: MEDIUM
- **OWASP Category**: A04 (Insecure Design)
- **Location**: `auralis/library/artwork.py:244-320` (`_bound_dimensions`, `_save_artwork`);
  `auralis-web/backend/routers/artwork.py:131-265, 383-420` (`_render_thumbnail`,
  `_get_or_create_thumbnail`, `get_album_artwork`)
- **Status**: NEW
- **Description**: Both code paths that decode image data call `PIL.Image.open` on bytes taken
  directly from an untrusted file (an ID3 `APIC` frame, a `folder.jpg` beside the audio file,
  or a downloaded cover). `Image.MAX_IMAGE_PIXELS` is **set nowhere in the repository**, and no
  `warnings` filter promotes `DecompressionBombWarning` to an error — both confirmed by
  repo-wide grep including `pytest.ini`, `pyproject.toml`, and `setup.cfg`. Pillow's defaults
  therefore apply unmodified, producing two bad outcomes:

  - **Below ~178 Mpx** (2× Pillow's default): only a `DecompressionBombWarning` is emitted and
    the image **decodes normally**. A ~100 Mpx PNG compresses to a few hundred kilobytes but
    costs roughly 300-400 MB of RSS when `thumbnail()` forces the decode — on the **library
    scan** path.
  - **Above the hard threshold**: `DecompressionBombError` is raised from inside `Image.open()`
    itself, off the header-declared dimensions. `_bound_dimensions` catches it with a bare
    `except Exception` and **returns the original bytes unchanged** (`artwork.py:277-279`), so
    the bomb is persisted at full size. Later `_render_thumbnail` fails identically,
    `_get_or_create_thumbnail` returns `None`, and `get_album_artwork` **falls back to serving
    the original full-resolution file** (`routers/artwork.py:386-393`), moving the decode cost
    into the Electron renderer.

  The `_MAX_ARTWORK_DIMENSION = 2048` cap is applied *after* the decode it exists to bound, so
  it does not help — `image.thumbnail(...)` is what triggers the allocation. The guard that
  fires is the only safeguard, and catching it defeats it.
- **Evidence**:
  ```python
  # auralis/library/artwork.py:265-279
  with Image.open(io.BytesIO(artwork_data)) as image:
      if max(image.size) <= _MAX_ARTWORK_DIMENSION:
          return artwork_data
      image.thumbnail((_MAX_ARTWORK_DIMENSION, _MAX_ARTWORK_DIMENSION))  # decode happens here
      ...
  except Exception as e:
      debug(f"Artwork dimension-bounding skipped: {e}")
      return artwork_data          # bomb stored verbatim
  ```
  ```python
  # auralis-web/backend/routers/artwork.py:386-393
  serve_path = requested_path
  if size is not None:
      thumbnail = await asyncio.to_thread(_get_or_create_thumbnail, ...)
      if thumbnail is not None:                    # None on bomb
          serve_path, serve_media_type = thumbnail # else: serve the original
  ```
- **Exploit Scenario**:
  1. Attacker publishes an album whose FLAC files carry a 30000×30000 PNG in the picture block
     — a highly compressible solid-colour image, a few hundred KB on disk.
  2. User adds the folder. During scan, `_bound_dimensions` runs per file: at ~100 Mpx the
     backend RSS spikes hundreds of MB per concurrent worker; above the threshold the decode
     raises, is swallowed, and the full bomb lands in `~/.auralis/artwork`.
  3. User opens the album view. `GET /api/albums/{id}/artwork?size=…` tries to thumbnail,
     fails, and streams the full-resolution bomb to the renderer, which decodes it in-process.
- **Impact**: Availability. Backend memory exhaustion during scan (possible OOM-kill of the
  backend child, surfacing as a dead app) plus renderer crash on view. **Persistent**: the
  bomb stays on disk and re-triggers on every subsequent view until manually deleted. No
  confidentiality or integrity impact.
- **Siblings**: These two are the complete set — the only `PIL.Image.open` calls on untrusted
  bytes in the tree.
- **Suggested Fix**: Set a conservative `Image.MAX_IMAGE_PIXELS` once at import in a shared
  module both paths touch, and handle `DecompressionBombError` **distinctly from generic
  failure**: on a bomb, drop the artwork entirely rather than falling back to the original
  bytes. Give `get_album_artwork` a size ceiling on its fallback branch so it never serves an
  image it could not thumbnail.

---

### SEC-04: The tag-length clamp covers only `TrackRepository.add()` — every update path and the lyrics/comments/genre fields are unbounded, with no request-body size limit behind them

- **Severity**: MEDIUM
- **OWASP Category**: A04 (Insecure Design) / A03 (Injection — resource side)
- **Location**: `auralis/library/repositories/track_repository.py:111-124`
  (`_validate_and_normalize_track_info`), `:200` (its only call site), `:844` (`update`),
  `:905` (`update_metadata`), `:943` (`update_metadata_batch`), `:153-166`
  (`_get_or_create_genres`); `auralis-web/backend/routers/tracks.py:184-224` (lyrics);
  `auralis-web/backend/routers/metadata.py:257-291` (live metadata read)
- **Status**: NEW
- **Description**: A truncation helper **does** exist and does the right thing —
  `_validate_and_normalize_track_info` clamps `title` and `album` to 500 chars and each entry
  of `artists` to 200. But it has exactly **one** call site, at line 200 inside `add()`. Three
  separate gaps follow, all verified against the live source:

  1. **`update()` (line 844), `update_metadata()` (line 905), and `update_metadata_batch()`
     (line 943) never call it.** Any path that edits an existing track writes unbounded
     strings.
  2. **`lyrics`, `comments`, and `genre` are not in the clamp list at all**, so they are
     unbounded even on the `add()` path. `lyrics` in particular is a `Text` column populated
     from a `USLT`/`©lyr` frame — a field with no natural size limit.
  3. `_get_or_create_genres` (line 153) applies no truncation to genre names before creating
     `Genre` rows.

  The ORM columns are declared `mapped_column(String)` / `mapped_column(Text)` with **no
  length argument**, and SQLite enforces no length on either, so nothing downstream catches it.

  *(This finding corrects an earlier orchestrator draft that claimed there was no bound
  anywhere — the `add()` path is in fact protected. The delegated A04 agent's narrower,
  accurate scoping is what is recorded here.)*
- **Evidence**:
  ```python
  # track_repository.py:119-124 — the clamp, and everything it omits
  for field, max_len in (('title', 500), ('album', 500)):
      if field in track_info and isinstance(track_info[field], str) and len(track_info[field]) > max_len:
          track_info[field] = track_info[field][:max_len]
  if 'artists' in track_info:
      track_info['artists'] = [a[:200] for a in track_info['artists'] if isinstance(a, str)]
  # no 'lyrics', no 'comments', no 'genre'
  ```
  ```
  $ grep -n "_validate_and_normalize_track_info" auralis/library/repositories/track_repository.py
  111:    def _validate_and_normalize_track_info(...)     # definition
  200:        self._validate_and_normalize_track_info(track_info)   # ONLY call site — inside add()
  ```
  A fourth aggravating factor, found by the A01/A03 agent and verified: `update_metadata` runs
  values through `_filter_metadata_fields` (`track_repository.py:78-94`), which allowlists
  **column names, not value length or content**, then `setattr(track, key, value)` directly at
  line 929. And **no global request-body size limit exists** — neither `config/middleware.py`
  nor `config/limits.py` imposes one — so the client-driven write vector is uncapped end to
  end.

  This became reachable partly as a side effect of a *fix*: closed issue **#4730** ("every
  file-extracted lyric is discarded") repaired the broken persist call without adding a bound,
  turning a silently-dropped value into a permanently-stored one.
- **Exploit Scenario**: Two independent vectors:
  1. **Malicious file** — attacker embeds an oversized `USLT` (lyrics) frame in an MP3 (ID3v2
     frame sizes are attacker-controlled up to hundreds of MB). The first
     `GET /api/library/tracks/{id}/lyrics` extracts and *permanently persists* the full blob
     (`tracks.py:215`). Every subsequent whole-library listing embeds it.
  2. **Local client** — any caller of `PUT /api/metadata/tracks/{id}` or
     `POST /api/metadata/batch` writes an arbitrarily large `title`/`comment`/`lyrics`
     directly, with no `max_length` on `MetadataUpdateRequest` (`metadata.py:36-53`) and no
     body-size middleware behind it.
- **Impact**: Availability and library usability. Unbounded DB growth and a backend memory
  spike proportional to `page_size × field_size` on endpoints that touch the row. **No XSS** —
  React escapes by default and there is no HTML sink (verified), so this is purely a resource
  issue.
- **Siblings**: All three update methods, plus `_get_or_create_genres` and the
  lyrics-extraction persist call.
- **Suggested Fix**: Call `_validate_and_normalize_track_info` from `update()`,
  `update_metadata()`, and `update_metadata_batch()` as well as `add()`, and extend its field
  list to cover `genre`, `comments`, and `lyrics` (the last with a larger but finite bound).
  Strip NUL and control characters at the same point.

---

### SEC-05: CSP omits `base-uri`, `form-action`, and `frame-ancestors`, which do not inherit from `default-src`; no COOP/CORP

- **Severity**: MEDIUM
- **OWASP Category**: A05 (Security Misconfiguration)
- **Location**: `auralis-web/backend/config/middleware.py:114-135`
  (`SecurityHeadersMiddleware.dispatch`)
- **Status**: NEW (distinct from open **#3900** `unsafe-inline` and open **#4712**
  `connect-src`)
- **Description**: The policy sets `default-src`, `script-src`, `style-src`, `font-src`,
  `img-src`, `connect-src`, and `media-src`. The CSP fallback rules treat the omissions
  differently, and that distinction is the finding: `object-src` **does** inherit from
  `default-src 'self'` (covered, though `'none'` is stricter), but **`base-uri`,
  `form-action`, and `frame-ancestors` do not fall back at all** and are therefore entirely
  unconstrained. `X-Frame-Options: DENY` (line 119) covers the framing case for legacy
  browsers, but `frame-ancestors` is the modern control and is absent. The response also never
  sets `Cross-Origin-Opener-Policy` or `Cross-Origin-Resource-Policy`.
- **Evidence**:
  ```python
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self' 'unsafe-inline'; "
      ...
      "media-src 'self' blob:;"
  )   # no base-uri, no form-action, no frame-ancestors, no object-src
  ```
- **Exploit Scenario**: Defence-in-depth only. There is no HTML-injection sink in the app
  today (verified), so nothing can currently inject a `<base>` tag or a hostile `<form>`. The
  finding is that if such a sink were introduced, `script-src 'self'` would become
  circumventable via `<base href>` redirecting relative script URLs, and form data could be
  exfiltrated cross-origin.
- **Impact**: None today. Hardening that removes a precondition permanently.
- **Related**: #3900, #4712 — fix all three in one pass.
- **Suggested Fix**: Append `base-uri 'self'; form-action 'self'; object-src 'none'; frame-ancestors 'none';`
  and add `Cross-Origin-Opener-Policy: same-origin` plus `Cross-Origin-Resource-Policy: same-origin`.

---

### SEC-06: Backend and FFmpeg child processes are spawned by bare command name through a fully inherited `PATH`

- **Severity**: LOW
- **OWASP Category**: A05 (Security Misconfiguration)
- **Location**: `desktop/main.js:132, 151, 184` (`spawn(pythonCmd, …)`);
  `auralis/io/loaders/ffmpeg_loader.py:140, 173, 196, 358`
  (`subprocess.run(['ffmpeg'/'ffprobe', …])`)
- **Status**: NEW
- **Description**: Both the Electron shell (spawning the Python backend) and the loader
  (invoking `ffmpeg`/`ffprobe`) resolve the executable by bare name against the fully
  inherited environment `PATH`. A binary shadowing `python`, `python3`, `ffmpeg`, or `ffprobe`
  earlier in the user's `PATH` executes instead, inside the app's process tree.
- **Impact**: Low under this threat model — it requires an attacker who can already write to
  a directory on the user's `PATH`, which implies capabilities that make this redundant. Worth
  recording because a packaged desktop app that bundles its own runtime should not be
  reachable by user-environment shadowing at all.
- **Suggested Fix**: For the packaged build, resolve the bundled interpreter and FFmpeg by
  absolute path. Where a system binary is genuinely intended, resolve once via
  `shutil.which()` / `which` at startup, log the resolved path, and reuse it.

---

### SEC-07: Two Electron navigation rejections log via `console.warn`, so they vanish in a packaged build

- **Severity**: LOW
- **OWASP Category**: A09 (Security Logging and Monitoring Failures)
- **Location**: `desktop/main.js:21` (`openExternalSafely`), `desktop/main.js:690`
  (`blockOffOrigin`, the `will-navigate`/`will-redirect` handler)
- **Status**: NEW
- **Description**: These are the two Electron controls that reject a navigation or an external
  URL — the highest-signal security events the shell produces. Both report via `console.warn`
  rather than `electron-log`. The sibling gap for backend stdout/stderr was already fixed
  (#4920), but that fix did not reach these two call sites, so in a packaged build a blocked
  navigation leaves no durable trace.
- **Impact**: Post-incident investigation. A user reporting "the app opened something odd" has
  no log to check.
- **Related**: #4920 (the fix that covered the sibling case).
- **Suggested Fix**: Replace both `console.warn` calls with the `electron-log/main` logger
  already imported at `main.js:3`.

---

### SEC-08: REST rate-limit 429s and Host-header 400s leave no log trace, unlike the equivalent WebSocket path

- **Severity**: LOW
- **OWASP Category**: A09 (Security Logging and Monitoring Failures)
- **Location**: `auralis-web/backend/config/middleware.py:206-267`
  (`RateLimitMiddleware.dispatch`), `:431` (`TrustedHostMiddleware` registration)
- **Status**: NEW
- **Description**: `OriginCheckMiddleware` logs every rejection with the offending origin
  (lines 301-314), and the WebSocket rate limiter returns a descriptive error. By contrast the
  REST rate limiter returns a bare 429 with no log line, and `TrustedHostMiddleware` — the
  DNS-rebinding defence — is Starlette's stock implementation, which logs nothing when it
  rejects a Host. A rebinding probe or an abusive local client is therefore invisible.
- **Impact**: Detection. These are exactly the two signals that would indicate a local process
  probing the backend.
- **Related**: #4925 (the same shape for path-validation rejections).
- **Suggested Fix**: Add a `logger.warning` in `RateLimitMiddleware.dispatch` on the 429 branch
  (client IP + matched prefix), and wrap or subclass `TrustedHostMiddleware` to log rejected
  Host values.

---

### SEC-09: Frontend `pnpm audit` reports 9 advisories; all confined to dev/build-only chains

- **Severity**: LOW (informational)
- **OWASP Category**: A06 (Vulnerable and Outdated Components)
- **Location**: `auralis-web/frontend/package.json`, `auralis-web/frontend/pnpm-lock.yaml`
- **Status**: NEW for the 6 non-router advisories (the react-router subset is covered by
  closed #4884 and open #4954; #4879 covered `desktop/` only)
- **Description**: `pnpm audit` reports 2 high, 5 moderate, 2 low across 375 dependencies.
  Reachability was checked with `pnpm why` for each high; **none ships in the packaged app**:

  | Advisory | Sev | Package | Reachability |
  |---|---|---|---|
  | Memory-exhaustion DoS from tiny fragments | high | `ws` 8.18.3/8.21.0 | **Dev only** — via `vitest → jsdom / happy-dom` |
  | Custom generators loop indefinitely at size 0 | high | `nanoid` 3.3.16 | **Dev only** — via `vite → postcss` |
  | Uninitialized memory disclosure | moderate | `ws` | Same dev-only path |
  | Stack overflow via deeply nested YAML | moderate | `yaml` | Build/config-time |
  | Arbitrary file read via dev server | low | `esbuild` | Dev server only, binds localhost |
  | Arbitrary file read via `sourceMappingURL` | low | `@babel/core` | Build-time |
  | Open redirect via backslash in `<Link>` | moderate | `react-router(-dom)` | Prod dep, but **zero production importers** per open #4954 |
  | Arbitrary constructor injection via `deserializeErrors()` | moderate | `react-router` | Requires SSR/data-router error path; this is an SPA with no SSR |

  For contrast, `desktop/` — which *does* ship — now reports **0 advisories across 277
  dependencies**, down from 26 on 2026-07-29.
- **Impact**: None on the shipped artifact. Recorded so the next audit inherits the
  reachability baseline instead of re-deriving it.
- **Suggested Fix**: Bump `vite`/`vitest`/`postcss` opportunistically. Acting on #4954 and
  dropping `react-router-dom` from `dependencies` removes the only production-declared package
  on the list.

---

### SEC-10: Artwork URL allowlist accepts cleartext `http://` as well as `https://`

- **Severity**: LOW
- **OWASP Category**: A02 (Cryptographic Failures)
- **Location**: `auralis/utils/artwork_security.py:24-37`
- **Status**: NEW
- **Description**: `validate_artwork_url` enforces a strict host allowlist — the control that
  makes the SSRF posture sound — but permits either scheme:
  `if parsed.scheme not in ("https", "http")`. Every host in `TRUSTED_ARTWORK_DOMAINS` serves
  HTTPS, so the `http` branch buys nothing and leaves a cleartext path open. The URLs come
  from third-party API responses, and a MusicBrainz `url-rels` resource is arbitrary
  editor-supplied data, so an upstream record specifying `http://upload.wikimedia.org/…` would
  be accepted and fetched in the clear.
- **Exploit Scenario**: A network-position attacker (hostile Wi-Fi, malicious router) replaces
  the response body for a cleartext artwork fetch, writing chosen image bytes into
  `~/.auralis/artwork`. The payload is magic-byte sniffed and size-capped on the way in, so the
  practical result is a wrong or offensive cover image — and, chained with SEC-03, an attacker
  who controls those bytes controls the decompression bomb too.
- **Impact**: Low. Integrity of cached artwork, plus disclosure over a hostile network of which
  artists the user is looking up.
- **Related**: SEC-03 (chain: cleartext fetch is one way to deliver the bomb).
- **Suggested Fix**: Drop `"http"` from the accepted scheme tuple — one line, no legitimate
  caller affected.

---

### SEC-11: `POST /api/metadata/batch` echoes the server's absolute filepath, the one place the "#3205 filepath is server-only" rule is broken

- **Severity**: LOW
- **OWASP Category**: A01 (Broken Access Control)
- **Location**: `auralis-web/backend/routers/metadata.py:120-131`
  (`BatchMetadataResultItem.filepath`), populated at `:453-458`, returned at `:506`
- **Status**: NEW
- **Description**: The batch-metadata response model declares `filepath: str | None` per result
  item. Every other client-facing payload in the codebase deliberately omits the server
  filesystem path — `serialize_track`, the single-track metadata endpoints, and `player.py`'s
  `track_loaded` broadcast all strip it per **#3205**. This is the single place it leaks, and
  the code comment at the declaration **says so explicitly**, having flagged it rather than
  fixed it because removing the field is a contract change.
- **Evidence**:
  ```python
  # metadata.py:123-128 — the codebase documenting its own exception
  # NOTE: `filepath` is echoed by `MetadataEditor.batch_update` and is
  # therefore declared here so the response_model does not silently drop it.
  # It is the one place a server-side path reaches a client, which sits
  # awkwardly beside #3205's "filepath is server-only" rule — flagged rather
  # than changed here, since removing it is a contract change, not a
  # schema-coverage fix.
  filepath: str | None = Field(default=None, description="Server-side file path")
  ```
- **Exploit Scenario**: A local script calling the batch-metadata API for tag edits
  incidentally learns the absolute on-disk path of every track it touches. Under this threat
  model that information is already available to any local process with the user's
  privileges, which is what caps this at LOW.
- **Impact**: Minor local filesystem-layout disclosure. No privilege gain. The real cost is
  consistency: a documented invariant with one known exception erodes into no invariant.
- **Suggested Fix**: Drop `filepath` from `BatchMetadataResultItem`, or run it through
  `security/path_security.py::sanitize_path_for_response()` (which already exists for exactly
  this purpose) so it degrades to a `~/`-relative form.

---

### SEC-12: Rust `median()` panics on NaN via `partial_cmp().unwrap()`, reachable from the fingerprint PyO3 boundary

- **Severity**: LOW
- **OWASP Category**: A03 (Injection — Rust FFI boundary)
- **Location**: `vendor/auralis-dsp/src/rhythm.rs:510-511` (`median()`), reached via
  `trim_beats()` from `rhythm_stability()` (`rhythm.rs:50`), whose value is surfaced across
  the PyO3 boundary at `vendor/auralis-dsp/src/py_bindings.rs:612`
- **Status**: NEW
- **Description**: `median()` sorts a float slice with
  `v.sort_by(|a, b| a.partial_cmp(b).unwrap())`. `f64::partial_cmp` returns `None` for NaN
  operands, so a single NaN anywhere in the beat-tracking `localscore` array panics. The
  containment is genuinely good and worth recording: `vendor/auralis-dsp/src/` contains
  **zero `unsafe` blocks** (verified — `grep -rn unsafe src/` returns 0 hits), so this is a
  clean panic, not memory unsafety, and PyO3 wraps `#[pyfunction]` calls in `catch_unwind`,
  converting it to a Python `PanicException` rather than aborting the process.

  *Reachability precision*: `rhythm_stability` is not itself a `#[pyfunction]`; its value is
  computed as part of the fingerprint and set into the returned dict at `py_bindings.rs:612`,
  so the reachable entry point is `compute_fingerprint`.
- **Evidence**:
  ```rust
  // vendor/auralis-dsp/src/rhythm.rs:510-511
  fn median(v: &mut [f64]) -> f64 {
      v.sort_by(|a, b| a.partial_cmp(b).unwrap());
  ```
  Other production `.unwrap()`/`.expect()` sites noted but **not** traced for reachability:
  `limiter.rs:101`, `compressor.rs:179,188`, `onset_detector.rs:160`.
- **Exploit Scenario**: A crafted or corrupted audio file whose decoded samples produce a NaN
  in the onset-strength envelope reaches `compute_fingerprint` during a library scan and
  panics that analysis call. This codebase has a precedent for the class — closed **#4520**
  fixed "Rust HPSS panics/overflows on very short audio" in a different module.
- **Impact**: One fingerprint operation raises `PanicException` instead of completing. Whether
  that degrades to "this track's fingerprint silently fails" or aborts a wider scan depends on
  how broadly the Python caller catches — **not verified this pass**.
- **Suggested Fix**: Use `f64::total_cmp` (or
  `partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal)`), matching the NaN-guard pattern
  already established by #4910 and #4520. Then sweep the four untraced `.unwrap()` sites above
  for the same shape.

---

## Relationships between findings

- **SEC-01 + SEC-02 are one supply-chain problem** with two symptoms: the release path resolves
  transitives fresh and unscanned, and the two lockfiles disagree so nobody notices. A single
  FastAPI bump plus a `--require-hashes` release install closes both.
- **SEC-03 + SEC-04 are the same design gap in two parsers.** The audio decoder bounds
  *decoded* size before allocating; neither the image decoder nor the tag parser applies the
  equivalent check to the same untrusted file. One shared "bound untrusted parsed output"
  discipline closes the class rather than the instances.
- **SEC-03 chains with itself across a trust boundary**: the scan-time failure (backend) is
  what *persists* the artefact causing the view-time failure (renderer). Fixing only the
  serving side leaves the bomb on disk; fixing only the scan side leaves already-imported
  libraries exploitable. Both halves are required.
- **SEC-10 → SEC-03**: the cleartext fetch is a delivery vector for the bomb SEC-03 fails to
  contain — two LOW/MEDIUM findings that combine into attacker-controlled bytes on disk.
- **SEC-01 + SEC-05 + SEC-11 share a theme**: each is a place where a *comment, a default, or
  a documented rule* claims a protection the code does not actually provide — the inverted
  middleware-order rationale, the CSP directives that silently do not inherit, and a
  "filepath is server-only" invariant with a self-documented exception. None is exploitable
  today; all three are cheap to make true, and each one left standing makes the next reader
  trust a guarantee that is not there.
- **SEC-04 has two independent trigger vectors** (malicious file *and* local client PUT) that
  share one fix. The file vector became reachable as a side effect of the #4730 bug fix — a
  reminder that repairing a "value is silently dropped" bug converts an unbounded input from
  harmless to persistent.

## Prioritized Fix Order

1. **SEC-01** (HIGH) — change the release install to `requirements-lock.txt --require-hashes`
   and add `pip-audit` to CI. This is the only finding affecting what ships, and the fix is
   configuration, not code. Fix the inverted `middleware.py:433-436` comment in the same pass.
2. **SEC-03** (MEDIUM) — the only code finding reachable by simply adding an album, and the
   only one that persists a hostile artefact. Fix scan side and serving side together.
3. **SEC-04** (MEDIUM) — same attacker, same file, and the fix is three call sites plus three
   field names in an existing helper.
4. **SEC-02** (MEDIUM) — falls out of SEC-01's FastAPI bump; add the reconciliation check.
5. **SEC-05** (MEDIUM) — one header string; bundle with open #3900 / #4712 so CSP is touched once.
6. **SEC-12** (LOW) — one-character-class fix (`total_cmp`), and it is the only finding in the
   Rust FFI surface, which is otherwise unaudited. Sweep the four untraced `.unwrap()` sites
   at the same time.
7. **SEC-07, SEC-08, SEC-10, SEC-11** (LOW) — one-liners each. Bundle SEC-07/SEC-08 with
   #4925 (same logging gap) and SEC-11 with any #3205 contract cleanup.
8. **SEC-06, SEC-09** (LOW) — no action needed for security; fold into packaging and #4954
   dependency cleanup respectively.

### Also worth doing: close #4814

**#4814** ("`GET /api/library/tracks/{id}/lyrics` reads DB filepath with mutagen, bypassing
`validate_file_path`") is **already fixed in code but still open on GitHub**. Verified at
`auralis-web/backend/routers/tracks.py:182-183`, which now calls
`validate_file_path(str(track.filepath))` before `mutagen.File(...)`. Closing it keeps the
open-issue list from overstating the real exposure.

---

## Known / Already Tracked (verified still present, not re-filed)

| Issue | Title | Verified |
|---|---|---|
| #5066 | `file://` in WS origin allowlist but not REST allowlist | `globals.py:46` vs `middleware.py:345-350` |
| #4954 | `react-router-dom` is a production dep with zero production importers | Relevant to SEC-09 |
| #4932 | electron-log file transport mode `0o666` | Still present |
| #4925 | Path-validation rejections logged at only ~half of call sites | Still present; SEC-08 is the sibling |
| #4905 | Auto-update ships unsigned binaries, verification disabled | Still present; nothing new adjacent |
| #4871 | Pinned manifests don't describe the verified environment; Starlette pinned nowhere | Root cause of SEC-01/SEC-02 |
| #4868 | GitHub Actions pinned to mutable tags, not commit SHAs | Still present |
| #4855 | Predictable fixed-name temp working dirs, world-readable | Still present |
| #4853 | `setAsDefaultProtocolClient` with no `open-url` handler | Still present |
| #4851 | Preload exposes 2 IPC methods with no `ipcMain` handler | `preload.js:45` (comment now documents it) |
| #4834 | FFmpeg protocol guard only checks `"://"` | `ffmpeg_loader.py:275` |
| #4824 | `fetch_artwork.py` bypasses `~/.auralis` permission hardening | Still present |
| #4823 | Scanner follows symlinks with no containment check | Still present |
| #4818 | `_preprocess_upcoming_chunks` uses unvalidated player-state filepath | Still present |
| #4817 | Mastering-recommendation endpoint feeds unvalidated DB filepath | Still present |
| #4814 | `tracks/{id}/lyrics` reads DB filepath with mutagen, bypassing validation | **FIXED IN CODE, ISSUE STILL OPEN** — `tracks.py:182-183` now calls `validate_file_path`. Recommend closing. |
| #4807 | `PathValidationError` text with allowed-dir list reflected into 400 bodies | `path_security.py:158-162` |
| #4806 | `ModuleError` embeds raw FFmpeg stderr + absolute paths | Still present |
| #4712 | CSP `connect-src` localhost-only vs CORS/WS allowing `127.0.0.1` | Still present |
| #4405 | Sidecar checksum gap (residual after #4910) | Correctly still open |
| #3902 / #3901 / #3900 | Middleware magic numbers; rate-limit magic numbers; CSP `unsafe-inline` | Still present |

## Fixed since the 2026-07-29 audit (confirmed resolved, no regression)

| Was | Now |
|---|---|
| #4531 / #4872 / #4882 — `Cargo.lock` gitignored; `cargo audit` gate scanned nothing | `Cargo.lock` **tracked**; `rust-audit.yml` runs and reports clean |
| #4889 — no hash-locked Python lockfile | `uv.lock` **and** `requirements-lock.txt` exist and are tracked; `requirements.txt` 19/19 `==`-pinned; `lockfile-guard.yml` + `requirements-pin-guard.yml` added |
| #4879 / #4876 / #4883 — `desktop/` had 26 advisories incl. `builder-util-runtime`, `app-builder-lib` | `pnpm audit` in `desktop/`: **0 advisories / 277 deps**; Electron bumped to 43.2.0 |
| #4874 — build orchestrators shelled out to npm, bypassing the pnpm lockfile | Now use pnpm; `lockfile-guard.yml` gates it |
| A05-1 / A05-2 / A05-7 (prior report) — `shell.openExternal` unguarded; `sandbox` unset; no `will-navigate` handler | All fixed: `sandbox: true` (`main.js:337`), `openExternalSafely()` on both handler sites, `will-navigate` + `will-redirect` guards (`main.js:666-696`), preload origin guard (#4858) |
| #4910 — sidecar NaN/range validation | Fixed; residual checksum gap correctly remains as #4405 |
| #4929 — absolute-path INFO logging in `migration_manager.py` | Fixed |
| #4920 — backend logs lost in packaged app | Fixed for backend stdout/stderr (SEC-07 is the part it didn't reach) |
| #4837 — fingerprint worker per-file timeout | Fixed; no permanent wedge possible |
| #4839 / #4758 — `StreamlinedCacheAdapter._temp_chunk_cache` unbounded | Fixed — the class no longer exists |

## Regression checks — 22 prior fixes re-verified as still present

`#4826` (ffprobe `--` end-of-options, **both** call sites) · `#2413` + `#3845` (WS origin
allowlist + loopback-only empty Origin) · `#4353` (TrustedHost) · `#4893` (OriginCheck / CSRF)
· `#4728` (rate limit keyed on matched prefix, not full path) · `#4804` (rate-limit hard cap +
LRU touch) · `#3329` (rate-limit critical section under `asyncio.Lock`) · `#3843` (RateLimit
innermost so 429s carry security headers) · `#3671` + `#4875` + `#4128` (pre-decode duration /
decoded-size / VBR-fallback guards) · `#4532` + `#4527` (thumbnail purge + per-writer temp) ·
`#2560` + `#2170` (upload UUID filename + `open(…, "xb")` exclusive create) · `#2415` + `#2421`
(upload magic-byte validation + rejection logging) · `#3494` (upload size cap applied at read)
· `#2561` (job output confined to tempdir) · `#2559` (client-supplied processing paths
validated) · `#2416` + `#2576` (SSRF host allowlist + payload cap) · `#4858` (preload origin
guard) · `#4844` (`openExternalSafely`) · `#3811` (per-IP WS rate limit surviving reconnect) ·
`#3842` (scan-folder unregistration) · `#4802` (namespaced `AURALIS_DEV_MODE`).

## Verified Clean — examined and found not vulnerable

| Area | Location | Why it is clean |
|---|---|---|
| Path containment | `security/path_security.py:103-178` | `Path(filepath).resolve()` then `resolved.relative_to(base)`; `".."` rejected in raw parts; exists/is_file/`R_OK` checked. `resolve()` follows symlinks **before** the compare, so a symlink inside `~/Music` pointing at `/etc/passwd` is rejected. |
| Bind address | `main.py:259-261` | `host="127.0.0.1"` hardcoded. No `0.0.0.0` reachable by config, argv, or env. Single listener confirmed. |
| CORS | `config/middleware.py:321-350, 452-460` | Explicit `{http,https}://{localhost,127.0.0.1}:{8765 [+3000-3006 dev-only]}`; `allow_credentials=True` with explicit method/header lists — never `["*"]`. |
| Middleware order | `config/middleware.py:393-465` | Inbound CORS → SecurityHeaders → NoCache → OriginCheck → TrustedHost → RateLimit → app. Every short-circuit response bubbles back through SecurityHeaders. (The *rationale comment* at 433-436 is wrong — see SEC-01 — but the order itself is deliberate and correct.) |
| CSRF | `config/middleware.py:270-318` | All state-changing `/api` methods require a trusted Origin; empty Origin only from `LOOPBACK_HOSTS`. Closes the "simple request" hole CORS does not cover. |
| DNS rebinding | `config/middleware.py:353-390` | `TrustedHostMiddleware` on `("localhost","127.0.0.1")`; test hosts admitted only under pytest. |
| Dev-mode gate | `config/app.py:25-49` | Namespaced `AURALIS_DEV_MODE` (no bare `DEV_MODE` alias) + `--dev` argv, with a warning on env activation. |
| WS connect | `config/globals.py:79-113` | Origin allowlist; empty Origin only from loopback. |
| WS per-message hygiene | `websocket/websocket_security.py:170-229` | 64 KB cap → JSON guard → Pydantic `WebSocketMessageBase` validation, on the one real receive loop. Applied per message, not just at handshake. |
| WS rate limiting | `websocket/websocket_security.py:88-137` | Per-connection **and** per-IP buckets; the IP bucket deliberately survives `cleanup()` so a reconnect loop cannot reset it. |
| **SQL injection** | `auralis/library/` (all 13 repos) | 100% SQLAlchemy ORM. Only raw SQL is parameterless `PRAGMA` and migration DDL. `order_by` is `Literal[…]`-constrained at the router boundary (`tracks.py:71`, `albums.py:93`, `artists.py:166`) **and** re-validated against `VALID_ORDER_COLUMNS` / `getattr(Model, col, default)` in the repos (`album_repository.py:134-136`). Defence in depth, no interpolation. |
| **Command injection** | repo-wide | `shell=True` appears **nowhere**. All `subprocess` calls are list-form. |
| Argument injection | `unified_loader.py:223-231`, `ffmpeg_loader.py:195-203` | `--` end-of-options present at both ffprobe sites (#4826 not regressed). FFmpeg input is the value of `-i`, so a leading-dash filename cannot become a flag. |
| Pre-decode bounds | `ffmpeg_loader.py:296-322` | ffprobe first, then `MAX_DURATION_SECONDS` (7200) **and** `oversize_decode_detail(duration, sr, channels)` enforced before decode, plus a file-size lower-bound fallback for VBR MP3s with no reported duration. Exemplary. |
| Deserialization | repo-wide grep | No `pickle`, `yaml.load`, `marshal`, `joblib`, `torch.load`, or `np.load(allow_pickle=True)` in `auralis/` or the backend. ML genre classifier confirmed rule-based — no model files loaded. |
| Artwork read route | `routers/artwork.py:329-357` | `resolve(strict=False)` then `is_relative_to(~/.auralis/artwork)` **before** the existence check — correct ordering, no oracle. |
| Thumbnail cache key | `core/thumbnail_cache.py:52-58` | `sha1(str(src))[:12]` — fully hashed; no user-controlled component reaches a filename. |
| Embedded-artwork write | `auralis/library/artwork.py:293-316` | Filename is `album_{int}_{md5[:8]}{.png\|.jpg}`; extension from a two-branch literal, never the tag's MIME string. |
| Upload (files router) | `routers/files.py:183-250` | Extension allowlist → 500 MB cap applied *at read* → magic-byte check → UUID permanent name. |
| Upload (processing) | `routers/processing_api.py:322-350` | UUID name, extension allowlist with `.bin` fallback, `open(…, "xb")` defeats the symlink TOCTOU. |
| Job download | `routers/processing_api.py:434-459` | Output confined to `tempfile.gettempdir()` via `relative_to`. |
| Pagination | all list routers | Every endpoint uses `Query(…, ge=, le=)`, mostly via `PaginationParams`. No unbounded `limit`. |
| Frontend HTML sinks | `frontend/src/` | No `dangerouslySetInnerHTML`, `eval`, `new Function`, `document.write`, `srcdoc`, or `insertAdjacentHTML` in app code. The single `innerHTML` write (`index.tsx:54`) escapes message and stack first. |
| SSRF | `utils/artwork_security.py`, `services/artwork_service.py`, `services/artwork_downloader.py` | Host allowlist at every fetch site — including the open-ended MusicBrainz `url-rels` resource (`artwork_service.py:179`) — **and re-applied to the final URL after redirects** (`artwork_downloader.py:270-273`), with a 5 MB cap. |
| Electron hardening | `desktop/main.js:334-339, 357, 666-696`; `preload.js:13-70` | `nodeIntegration:false`, `contextIsolation:true`, `sandbox:true`, `webSecurity:true`; both `setWindowOpenHandler` sites plus `will-navigate` and `will-redirect` route through `openExternalSafely()`; preload refuses to expose `electronAPI` on a non-localhost origin. |
| Hardcoded secrets | repo-wide grep | None. Discogs token / Last.fm key arrive only via CLI args or env. `.gitignore` excludes `.env`; no credential committed. |
| CI workflow injection | `.github/workflows/` (7 files) | No `pull_request_target`, no `workflow_run`, no `${{ github.event.* }}` interpolated into any `run:` block. |
| Migration integrity | `library/migration_manager.py:29-135, 293-330, 427-463` | Inter-process file lock (`fcntl.flock` / `msvcrt.locking`) **plus** a same-process `threading.Lock` (line 48); explicit `BEGIN`/`COMMIT`/`ROLLBACK`; backups use the SQLite Online Backup API (`src.backup(dst)`), correctly capturing WAL-resident data a file copy would miss; fail-closed on backup failure; no downgrade path. |
| Fingerprint worker | `services/fingerprint_queue.py` | Per-file timeout/watchdog present (#4837); `ResizableSemaphore` permit accounting correct. No pathological-file wedge. |
| Queue / player state | `player/queue_controller.py`, `playback_controller.py` | Index clamping and locking already heavily hardened; no out-of-bounds or invalid transition found. |
| Playlist import | M3U/XSPF parser | Present but **unreachable dead code** — no router or frontend path wires it up. |
| Scan depth | `library/scanner/file_discovery.py:19, 124` | `MAX_SCAN_DEPTH = 50` bounds recursive descent. |
| Log rotation | `desktop/main.js:3, 11` | Backend installs no `FileHandler`; stdout is captured by `electron-log` (#4920), whose file transport rotates at 1 MB. Bounded. |

## Coverage Gaps — not reached in this run

Stated explicitly so the next audit starts here rather than re-deriving it:

- **Rust FFI internals** (`vendor/auralis-dsp/src/`, 19 files): **partially** covered. Two
  useful facts were established — the crate contains **zero `unsafe` blocks**, and one
  NaN-panic path was found and filed (SEC-12). Still **not** audited: slice indexing and
  integer casts drivable out of bounds by attacker-sized input, and the reachability of the
  four remaining production `.unwrap()`/`.expect()` sites (`limiter.rs:101`,
  `compressor.rs:179,188`, `onset_detector.rs:160`). **Highest-value target for the next run.**
- **Whether a Rust `PanicException` aborts a wider scan** or is swallowed per-track — the
  Python-side catch breadth around `compute_fingerprint` was not traced (see SEC-12 Impact).
- **Chunk cache eviction bounds** (`auralis-web/backend/core/chunk_cache*.py`) — whether the
  on-disk chunk cache is size-bounded for a very long track.
- **`~/.auralis` and SQLite DB file modes** (#4347) were not individually re-verified.
- **The CVE identifier in SEC-01** was not independently confirmed by the orchestrator (see
  the verification caveat in that finding).

---

*Report generated 2026-08-13. No GitHub issues were created; no git write operations were
performed. To publish:*

```
/audit-publish docs/audits/AUDIT_SECURITY_2026-08-13.md
```
