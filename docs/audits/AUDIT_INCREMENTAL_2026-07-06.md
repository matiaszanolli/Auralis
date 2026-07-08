# Incremental Audit — 2026-07-06

**Range**: `HEAD~30..HEAD` (30 commits, `1868e2c7` → `f2e36d5b`)
**Focus (override)**: tech debt introduced or left behind in this range — shortcuts, duplication, dead code, stale markers, magic numbers, stub implementations — not general bug-hunting.
**Dedup baseline**: `gh issue list --limit 200` → 141 open issues snapshotted to `/tmp/audit/issues.json` before analysis.

## 1. Change Summary

30 commits, 81 files changed (+1140/-1664 lines). Three themes dominate:

1. **Library refactor** — `0f0fb69c` extracted `BaseRepository` (session lifecycle) and migrated all 14 repositories under `auralis/library/repositories/` to inherit from it (#4017).
2. **Frontend cleanup batch** — component-size splits (`CacheStatsDashboard`, `ConnectionStatusIndicator` under 300 lines: #4186/#4187), a `<style>`-injection fix (#4188), and several small correctness/perf fixes (#4189, #4191, #4192, #4193).
3. **Test-hygiene batch** — un-skipping/un-xfailing tests (#4041–#4050), moving two non-test debug scripts out of the pytest suite, and a backend router fix unshadowing `pathlib.Path` in `artwork.py` (#4048/#4233) plus a stale version-fallback refresh in `health.py` (#4053).

The remainder of the range (roughly half the commits) is documentation-only (`CLAUDE.md`, `docs/**`, `.claude/commands/**`, `ARCHITECTURE.md`, `FIRST_TIME_SETUP.md`, `README.md`) — doc-sync work with no runtime surface; spot-checked for stale numbers/markers and found none introduced.

Changed-file domains:

| Domain | Files | Risk |
|---|---|---|
| Library/Repositories | 15 (`base.py` + 14 repos + `__init__.py`) | HIGH |
| Backend Routers | 2 (`artwork.py`, `health.py`) | HIGH |
| Frontend Components/Hooks/Store | 16 | LOW-MEDIUM |
| Tests | 12 | LOW |
| Docs/Config | ~36 | LOW |

## 2. High-Risk Changes

- `auralis/library/repositories/base.py` + all 14 repositories (session-lifecycle refactor) — reviewed in full; no broken `__init__`, no dead duplicated session boilerplate left behind, migration is complete and consistent across all 14 files.
- `auralis-web/backend/routers/artwork.py` — `pathlib.Path`/`fastapi.Path` unshadow (#4233) verified complete: all three `Path` uses at lines 82/86/91 now resolve to `pathlib.Path`, and the traversal check (`is_relative_to`) correctly runs before the existence check.

No sample-count, dtype, or DSP-invariant risk in this range — no files under `auralis/core/`, `auralis/dsp/`, `auralis/player/`, or `vendor/auralis-dsp/` were touched.

## 3. Findings

### INC-N-1: Tautological chunk-count assertion in un-skipped boundary test
- **Severity**: MEDIUM
- **Changed File**: `tests/backend/test_boundary_max_min_values.py:107-125` (`test_very_long_audio_chunk_count`) (commit: `b0943a43`)
- **Status**: NEW
- **Description**: #4044 removed the `@pytest.mark.skip` and replaced the old hardcoded `assert expected_chunks == 3600` (stale for the current 15s chunk model) with an assertion that recomputes the exact same expression it checks against — a no-op tautology. `ChunkedAudioProcessor` is imported but never instantiated or called, so the test never exercises the production chunk-count code path.
- **Evidence**:
  ```python
  from core.chunked_processor import (
      CHUNK_DURATION,
      ChunkedAudioProcessor,   # imported, never used
  )
  ...
  duration = 36000.0  # 10 hours
  expected_chunks = int(np.ceil(duration / CHUNK_DURATION))

  assert expected_chunks == int(np.ceil(36000.0 / CHUNK_DURATION)), (   # always true
      f"Chunk count must derive from CHUNK_DURATION={CHUNK_DURATION}; got {expected_chunks}"
  )
  assert expected_chunks == 2400, f"Expected 2400 chunks at 15s, calculated {expected_chunks}"
  ```
- **Impact**: False confidence — the test looks like it verifies chunk-count behavior for very long audio, but it only checks that `np.ceil` agrees with itself. It would not catch a regression of the exact class fixed in #4124 (off-by-one in chunk counting), because it never calls the canonical `content_chunk_count()` / `ChunkedAudioProcessor` API.
- **Suggested Fix**: Call the actual product function under test (e.g. `ChunkedAudioProcessor.calculate_total_chunks(duration)` or `content_chunk_count(duration, CHUNK_DURATION, ...)`) and assert its return equals 2400; drop the redundant self-referential assertion and the unused import.

### INC-N-2: Unused `fastapi.Path` import survives in 5 routers — same shadowing footgun just fixed in artwork.py
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/routers/artwork.py` (commit: `45e646b2`) — siblings not touched by this range
- **Status**: NEW
- **Description**: `45e646b2` fixed `artwork.py` by removing an unused `from fastapi import Path` that was shadowing `pathlib.Path` (#4233 — this had caused `Path.home()` to crash and disabled path-traversal protection). The identical unused `fastapi.Path` import is still present, unused, in 5 other routers — a latent re-introduction of the same bug class the moment any of them adds `from pathlib import Path`.
- **Evidence**: `grep -nE "\bPath\b"` (excluding the import line) returns nothing in any of:
  - `auralis-web/backend/routers/cache_streamlined.py:17`
  - `auralis-web/backend/routers/artists.py:15`
  - `auralis-web/backend/routers/metadata.py:22`
  - `auralis-web/backend/routers/playlists.py:26`
  - `auralis-web/backend/routers/similarity.py:17`
- **Impact**: Dead imports today; each is a silent-shadowing time bomb identical to #4233 if pathlib usage is ever added to these files without noticing the existing `fastapi.Path` import.
- **Siblings**: All 5 listed above — same finding, one fix pass.
- **Suggested Fix**: Drop `Path` from the `from fastapi import ...` line in all 5 files (none use FastAPI's `Path(...)` parameter helper).

### INC-N-3: Stale file-count in new `BaseRepository` docstring
- **Severity**: LOW
- **Changed File**: `auralis/library/repositories/base.py:9-10` (commit: `0f0fb69c`)
- **Status**: NEW
- **Description**: The new module docstring justifies centralizing session lifecycle by avoiding "a ~13-file sweep," but the refactor's own commit message says "all 14 repositories now inherit from it," and there are in fact 14 `*_repository.py` files. A minor internal inconsistency authored within the same commit.
- **Evidence**: docstring: `instead of a ~13-file sweep.` vs. actual repository count of 14.
- **Impact**: Cosmetic; no runtime effect, but a small piece of misleading documentation introduced in the very commit meant to be a cleanup.
- **Suggested Fix**: Correct to "~14-file sweep" (or say "per-repository sweep" to avoid the count needing future upkeep).

### INC-N-4: Redundant `void` lint-silencing in `useLibraryWithStats`
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:59` (commit: `42dfde83`)
- **Status**: NEW
- **Description**: #4193 destructures three abort refs with `_`-prefixed names to exclude them from the hook's public return spread, then additionally adds `void _fetchAbortRef; void _statsAbortRef; void _scanAbortRef;` to silence unused-variable warnings. TypeScript's `noUnusedLocals` already ignores `_`-prefixed identifiers (the sibling `CacheManagementPanel.tsx:28` relies on the same convention with no `void` needed), so the `void` line is unnecessary belt-and-suspenders left behind by the fix.
- **Evidence**: `const { fetchTracks, loadMore, fetchAbortRef: _fetchAbortRef, ...paginationState } = ...` followed by `void _fetchAbortRef; void _statsAbortRef; void _scanAbortRef;`
- **Impact**: Pure noise; inconsistent with the established `_`-prefix convention used elsewhere in the same directory.
- **Suggested Fix**: Delete the `void ...` statement.

### INC-N-5: Dead `refreshInterval` prop left on `CacheStatsDashboard` after the size-split
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/components/shared/CacheStatsDashboard.tsx:20-24, 34-36` (commit: `49321113`)
- **Status**: NEW
- **Description**: `#4187` rewrote `CacheStatsDashboard`'s props/signature as part of the under-300-lines split. `CacheStatsDashboardProps` still declares `refreshInterval?: number` (documented as "default 5000ms"), but the component only destructures `showTracks` — `refreshInterval` is never read; polling is owned internally by `useCacheStats`. No caller passes it, but the public prop still advertises control that silently does nothing.
- **Evidence**: `interface CacheStatsDashboardProps { refreshInterval?: number; ... }` vs. `export function CacheStatsDashboard({ showTracks = false }: CacheStatsDashboardProps)`.
- **Impact**: Misleading public API surface — a consumer setting `refreshInterval` would reasonably expect it to change poll cadence.
- **Suggested Fix**: Remove `refreshInterval` from the props interface, or wire it through to `useCacheStats`.

### INC-N-6: Hardcoded "every 5s" string drifts from the actual poll interval
- **Severity**: LOW
- **Changed File**: `auralis-web/frontend/src/components/shared/CacheStatsDashboard.tsx:267` (commit: `49321113`)
- **Status**: NEW
- **Description**: The footer hardcodes the literal string `Auto-refreshing every 5s`, while the sibling `CacheHealthMonitor.tsx:363` derives the equivalent label dynamically from its actual interval (`Auto-refreshing every {refreshInterval / 1000}s`). The magic `5s` here is untied to `useCacheStats`'s real internal interval, so it will silently go stale if that interval ever changes.
- **Evidence**: `Auto-refreshing every 5s` (string literal) vs. `CacheHealthMonitor`'s interpolated equivalent.
- **Impact**: Cosmetic drift risk; inconsistent pattern between the two near-identical cache dashboards.
- **Suggested Fix**: Source the interval value from `useCacheStats` (or a shared constant) and interpolate it, matching `CacheHealthMonitor`.

### Noted but not re-filed (already tracked / accepted state)
- `_session_scope()` context manager added in `base.py` has zero callers repo-wide (verified via `grep -rn "_session_scope"`). This is the documented, intentional deferred-migration state from #4017 (per project memory: ~110 existing manual session call sites were deliberately not migrated) — not new debt, not re-reported.
- `health.py`'s `ImportError` fallback (commit `1868e2c7`, #4053) is now back in sync with `auralis/version.py`, but remains a fully hand-duplicated 9-field literal that already drifted stale once and can drift again on the next version bump. The staleness itself was just fixed; the underlying duplication pattern is the residual debt. Tracked against #4053 rather than filed as a new issue.

## 4. Cross-Layer Impact

No contract breaks identified in this range:
- No REST/WebSocket schema changes.
- No frontend/backend API signature drift — the two backend router changes (`artwork.py`, `health.py`) are internal-logic fixes only, response shapes unchanged.
- No database schema/migration changes — the library-layer change is a pure internal refactor (session lifecycle), not a schema change; all 14 repositories' public methods are unchanged.

## 5. Missing Tests

- `test_boundary_max_min_values.py::test_very_long_audio_chunk_count` (INC-N-1) is nominally "un-skipped" but doesn't actually cover the code path it claims to — see finding above. This is the one genuine test-coverage gap surfaced in this range; all other un-skipped/un-xfailed tests in the batch (#4041–#4050) were verified to exercise real, current code paths.
- No test was added for the `CacheStatsDashboard` dead `refreshInterval` prop (INC-N-5) or the hardcoded interval string (INC-N-6) — low priority given LOW severity.
- Library refactor (#4017) has no new dedicated unit tests for `BaseRepository` itself, but all 14 repositories' existing test suites continued to pass through the refactor (inheritance-only change, no behavior change) — acceptable given the mechanical nature of the change.

## Summary

**6 NEW findings** (0 CRITICAL, 0 HIGH, 1 MEDIUM, 5 LOW). No cross-layer contract breaks. No DSP/audio-invariant risk (no engine files touched this range). Two additional items noted as already tracked/accepted (`_session_scope()` non-adoption under #4017, `health.py` fallback duplication under #4053) and not re-filed.

---
*Suggested next step*: `/audit-publish docs/audits/AUDIT_INCREMENTAL_2026-07-06.md`
