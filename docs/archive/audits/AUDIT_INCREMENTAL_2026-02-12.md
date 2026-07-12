# Incremental Audit Report — 2026-02-12

## Change Summary

**Commit range**: `aadd1858..3e44f533` (10 commits)
**Date range**: Recent development cycle
**Key themes**: Mastering algorithm improvements (crossfade, parallel EQ, RMS expansion), CI/CD restructuring, audit tooling

### Commits Audited

| Commit | Message | Risk |
|--------|---------|------|
| `3e44f533` | feat: Add 6 audit slash commands and remove auto-issue-creation scripts | MEDIUM |
| `0a5df7a3` | fix: Add equal-power crossfade between mastering chunks | HIGH |
| `922812a8` | fix: Allow backup GitHub workflows in .gitignore | LOW |
| `c9566e7f` | feat: Add comprehensive CI/CD workflows for backend, frontend, and release | MEDIUM |
| `8bc5b217` | fix: Use parallel processing for sub-bass control | HIGH |
| `8adbd72b` | docs: Add parallel processing pattern guide | LOW |
| `4876c942` | fix: Resolve spectral loss in mastering pipeline | HIGH |
| `3ac56f26` | fix: Update the mastering algorithm | HIGH |
| `632b629c` | fix: Use parallel processing for EQ to prevent phase cancellation | HIGH |
| `aadd1858` | fix: Use RMS reduction expansion for compressed loud material | HIGH |

### Files Changed by Risk Domain

| Domain | Files | Risk |
|--------|-------|------|
| **Audio Core** | `auralis/core/simple_mastering.py` | HIGH |
| **DSP Utils** | `auralis/dsp/utils/stereo.py` | HIGH |
| **Tests** | `tests/regression/test_mastering_regression.py` | LOW |
| **CI/CD** | `.github/workflows/*`, `.github/scripts/*`, `.github/workflows.backup/*` | MEDIUM |
| **Docs** | `docs/development/PARALLEL_PROCESSING_GUIDE.md` | LOW |
| **Config** | `.gitignore`, `.claude/commands/*` | LOW |

---

## High-Risk Changes

### 1. `auralis/core/simple_mastering.py` — Mastering Algorithm (6 commits)

**Changes across commits**:

1. **Equal-power crossfade** (`0a5df7a3`): Added `sin²/cos²` crossfade between internal mastering chunks, replacing hard concatenation. Uses `np.sin(t)**2` and `np.cos(t)**2` curves that sum to 1.0 at all points, maintaining constant power.

2. **Parallel EQ processing** (`632b629c`, `4876c942`, `8bc5b217`): Refactored all EQ stages (`_apply_bass_management`, `_apply_mid_presence_balance`, `_apply_presence_enhancement`, `_apply_air_enhancement`) from sequential band-split-recombine to parallel additive pattern:
   ```python
   band = sosfilt(sos_bp, audio, axis=1)
   processed = audio + band * (boost_linear - 1.0)
   ```
   This avoids crossover notches that occur when splitting into bands and recombining with `sosfiltfilt`.

3. **RMS reduction expansion** (`aadd1858`): For compressed loud material, replaced peak enhancement expansion with RMS reduction via `ExpansionStrategies.apply_rms_reduction_expansion()`. This increases crest factor by reducing RMS rather than boosting peaks — a safer approach that avoids clipping.

4. **Pre-EQ headroom** (`3ac56f26`): Added -2dB headroom before EQ processing to prevent clipping from EQ boosts, with makeup gain after.

5. **Safety limiter** (`3ac56f26`): Added `_apply_safety_limiter()` as a final stage with soft clipping at -0.5dB ceiling.

6. **Unified output normalization** (`3ac56f26`): All processing branches now set `needs_output_normalize = True/False` consistently, with normalization applied in a single post-processing block.

**Audit verdict**: All changes are **correct and well-structured**:
- Sample count invariant (`len(output) == len(input)`) is preserved through all new code paths
- `audio.copy()` is used before in-place modification
- The parallel EQ pattern is mathematically sound (additive difference preserves flat frequency response)
- Equal-power crossfade math is correct (`sin²(t) + cos²(t) = 1`)
- All branches properly set `needs_output_normalize`

### 2. `auralis/dsp/utils/stereo.py` — Stereo Width (1 commit)

**Changes** (`8bc5b217`): Refactored `adjust_stereo_width_multiband()` from LR4 crossover band-split to parallel additive processing, matching the pattern used in `simple_mastering.py`:
```python
diff = band_widened - band_original
result = stereo_audio + diff_lowmid + diff_highmid + diff_high
```

Also inverted the expansion factor curve — old code gave more expansion to bass, new code correctly gives more expansion to higher frequencies (matching psychoacoustic expectations — bass should stay centered).

**Audit verdict**: **Correct**, but left dead code (see INC-01 below).

### 3. `tests/regression/test_mastering_regression.py` — Spectral Tests (1 commit)

**Changes** (`0a5df7a3`): Added `measure_spectral_bands()` function for FFT-based band energy measurement. Added spectral preservation validation comparing input vs output in air and presence bands. Updated expected stages to accept `rms_expansion`, `skip_expansion`, or legacy `expansion`.

**Audit verdict**: Good improvements. Test coverage now includes spectral preservation which catches the class of bugs that motivated the parallel processing refactors.

---

## Medium-Risk Changes

### 4. CI/CD Restructuring (`3e44f533`, `c9566e7f`, `922812a8`)

**Changes**:
- **Deleted**: `.github/workflows/test-with-issue-creation.yml`, `.github/workflows/backend-tests.yml`, `.github/workflows/build-release.yml`, `.github/workflows/ci.yml`, `.github/workflows/frontend-build.yml`, `.github/workflows/README.md`
- **Deleted**: `.github/scripts/create_test_issues.py`, `.github/scripts/test_issue_creation.sh`, `.github/scripts/README.md`
- **Added**: `.github/workflows.backup/` with copies of deleted workflows
- **Added**: `.gitignore` entry for `.github/workflows.backup/`

**Audit verdict**:
- The deletion of all active CI workflows means **no CI currently runs** on push/PR. This is a significant gap — any code pushed now has no automated testing. However, this appears intentional (the workflows were backed up, suggesting a planned transition to new CI setup).
- The auto-issue-creation script was replaced by audit slash commands, which is a reasonable replacement for manual auditing but not for CI-triggered test failure tracking.
- No security concerns — the deleted scripts used `GITHUB_TOKEN` from secrets, not hardcoded values.

---

## Findings

### INC-01: Dead code `_linkwitz_riley_4` in stereo.py
- **Severity**: LOW
- **Changed File**: `auralis/dsp/utils/stereo.py:83-93` (commit: `8bc5b217`)
- **Status**: NEW
- **Description**: The `_linkwitz_riley_4()` function creates a 4th-order Linkwitz-Riley crossover filter. After the refactor to parallel processing, this function has zero callers anywhere in the codebase. It was previously used by the old band-split approach in `adjust_stereo_width_multiband()` but is now orphaned.
- **Evidence**:
  ```python
  def _linkwitz_riley_4(freq: float, btype: str) -> np.ndarray:
      """Create 4th-order Linkwitz-Riley filter (LR4, 24dB/octave)."""
      sos1 = butter(2, freq, btype=btype, output='sos')
      sos2 = butter(2, freq, btype=btype, output='sos')
      return np.vstack([sos1, sos2])
  ```
  `grep -r "_linkwitz_riley_4"` returns only the definition at line 83 — no callers.
- **Impact**: Minor code bloat. Could confuse future developers into thinking LR4 crossovers are still used.
- **Suggested Fix**: Remove the function. If needed in the future, it can be restored from git history.

### INC-02: Duplicate `ExpansionStrategies` class
- **Severity**: MEDIUM
- **Changed File**: `auralis/core/processing/base_processing_mode.py:701` vs `auralis/core/processing/base/compression_expansion.py:122`
- **Status**: NEW
- **Description**: The `ExpansionStrategies` class exists in two locations with identical implementations. The active version is in `base/compression_expansion.py` (imported by `simple_mastering.py` via `processing/base/__init__.py`). The version in `base_processing_mode.py` at line 701 is dead code — nothing imports from `base_processing_mode.py` anywhere in the codebase.
- **Evidence**:
  - Active import chain: `simple_mastering.py` → `from .processing.base import ExpansionStrategies` → `base/__init__.py` → `compression_expansion.py:122`
  - Dead copy: `base_processing_mode.py:701` — `grep -r "from.*base_processing_mode import"` returns 0 results
- **Impact**: Code duplication creates maintenance risk — if someone fixes a bug in one copy but not the other, or accidentally imports from the wrong module.
- **Suggested Fix**: Remove `ExpansionStrategies` (and likely `CompressionStrategies`, `MeasurementUtilities`, and other duplicated classes) from `base_processing_mode.py`. The extracted `base/` package is the canonical location.

### INC-03: Linear crossfade in chunked_processor vs equal-power in mastering
- **Severity**: LOW
- **Changed File**: `auralis-web/backend/chunked_processor.py:1081-1082` (pre-existing, not from these commits)
- **Status**: Existing: related to `0a5df7a3` but not a regression
- **Description**: The chunked processor uses linear crossfade (`np.linspace(1.0, 0.0, N)`), while the mastering pipeline now uses equal-power crossfade (`sin²/cos²`). Linear crossfade causes a -6dB dip at the midpoint, which can be audible as a brief volume drop at chunk boundaries.
- **Evidence**:
  ```python
  # chunked_processor.py:1081-1082 (LINEAR - causes -6dB dip)
  fade_out = np.linspace(1.0, 0.0, actual_overlap)
  fade_in = np.linspace(0.0, 1.0, actual_overlap)

  # simple_mastering.py (EQUAL-POWER - constant loudness)
  fade_in = np.sin(t) ** 2
  fade_out = np.cos(t) ** 2
  ```
- **Impact**: Subtle volume dip at 30s chunk boundaries during WebSocket streaming. Not a regression — this is pre-existing behavior, but the mastering pipeline now demonstrates the better approach.
- **Suggested Fix**: Update `chunked_processor.py:apply_crossfade_between_chunks()` to use equal-power crossfade matching `simple_mastering.py`.

### INC-04: All CI workflows deleted — no automated testing
- **Severity**: MEDIUM
- **Changed File**: `.github/workflows/` (commits: `3e44f533`, `c9566e7f`)
- **Status**: NEW
- **Description**: All 5 active GitHub Actions workflows were deleted (backed up to `.github/workflows.backup/`). No replacement workflows were added. This means pushes and PRs to master currently have zero CI protection.
- **Evidence**: `ls .github/workflows/` returns empty (all files deleted in `3e44f533`). Backup directory exists but `.gitignore` entry was added for it (`922812a8`), so backups won't be tracked.
- **Impact**: Code can be merged to master without any automated testing. Regressions in audio processing, backend API, or frontend may go undetected until manual testing.
- **Suggested Fix**: Either restore the workflows from `.github/workflows.backup/` or create new streamlined CI workflows. At minimum, a workflow running `pytest -m "not slow" -v` on push/PR should be active.

---

## Cross-Layer Impact

### Mastering ↔ Chunked Processor
- **No conflict**: The mastering crossfade (within `simple_mastering.py`) and the chunked processor crossfade (within `chunked_processor.py`) operate at different levels. The mastering crossfade handles boundaries between internal processing chunks within a single mastering pass. The chunked processor crossfade handles boundaries between 30s streaming chunks. They don't interfere.
- **The chunked processor does NOT call `simple_mastering.py`** — it uses `HybridProcessor` which is a separate processing pipeline. No import path exists between them.

### ExpansionStrategies Import Chain
- `simple_mastering.py` correctly imports from `processing/base/compression_expansion.py` via `processing/base/__init__.py`. No callers use the dead copy in `base_processing_mode.py`. The import chain is clean.

### Regression Test Coverage
- The updated `test_mastering_regression.py` now validates spectral preservation (air and presence band loss thresholds), which directly tests the parallel EQ changes. This is good coverage for the most impactful changes.

---

## Missing Tests

1. **Stereo width parallel processing**: No unit test validates `adjust_stereo_width_multiband()` against the old LR4 implementation. The regression tests only check if `stereo_expand` stage runs, not the frequency-dependent width profile.

2. **RMS reduction expansion**: No unit test for `ExpansionStrategies.apply_rms_reduction_expansion()` verifying that crest factor increases while peak level doesn't change.

3. **Safety limiter**: The new `_apply_safety_limiter()` method has no dedicated test.

---

## Summary

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| INC-01 | Dead code `_linkwitz_riley_4` in stereo.py | LOW | NEW |
| INC-02 | Duplicate `ExpansionStrategies` class | MEDIUM | NEW |
| INC-03 | Linear crossfade in chunked_processor | LOW | Pre-existing |
| INC-04 | All CI workflows deleted | MEDIUM | NEW |

**Overall assessment**: The audio processing changes (crossfade, parallel EQ, RMS expansion) are **well-implemented and correct**. The parallel processing pattern is mathematically sound, sample count invariants are preserved, and spectral test coverage was added. The main concerns are dead code cleanup (INC-01, INC-02) and the absence of CI workflows (INC-04).
