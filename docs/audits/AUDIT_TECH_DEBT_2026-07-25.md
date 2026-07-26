# Tech-Debt Audit — Auralis

**Date**: 2026-07-25
**Scope**: `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/`, `fingerprint-server/`, `tests/`, `docs/`, `.claude/commands/`
**Depth**: deep (file-by-file, concrete fix proposals) · **Limit**: none · **Dimensions**: all 10
**HEAD at audit**: `54d055df` (master) — 168 commits since the previous tech-debt report (2026-07-12)
**Method**: fresh read of current source. Prior reports in `docs/audits/` were used **only** for deduplication, never as a source of findings.


## Executive Summary

**32 findings: 0 CRITICAL · 0 HIGH · 3 MEDIUM · 29 LOW.**

| Dimension | MEDIUM | LOW | Total |
|---|---:|---:|---:|
| 1. Stale Markers | 0 | 1 | 1 |
| 2. Dead Code & Unused Surface | 0 | 5 | 5 |
| 3. Logic Duplication | 0 | 4 | 4 |
| 4. Magic Numbers & Hardcoded Constants | 0 | 3 | 3 |
| 5. Stub & Placeholder Implementations | 0 | 1 | 1 |
| 6. Test Hygiene | 1 | 1 | 2 |
| 7. Stale Documentation & Comments | 1 | 2 | 3 |
| 8. Backwards-Compat Cruft & No-Variants | 1 | 5 | 6 |
| 9. File / Function / Module Complexity | 0 | 5 | 5 |
| 10. Audit-Finding Rot | 0 | 2 | 2 |
| **Total** | **3** | **29** | **32** |

Three further verified candidates were **suppressed as already-tracked OPEN issues** rather than
re-filed: #4243 (`Scanner._update_library_stats()` reachable no-op), #4239 (`useFingerprintCache`
hardcoded mock fingerprint), and #4312 (dead `library_manager` parameter threaded through
`AudioPlayer` → `QueueController`). Each was independently re-derived by this audit and confirmed
still accurate — worth noting as evidence the tracker is current, not as new findings.

No CRITICAL or HIGH findings. That is the expected shape for a debt audit — and the two HIGH
promotion triggers were **actively checked and did not fire**. Dimension 3 re-verified all 12 DSP
stage modules against #4298 and found the shared `no_op` guard structurally intact, with no sibling
omitting `.copy()`; Dimension 4 traced every call site of the 40 `sample_rate=44100` defaults and
confirmed no current caller relies on one (TD4-2).

### The three MEDIUM findings

1. **TD8-7 — the orphaned `fingerprint-server/` crate.** The highest-value item in this report.
   2,364 LOC of Rust at the repo root containing a *second*, independently-drifting 25D fingerprint
   implementation. No workspace membership, no CI build, no launcher, and — since streamlining item
   #12 deleted the Python client — no possible caller. Yet it absorbed three parity fixes in 2026
   (#4110, #4113, #4123), the last landing **four days after** its client was removed, and one of
   those commits describes its YIN port as *"kept in sync via a header comment."* Its `Cargo.lock`
   gets Dependabot PRs while `rust-audit.yml` scans only `vendor/auralis-dsp`.
2. **TD7-1 — the path-validation gate has a blind spot.** `_audit-validate.sh` passes cleanly (592
   refs, 25 skill files, 0 stale) but covers only `.claude/commands/`. Applying its own rule to the
   docs tree finds **128** stale backticked paths in the authoritative docs — three deleted modules
   referenced by `docs/subsystems/dsp-engine.md` alone, and `docs/architecture/module-map.md` still
   describing a deleted binary as *"primary fingerprint path"*, the exact error
   `STREAMLINING_PLAN.md` records having already corrected once.
3. **TD6-1 — the thread-safety suite asserts nothing.** 13 strict `xfail`s with placeholder reasons
   (*"API compatibility - needs updates"*) and no issue reference disable this project's only
   dedicated concurrency suite, in a codebase whose severity scale rates lock-ordering violations
   HIGH. Its sibling file does it correctly (every xfail cites #4269).

### What is genuinely healthy

Two baseline metrics look alarming and are not — both corrected below:
- **Marker debt is zero.** A widened, case-insensitive sweep across every source extension returns 5
  hits, **all false positives** (`spacingXXXLarge`, `migration_vXXX_to_vYYY.sql`). See TD1-1 for why
  this metric is now a poor proxy for deferred work in this repo.
- **Frontend type debt is small.** 532 of the 560 `any` occurrences are in test files; non-test usage
  is **28**, half of it inside the dead `src/performance/` module (TD2-4).

`mypy --warn-unused-ignores` finds exactly **one** stale ignore tree-wide after 168 commits, and
`_audit-validate.sh` is green. Prior audits' fixes were spot-checked throughout and **no regressions
were found** — #4021, #4042, #4088, #4293, #4298, #4304, #4380, #4395 and #4314 were each verified
still in place (#4314 only partially — see TD8-6).
## Baseline Snapshot

Captured in Phase 1 so the next run can diff direction.

| Metric | Count |
|---|---|
| TODO/FIXME/HACK/XXX (Python) | 1 (widened sweep: **0 genuine**, see TD1-1) |
| TODO/FIXME/HACK/XXX (TS/TSX) | 4 (widened sweep: **0 genuine**) |
| `NotImplementedError` (Python) | 3 (all in one documented contract guard) |
| `# type: ignore` (Python) | 84 |
| `@ts-ignore` / `@ts-expect-error` | 2 |
| `: any` / `as any` / `<any>` (TS) | 560 raw — but only **28** in non-test code (532 are in specs/mocks) |
| `@pytest.mark.skip/skipif/xfail` | 65 |
| `it.skip` / `describe.skip` / `.todo` (TS) | 5 |
| Python files > 300 LOC | **102** of 414 |
| TS/TSX files > 300 LOC | 145 of 819 (**43** excluding tests) |
| Python functions > 100 LOC | **72** |
| `#[allow(dead_code)]` (Rust) | 0 |
| Test files (`tests/`) | 395 · **5,115** test functions |
| `auralis/version.py` | `1.5.1` |
| `_audit-validate.sh` | **PASS** — 592 refs / 25 skill files, 0 stale |

**Two baseline metrics are misleading and were corrected during this audit** — future runs should use the corrected form:
- The raw `TODO|FIXME|HACK|XXX` grep returns 5 hits; a widened, case-insensitive sweep across all source extensions confirms **all 5 are false positives** (`spacingXXXLarge`, `migration_vXXX_to_vYYY.sql`). Genuine marker debt is **zero** (TD1-1).
- The raw `any` grep returns 560; **532 of those are in test files**. Non-test `any` usage is **28**, concentrated in `src/performance/` (14). Type-safety debt in shipped code is small.

**Direction**: marker debt is effectively eliminated and frontend type debt is small — both genuinely good results. Oversized-module debt has **not** improved: 102 Python + 43 non-test frontend files remain over the 300-LOC rule, 72 Python functions exceed 100 LOC, and four *closed* god-file issues left their targets 2.3–2.7× over the limit (TD9-3).

## Top 10 Quick Wins

Trivial or small effort, immediate payoff.

| # | Finding | Action | Effort |
|---|---|---|---|
| 1 | **TD8-7** | `rm -rf fingerprint-server/` — 2,364 LOC, no build, no client, no launcher | small |
| 2 | **TD4-1** | Replace `cache/manager.py::_calculate_total_chunks`'s re-derived formula with a call to `content_chunk_count()` | trivial |
| 3 | **TD10-2** | Strike #4511's checklist item for the deleted `RealTimeAnalysisStream.ts` so the issue can close | trivial |
| 4 | **TD8-1** | Delete `ProcessorFactory.set_mastering_targets` — self-documented as dead and racy | trivial |
| 5 | **TD8-5** | Delete 5 `// removed (#NNNN)` breadcrumb comments (git log is the record) | trivial |
| 6 | **TD8-6** | Drop *"will be removed in v2.0.0"* from `LibraryManager`'s runtime warning to match its now-honest docstring | trivial |
| 7 | **TD8-2** | Delete 3 zero-consumer compat re-exports (`_SEND_QUEUE_MAXSIZE`, `auralisTheme`/`colors`, `getShortcutString`) | trivial |
| 8 | **TD2-1** | Delete `frequency_ops.py` — 422-line class, zero callers, no re-export to clean up | small |
| 9 | **TD6-2** | Delete `streaming-mse.test.tsx` — 879 lines of skipped, fixture-only tests | trivial |
| 10 | **TD7-2** | Fix `CLAUDE.md`'s three moved module paths, one package/module confusion, and four wrong counts | trivial |

## Top 5 Medium Investments

Structural work with compounding payoff.

| # | Finding | Investment | Effort |
|---|---|---|---|
| 1 | **TD7-1 + TD10-1** | Extend `_audit-validate.sh` to `docs/architecture|subsystems|development/` + `CLAUDE.md` + `README.md`, add a count-recomputation check, and archive `docs/guides/`. Fixes the path *and* count halves of doc rot structurally rather than by hand. | small (gate) + medium (fixups) |
| 2 | **TD9-1** | Hoist router handlers to module level with `Depends()`, leaving `create_*_router()` a ~10-line assembler. Unblocks the two workstreams (#3838 response_models, TD3-2 error handling) that both stalled on these closure factories. | large — one router per PR, start with `player.py` |
| 3 | **TD6-1** | Fix the 13 thread-safety xfails, starting with the 5 that need only a repository fixture. Restores real coverage of the project's highest-severity bug class. | medium |
| 4 | **TD3-1 + TD3-2** | Finish two abandoned migrations: `BaseRepository._session_scope()` (stalled at 19% adoption) and `@with_error_handling` (9 routers adopted, 13 bypassed — the bypassers silently lose retryable-503 mapping). | medium each |
| 5 | **TD2-2 + TD2-4** | Decide-or-delete on ~3,000 LOC of built-but-unwired subsystems: frontend `src/performance/` (1,505 LOC, zero consumers) and four engine modules imported only by their own tests, one of which (`PersonalPreferences`) is still absorbing bug fixes. | medium — needs a product call, not a silent delete |

## Deferred

Findings gated on other work, or deliberately not filed:

- **TD2-2** (`PersonalPreferences`, `ReferenceAnalyzer`, `ParallelSpectrumAnalyzer`,
  `ContentAwareAnalyzer`) — gated on a product decision. Each has real bug-fix history, so "wire it
  up or delete it" is a roadmap question, not a cleanup. Route to `/audit-engine` for the wiring view.
- **TD2-4** (`src/performance/`) — same shape: gated on whether render-profiling tooling is still
  wanted. TD2-5 (~90 LOC of selectors) must be deleted in the same PR or it becomes newly orphaned.
- **TD3-4** (`fetchWithTimeout` duplication) — already catalogued as the one deferred item of
  `STREAMLINING_PLAN.md` #7. Confirmed and quantified here, **not re-filed**. Note the two copies are
  not behaviorally identical (only one forwards an external `AbortSignal`), so this is a reconcile,
  not a delete.
- **TD9-3** — the >300 LOC portfolio is 102 Python + 43 non-test frontend files. This report tracks
  the *census* and the closed-issue-but-still-oversized pattern; individual splits belong to #4511 and
  the successor issues it should spawn.
- **TD8-6** — the honest fix (finish the `RepositoryFactory` migration across ~20 call sites and
  delete `LibraryManager`) is large; the trivial fix (correct the warning text) is listed as a quick
  win instead.

## Deduplication

Every finding was checked against 159 open issues, 204 `tech-debt`-labelled issues (open + closed),
`docs/development/STREAMLINING_PLAN.md` (including its **do-not-collapse list**), and the tracked
LARGE items #3838, #4075–#4083, #4123, #4203, #4511. Prior reports in `docs/audits/` were consulted
**only** for dedup, never as a source of findings.

**Not re-filed (already tracked, confirmed still accurate):** #3838, #3879, #3892, #4012, #4259,
#4239, #4243, #4260, #4265, #4266, #4268, #4277, #4278, #4281, #4284, #4288, #4312, #4391, #4392,
#4397, #4398, #4400, #4511.

**Verified not regressed:** #4017/#4294 (`_session_scope` migration intact), #4018
(`with_error_handling` on its 7 scoped routers), #4021, #4025, #4029, #4042 (`strict=True` intact in
both concurrency files), #4088/#4293 (breadcrumbs cleared from their target files), #4124, #4241,
#4298 (DSP `no_op` guard intact across all 12 stages), #4300, #4304, #4314 (docstring half only — see
TD8-6), #4380, #4395.

**Do-not-collapse list honoured:** offline vs realtime dynamics, the three chunk paths,
`HybridProcessor` vs `SimpleMasteringPipeline`, `quality/` vs `quality_assessors/`, `AdaptiveMode`,
`SpectrumMapper` vs `AdaptiveTargetGenerator`, `FingerprintStorage` vs `SidecarManager`, and the two
layered processor caches — all checked, none re-reported.

**Investigated and disproved** (documented so a future audit does not re-flag them):

| Candidate | Why it is not a finding |
|---|---|
| `duplicate_detector.py`'s `NotImplementedError` | Documented, tested contract guard (#4241) with a dedicated regression test |
| `stream_normal.py:166` naive `ceil()` chunk count | The normal streaming path deliberately uses zero overlap; the naive formula is correct there |
| `audit-tech-debt.md`'s "all 9 dimensions" string | Self-referential worked example inside its own Dim 10 checklist; the file has exactly 10 dimensions |
| `playback_service.py` / `queue_service.py` / `recommendation_service.py` `...` bodies | `typing.Protocol` structural-typing definitions, not stubs |
| `mastering_branches/base.py::apply()` `pass` body | Correct ABC idiom with 3 concrete subclasses |
| `usePlayEnhanced` / `EnhancementPane` / `EnhancedAudioPlayer` / `UnifiedConfig` | Genuine domain names, not copy-of-X variants |
| `track_repository.get_by_filepath` | Live via the scanner dedup path, not a dead compat alias |
| `src/api/transformers/` | Real consumers via `useLibraryQuery` / `useInfiniteAlbums` |
| `store/selectors/player|queue|combined.ts` | Real `useSelector` consumers; the dead selector layer is isolated to cache/connection |

## Findings

Grouped by severity, then by dimension. Every finding proposes a concrete deletion, consolidation
site, or split axis. Correctness concerns discovered along the way are routed via `Related` to the
owning audit (`/audit-engine`, `/audit-backend`, `/audit-frontend`, `/audit-concurrency`) rather than
re-derived here.

## MEDIUM (3)


### Dimension 6: Test Hygiene

#### TD6-1: 13 strict `xfail`s disable the entire thread-safety concurrency suite with no issue reference and no owner
- **Severity**: MEDIUM (promotion trigger: skip markers guarding regression coverage in a domain with closed HIGH-severity issues)
- **Dimension**: Test Hygiene
- **Location**: `tests/concurrency/test_thread_safety.py:84,130,166,212,262,299,469,532,582,606,635,817,851`
- **Status**: NEW (CLOSED #4042 fixed only the missing `strict=True` on these same markers — verified still present, **not** a regression. The vague-reason/no-issue-ref half was never addressed)
- **Age**: `67315325` 2026-06-28 (#4042 added `strict=True`); the xfails themselves are older
- **Effort**: medium (<=1 day) — the reasons say "needs fixture updates", which is the work
- **Description**: Every reason is a placeholder: `"API compatibility - needs updates"` (×4), `"Database setup requires complex fixtures"` (×5), `"API compatibility issue"` (×2), `"API compatibility - needs fixture updates"` (×2). None cites an issue. The result is that this project's *only* dedicated thread-safety suite reports green while asserting nothing — in a codebase whose documented invariants are *"Player RLock → Library Session is the only safe order"* and *"thread-safe pooling, all access via repositories"*, and whose severity scale rates lock-ordering violations HIGH.
- **Evidence**:
  ```python
  # tests/concurrency/test_thread_safety.py:130
  @pytest.mark.xfail(reason="Database setup requires complex fixtures", strict=True)
  ```
  Contrast the sibling file, which does it right: `tests/concurrency/test_parallel_processing.py` has 11 xfails, every one citing `(see #4269)`.
- **Impact**: A regression in player/library lock ordering or repository thread-safety would not be caught, and `strict=True` means an accidental *fix* also fails the suite — so the markers can only be removed deliberately, which nobody is tracked to do. Memory also records that this file **hangs** when run whole, compounding the invisibility.
- **Siblings**: `tests/concurrency/test_parallel_processing.py` (11 xfails — correctly issue-referenced, do not re-file); `tests/backend/test_boundary_exact_conditions.py:364` (1 skip, reason *"Predates current AudioPlayer API"*, no issue ref).
- **Related**: CLOSED #4042 (strict=True, verified intact), CLOSED #4269 (the sibling file's issue-ref fix — this finding is that same fix never applied here), CLOSED #4274 (same pattern, HPSS xfail). `/audit-concurrency` owns any real race these tests would have caught.
- **Suggested Fix**: File one tracking issue for the fixture work, replace all 13 reasons with `reason="... (see #NNNN)"` exactly as `test_parallel_processing.py` does, and fix the 5 `"Database setup requires complex fixtures"` cases first — those need a repository fixture, not an API change, and are the cheapest path back to real coverage.


### Dimension 7: Stale Documentation & Comments

#### TD7-1: 128 stale backticked path references in the authoritative docs tree — the `_audit-validate.sh` gate covers only `.claude/commands/`, not `docs/`
- **Severity**: MEDIUM (promotion trigger: a stale doc baseline that has misled work in the last 90 days)
- **Dimension**: Stale Documentation & Comments
- **Location**: `docs/architecture/`, `docs/subsystems/`, `docs/development/`, `docs/guides/`, plus `CLAUDE.md`; gate at `.claude/commands/_audit-validate.sh`
- **Status**: NEW
- **Age**: `docs/subsystems/dsp-engine.md` last touched `29650ea0` 2026-07-12; the stale refs survived that edit
- **Effort**: small (extend the gate) + medium (fix or archive the flagged docs)
- **Description**: `_audit-validate.sh` ran clean in this audit — *"OK: all path references valid. Checked 592 refs across 25 skill files."* But its scope is `.claude/commands/*.md` only. Applying the same rule (backticked path must resolve against the tracked tree, basenames included) to the docs tree finds **128** stale refs in `docs/architecture|subsystems|development|guides` + `CLAUDE.md` + `README.md`, and **416** across all non-archive docs. The worst offenders are exactly the docs the 2026-07-11 dev-docs rebuild produced as authoritative:
  - `docs/subsystems/dsp-engine.md:106,117,312` → `mastering_branches.py` (it is a **package** now, `auralis/core/mastering_branches/`, not a file)
  - `docs/subsystems/dsp-engine.md:178` → `src/bin/grpc_fingerprint_server.rs` (**deleted** 2026-07-11; `vendor/auralis-dsp/src/bin/` does not exist)
  - `docs/subsystems/dsp-engine.md:195` → `auralis/analysis/fingerprint/utilities/dsp_backend.py` (**deleted** in streamlining #13 Stage 4)
  - `docs/subsystems/backend-api.md:105,185` → `wav_streaming.py` / `routers/wav_streaming.py` (**deleted long ago** — the exact class of drift the gate's basename check was added to catch, in a tree the gate doesn't scan)
  - `docs/subsystems/frontend.md:29,242` → `src/main.tsx` (**deleted** by streamlining Wave 1 item #2, which `STREAMLINING_PLAN.md` itself records)
  - `docs/architecture/module-map.md:128` describes `grpc_fingerprint_server.rs` as *"Standalone gRPC server (primary fingerprint path, :8766)"* — a deleted file, described as the primary path
- **Evidence**: Re-implementation of the gate's rule over the docs tree (script run in this audit) → 128 stale refs in the authoritative subset, 416 repo-wide excluding `docs/archive/`.
- **Impact**: This is not hypothetical rot: `STREAMLINING_PLAN.md` item #12 records that these same deep-dive docs *"wrongly called the gRPC server the primary path"* and had to be corrected once — and `module-map.md` still says it. A reader (or an audit agent) trusting `docs/subsystems/` today gets pointed at three deleted modules in the DSP doc alone.
- **Siblings**: `docs/guides/` is the largest cluster (~80 of the 128) and is almost entirely historical phase snapshots — `enhanced_audio_player_refactored.py` (×5 files), `multi_tier_buffer.py` (×3 files), `ContextMenu.old.tsx`, `library-v3/`, `player-bar-v3/`.
- **Related**: The 2026-07-11 dev-docs rebuild archived ~300 historical files but stopped short of `docs/guides/`. Dim 10 finding TD10-1 covers the counts side of the same problem.
- **Suggested Fix**: (1) Extend `_audit-validate.sh`'s file list to `docs/architecture/`, `docs/subsystems/`, `docs/development/`, `CLAUDE.md`, `README.md`, `auralis-web/backend/WEBSOCKET_API.md` — same rule, same failure mode; (2) fix the ~20 refs in those four authoritative docs; (3) move `docs/guides/` to `docs/archive/guides/` (it is a phase-snapshot tree, exempt from the gate like `docs/archive/` already is).


### Dimension 8: Backwards-Compat Cruft & "No Variants" Violations

#### TD8-7: Orphaned root-level `fingerprint-server/` Rust crate — 2,364 LOC of a second, divergent 25D fingerprint implementation, still receiving fixes 4 days after its only client was deleted
- **Severity**: MEDIUM (promotion trigger: duplicated logic with divergent bug-fix history)
- **Dimension**: Backwards-Compat Cruft / Logic Duplication
- **Location**: `fingerprint-server/` (16 files, 2,364 LOC Rust) — notably `fingerprint-server/src/analysis/analyzer.rs:11` (`analyze_fingerprint`), `fingerprint-server/src/analysis/yin.rs`, `fingerprint-server/src/analysis/rhythm.rs`
- **Status**: NEW
- **Age**: `a107dc9f` 2025-12-09 (crate created); last touched `b9751733` 2026-07-15
- **Effort**: small (delete the directory) — but needs a product confirmation that the HTTP fingerprint server is not a planned deliverable
- **Description**: A complete standalone Rust HTTP fingerprint server lives at the repo root. It is **not** the `grpc_fingerprint_server.rs` that `STREAMLINING_PLAN.md` item #12 removed on 2026-07-11 (that file lived under `vendor/auralis-dsp/src/bin/`, which no longer exists at all). This crate is entirely orphaned: there is no root `Cargo.toml` workspace, no CI job builds it, `desktop/package.json` and `pyproject.toml` never reference it, and grepping `auralis/`, `auralis-web/backend/`, and `desktop/` for `8766`, `RUST_SERVER`, `use_rust_server`, or `_call_rust_server` returns **zero** hits — the Python client that used to call it was deleted by streamlining item #12.
- **Evidence**:
  ```
  $ ls Cargo.toml                       # no workspace root
  ls: cannot access 'Cargo.toml': No such file or directory
  $ grep -rn "8766\|RUST_SERVER\|use_rust_server" auralis auralis-web/backend desktop
  (no matches)
  $ git log --oneline -- fingerprint-server | wc -l
  12
  ```
  Its own commit messages show a second, drifting implementation being hand-synced to the canonical one:
  - `4f1da969` (2026-06-02, #4110): *"Adds fingerprint-server/src/analysis/yin.rs — a verbatim port of the canonical vendor/auralis-dsp/src/yin.rs ... **kept in sync via a header comment**."*
  - `36ff9721` (2026-06-10, #4113): fixed `rhythm_stability` + `silence_ratio` computed with *"formulas algorithmically incompatible with the Python fallback"*.
  - `b9751733` (2026-07-15, #4123): fixed a LUFS coefficient *"diverging from every other path by ~2x in dB"* — landed **four days after** the client that could reach this code was deleted.
- **Impact**: This is the promotion-trigger case precisely: two implementations of the same 25D fingerprint (`fingerprint-server/src/analysis/analyzer.rs::analyze_fingerprint` vs `vendor/auralis-dsp/src/fingerprint_compute.rs::compute_complete_fingerprint`), with a documented history of one copy carrying bugs the other did not, and a manual "kept in sync via a header comment" contract. Three separate 2026 engineering cycles were spent fixing parity in a binary nothing runs. It also generates ongoing maintenance noise with no coverage: `fingerprint-server/Cargo.lock` is checked in and Dependabot bumps it (`80aec1f3`, `e37eb6a2`), while `.github/workflows/rust-audit.yml` audits **only** `vendor/auralis-dsp/Cargo.lock` — so the dead crate's dependency tree produces PRs but is never security-scanned.
- **Siblings**: `fingerprint-server/src/analysis/yin.rs` (229 LOC) duplicates `vendor/auralis-dsp/src/yin.rs`; `fingerprint-server/src/analysis/rhythm.rs` duplicates the tempo/onset logic in `vendor/auralis-dsp/src/tempo.rs` + `onset_detector.rs`.
- **Related**: `docs/development/STREAMLINING_PLAN.md` item #12 (removed the *vendor* gRPC bin, not this crate). #4110, #4113, #4123 all landed here. `/audit-engine` owns any correctness question about the surviving canonical path.
- **Suggested Fix**: Delete `fingerprint-server/` outright — `vendor/auralis-dsp` is the single Rust source of truth per streamlining decision #13 ("let Rust own the heavy DSP; Python is the glue layer"), and this crate has no build, no client, and no launcher. If an out-of-process fingerprint service is wanted later, rebuild it as a thin binary over `auralis_dsp::fingerprint_compute` rather than a second algorithm.

---


## LOW (29)


### Dimension 1: Stale Markers

#### TD1-1: The repo has effectively zero TODO/FIXME/HACK/XXX debt — but deferral language survives in prose comments
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: repo-wide; the surviving deferrals are `auralis/library/scanner/scanner.py:318`, `auralis/library/sidecar_manager.py:131`, `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:102`, `auralis-web/backend/core/audio_processing_pipeline.py:188`
- **Status**: NEW (informational baseline correction)
- **Effort**: trivial
- **Description**: A widened marker sweep (case-insensitive `TODO|FIXME|HACK|XXX|@todo|TBD` across `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.rs`, `*.mjs` in `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`, `desktop/`) returns **5 hits, all false positives**: `spacingXXXLarge` (×3, a design-system token name), `migration_vXXX_to_vYYY.sql` (a filename pattern in a docstring). There is not one genuine marker left in the tree — a genuinely excellent result and a real change from the baseline snapshot's expectation. What *has* survived is deferral expressed as prose, which no marker grep catches: `scanner.py:318` *"For now, just log the results"*, `sidecar_manager.py:131` *"For now, size + mtime is sufficient for validation"*, `useFingerprintCache.ts:102` *"For now, we'll simulate the worker in the main thread"*, `audio_processing_pipeline.py:188` *"Temporarily disable per-chunk fingerprint analysis"*.
- **Evidence**: widened grep → 5 hits, 0 genuine. Prose-deferral grep (`for now|temporarily|workaround|revisit|not implemented`) → 4 substantive hits in production code.
- **Impact**: The marker census is a poor proxy for deferred work in this repo, because the team writes deferrals as sentences. Any future audit that reports "0 TODOs" as a health signal is measuring the wrong thing.
- **Siblings**: —
- **Related**: The four prose deferrals are routed to Dimension 5 (stub implementations) for reachability analysis rather than re-reported here.
- **Suggested Fix**: Nothing to delete. Recommend the team adopt `# TODO(#NNNN):` for genuine deferrals so they are greppable and issue-linked, and convert the four prose deferrals above into either that form or a closed decision comment.

---


### Dimension 2: Dead Code & Unused Surface

#### TD2-1: `FrequencyOperations` (frequency_ops.py) — whole 422-line class, zero external callers
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/analysis/quality_assessors/utilities/frequency_ops.py:1-422`
- **Status**: NEW
- **Age**: `1c1514b0` 2025-11-29 (Phase 7.1 quality-assessors refactor), mechanically touched by 4 mypy-typing commits through 2025-12-13, otherwise untouched
- **Effort**: small
- **Description**: The module defines one class, `FrequencyOperations`, with 9 static methods (`apply_a_weighting`, `apply_c_weighting`, `compute_frequency_bands`, `analyze_frequency_balance`, `detect_frequency_peaks`, `estimate_spectral_centroid`, `estimate_spectral_spread`, `detect_frequency_anomalies`, `compute_crest_factor`). None is imported or referenced anywhere outside the file itself (one internal self-call at line 307). `auralis/analysis/quality_assessors/utilities/__init__.py` does not re-export it.
- **Evidence**: `grep -rn "FrequencyOperations" --include='*.py' auralis auralis-web tests desktop` → only the class definition (line 19) and one in-file self-call (line 307). Per-method grep for `apply_a_weighting`/`apply_c_weighting`/`estimate_spectral_centroid` also returns zero external hits.
- **Impact**: 422 dead lines sit in `auralis/analysis/quality_assessors/utilities/`, a directory the do-not-collapse list already flags as easy to confuse with `analysis/quality/`; this adds a third, genuinely-unused sibling that increases that confusion for no benefit.
- **Siblings**: None of the other `quality_assessors/utilities/` modules (checked `scoring_ops`, `assessment_constants` imports) showed the same zero-caller pattern — this one is isolated.
- **Related**: None (not on the streamlining do-not-collapse list; that list covers `quality/` vs `quality_assessors/` as directories, not this specific dead class).
- **Suggested Fix**: Delete `frequency_ops.py` outright (no re-export exists to clean up).

#### TD2-2: 4 engine modules (1,491 lines) imported only by test/validation files, never by production code
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/learning/reference_analyzer.py` (431L, used only by `tests/validation/test_against_masters.py`), `auralis/core/personal_preferences.py` (331L, used only by `tests/regression/test_personal_preferences_atomic.py`), `auralis/analysis/parallel_spectrum_analyzer.py` (351L, used only by `tests/validation/validate_parallel_quick.py`, a non-pytest manual script — no `test_` prefix), `auralis/analysis/content_aware_analyzer.py` (378L, used only by `tests/auralis/core/test_analysis_fast_path_windows_4308.py`)
- **Status**: NEW
- **Age**: `personal_preferences.py` from Phase 6.3 "Developer Feedback System" (`72a187f1`, 2025-11-17), still bug-fixed as recently as `957ab72e` 2026-02-17 (#2212 atomic-write fix) — real engineering investment in a module with no production wiring. Others not individually dated (effort not worth per-file `git log -L`).
- **Effort**: medium (needs a product decision per module, not a single mechanical deletion)
- **Description**: Each module has a real, non-trivial public class (`ReferenceAnalyzer`/`MasteringProfile`, `PersonalPreferences`, `ParallelSpectrumAnalyzer`, `ContentAwareAnalyzer`) with zero import sites in `auralis/`, `auralis-web/`, or `desktop/` — only their own dedicated test/validation file references them. `ContentAwareAnalyzer` is also mentioned by name only in docstrings (not imports) inside two OTHER already-tracked dead modules (`profile_matcher.py`, `continuous_target_generator.py` — both part of open #4259's 5-module dead cluster), confirming it isn't reachable via that path either.
- **Evidence**: Module-orphan sweep — for each basename, `grep -rlE` across `auralis auralis-web desktop` (production) returned 0 hits, and across `tests` returned exactly 1 hit each. Class-name greps (`PersonalPreferences`, `ContentAwareAnalyzer`, `ParallelSpectrumAnalyzer`, `ReferenceAnalyzer`) confirm no partial/aliased import elsewhere.
- **Impact**: `PersonalPreferences` in particular is a designed-but-unwired feature (personal mastering-preference layer intended to sit atop the base model) that keeps absorbing real bug fixes (atomic write, file locking) without ever being called by the mastering pipeline or exposed via a backend route — the fix effort is currently pure sunk cost until wired up or deleted. The other three inflate `auralis/analysis/` (already the largest module) and `auralis/learning/` with code that only exists to keep their own tests green.
- **Siblings**: This is the "modules imported ONLY by tests" bucket requested by the checklist; distinct from open #4259 (5 *fully unreferenced* analysis modules — dead even to tests) and open #4278/#4281/#4277 (dead single-function findings, not whole-module).
- **Related**: Not on the STREAMLINING_PLAN.md do-not-collapse list. `/audit-engine` should weigh in on whether `PersonalPreferences` is a live feature roadmap item before deletion (real bug-fix history argues for a product decision, not a silent delete).
- **Suggested Fix**: For each: either wire it into its intended call site (`PersonalPreferences` into the mastering-recommendation flow; `ReferenceAnalyzer` into a real QA/validation CI step; `ParallelSpectrumAnalyzer` into the live spectrum-analysis path if it's meant to supersede the serial one; `ContentAwareAnalyzer` into `AdaptiveMode`/`ContentAnalyzer`) or delete module + its sole test together. Do not leave as-is — each currently fails the "no variants floating unused" principle.

#### TD2-3: Rust `pub fn`s reachable only from the crate's own `#[cfg(test)]` blocks or nowhere at all — 7 sites across 5 files
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `vendor/auralis-dsp/src/stereo_analysis.rs:162` (`is_stereo`, also re-exported at `lib.rs:50` but the crate is a `cdylib` PyO3 extension — the `pub use` creates no external Rust consumer), `compressor.rs:269` (`Compressor::get_state`), `limiter.rs:255` (`Limiter::get_state`), `envelope.rs:113` (`EnvelopeFollower::get_envelope`), `chunk_processor.rs:147` (`process_mono_chunks`), `onset_detector.rs:37` (`OnsetDetector::with_threshold` — zero callers anywhere, not even a test), plus `compressor.rs:256`/`limiter.rs:247`/`biquad_filter.rs:~194` (`Compressor::reset`/`Limiter::reset`/`MultiBandEQ::reset` — zero callers anywhere including tests)
- **Status**: NEW
- **Effort**: small
- **Description**: `rustc`'s `dead_code` lint does not fire on `pub` items in a library crate (it assumes external consumers), so `cargo check --lib` only caught one *private* dead method (`limiter.rs::detect_isr_peaks`, already tracked as open #4265). Manually tracing the 11 `#[pyfunction]`/`#[pymethods]` wrappers in `py_bindings.rs` against every `pub fn` in the other 16 files shows a consistent pattern: builder/introspection/reset methods on the four PyO3-exposed structs (`Compressor`, `Limiter`, `BiquadCascade`/`MultiBandEQ`, `EnvelopeFollower`, `OnsetDetector`) and one standalone helper (`process_mono_chunks`) and one standalone predicate (`is_stereo`) are never called by any of the 11 wrappers or by `fingerprint_compute.rs` (which is the only other internal caller graph, itself reachable via `compute_fingerprint_wrapper`). `get_state`/`get_envelope`/`process_mono_chunks`/`is_stereo` are exercised only inside their own file's `#[cfg(test)] mod tests`; `reset()` on all three structs and `with_threshold()` have zero callers anywhere, test or production.
- **Evidence**: Per-symbol `grep -n "\bSYMBOL\b" *.rs` inside `vendor/auralis-dsp/src/`, filtered to exclude the definition line, for each of the 7 symbols above; cross-checked against `py_bindings.rs`'s 11 `fn *_wrapper` bodies and `fingerprint_compute.rs`'s internal call graph.
- **Impact**: A false sense that these structs' full public API is exercised by the Rust unit-test suite (`cargo test`) — `reset()`/`with_threshold()` in fact have zero test coverage at all, so a bug in them would go undetected all the way to a PyO3 rebuild that happens to expose them later.
- **Siblings**: All in the same `#[pymethods]`-adjacent struct family — treat as one cleanup pass, not 7 separate ones.
- **Related**: Distinct from open #4265 (`detect_isr_peaks`, private, already compiler-flagged) and open #4268 (unused imports) — those are the two Rust dead-code items already tracked; this finding is the "pub-but-actually-dead" category the compiler can't see, which neither open issue covers.
- **Suggested Fix**: Either wire `reset()` into the PyO3 layer (useful for streaming/chunked reuse of a single `Compressor`/`Limiter` instance across calls — plausibly intended but never finished) or delete the 7 methods/functions and their signatures; if kept for future streaming reuse, add a `#[cfg(test)]`-gated unit test for `reset()`/`with_threshold()` so they're not silently untested.

#### TD2-4: Frontend `src/performance/` — entire 1,505-line "Phase C.4b" module has zero consumers anywhere
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/frontend/src/performance/index.ts` (190L, barrel), `withMemo.tsx` (264L), `useRenderProfiler.ts` (309L), `lazyLoader.tsx` (336L), `bundleAnalyzer.ts` (406L) — 1,505 production lines (plus a matching `__tests__/` suite of similar size, not counted)
- **Status**: NEW
- **Age**: `62733980` 2025-11-28 "feat: Phase C.4b & C.4c - Performance Optimization & Accessibility"; touched only by two repo-wide mechanical passes since (`157663a2` 2025-12-02 import fixes, `5811bd03` 2026-03-20 `any`-cast removal, `c2034220` 2026-03-22 relative→absolute import conversion) — no feature work, no real consumer added in 8 months
- **Effort**: medium
- **Description**: `npx ts-prune` flags every export in this directory; manual verification confirms zero importers anywhere in `src/` for both the barrel path (`from '@/performance'` → 0 hits outside the directory itself) and every individual file's direct symbols (`withMemo`, `useRenderProfiler`, `lazyLoader`, `bundleAnalyzer` → 0 hits outside their own files). The sibling accessibility half of the same "Phase C.4b & C.4c" commit, `src/a11y/focusManagement.ts`, is already tracked (open #4392) — this is the performance half of the same dead feature-flag-less rollout, never separately reported.
- **Evidence**: `grep -rn "from '@/performance'" src --include='*.ts' --include='*.tsx' | grep -v '^src/performance/'` → no output. Same null result grepping each of `withMemo`/`useRenderProfiler`/`lazyLoader`/`bundleAnalyzer` as bare identifiers outside their own directory.
- **Impact**: 1,505 lines of render-profiling/memoization/lazy-loading/bundle-analysis infrastructure (plus its test suite) accumulate lint/type-check/CI time and give a false "we have perf tooling" impression, but no component or hook actually benefits from it — any real render-perf regression in the app today is invisible to this tooling because it's never invoked.
- **Siblings**: `src/a11y/focusManagement.ts` (open #4392, same rollout, do not re-file); internally `store/selectors/cache.ts::cacheSelectors` and `store/selectors/connection.ts::connectionSelectors` are re-exported *by* `src/performance/index.ts` (see TD2-5) — once this module is deleted those two re-exports become dead too, tightening the case for deleting both together.
- **Related**: Not the same as old-audit TD2-4 (`useVisualizationOptimization.ts` + `utils/performanceOptimizer.ts`, a different pair of files under `hooks/shared/` and `utils/`) — that was a *different* dead pair from the same 2026-07-06 audit; this is a third, previously unreported dead-perf-tooling case in the same codebase area. Worth a single combined cleanup ticket covering all three (`hooks/shared/useVisualizationOptimization.ts`+`utils/performanceOptimizer.ts` if still open, plus this `src/performance/` directory).
- **Suggested Fix**: Confirm with the user whether render-profiling/lazy-loading tooling is still wanted; if not, delete `src/performance/` (5 files + tests) wholesale. If wanted, wire at minimum `useRenderProfiler` into the top-level `App` shell so it stops being pure dead weight.

#### TD2-5: `cacheSelectors`/`connectionSelectors`/`selectCacheMetrics`/`selectCacheHealthDerived`/`SelectorPerformanceTracker` — memoized-selector layer with no consumer outside the dead `src/performance/` barrel
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/frontend/src/store/selectors/cache.ts:14-44` (`cacheSelectors`, `selectCacheMetrics`, `selectCacheHealthDerived`), `src/store/selectors/connection.ts:14-19` (`connectionSelectors`), `src/store/selectors/selectorPerformance.ts:24-123` (`SelectorPerformanceTracker` class)
- **Status**: NEW
- **Age**: Split out of `store/selectors/index.ts` by #4316 (per file header comments); not individually dated further
- **Effort**: trivial
- **Description**: `selectCacheMetrics` and `selectCacheHealthDerived` (memoized `createSelector` selectors) have zero `useSelector`/import consumers anywhere. `cacheSelectors` and `connectionSelectors` (plain selector-map objects) are re-exported once, by the also-dead `src/performance/index.ts` barrel (TD2-4) — so they have no *live* consumer either. `SelectorPerformanceTracker` is imported only by that same dead barrel (as the `selectorPerformance` singleton). This is distinct from closed #4395, which removed different, individual selector functions living directly inside `cacheSlice.ts`/`connectionSlice.ts` (not this `store/selectors/` memoized layer) — confirmed by reading the #4395 fix commit (`b5f4152f`), which touches only the two slice files, not `store/selectors/cache.ts`/`connection.ts`/`selectorPerformance.ts`.
- **Evidence**: `grep -rn "\bSYMBOL\b" src --include='*.ts' --include='*.tsx' | grep -v store/selectors/` for each of the 5 symbols → only the one hit inside `src/performance/index.ts` for `cacheSelectors`/`connectionSelectors`/`selectorPerformance`, and zero hits at all for `selectCacheMetrics`/`selectCacheHealthDerived`.
- **Impact**: Small (~90 lines combined) but compounds with TD2-4 — deleting `src/performance/` without also removing these leaves an orphaned selector layer that *looks* load-bearing (it's exported through the domain barrel `store/selectors/index.ts` alongside genuinely-used selectors like `selectFormattedRemainingTime`).
- **Siblings**: None beyond the two files; `store/selectors/player.ts`, `queue.ts`, `combined.ts` were spot-checked and show real `useSelector` consumers, so this is isolated to the cache/connection/performance-tracking trio.
- **Related**: TD2-4 (same root cause — both exist to feed the dead `src/performance/` module); distinct from closed #4395 (different files, verified via the fix commit).
- **Suggested Fix**: Delete alongside TD2-4 in the same PR — removing `src/performance/` first will make these show up as newly-dead in a follow-up `ts-prune` pass, confirming the fix is complete.


### Dimension 3: Logic Duplication

#### TD3-1: BaseRepository._session_scope() adoption stalled at 2/14 repositories — the phase-2 follow-up from #4294 was never tracked
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/base.py:33-53` (helper); 89 hand-rolled call sites across
  `album_repository.py` (9), `artist_repository.py` (6), `genre_repository.py` (8), `playlist_repository.py`
  (10), `queue_history_repository.py` (5), `queue_repository.py` (4), `queue_template_repository.py` (12),
  `settings_repository.py` (5), `similarity_graph_repository.py` (7), `stats_repository.py` (1),
  `fingerprint_scheduler_repository.py` (2), `fingerprint_stats_repository.py` (4) — the `session =
  self.get_session(); try: ... finally: session.close()` pattern, none using `_session_scope()`
- **Status**: NEW (the underlying duplication itself is a verified-not-regressed part of #4294, but the
  "follow-up pass across the other 12 repositories" #4294's own closing comment calls for was never filed
  as its own issue — grepped both `open_issues.txt` and `td_issues.txt`, no match)
- **Age**: `731f18b5` (2026-07-06, per #4294) migrated `track_repository.py`/`fingerprint_repository.py`
  only; the other 12 repos' pattern predates that and is untouched since
- **Effort**: medium (1 day) — 89 read-only call sites, mechanical but must preserve commit/rollback
  semantics on write paths per #4294's own migration checklist
- **Description**: `_session_scope()` was added specifically to end this duplication (#4017 → #4294), and
  #4294 migrated the two largest offenders (21 combined sites) explicitly leaving "remaining manual call
  sites: 90 (was 111), tracked for a follow-up pass across the other 12 repositories" in its closing
  comment. Current count is 89 (one site closed incidentally since). No issue exists for that follow-up,
  so the helper sits at 21/110 adoption (19%) with no tracked path to completion — the exact
  "partially-adopted helper" pattern this dimension is asked to flag.
- **Evidence**: 
  ```
  auralis/library/repositories/album_repository.py:34   session = self.get_session()
  auralis/library/repositories/album_repository.py:...   try: ... finally: session.close()
  ```
  vs. the migrated form already in `track_repository.py`:
  ```python
  with self._session_scope() as session:
      return session.execute(...).scalars().all()
  ```
- **Impact**: Any future session-lifecycle change (pooling instrumentation, retry policy, async migration)
  still requires a ~89-site sweep across 12 files instead of a one-file edit — the exact cost #4017/#4294
  set out to eliminate, now 81% unrealized with no open tracking.
- **Siblings**: All 12 repositories listed above; `factory.py` and `base.py` itself are correctly excluded
  (no query methods).
- **Related**: Follow-up to CLOSED #4294 (itself a follow-up to CLOSED #4017). Not a regression — the
  91→89 delta and partial state exactly match #4294's own closing note; this finding is the missing
  tracking issue for the phase explicitly deferred there.
- **Suggested Fix**: File the follow-up #4294 itself called for: migrate the 89 remaining read-only
  call sites (same phasing as #4294 — leave commit/rollback write paths for a further pass) to
  `BaseRepository._session_scope()`, starting with `playlist_repository.py` (10) and
  `queue_template_repository.py` (12), the two largest remaining offenders.

#### TD3-2: `with_error_handling` decorator adopted by 9 routers, bypassed by 13 — `player.py` alone has 19 raw try/except blocks
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/dependencies.py:151-189` (`with_error_handling` helper,
  docstring literally says "eliminates the boilerplate try/except pattern that appears in 60+ router
  endpoints"); bypassed in `auralis-web/backend/routers/player.py` (19 sites, e.g. lines 402-406, 440-444),
  `system.py` (8), `tracks.py` (8), `enhancement.py` (8), `cache_streamlined.py` (5), `files.py` (3),
  `fingerprint_status.py` (3), `library_scan.py` (3), `processing_api.py` (3), `fingerprint_queue.py` (1)
- **Status**: NEW (checked #4018, which added `@with_error_handling` to 7 named routers — `playlists.py`,
  `library.py`, `similarity.py` [via its own decorator, deliberately], `albums.py`, `artwork.py`,
  `metadata.py`, `settings.py` — and closed as fully done for those 7. `player.py`/`system.py`/`tracks.py`/
  `enhancement.py`/etc. were never in scope for #4018 and have no other open issue.)
- **Age**: `dependencies.py`'s `with_error_handling` predates #4018 (2026-07-06); `player.py`'s raw
  try/except blocks are older still (some pre-`c40509eb`) and were untouched by that migration
- **Effort**: medium (1 day) for `player.py` alone (19 sites, careful check each preserves its specific
  status code — most are 500 but `seek_position` mixes a 503 ValueError branch, so this isn't a pure
  mechanical decorator swap everywhere); small (<=2h) per remaining router
- **Description**: `player.py:402-406` and 18 siblings all follow exactly the pattern the decorator's own
  docstring calls out as its replacement target: `try: ... / except HTTPException: raise / except
  Exception: logger.error(...); raise HTTPException(500, "Failed to X")`. This is the single largest
  concentration of the boilerplate `with_error_handling` was built to remove, and it's completely
  unmigrated — a stronger finding than raw duplication because the fix already exists and 9 routers prove
  it's a drop-in replacement.
- **Evidence**:
  ```python
  # auralis-web/backend/routers/player.py:402-406
          except HTTPException:
              raise
          except Exception:
              logger.error("Failed to load track", exc_info=True)
              raise HTTPException(status_code=500, detail="Failed to load track")
  ```
  identical shape to what `dependencies.py:178-187`'s docstring shows the decorator replacing.
- **Impact**: Divergent-fix risk: `with_error_handling` centrally maps `OperationalError` → 503 (via
  `handle_query_error`); none of the 13 non-adopting routers get that retryable-503 behavior for free —
  any transient SQLite lock in `player.py`'s 19 handlers surfaces as a flat 500 instead of a retryable 503,
  while the 7 already-migrated routers get it automatically.
- **Siblings**: `system.py`, `tracks.py`, `enhancement.py`, `cache_streamlined.py`, `files.py`,
  `fingerprint_status.py`, `library_scan.py`, `processing_api.py`, `fingerprint_queue.py` (counts above).
- **Related**: Direct continuation of CLOSED #4018 (which scoped itself to 7 specific routers and didn't
  claim wider coverage) and CLOSED #4304 (the sibling 404-helper migration, which did cover all routers).
  Also touches #3838 (response_model gap) — same routers, different axis.
- **Suggested Fix**: Extend #4018's migration to the 10 listed routers, applying `@with_error_handling`
  per-endpoint exactly as done for the 7 already-migrated ones; start with `player.py` (19 sites, biggest
  win) and preserve any non-500 branches (e.g. `seek_position`'s `except ValueError -> 503`) as pre-decorator
  checks the way `similarity.py`'s local decorator variant already demonstrates is compatible.

#### TD3-3: `helpers.py`'s pagination/batch/filter/cache-response helper cluster is entirely dead in production — duplicates concepts covered elsewhere, exercised only by tests
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/helpers.py:76-241,319-405,412-430,470-607` (`create_pagination_meta`,
  `create_paginated_response`, `validate_pagination_params`, `execute_batch_operation`,
  `execute_batch_operation_sync`, `validate_batch_request`, `paginate_list`, `apply_filters`,
  `apply_search`, `create_success_response`, `calculate_cache_hit_probability`, `format_cache_stats`,
  `estimate_cache_completion_time`, `create_cache_aware_response` — ~13 functions, ~250 of the file's 648
  lines); backing models `schemas.py:78` `PaginationMeta`, `schemas.py:97` `PaginatedResponse`,
  `schemas.py:124-171` `BatchItem`/`BatchRequest`/`BatchItemResult`/`BatchResponse`,
  `schemas.py:38` `SuccessResponse`
- **Status**: NEW (distinct from OPEN #3892, which covers only the `PaginatedResponse` half of this — the
  batch-operation/filter-search/cache-response functions and their backing `BatchItem`/`BatchRequest`/
  `BatchItemResult`/`BatchResponse`/`SuccessResponse` models are a separate dead cluster with no open issue)
- **Age**: `helpers.py` docstring says "Phase B.1: Backend Endpoint Standardization" — an earlier phase than
  the currently-live `spawn_background_task`/`seed_enhancement_settings` additions (most recent real commit
  to the file, `dd90fd76`, 2026-07-14, only touched the still-live `seed_enhancement_settings`)
- **Effort**: small (<=2h) — delete the 13 dead functions + 5 backing schema models, confirmed zero
  production call sites
- **Description**: Verified via `grep -rn` across every `.py` file in `auralis-web/backend/` (routers,
  services, core, ws_handlers, analysis) plus the whole `auralis/` tree: none of these 13 functions is
  called anywhere in production code. Every production importer of `helpers.py` (`ws_handlers/connection.py`,
  `core/job_worker.py`, `core/streamlined_worker.py`, `core/state_manager.py`,
  `services/library_auto_scanner.py`, `routers/library_scan.py`, `routers/enhancement.py`,
  `config/startup.py`, `analysis/fingerprint_queue.py`) imports only `spawn_background_task`,
  `log_task_exception`, `scan_progress_percentage`, or `seed_enhancement_settings` — the unrelated,
  actively-used async-task/scan-progress half of the file. The pagination/batch/filter/cache-response half
  is exercised only by `tests/backend/test_cache_integration_b2.py` and
  `tests/backend/test_schemas_and_middleware.py`. Its own `routers/pagination.py::PaginatedResponse.create()`
  sibling (the "canonical" flat-shape alternative per #3892) is *also* zero-callers, confirming there are
  two dead pagination implementations plus a third dead batch-operation implementation, none used by the
  ad-hoc dict-literal pagination/batch shapes that routers actually ship (`routers/library.py:167-173` etc.).
- **Evidence**:
  ```
  $ grep -rln "execute_batch_operation\|apply_filters\|apply_search\|format_cache_stats\|create_cache_aware_response\|create_success_response" auralis-web/backend/routers/*.py auralis-web/backend/main.py
  # (no matches)
  $ grep -n "create_paginated_response\|execute_batch_operation\|..." tests/backend/*.py | cut -d: -f1 | sort -u
  tests/backend/test_cache_integration_b2.py
  tests/backend/test_schemas_and_middleware.py
  ```
- **Impact**: Anyone reading `helpers.py` or `schemas.py` to find "the" batch/pagination/cache-response
  pattern lands on three unused implementations before finding the real ad-hoc dict shapes routers
  actually return — pure onboarding/change-cost tax with no runtime benefit.
- **Siblings**: `routers/pagination.py::PaginatedResponse`/`PaginationParams` (already tracked, #3892) is
  the same dead-duplication shape one module over.
- **Related**: Complements OPEN #3892 (pagination half only) — recommend resolving both in the same PR
  since the decision ("pick the flat shape, delete the rest, migrate routers" per #3892, or "delete all
  three, keep ad-hoc dicts") applies to both clusters identically.
- **Suggested Fix**: Delete the 13 dead functions from `helpers.py` and the 5 backing models
  (`PaginationMeta`, `PaginatedResponse`, `BatchItem`, `BatchRequest`, `BatchItemResult`, `BatchResponse`,
  `SuccessResponse`) from `schemas.py`, plus their two dedicated test files' now-pointless coverage —
  unless #3892's resolution decides to actually adopt one of the pagination shapes, in which case fold this
  finding's batch-operation half into that same migration PR rather than reviving it separately.

#### TD3-4: Two independent `fetchWithTimeout`-style implementations (confirm/quantify of already-catalogued item)
- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/frontend/src/hooks/api/useRestAPI.ts:67-89` (hook-local `AbortController` +
  `setTimeout(() => controller.abort(), REQUEST_TIMEOUT)` fetch wrapper) vs.
  `auralis-web/frontend/src/services/api/standardizedAPIClient.ts:220-269` (class-method version with the
  same `AbortController`/`setTimeout` shape, plus external-signal forwarding for unmount cancellation)
- **Status**: Existing — catalogued in `docs/development/STREAMLINING_PLAN.md` item #7 (done 2026-07-12) as
  "the one genuine remaining duplication, deferred": *"extract a shared `fetchWithTimeout` helper both
  clients could sit on"*. Per SHARED.md instruction this is confirmed and quantified here, not re-filed.
- **Age**: `standardizedAPIClient.ts` last touched `199f4812` (2026-07-12, unrelated cache-payload fix);
  `useRestAPI.ts` last touched `c16429ea` (2026-05-30, unrelated `setError` fix) — both predate and are
  untouched by the #7 streamlining pass that flagged the duplication
  `useRestAPI.ts:32,71-72,78,82` — timeout constant `REQUEST_TIMEOUT`, own `AbortController`, no
  external-signal forwarding
  `standardizedAPIClient.ts:99,114,120,194,203,220,247-269` — configurable per-request `timeout`, own
  `AbortController`, `options.signal` forwarding for caller-driven cancellation (#3393)
- **Impact**: Any future change to timeout/cancellation semantics (e.g. AbortSignal.timeout() adoption,
  retry-on-abort policy) requires editing both call sites; the two are not behaviorally identical today
  (`standardizedAPIClient` forwards an external signal, `useRestAPI` does not) so a naive merge would need
  to reconcile that gap, not just delete one copy.
- **Siblings**: None beyond the two named — confirmed no third implementation exists (`grep -rln
  "new AbortController"` across `src/services/` and `src/hooks/` returns only these two files).
- **Related**: `STREAMLINING_PLAN.md` item #7 (Wave 3), which already retired the 3 dead
  `standardizedAPIClient`-backed hooks and kept this exact duplication as its one documented deferred item.
- **Suggested Fix**: As STREAMLINING_PLAN #7 already proposes — extract a shared `fetchWithTimeout(url,
  options, timeoutMs, externalSignal?)` helper (e.g. `src/services/api/fetchWithTimeout.ts`) that both
  `useRestAPI.ts` and `standardizedAPIClient.ts` call, preserving `standardizedAPIClient`'s external-signal
  forwarding as an optional parameter so `useRestAPI` callers gain it rather than lose parity.


### Dimension 4: Magic Numbers & Hardcoded Constants

#### TD4-1: `cache/manager.py::_calculate_total_chunks` re-derives `content_chunk_count`'s formula instead of calling it
- **Severity**: LOW
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: `auralis-web/backend/cache/manager.py:162-172`
- **Status**: NEW (related to CLOSED #4025, which removed this file's *constant* redeclarations; the *formula* duplication survived)
- **Age**: introduced with the #4124 fix
- **Effort**: trivial (<=30 min)
- **Description**: `auralis-web/backend/core/chunk_boundaries.py` is the documented single source of truth and already exports `content_chunk_count(total_duration)`. `cache/manager.py` imports `CHUNK_DURATION`/`CHUNK_INTERVAL` from it (correctly, per #4025) but then re-implements the overlap-aware count inline, with a function-local `import math` and a locally re-derived `overlap = CHUNK_DURATION - CHUNK_INTERVAL`:
  ```python
  def _calculate_total_chunks(self, duration: float) -> int:
      import math
      overlap = CHUNK_DURATION - CHUNK_INTERVAL
      return max(1, math.ceil((duration - overlap) / CHUNK_INTERVAL))
  ```
  vs. the SoT `return max(1, int(np.ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL)))`.
- **Evidence**: The docstring states the invariant it is at risk of breaking — *"so the cache-completion target matches `ChunkedAudioProcessor.total_chunks`"* — and `ChunkedAudioProcessor.total_chunks` is set from `content_chunk_count()` (`chunked_processor.py:272,287`). Two expressions, one required-equal result.
- **Impact**: If the chunk model is ever retuned (e.g. `OVERLAP_DURATION` decoupled from `CHUNK_DURATION - CHUNK_INTERVAL`), the two diverge silently and the cache never reports a track complete. Not a live bug — the two expressions are numerically identical today.
- **Siblings**: Checked all other `ceil(` chunk-count sites. `auralis-web/backend/core/stream_normal.py:166` uses a naive `ceil(total_frames / interval_samples)` but is **correct** — the normal (unenhanced) streaming path deliberately uses zero overlap, documented at `stream_normal.py:161-163`. Not a finding.
- **Related**: CLOSED #4025 (constants), CLOSED #4124 (the count formula itself), OPEN #4284 (`MAX_LEVEL_CHANGE_DB` duplicated verbatim in `chunked_processor.py` — same "duplicate instead of import" pattern, already tracked).
- **Suggested Fix**: `from core.chunk_boundaries import content_chunk_count` and make `_calculate_total_chunks` a one-line delegation, exactly as `core/chunk_operations.py:367-368` already does.

#### TD4-2: 40 DSP entry points default `sample_rate=44100`, so a single forgetful call site silently mis-tunes every filter
- **Severity**: LOW
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: 40 sites across `auralis/dsp/` and `auralis/core/` — e.g. `auralis/dsp/utils/spectral.py:44,93,205,247`, `auralis/dsp/utils/adaptive.py:108`, `auralis/dsp/eq/psychoacoustic_eq.py:40`, `auralis/dsp/eq/masking.py:23`, `auralis/dsp/dynamics/brick_wall_limiter.py:27,250`, `auralis/dsp/dynamics/settings.py:68`, `auralis/dsp/dynamics/lowmid_transient_enhancer.py:28`, `auralis/dsp/advanced_dynamics.py:342`, `auralis/dsp/realtime_adaptive_eq/settings.py:28`, `auralis/core/processing/stage_snapshot.py:62`, `auralis/learning/reference_library.py:88`
- **Status**: NEW
- **Effort**: medium (<=1 day) — 40 signatures plus call-site verification
- **Description**: Every one of these is a *default parameter*, not a hardcoded constant in the body, so the promotion trigger ("would silently truncate/overflow audio under documented use") does **not** fire today. **I verified the call sites**: `spectral_centroid`, `tempo_estimate`, and `calculate_loudness_units` are called with an explicit rate at every production site (`content_analyzer.py:92,290,98,293`, `adaptive_mode.py:115,124,153,258`, `normalization_step.py:69`, `feature_extractor.py:90,185`). So this is latent, not live — reported as LOW accordingly.
- **Evidence**: `grep -RIn -E 'sample_rate\s*:?\s*(int)?\s*=\s*44100' auralis | wc -l` → 40. No current caller relies on the default.
- **Impact**: The failure mode is silent and severe: 48 kHz content processed with 44.1 kHz filter geometry shifts every critical-band centre and every filterbank edge by ~8.8%, with no error and no audible cue at the call site. CLAUDE.md's own DSP rule — *"Load metadata (sample rate, channels) BEFORE processing"* — exists precisely because of this, and 40 defaults quietly make violating it legal. CLOSED #4029 (`content_analyzer.py` hard-coding `window_size=44100`) is the same bug class already having bitten once.
- **Siblings**: The full 40-site list above; `auralis/core/config.py:61`'s `internal_sample_rate: int = 44100` is the legitimate configured default and should stay.
- **Related**: CLOSED #4029. Any *actual* wrong-rate bug belongs to `/audit-engine`, not here.
- **Suggested Fix**: Make `sample_rate` a required positional parameter on the ~30 module-level DSP functions (defaults on `@dataclass` settings objects like `dynamics/settings.py` and `eq/psychoacoustic_eq.py` are fine to keep — they are configured objects, not call-through helpers). `mypy` will surface every call site that was relying on the default; today's evidence says there are none, so the change is safe and turns a latent class of bug into a type error.

#### TD4-3: 26 hardcoded hex colors outside the design system (verified small and mostly legitimate)
- **Severity**: LOW
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: `auralis-web/frontend/src/store/middleware/loggerMiddleware.ts` (7), `components/shared/MediaCard/MediaCardArtwork.tsx` (4), `index.tsx` (3), `components/shared/Toast/toastColors.ts` (2), `components/library/AlbumCharacterPane/GlowingArc.tsx` (2), `a11y/focusManagement.ts` (2), + 6 single-hit files
- **Status**: NEW
- **Effort**: trivial
- **Description**: Excluding tests and `design-system/`, only 26 raw hex colors remain in the frontend. Most are defensible — `loggerMiddleware.ts`'s 7 are devtools console styling, `focusManagement.ts`'s 2 are a screen-reader live-region, and `toastColors.ts`'s 2 sit on lines that *explicitly document* replacing a deprecated hex with a token. The genuine token bypasses are the artwork/gradient sites: `MediaCardArtwork.tsx` (4) and `GlowingArc.tsx` (2).
- **Evidence**: `grep -RIn -E "#[0-9a-fA-F]{6}\b" src | grep -v tests | grep -v design-system/ | wc -l` → 26.
- **Impact**: Small. Reported mainly as a baseline number — the design-token migration is essentially complete, and the remaining six real bypasses are in artwork-placeholder gradients that the 2026-07-25 theme-unification commit (`f2143dd7`) did not reach.
- **Siblings**: —
- **Related**: Overlaps `/audit-frontend` Dim 5; reported here only, to avoid double-filing.
- **Suggested Fix**: Move `MediaCardArtwork.tsx`'s and `GlowingArc.tsx`'s six gradient stops into `design-system/tokens` as named artwork-placeholder gradient tokens; leave the devtools/a11y hexes as-is with a short justifying comment.

---


### Dimension 5: Stub & Placeholder Implementations

#### TD5-3: `captureErrorToServer` POSTs to a backend route that doesn't exist, permanently dead behind a `false` default
- **Severity**: LOW
- **Dimension**: Stub & Placeholder Implementations
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:281-283, 344-355`
- **Status**: NEW
- **Effort**: small (<=2h)
- **Description**: The Redux error-tracking middleware has a real (non-mock) implementation of
  `captureErrorToServer()` — it POSTs tracked errors to `/api/errors` via `navigator.sendBeacon`/
  `fetch`, guarded by `finalConfig.logToServer`. But: (1) `logToServer` defaults to `false`
  (line 140) and the one production instantiation site, `store/index.ts:39`
  (`createErrorTrackingMiddleware({ logToConsole: import.meta.env.DEV })`), never overrides it, so
  the call is permanently unreachable in the shipped app; and (2) even if enabled, grepping every
  backend router and `config/routes.py` shows no `/api/errors` (or `/errors`) endpoint is registered
  anywhere — the target route doesn't exist, so enabling the flag today would 404/silently drop
  every beacon.
- **Evidence**:
  ```ts
  // errorTrackingMiddleware.ts:140 — default
  logToServer: false,
  // errorTrackingMiddleware.ts:281-283 — gated call
  if (finalConfig.logToServer) {
    captureErrorToServer(trackedError);
  }
  // errorTrackingMiddleware.ts:344-345
  function captureErrorToServer(error: TrackedError): void {
    // This would typically send to a logging service like Sentry
  ```
  ```ts
  // store/index.ts:39 — the only production wiring, logToServer never set
  createErrorTrackingMiddleware({ logToConsole: import.meta.env.DEV })
  ```
- **Impact**: Currently harmless (dead code, flag is off), but it's a trap: flipping `logToServer:
  true` in some future config change would silently start firing beacons at a 404 route rather than
  actually reporting errors anywhere useful — the comment's "like Sentry" framing invites exactly
  that false confidence.
- **Siblings**: None.
- **Related**: None found in open/closed issue lists for this specific function.
- **Suggested Fix**: Either delete `captureErrorToServer` and the `logToServer` config option
  entirely (client-side `errorStore` + console logging is the only thing actually used), or if
  server-side error reporting is wanted, add the matching `/api/errors` backend route and flip the
  default — but don't leave a flag defaulting to a route that was never built.


### Dimension 6: Test Hygiene

#### TD6-2: `streaming-mse.test.tsx` — 879 lines of fully-skipped, fixture-only tests kept as a "historical fixture"
- **Severity**: LOW
- **Dimension**: Test Hygiene / Dead Code
- **Location**: `auralis-web/frontend/src/tests/integration/streaming-audio/streaming-mse.test.tsx:439` (`describe.skip`)
- **Status**: NEW
- **Age**: `d8861c76` 2026-07-08 (*"skip fixture-only MSE test, add real AudioPlaybackEngine tests"*)
- **Effort**: trivial
- **Description**: The file's own docstring is admirably honest: the 20 tests exercise `TestMSEPlayer`/`MockMediaSource`/`MockSourceBuffer` all defined in the same file, import no production module, and test an API (Media Source Extensions) that *"Auralis never adopted"*. Skipping it fixed a false-green (#3935/TC-3) — correct call. But it was then **kept, skipped, "as a historical fixture in case MSE-based streaming is revisited"**, making it the single largest file in `src/tests/` (879 lines) and the 6th largest TS file in the repo, none of which will ever run.
- **Evidence**: `describe.skip('Streaming & MSE Integration Tests', ...)` at line 439; the real coverage it points to (`src/services/audio/__tests__/AudioPlaybackEngine.test.ts`) exists and runs.
- **Impact**: 879 lines that every repo-wide grep, LOC census, and test-file count includes but no CI run executes. Directly inflates the frontend test-file metrics and slows `vitest` collection. Git history is the correct home for a "historical fixture" — this is exactly the "breadcrumb instead of deletion" pattern CLAUDE.md's No-Variants principle rejects.
- **Siblings**: `auralis-web/frontend/src/components/shared/__tests__/CacheHealthWidget.test.tsx:370,574` and `components/__tests__/Integration.test.tsx:252` are 3 further `it.skip`s — all three have *good*, specific reasons documenting a real design decision (ESC not implemented; auto-refresh belongs in hook tests; WebSocket isolation). Not findings; noted so a future audit does not re-flag them.
- **Related**: #3935 (the false-green fix that skipped it). OPEN #4400 covers the *other* skip family (deleting skipped tests for removed/deprecated REST endpoints in `test_main_api.py` / `test_api_endpoint_integration.py`) — **deduped, not re-filed here**.
- **Suggested Fix**: Delete the file. It is recoverable from `d8861c76` if MSE is ever revisited, and the docstring's own reasoning ("no production module is imported") is the argument for deletion, not retention.


### Dimension 7: Stale Documentation & Comments

#### TD7-2: `CLAUDE.md`'s Codebase Map points at three backend modules that moved to `core/`, one module that became a package, and quotes four wrong counts
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `CLAUDE.md` (Codebase Map + Reference sections)
- **Status**: NEW
- **Age**: `e4353a53` 2026-07-25 (last edited today, for the version bump — the map was not revalidated)
- **Effort**: trivial (<=30 min)
- **Description**: `CLAUDE.md` is loaded into every session as authoritative context, so its drift compounds. Verified against the live tree:

  | CLAUDE.md claim | Live |
  |---|---|
  | `auralis-web/backend/chunked_processor.py` | actually `auralis-web/backend/core/chunked_processor.py` |
  | `auralis-web/backend/audio_stream_controller.py` | actually `.../core/audio_stream_controller.py` |
  | `auralis-web/backend/processing_engine.py` | actually `.../core/processing_engine.py` |
  | `auralis/library/scanner.py  Folder scanning` | `auralis/library/scanner/` is a **package** |
  | `routers/  19 route handlers` | **21** `include_router()` calls in `config/routes.py`; 26 `.py` files |
  | `tests/  ~5,400 test functions (391 files)` | **5,115** functions, **395** files |
  | `docs/  21 topic dirs` | **19** |
  | `migration_manager.py  DB migrations (schema v16)` | correct (`__db_schema_version__ = 16`) ✓ |
- **Evidence**: `ls auralis-web/backend/chunked_processor.py` → no such file; `grep -c include_router auralis-web/backend/config/routes.py` → 21; `grep -rhoE '^\s*(async )?def test_' tests \| wc -l` → 5115.
- **Impact**: Every session starts with three wrong module paths and four wrong counts. The counts in particular are the kind of number audits quote instead of recomputing (see TD10-1).
- **Siblings**: `.claude/commands/_audit-common.md` has the same class of drift (TD10-1).
- **Related**: TD7-1, TD10-1.
- **Suggested Fix**: Correct the seven rows above, and add the count recomputation to the same gate proposed in TD7-1 so the map is validated mechanically rather than by memory.

#### TD7-3: `README.md` install instructions ship download filenames from `1.2.0-beta.2` while the project is at `1.5.1`
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `README.md:99,106-108,120`; also `docs/ARTIST_ARTWORK.md:4` (*"Version: 1.2.0-beta.1+"*)
- **Status**: NEW
- **Age**: predates the 1.5.0/1.5.1 bumps (2026-07-18 / 2026-07-25)
- **Effort**: trivial
- **Description**: `auralis/version.py` is the single source of truth at `1.5.1`, and `sync_version.py` correctly propagates it to `package.json`, `pyproject.toml`, `desktop/package.json`, `auralis-web/frontend/package.json` (all verified at 1.5.1). But `README.md`'s user-facing install block still names `Auralis.Setup.1.2.0-beta.2.exe`, `Auralis-1.2.0-beta.2.AppImage`, and `Auralis-1.2.0-beta.2.dmg` — artifacts three minor versions old, from a line that (per `docs/MASTER_ROADMAP.md:33`) is the last actually-tagged release.
- **Evidence**: `grep -n '1\.2\.0-beta' README.md` → lines 99, 106, 107, 108, 120.
- **Impact**: Low functional risk (there is no 1.5.1 release artifact yet, since 1.5.0/1.5.1 are untagged source milestones), but the README is the first thing a contributor reads and it contradicts `README.md:386`'s own *"Version metadata aligned on 1.5.1"* checkbox six lines of scroll away.
- **Siblings**: `docs/ARTIST_ARTWORK.md:4`.
- **Related**: `sync_version.py` covers manifests but not prose; TD7-1's proposed gate could cover version strings too.
- **Suggested Fix**: Replace the hardcoded filenames with a version placeholder or a "latest release" link, and teach `sync_version.py` to rewrite version strings in `README.md` and `docs/*.md` front-matter the way it already does for the four manifests.

---


### Dimension 8: Backwards-Compat Cruft & "No Variants" Violations

#### TD8-1: `ProcessorFactory.set_mastering_targets` — confirmed zero callers, racy by its own admission
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/core/processor_factory.py:354-393`
- **Status**: NEW
- **Effort**: trivial (<=30 min)
- **Description**: The method's own docstring says "DEPRECATED (#3720) ... Kept for backward
  compatibility; no in-tree callers as of #3720" and explains the replacement (`get_or_create(...)`
  with `mastering_targets` folded into the cache key). Grepped the whole tree for
  `set_mastering_targets(` — the only hit is the definition itself; zero callers in
  production or tests.
- **Evidence**:
  ```python
  """
  DEPRECATED (#3720): ... this
  method mutates a cached processor in place, which races with
  any concurrent `process_chunk()` call on the same instance.
  Kept for backward compatibility; no in-tree callers as of #3720.
  """
  ```
- **Impact**: ~40 lines of dead, self-admittedly racy code sitting in a hot-path class
  (`ProcessorFactory`), adding surface area and a landmine for anyone who re-discovers and calls it.
- **Siblings**: None.
- **Related**: #3720 (already closed migration this method was superseded by).
- **Suggested Fix**: Delete the method entirely (no deprecation shim — per CLAUDE.md "no variants" /
  this repo refactors in place).

#### TD8-2: Dead re-exports kept "for backward compatibility" with zero consumers
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**:
  - `auralis-web/backend/core/audio_stream_controller.py:45`
  - `auralis-web/frontend/src/theme/themeConfig.ts:504-507`
  - `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:126-132` (`getShortcutString`)
- **Status**: NEW
- **Effort**: trivial (<=30 min) each
- **Description**: Three unrelated but same-shaped cases of a symbol re-exported/kept explicitly
  "for compat" that has zero real consumers:
  - `audio_stream_controller.py:45`: `from .stream_protocol import _SEND_QUEUE_MAXSIZE  # noqa: F401
    (re-exported for compat)`. Grepped every import of `audio_stream_controller` across the backend
    (10 importers) — none import `_SEND_QUEUE_MAXSIZE` from it; the constant is only used internally
    by `stream_protocol.py` itself.
  - `themeConfig.ts:504-507`: `export const auralisTheme = createAuralisTheme('dark'); export {
    darkColors as colors }; export default auralisTheme;` all three explicitly commented "for
    backward compatibility". The only consumer of the module (`contexts/ThemeContext.tsx`) imports
    `createAuralisTheme`, `darkColors`, `lightColors`, `glassEffects` — never `auralisTheme`, the
    default export, or the `colors` alias. Confirmed via grep: no file imports the default export or
    `colors` from this module anywhere.
  - `useKeyboardShortcuts.ts:126-132`: `getShortcutString`, docstringed "Legacy alias for
    formatShortcut (for backward compatibility with tests)" — grepped every reference; the only
    importer is its own test file (`__tests__/useKeyboardShortcuts.test.ts`). Zero production
    consumers; `formatShortcut` itself (the thing it's an alias for) IS live, consumed by
    `ComfortableApp.tsx`.
- **Impact**: Each is small in isolation, but together they're a recognizable pattern of
  "compat exports nobody asked to keep" — the exact rot CLAUDE.md's no-variants rule and this
  desktop-only app (no external API consumers) argue against keeping.
- **Siblings**: All three share the "kept for compat, zero consumers" shape; grouped as one finding
  per the sibling-detection rule.
- **Related**: None (no matching open/closed issue found for these three specific symbols).
- **Suggested Fix**: Delete the `_SEND_QUEUE_MAXSIZE` re-export line; delete `auralisTheme`/default
  export/`colors` alias from `themeConfig.ts` (keep the named `createAuralisTheme`/`darkColors`/
  `lightColors`/`glassEffects` exports that are actually used); delete `getShortcutString` and update
  its test file to test `formatShortcut` directly (or delete the test if it's purely testing the
  now-deleted alias).

#### TD8-4: `create_files_router`'s `get_library_manager` parameter is unused but still wired in production
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/routers/files.py:85-94`, wired at
  `auralis-web/backend/config/routes.py:126`
- **Status**: NEW
- **Effort**: trivial (<=30 min)
- **Description**: `create_files_router(get_library_manager=..., connection_manager=...,
  get_repository_factory=...)`'s docstring says "get_library_manager: Deprecated, unused. Kept for
  backward compatibility." Confirmed via grep of the whole `files.py` body: the parameter appears
  only in the signature and the docstring, never called. Yet `config/routes.py:124-129` still passes
  a real, live callable: `create_files_router(get_library_manager=get_component('library_manager'),
  connection_manager=manager, get_repository_factory=get_component('repository_factory'))`.
- **Evidence**:
  ```python
  def create_files_router(
      get_library_manager: Callable[[], Any] | None = None,   # never called in this file
      connection_manager: Any = None,
      get_repository_factory: Callable[[], Any] | None = None
  ) -> APIRouter:
      """
      Args:
          get_library_manager: Deprecated, unused. Kept for backward compatibility.
      """
  ```
- **Impact**: Small but real — a real component lookup (`get_component('library_manager')`) is
  resolved and passed at every app startup for a parameter with no effect.
- **Siblings**: Same shape as TD8-3 (dead `library_manager` plumbing) but a different call chain —
  kept as a separate finding since the fix site (a router factory signature + one `routes.py` call)
  is independent of TD8-3's fix site (player constructors).
- **Related**: TD8-3 above; `dependencies.py::require_library_manager` (already flagged by
  orchestrator).
- **Suggested Fix**: Remove the `get_library_manager` parameter from `create_files_router` and its
  corresponding kwarg at the `routes.py:126` call site, in the same PR.

#### TD8-5: Breadcrumb "removed (#NNNN)" comments left in place of deletion (recurring pattern)
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**:
  - `auralis-web/frontend/src/hooks/library/index.ts:12-14`
  - `auralis-web/frontend/src/hooks/player/index.ts:14-16, 22-30`
  - `auralis-web/frontend/src/types/api.ts:141-144, 152-153, 165-166, 278-281`
  - `auralis-web/backend/schemas.py:227-229`
- **Status**: NEW (this exact pattern was previously filed and fixed twice — CLOSED #4088 "Delete 10
  '# REMOVED (Phase N)' breadcrumb comments in chunked_processor.py (+2 siblings)" and CLOSED #4293
  "REMOVED/Removed breadcrumb comments: #4088 fix incomplete + 1 new instance" — verified
  `chunked_processor.py`/`chunk_cache_manager.py`/`chunk_operations.py` themselves have NO regression,
  zero `REMOVED`/`removed (#` hits remain there. The 5 locations above are NEW instances in different
  files, not a regression of #4088/#4293.)
- **Effort**: trivial (<=30 min) total
- **Description**: Five comments across 4 files document a symbol that was deleted, phrased as
  "X removed (#NNNN) — reason", left behind purely as a historical footnote with nothing left to
  explain (the symbol is gone; only the comment remains). This is the exact recurring pattern
  #4088/#4293 already fixed twice in `auralis-web/backend/core/chunk_*.py` — it has regrown in
  `hooks/library/index.ts`, `hooks/player/index.ts`, `types/api.ts`, and `schemas.py`.
- **Evidence**:
  ```ts
  // hooks/library/index.ts:12-14
  // New hooks moved from root
  // #3645: useLibraryWithStats subsumes useLibraryData + useLibraryStats —
  // the deprecated hooks were removed (no remaining consumers).
  ```
  ```ts
  // hooks/player/index.ts:14-16, 23-30
  // usePlaybackState removed (#3126) — parallel WS-shadow state with no
  // production consumers. Use Redux selectors (playerSlice / queueSlice)
  // as the single source of truth for playback state.
  ...
  // usePlayerControls removed (#4387) — orphaned hook with zero production
  // consumers; togglePlayPause was a permanent {success:false} stub. Use
  // usePlaybackControl / play() / pause() directly.
  // #3776: usePlayerStreaming removed — was 475 lines of dead code with
  // zero production importers. ...
  ```
  ```ts
  // types/api.ts:141-144 (x3 more, same shape, #4372)
  // LibraryScanRequest/LibraryScanResponse removed (#4372) — diverged from the
  // backend contract (backend takes {directories: list[str]} and returns
  // ScanResultResponse) and had zero importers.
  ```
  ```python
  # schemas.py:227-229
  # processing_settings_* and ab_track_* removed (#4421): dead both
  # directions — the frontend never sent the inbound types nor subscribed
  # to the outbound ones, and the handlers were never triggered.
  ```
- **Impact**: Pure noise — each comment documents a decision that's already fully reflected by the
  symbol's absence; keeping them provides no more information than a `git log`/`git blame` on the
  line would, at the cost of file-reading overhead for every future maintainer.
- **Siblings**: All five explicitly grouped here as one finding (sibling detection rule).
- **Related**: CLOSED #4088, CLOSED #4293 (same pattern, different files — not a regression of
  either, since those two closed issues' actual target files are clean).
- **Suggested Fix**: Delete all 5 breadcrumb comments; the removal history is already in git log
  under the referenced issue numbers, which is the correct permanent record — not a source comment.

#### TD8-6: `LibraryManager.__init__`'s deprecation warning still makes the same unfulfilled-timeline promise the CLOSED #4314 fix addressed
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/library/manager.py:80-94`
- **Status**: Regression of #4314 (partial — see description)
- **Effort**: trivial (<=30 min)
- **Description**: #4314 ("LibraryManager 'DEPRECATED' migration-timeline promise unfulfilled 5
  versions later") was closed by commit `9091525e`, which rewrote the CLASS DOCSTRING to drop the
  unmet "v2.0.0+: Removal or minimal facade only" timeline claim, replacing it with "No removal
  version is committed; only __init__() emits a DeprecationWarning today (see #4314)". However, the
  actual runtime `warnings.warn(...)` call in `__init__` (a few lines below, NOT touched by that
  commit) still says verbatim: `"This class will be removed in v2.0.0."` — the identical unfulfilled
  promise the issue was about, just in the message users actually see at runtime instead of the
  docstring. `LibraryManager` is confirmed still the live production library manager (constructed at
  `auralis-web/backend/config/startup.py:210`, used across ~20 backend/engine files), so this warning
  fires on every real app startup.
- **Evidence**:
  ```python
  # manager.py:80 (docstring, FIXED by 9091525e)
  """Deprecated since v1.1.0. No removal version is committed; only
  __init__() emits a DeprecationWarning today (see #4314)."""

  # manager.py:88-94 (runtime warning, NOT touched by 9091525e — still makes the same claim)
  warnings.warn(
      "LibraryManager is deprecated. Use RepositoryFactory instead. "
      "See MIGRATION_GUIDE.md for migration instructions. "
      "This class will be removed in v2.0.0.",
      DeprecationWarning,
      stacklevel=2
  )
  ```
- **Impact**: Every production startup (and every test/script that constructs `LibraryManager`
  directly) emits a warning promising removal-by-v2.0.0 with no such removal plan actually committed
  — the same credibility/noise problem #4314 was filed to fix, just left live in the one place users
  (via stderr/logs) actually see it.
- **Siblings**: None.
- **Related**: #4314 (closed, partial fix).
- **Suggested Fix**: Either drop the "This class will be removed in v2.0.0" clause from the runtime
  message (matching the docstring's now-honest "no removal version is committed"), or — better,
  given this is a desktop-only app with no external API consumers per CLAUDE.md's own guidance on
  deprecation shims — commit to an actual removal by finishing the RepositoryFactory migration for
  the ~20 remaining call sites and deleting `LibraryManager` outright instead of perpetuating an
  unfulfilled warning indefinitely.


### Dimension 9: File / Function / Module Complexity

#### TD9-1: Nine FastAPI routers hide their entire route surface inside one 200–515-line `create_*_router()` closure factory
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/backend/routers/player.py:232` (`create_player_router()`, **515 LOC**), `routers/enhancement.py:89` (486), `routers/processing_api.py:137` (414), `routers/artwork.py:101` (307), `routers/metadata.py:67` (304), `routers/playlists.py:53` (284), `routers/similarity.py:86` (253), `routers/albums.py:25` (225), `routers/files.py:85` (209)
- **Status**: NEW (no open issue matches — grepped `create_.*_router`, "long function", "closure" against 159 open + 204 tech-debt issues)
- **Age**: pattern predates the #4075 router split series (2026-05-30); `player.py`'s factory survived every god-file pass
- **Effort**: large per router (>1 day) — decompose one router per PR
- **Description**: The project rule is <300 lines per **module**; these files satisfy it loosely but violate it catastrophically at **function** level, because every handler is a nested `async def` inside a single factory closure that captures `get_library_manager`, `get_audio_player`, etc. A 515-line function is not reviewable, and no individual handler can be imported or unit-tested without constructing the whole router.
- **Evidence**: `python -c` AST census over `auralis/` + `auralis-web/backend/` finds **72 functions >100 LOC**; the top 5 are all `create_*_router()` / `create_lifespan()` closures.
- **Impact**: Blocks per-handler unit testing, makes `git blame` and diffs on any single endpoint span the whole factory, and is the structural reason `#3838` (missing `response_model=`) and TD3-2 (`with_error_handling` non-adoption) both stalled on these exact files — closure-scoped handlers are awkward to decorate consistently.
- **Siblings**: `routers/artists.py:82` (161), `routers/tracks.py:33` (160), `routers/fingerprint_queue.py:29` (197), `routers/library_scan.py:30` (170).
- **Related**: #3838 (same routers, response_model axis); TD3-2 (same routers, error-handling axis); the closed #4075–#4083 god-file series never targeted function length inside routers.
- **Suggested Fix**: Split axis = **hoist handlers to module level** and replace closure capture with FastAPI `Depends()`, leaving `create_*_router()` as a ~10-line assembler that instantiates `APIRouter` and registers module-level handlers. Start with `player.py` (largest, and the one blocking two other tracked workstreams).

#### TD9-2: `config/startup.py::lifespan()` is a 439-line function nested inside a 467-line `create_lifespan()`
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/backend/config/startup.py:146-612`
- **Status**: NEW
- **Age**: file last restructured around the backend app-wiring split; the nesting predates it
- **Effort**: medium (<=1 day)
- **Description**: The entire application startup/shutdown sequence — library manager construction, processing engine, cache worker, background workers, fingerprint scheduler, WebSocket setup — is one linear 439-line async function inside a factory. The whole file is 612 LOC (2× the module limit).
- **Evidence**: AST census: `create_lifespan()` 467 LOC (`startup.py:146`), inner `lifespan()` 439 LOC (`startup.py:172`).
- **Impact**: Startup ordering bugs are the hardest class to diagnose here, and there is no seam to test a single subsystem's init in isolation. Directly relevant to CLOSED #4318 (services staying globally truthy when their background task fails after startup returns) — that failure mode is a symptom of one monolithic init with no per-subsystem boundary.
- **Siblings**: `auralis-web/backend/config/routes.py:44::setup_routers()` (237 LOC).
- **Related**: #4318 (CLOSED, same file, symptom of the same monolith).
- **Suggested Fix**: Split axis = **one `_init_<subsystem>()` / `_shutdown_<subsystem>()` pair per subsystem** (library, processing engine, cache, workers, fingerprint), each returning a teardown callable; `lifespan()` becomes an ordered list of those, which also gives #4318's "did this subsystem actually come up?" check a natural home.

#### TD9-3: The `>300 LOC` census is 102 Python + 43 non-test frontend modules, but only 8 are tracked — and four *closed* god-file issues left their files 2.3–2.7× over the limit
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: repo-wide; the largest untracked offenders are `auralis/core/processing/continuous_mode.py` (802), `auralis-web/backend/core/chunked_processor.py` (797), `auralis-web/backend/routers/player.py` (746), `auralis/player/enhanced_audio_player.py` (730), `auralis-web/backend/core/processing_engine.py` (681), `auralis/library/manager.py` (615), `auralis-web/backend/config/startup.py` (612), `auralis-web/backend/cache/manager.py` (585), `auralis-web/backend/monitoring/metrics_collector.py` (575), `auralis-web/backend/routers/enhancement.py` (574), `auralis-web/backend/routers/processing_api.py` (550)
- **Status**: NEW (the *census* is new; individual files below are deduped — see Related)
- **Age**: n/a (census)
- **Effort**: large (portfolio-level; decompose per file)
- **Description**: OPEN #4511 is titled *"8 untracked oversized modules"* and presents its list as the complete untracked set. Re-derived from the live tree, there are **102** Python files and **43** non-test TS/TSX files over 300 LOC. Separately, four *closed* split issues left their target still far over the limit: #4245 closed `chunked_processor.py` at 958 → now **797**; #4249 closed `enhanced_audio_player.py` at 821 → now **730**; #4250 closed `processing_engine.py` at 786 → now **681**; #4082/#4254 targeted methods in `continuous_mode.py`, which is still **802**. #4254's own title says it best: *"#4082's split relocated complexity, didn't remove it."*
- **Evidence**:
  ```
  $ find auralis auralis-web/backend -name '*.py' -exec wc -l {} + | awk '$1>300 && $2!="total"' | wc -l
  102
  $ find auralis-web/frontend/src \( -name '*.ts' -o -name '*.tsx' \) ! -path '*__tests__*' ! -name '*.test.*' \
      -exec wc -l {} + | awk '$1>300 && $2!="total"' | wc -l
  43
  ```
  Also: #4511's checklist item *"`auralis-web/frontend/src/services/RealTimeAnalysisStream.ts` — 628"* refers to a file that **no longer exists** (deleted in the dead-streaming-analysis cleanup, `c0088b42`) — the issue's checklist is 1/8 stale.
- **Impact**: The "8 untracked" framing understates the backlog by an order of magnitude, and the closed-issue pattern means "god-file split: done" in the issue tracker does not mean the file is under the limit. Any future audit that trusts #4511 as the census will under-report.
- **Siblings**: `auralis/library/repositories/track_repository.py` (906) and the other 7 in #4511.
- **Related**: OPEN #4511; CLOSED #4075–#4083, #4245, #4249, #4250, #4254, #4082. **Deduped, not re-filed**: `queue_service.py` (OPEN #4260), `hybrid_processor.py` (OPEN #4266), `helpers.py` (OPEN #4288), and the 8 in #4511.
- **Suggested Fix**: Update #4511's premise and checklist (drop the deleted `RealTimeAnalysisStream.ts` item, restate the real census), and adopt an explicit acceptance criterion for split issues: *close only when the file is under 300 LOC, otherwise re-scope*. Highest-value untracked next targets by size-and-churn: `continuous_mode.py`, `routers/player.py`, `config/startup.py`.

#### TD9-4: `ProgressBar.tsx` runs 23 hook calls in a 331-line component
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/frontend/src/components/player/ProgressBar.tsx`
- **Status**: NEW
- **Effort**: small (<=2 h)
- **Description**: 23 `useState`/`useEffect`/`useMemo`/`useCallback`/`useRef` calls in one component — drag state, hover preview, seek commit, and time formatting are all interleaved in a single render body. The component also exceeds the 300-line rule (331).
- **Evidence**: `grep -cE 'use(State|Effect|Memo|Callback|Ref|Reducer)\(' ProgressBar.tsx` → 23. Nearest sibling is `QueuePanel/QueuePanel.tsx` at 15.
- **Impact**: Its test file is 882 lines — the largest component spec in the repo — because there is no seam to test drag arithmetic independently of render.
- **Siblings**: `auralis-web/frontend/src/components/player/QueuePanel/QueuePanel.tsx` (15 hooks).
- **Related**: —
- **Suggested Fix**: Extract `useSeekDrag()` (pointer/drag arithmetic + commit) and `useHoverPreview()` into `src/hooks/player/`, leaving `ProgressBar.tsx` as presentation over two hook return values.

#### TD9-5: `design-system/primitives/index.ts` re-exports 38 symbols
- **Severity**: LOW
- **Dimension**: File/Function/Module Complexity
- **Location**: `auralis-web/frontend/src/design-system/primitives/index.ts`
- **Status**: NEW
- **Effort**: trivial (<=30 min)
- **Description**: 38 exports from one barrel — the only barrel in the repo over the 20-export guideline. A barrel this wide defeats tree-shaking granularity and makes it impossible to tell which primitives are actually consumed.
- **Evidence**: `grep -cE '^\s*export ' design-system/primitives/index.ts` → 38; no other `index.ts` in `src/` exceeds 20.
- **Impact**: Minor; mostly a discoverability/dead-export-detection tax (it hides unused primitives from `ts-prune`-style analysis).
- **Siblings**: none.
- **Related**: #4203 (`semantics.ts` token convention, OPEN) — same package, decide together.
- **Suggested Fix**: Group into sub-barrels by primitive family (layout / typography / surface / control) and re-export those four from `index.ts`.

---


### Dimension 10: Audit-Finding Rot

#### TD10-1: `_audit-common.md`'s Project Layout quotes four counts that no longer match the tree it tells auditors to trust
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:32-33,56`
- **Status**: NEW
- **Effort**: trivial
- **Description**: The shared audit protocol says *"Counts above were re-derived from the live tree when this file was last updated. If a finding depends on an exact number, recompute it"* — good hedging, but four of its numbers are now wrong, and other skills copy them verbatim into their own checklists:

  | `_audit-common.md` claim | Live |
  |---|---|
  | `config/routes.py` *"registers all 20 routers"* (line 32) | **21** |
  | *"20 registered routers"* (line 33) | **21** |
  | `tests/` *"~5,100 test functions (446 files)"* | 5,115 functions ✓, **395** files |
  | `tests/` *"across 18 dirs"* | **19** |
- **Evidence**: `grep -c include_router auralis-web/backend/config/routes.py` → 21; `find tests -name 'test_*.py' | wc -l` → 395; `ls -d tests/*/ | wc -l` → 19.
- **Impact**: `_audit-common.md`'s own Sibling Detection table tells auditors to *"derive the live list from `auralis-web/backend/config/routes.py`, not from a hardcoded count"* — while hardcoding 20 two lines earlier. `audit-tech-debt.md` Dimension 3 repeats *"20 registered routers"*. An audit that trusts it under-scopes router sibling sweeps by one router.
- **Siblings**: `.claude/commands/audit-tech-debt.md:139` (*"20 registered routers"*); `_audit-common.md:138`.
- **Related**: TD7-2 (`CLAUDE.md` has the same drift). The path-reference half of this problem is already solved by `_audit-validate.sh`; the count half is not.
- **Suggested Fix**: Add a count check to `_audit-validate.sh` (recompute router/repo/test/analysis totals and diff against the numbers in `_audit-common.md` and `CLAUDE.md`), so the same gate that keeps paths honest keeps counts honest.

#### TD10-2: OPEN #4511's checklist item for `RealTimeAnalysisStream.ts` refers to a deleted file
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: GitHub issue #4511 (frontend checklist item)
- **Status**: NEW
- **Effort**: trivial
- **Description**: #4511 lists *"`auralis-web/frontend/src/services/RealTimeAnalysisStream.ts` — 628"* as one of its 8 split targets. The file was deleted in `c0088b42` (*"refactor(frontend): delete dead export/streaming-analysis infrastructure"*), so 1 of the issue's 8 acceptance-criteria checkboxes can never be ticked and its "close when all 8 are under 300 LOC" criterion is unsatisfiable as written.
- **Evidence**: `find auralis-web/frontend/src -name 'RealTimeAnalysisStream*'` → no results.
- **Impact**: Blocks clean closure of the only open god-file tracking issue.
- **Siblings**: —
- **Related**: TD9-3 (which also disputes #4511's "8 untracked" premise).
- **Suggested Fix**: Edit #4511 to strike the deleted item and note it was resolved by deletion; restate the census per TD9-3.

**Checked and clean (Dim 10):** `.claude/commands/_audit-validate.sh` passes (592 refs / 25 skill files, 0 STALE). No skill file contains a stale `Existing: #NNNN` callout (there are no `#NNNN` refs in `.claude/commands/*.md` at all). Dimension-count claims are honest — `audit-tech-debt.md` has exactly 10 `### Dimension N` headings and its one `"all 9 dimensions"` string is the self-referential *example* in its own Dim 10 checklist, not a live claim. No report in `docs/audits/` is older than 90 days (oldest live: 2026-07-12).

---
