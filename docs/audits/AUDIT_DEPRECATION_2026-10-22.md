# Deprecation Audit — 2026-10-22

**Scope**: all 8 dimensions of `.claude/commands/audit-deprecation.md`: Python stdlib, NumPy/SciPy/audio, FastAPI/Pydantic/SQLAlchemy, React/Redux/MUI, Node/npm/build, Rust/PyO3, internal deprecations, config/CI.
**Method**: a fresh read of the tree at `44e4d433` and the commits after it. No prior report was used. Dedup ran against `gh issue list --state all` (5,613 issues, highest #5859), plus `docs/audits/` and `.claude/issues/`.
**Execution**: Dimensions 1-6 and 8 were run inline. Dimension 7 is a broad, read-heavy sweep of compat and deprecated comments; it was delegated to one read-only `general-purpose` agent. Its findings were spot-checked against call sites before being merged: DEP-11, DEP-12, DEP-14, DEP-15 and DEP-16 were re-grepped by the orchestrator.

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 16 |

**There are no upgrade blockers.** Empirical checks:

- **Python imports**: all 542 first-party modules under `auralis/` and `auralis-web/backend/` imported with `warnings.simplefilter("always")`. Result: zero `DeprecationWarning`, `PendingDeprecationWarning` or `FutureWarning`, and zero import failures.
- **Scoped pytest**: 13 representative test files plus `tests/auralis/dsp` (dsp, io, library, backend API, streaming lifecycle, lifespan, migrations; about 500 tests) were run with `-W default::DeprecationWarning -W default::PendingDeprecationWarning -W default::FutureWarning`. They emitted zero warnings.
- **Rust**: `cargo check --all-targets` on `vendor/auralis-dsp` (pyo3/numpy 0.29.2, edition 2024, toolchain 1.96.0) reported zero deprecation warnings.
- **Grep sweeps came back clean on**:
  - Python: `utcnow`, removed stdlib modules, `collections` ABCs, unittest aliases, `codecs.open`, `rmtree(onerror=)`.
  - NumPy/SciPy: NumPy 2.x removed aliases and functions, `scipy.fftpack`, `scipy.misc`, removed `scipy.signal` and `scipy.integrate` names.
  - Pydantic V1 syntax, `on_event`, Starlette-1.x-removed APIs.
  - React: `ReactDOM.render`, legacy lifecycles, `defaultProps`, `PropTypes`, `React.FC`, `connect()`, `@mui/styles`, MUI v6/v7 deprecated props (all moved to `slotProps`).
  - Node: built-ins without `node:`, `url.parse`, `fs.exists`.
  - Electron 43: deprecated APIs.
  - GitHub Actions: all actions are pinned to SHAs at current majors, `pnpm/action-setup` has no `version:`, and every workflow uses Python 3.14.

What remains is housekeeping:

- **Dependency hygiene** (DEP-01 to DEP-03, DEP-06): two of these were introduced *today* by Dependabot bumps.
- **One regression of a closed migration** (DEP-04).
- **Two small build and naming leftovers** (DEP-07, DEP-08).
- **Internal compat shims and re-exports that only tests still use** (DEP-09 to DEP-16).

**Recommended order**:

1. DEP-01 (re-align the vitest family; one-line `package.json` change).
2. DEP-02 (desktop `@xmldom/xmldom` override).
3. DEP-06 (dev floors and pre-commit revs).
4. DEP-04 and DEP-05 (test-tree API drift).
5. DEP-03 and DEP-07.
6. The internal-shim deletions DEP-09 to DEP-16, one PR per subsystem.

**Already tracked, not re-reported**:

| Issue | What |
|---|---|
| #5688 | `asyncio.TimeoutError` at 6 test sites, still present |
| #5689 | Blanket `PendingDeprecationWarning` ignore. **Sibling for that issue**: `pytest.ini:106-108`'s `ignore::DeprecationWarning:soundfile` and the two `UserWarning:.*soundfile.*` filters are dead too, because installed `soundfile.py` 0.14.0 contains no `warnings.warn` call at all. Fold them into the #5689 fix. |
| #5687 | pnpm `rollup` override |
| #5686 | QueueController aliases |
| #5823 | Twin wire spellings |
| #5803 | `serialize_object` Mock branch |
| #5628 | Orphaned components |
| #5411 | Closed deliberately for production. `from __future__ import annotations` remains in 74 test files and 6 `scripts/` files by decision. |

---

## Findings

### DEP-01: Vitest bumped to 4.1.11 while `@vitest/coverage-v8` and `@vitest/ui` stay at 4.1.7 (mixed-version family)
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/package.json:57-58,65`; `auralis-web/frontend/pnpm-lock.yaml:844-848`
- **Status**: NEW
- **Deprecated API**: Running Vitest companion packages at a different version from `vitest`, which is unsupported. `@vitest/coverage-v8@4.1.7` declares an exact peer `vitest: 4.1.7`.
- **Deprecated Since**: Introduced today by Dependabot `5f0f3a79` (merged in `e4a0e3fb`), which bumped only `vitest`.
- **Removal Version**: n/a
- **Replacement**: Bump `@vitest/coverage-v8` and `@vitest/ui` to `^4.1.11` in the same change.
- **Affected Files**: 2 (`package.json`, `pnpm-lock.yaml`)
- **Evidence**:
  ```yaml
  '@vitest/coverage-v8@4.1.7':
    peerDependencies:
      '@vitest/browser': 4.1.7
      vitest: 4.1.7          # installed vitest is 4.1.11
  ```
  The lockfile now carries two copies of `@vitest/pretty-format` (4.1.7 and 4.1.11).
- **Migration Path**:
  1. Run `pnpm add -D @vitest/coverage-v8@^4.1.11 @vitest/ui@^4.1.11`.
  2. Confirm `pnpm install --frozen-lockfile` has no unmet-peer warnings.
  3. Run `pnpm run test:coverage` once.
- **Risk**: `test:coverage` and `test:ui` run on a mixed family. Vitest warns on mixed versions and coverage instrumentation can break. CI's `test:ci` does not use coverage, so the gate is unaffected today. Dependabot will keep splitting the family until the three are bumped together; a Dependabot `groups:` entry would prevent that.

### DEP-02: Desktop lockfile now resolves `@xmldom/xmldom@0.8.13`, which the registry flags "this version has critical issues"
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `desktop/pnpm-lock.yaml:146-149` (consumer `plist@3.1.0` at `:2000-2003`, under `app-builder-lib@26.15.7`)
- **Status**: NEW. Related: #5429 (closed), which inventoried the other 5 deprecated transitive packages in this lockfile; this one was not among them.
- **Deprecated API**: `@xmldom/xmldom@0.8.13`, marked `deprecated: this version has critical issues, please update to the latest version`.
- **Deprecated Since**: The flag entered the lockfile today in `7c565a4c` (the Electron 43.2→43.7 Dependabot bump re-resolved the tree).
- **Removal Version**: n/a
- **Replacement**: The patched `@xmldom/xmldom` line, via a pnpm override.
- **Affected Files**: `desktop/pnpm-lock.yaml`, `desktop/pnpm-workspace.yaml`
- **Evidence**: `grep -n deprecated: desktop/pnpm-lock.yaml` shows 6 entries. The 5 known from #5429 are `boolean`, `glob@7`, `inflight`, `lodash.isequal`, `rimraf@2`; the new one is `@xmldom/xmldom@0.8.13`, with the chain `electron-builder → app-builder-lib → plist → @xmldom/xmldom`.
- **Migration Path**:
  1. Add `'@xmldom/xmldom': '<latest patched>'` to `overrides:` in `desktop/pnpm-workspace.yaml`. That file already overrides `app-builder-lib` and `js-yaml` for the same reason.
  2. Run `pnpm install`.
  3. Run a `build:mac` dry run in CI.
- **Risk**: Build-time only. plist parsing runs during macOS packaging over files the project controls, so exposure is low. It is still an unreviewed "critical" flag in the release toolchain, and `lockfile-guard` / `pnpm audit` will keep surfacing it.

### DEP-03: `criterion = "0.5"` dev-dependency has no benchmark or caller; it accounts for ~40 of 84 locked crates
- **Severity**: LOW
- **Dimension**: Rust/PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:28`; `vendor/auralis-dsp/Cargo.lock`
- **Status**: NEW
- **Deprecated API**: An unused dev-dependency pinned to criterion 0.5. Newer criterion deprecates `criterion::black_box` in favour of `std::hint::black_box`.
- **Deprecated Since**: Added in `0e7ee0aa` (2025-11-24). The crate has never had a `benches/` directory or a `[[bench]]` target.
- **Removal Version**: n/a
- **Replacement**: Delete the dependency. Re-add a current criterion only together with a real bench target.
- **Affected Files**: 2
- **Evidence**:
  - `grep -rn criterion vendor/auralis-dsp/src vendor/auralis-dsp/Cargo.toml` finds only the `Cargo.toml` line.
  - `cargo tree -e normal,build` shows 44 crates against 84 for the full tree.
  - `cargo tree -i criterion` shows `[dev-dependencies] └── auralis-dsp`.
- **Migration Path**:
  1. Remove the `[dev-dependencies]` entry.
  2. Run `cargo update -w`.
  3. Commit the lockfile, which is tracked.
- **Risk**: Roughly 40 extra crates that `rust-audit.yml` must scan and that can raise RustSec advisories on code that never builds into anything.

### DEP-04: Legacy `Session.query()` reintroduced in the test tree after #4333 migrated it, plus 2 sites in a tracked dev script
- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic/SQLAlchemy
- **Location**:
  - `tests/auralis/library/test_fingerprint_version_stamping_5572.py:106`
  - `scripts/development/monitor_fingerprinting.py:37-38`
- **Status**: Regression of #4333. That issue converted all 15 test files (50 sites) in `36f6f26f`. The new test arrived in `c340250e` on 2026-10-20.
- **Deprecated API**: The `Session.query()` / `Query` API, which SQLAlchemy 2.0 documents as "legacy".
- **Deprecated Since**: SQLAlchemy 2.0, which designates it legacy.
- **Removal Version**: Not scheduled. The 2.0 docs say it will remain but receive no new features.
- **Replacement**: `session.scalars(select(TrackFingerprint).filter_by(track_id=1)).one()`; `session.scalar(select(func.count()).select_from(Track))`.
- **Affected Files**: 2 (3 sites)
- **Evidence**: `row = session.query(TrackFingerprint).filter_by(track_id=1).one()`. Production (`auralis/`, `auralis-web/backend/`) has 0 `.query(` calls.
- **Migration Path**:
  1. Rewrite the 3 sites with `select()`.
  2. Optionally add a `tests/`-wide AST guard like the one in `tests/test_conftest_hooks_4529.py` so the next new test cannot reintroduce the legacy API.
- **Risk**: Style drift only; it works on 2.0.51. The monitor script also opens `~/.auralis/library.db` with its own engine instead of going through `LibraryDatabase`.

### DEP-05: `asyncio.get_event_loop().time()` in a backend test (4 sites)
- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/backend/test_jump_to_track_broadcast_outside_lock_5324.py:109,111,131,133`
- **Status**: NEW. Related: #5688 (open), the `asyncio.TimeoutError` sibling in the same tree; both are test-only asyncio legacy APIs and can be fixed in one PR.
- **Deprecated API**: `asyncio.get_event_loop()`. Since 3.12 it warns outside a running loop, and since 3.14 it raises `RuntimeError` when there is no current loop. Inside a coroutine it still works, but `get_running_loop()` is the documented API.
- **Deprecated Since**: Python 3.10/3.12 (progressive)
- **Removal Version**: The no-loop path raises from 3.14.
- **Replacement**: `asyncio.get_running_loop().time()`, or `time.monotonic()`.
- **Affected Files**: 1
- **Evidence**: `start = asyncio.get_event_loop().time()` inside `async def test_...`. Production has 0 hits.
- **Migration Path**: Replace the 4 calls.
- **Risk**: None today, because the calls sit inside running coroutines. The pattern is the one #2145 removed from production.

### DEP-06: Dev-tool floors and pre-commit revs no longer describe the toolchain
- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:98,104,108`; `.pre-commit-config.yaml:34` (black rev)
- **Status**: NEW. Related closed issues: #4336, #4904, #4528.
- **Deprecated API**: Version floors and justifications that no longer hold.
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Floors that match the config the repo actually uses.
- **Affected Files**: 2
- **Evidence**:
  1. **pytest-asyncio floor is too low.** `"pytest-asyncio>=0.17.0"`, but `pytest.ini` sets `asyncio_default_fixture_loop_scope = function` under `--strict-config`. That ini key exists only from pytest-asyncio 0.24, so any install between the floor and 0.24 fails collection with "Unknown config option". CI installs it unpinned (`backend-tests.yml:128`), so the floor is never exercised; `uv.lock` has 1.4.0.
  2. **websockets justification is false.** The comment says `websockets -> tests/integration/test_phase4_player_workflow.py`, but that file stopped importing `websockets` in `4efe00a0` (#5291, now in-process `TestClient`), and no file under `tests/` imports it. The dev dependency survives on a false justification; the package still arrives transitively via `uvicorn[standard]`.
  3. **pre-commit black drifted.** `.pre-commit-config.yaml` pins `psf/black` `rev: 26.5.1`, while `uv.lock` moved to black 26.10.1 today (Dependabot `d9d297b1`). The two formatters now differ by version. (`mirrors-mypy v2.3.0` matches `uv.lock`.)
- **Migration Path**:
  1. Raise the pytest-asyncio floor to `>=0.24` (or `>=1.0`, matching what is locked).
  2. Drop `websockets>=10.0` and its comment line, or re-justify it.
  3. Bump the pre-commit black rev to 26.10.1. Consider letting `pre-commit autoupdate` run alongside Dependabot.
- **Risk**: A contributor who installs the declared floors gets a collection error. The stale comment misleads future dependency pruning.

### DEP-07: Dead CRA-era `process.env.*` defines in the Vite and Vitest configs; `VITE_COMMIT_ID` is typed on `import.meta.env` but never set or read
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**:
  - `auralis-web/frontend/vite.config.mts:99-101`
  - `auralis-web/frontend/vitest.config.ts:140-141`
  - `auralis-web/frontend/src/vite-env.d.ts:4`
- **Status**: NEW. Related: #3485 (closed), which moved all browser reads to `import.meta.env`.
- **Deprecated API**: A `define`-injected `process.env.X` (the CRA/webpack convention). Vite exposes env through `import.meta.env`.
- **Deprecated Since**: n/a (Vite convention)
- **Removal Version**: n/a
- **Replacement**: Delete both defines. Mark `VITE_COMMIT_ID` optional, or delete it, since the commit id reaches the page through the `inject-commit-id` HTML plugin (`%VITE_COMMIT_ID%` in `index.html`), not through env.
- **Affected Files**: 3
- **Evidence**:
  - `grep -rn "process\.env" auralis-web/frontend/src` finds 1 hit, a Node `spawn` env in a test.
  - `grep -rn VITE_COMMIT_ID src` finds only the `.d.ts` declaration.
  - The `define` sets `'process.env.VITE_COMMIT_ID'`, and `vitest.config.ts` sets `'process.env.NODE_ENV': '"test"'`. Nothing reads either.
- **Migration Path**:
  1. Remove the two `define` entries.
  2. Drop or optionalize `readonly VITE_COMMIT_ID: string` in `vite-env.d.ts`.
  3. Run `pnpm run type-check` and `pnpm run build`.
- **Risk**: None functionally. The defines suggest an env contract that does not exist, and the non-optional `.d.ts` type claims a value that is always `undefined`.

### DEP-08: MUI v7+ `Grid` imported under the retired `Grid2` name in 7 files
- **Severity**: LOW
- **Dimension**: React/Redux/MUI
- **Location**: `import Grid2 from '@mui/material/Grid'` in:
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataDetailFields.tsx:5`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataExtendedFields.tsx:5`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataBasicFields.tsx:5`
  - `auralis-web/frontend/src/components/library/EditMetadataDialog/MetadataFormFields.tsx:12`
  - `auralis-web/frontend/src/components/shared/ui/loaders/LibraryGridSkeleton.tsx:2`
  - `auralis-web/frontend/src/components/library/Items/albums/AlbumGridLoadingState.tsx:8`
  - `auralis-web/frontend/src/components/library/Views/AlbumsTab.tsx:7`
- **Status**: NEW
- **Deprecated API**: The `Grid2` / `Unstable_Grid2` name, which MUI v7 promoted to `Grid` (the old Grid became `GridLegacy`). The code already uses the new API (`size={12}`); only the local alias is stale. The alias dates from the v7 upgrade, `e696db61` (#3487).
- **Deprecated Since**: MUI v7
- **Removal Version**: `Grid2` export removed in v7. The code is unaffected because it imports the default from `@mui/material/Grid`.
- **Replacement**: `import Grid from '@mui/material/Grid'`.
- **Affected Files**: 7
- **Evidence**: `<Grid2 size={12}>` in `MetadataBasicFields.tsx:21`.
- **Migration Path**: Rename the import and the JSX tags in the 7 files.
- **Risk**: Readability only. The name implies the v6 unstable component and invites a wrong "upgrade" to a removed API.

### DEP-09: Router coordinators keep `# noqa: F401` re-export blocks "so existing import paths keep working", but only tests import through them, and ~24 names have no importer at all
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - The first re-export block in each of `auralis-web/backend/routers/player.py:30`, `processing_api.py:29`, `enhancement.py:36`, `similarity.py:26`, `playlists.py:26`, `metadata.py:25`, `artwork.py:35`, `files.py:32`, `albums.py:28`, `library_scan.py:33`
  - `auralis-web/backend/cache/manager.py:41-62`
- **Status**: NEW. This is the router/cache sibling of #5775 (closed, `78a39d25`), which removed the same pattern from `chunked_processor`, `adaptive`, `unified_loader` and `stream_*` but did not cover `routers/` or `cache/manager.py`.
- **Deprecated API**: Compat re-exports left behind by the #5238 and #5831/#5832 router and cache splits.
- **Deprecated Since**: #5238, #5831, #5832
- **Removal Version**: n/a
- **Replacement**: Import from the defining `*_deps.py` / `*_models.py` / mixin modules.
- **Affected Files**: 11 production files, plus the tests that import through them
- **Evidence**: An AST sweep of importers (agent scratch `/tmp/audit/deprecation/reexp.py`) found:
  - 0 production importers through the coordinator paths.
  - About 58 names imported only by tests. Examples: `routers.player` `LoadTrackRequest`, `SeekRequest`, `_get_*_service`; `cache.manager` `CHUNK_DURATION`, `CachedChunk`, `TrackCacheStatus`.
  - About 24 names with no importer. Examples: player `AddTracksToQueueRequest`, `RepeatModeRequest`, `ShuffleRequest`, `_get_player_state_manager`; similarity `require_fitted`, `_unavailable`; metadata `_METADATA_FIELD_TO_COLUMN`; enhancement `_get_streamlined_cache`; playlists `MAX_PLAYLIST_DESCRIPTION`.
- **Migration Path**:
  1. Repoint the test imports and `monkeypatch` targets at the defining modules. Patch targets must move with the symbol, the same way #5775 handled it.
  2. Delete the re-export blocks, keeping only the names the coordinator itself uses.
- **Risk**: None at runtime. The blocks make every rename in a split look as if it has callers, and the patch-through-coordinator tests can silently patch a name the handler no longer reads.

### DEP-10: `ffmpeg_loader` and `unified_loader` pass through test-only names "so existing import paths keep working"
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:8-9,25,35`; `auralis/io/unified_loader.py` (names listed below)
- **Status**: NEW. Same family as #5775, which handled `unified_loader.check_ffmpeg` only.
- **Deprecated API**: Pass-through re-exports. In `ffmpeg_loader`: `_PROTOCOL_WHITELIST_ARGS`, `MINIMUM_FFMPEG_VERSION`, `_parse_ffmpeg_version`, `ffprobe_command`, `FFMPEG_TERMINATE_GRACE_S`, `FFMPEG_VERSION_CHECK_TIMEOUT_S`, `FFPROBE_TIMEOUT_S`, `SUBPROCESS_TEXT_KWARGS`, `_terminate_process`. In `unified_loader`: `_get_info_with_ffprobe`, `_get_info_with_soundfile`, `get_supported_formats`, `is_audio_file`, `load_reference`.
- **Deprecated Since**: The `ffmpeg_command` / `ffmpeg_probe` / `ffmpeg_process` split
- **Removal Version**: n/a
- **Replacement**: Import from `auralis/io/loaders/ffmpeg_probe.py` and `auralis/io/loaders/ffmpeg_process.py`.
- **Affected Files**: 2 production files; test importers include `test_ffmpeg_minimum_version_check.py:35,83`, `test_ffprobe_timeout_single_source_5798.py:46`, `test_ffmpeg_stderr_decoding_5555.py:20`, `test_ffmpeg_protocol_whitelist_5326.py:27`.
- **Evidence**: Each `ffmpeg_loader` name above occurs once in the file, on the import line, and has 0 production importers.
- **Migration Path**: Repoint the tests, then drop the pass-through names. `SUPPORTED_FORMATS` is used in-file; keep it.
- **Risk**: None at runtime. Same maintenance hazard as DEP-09.

### DEP-11: AudioPlayer's "backward-compatible" property and callback surfaces have no production consumer
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - `auralis/player/player_properties_mixin.py:5,51-117`: `current_file`, `current_track` (get and set), `reference_file`, `audio_data`, `reference_data`, `sample_rate`
  - `auralis/player/player_callbacks_mixin.py:43-100`: `add_callback`, `_notify_callbacks`, `get_playback_info`
- **Status**: NEW. Related: #5233 (closed with a docstring-only fix that itself says "Remaining callers are test-only … a dead-code deletion candidate in its own right"), and #4574, #3785, #5329, which keep re-hardening the locks of this surface.
- **Deprecated API**: The self-described "Backward-compatible property surface" (module docstring, line 5) and the AudioPlayer-level callback registration.
- **Deprecated Since**: #4249 (mixin extraction)
- **Removal Version**: n/a
- **Replacement**: The components themselves: `player.file_manager`, `player.integration`, `player.playback`.
- **Affected Files**: 2 production files; tests `tests/concurrency/test_player_property_setter_locks.py`, `test_player_property_getter_locks_3785.py`, `tests/auralis/player/test_properties_mixin_locked_reads_5329.py`, `test_player_lock_ordering.py`
- **Evidence**:
  - `grep -rnE "\b(audio_player|player|_player)\.(current_track|sample_rate|current_file)\b" auralis auralis-web/backend` returns only the mixin's own docstring.
  - `grep -rn "\.add_callback(\|\.get_playback_info(" auralis-web/backend` returns 0.
  - The only `add_callback` caller in `auralis/` is internal wiring (`integration_manager.py:104` → `self.playback`).
- **Migration Path**:
  1. Point the lock tests at the component objects.
  2. Delete the six properties and the three AudioPlayer-level callback methods.
  3. Keep the IntegrationManager/PlaybackController callback plumbing.
- **Risk**: None at runtime. Three lock-discipline fixes have already been spent maintaining code nothing reads.

### DEP-12: `useTracksQuery`, `useAlbumsQuery` and `useInfiniteScroll` have zero production callers; superseded by `useInfiniteAlbums`
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - `auralis-web/frontend/src/hooks/library/useLibraryQueries.ts:25,37,73`
  - Re-exports: `auralis-web/frontend/src/hooks/library/useLibraryQuery.ts:295-298` ("so existing imports keep working") and `auralis-web/frontend/src/hooks/library/index.ts:9`
- **Status**: NEW. Related: #5788 (closed; deduped `useAlbumsQuery` and deferred the rest to #5779, whose body does not list these hooks), #4422 (closed).
- **Deprecated API**: Hooks that `auralis-web/frontend/src/hooks/library/useInfiniteAlbums.ts:5` says it "Replaces".
- **Deprecated Since**: `useInfiniteAlbums` introduction
- **Removal Version**: n/a
- **Replacement**: `useInfiniteAlbums`. `useArtistsQuery` is live in `CozyArtistList.tsx` and stays.
- **Affected Files**: 3 production files and 2 test files (`useLibraryQuery.test.ts`, `useLibraryQueries.albums.test.ts`)
- **Evidence**: A non-test grep for `use(Tracks|Albums)Query\b|useInfiniteScroll\b` finds only definitions, JSDoc examples and the two re-exports.
- **Migration Path**: Delete the three hooks, their re-exports and their tests.
- **Risk**: None at runtime. Dead surface keeps showing up in hook audits (#4570 fixed a camelCase bug in it).
- **Cross-audit overlap**: `AUDIT_FRONTEND_2026-10-22.md` TS-09 (lists `useInfiniteScroll` as a zero-production-caller sibling) and API-03 (its suggested fix includes deleting `useAlbumsQuery` / `useTracksQuery`). Publish one issue, not two.

### DEP-13: Frontend tolerates wire shapes the backend never emits (legacy serializer fallbacks)
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - Bare `Playlist[]` list response ("legacy serializer"): `auralis-web/frontend/src/services/playlistService.ts:88-93,119-128` and `responseGuards.ts:150-155`
  - Generic `items` key: `responseGuards.ts:64-77` and `libraryQueryRequest.ts:97-104`
  - `/^HTTP (\d{3}):/` status regex fallback: `auralis-web/frontend/src/types/api.ts:48-58`
- **Status**: NEW. The Track singular-field fallbacks are Existing: #5823.
- **Deprecated API**: Compat parsing for response shapes from pre-envelope backends.
- **Deprecated Since**: The paginated-envelope and `pagination.py` conventions
- **Removal Version**: n/a
- **Replacement**: The actual shapes:
  - `PlaylistListResponse` `{playlists,total,limit,offset,has_more}` (`auralis-web/backend/routers/playlists_models.py:55`).
  - Domain-keyed envelopes. `auralis-web/backend/routers/pagination.py:21` says every router uses a domain key, "not a generic items field".
  - A `.status` field on errors (`httpError.ts:134`, `Object.assign`).
- **Affected Files**: 4 production files, plus the tests that feed the dead shapes (`apiErrorHandler.test.ts:49`, `useQueueMutations.*.test.ts`)
- **Evidence**: The comment at `playlistService.ts:88-90` reads "the bare-array shape is the legacy serializer the runtime tolerance (and the service's own tests) still accept". This is a single-client desktop app whose backend ships with it, so no older server exists to tolerate.
- **Migration Path**:
  1. Narrow the guards and the `TList` union to the real envelope.
  2. Remove the regex fallback.
  3. Delete the tests that construct the dead shapes.
- **Risk**: None at runtime. The unions weaken type narrowing and keep the dead shapes alive through their own tests.
- **Cross-audit overlap**: `AUDIT_FRONTEND_2026-10-22.md` API-03 mentions the "bare Playlist" fallback in `playlistService.createPlaylist` in passing; this finding covers the list-response, `items` and HTTP-regex fallbacks it does not.

### DEP-14: Twin library-stats fields `avg_dr_rating` / `avg_lufs` justified by a frontend reader that does not exist
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - `auralis/library/repositories/stats_repository.py:67-68`
  - `auralis-web/backend/routers/library_models.py:20-23,46-47` (lines 32-33 of the class)
  - `auralis-web/frontend/src/types/domain.ts:151-154`
- **Status**: NEW
- **Deprecated API**: Alias fields kept "because the frontend reads the former pair" (the `library_models.py` docstring).
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: The single pair `average_dr` / `average_lufs`.
- **Affected Files**: 3
- **Evidence**: The repository sets `stats['avg_dr_rating'] = stats['average_dr']` and `stats['avg_lufs'] = stats['average_lufs']`. In the frontend, `grep -rn "avg_dr_rating\|avg_lufs\|average_dr\|average_lufs" auralis-web/frontend/src` finds only the 4 type declarations in `domain.ts`; no component or hook reads either pair. (The ORM columns `Album.avg_dr_rating` / `LibraryStats.avg_*` are distinct and out of scope.)
- **Migration Path**:
  1. Drop the alias pair from the repository, the response model and the TS type.
  2. Fix the docstring.
  3. If neither pair is rendered, consider dropping both.
- **Risk**: None at runtime. The docstring's false claim blocks the cleanup.

### DEP-15: `FingerprintRepository` "thin delegators keep the contract": 3 of 4 have no production caller
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/repositories/fingerprint_repository.py:68-86`
- **Status**: NEW
- **Deprecated API**: The facade delegators `update_status`, `get_fingerprint_status` and `cleanup_incomplete_fingerprints`. They were kept after the stats split ("callers still hold the facade").
- **Deprecated Since**: The `fingerprint_stats` repository split
- **Removal Version**: n/a
- **Replacement**: The `FingerprintStatsRepository` methods, or nothing. `update_status` and `get_fingerprint_status` have no production caller in either class.
- **Affected Files**: 1 production file; tests `tests/integration/test_repositories.py` (pre-existing broken, #4234), `test_fingerprint_status_update.py`, `test_fingerprint_repository_db_path.py`
- **Evidence**: A production grep for `.update_status(`, `.get_fingerprint_status(` and `.cleanup_incomplete_fingerprints(` finds only the delegators themselves, plus `database.py:249`, which calls `self.fingerprint_stats.cleanup_incomplete_fingerprints()` directly and bypasses the facade. `get_fingerprint_stats` is live (`routers/fingerprint_status.py:64`, `fingerprint_queue.py:144,200`).
- **Migration Path**:
  1. Delete the three delegators.
  2. If `FingerprintStatsRepository.update_status` / `get_fingerprint_status` are still uncalled, delete them too.
  3. Repoint or delete the tests.
- **Risk**: None at runtime.

### DEP-16: Small compat leftovers: bare-arg `completeStreaming`, alias-layer `BorderRadius.styles.ts`, duplicate product version in `auralis/__version__.py`
- **Severity**: LOW
- **Dimension**: Internal
- **Location**:
  - `auralis-web/frontend/src/store/slices/playerStreamingReducers.ts:182-184`: a "Back-compat: accept a bare streamType" branch. The sole production caller, `useStreamMessageHandlers.ts:215`, passes the object form; the bare form is used only by `playerSlice.test.ts:234` and `playerStreamingReducers.test.ts:114`.
  - `auralis-web/frontend/src/components/library/Styles/BorderRadius.styles.ts`: 5 of 7 exports (`radiusSmall`, `radiusLarge`, `radiusXLarge`, `radiusFull`, `borderRadiusPresets`) have 0 consumers. This is the alias layer from #3599.
  - `auralis/__version__.py:3-10`: `__version__` / `__version_info__` are "retained for older importers". No module imports them; `auralis-web/backend/version.py:8` imports from `auralis.version`. They exist only to be kept in sync by `sync_version.py`, `scripts/validate_release_metadata.py` and `tests/regression/test_release_version_consistency.py`. The same file's `__db_schema_version__` and `FINGERPRINT_ALGORITHM_VERSION` are live.
- **Status**: NEW
- **Deprecated API**: Compat overloads, aliases and a second copy of the product version.
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: The object-form action; the design tokens; `auralis.version`.
- **Affected Files**: 3 production files, plus the tooling and tests listed
- **Evidence**: As listed per item. The `__version__` importer grep was re-run by the orchestrator and returned 0.
- **Migration Path**:
  1. Narrow `prepare` to the object form and update the 2 tests.
  2. Delete the 5 unused radius exports.
  3. Drop the two product constants from `auralis/__version__.py` and their sync/validation hooks.
- **Risk**: None at runtime. The version duplicate is a second source of truth that only tooling keeps honest.

---

## Dependency Upgrade Roadmap

| Order | Package | Current | Target | What breaks / notes |
|---|---|---|---|---|
| 1 | `@vitest/coverage-v8`, `@vitest/ui` | 4.1.7 | 4.1.11 (match `vitest`) | Nothing. Fixes DEP-01. Add a Dependabot `groups:` entry for `vitest` + `@vitest/*`. |
| 2 | `@xmldom/xmldom` (desktop, transitive) | 0.8.13 | Latest patched, via override | Nothing expected. Verify a macOS packaging run. DEP-02. |
| 3 | `criterion` (Rust dev) | 0.5.1 | Remove | Nothing; it is unused. DEP-03. |
| 4 | pre-commit `psf/black` rev | 26.5.1 | 26.10.1 | Same yearly stable style, so no reformat expected. DEP-06. |
| 5 | React 18.3 → 19 | 18.3.1 | 19.x | The next real major. The codebase is already clean of the APIs React 19 removes: no `defaultProps`, string refs, legacy context, `ReactDOM.render` or global `JSX`. `forwardRef` (16 uses) still works in 19 but becomes unnecessary. `@mui/material` 9 already allows `react@^19`. Blockers to check: `@hello-pangea/dnd` 18 and `react-infinite-scroll-component` 6.1.1 peer ranges (`>=16`). |
| 6 | TypeScript 5.9 → 6.x | 5.9.3 | 6.x | `tsconfig.json` already uses `moduleResolution: bundler`, `paths` without `baseUrl` (#5435) and an ES2020 target. Nothing deprecated in TS 6 is in use. |
| 7 | numpy | 2.4.6 | 2.5 | Held by the deliberate `<2.5` ceiling until numba supports numpy 2.5 (`pyproject.toml` comment). No NumPy-2.x-removed APIs are used. |
| 8 | pnpm | 10.20.0 | 11.x | Settings already live in `pnpm-workspace.yaml` (#5407). |

## Migration Effort Estimate

| Finding | Call sites / files | Effort |
|---|---|---|
| DEP-01 | 2 files | Small |
| DEP-02 | 1 override | Small |
| DEP-03 | 1 line + lockfile | Small |
| DEP-04 | 3 sites / 2 files | Small |
| DEP-05 | 4 sites / 1 file | Small |
| DEP-06 | 3 lines / 2 files | Small |
| DEP-07 | 3 lines / 3 files | Small |
| DEP-08 | 7 files | Small |
| DEP-09 | 11 modules, ~80 names, test patch targets | Medium |
| DEP-10 | 2 modules, ~14 names, ~5 test files | Small |
| DEP-11 | 9 members / 2 modules, 4 test files | Small |
| DEP-12 | 3 hooks, 2 tests | Small |
| DEP-13 | 4 files + tests | Small |
| DEP-14 | 3 files | Small |
| DEP-15 | 3 methods + tests | Small |
| DEP-16 | 3 files + tooling | Small |

## Dimension 7 coverage note (examined and dismissed)

These were checked and are live, or are deliberate keeps:

- `PreferenceVector.from_preset_name` fallback (live, `continuous_mode.py:269`)
- The AdaptiveMode and "legacy deficit-based EQ" paths (live fallbacks for hybrid/reference jobs and for an empty reference cloud)
- `AudioFingerprintAnalyzer.close` (#4744)
- `scan_stages.preview_folder` (#4973)
- `TrackCard` / `AlbumCard` wrappers (live; comment wording only)
- The chunked_processor `.duration` / `_get_wav_chunk_path` aliases (production callers)
- `CancelButtonForDialog` (live)
- `unified_loader` `FFMPEG_FORMATS` (live in `stream_normal.py`)
- The WebSocket context re-exports (production importers)
- Design-token semantic aliases (#4402)
- The `BufferScheduler` `ScriptProcessorNode` fallback (#4623 keep)
- `recording_type_detector.py` (#4873 keep)
- `desktop/resources/**` (gitignored staging)

No first-party `warnings.warn(..., DeprecationWarning)`, `@deprecated` tag, or deprecation/migration TODO exists anywhere in shipped code.

---

Publish with:
```
/audit-publish docs/audits/AUDIT_DEPRECATION_2026-10-22.md
```
