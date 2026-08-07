# Technical Debt Audit — Auralis — 2026-08-07

**Scope**: accumulated technical debt across the Python engine, FastAPI backend, React frontend, Rust DSP crate, test suite, and project documentation/audit tooling.
**Method**: 10 parallel dimension agents (max 3 concurrent), findings merged post-hoc. All 10 dimensions completed cleanly (no crashes).
**Repo HEAD at run time**: `90bebd2f` (140 commits ahead of the prior tech-debt audit's `09004fa2`, 2026-07-29 → 2026-08-07, 9 days).

---

## Methodology Note — This Run vs. the 2026-07-29 Audit

The last full tech-debt audit ran only 9 days before this one. Every dimension agent was explicitly instructed to read `AUDIT_TECH_DEBT_2026-07-29.md` in full, re-verify (not re-derive) its findings against the live tree, and report only **genuinely new** debt or **regressions**. This kept the run from re-spamming already-triaged findings and instead produced a useful signal: of the ~34 findings that report tracked, **2 were fixed and confirmed** in the 9-day window (WAVEncoderError doc claim via #4979, structural-count reconciliation via #4982 — though the latter has already partially re-drifted, see TD10 below), the rest remain open and correctly tracked, and **zero regressed**.

Consistent with the grep-inflation warning both this and the prior audit carry: every finding below is verified against a real call-site/evidence trail, not a raw grep count. Several strong-looking candidates were investigated and dropped because they turned out to be exact duplicates of already-open issues (`#4645`, `#4649`, `#4605`, `#4973`, `#4236`, `#4963`) — these are noted inline as dedup notes, not filed as new findings.

### Headline result: zero MEDIUM/HIGH/CRITICAL this run

Every one of this run's 32 new findings is LOW severity — none met a promotion trigger (no divergent-bugfix duplication currently live, no stub reachable from a shipped route, no skip guarding a closed CRITICAL/HIGH regression test, no audio-truncating magic constant). This is a different shape than 2026-07-29's 9 MEDIUM findings, and reflects that the highest-leverage items from that run (dead-code inventory, test-hygiene "tests that cannot fail") are already filed and being worked, not that the codebase suddenly has less debt — see "Deferred" below for what's still outstanding from that report.

### The most interesting structural finding: audit-tooling drift regenerates itself faster than it's fixed

Three consecutive tech-debt audits (07-25, 07-29, and this one) have now independently found the *exact same class* of debt: a structural count (test functions, test files, repository count) drifts, gets "fixed" by a dedicated issue, and re-drifts within about a week because the fix updates the number once but wires in no recurring enforcement. This run's TD10-1/TD10-2 are the third occurrence. `scripts/check_doc_counts.py` (added by #4982) is the right tool; it just isn't wired into anything that runs automatically. See the Top 10 Quick Wins — fixing the *enforcement gap* once is higher leverage than fixing the numbers a fourth time.

---

## Executive Summary

**32 new findings** (0 CRITICAL, 0 HIGH, 0 MEDIUM, 32 LOW) across 8 of 10 dimensions — Dimensions 1 (Stale Markers) and 5 (Stub Implementations) both independently returned **zero genuine findings**, each corroborating (not just repeating) the prior audit's identical conclusion via a fresh, independent sweep against 9 days of churn.

| Severity | Count | vs. 2026-07-29 |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 0 | -9 |
| LOW | 32 | +16 |
| **Total (new)** | **32** | +7 |

| Dimension | New findings | Notable re-verification result |
|---|---|---|
| 1 — Stale Markers | 0 | Re-confirms zero marker debt across 274 files touched since |
| 2 — Dead Code | 3 | TD2-8 (6 unused imports) fixed; TD2-1/2/3 unchanged |
| 3 — Logic Duplication | 2 | DSP `no_op()` family, stream/mastering families all still clean |
| 4 — Magic Numbers | 3 | Chunk-boundary bypass, upload limits, FFT sizes all still clean |
| 5 — Stub Implementations | 0 | Every candidate resolved to fixed code or an open tracked issue |
| 6 — Test Hygiene | 2 | TD6-2/TD6-3 (07-29) fixed; TD6-1 partially fixed (#4941 open remainder); TD6-5 still open (#4969) |
| 7 — Stale Documentation | 4 | 2 of 8 prior findings fixed (#4979, #4982); 6 still open, none regressed |
| 8 — Backwards-Compat Cruft | 6 | New dimension this run (07-29 had none) |
| 9 — File/Function Complexity | 10 | Most large files already tracked; 3 closed-issue regrowths investigated, confirmed not regressions |
| 10 — Audit-Finding Rot | 2 | Both are the count-drift pattern described above |

---

## Baseline Snapshot (captured at run start, for the next audit to diff against)

```
TODO/FIXME/HACK/XXX (py):    0
TODO/FIXME/HACK/XXX (ts):    0
NotImplementedError:         3   (all one intentionally-guarded path, #4241, closed)
type: ignore (py):           83
@ts-ignore/@ts-expect-error: 2
': any' / 'as any' (ts):     512
skipped tests (py):          61
skipped tests (ts):          2
py files >300 LOC:           108
ts/tsx files >300 LOC:       126
allow(dead_code) (rust):     0  (misleading zero — see TD2-9: rustc doesn't warn on unused `pub` items in a lib crate)
```

`auralis/version.py`: `1.5.1` (confirmed current; `pyproject.toml`/`README.md` agree; only `AGENTS.md` disagrees — see TD7-10).

---

## Top 10 Quick Wins (trivial/small effort, immediate payoff)

1. **TD10-1** — Fix the 6-location repo-count regression (14→13, following closed #4997), including a same-file self-contradiction inside `_audit-common.md` itself.
2. **TD10-2** — Re-run `scripts/check_doc_counts.py` and paste fresh numbers into `_audit-common.md:57` / `CLAUDE.md:151`; wire the script into `_audit-validate.sh` as a WARN check so this stops being a recurring finding.
3. **TD7-9** — Delete the 6 stale `auralis/core/config.py` references across 5 audit-skill files (file was deleted in #4918).
4. **TD2-10** — Delete 7 newly-stale `# type: ignore[attr-defined]` comments on `mutagen` imports (mutagen 1.47.0 now ships `py.typed`; mypy is already clean without them).
5. **TD8-1** — Delete `# removed (#NNNN)` breadcrumb comments regrown in 7 more files — the 4th recurrence of a pattern already fixed twice (#4088, #4293) and open again as #4649 for other files.
6. **TD8-2 / TD8-3 / TD8-4 / TD8-5** — Four independent dead-code deletions with zero callers each: `formatDuration` re-export (`types/domain.ts`), `announceFocus()` (`a11y/focusManagement.ts`), the unused `connection_manager` param on `create_files_router()`, and `VectorizedEnvelopeFollower.process()`.
7. **TD4-7** — Replace the hand-typed `#7366f0` fallback color at 2 sites with `tokens.colors.audioSemantic.identity` (the exact same value, already tokenized).
8. **TD4-5** — Promote `"auralis_uploads"`/`"auralis_chunks"`/`"auralis_processing"` temp-dir names to named constants (5 re-typed sites, one added the same day as this audit).
9. **TD3-6** — Extract `_ALBUM_DETAIL_OPTIONS`/`_ARTIST_DETAIL_OPTIONS` constants in `album_repository.py`/`artist_repository.py`, completing the consolidation closed issue #4236 proposed but never implemented.
10. **TD6-7** — File one issue covering the two performance tests sharing an identical, unreferenced `pytest.mark.skip` reason, and cite it from both.

## Top 5 Medium Investments (file/function splits, duplication consolidations)

1. **TD9-1** — `stream_normal.py`/`stream_enhanced.py`/`stream_seek.py` (~400 lines each, single-function). Do **not** attempt a mechanical split — extract the pure chunk-plan-calculation block first (safe, testable), then the per-chunk read/encode helper; leave the semaphore/cancellation skeleton in place since that's where the fix history lives.
2. **TD9-2** — `streamlined_worker.py`: extract the LRU processor-cache/lock bookkeeping (3 past bug references: #4521, #4369, #4737) into a standalone `ProcessorLRUCache`, separating it from tier-priority scheduling.
3. **TD3-5** — Collapse `AGENTS.md` into a thin pointer to `CLAUDE.md`, or generate it mechanically — the two files have drifted on version, toolchain flags, the entire CI-gates section, and schema version, exactly the "No-variants" pattern `CLAUDE.md`'s own header already flags but nothing has acted on.
4. **TD9-7** — `parameter_generator.py`: split `EQParameterGenerator`/`DynamicsParameterGenerator` out of `ContinuousParameterGenerator`, mirroring the DSP-execution side's existing 13-stage split.
5. **TD2-9** — Rust PyO3 crate: decide whether the one-shot-per-call binding design is intentional (likely) and delete ~9 unreachable stateful-instance methods (`reset`/`get_state`/`get_envelope`), or commit to `#[pyclass]`/`#[pymethods]` wrapping if streaming/stateful use across chunks is actually wanted.

---

## Findings

All 32 findings below are **LOW** severity (see Executive Summary — no promotions this run). Grouped by dimension.

### Dimension 2 — Dead Code & Unused Surface

#### TD2-9: Rust PyO3 crate — a whole class of stateful-instance methods (reset/get_state/get_envelope) plus 4 standalone functions are unreachable at the PyO3 boundary, with no `#[allow(dead_code)]` to mark them
- **Location**: `vendor/auralis-dsp/src/envelope.rs:108,113`; `biquad_filter.rs:140,195`; `compressor.rs:256,269`; `limiter.rs:247,255`; `chunk_processor.rs:141,147-193,196-217`; `onset_detector.rs:37`; `stereo_analysis.rs:5,162`
- **Status**: NEW · **Age**: pre-dates the 140-commit window (Dec 2025 crate build-out) · **Effort**: medium
- **Description**: `grep -rn "pyclass\|#\[pymethods\]" vendor/auralis-dsp/src/*.rs` → 0 hits — every `#[pyfunction]` wrapper constructs a fresh struct, uses it once, discards it. Because Python can never hold a live handle across calls, every `reset()`/`get_state()`/`get_envelope()`/`with_threshold()` method is structurally unreachable by binding design, not oversight — which is exactly why the baseline's `allow(dead_code)` grep found 0 hits and stopped: rustc doesn't warn on unused `pub` items in a *library* crate. `process_mono_chunks`/`ChunkStats` and `is_stereo`/`is_stereo_signals` are dead for the ordinary reason (never called outside `#[cfg(test)]`).
- **Impact**: ~9 methods/1 struct compiled into the shipped `.so` that can never run outside `cargo test`; a reader of `Compressor`'s public API would reasonably assume stateful streaming use is supported when the Python-facing contract is strictly one-shot.
- **Related**: Same "well-engineered, unreachable by design" shape as `AUDIT_TECH_DEBT_2026-07-29.md` TD2-3, one layer down at the Rust/PyO3 boundary.
- **Suggested Fix**: Either delete the dead instance-state methods (~120 LOC, no behavior change) if one-shot is intentional, or add `#[pyclass]`/`#[pymethods]` wrapping if persistent per-track instances are actually wanted (a real design change).

#### TD2-10: 7 newly-stale `# type: ignore[attr-defined]` comments on `mutagen` imports — mutagen now ships `py.typed`
- **Location**: `auralis/library/artwork.py:15`, `scanner/metadata_extractor.py:15`, `metadata_editor/metadata_editor.py:15`, `metadata_editor/__init__.py:16`, `metadata_editor/writers.py:16`, `auralis-web/backend/core/mastering_target_service.py:31`, `routers/tracks.py:161`
- **Status**: NEW · **Age**: oldest `b6ed4d0f5` 2025-12-08, newest `57342a06` 2026-06-01 (drift accumulated over ~8 months) · **Effort**: trivial
- **Description**: Installed `mutagen` 1.47.0 ships a `py.typed` marker, so mypy now type-checks against its inline stubs instead of falling back to `Any` — the `attr-defined` errors these 7 comments silence no longer occur. `mypy --warn-unused-ignores --ignore-missing-imports` confirms all 7 as `[unused-ignore]`.
- **Related**: Existing #4397 for an 8th, unrelated stale-ignore hit (`mastering_profile.py:26`, `yaml`) surfaced by the same mypy run — not re-filed.
- **Suggested Fix**: Delete all 7; mypy is already clean without them (verified).

#### TD2-11: `responseGuards.ts` — 4 of 9 declared runtime shape guards are never wired to a real `apiRequest` call (#4607's rollout is incomplete)
- **Location**: `auralis-web/frontend/src/api/responseGuards.ts:69,72,75,153` (`isTracksListShape`, `isAlbumsListShape`, `isArtistsListShape`, `isPlayerStatusShape`)
- **Status**: NEW · **Age**: `09141166` 2026-07-25 (4 days before the prior audit — a genuine miss, not a regression) · **Effort**: small
- **Description**: 5 of 9 guards are genuinely wired (playlists, settings, queue, artist-tracks). `isAlbumsListShape`/`isArtistsListShape`/`isPlayerStatusShape` have zero references anywhere, including tests. `useRestAPI.ts`'s own module docstring shows `isPlayerStatusShape` as its worked example — the real `/api/player/status` fetch never uses it.
- **Impact**: Three of the app's higher-traffic reads (albums, artists, player status) get none of the boundary protection the file's docstring implies they already have.
- **Suggested Fix**: Wire `validate: isAlbumsListShape`/`isArtistsListShape`/`isPlayerStatusShape` into their corresponding fetch calls (mechanical, pattern already established at 5 live call sites), or delete if genuinely unneeded.

---

### Dimension 3 — Logic Duplication

#### TD3-5: `CLAUDE.md` and `AGENTS.md` are two hand-maintained copies of the same project brief, already drifted in 4+ places
- **Location**: `/CLAUDE.md` (241 lines) vs `/AGENTS.md` (162 lines)
- **Status**: NEW · **Age**: not edited together in at least 4 days · **Effort**: small
- **Description**: `CLAUDE.md`'s own header already flags this; a direct diff confirms it's worse than stated: version (1.5.1 vs stale 1.5.0), run commands (missing the `--python-preference only-managed` toolchain fix), the entire ~34-line CI-gates/ratchet-baseline section is absent from `AGENTS.md`, and the codebase map shows `LibraryManager` as current (no DEPRECATED annotation) and schema v16 (live is v17).
- **Impact**: Any agent tooling that loads `AGENTS.md` instead of `CLAUDE.md` gets stale version/toolchain/schema guidance and no CI-ratchet explanation.
- **Suggested Fix**: Collapse `AGENTS.md` into a thin pointer to `CLAUDE.md`, or generate it mechanically from `CLAUDE.md` so there is one source of truth.

#### TD3-6: `AlbumRepository`/`ArtistRepository` still inline-duplicate eager-load `.options(...)` tuples, unlike siblings that already extracted the identical pattern
- **Location**: `album_repository.py:63,81`; `artist_repository.py:29-31,50-52,122-123,169-170` — vs. the established pattern at `genre_repository.py:27` (`_GENRE_LOAD_OPTIONS`) and `track_repository.py:36-37` (`_track_eager_options()`)
- **Status**: NEW (related to CLOSED #4236) · **Age**: `44cd4a99` 2026-02-21 / `aaf9d02c` 2026-03-25 · **Effort**: small
- **Description**: Closed #4236 fixed a real `DetachedInstanceError` in this exact pair of files and its own "Proposed Fix" text explicitly recommended extracting named eager-load constants — the crash-fix half was done, the consolidation half never was. Both pairs are currently consistent (not a live bug), but this is precisely the shape that produced #4236 in the first place, and violates the project's own documented "Detached ORM instances" invariant (define the option tuple once at module scope).
- **Suggested Fix**: Add `_ALBUM_DETAIL_OPTIONS`/`_ARTIST_DETAIL_OPTIONS`/`_ARTIST_LIST_OPTIONS` module constants, mirroring `track_repository.py`'s naming convention.

**Dedup note (not filed)**: `errors.py` typed-exception adoption (96 raw `HTTPException(500/503/400)` sites across 10 router files) is the same root debt open issue #4605 already tracks via the decorator angle — recorded as a refinement for whoever picks that up, not filed separately.

---

### Dimension 4 — Magic Numbers & Hardcoded Constants

#### TD4-5: Temp-directory names `"auralis_uploads"`/`"auralis_chunks"` re-typed as bare string literals at 5 call sites
- **Location**: `routers/processing_api.py:296`, `core/processing_engine.py:808`, `config/startup.py:654,347`, `core/chunked_processor.py:183`
- **Status**: NEW · **Age**: oldest `4077d5fe7` 2025-10-22; newest `a6751a3bf` 2026-08-06 (`#4762`, added a 3rd `auralis_uploads` site the same day as this audit) · **Effort**: trivial
- **Description**: Same "duplicate-instead-of-import" shape as the prior audit's TD4-1 (chunk-geometry constants), for directory-name strings. `#4762` landed literally the same day this audit ran, adding a 3rd independent literal.
- **Suggested Fix**: Add `UPLOAD_TEMP_DIRNAME`/`CHUNK_TEMP_DIRNAME`/`PROCESSING_TEMP_DIRNAME` constants to `config/limits.py` (which already centralizes the sibling upload-size constants) and import at all 6 sites.

#### TD4-6: `DynamicsSettings`/`CompressorSettings`/`LimiterSettings.__post_init__` clamp fields to bare inline bounds, with 2 exact-duplicate bound pairs
- **Location**: `auralis/dsp/dynamics/settings.py:36-42,54-57,86-91`
- **Status**: NEW · **Age**: `ae9f81bf5` 2026-02-22 (Compressor/Limiter) / `69417126` 2026-08-03 (Dynamics, added after the prior audit) · **Effort**: small
- **Description**: `ratio`'s `(1.0, 100.0)` clamp is byte-for-byte duplicated by `gate_ratio`, added 5+ months later with no cross-reference; `lookahead_ms`'s `(0.0, 50.0)` appears identically twice in the same file.
- **Suggested Fix**: Promote the 2 duplicated bound pairs to module-level named constants shared by all 3 dataclasses.

#### TD4-7: Fallback accent color `#7366f0` hand-typed twice instead of importing `tokens.colors.audioSemantic.identity`
- **Location**: `utils/colorExtraction.ts:287`, `hooks/app/useArtworkPalette.ts:143` — vs. `design-system/tokens/colors.ts:70` (`identity: '#7366F0'`)
- **Status**: NEW · **Age**: `useArtworkPalette.ts` touched `3f25c0c5` 2026-08-03 (after the prior audit) · **Effort**: trivial
- **Description**: Distinct from the frontend audit's D5-01 (which token *accessor* — this is a literal that bypasses the token system entirely). Both are low-traffic fallback paths (artwork-extraction failure) — exactly where a future rebrand is least likely to be tested and most likely to silently miss.
- **Related**: Overlaps `/audit-frontend` Dimension 5 scope — reported here per instructions for merge-time dedup.
- **Suggested Fix**: `import { tokens } from '@/design-system'` and use `tokens.colors.audioSemantic.identity` at both sites.

---

### Dimension 6 — Test Hygiene

#### TD6-6: `except Exception: pass` silently swallows the real assertion in ~60+ test bodies across ~20 files — a broader, less visible sibling of the tracked `pytest.skip` variant (#4969)
- **Location**: Worst offender `tests/auralis/player/test_enhanced_player_detailed.py` (24 sites); ~19 other files across `tests/backend/`, `tests/boundaries/`, `tests/concurrency/`, `tests/stress/`, `tests/auralis/` — full list in dimension detail
- **Status**: NEW (distinct mechanism from #4969/07-29's TD6-5 — that pattern is `except Exception: pytest.skip(...)`, which at least shows as SKIPPED; this is a bare `pass`, which reports as an ordinary PASS)
- **Effort**: large (>1 day) systemically; small for the worst single file
- **Description**: Identical false-confidence mechanism to #4969, but *less visible* — no SKIPPED marker, no reason string, no test-count deviation. `tests/backend/test_boundary_data_integrity.py:390-399` shows the mechanism actively undermining a real prior fix: closed #4257 upgraded a smoke check to a real value assertion, but the whole block is still wrapped in `except Exception: pass`, so an unrelated crash would silently discard #4257's actual regression check.
- **Suggested Fix**: Replace bare `except Exception` with the specific tolerated exception type(s), or `pytest.raises(...)`/`xfail(strict=False)`. Consider fixing alongside #4969 since they share root cause and remedy.

#### TD6-7: Two performance test files carry an identical, unreferenced `pytest.mark.skip` reason with no tracking issue
- **Location**: `tests/performance/test_memory_profiling.py:307`, `tests/performance/test_audio_processing_performance.py:708`
- **Status**: NEW · **Effort**: small
- **Description**: Both carry the byte-for-byte identical reason `"Memory measurement unreliable - needs redesign to measure growth over iterations"` — unlike every other skip in the 61-site project sweep, which cites a specific issue or a self-evidently permanent environment condition.
- **Suggested Fix**: File one issue for both (same fix: multi-iteration growth-delta measurement instead of single before/after snapshot); cite it from both `reason=` strings.

**Re-verification of 2026-07-29's Dimension 6**: TD6-2 (#4947) and TD6-3 (#4789) confirmed CLOSED and fixed. TD6-1 partially fixed — 3 of 8 tests repaired (#4780, closed), the 5 sibling `test_stream_disconnect_toctou.py` tests still crash on the removed `active_streams` attribute, tracked as **#4941 (OPEN)**, not re-filed. TD6-5 (13 `except: pytest.skip` sites) confirmed still open and unfixed as **#4969**.

---

### Dimension 7 — Stale Documentation & Comments

#### TD7-9: Six stale `` `auralis/core/config.py` `` references to a file deleted in #4918
- **Location**: `.claude/commands/audit-engine.md:26,79`, `audit-integration.md:66`, `audit-tech-debt.md:151`, `_audit-severity.md:61`, `.claude/agents/dsp-specialist.md:21`
- **Status**: NEW · **Effort**: trivial
- **Description**: All 6 are phrased as active investigative prompts ("check both", "a value defined in both is itself a finding") sending a future audit run hunting for a config-duality bug against a module deleted specifically because it was unreachable dead code. Per the Path-Reference Convention, a reference to a deleted file must not use backticks.
- **Suggested Fix**: Delete the `auralis/core/config.py` clause in each location; the surrounding sentence already correctly describes the current `auralis/core/config/` package.

#### TD7-10: `AGENTS.md` is comprehensively stale across version, architecture, and command-safety fields
- **Location**: `AGENTS.md:4,12,22-23,45-46,65,71,75-76,84,104,106,113`
- **Status**: NEW · **Effort**: small
- **Description**: See TD3-5 above for the duplication framing — this is the same underlying drift, catalogued field-by-field: version (1.5.0 vs live 1.5.1), `LibraryManager` presented as current/constructed-at-startup (post-#4619 it's `LibraryDatabase`), schema v16 vs live v17, router count 19 vs live 20, test counts ~5,400/391 files/21 dirs vs live 5,923/494/19, and — the one genuine hazard — a documented test command (`python -m pytest tests/ -v`) with no `--ignore` flags that **will hang** on the same two files `CLAUDE.md`'s troubleshooting table explicitly warns about.
- **Suggested Fix**: Same as TD3-5.

#### TD7-11: `docs/subsystems/backend-api.md` still describes `LibraryManager` as the component built at startup — post-#4619 it's `LibraryDatabase`
- **Location**: `docs/subsystems/backend-api.md:41-43,56-58`
- **Status**: NEW · **Age**: doc last touched `1ace03d4` 2026-07-25, same day #4619 was filed; the doc's most recent edit didn't pick up the change · **Effort**: trivial
- **Description**: One of the 11 docs the path-reference gate actively validates — but the gate only checks that backticked *paths* exist, not that prose describing *behavior* is accurate, so nothing catches this class of drift. `config/startup.py:376-383`'s own comment confirms: `globals_dict['library_manager'] = LibraryDatabase()`.
- **Suggested Fix**: Replace both `LibraryManager` mentions with `LibraryDatabase`; optionally note the dict key is still spelled `library_manager` for historical reasons.

#### TD7-12: `CLAUDE.md` states two different test-function counts in the same file (~5,600 vs ~5,700), and both now trail the live count
- **Location**: `CLAUDE.md:26` vs `CLAUDE.md:151`
- **Status**: NEW · **Effort**: trivial
- **Description**: `scripts/check_doc_counts.py` (added by #4982, the fix that reconciled these files a week ago) now reports 5,923 functions / 494 files — both in-file numbers already trail live, and the file self-contradicts even immediately after that reconciliation (line 26 was never touched by #4982's fix, only line 151 was).
- **Related**: Same underlying gap as TD10-2 — see that finding for the "fix doesn't wire in enforcement" root cause.
- **Suggested Fix**: Update line 26 to match line 151 (or replace both with non-numeric phrasing), then re-run `check_doc_counts.py`.

**Re-verification of 2026-07-29's Dimension 7 (TD7-1 through TD7-8, that report's own numbering)**: 2 of 8 fixed and confirmed (#4979 WAVEncoderError claim, #4982 count reconciliation — though #4982 has already partially re-drifted, see TD7-12/TD10-2). 6 remain open, already tracked (#4974, #4984, #4987, #4988, #4990, #4991), zero regressed.

---

### Dimension 8 — Backwards-Compat Cruft & "No Variants" Violations

*(New dimension this run — the 2026-07-29 audit had no Dimension 8.)*

#### TD8-1: `# removed (#NNNN)` breadcrumb comments regrown in 7 more files — 4th recurrence of a pattern fixed twice already
- **Location**: `routers/enhancement.py:608-613`, `routers/library.py:87-91`, `optimization/performance_optimizer.py:171-173`, `services/playback_service.py:300-307`, `library/manager.py:118-121`, `library/repositories/track_repository.py:365-367`, `hooks/enhancement/index.ts:17-21`
- **Status**: NEW (same pattern as OPEN #4649, different files) · **Effort**: trivial
- **Description**: 4th occurrence of this exact shape — fixed in #4088 (10 instances), regrown and fixed in #4293, regrown again and open as #4649 (4 files), now found in 7 more files #4649 doesn't cover. `routers/enhancement.py`/`library.py` are pre-existing files both prior sweeps missed entirely (not regrowth).
- **Suggested Fix**: Delete all listed comments (reasoning already permanent in `git log`/the cited issues); consider a CI grep gate for `removed (#\d+)` so this stops recurring.

#### TD8-2: `formatDuration` re-exported from `types/domain.ts` "for backwards compatibility" has zero consumers
- **Location**: `types/domain.ts:404-405`
- **Status**: NEW (4th instance of the shape OPEN #4645 tracks 3 of) · **Effort**: trivial
- **Suggested Fix**: Delete the re-export; fold into #4645's fix PR.

#### TD8-3: `announceFocus(_element, message)` — unused param renamed instead of deleted, function itself has zero callers
- **Location**: `a11y/focusManagement.ts:377-391`
- **Status**: NEW · **Effort**: trivial
- **Suggested Fix**: Delete the function entirely, or wire it up and drop the unused parameter.

#### TD8-4: `create_files_router(connection_manager=...)` accepts and is actively passed a live `ConnectionManager`, but never references it
- **Location**: `routers/files.py:85-98`, called from `config/routes.py:124-127`
- **Status**: NEW · **Effort**: trivial
- **Description**: Unlike a typical dead default, the real `manager` singleton is constructed and threaded through at the call site purely to satisfy the signature — misleading for anyone auditing "what routers can broadcast over WebSocket."
- **Suggested Fix**: Drop the parameter and its call-site argument, or wire it up if upload/scan broadcast events are actually wanted.

#### TD8-5: `VectorizedEnvelopeFollower.process()` is self-labeled "for backward compatibility" with zero callers
- **Location**: `auralis/dsp/dynamics/vectorized_envelope.py:45-51`
- **Status**: NEW · **Effort**: trivial
- **Description**: Both real callers (`limiter.py`, `compressor.py`) use `process_buffer()`. The sibling fallback `EnvelopeFollower.process()` in `envelope.py` genuinely is live (its own `process_buffer()` calls it internally) — correctly not flagged.
- **Suggested Fix**: Delete `VectorizedEnvelopeFollower.process()`.

#### TD8-6: `useAdvancedScrollAnimation`/`useStaggerAnimation` — a dead "Advanced"-variant pair sitting alongside a base hook, with zero production consumers for all three
- **Location**: `hooks/shared/useScrollAnimation.ts:120-168,180-206`
- **Status**: NEW · **Effort**: small
- **Description**: A textbook base+"Advanced"-variant shape, except unlike a legitimate domain name (e.g. `EnhancedAudioPlayer`, the one live player), none of the three hooks — including the base — has a single production import; only their own test file uses them.
- **Suggested Fix**: Delete all three (+ test file) if scroll-triggered fade-in isn't on the roadmap, or wire the base hook into a real view and delete the two variants per No-Variants.

**Dedup notes (not filed)**: `getShortcutString`/`auralisTheme` (Existing #4645), `QueueHistoryRepository.undo(queue_repository=)`/`create_psychoacoustic_eq()` (Existing #4973), `hooks/player/index.ts` breadcrumb block (Existing #4649).

---

### Dimension 9 — File / Function / Module Complexity

Re-scan matches the baseline exactly (108 Python / 126 TS/TSX files >300 lines — no drift). Most of the largest offenders are already tracked; 3 closed issues (#4248, #4250, #4260) whose target files have regrown past their closure size were investigated in depth — in all three cases the structural fix is still intact and the regrowth is ordinary feature accretion, not a reverted fix (full skip-table in dimension detail). 10 genuinely untracked findings follow, each with a concrete split axis.

#### TD9-1: `stream_normal.py`/`stream_enhanced.py`/`stream_seek.py` — three ~400-line single-function WebSocket streaming handlers
- **Location**: `core/stream_normal.py:36-446` (411-line function), `stream_enhanced.py:38-407`, `stream_seek.py:41-395`
- **Effort**: large · See Top 5 Medium Investments for the extraction plan.

#### TD9-2: `streamlined_worker.py` — LRU-cache/lock bookkeeping intermixed with tier-priority scheduling
- **Location**: `core/streamlined_worker.py:1-610`
- **Effort**: medium · See Top 5 Medium Investments.

#### TD9-3: `library/models/core.py` — 7 ORM entity classes in one module, the one holdout in an otherwise per-domain-split package
- **Location**: `auralis/library/models/core.py:83-587` (`Track`, `Album`, `Artist`, `Genre`, `Playlist`, `QueueState`, `QueueHistory`)
- **Effort**: medium
- **Suggested Fix**: Split along the package's existing convention: `track.py`, `album.py`, `artist_genre.py` (paired — always upserted together), `playlist.py`, `queue.py` (`QueueState`+`QueueHistory`, same lifecycle); re-export all from `models/__init__.py`.

#### TD9-4: `metrics_collector.py` — `MetricsCollector` and `HealthChecker` are two unrelated classes sharing a file
- **Location**: `monitoring/metrics_collector.py:21-575`
- **Effort**: small
- **Suggested Fix**: Move `HealthChecker` to `health_checker.py`; zero cross-references between the two classes confirmed.

#### TD9-5: `normalization.py` — 11-method `MetricUtils` mixing simple range ops with statistical/robust-scaling ops
- **Location**: `analysis/fingerprint/metrics/normalization.py:19-526`
- **Effort**: small · Oldest untracked offender found (`2ff696c9` 2026-02-13, sat >300 lines ~6 months with no split issue).
- **Suggested Fix**: Split into `normalization_basic.py` and `normalization_robust.py`, keeping `MetricUtils` as a thin re-exporting facade.

#### TD9-6: `services/fingerprint_queue.py` — worker-loop/dynamic-scaling/progress-reporting in one 415-line class
- **Location**: `auralis/services/fingerprint_queue.py:39-517`
- **Effort**: medium
- **Suggested Fix**: Move `FingerprintQueueManager` to its own file (low-risk); extract dynamic-rescaling callbacks into a `_DynamicWorkerScaler` helper mirroring the existing `ResizableSemaphore` pattern.

#### TD9-7: `parameter_generator.py` — one class generating EQ, dynamics, and loudness/stereo parameters
- **Location**: `core/processing/parameter_generator.py:36-509`
- **Effort**: medium · See Top 5 Medium Investments.

#### TD9-8: `useAudioStreamingCore.ts` — 144-line `handleChunk` callback (the largest frontend callback found) plus inline watchdog-timer logic
- **Location**: `hooks/enhancement/useAudioStreamingCore.ts:135-574`
- **Effort**: medium
- **Description**: `handleChunk` runs on every WebSocket audio-chunk message during playback — the hottest path in the hook.
- **Suggested Fix**: Extract the watchdog timer into `useStreamStartWatchdog(onTimeout)`; extract `handleChunk`'s decode/append logic into a standalone non-hook function, independently unit-testable without mounting React.

#### TD9-9: `playerSlice.ts` — 369-line reducers block mixing flat player state with nested streaming sub-state, plus 2 misplaced queue-sync thunks
- **Location**: `store/slices/playerSlice.ts:83-455`
- **Effort**: medium
- **Suggested Fix**: Move the 2 `...SyncQueue` thunks to `playerQueueSync.ts`; define streaming-substate reducers in a separate module and spread them into `reducers:` (RTK supports externally-defined reducer functions — splits the file without splitting the slice).

#### TD9-10: `useLibraryQuery.ts` — pure request/response-shaping functions embedded inside the hook body
- **Location**: `hooks/library/useLibraryQuery.ts:171-557`
- **Effort**: small
- **Description**: `extractItemsFromResponse`/`buildEndpoint` are pure functions of their arguments but currently require `renderHook` to test — plausibly why closed #4963 found this hook's tests only validate the mock rather than real pagination logic.
- **Suggested Fix**: Move both to `libraryQueryRequest.ts` as plain exported functions, enabling direct unit tests.

---

### Dimension 10 — Audit-Finding Rot

#### TD10-1: `13`→`14` repository-count regression across 6 locations in 3 skill files, including a same-file self-contradiction inside `_audit-common.md`
- **Location**: `_audit-common.md:148,174`, `audit-engine.md:32`, `audit-tech-debt.md:139`, `.claude/agents/library-specialist.md:9,68`
- **Status**: NEW (regression triggered by closed #4997, itself a fix for a 2026-07-29 finding) · **Age**: `22a6dcf3` 2026-07-30 · **Effort**: trivial
- **Description**: #4997 deleted the 14th repository (`QueueTemplateRepository`), dropping the live count to 13. `_audit-common.md`'s own top-of-file table was updated (line 20: "13 repos") but two other tables in the **same file** were not (lines 148, 174: "14 repositories"/"14 repos") — plus 4 more locations in 2 other files.
- **Suggested Fix**: Update all 6 to "13"; extend `check_doc_counts.py` to also recompute the repository count and check `.claude/agents/*.md` too, not just the two files #4982 targeted.

#### TD10-2: `_audit-common.md`'s test-function/test-file count has already drifted again, one week after #4982 "fixed" the same drift
- **Location**: `_audit-common.md:57`
- **Status**: NEW (3rd occurrence of this exact class across 3 consecutive tech-debt audits) · **Age**: last edited `38ebd98e` 2026-07-30 (#4982's fix), drifted again within ~1 week · **Effort**: trivial
- **Description**: Reads "~5,700 test functions (462 files)"; live is 494 files / 5,923 functions. The `docs/` topic-dir count and `analysis/` file count in the same table are still accurate — only the two fastest-moving numbers (which change on every test-adding commit) have gone stale.
- **Impact**: `check_doc_counts.py` exists and works but nothing calls it on a cadence — it prevents `CLAUDE.md`⇄`_audit-common.md` *cross-file* divergence (both still agree with each other) but not *tree* divergence.
- **Suggested Fix**: Refresh both files now, then wire the script into `_audit-validate.sh` as a WARN-level check so a doc edit gets a nudge when the numbers are stale beyond a threshold, without requiring a human to remember.

**Checked, found clean**: all 8 unique `#NNNN` callouts across skill/agent files are historical "fixed-by" citations, not stale "current state" claims. No audit report is old enough (>90 days) to trigger the untriaged-CRITICAL/HIGH check. All 7 audit skills' self-referential dimension/category counts match their live heading counts. Router count (20) and the WAVEncoderError doc claim are both re-verified accurate.

---

## Deferred

Findings gated on in-progress or larger work, carried forward from `AUDIT_TECH_DEBT_2026-07-29.md` (not re-derived this run, still open):

- **TD2-3 (07-29)** — ~4,800 LOC of engine processing code (13-stage `stages/` pipeline, `optimization/parallel/`, `AdaptiveLimiter` chain, `RecordingTypeDetector`) unreachable from the shipped app. This run's TD2-9 independently corroborates the same shape one layer down (Rust/PyO3). Still a "decide, then wire up or delete" architectural call, not a mechanical fix.
- **#4969 (TD6-5, 07-29)** — 13 sites converting real crashes into silent `pytest.skip`. This run's TD6-6 found a much larger sibling class (`except: pass`, ~60 sites) — recommend fixing both in the same pass given shared root cause.
- **#4974, #4984, #4987, #4988, #4990, #4991 (TD7-1,4-8, 07-29)** — 6 still-open stale-documentation issues, all re-verified unregressed this run.
- **#4605** — typed-exception-class adoption gap in `routers/errors.py` (96 raw `HTTPException` sites); this run's Dimension 3 dedup note refines the remaining scope (12 files that adopted `NotFoundError` but not the other 3 error classes).
- **#4649, #4645, #4973** — backwards-compat cruft issues this run found 4 additional untracked siblings for (TD8-1, TD8-2, dedup notes) — worth batching into the same fix PRs rather than filing as new issues.
- **#4266, #4671, #4456** — open god-file-split tracking issues (`hybrid_processor.py`, `startup.py`'s 439-line `lifespan()`, 4 oversized frontend components) — unaffected by this run, no new evidence either way.

---

## Report Provenance Note (finding-ID cross-reference)

Two dimensions in this report reused ID numbers from *different* prior audit reports for *different* findings. To avoid ambiguity when cross-referencing:
- **Dimension 7**: this report's TD7-9 through TD7-12 were generated by the dimension agent as "TD7-1" through "TD7-4" (correctly scoped to *this* run) — renumbered here to continue after `AUDIT_TECH_DEBT_2026-07-29.md`'s TD7-1 through TD7-8, which are a **different set of findings** and remain that report's authoritative numbering.
- **Dimension 10**: this report's TD10-1/TD10-2 were independently generated by both this report's agent and the (older, separate) `AUDIT_TECH_DEBT_2026-07-25.md` report. `docs/audits/AUDIT_TECH_DEBT_2026-07-25.md`'s TD10-1/TD10-2 are a **different set of findings** (07-25's TD10-2 is tracked as #4687, unrelated to this report's TD10-2).
- **Dimension 6**: the dimension agent used "TD6b-1"/"TD6b-2" internally to sidestep collision with `AUDIT_TECH_DEBT_2026-07-29.md`'s TD6-1 through TD6-5; renumbered here as TD6-6/TD6-7 for readability, continuing that report's sequence.

No other dimension's numbering collides across reports.
