# Tech-Debt Audit — 2026-08-14

**Scope**: whole repo — `auralis/`, `auralis-web/backend/`, `auralis-web/frontend/src/`, `vendor/auralis-dsp/src/`, `tests/`, `docs/`, `.claude/commands/`
**Depth**: deep · **Dimensions**: all 10 · **Limit**: none
**Tree state audited**: `7e9c401f` (master, clean working tree, verified unchanged for the duration of the run)
**Dedup baseline**: 200 OPEN issues + 315 `tech-debt`-labelled issues (all states)

> **This report supersedes `docs/audits/AUDIT_TECH_DEBT_2026-08-13.md`**, which was generated
> against `188db72a` and never published as issues. All **13** of its findings were
> re-verified against the live tree and carried forward here with fresh evidence — none
> was dropped, and three were materially corrected (see *Corrections to the 2026-08-13
> report*). Publish **this** file; the 2026-08-13 file can be treated as history.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | **5** |
| LOW | **26** |
| **Total** | **31** |

| Provenance | Count |
|---|---|
| Carried forward from the unpublished 2026-08-13 report | **13** (all of them) |
| Genuinely new this run | **18** |
| Confirmed-present but already tracked on GitHub (not re-filed) | 19 |
| OPEN issues found already fixed by the tree (recommend closing) | 4 |

**Headline**: the product's own debt hygiene remains good — zero genuine marker debt in
shipped source, zero chunk-geometry literal bypasses, zero raw-hex design-token
violations, zero Rust `#[allow(dead_code)]`, a clean version string across all five
files that carry it, and zero stale path references in `.claude/`. **Four of the five
MEDIUM findings are in the audit tooling and project documentation, not the product.**

The dominant theme this run is **the meta-layer rotting faster than the code**. The
protocol file every audit skill loads first (`_audit-common.md`) currently instructs
auditors to cap severity on a package that runs on the main DSP pipeline; the
path-reference gate built to prevent exactly this class of drift has been red since
2026-08-07 and grew by 4 more stale refs in a single day; CLAUDE.md describes a package
deleted two days ago as live; and the marker-debt metric that CLAUDE.md quotes as a
project-health signal is scoped in a way that hides nine real markers. Meanwhile the only
product-side MEDIUM (**TD3-1**) is a fix that landed in seven routers and never reached
three others — including `player.py`, the most lock-contention-sensitive surface in the
backend.

### Direction vs. the Phase-1 baseline

Read the metric notes in `.claude/commands/audit-tech-debt.md` before quoting any of
these (#4564). Deltas are vs the 2026-08-13 run.

| Metric | 2026-08-13 | **2026-08-14** | Read |
|---|---|---|---|
| **markers, genuine (all src)** | 0 | **0** | The real marker debt in shipped source. **Zero is the expected and correct value** — a good result, not a suspicious one. But see **TD1-3**: this metric's scope excludes `tests/`, where 9 genuine markers live. |
| markers, raw (pre-filter) | 2 | 2 | Diagnostic only. Both individually verified false positives (a `#3xxx` issue placeholder in `auralis/analysis/fingerprint/schema.py:37`; the string `"0.xxxxxxxx…"` in a vitest spec). **Not debt** — never quote this as marker debt. |
| prose deferrals (non-test) | 9 | 9 | High recall / low precision — every hit was read individually, not quoted as a count. **4 are genuine deferrals**: 3 already tracked (#4243, #4239, #4405) and 1 untracked (TD1-1). The other 5 are ordinary prose (HTTP 503 message text, a `try/finally` toggle, "…not a workaround"). |
| NotImplementedError | 3 | 3 | All three in `auralis/library/scanner/duplicate_detector.py`, all deliberate (one docstring, one re-raise, one documented precondition guard from #4241). Re-verified. Not debt. |
| type: ignore (py) | 72 | **70** | −2. Whole-tree `mypy --warn-unused-ignores` found exactly **one** stale ignore (`auralis/analysis/mastering_profile.py:26`, already #4397). The 2026-08-13 report listed this metric as *Not Covered*; it is now covered and near-clean. |
| @ts-ignore / @ts-expect-error | 3 | 3 | All three in test files with justifying comments. Clean. |
| **'any' non-test (ts)** | 29 | **29** | The type-safety debt that ships. **14 of the 29 (48%) sit in `src/performance/`** — already-tracked dead code (#4696). Deleting that directory halves the shipped `any` surface. The remainder are legitimate generic constraints. Healthy. |
| 'any' raw incl. tests (ts) | 516 | 514 | Trend continuity only. Specs and mocks dominate. |
| skipped tests (py) | 59 | 59 | Composition analysed in full under TD6-2/TD6-3/TD6-4. |
| skipped tests (ts) | 2 | **18** | **+16 — this is a fix, not a regression.** #5119 (CLOSED HIGH, landed today) wrapped 15 fake integration-test files in `describe.skip` with per-file docstrings. Do not read this jump as new skip rot; see TD6-5 for what it *did* leave untracked. |
| **py files >300 LOC** | 105 | **108** | +3 in one day; 102 at #4673 (2026-07-25). Monotonically rising ~2/week. See TD9-1. |
| ts/tsx files >300 LOC | 127 raw / 36 prod | **127 raw / 36 prod** | Flat. The raw count includes specs — **36** is the production figure. Do not compare the two. |
| allow(dead_code) (rust) | 0 | **0** | Clean, re-verified across all 19 `.rs` files. |
| stale path refs (`_audit-validate.sh`) | 306 | **310** | +4 in one day. **All 310 in `docs/`; 0 in `.claude/`** (across 1,706 refs / 138 skill files). See TD7-2. |

### Verified clean (recorded so the next run can detect regression)

- **Chunk geometry**: zero literals bypass `auralis-web/backend/core/chunk_boundaries.py`. Every chunk count routes through the overlap-aware `content_chunk_count()`. `stream_normal.py:205`'s naive ceil is *not* a bypass — that path is intentionally non-overlapping, so the two formulas are identical when overlap is zero.
- **Design tokens**: zero real hardcoded hex/rgb in `auralis-web/frontend/src/components/`. The raw 173-file grep hit is a regex artefact — `#NNNN` issue references read as hex; requiring at least one `a-f` letter collapses it to 10 hits, all comments annotating a token's resolved value or documenting an already-removed literal. `src/theme/` has zero.
- **Version drift**: `auralis/version.py` (1.5.1) matches `package.json`, `desktop/package.json`, `auralis-web/frontend/package.json`, and `pyproject.toml`. `vendor/auralis-dsp/Cargo.toml` at 0.1.0 is an independently-versioned crate, not drift.
- **Router count**: `auralis-web/backend/config/routes.py` makes exactly **20** `include_router()` calls — matches every document that quotes it.
- **Consolidations holding**: DSP-stage `no_op()` bypass (#4298) across all 11 applicable stages; pagination `has_more` via `routers/pagination.py` across all 4 paginating routers; `MAX_LEVEL_CHANGE_DB` single definition (#4284); `cache/manager.py`'s PCM_16 chunk-size formula (#4238); `AlbumRepository`/`ArtistRepository` named eager-load option tuples (#5028 — appears already fixed).
- **Frontend component complexity**: exactly one production `.tsx` exceeds 14 hook calls (`ProgressBar.tsx`, and its 23 are memoisation on a drag surface, not multi-job sprawl). No custom-hook extraction is needed anywhere.
- **Barrel bloat**: exactly one module tree-wide exceeds 20 re-exports (`design-system/primitives/index.ts`, 38 — a deliberate catalogue). Zero Python `__init__.py` files exceed 20.
- **Test-hygiene cleanups that held**: #4246 (`test_summary_stats()` — 29 files → **0**); #5023 (bare `except Exception: pass` in test bodies → **0** residue); zero commented-out assertions in any real test (all 13 grep hits are in `src/test/TEMPLATE.example.tsx`, a scaffold); `WebSocketContext` auto-mocking correctly scoped — all 7 specs that should `vi.unmock()` do, and the other 20 correctly rely on the mock.
- **`WEBSOCKET_API.md`**: its 35-member `WebSocketMessageType` union matches `types/ws/registry.ts` member-for-member; chunk-duration prose matches `chunk_boundaries.py`. #4988/#4991 holding.
- **No-Variants**: repo-wide sweep found no genuine copy-of-X violations. `enhanced_audio_player.py`, `advanced_dynamics.py`, `stream_enhanced.py`, the `useEnhanced*.ts` family and `NewArtistsTab.tsx` are all product-feature names, not version variants.
- **No audit report in `docs/audits/` is older than 90 days** (oldest: 2026-07-12), so the >90-day triage-completeness check has an empty input set — a genuinely clean result, not an unchecked one.
- **Dimension-count honesty**: `audit-tech-debt.md` defines exactly 10 `### Dimension` headers and both it and `audit-suite.md:41` say "10". Self-consistent.

### Corrections to the 2026-08-13 report

Three of yesterday's claims did not survive re-verification and are corrected here rather
than repeated:

1. **`tests/validation/` did not grow.** Yesterday counted 13 `validate_*.py` files / 2,168 LOC; this run's Dim-2 agent counted all 20 `.py` files / 3,628 LOC and framed the difference as growth. `git ls-tree 188db72a -- tests/validation` returns **20 files** — the directory is byte-identical between the two commits. The correct figure is 13 `validate_*.py` (2,168 LOC) **+ 7 `test_*.py` (1,460 LOC) = 20 files / 3,628 LOC**, unchanged. The genuinely new information is the 7 `test_*.py` files, not any growth (TD2-3).
2. **The four "prematurely closed" god-file issues are OPEN.** Yesterday's Top-5 Medium Investment #5 repeated the skill file's claim that #4245/#4249/#4250/#4254 "were closed in 2026-07 with their targets still 2.3–2.7× over the limit." All four have `closedAt: null` — they were reopened once #4673's acceptance criterion was adopted. The criterion worked; recommending it again as a medium investment was spurious (TD10-2).
3. **The sidecar checksum prose deferral is tracked.** Yesterday classified `auralis/library/sidecar_manager.py:142-143` as ordinary prose. It is a genuine deferral and is already **#4405 (OPEN)** (TD1-1 siblings).

---

## Top 10 Quick Wins

Trivial/small effort, immediate payoff.

| # | Finding | Effort | Payoff |
|---|---|---|---|
| 1 | **TD10-1** — delete the false "no production importers" claim from `_audit-common.md:23,81` | trivial | Stops **every** audit capping severity on live DSP-pipeline code |
| 2 | **TD7-1** — drop the `parallel/` + `parallel_processor.py` rows from CLAUDE.md's Codebase Map and `docs/architecture/module-map.md:56` | trivial | CLAUDE.md stops describing a directory deleted two days ago as live |
| 3 | **TD7-3** — correct `CLAUDE.md:68` and `_audit-common.md:94`: the backend pytest baseline **is** checked in and CI-enforced (and `_audit-common.md:89` already says so) | trivial | Removes a self-contradiction that already cost one audit a turn; closes #4974 |
| 4 | **TD1-3** — add `tests` to `SRC_DIRS` in `audit-tech-debt.md:76` and amend CLAUDE.md Principle 5's scope | trivial | Makes the "zero marker debt" health signal honest; surfaces 9 hidden markers |
| 5 | **TD2-2** — `rm -r auralis/library/caching/` (empty package, `__all__ = []`) | trivial | −1 phantom package; closes the last #4915 residue |
| 6 | **TD8-3 / TD8-4 / TD8-5** — delete `announceFocus()`, the `PlayEnhanced` type alias, and `QueueController.tracks` | trivial | Three zero-consumer compat survivors in an app with nobody to be compatible for |
| 7 | **TD2-6** — delete `DebugInfo.tsx` + `useCommitId.ts` + the barrel re-export | trivial | −76 LOC of unreachable UI; removes a second commit-id code path |
| 8 | **TD10-2** — add "(and were reopened once this criterion was adopted)" to `audit-tech-debt.md:246` | trivial | Stops the skill file's motivating anecdote generating spurious recommendations |
| 9 | **TD7-6 / TD7-7** — add `backend-tests.yml` to `TESTING_GUIDELINES.md`'s workflow list; add `--python-preference only-managed` to `README.md:152` | trivial | Two authoritative docs stop contradicting CLAUDE.md on CI and on venv setup |
| 10 | **TD6-2** — delete the `/api/library/search` skip; add an issue ref to the three "Known limitation" skips | trivial | Every remaining skip becomes traceable |

Runner-up: **TD2-1** (move `WAVEncoderError` into `core/encoding/`, delete
`auralis-web/backend/encoding/`) — small rather than trivial, but it removes 112 LOC and
three fragile bare `from encoding.…` `sys.path` imports, and collapses #3912 to a
one-file change.

## Top 5 Medium Investments

1. **TD3-1 — propagate #4018's error-handling fix to `player.py`, `enhancement.py`, `cache_streamlined.py` (29 sites).** The only product-side MEDIUM. `player.py` alone has 19 hand-rolled `except Exception → HTTP 500` blocks, more than `playlists.py` had before #4018 fixed it; each one loses the `OperationalError → 503` mapping on the backend's most lock-contention-sensitive surface. Mechanical: apply the existing `@with_error_handling` decorator. **Do TD9-2 first or alongside** — the 19 sites are all inside one 518-line function, so there is currently no per-handler seam to decorate.
2. **TD7-2 — get `_audit-validate.sh` back to a meaningful exit code.** Split it: hard-fail on `.claude/**` (already green at 0/1,706 — wire it into CI today) and emit a shrink-only tracked baseline for `docs/**`, mirroring the `test-baseline.json` ratchet the project already runs twice. Until then the gate cannot distinguish new rot from the 310-and-growing backlog, and TD7-1 is a worked example of new rot it failed to surface.
3. **TD9-1 / TD9-2 — re-scope #4511 against the live 108-file census and attack the router factories.** The Python census is moving away from the <300 rule (~2 files/week; `startup.py` alone added 161 LOC in a day). File one issue per file for the **top 5 only**, each carrying #4673's acceptance criterion, and add the census to a tracked ratchet. Separately, converting `create_<name>_router()` factories to module-level handlers + `Depends()` is the change that makes both the LOC issues and TD3-1 closable.
4. **TD6-3 / TD6-4 — file the follow-up issues that #4548 and #4269 explicitly deferred.** Closing those two meta-issues fixed marker hygiene and left 16 real defects with no tracking: 5 API-signature drifts, 9 `HybridProcessor` pickling failures, and — most importantly — a genuine `play_count` lost-update race in `TrackRepository.record_play` that #4548's own closing comment called "a product change worth its own issue" and nobody filed. Route TD6-4 to `/audit-concurrency` for scoping.
5. **TD8-1 — rename `library_manager` → `library_database` across 29 files / 118 references** and rewrite the four present-tense docstrings describing a class deleted three weeks ago. Mechanical, `mypy`-guarded, and it closes #4312 and de-fangs #5031 as side effects. This is the single largest source of false grep leads in the backend.

---

# Findings

## MEDIUM

### TD10-1: `_audit-common.md` tells every auditor that a live DSP-pipeline package is dead code — and the claim is broader than previously recorded
- **Severity**: MEDIUM *(promotion: stale audit baseline that has misled an audit in the last 90 days)*
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/_audit-common.md:23`, `.claude/commands/_audit-common.md:81`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD10-1)** — re-verified at `7e9c401f`: still present, unchanged, and **understated**
- **Age**: `188db72a` 2026-08-13 (introduced yesterday)
- **Effort**: trivial
- **Description**: The shared protocol file every audit skill loads first asserts that `auralis/optimization/` has no production importers, and instructs auditors to cap severity there on that basis. The assertion is false. This run found **two** production importers where the 2026-08-13 report found one — and one of them is a module the file's own inventory does not list.
- **Evidence**:
  ```
  _audit-common.md:23  "…performance_optimizer.py. NO production code imports this package —
                        the only importers are tests. … Treat the remainder as
                        unreferenced-by-runtime: a bug here has no user-visible blast radius,
                        so cap severity accordingly…"
  _audit-common.md:81  "The rest of `auralis/optimization/` survives but is imported only by tests."
  ```
  Contradicted at `7e9c401f`:
  ```
  auralis/core/hybrid_processor.py:26   from ..optimization.performance_optimizer import get_performance_optimizer
  auralis/dsp/utils/spectral.py:221         from ...optimization.rust_integration import try_import_rust_module
  ```
  `hybrid_processor.py` — the main DSP pipeline per CLAUDE.md's own Codebase Map — is worse than a plain importer: `_apply_module_optimizations()` (line 513) is **called unconditionally at module-import time** (line 557), constructing the `PerformanceOptimizer` singleton and wrapping `AdaptiveMode.process` in a profiling decorator that then runs on every real mastering call. `performance_optimizer.py:27-33` pulls in `SIMDAccelerator`, `SmartCache`, `PerformanceConfig`, `MemoryPool` and `PerformanceProfiler`, so **every submodule named in the line-23 inventory is transitively live**. `rust_integration.py`, the second importer's target, is not in that inventory at all.
- **Impact**: Severity suppression at the protocol level. A CRITICAL DSP bug in `SmartCache` or `MemoryPool` — or a thread-safety bug in the double-checked-locking singleton — would be written up as LOW tech debt by any audit that follows the instruction. The second-order cost is already measurable: this run's Dimension 2 agent spent part of its budget independently rediscovering and re-evidencing this finding as NEW, because it was written down yesterday and never published.
- **Siblings**: The newest member of a recurring family of false/stale `_audit-common.md` prose claims — #4979, #4974 (OPEN), #4922, #4685, #4067, #4066, #4065, #5045 (OPEN), #5044 (OPEN). The file has automated verification for its **backticked paths** only (`_audit-validate.sh`), never for its prose assertions. **Note the mirror-image error**: CLAUDE.md makes the *opposite* mistake about the same package (TD7-1), describing a subdirectory deleted two days ago as live.
- **Related**: #4565 (CLOSED — the deletion this over-generalized from; `parallel/` *was* dead, the rest is not). Route any actual bug in `auralis/optimization/` to `/audit-engine`. Reported independently this run as Dim 2's TD2-5; merged here, counted once.
- **Suggested Fix**: Replace line 23 with the factual statement (`performance_optimizer.py` ← `hybrid_processor.py`, applied at import time; `rust_integration.py` ← `dsp/utils/spectral.py`; both pull in `acceleration/`, `caching/`, `config.py`, `memory/`, `profiling/` — treat the package as live engine code) and amend line 81 the same way. Then extend `scripts/check_doc_counts.py` (or a sibling gate) with an importability assertion so "no production importers" becomes machine-checked. **The text edit alone does not break the recurrence chain — the gate does.**

### TD7-2: The path-reference gate is still red on every run, and the `docs/` backlog it cannot clear grew by 4 more refs in one day
- **Severity**: MEDIUM *(promotion: stale doc baseline that has misled an audit in the last 90 days — the detection mechanism itself is inert)*
- **Dimension**: Stale Documentation
- **Location**: `.claude/commands/_audit-validate.sh:103-126`, `.claude/commands/audit-tech-debt.md:68`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD7-1)** — re-verified; count moved 306 → 310
- **Age**: `06b9d0aa` 2026-08-07 (the #4984 widening to `docs/`); never re-greened
- **Effort**: medium (310 refs, mostly mechanical) — or small, if the historical planning trees move to `docs/archive/` first
- **Description**: #4984 widened the gate from 11 docs files to ~13 glob patterns across `docs/`. No cleanup pass followed, so the gate reports **310 stale backticked path refs and exits 1 on every invocation**. Because it can never pass, `audit-tech-debt.md:68` invokes it as `… || true`, and it is wired into **no** CI workflow. A gate that always fails and whose failure is always swallowed cannot distinguish new rot from old — the entire function it was built for (#4052, #4063, #4258).
- **Evidence**:
  ```
  $ .claude/commands/_audit-validate.sh; echo $?
  Checked 1706 refs across 138 skill files.
  Checked 237 markdown links across 11 doc files.
  FAIL: 310 stale path reference(s).
  1

  $ grep -c '^STALE:' /tmp/.../validate.txt          → 310
  $ grep '^STALE: \.claude' /tmp/.../validate.txt | wc -l → 0
  $ grep -RIn 'audit-validate' .github/workflows/    → (no matches)
  ```
  **51 files hold all 310** (up from "40 files hold all 306"). Top offenders: `docs/features/cache-system/CACHE_AND_CHUNKING_AUDIT.md` (22), `docs/frontend/PHASE1_2_3_LAUNCH_CHECKLIST.md` (21), `docs/frontend/analysis/PLAYER_COMPONENT_CONSOLIDATION_PLAN.md` (20), `docs/UI_DESIGN_GUIDELINES.md` (20), `docs/ui_audit/IMPLEMENTATION_STATUS.md` (16). Four hits were sample-verified as **true positives**, not noise (`auralis/dsp/stages.py`, `streamlined_cache.py`, `EnhancedButton.tsx` all genuinely absent; `scripts/sync_version.py` is actually at repo root).
- **Impact**: The one structural defence against path drift is disabled, and this run supplies the proof: **TD7-1** (CLAUDE.md describing a directory deleted 2026-08-12 as live) is exactly the class of drift the gate exists to catch, and it landed and survived during the window the gate has been silently failing. No auditor is alerted when a new stale ref appears, because the exit code is identical before and after.
- **Siblings**: `.claude/` holds **0** stale refs across 1,706 checked — the skill-file half of the gate is genuinely clean and worth preserving as a separate, green, CI-enforced check.
- **Related**: #4547 (CLOSED, 128 refs), #4984 (CLOSED, the widening that caused this), #4052 / #4063 / #4258 (the recurrences the gate was built to stop).
- **Suggested Fix**: Split the gate into two exit codes — hard-fail on `.claude/**` (green today; put it in CI now) and a tracked shrink-only baseline count for `docs/**`, mirroring the ratchet the project already runs for both test suites. Then fix or de-backtick the 310; ~85 sit in five historical planning trees (`docs/ui_audit/`, `docs/frontend/PHASE*`, `docs/frontend/analysis/`) that arguably belong under `docs/archive/` and out of the gate's scope entirely.

### TD7-3: CLAUDE.md and `_audit-common.md` still say the backend pytest baseline does not exist — the file was updated again today, and `_audit-common.md` now contradicts itself
- **Severity**: MEDIUM *(promotion: stale doc baseline that has misled an audit in the last 90 days — #4974 documents it misdirecting a concurrent backend audit)*
- **Dimension**: Stale Documentation
- **Location**: `CLAUDE.md:68`, `.claude/commands/_audit-common.md:94` — self-contradicted by `_audit-common.md:89`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD7-2)**; also overlaps **#4974 (OPEN)**, which files the internal contradiction from the opposite direction
- **Age**: `pytest-baseline.json` first tracked `003c9312` 2026-08-12; **most recently updated `f59b4901` 2026-08-14 (today)**
- **Effort**: trivial
- **Description**: `CLAUDE.md:68` still reads *"`pytest-baseline.json` does not exist yet, so `backend-tests.yml` cannot pass until one is generated from a real run."* `_audit-common.md:94` still reads *"…(it is not tracked yet)"* with the filename de-backticked per the project's own "this path doesn't resolve" convention — so the convention is itself now carrying a false signal. Both are wrong, and `_audit-common.md` contradicts itself **within the same section**: line 89 says "the baselines are checked in and CI-enforced"; line 94, two rows down, says the backend one is not tracked. The file is not merely tracked — it is actively maintained, having been updated today.
- **Evidence**:
  ```
  $ git ls-files pytest-baseline.json               → pytest-baseline.json
  $ git log -1 --format='%h %ci' -- pytest-baseline.json
  f59b4901 2026-08-14 10:05:00 -0300

  _audit-common.md:89  "…the baselines are checked in and CI-enforced."
  _audit-common.md:94  "*pytest-baseline.json* … (it is not tracked yet)"
  CLAUDE.md:68         "`pytest-baseline.json` does not exist yet…"
  ```
- **Impact**: A contributor following CLAUDE.md literally would regenerate a baseline **from a local run** — which the same CLAUDE.md section explicitly warns against ("Generate a baseline from a CI artifact, not a local run") — and overwrite a good CI-derived baseline with a worse one. That is a real footgun, not cosmetic rot. #4974 additionally records that this section already cost a concurrent backend audit a turn re-deriving ground truth.
- **Siblings**: Same dual-maintenance hazard as the structural counts (#4982 class): CLAUDE.md and `_audit-common.md` hold independent copies of the same fact and drift apart when only one is edited.
- **Related**: #4974 (OPEN — closeable in the same change), #4562, #4640.
- **Suggested Fix**: Update `CLAUDE.md:68` and `_audit-common.md:94` in one edit to match line 89, re-backtick `pytest-baseline.json` now that the path resolves, and close #4974 noting the tree overtook it in both directions.

### TD3-1: The #4018 raw-`except Exception` → HTTP 500 pattern survives in three routers #4018 never touched — `player.py` is now the worst offender in the codebase
- **Severity**: MEDIUM *(promotion: duplicated logic with divergent bug-fix history — the fix landed in one copy and not the others)*
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/player.py` (**19 sites**: 342-349, 420-428, 460-466, 488-494, 507-510, 519-522, 544-547, 563-567, 619-623, 633-636, 645-648, 657-660, 669-672, 681-684, 693-696, 708-711, 733-736, 748-752, 760-764), `auralis-web/backend/routers/enhancement.py:296-298,356-358,414-416,428-430,529-531` (5), `auralis-web/backend/routers/cache_streamlined.py:95-98,131-134,142-145,167-170,203-206` (5). Reference implementation (correct): `auralis-web/backend/routers/dependencies.py:151-218` (`with_error_handling`), `auralis-web/backend/routers/errors.py:118-145` (`handle_query_error`)
- **Status**: NEW — distinct scope from CLOSED #4018, whose evidence names only `playlists.py`, `library.py`, `similarity.py`, `albums.py`, `artwork.py`, `metadata.py`, `settings.py` (all seven confirmed migrated at `7e9c401f`)
- **Age**: `player.py`'s catch-alls predate #4018 (2026-05-30) and were never migrated; `handle_query_error` has existed since #3222/#4018 (2026-07-08)
- **Effort**: small (decorator + import swap, identical to the #4018 migration)
- **Description**: `errors.py::handle_query_error()` maps `sqlalchemy.exc.OperationalError` (transient SQLite lock/busy) to a **retryable HTTP 503** and everything else to 500 — the fix #3222 made and #4018 propagated to seven routers via `@with_error_handling`. Three routers still hand-roll `except Exception: raise HTTPException(status_code=500, …)`, losing the 503 mapping entirely. This is the textbook divergent-bug-fix-history shape: the fix exists in one place and 29 call sites bypass it.
- **Evidence**:
  ```python
  # routers/player.py:342-349 — one of 19 identical shapes
  except ValueError as e:
      raise HTTPException(status_code=503, detail=str(e))
  except Exception:
      logger.error("Failed to get player status", exc_info=True)
      raise HTTPException(status_code=500, detail="Failed to get player status")

  # routers/errors.py:118-145 — the fix these 29 sites bypass
  def handle_query_error(operation: str, error: Exception) -> NoReturn:
      from sqlalchemy.exc import OperationalError
      if isinstance(error, OperationalError):
          raise ServiceUnavailableError(f"Database temporarily unavailable during {operation}")
      raise InternalServerError(operation, error)
  ```
  Adoption at `7e9c401f` (`grep -c with_error_handling`): `player.py`=**0**, `enhancement.py`=**0**, `cache_streamlined.py`=**0**, vs `playlists.py`=8 and >0 in `albums.py`, `artists.py`, `artwork.py`, `metadata.py`, `settings.py`, `similarity_common.py`, `processing_api.py`. `tracks.py` calls `handle_query_error()` directly at all 6 of its REST catch sites — correct, not a sibling. `system.py` / `library_scan.py`'s `except Exception` blocks are WebSocket-lifecycle handlers, not HTTP response paths — not siblings either.
- **Impact**: `player.py` backs playback, queue, and transport — the most latency- and lock-contention-sensitive surface in the backend (player `RLock` + library session pooling). A transient `OperationalError` there is exactly the scenario #3222 was filed to make retryable, and it is now the *least* protected router (19 unmapped sites vs `playlists.py`'s 8 before its fix). Any future change to the status mapping must be hand-applied to 29 sites instead of one function.
- **Siblings**: None beyond the three routers — confirmed across all 27 files in `auralis-web/backend/routers/`.
- **Related**: #4018 (CLOSED — this is its unfinished half), #3222 (the underlying `OperationalError` → 503 fix), **TD9-2** (all 19 `player.py` sites live inside one 518-line factory function, so there is no per-handler seam to decorate — sequence these together).
- **Suggested Fix**: Apply `@with_error_handling("<operation>")` from `routers/dependencies.py` to the 19 `player.py` endpoints and the 10 in `enhancement.py`/`cache_streamlined.py`, mirroring the `playlists.py`/`artists.py` migration #4018 already performed. No new code — decorator, import, and deletion of the redundant `try/except`.

### TD1-3: The `markers, genuine = 0` metric excludes `tests/`, where all 9 remaining genuine markers live — and 7 of them cite CLOSED issues
- **Severity**: MEDIUM *(promotion: stale audit baseline that has misled an audit in the last 90 days — it produced the 2026-08-13 report's headline claim yesterday)*
- **Dimension**: Stale Markers *(also Audit-Finding Rot)*
- **Location**: `.claude/commands/audit-tech-debt.md:76` (the `SRC_DIRS` definition), `CLAUDE.md` Principle 5, and the 9 markers below
- **Status**: NEW
- **Age**: the `SRC_DIRS` scope dates from the #4564 rewrite (2026-07-25); the oldest marker it hides is `b2be372ac` 2025-11-24
- **Effort**: trivial (fix the grep) + small (triage the 9 markers)
- **Description**: `SRC_DIRS` is `(auralis auralis-web/backend auralis-web/frontend/src vendor/auralis-dsp/src)` — `tests/` is not in it. So `markers, genuine = 0` is true within its scope but is read repo-wide: CLAUDE.md Principle 5 states "Genuine marker debt is currently **0**" as a project-health claim, and the 2026-08-13 report's headline asserted "genuine marker debt is **zero**". Nine genuine markers sit one directory over, and **seven cite issues that are now CLOSED** — precisely the Dim-1 condition "a marker citing a CLOSED issue has outlived its driver (delete or reopen)".
- **Evidence**:
  ```
  $ grep -RIniE '(TODO|FIXME|HACK|XXX)\b' tests --include='*.py' | grep -viE "$MARKER_FP"
  tests/test_yin_rust_validation.py:153             # TODO: Call Rust version when available   (bare — TD1-2)
  tests/backend/test_playlist_integration.py:377    # TODO(#4915): playlist search was never implemented …
  tests/backend/test_boundary_data_integrity.py:555 # TODO(#4915): the '/nonexistent/file.wav' rejection …
  tests/backend/test_boundary_advanced_scenarios.py:652 # TODO(#4915): nothing validates on-disk existence …
  tests/backend/test_boundary_advanced_scenarios.py:807 # TODO(#4915): if "exactly one delete wins" …
  tests/backend/test_database_migrations.py:309     # … TODO(#5023): LibraryDatabase.__init__ …
  tests/performance/test_phase5d_example.py:75      # TODO(#5023): could not fully confirm …
  tests/validation/validate_blind_guardian_comprehensive.py:151  # TODO(#5023): could not fully rule out …

  #4915  CLOSED   #5023  CLOSED
  ```
  The four `TODO(#4915)` markers landed in `aacb4d53a` 2026-08-07 — **after** #4915 closed on 2026-07-29. They use the issue number as *provenance* ("found while doing #4915") rather than as a tracking issue, so no open item will ever drive them. The three `TODO(#5023)` markers are the same pattern. Separately: **zero** well-formed `TODO(#NNNN)` markers exist anywhere under `auralis/`, `auralis-web/`, or `vendor/` — every adopter of the mandated convention is in `tests/`.
- **Impact**: The two documents an agent reads first (CLAUDE.md; each fresh tech-debt report) state a repo-wide "zero marker debt" that is scope-limited, so a marker sweep concludes there is nothing to triage while 7 markers point at closed issues and 1 has been stale for 9 months. This is #4564's failure mode one iteration later, in the opposite direction — a metric definition producing a systematically misleading number, now understating rather than overstating.
- **Siblings**: The same `SRC_DIRS` array scopes `prose deferrals`, `'any' non-test`, and both `>300 LOC` censuses in the same baseline block, so any conclusion drawn about `tests/` from those numbers is equally out of scope. (The skipped-test metrics do target `tests/` and are unaffected.)
- **Related**: #4564 (CLOSED — the prior metric-definition fix), #4915 / #5023 (CLOSED — the cited issues), TD1-2, #5033 / #5045 (the CLAUDE.md dual-maintenance family).
- **Suggested Fix**: Add `tests` to `SRC_DIRS` at `audit-tech-debt.md:76` — or emit a second `markers, genuine (tests)` line so the two stay separable — and amend CLAUDE.md Principle 5 to scope its claim to `auralis/`, `auralis-web/` and `vendor/`. Then triage the 9: re-tag the four `TODO(#4915)` and three `TODO(#5023)` markers against newly-filed follow-up issues (they describe real untested behaviour) or delete them, and resolve TD1-2 by wiring up the Rust call.

---

## LOW

### Dimension 1 — Stale Markers

### TD1-1: `get_allowed_directories()` records a deferral as prose instead of `TODO(#NNNN)`
- **Severity**: LOW
- **Dimension**: Stale Markers
- **Location**: `auralis-web/backend/security/path_security.py:85-87`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD1-1)** — re-verified: byte-identical, unchanged since 2026-02-14
- **Age**: `7163b5306` 2026-02-14 (~6 months)
- **Effort**: trivial
- **Description**: Genuine marker debt in shipped source is zero, which is the convention working. Its counterpart — that deferrals be written as `# TODO(#NNNN):` — has one unmet case in src: a security-relevant function whose deferral is invisible to every marker sweep.
- **Evidence**:
  ```python
  # auralis-web/backend/security/path_security.py:85-87
  Note:
      In production, this should read from configuration.
      For now, we default to user's home directory and standard music folders.
  ```
- **Impact**: The allow-list backing path containment is hardcoded and the intent to make it configurable is recorded where no marker sweep can find it — the exact invisibility #4564 was filed about. Low product impact (desktop-only, localhost-bound, `_extra_allowed_dirs` already accepts runtime scan folders).
- **Siblings**: Re-classified prose-deferral hits at `7e9c401f` — `auralis/library/scanner/scanner.py:470` = **#4243 (OPEN)**; `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:102` = **#4239 (OPEN)**; `auralis/library/sidecar_manager.py:142-143` = **#4405 (OPEN)** *(yesterday mis-classified this as ordinary prose; `SidecarManager.compute_checksum()` at line 359 additionally has **zero callers repo-wide**, so the deferral and the orphaned method are one item)*. The remaining 5 hits (`routers/errors.py:20,21,143` HTTP-503 message text; `core/audio_processing_pipeline.py:188`, a `try/finally` set/restore, not a deferral; `useEnhancementControl.ts:269` "…not a workaround") are **ordinary prose, not debt**.
- **Related**: #4564 (CLOSED). Route any containment-bypass concern to `/audit-security`.
- **Suggested Fix**: Either file an issue for config-driven allowed directories and rewrite the note as `# TODO(#NNNN): read the allow-list from UnifiedConfig`, or — since `_extra_allowed_dirs` already covers the real use case — delete the "In production, this should…" sentence as an intention nobody holds.

### TD1-2: `test_yin_rust_validation.py` validates librosa against itself — the marker driving it expired when the PyO3 bindings shipped
- **Severity**: LOW
- **Dimension**: Stale Markers *(overlaps Test Hygiene; filed here because the expired marker is the driver)*
- **Location**: `tests/test_yin_rust_validation.py:151-158` (marker at :153); 361 LOC / 8 collected tests
- **Status**: NEW
- **Age**: `b2be372ac` 2025-11-24 — **~9 months**, the oldest live marker in the tree
- **Effort**: small
- **Description**: A bare `# TODO: Call Rust version when available` with no issue number, whose stated precondition has been met for months. The Rust `yin` is exposed at the PyO3 boundary (`vendor/auralis-dsp/src/py_bindings.rs:147` `yin_wrapper`, registered line 32). Meanwhile `YinValidator.test_audio_file()` assigns `f0_rust = f0_librosa` and then "compares" them, so every correlation the file computes is `corr(x, x)`.
- **Evidence**:
  ```python
  # tests/test_yin_rust_validation.py:151-158
  # For now, Rust implementation is still in Python via librosa
  # This will be updated in Phase 5 when PyO3 bindings are added
  f0_rust = f0_librosa  # TODO: Call Rust version when available
  rust_stats = self.analyze_f0_contour(f0_rust)
  comparison = self.compare_f0_contours(f0_librosa, f0_rust)
  ```
  The file is collected (`pytest.ini`: `python_files = test_*.py`, `testpaths = tests`, not in `norecursedirs`). Its downstream tests assert only `np.isfinite(...)` on the **librosa** stats (`:314-316`, `:334-336`), so nothing here would fail if the Rust `yin` were deleted outright. Only `test_yin_compilation` (line 203) touches the Rust module at all.
- **Impact**: A collected, green, 361-LOC suite named "rust validation" provides zero validation of the Rust DSP module while reading as coverage in every directory listing and every "is the Rust port tested?" search — in exactly the subsystem where a wrong dtype/shape at the PyO3 boundary is a HIGH-severity class per `_audit-severity.md`.
- **Siblings**: No other `tests/*rust*` file exercises `yin`.
- **Related**: #4123 (OPEN — the other Rust-side deferral), #4533 (the port that made the bindings available), TD1-3. Route any actual YIN numeric discrepancy to `/audit-engine`.
- **Suggested Fix**: Replace `f0_rust = f0_librosa` with a real `auralis_dsp.yin(...)` call and assert `comparison['correlation']` against a threshold; or, if the Rust/librosa contract is not worth pinning, delete the file and fold `test_yin_compilation` into an existing Rust-boundary test. Either way the marker goes — its precondition is satisfied.

### Dimension 2 — Dead Code & Unused Surface

### TD2-1: `auralis-web/backend/encoding/` survives only to host one exception class
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/encoding/wav_encoder.py:35-90`, `auralis-web/backend/encoding/__init__.py:11-16`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD2-1)** — re-verified unchanged
- **Age**: `a0179495` 2026-08-07 (last touched); predates the `core/encoding/` replacement
- **Effort**: small
- **Description**: `encode_to_wav()` has zero production callers — its own comment says so. Every remaining consumer is a test. The package stays alive only because `WAVEncoderError` is defined in it, and three live modules reach that exception through a bare `from encoding.wav_encoder import …` absolute import that resolves only because `pytest.ini`/uvicorn put `auralis-web/backend` on `sys.path`.
- **Evidence**:
  ```
  auralis-web/backend/core/processing_engine.py:68     from encoding.wav_encoder import WAVEncoderError
  auralis-web/backend/core/encoding/wav_encoder.py:18  from encoding.wav_encoder import WAVEncoderError
  auralis-web/backend/core/chunked_processor.py:66     from encoding.wav_encoder import WAVEncoderError
  ```
  `encode_to_wav` callers repo-wide: `tests/backend/test_encode_to_wav_nonfinite_guard_4672.py`, `tests/backend/test_absolute_path_log_hygiene.py` — tests only.
- **Impact**: 112 LOC of maintained-but-unreachable code that has absorbed real fix effort as recently as #4672 (a NaN guard added to a function nothing calls). The bare `from encoding.…` imports break the moment anything runs from a different working directory or is packaged differently — the exact failure mode the 2026-03 PyInstaller packaging regression exhibited.
- **Siblings**: `auralis-web/backend/core/encoding/wav_encoder.py` (260 LOC, class-based) is the live implementation. `_audit-common.md:42` frames the pair as two live implementations; only one is live.
- **Related**: #4919 (CLOSED — fixed error typing in the *live* copy), #4895, #4672, #3872 (effort spent on the dead copy), **#3912 (OPEN** — `WAVEncoderError` unmapped in the global handler; fixing this first makes that a one-file change**)**.
- **Suggested Fix**: Move `class WAVEncoderError` into `auralis-web/backend/core/encoding/wav_encoder.py`, re-export from `core/encoding/__init__.py`, repoint the three importers to `from core.encoding import WAVEncoderError`, then delete `auralis-web/backend/encoding/` and its two dedicated tests. Update `_audit-common.md:42` in the same change.

### TD2-2: `auralis/library/caching/` is an empty package left behind by #4915
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/library/caching/__init__.py:1-9`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD2-2)** — re-verified unchanged
- **Age**: `2ff696c9` 2026-02-13 (last content change); emptied by #4915 on 2026-07-29
- **Effort**: trivial
- **Description**: The package contains nothing but a docstring and `__all__ = []`. The cache layer it wrapped was deleted with `LibraryManager` in #4915; the directory was left behind. Zero importers anywhere in the tree.
- **Evidence**:
  ```python
  """
  Caching Layer for Auralis Library
  Provides caching infrastructure for queries and persistent storage.
  DSP-related caches have been removed post-Rust migration.
  """
  __all__ = []
  ```
  Directory listing: `__init__.py` and `__pycache__` only.
- **Impact**: Minimal at runtime, but the library subtree misrepresents itself: a reader (or an agent) grepping for a caching layer finds a package that promises one and delivers nothing. `_audit-common.md:82` already documents it as "now an empty package" — encoding the debt into the protocol instead of deleting it.
- **Siblings**: None — the rest of #4915's cleanup was complete.
- **Related**: #4915 (CLOSED).
- **Suggested Fix**: `rm -r auralis/library/caching/` and drop the "now an empty package" clause from `_audit-common.md:82`.

### TD2-3: `tests/validation/` holds 20 never-collected files — and 7 of them are named `test_*.py`
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `tests/validation/` (20 `.py` files, 3,628 LOC), `pytest.ini:12`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD2-3)** — carried forward with **corrected counts and materially new evidence**
- **Age**: mixed; directory contents byte-identical to `188db72a` (verified via `git ls-tree`)
- **Effort**: small
- **Description**: Thirteen `validate_*.py` scripts (2,168 LOC) plus **seven `test_*.py` files (1,460 LOC)** sit in `tests/validation/`. The `validate_*` ones are doubly excluded (they don't match `python_files = test_*.py`, and the directory is in `norecursedirs`). The seven `test_*.py` files **do** match `python_files` — `pytest --collect-only tests/validation/` collects 13 items when pointed at the directory directly — but `norecursedirs` silently drops them from `pytest tests`, so they never run in any normal invocation, CI job, or agent sweep. Separately, `norecursedirs` still excludes `tests/obsolete`, a directory that no longer exists.
  > **Correction**: the 2026-08-13 report counted only the 13 `validate_*.py` files. This run's Dim-2 agent counted all 20 and described the difference as growth from 13→20. It is not growth — `git ls-tree -r 188db72a -- tests/validation` returns 20 files. The directory is unchanged; the count method differed.
- **Evidence**:
  ```ini
  # pytest.ini
  testpaths = tests
  python_files = test_*.py
  norecursedirs = tests/validation tests/obsolete .git __pycache__ build dist *.egg-info
  ```
  ```
  $ ls -d tests/obsolete                 → No such file or directory
  $ find tests/validation -name 'validate_*.py' | wc -l → 13   (2,168 LOC)
  $ find tests/validation -name 'test_*.py'     | wc -l → 7    (1,460 LOC)

  file                                       def test_*   asserts
  test_release_version_consistency.py             4          14   ← the valuable one
  test_against_masters.py                         3           3
  test_adaptive_processing_standalone.py          1           0
  test_comprehensive_presets.py                   1           0
  test_diverse_presets.py                         1           0
  test_e2e_processing.py                          2           0
  test_preset_integration.py                      1           0
  ```
  `test_release_version_consistency.py` is the one that matters: 14 assertions guarding release version consistency, named in `docs/releases/RELEASE_CHECKLIST_1_5_1.md` and `docs/versions/RELEASE_GUIDE.md`, and listed as a **path trigger** in `.github/workflows/build-release.yml:18,30` — but that workflow **never invokes pytest**, on that file or anything else. It runs only if a human remembers the checklist step.
- **Impact**: Worse than clutter. Seven files look, name, and structure themselves like real tests and would be swept up by anyone's mental model of "pytest discovers `tests/`", but never run anywhere. Five of them have zero assertions (print-style scripts misnamed as tests); the two that do assert include the only automated guard against a bad release's version metadata — and it is not automated.
- **Siblings**: `tests/stress/stress_test_suite.py` is a documented manual entry point — keep. `tests/backend/full_stack_smoke.py` is TD2-4. The four `helpers.py` modules under `tests/{performance,concurrency,stress,security}/` are legitimate imports — keep.
- **Related**: #4246 (CLOSED — the adjacent print-only convention).
- **Suggested Fix**: **Wire `test_release_version_consistency.py` into `build-release.yml` first** (the path trigger already exists; it just needs a pytest step) or move it to a collected path — a 14-assertion release guard that depends on human memory is the sharpest edge here. Then delete the 13 `validate_*.py` scripts (or move any with residual value to `scripts/development/`), and for the other 6 `test_*.py` files either relocate them to a collected directory or delete them after diffing against current `tests/regression/` coverage. Remove the dead `tests/obsolete` entry from `pytest.ini:12` regardless.

### TD2-4: `full_stack_smoke.py` is uncollected, points at the wrong port, and was flagged 7 weeks ago
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface *(also Audit-Finding Rot)*
- **Location**: `tests/backend/full_stack_smoke.py:46,87,110,154,169`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD2-4)** — re-verified unchanged
- **Age**: `9efbe580` 2026-06-28
- **Effort**: trivial
- **Description**: The filename does not match `test_*.py`, so pytest collects zero tests from it, and every request targets `http://localhost:8000` while the backend binds 8765. It is doubly inert. `AUDIT_RECOVERY_2026-07-24.md` documented both facts and listed conversion as remediation item 8; seven weeks later nothing has changed and no GitHub issue tracks it.
- **Evidence**:
  ```
  tests/backend/full_stack_smoke.py:46   requests.get("http://localhost:8000/api/health", timeout=1)
  tests/backend/full_stack_smoke.py:87   requests.get(f"http://localhost:8000{endpoint}", timeout=2)
  tests/backend/full_stack_smoke.py:110  requests.get("http://localhost:8000/", timeout=2)
  tests/backend/full_stack_smoke.py:154  requests.get(f"http://localhost:8000/static/css/{css_file}", timeout=2)
  tests/backend/full_stack_smoke.py:169  requests.get(f"http://localhost:8000/static/js/{js_file}", timeout=2)
  ```
- **Impact**: A file named "smoke test" providing no smoke coverage is worse than no file — it reads as coverage in a directory listing. It is also a live instance of the Dim-10 rot pattern: a published audit finding with no issue behind it silently expires.
- **Siblings**: TD2-3's uncollected files; both are symptoms of "the tests directory contains things that are not tests".
- **Related**: AUDIT_RECOVERY_2026-07-24 item 8.
- **Suggested Fix**: Delete the file. If a real full-stack smoke test is wanted, write it fresh as `tests/backend/test_full_stack_smoke.py` reading the port from `auralis-web/backend/core/env_config.py` rather than a literal — reviving a file wrong on two axes since June is more work than replacing it.

### TD2-6: `DebugInfo.tsx` + `useCommitId.ts` — a dead React component and the hook that exists only to feed it
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/frontend/src/components/debug/DebugInfo.tsx:1-58`, `auralis-web/frontend/src/hooks/app/useCommitId.ts:1-18`, re-exported at `auralis-web/frontend/src/hooks/app/index.ts:11`
- **Status**: NEW
- **Age**: `c5e913ae` 2026-05-26 (last touched)
- **Effort**: trivial
- **Description**: `DebugInfo.tsx` has zero importers anywhere — no route, no parent component, no test, no dynamic `import()`. It attaches a `Ctrl/Cmd+Shift+D` keydown listener to toggle its own visibility, but since it is never mounted the `useEffect` never runs and the shortcut does nothing. Its docstring is stale on top of being dead, promising `Ctrl+Shift+I` while the code implements `Ctrl+Shift+D`. Its only two dependencies, `useCommitId()` and `getVersionString()`, have no other consumer, so the whole three-symbol cluster is reachable only from itself — including a barrel re-export nobody uses.
- **Evidence**:
  ```
  $ grep -rn "DebugInfo" auralis-web/frontend/src --include='*.ts' --include='*.tsx'
  src/components/debug/DebugInfo.tsx:10:export const DebugInfo = () => {
  src/components/debug/DebugInfo.tsx:58:export default DebugInfo
  # no other reference anywhere, no test file

  $ grep -rn "useCommitId" auralis-web/frontend/src | grep -v test
  hooks/app/useCommitId.ts:6:export function useCommitId(): string {
  hooks/app/index.ts:11:export { useCommitId } from './useCommitId';
  components/debug/DebugInfo.tsx:2,12   # the dead component is the only consumer
  ```
  Note: the app already has a **live** commit/version-display path — `src/index.tsx:22-32` reads a `<meta name="commit-id">` tag and sets `window.__AURALIS_DEBUG__` on every boot. Both the dead copy and the live copy hardcode `version: '1.0.0-beta.13'`, stale against `auralis/version.py` (1.5.1) — noted for `/audit-frontend`, not evaluated here.
- **Impact**: 76 combined LOC of unreachable UI plus a barrel re-export that exists only to serve it. Tree-shaken out of the production bundle, so blast radius is low — but it is a second instance of the pattern #4696 already documents for `src/performance/`, in a different directory.
- **Siblings**: **#4696 (OPEN)** — `src/performance/`, the same class at larger scale (and the source of 14 of the 29 shipped `any` usages). No other files exist under `components/debug/`.
- **Related**: #4696 (OPEN — distinct directory, not a duplicate).
- **Suggested Fix**: Delete `components/debug/DebugInfo.tsx` and `hooks/app/useCommitId.ts`, and remove the `useCommitId` line from `hooks/app/index.ts`. If a debug overlay is wanted later, wire it behind the `window.__AURALIS_DEBUG__` state `index.tsx` already populates rather than maintaining two commit-id paths.

### Dimension 4 — Magic Numbers & Hardcoded Constants

### TD4-1: Genre-based compression magic numbers sit in a confirmed-dead path that reintroduces the retired categorical model
- **Severity**: LOW
- **Dimension**: Magic Numbers
- **Location**: `auralis/dsp/advanced_dynamics.py:190-231` (the `else` branch of `_adapt_to_content`)
- **Status**: NEW
- **Age**: dead since #4873 deleted `RealtimeDSPPipeline`, its only `process()` caller
- **Effort**: trivial to delete, but gated on the decision to retire the class — treat as small
- **Description**: `DynamicsProcessor._adapt_to_content()` hardcodes genre buckets (classical / electronic / rock+metal / broadcast / default), each with bare `target_threshold` / `target_ratio` literals, plus further magic adjustments for dynamic-range and energy bands. This is the categorical branch-by-genre model `_audit-common.md`'s Retired Architecture table says was replaced by continuous parameter generation — except this copy was orphaned rather than deleted.
- **Evidence**:
  ```python
  # auralis/dsp/advanced_dynamics.py:198-217
  if primary_genre == 'classical':      target_threshold, target_ratio = -12.0, 2.0
  elif primary_genre == 'electronic':   target_threshold, target_ratio = -20.0, 6.0
  elif primary_genre in ['rock','metal']: target_threshold, target_ratio = -16.0, 4.0
  elif primary_genre == 'broadcast':    target_threshold, target_ratio = -18.0, 8.0
  else:                                 target_threshold, target_ratio = -18.0, 4.0
  ```
  ```python
  # auralis/core/hybrid_processor.py:69-80
  # #4873 deleted RealtimeDSPPipeline, its only `process()` caller, so nothing
  # currently runs this processor's chain — it survives only for the
  # reset_dynamics()/set_dynamics_mode()/get_dynamics_info() public API …
  # Do NOT insert it into the offline chain to "make it live"
  ```
  Confirmed: `DynamicsManager` (`auralis/core/hybrid/dynamics_manager.py`) calls only `get_info()`, `set_mode()`, `reset()`. No module in `auralis/` calls `dynamics_processor.process(...)`.
- **Impact**: Zero runtime blast radius — dead code cannot mistune audio. The cost is comprehension: a contributor grepping for "compression ratio" or "genre" lands here and may reasonably assume it is the live tuning surface, duplicate tuning effort, or wire it back into the pipeline exactly as the comment warns against (double compression fighting the continuous-space LUFS target). Its retirement is recorded as prose ("Retiring it is tracked separately") with no issue number, so it is invisible to marker sweeps — the same class as TD1-1.
- **Siblings**: None — `auralis/core/processing/continuous_space.py` does not duplicate any of these values, so this is an isolated orphan, not a divergent pair.
- **Related**: #4873 (the deletion that orphaned it), TD1-1 / TD1-3 (the prose-deferral convention).
- **Suggested Fix**: Delete the genre-branch literals when `DynamicsProcessor.process()`/`_adapt_to_content` is retired, rather than letting them drift further from the live continuous-space tuning surface. If retirement is not imminent, at minimum convert the prose deferral at `hybrid_processor.py:80` into `# TODO(#NNNN): delete DynamicsProcessor.process()/_adapt_to_content once callers are fully removed`.

### Dimension 5 — Stub & Placeholder Implementations

### TD5-1: `ArtistHeader` ships a static "Artist" line where its sibling renders real metadata
- **Severity**: LOW
- **Dimension**: Stub Implementations
- **Location**: `auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx:82-89`
- **Status**: NEW
- **Age**: `936b8856` 2025-12-27 (text introduced)
- **Effort**: small
- **Description**: The artist detail header renders a secondary metadata line that is the hardcoded literal `"Artist"`, with a comment admitting it. The equivalent album header (`AlbumHeaderActions.tsx`, same `DetailViewHeader` shell) renders real fields — `year`, `track_count`, `total_duration`, `genre` — via `AlbumMetadata`. There is no `ArtistMetadata` counterpart; the artist path never grew past its placeholder.
- **Evidence**:
  ```tsx
  {/* Additional context - currently placeholder, can be expanded with backend data */}
  <Typography variant="body2" sx={{ color: themeVars.textMuted, ... }}>
    Artist
  </Typography>
  ```
  Reachability confirmed: `ArtistDetailView.tsx` → `ArtistDetailHeaderSection` → `ArtistHeader`. Rendered on every artist detail page. **Stays LOW rather than promoting to MEDIUM**: the promotion trigger requires a reachable `NotImplementedError`/`pass`-only/`...` stub; a cosmetic filler string is not that.
- **Impact**: Cosmetic only — no bug class, no data-integrity risk. It raises change-cost slightly: a contributor implementing artist stats must first discover the line is decorative filler, not a field binding.
- **Siblings**: None — `AlbumHeaderActions.tsx` (the only other `DetailViewHeader` consumer) is fully data-bound.
- **Related**: None filed.
- **Suggested Fix**: Delete the line (falling back to the primary stat) — implementing it needs a backend field that does not exist on `Artist` today, so deletion is the pragmatic default.

### Dimension 6 — Test Hygiene

### TD6-1: Sole-`is not None` smoke tests survive the #4049 / #4257 cleanups — 57 by a strict AST measure, 14 of them with multiple redundant assertions
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_string_input_boundaries.py`, `tests/integration/test_e2e_workflows.py`, `tests/integration/test_repositories.py`, `tests/backend/test_boundary_advanced_scenarios.py`, `tests/boundaries/test_audio_processing_boundaries.py`, `tests/auralis/player/test_enhanced_player.py`, +more
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD6-1)** — re-verified; **methodology gap the 2026-08-13 report left open is now closed**
- **Age**: various; the pattern predates both cleanup issues
- **Effort**: small
- **Description**: An AST sweep — every `assert` in the function body is `X is not None` — finds **57** such test functions at `7e9c401f`, of which **14** have more than one such assertion (the clearest offenders). The 2026-08-13 report said 22 with an unstated narrower filter; this run reproduces every example it cited and supplies the reconciled number. #4049 fixed 31 and #4257 fixed 56 across 32 files, both closed, but the pattern was never gated.
- **Evidence**:
  ```
  Top offenders (assert count, all `is not None`):
    8  tests/integration/test_repositories.py::test_factory_provides_all_repositories
    4  tests/integration/test_e2e_workflows.py::test_add_track_with_metadata_extraction
    4  tests/auralis/player/test_enhanced_player.py::test_enhanced_player_initialization_with_factory
    3  tests/integration/test_repositories.py::test_different_repository_instances_independent
    3  tests/auralis/player/test_enhanced_player.py::test_integration_manager_with_factory
    2  tests/backend/test_string_input_boundaries.py::test_sql_injection_in_title
    2  tests/backend/test_boundary_data_integrity.py::test_relationship_integrity_after_operations
    … 50 more with a single such assertion
  ```
  Every example named in the 2026-08-13 report reproduces byte-for-byte.
  **Related residue found this run**: 28 test functions contain `print()` and **zero** assertions (5 of them in the never-collected `tests/validation/`, so 23 in collected directories) — the broader form of the pattern #4246 (CLOSED) fixed for `test_summary_stats()` specifically.
- **Impact**: `test_sql_injection_in_title` asserting only non-null means an injection that succeeded and returned a row passes the test. `test_add_track_with_metadata_extraction` is a 4-assert E2E test that would pass against a metadata extractor returning the wrong value for every field.
- **Siblings**: `tests/integration/test_repositories.py` is separately **pre-existing broken** (#4234 — calls repository methods on the class, not instances), so its two entries here should be fixed as part of that, not separately.
- **Related**: #4049 (CLOSED, 31 tests), #4257 (CLOSED, 56 tests / 32 files), #4246 (CLOSED, the print-only convention), #4234 (the broken repositories test).
- **Suggested Fix**: Strengthen the 14 multi-assert cases first (`test_sql_injection_in_title`: assert the stored title round-trips byte-identically and no extra rows exist; `test_add_track_with_metadata_extraction`: assert extracted title/artist/album/duration equal the fixture's known values), then add the AST check used to produce this list as a pytest collection-time warning so the count cannot climb back — the 56 → 22 → 57 history shows point-fixes do not hold without a gate.

### TD6-2: Four permanent skips carry no issue reference, one for an endpoint that never existed
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_boundary_max_min_values.py:377,431,505`, `tests/backend/test_api_endpoint_integration.py:175`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD6-2)** — re-verified byte-for-byte unchanged
- **Age**: `aacb4d53` 2026-08-07 (max_min_values), `af4e1d6f` 2026-07-15 (api_endpoint_integration)
- **Effort**: trivial
- **Description**: Four `@pytest.mark.skip` markers state a limitation as permanent fact with no tracking issue, so nothing will ever prompt a re-check. One describes an endpoint that was never implemented and is on no roadmap — aspirational, not deferred.
- **Evidence**:
  ```python
  test_boundary_max_min_values.py:377   reason="Known limitation: Extreme DC offset edge case not fully handled. …"
  test_boundary_max_min_values.py:431   reason="Known limitation: Repository deduplicates by filepath. …"
  test_boundary_max_min_values.py:505   reason="Known limitation: Repository deduplicates by filepath. …"
  test_api_endpoint_integration.py:175  reason="Endpoint /api/library/search not yet implemented (returns 404)"
  ```
  `/api/library/search` still does not exist — `auralis-web/backend/routers/library.py` registers exactly three routes (`/api/library/refresh-references`, `/api/library/stats`, `/api/library/reset`).
- **Impact**: "Known limitation" with no issue is indistinguishable from "someone gave up". The DC-offset one asserts a documented DSP gap `/audit-engine` would want to know about; the `/api/library/search` one advertises a feature nobody is building.
- **Siblings**: The other 55 Python skips are accounted for — 16 `xfail(strict=True)` under TD6-3/TD6-4, 5 removed-endpoint skips under **#4400 (OPEN)**, 2 identical perf skips under **#5024 (OPEN)**, and ~12 legitimate dependency guards (`mutagen not installed` ×11, `requires ffmpeg`, chroma/adaptive-mastering availability) plus documented slow-test skips in `tests/stress/`.
- **Related**: #4400 (OPEN), #5024 (OPEN).
- **Suggested Fix**: Delete `test_api_endpoint_integration.py:175` outright — testing an endpoint nobody intends to build is not deferred work. For the three "Known limitation" skips, file one issue covering both limitations and add `(#NNNN)` to each reason string, or delete the two repository-dedup ones and rewrite them against the actual dedup contract.

### TD6-3: 14 `xfail(strict=True)` markers cite CLOSED annotation-only issues, leaving the real defects untracked
- **Severity**: LOW *(promotion checked and correctly declined — #4548 was MEDIUM and #4269 was LOW, so the "closed CRITICAL/HIGH" trigger does not fire)*
- **Dimension**: Test Hygiene
- **Location**: `tests/concurrency/test_thread_safety.py:378,441,491,515,544`; `tests/concurrency/test_parallel_processing.py:386,417,438,465,493,527,548,572,605`
- **Status**: NEW
- **Age**: `aacb4d53` 2026-08-07
- **Effort**: medium (5 tests need re-pointing at current APIs; 9 need a pickling fix or an explicit design decision)
- **Description**: #4548 and #4269 are both CLOSED, but neither was ever about fixing the underlying bugs — both were meta-issues about the xfail *markers* lacking `strict=True` and issue references. Closing them replaced vague reasons with precise per-symbol diagnoses (real, valuable work) and left the 14 diagnosed defects unfixed with **no live tracking issue at all**. Because every marker is `strict=True`, this is not inert: if any drift is ever incidentally fixed, the suite starts *failing* on XPASS, and whoever hits it has no open issue to consult.
- **Evidence** (every claim independently re-verified against live source, not just re-read from the marker string):
  ```
  test_thread_safety.py:378  "UnifiedConfig has no set_intensity()"
    → grep 'def set_intensity' auralis/core/config/unified_config.py → 0 matches
  test_thread_safety.py:441  "AdaptiveCompressor.__init__ now requires 'settings'"
    → auralis/dsp/dynamics/compressor.py:32  def __init__(self, settings: CompressorSettings, sample_rate: int)
  test_thread_safety.py:491  "BaseSpectrumAnalyzer.__init__ no longer accepts 'sample_rate'"
    → auralis/analysis/base_spectrum_analyzer.py:43  def __init__(self, settings: SpectrumSettings | None = None)
  test_thread_safety.py:515  "ContentAnalyzer.analyze_content() takes 1 argument, test passes 2"
    → auralis/core/analysis/content_analyzer.py:68  def analyze_content(self, audio: np.ndarray)
  test_thread_safety.py:544  "AdaptiveTargetGenerator.__init__ now requires 'config'"
    → auralis/core/analysis/target_generator.py:20  def __init__(self, config: UnifiedConfig, processor: Any | None = None)
  test_parallel_processing.py ×9  "HybridProcessor cannot be pickled for multiprocessing IPC"
    → pickle.dumps(HybridProcessor(UnifiedConfig())) → TypeError: cannot pickle '_thread.lock' object
  ```
  All 14 reasons are still factually accurate at HEAD — none is stale-in-the-dangerous-direction (now-fixed-but-still-strict-xfailed), which was explicitly checked.
- **Impact**: The project's only dedicated thread-safety suite has 7 of ~13 tests permanently disabled with no owner, and the parallel-processing suite has 9 more. A fix to any of them produces a strict-XPASS failure with no linked issue explaining why a passing test is being treated as a bug.
- **Siblings**: The 2 remaining xfails in the same file are a distinct root cause — TD6-4.
- **Related**: #4548 (CLOSED, MEDIUM — fixed marker hygiene, not the drift), #4269 (CLOSED, LOW — same, for the pickling file).
- **Suggested Fix**: File one issue per cluster — *signature re-pointing* (5 tests, ~1-2 h) and *`HybridProcessor` picklability* (9 tests; needs a design call on whether `__getstate__`/`__setstate__` stripping the lock is acceptable, or whether multiprocessing IPC is permanently out of scope) — and reference each from the `reason=` strings, exactly as #4548 did for its predecessors.

### TD6-4: A genuine `play_count` lost-update race was explicitly flagged as needing its own issue and never got one
- **Severity**: LOW *(as a **paper-trail** finding — the underlying defect is a correctness bug and is routed, not scored, here)*
- **Dimension**: Test Hygiene
- **Location**: `tests/concurrency/test_thread_safety.py:108,208`; underlying code `auralis/library/repositories/track_repository.py:606-620`
- **Status**: NEW
- **Age**: `aacb4d53` 2026-08-07
- **Effort**: medium (making `record_play` atomic is a DB-layer change, not a test fix)
- **Description**: `test_concurrent_database_transactions` and `test_concurrent_metadata_updates` assert that concurrent `play_count` increments do not lose updates. #4548's closing comment diagnosed the cause precisely — both the tests' hand-rolled increment and `TrackRepository.record_play` do `SELECT` then `play_count + 1` in Python with no atomic `UPDATE` and no row lock, so lost updates are guaranteed by construction — and stated verbatim: *"Making `record_play` atomic is a product change worth its own issue."* No such issue exists (`gh issue list --search "record_play atomic"` / `"play_count"` return nothing but #4548).
- **Evidence**:
  ```python
  # tests/concurrency/test_thread_safety.py:108
  @pytest.mark.xfail(reason="Asserts no lost updates across concurrent read-modify-write
    increments, which neither this test's hand-rolled increment nor TrackRepository.record_play
    provides — both do SELECT then play_count+1 in Python. Needs an atomic UPDATE (see #4548)",
    strict=True)
  ```
  #4548 is CLOSED. Its own text names this as separate, unfiled product work.
- **Impact**: `TrackRepository.record_play` — the real, non-test path that increments play counts on actual playback — silently loses increments under concurrent play events (two windows playing the same track, rapid skip-and-replay). This is a **real production correctness bug with zero tracking issue**; the only artifacts naming it are a closed issue's closing comment and two permanently-disabled tests.
- **Siblings**: None — distinct from TD6-3's signature-drift cluster.
- **Related**: #4548 (CLOSED — the only place this is documented). **Route to `/audit-concurrency` or `/audit-backend` for severity scoping** — this dimension flags only the missing paper trail; the bug itself is likely MEDIUM under the standard scale.
- **Suggested Fix**: File an issue (library/backend domain) for "`TrackRepository.record_play` uses non-atomic read-modify-write, losing concurrent play-count increments" and reference it from both xfail markers in place of #4548.

### TD6-5: #5119's frontend remediation left the promised rewrite — and a stale baseline — untracked
- **Severity**: LOW
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/frontend/src/tests/integration/README.md`, `auralis-web/frontend/test-baseline.json`
- **Status**: NEW
- **Age**: `0b7ceb5d` 2026-08-14 (today)
- **Effort**: trivial (file an issue + regenerate the baseline); the rewrite itself is separately large
- **Description**: The 15 `describe.skip`-wrapped files from #5119 (CLOSED HIGH, fixed today) are the **correct** remediation, following #3935's precedent, and the guard test that should prevent recurrence is real and functional — verified by reading `integration-tests-exercise-production-code.test.ts`, which walks `src/tests/{integration,api-integration}`, requires every spec to import a non-infrastructure module or have every top-level `describe` skipped, and guards itself against a silent empty-glob pass. Two things the remediation itself flags as open are tracked nowhere:
  1. **The rewrite has no issue.** #5119's closing comment says: *"the 14 suites are skipped, not rewritten … worth a separate issue if that coverage is wanted."* None was filed. Ten feature areas (library search/filter/sort, metadata, artwork, accessibility, API error handling, pagination, caching, bundle-splitting, memory cleanup) currently have zero real integration coverage and no scheduled path back.
  2. **`test-baseline.json` was not regenerated**, despite the same comment flagging it. At `7e9c401f` it still lists 8 `library-api.test.ts` entries as known failures.
- **Evidence**:
  ```
  $ git log -1 --format='%h %ad' -- auralis-web/frontend/test-baseline.json
  a866550c 2026-08-13          # predates 0b7ceb5d
  $ git show 0b7ceb5d --stat | grep baseline   → (no output)
  $ grep -c library-api auralis-web/frontend/test-baseline.json → 8
  ```
- **Impact**: (1) is an unscheduled coverage gap across ten feature areas. (2) is functionally inert — `check-test-baseline.mjs` is a ratchet that fails only on *new* failures, so stale entries just report "no longer failing" — but the baseline file no longer accurately lists known-failing specs, which is the one thing it exists to do.
- **Siblings**: None new — this is the same-day follow-up to #5119/#3935, not a fresh instance.
- **Related**: #5119 (CLOSED HIGH, today), #3935 (CLOSED HIGH, the precedent).
- **Suggested Fix**: File the follow-up issue #5119's own closing comment asked for (rewrite-or-permanently-accept the 15 skipped files, referencing the three real patterns already in the tree: `library-management.test.tsx`, `playlist-management.test.tsx`, `websocket-realtime.test.tsx`). Separately regenerate the baseline **from a CI artifact** via `pnpm run test:ci && pnpm run test:baseline:update`.

### Dimension 7 — Stale Documentation & Comments

### TD7-1: CLAUDE.md's Codebase Map describes a module and package as live two days after both were deleted
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `CLAUDE.md:116-118`; sibling `docs/architecture/module-map.md:56`
- **Status**: NEW
- **Age**: doc line added `4171f36c` 2026-07-30; the deletion landed `2ca72012` 2026-08-12 — **2 days before this audit**
- **Effort**: trivial
- **Description**: CLAUDE.md — auto-loaded into every agent session — still describes `auralis/optimization/parallel/` as "Parallel audio processing (impl lives here)" and `parallel_processor.py` as a "Compatibility barrel re-exporting parallel/ (#4276)". Both were deleted in #4565's resolution: 1,323 LOC across `parallel/`'s 8 modules, `parallel_processor.py`, `auralis/analysis/parallel_spectrum_analyzer.py`, and 5 test modules. The directory now contains only `.pyc` files.
- **Evidence**:
  ```
  CLAUDE.md:116-118
    ├── optimization/                 Performance
    │   ├── parallel/                   Parallel audio processing (impl lives here)
    │   └── parallel_processor.py       Compatibility barrel re-exporting parallel/ (#4276)

  $ ls auralis/optimization/parallel_processor.py   → No such file or directory
  $ find auralis/optimization/parallel -name '*.py' → (nothing; 15 .pyc files only)
  $ git log --diff-filter=D --format='%h %ci %s' -- auralis/optimization/parallel_processor.py
  2ca72012 2026-08-12  refactor: delete unreachable optimization/parallel cluster (#4565)
  ```
  `_audit-common.md:81` already documents this correctly — the audit-skill half of the docs caught up; the project's own primary brief did not.
- **Impact**: Every session (agent or human) reading the Codebase Map is told `parallel/` holds a live implementation. An agent asked to touch parallel audio processing greps an empty directory and burns a turn re-discovering what `_audit-common.md` already knows. **This is the worked example for TD7-2**: exactly the drift the path gate exists to catch, landing and surviving during the window the gate has been silently failing.
- **Siblings**: `docs/architecture/module-map.md:56` carries the identical claim. **Mirror-image error**: `_audit-common.md` gets the same package wrong in the *opposite* direction (TD10-1), calling the whole thing dead.
- **Related**: #4565 (CLOSED — the deletion), #4276 (the compat barrel the line was written for), TD7-2, TD10-1.
- **Suggested Fix**: Delete the `parallel/` and `parallel_processor.py` rows from CLAUDE.md's Codebase Map (or replace with one line noting both were deleted in #4565), and drop the equivalent from `docs/architecture/module-map.md:56`. Fix TD10-1 in the same edit so the two documents stop being wrong about the same package in opposite directions.

### TD7-4: `auralis/core/mastering_branches.py` is documented as a file in two live docs; it is a package
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/features/adaptive-mastering/ADAPTIVE_MASTERING_SYSTEM.md:9`, `docs/deployment/DEPLOYMENT_SUMMARY.md:34`
- **Status**: NEW *(distinct from #4627, which covers only `auralis/library/scanner.py` → package in CLAUDE.md)*
- **Effort**: trivial
- **Description**: `auralis/core/mastering_branches` is a package (`__init__.py`, `base.py`, `continuous.py`, `soft_clip_params.py`). Two docs still reference `mastering_branches.py` as a file, including one that cites it as "where much of the offline signal-path work now lives".
- **Evidence**:
  ```
  $ ls auralis/core/mastering_branches/
  __init__.py  base.py  continuous.py  soft_clip_params.py

  ADAPTIVE_MASTERING_SYSTEM.md:9  "…(auralis/core/simple_mastering.py + auralis/core/mastering_branches.py)…"
  DEPLOYMENT_SUMMARY.md:34        "…see auralis/core/simple_mastering.py … and auralis/core/mastering_branches.py…"
  ```
  `_audit-common.md:78,81` already uses the package path correctly — the same "audit-skill fixed, `docs/` tree not fixed in the same change" pattern as TD7-1.
- **Impact**: Low — a reader gets a clean "No such file", not a silent wrong answer. Both entries also count toward TD7-2's 310.
- **Siblings**: TD7-1, TD7-5 — all three are the same class.
- **Related**: #4627 (the sibling `scanner.py` finding), TD7-2.
- **Suggested Fix**: Change both references to `auralis/core/mastering_branches/`.

### TD7-6: `TESTING_GUIDELINES.md` still asserts no backend test gate exists — introduced false by the very commit that added the gate
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `docs/development/TESTING_GUIDELINES.md:1022-1037`
- **Status**: NEW
- **Age**: `43c983ad` 2026-07-26 — the commit that added `.github/workflows/backend-tests.yml` also edited this section and left the false claim in place
- **Effort**: trivial
- **Description**: The section reads *"there is **no** automated pytest / coverage / codecov / e2e gate on push or PR"* and enumerates the workflows as `build-release.yml`, `frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml`, `requirements-pin-guard.yml`, `rust-audit.yml` — omitting `backend-tests.yml` entirely, and (added later) `action-pin-guard.yml`.
- **Evidence**:
  ```
  $ ls .github/workflows/
  action-pin-guard.yml  backend-tests.yml  build-release.yml  frontend-test.yml
  frontend-typecheck.yml  lockfile-guard.yml  requirements-pin-guard.yml  rust-audit.yml

  $ git log -1 --format='%h %ci %s' -- .github/workflows/backend-tests.yml docs/development/TESTING_GUIDELINES.md
  43c983ad 2026-07-26  fix: update integration guide and add backend tests workflow; …
  ```
- **Impact**: A contributor is told outright that no backend CI test gate exists, contradicting CLAUDE.md's own CI-gates table (`backend-tests.yml` runs `pytest --junitxml`, gated by `scripts/check_pytest_baseline.py` against `pytest-baseline.json` — which TD7-3 shows is live and updated today). **Stays LOW** because the section carries a self-aware "verify against the Actions tab" caveat added in the same commit (referencing the `.github/workflows.backup/` incident, #4562), which partially defends against the claim being taken at face value.
- **Siblings**: None elsewhere in the file for the same claim.
- **Related**: #4562, #4272 (CLOSED — an earlier round of this same section going stale), TD7-3.
- **Suggested Fix**: Add `backend-tests.yml` and `action-pin-guard.yml` to the enumerated list and replace "there is no automated pytest … gate" with a summary of the current ratchet mechanics, mirroring CLAUDE.md's table so the two authoritative docs agree.

### TD7-7: README's `uv venv` setup command omits the flag CLAUDE.md says is required
- **Severity**: LOW
- **Dimension**: Stale Documentation
- **Location**: `README.md:152`
- **Status**: NEW
- **Effort**: trivial
- **Description**: README's "run from source" setup block runs `uv venv --python 3.14`. CLAUDE.md's Commands section runs `uv venv --python-preference only-managed` and annotates it: *"`--python-preference only-managed` or uv silently picks a stale pyenv shim."* README lacks the flag.
- **Evidence**:
  ```
  README.md:152    uv venv --python 3.14
  CLAUDE.md        uv venv --python-preference only-managed && source .venv/bin/activate
                   # …or uv silently picks a stale pyenv shim
  ```
- **Impact**: A contributor following README verbatim on a machine with a pyenv shim on `PATH` — the exact failure mode CLAUDE.md warns about, and one this repo has hit before — silently gets a stale interpreter, surfacing confusingly at the Rust/PyO3 build step rather than at venv creation.
- **Siblings**: None — this is README's only `uv venv` invocation.
- **Related**: None filed.
- **Suggested Fix**: Change `README.md:152` to `uv venv --python-preference only-managed`, dropping the redundant `--python 3.14` since `.python-version` already pins it.

### Dimension 8 — Backwards-Compat Cruft & "No Variants" Violations

### TD8-1: `library_manager` names a class deleted three weeks ago — 118 references across 29 files
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/backend/config/startup.py:518-526`, `auralis/library/database.py:9-16`, `auralis/library/__init__.py:16-21`, `auralis-web/backend/routers/dependencies.py:88-91`, +25 files
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD8-1)** — re-verified; counts **byte-for-byte unchanged**
- **Age**: `LibraryManager` deleted 2026-07-29 (#4915); the naming survived intact
- **Effort**: medium
- **Description**: `LibraryManager` no longer exists — no `manager.py`, no class definition anywhere in `auralis/` (only an unrelated `LibraryManagerUnavailableError` exception). But the global holding the `LibraryDatabase` instance is still keyed `library_manager`, and four docstrings describe the deleted class in the **present tense** — precisely the construction `_audit-common.md:82` warns is "stale by construction".
- **Evidence**:
  ```
  $ grep -RIn "class LibraryManager" auralis/            → no matches
  $ find auralis/library -iname manager.py               → no such file
  $ grep -RIn "library_manager\|LibraryManager" auralis auralis-web/backend \
      --include='*.py' | grep -vE '/tests?/|test_' | wc -l   → 118  (29 files)
  ```
  ```python
  # auralis/library/database.py:15-16 — present tense, about a deleted class
  "…LibraryManager is now a legacy query facade over this class and
   nothing on the startup path constructs it."
  ```
- **Impact**: `grep -ri library_manager` returns 118 false leads across 29 files for anyone scoping a `LibraryDatabase` change, and the variable name mis-describes its own type at the composition root. Several prior audits have had to be corrected on exactly this point — which is why the Retired Architecture table has a row for it.
- **Siblings**: `auralis/player/enhanced_audio_player.py:76,84` and `auralis/player/queue_controller.py:31,38` still declare `library_manager: Any | None = None` parameters documented "Deprecated, kept for backward compatibility only", accepted and dropped on the floor — that specific pair is **Existing: #4312 (OPEN)**.
- **Related**: #4915 (CLOSED), #4619 (CLOSED), #4312 (OPEN), #5031 (OPEN — the doc half, see the deduped table).
- **Suggested Fix**: Rename the globals key `library_manager` → `library_database` (mechanical across 29 files, guarded by `mypy` plus the backend router tests) and rewrite the four docstrings in the past tense as one-line historical notes. This closes #4312 as a side effect and removes the need for the Retired Architecture row.

### TD8-2: Breadcrumb-comment cleanup is on its fourth recurrence with no automated guard
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: repo-wide; concentrated in `auralis-web/frontend/src/hooks/player/index.ts:9-27`, `auralis-web/frontend/src/types/api.ts:152,164,177,296`, `auralis-web/backend/routers/library.py:17-21`
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD8-2)** — re-verified; the finding is the missing **guard**, not the instances
- **Age**: recurrence chain #4088 (2026-05-30) → #4293 → #4649 (2026-07-25) → #5034 (2026-08-07)
- **Effort**: small
- **Description**: CLAUDE.md and `audit-tech-debt.md` require `// removed:` breadcrumbs to be deleted outright. The same cleanup has been filed four times, each fixed by hand, none adding a guard — so the fifth recurrence is already accruing. This is debt about the debt process.
- **Evidence**:
  ```typescript
  // auralis-web/frontend/src/hooks/player/index.ts:12-27 — four in one file
  // usePlaybackState removed (#3126) — parallel WS-shadow state with no production consumers.
  // usePlayerControls removed (#4387) — orphaned hook with zero production consumers…
  // usePlayerStreaming removed (#3776) — was 475 lines of dead code…
  ```
  Count is pattern-sensitive: a strict `removed (#NNNN)` grep returns 9 hits / 4 files; a looser pattern covering `REMOVED` / `#NNNN: … removed` phrasing returns 23; a broad "comment containing 'removed'" sweep returns 39. **That spread is itself the finding** — there is no canonical grep, so every audit derives a different number and none can ratchet.
- **Impact**: Four hand-cleanups over ~3 months for a pattern a 3-line grep would prevent. The cost is the recurring triage, not the comments.
- **Siblings**: Some of these comments are genuinely load-bearing ("do NOT re-add X, here's why") — `BufferScheduler.ts:253` is explicitly marked "DELIBERATELY KEPT, do not re-report". Any guard needs an opt-out marker rather than a blanket ban.
- **Related**: #4088 (CLOSED), #4293 (CLOSED), #4649 (OPEN), #5034 (OPEN). **Do not file a fifth instance-cleanup issue.**
- **Suggested Fix**: Add a grep check to the existing `scripts/` gate set — fail on `^\s*(//|#)\s*\w+ removed \(#\d+\)` unless the line also carries `DELIBERATELY KEPT` — and publish it as *the* canonical pattern so the count becomes comparable across runs. Then close #4649 and #5034 together with the mechanical sweep the gate forces.

### TD8-3: `announceFocus()` — dead exported function whose unused param was renamed to `_element` instead of deleted
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/a11y/focusManagement.ts:380-393`
- **Status**: NEW
- **Age**: introduced `62733980`; param underscore-renamed in `592891db` ("resolve 899 TypeScript errors after TS 5.x upgrade") — a mechanical lint fixup, not a design decision
- **Effort**: trivial
- **Description**: `announceFocus(_element: HTMLElement, message: string)` has zero callers anywhere in the frontend. Its first parameter was originally `element`; when a TS-upgrade lint pass flagged it unused, the fix was to underscore-rename rather than delete the parameter — or the whole dead function. CLAUDE.md is explicit: delete, don't rename to `_var`.
- **Evidence**:
  ```
  $ grep -rn "announceFocus(" auralis-web/frontend/src
  src/a11y/focusManagement.ts:380:export function announceFocus(_element: HTMLElement, message: string): void {
  # definition only — zero call sites

  $ git log --all -p --follow -- .../focusManagement.ts | grep -B2 '^+export function announceFocus(_element'
  -export function announceFocus(element: HTMLElement, message: string): void {
  +export function announceFocus(_element: HTMLElement, message: string): void {
  ```
  The body (380-393) never references `_element` — it builds a floating `aria-live` region from `message` alone.
- **Impact**: A dead a11y helper sits in the module surface with a signature that lies about needing an element. Anyone wiring new focus-announcement UX is likely to find and call this instead of the real live-region pattern, inheriting the unused-param smell.
- **Siblings**: A repo-wide sweep for `_`-prefixed parameter renames across Python and TS (excluding idiomatic `_event`/`_args` conventions) found only this one genuine accept-and-drop survivor. The two known others are already tracked: **#5035** (`create_files_router`'s `connection_manager`) and **#4312** (`library_manager` in the player/queue constructors).
- **Related**: None filed.
- **Suggested Fix**: Delete `announceFocus()` entirely — zero callers, nothing to preserve. If focus announcements are wanted later, write it against an actual call site so the signature reflects real need.

### TD8-4: `PlayEnhanced` type alias — a "backward-compatible public name" with zero consumers
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts:54-55`, re-exported at `auralis-web/frontend/src/hooks/enhancement/index.ts:27`
- **Status**: NEW
- **Age**: introduced alongside `useEnhancedPlayCommand.ts` (#4077's decomposition of `usePlayEnhanced`)
- **Effort**: trivial
- **Description**: `export type PlayEnhanced = StartPlayback;` is commented `/** Backward-compatible public name for consumers of the hook barrel. */` and re-exported from the barrel — but nothing anywhere in the frontend imports or annotates with it. In a desktop-only app with no external API consumers, this is a compatibility name invented for consumers that were never written.
- **Evidence**:
  ```
  $ grep -rn "\bPlayEnhanced\b" auralis-web/frontend/src --include='*.ts' --include='*.tsx'
  hooks/enhancement/useEnhancedPlayCommand.ts:55:export type PlayEnhanced = StartPlayback;
  hooks/enhancement/index.ts:27:export { useEnhancedPlayCommand, type PlayEnhanced } from './useEnhancedPlayCommand';
  ```
  Every other `PlayEnhanced`-shaped hit is the case-different, unrelated runtime identifier `usePlayEnhanced` / `playEnhanced` / `mockPlayEnhanced` — none references the type.
- **Impact**: Small — pure speculative surface. `StartPlayback` is the real, used name (it types `UseEnhancedPlayCommandParams` and the hook's own return).
- **Siblings**: None in the same barrel.
- **Related**: None filed.
- **Suggested Fix**: Delete the alias and its barrel re-export; keep `StartPlayback` as the sole exported name.

### TD8-5: `QueueController.tracks` — a property labelled "for old test code", with only old test code calling it
- **Severity**: LOW
- **Dimension**: Backwards-Compat Cruft
- **Location**: `auralis/player/queue_controller.py:57-61`
- **Status**: NEW
- **Age**: present since the `QueueController` extraction; the comment is self-dating
- **Effort**: trivial
- **Description**: `QueueController.tracks` is a property under a `# Backward compatibility properties for old test code` header, delegating to `self.queue.get_queue()`. `QueueController` instances are reachable from production as `audio_player.queue`, so `audio_player.queue.tracks` *would* resolve — but nothing in `auralis/` or `auralis-web/` calls it. The only callers are the tests, using exactly the "old test code" pattern the comment names.
- **Evidence**:
  ```python
  # tests/auralis/player/test_enhanced_player_detailed.py:78,92,93,102
  assert queue_manager.tracks == []
  assert len(queue_manager.tracks) == 1
  assert queue_manager.tracks[0] == track_info
  assert len(queue_manager.tracks) == 2
  ```
  No `.queue.tracks` property access exists in `auralis-web/backend` or any non-test `auralis/` module — every production "tracks" reference on a queue-adjacent object is either `repos.tracks` (a repository) or the inner `QueueManager.tracks` **list attribute** at `components/queue_manager.py:32`, a different object that happens to share the name.
- **Impact**: Low — a dead property whose docstring accurately predicted its own fate. Worth noting it is a candidate the #4973 sweep of this same class should have caught alongside the siblings it verified as live.
- **Siblings**: `QueueController.clear()` (`:112`) and `.set_queue()` (`:358`) carry identical "(backward compatibility alias)" phrasing but were verified **live** via `queue_service.py` callers under #4973 — **do not conflate `.tracks` with those two**.
- **Related**: #4973 (OPEN — covered `undo()`, `create_psychoacoustic_eq()`, `scan_folder()`/`scan_single_directory()` on the same sweep, but not this property).
- **Suggested Fix**: Delete the `tracks` property and update the four assertions in `test_enhanced_player_detailed.py` to call `queue_manager.queue.get_queue()` directly.

### Dimension 9 — File / Function / Module Complexity

### TD9-1: The >300 LOC Python census is on a steady upward trend — 102 → 105 → 108 in three weeks — while #4511 still scopes 8 files
- **Severity**: LOW
- **Dimension**: File / Function / Module Complexity
- **Location**: repo-wide — **108** Python + **36** production frontend modules over the limit
- **Status**: **Existing (unpublished 2026-08-13 report, finding TD9-1)** — re-verified; census moved again, numbers below supersede yesterday's
- **Age**: continuous drift; #4511 was scoped at 8 files
- **Effort**: large (decompose per file — do **not** file as one issue)
- **Description**: CLAUDE.md sets a <300 LOC per-module rule. The Python census is **108**, up from **105** on 2026-08-13 and **102** when #4673 closed on 2026-07-25 — three measurements, monotonically increasing at ~2 files/week. The production frontend census is **36**, flat since yesterday and down from 44 at #4673, so the two languages are moving in opposite directions and must not be discussed as one number.
- **Evidence**:
  ```
  Python, top 15 at 7e9c401f (Δ vs 2026-08-13 in brackets):
    1066  auralis/library/repositories/track_repository.py        [=]
    1014  auralis-web/backend/config/startup.py                   [+161]
     991  auralis-web/backend/core/chunked_processor.py           [+49]
     964  auralis-web/backend/core/processing_engine.py           [+3]
     795  auralis/library/repositories/fingerprint_repository.py  [=]
     789  auralis/core/processing/continuous_mode.py              [+28]
     766  auralis-web/backend/routers/processing_api.py           [=]
     766  auralis-web/backend/routers/player.py                   [-1]
     747  auralis-web/backend/services/queue_service.py           [+6]
     740  auralis/player/enhanced_audio_player.py
     713  auralis-web/backend/cache/manager.py
     671  auralis/core/hybrid_processor.py                        [-85]
     657  auralis/library/repositories/playlist_repository.py
     634  auralis-web/backend/core/streamlined_worker.py
     628  auralis/library/models/core.py

  Frontend production, top 6:
     575  src/hooks/library/useLibraryQuery.ts            (#5043 OPEN)
     574  src/hooks/enhancement/useAudioStreamingCore.ts  (#5041 OPEN)
     571  src/store/slices/playerSlice.ts                 (#5042 OPEN)
     538  src/store/middleware/errorTrackingMiddleware.ts
     515  src/theme/themeConfig.ts
     514  src/hooks/enhancement/useEnhancementControl.ts
  ```
  `startup.py` grew **+161 LOC in a single day** (853 → 1,014) and is now the second-largest module in the repo — the single biggest contributor to the census moving.
- **Impact**: `track_repository.py` at 1,066 LOC is 3.5× the limit and is the file every library change touches. The trend matters more than any individual file: the rule is being lost at roughly the rate it is being enforced. **Note for the next run**: `baseline.txt` reports **127** for frontend because its grep includes specs; the production figure is **36**. Do not compare the two.
- **Siblings**: Split axes worth proposing now — `track_repository.py` by read/write/search; `startup.py` by lifespan phase (DB / player / workers / routers); `chunked_processor.py` by cache-path vs render-path; `playerSlice.ts` by transport vs enhancement state; `enhanced_audio_player.py` by playback control vs fingerprint scheduling (#4249's stated scope).
- **Related**: **#4511 (OPEN** — title still says "track_repository 928 LOC" against a live 1,066**)**, #4673 (CLOSED — the acceptance criterion), #4245 / #4249 / #4250 / #4254 (all **OPEN**, see TD10-2), #5041 / #5042 / #5043 (OPEN).
- **Suggested Fix**: Re-scope #4511 against the live 108-file census instead of its frozen list of 8, and split it into one issue per file for the **top 5 only**, each carrying #4673's acceptance criterion (verify <300 LOC at close, else re-scope and keep open). Leave the tail untracked. Separately, add the census to a tracked ratchet file — the project already runs that pattern twice — since that is the only mechanism here that would have caught `startup.py`'s +161 the day it landed.

### TD9-2: The router-factory pattern makes every backend router a single 200-570 LOC function, so file-level splits cannot reduce function complexity
- **Severity**: LOW
- **Dimension**: File / Function / Module Complexity
- **Location**: `auralis-web/backend/routers/processing_api.py:200` (`create_processing_router`, **567 LOC**), `auralis-web/backend/routers/player.py:249` (`create_player_router`, **518**), `enhancement.py:124` (425), `playlists.py:112` (402), `artwork.py:268` (333), `metadata.py:183` (328), `library_scan.py:36` (256), `similarity.py:104` (247), `albums.py:70` (228), `files.py:124` (207)
- **Status**: NEW — the 2026-08-13 report measured file LOC only; this is the function-level axis it did not cover
- **Age**: architectural, predates the current census
- **Effort**: medium per router (mechanical, but touches every handler)
- **Description**: Every registered router is built by a `create_<name>_router()` factory that defines all of its endpoint handlers as **nested functions inside the factory body**, closing over injected dependencies. The factory is therefore as long as all its handlers combined by construction. `create_player_router` nests 26 inner `def`s serving 19 endpoints in one 518-line function. This is why the file-level LOC issues are hard to close: splitting the *file* does not help while the *function* stays monolithic, and the handlers cannot move to another module without unwinding the closure.
- **Evidence**:
  ```
  80 functions exceed 100 LOC across auralis/ + auralis-web/backend/. Top 10:
    567  routers/processing_api.py:200   create_processing_router
    518  routers/player.py:249           create_player_router
    476  core/stream_normal.py:48        stream_normal_audio
    425  routers/enhancement.py:124      create_enhancement_router
    402  routers/playlists.py:112        create_playlists_router
    393  core/stream_seek.py:41          stream_enhanced_audio_from_position
    370  core/stream_enhanced.py:38      stream_enhanced_audio
    333  routers/artwork.py:268          create_artwork_router
    328  routers/metadata.py:183         create_metadata_router
    297  auralis/analysis/fingerprint/windowed_compute.py:133  compute_windowed_fingerprint

  file                LOC   endpoints   nested defs in factory
  processing_api.py   766      10            11
  player.py           766      19            26
  enhancement.py      548       5             7
  playlists.py        513      10            10
  ```
- **Impact**: Nested handlers cannot be imported, unit-tested in isolation, or relocated — every test must go through the factory and a full dependency set, which is part of why the backend suite is slow and heavily fixture-bound. It also directly amplifies **TD3-1**: the 19 hand-rolled error blocks in `player.py` all live inside one function, so there is no per-handler seam at which the decorator could be applied incrementally.
- **Siblings**: `stream_normal_audio` (476), `stream_enhanced_audio_from_position` (393) and `stream_enhanced_audio` (370) are the same shape without the factory excuse — three near-identical mega-functions, already **#5032 (OPEN)**.
- **Related**: #5032 (OPEN), #4511 / #4673, **TD3-1**, #5035 (OPEN — `create_files_router`'s unused parameter, same factory family).
- **Suggested Fix**: Adopt the pattern already used elsewhere in the codebase: define handlers as **module-level** `async def`s taking dependencies via FastAPI `Depends()` (`routers/dependencies.py` already supplies the DI callables), reducing `create_<name>_router()` to a list of `router.add_api_route(...)` registrations. Do `player.py` first — largest, most endpoint-dense, and the one whose 19 duplicated error blocks TD3-1 needs a seam for.

### Dimension 10 — Audit-Finding Rot

### TD10-2: The skill file's cautionary anecdote about four prematurely-closed god-file issues is stale — all four were reopened
- **Severity**: LOW
- **Dimension**: Audit-Finding Rot
- **Location**: `.claude/commands/audit-tech-debt.md:246`
- **Status**: NEW
- **Age**: the sentence dates from the #4673 hardening (#4673 CLOSED 2026-08-08); the four issues were reopened afterwards
- **Effort**: trivial
- **Description**: Dimension 9's checklist justifies its "close only when verified <300 LOC" acceptance criterion with a specific anecdote: *"Four issues (#4245, #4249, #4250, #4254) were closed in 2026-07 while their targets stayed 2.3-2.7x over the limit."* All four are **OPEN** with `closedAt: null` — the criterion the sentence argues for has already been applied to them. The sentence is historically defensible but reads as a live grievance, with no "(since reopened)" clause.
- **Evidence**:
  ```
  $ for n in 4245 4249 4250 4254; do gh issue view $n --json number,state,closedAt; done
  4245 OPEN closedAt=null    4249 OPEN closedAt=null
  4250 OPEN closedAt=null    4254 OPEN closedAt=null

  Targets at 7e9c401f (still over — the issues remain valid; only the "closed" framing is stale):
    991  chunked_processor.py     (#4245, filed at 958L — grew)
    740  enhanced_audio_player.py (#4249, filed at 821L — shrank)
    964  processing_engine.py     (#4250, filed at 786L — grew)
    789  continuous_mode.py       (#4254)
  ```
  The drift already propagated: `AUDIT_TECH_DEBT_2026-08-13.md` reproduced the claim verbatim as **Top 5 Medium Investments item #5**, recommending as a medium investment work the tracker shows was already done.
- **Impact**: A skill file's motivating example is the text an auditor is most likely to quote without re-checking, because it reads as settled history rather than live state. This one produced a spurious recommendation in the immediately following report. A worked example of how audit-tooling prose rots: the *lesson* stayed true while the *facts* underneath it moved.
- **Siblings**: Related stale issue metadata — **#4511 (OPEN)** is titled "…track_repository 928 LOC + 7 more" against a live 1,066 LOC; **#4673 (CLOSED)** recorded a census of "102 Python + 44 frontend" that is now 108 / 36. Issue titles are GitHub-owned, not repo files, so they are noted rather than filed. Per this dimension's rule, `.claude/issues/<N>/ISSUE.md` snapshots are **not** flagged — GitHub is authoritative — and none are.
- **Related**: #4673 (CLOSED), #4245 / #4249 / #4250 / #4254 (all OPEN), #4511 (OPEN), TD9-1.
- **Suggested Fix**: Rewrite the sentence as *"Four issues (#4245, #4249, #4250, #4254) were closed in 2026-07 with their targets still 2.3-2.7× over the limit, and were reopened once this criterion was adopted — that is the criterion working."* Same lesson, no false current-state implication. Re-scope #4511's title against the live census while there.

---

## Deduped — confirmed present, already tracked, not re-filed

Every row was re-verified against `7e9c401f` this run. Counts in **bold** are updates the issue does not yet reflect.

| Debt | Live state at `7e9c401f` | Issue |
|---|---|---|
| `docs/subsystems/backend-api.md` describes `LibraryManager` as the class startup constructs (`:42,57`, incl. `LibraryManager.shutdown()`) | Confirmed still stale; pairs with TD8-1's identifier rename | #5031 (OPEN) |
| CLAUDE.md's Codebase Map shows `chunked_processor.py`, `audio_stream_controller.py`, `processing_engine.py` without `core/`, and `scanner.py` as a file | Confirmed all four still wrong | #4627 (OPEN) |
| `.claude/agents/library-specialist.md` says "14 repositories"; live count is 13 | Confirmed — but **narrowed from 6 locations / 3 files to 3 locations / 1 file** (`:9,27,68`). `_audit-common.md:152` is already correct. Update the issue's scope before closing | #5044 (OPEN) |
| CLAUDE.md / `_audit-common.md` test-file and test-function counts drifted | **4th occurrence.** Live: **541 files / 6,289 functions**; both docs say 540 / ~6,271. Was verified in sync one day ago | #5045, #5033 (OPEN) |
| `BaseRepository._session_scope()` adoption stalled | Still stalled — **26 raw `with Session(` sites across the 13 repos**. (The issue says "2/14, 111 sites"; yesterday's report said "3/16, 81". Denominators differ by counting method; the qualitative state is unchanged) | #4604 (OPEN) |
| `stream_normal.py` / `stream_enhanced.py` / `stream_seek.py` — three ~400-500 LOC sibling handlers | Confirmed unchanged; see also TD9-2 | #5032 (OPEN) |
| Stream-semaphore `timeout=5.0` duplicated bare in three files | Confirmed verbatim at `stream_enhanced.py:71`, `stream_normal.py:78`, `stream_seek.py:79` — while sibling constants in the same family *are* named module constants in `audio_stream_controller.py` | #4930 (OPEN) |
| `sample_rate=44100` defaults on DSP entry points | Still present. Spot-checked the pipeline-central call sites; **every live caller passes an explicit rate**, so no HIGH promotion is warranted. Not exhaustively recounted | #4622, #4924 (OPEN) |
| `library_manager` dead parameter threaded through `EnhancedAudioPlayer` → `QueueController` | Confirmed declared at `enhanced_audio_player.py:76` and `queue_controller.py:31`, never assigned | #4312 (OPEN) |
| `create_files_router`'s `connection_manager` accepted, threaded, never used | Confirmed still present | #5035 (OPEN) |
| `useFingerprintCache` DEV-only simulated worker + hardcoded 18-field mock fingerprint | Confirmed at `useFingerprintCache.ts:100-144`, still gated behind `import.meta.env.DEV` | #4239, #4667 (OPEN) |
| `Scanner._update_library_stats()` is a reachable log-only no-op | Confirmed at `scanner.py:466-473`, called from `:384`. Practical impact nil — `stats_repository.get_library_stats()` computes counts live | #4243 (OPEN) |
| Sidecar checksum validation deferred by a "for now" comment | Confirmed at `sidecar_manager.py:142-143`. **New detail**: `SidecarManager.compute_checksum()` (`:359`) has **zero callers repo-wide** — the deferral and the orphaned method are one item | #4405 (OPEN) |
| `errorTrackingMiddleware`'s advertised `onRecovery` / `recoveryStrategies` never invoked | Confirmed declared with no call site | #4933 (OPEN) |
| Frontend `src/performance/` toolkit is dead code | Confirmed. **Also accounts for 14 of the 29 shipped `any` usages (48%)** — deleting it halves the shipped type-safety debt | #4696 (OPEN) |
| `learning_system.py` + `audio_content_predictor.py` (1,062 LOC) have zero production consumers | Confirmed — the only cross-reference is between the two files themselves; nothing in `auralis-web/backend` imports either | #4750 (OPEN) |
| Regression suite for CLOSED HIGH #2076 (WebSocket TOCTOU) permanently erroring | Confirmed — `grep -rn active_streams auralis-web/backend/` outside tests returns **zero** hits, so all 8 tests across two files still error unconditionally. **The strongest live example of "regression suite for a closed HIGH provides zero coverage"** | #4941 (OPEN, MEDIUM) |
| `try/except Exception: pytest.skip(...)` converts crashes into silent skips (13 sites / 6 files) | Spot-verified 3 of 13 unchanged | #4969 (OPEN) |
| Skipped tests for removed/deprecated REST endpoints (5+1 sites) | Confirmed present | #4400 (OPEN) |
| Two identical unreferenced perf skips ("Memory measurement unreliable") | Confirmed at `test_memory_profiling.py:307` and `test_audio_processing_performance.py:680` | #5024 (OPEN) |
| `WAVEncoderError` / `WebMEncoderError` unmapped in the global handler | Confirmed. Fixing TD2-1 first collapses this to a one-file change | #3912 (OPEN) |

## Resolved by the tree, not by the tracker — recommend closing

Re-verified live at `7e9c401f` and found already fixed. These are **not** findings; they are triage output for `/audit-publish`.

| Issue | Evidence it is fixed |
|---|---|
| **#5025** (7 stale mutagen `type: ignore[attr-defined]` comments) | Commit `1b906d5a` *"chore: remove 7 stale mutagen type: ignore[attr-defined] comments (#5025)"* has landed; `grep 'type: ignore\[attr-defined\]' … \| grep -i mutagen` returns **0**. |
| **#5029** (six stale `auralis/core/config.py` refs survive #4918) | Only 2 references remain anywhere in `.claude/commands/*.md` (both in `_audit-common.md`, lines 16 and 83) and **both correctly describe the file in the past tense as deleted**. No stale-as-live claim survives. |
| **#5027** (CLAUDE.md and AGENTS.md are drifted duplicate briefs) | `AGENTS.md` is now a 12-line stub pointing at CLAUDE.md and narrating why, citing #5027 by number; CLAUDE.md's header states the same relationship. No longer independently-edited duplicates. |
| **#5028** (Album/Artist repositories inline-duplicate eager-load options) | `album_repository.py:47-64` and `artist_repository.py:89-121` now define named module-level option tuples (`_ALBUM_DETAIL_OPTIONS`, `_ARTIST_LIST_OPTIONS`, …) matching the `track_repository.py` convention; the remaining inline `.options(...)` sites carry explicit "(#5028 CONSISTENCY check)" comments justifying deliberate divergence. |
| **#4289** (`ChunkOperations` redeclares chunk geometry) | `chunk_operations.py` now imports `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION`/`CONTEXT_DURATION` from `chunk_boundaries` as default-parameter values rather than redeclaring literals. Likely superseded by the closed #4914. |
| **#4974** (`_audit-common.md` falsely claims the pytest baseline is checked in) | Resolved by the tree in the *opposite* direction — the baseline **is** now checked in and actively maintained. Closeable, but only alongside TD7-3, which fixes the other line in the same table that never caught up. |

## Deferred

| Item | Gated on |
|---|---|
| Splitting the top-5 oversized Python modules (TD9-1) | #4511 must be re-scoped against the live 108-file census first. Splitting `startup.py` should also wait on **#4764 (OPEN)** — startup-rollback shutdown ordering — to avoid two concurrent rewrites of the same lifespan. |
| Re-greening `_audit-validate.sh` for `docs/**` (TD7-2) | A decision on whether the five historical planning trees (`docs/ui_audit/`, `docs/frontend/PHASE*`, `docs/frontend/analysis/`) move to `docs/archive/` — that choice removes ~85 of the 310 refs without editing a line. |
| Deleting the `DynamicsProcessor` genre-branch literals (TD4-1) | The decision to actually retire `DynamicsProcessor.process()`, which `hybrid_processor.py:80` records as "tracked separately" with no issue number. File that issue first. |
| Converting the router factories (TD9-2) and applying `@with_error_handling` (TD3-1) | These should land together — decorating 19 handlers nested inside one 518-line closure is materially harder than decorating 19 module-level functions. Sequence TD9-2's `player.py` conversion first. |

---

## Coverage

All 10 dimensions produced findings. No dimension failed or returned empty. Dimensions 1,
9 and 10 were run directly by the orchestrator rather than delegated (each was small
enough or already covered by pre-computed data); Dimensions 2-8 ran as subagents, all of
which returned complete, evidenced reports.

Three subagent claims were **corrected by the orchestrator** during the merge rather than
passed through: the `tests/validation/` growth claim (TD2-3), the framing of Dim 2's
TD2-5 as NEW when it duplicated yesterday's TD10-1 (merged, counted once), and Dim 6's
open methodology question on TD6-1's count (reconciled to 57 by a strict AST measure).

### Not covered this pass

- **Rust (`vendor/auralis-dsp/src/`, 19 files)** was checked only for `#[allow(dead_code)]` (0), marker comments (0), and stub/placeholder keywords (0). It was **not** swept for magic numbers (FFT sizes, window constants, filter coefficients), function-length or module-size rules, or backwards-compat cruft. No Rust LOC convention is documented, so there is no rule to measure against — worth deciding one.
- **`auralis/analysis/`** (54 files, the largest module) was not swept for magic numbers, and its function-body-level dead code was not exhaustively checked — only import-level (`ruff F401/F811`, clean) and barrel-export spot checks.
- **Function-body-level dead code generally**: no `vulture` is installed and no `ts-prune` is configured, so the dead-code pass was import-level plus manual basename greps over `hooks/` and `components/`. Frontend `store/`, `services/`, `design-system/` and `types/` were not swept for dead exports.
- **Nesting depth > 4 and cyclomatic complexity** were not measured (no `radon`/`mccabe` available); Dimension 9 measured LOC only. 70 functions between 100 and 200 LOC were counted but not individually triaged.
- **`auralis/optimization/`'s internal API surface** — now established as live (TD10-1) — has never been audited method-by-method at normal severity, because the protocol file instructed auditors to cap severity there. **This is a real coverage hole created by TD10-1 and should be closed by an `/audit-engine` pass once the doc is fixed.**
- **In-code docstring staleness** was sampled only for the specific deleted symbols named in the dimension briefs (`LibraryManager`, `parallel_processor`, `RealtimeDSPPipeline`, `EnhancementContext`, `fingerprint-server`, `auralis/core/config.py`, the categorical branches). A broader sweep for comments referencing other renamed symbols was not attempted.
- **The remaining ~300 of the 310 path-gate hits** were grouped by file and sample-verified (4 samples, all true positives) rather than triaged line by line, per the dimension brief.
- **Correctness is out of scope by design.** Nothing here should be read as a bug finding. The two items closest to correctness are routed rather than scored: **TD6-4** (`record_play` lost-update race) → `/audit-concurrency`; the DC-offset "known limitation" in TD6-2 → `/audit-engine`; `test_sql_injection_in_title`'s weak assertion (TD6-1) → `/audit-security`.

---

*Report generated 2026-08-14 against `7e9c401f`. **No GitHub issues were created. No repository file other than this report was modified. No git write operation was performed.***

**Next step**: `/audit-publish docs/audits/AUDIT_TECH_DEBT_2026-08-14.md`
