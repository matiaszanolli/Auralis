# Mastering Algorithm "Dulling" Research — Current State
**Date**: 2026-07-08
**Status**: 🔎 RESEARCH / DIAGNOSIS — no code changes yet
**Reported symptom**: The offline mastering algorithm (`SimpleMastering`) produces a much smaller overall improvement over source material than it used to. The hypothesis is that a sequence of targeted fixes for specific problem tracks (dark/bass-heavy, quiet/high-crest vintage, buried-vocal) has cumulatively suppressed enhancement on typical, non-outlier material — i.e. we tuned away harshness on the tails and lost effect size in the middle of the distribution.

This document is a factual snapshot: current pipeline architecture, the exact numeric history of every tuning change to date, and the mechanism by which those changes could compound into "dulling." It does not yet contain a verdict — see **Open Questions** and **What I Need From You** at the end.

---

## 1. Which algorithm this is about

Auralis has **two independent mastering paths**. This report is about the second one only:

1. `HybridProcessor` / real-time adaptive mode (26-band psychoacoustic EQ + advanced dynamics) — used for live playback enhancement. Documented (stale, 2025-11-17) in [MASTERING_QUALITY_BASELINE_METRICS.md](MASTERING_QUALITY_BASELINE_METRICS.md) and [MASTERING_QUALITY_IMPROVEMENT_SESSION.md](MASTERING_QUALITY_IMPROVEMENT_SESSION.md). **Not in scope here.**
2. `SimpleMastering` — the offline full-file remaster path (`auto_master.py` → `SimpleMasteringPipeline.master_file` → per-chunk `_process` → `MaterialClassifier` → one of three branches in `auralis/core/mastering_branches.py`). **This is the algorithm the user is describing**, and the one all of the June 2026 tuning sessions worked on.

Anyone comparing against the Nov 2025 baseline metrics doc should discard it — it measured the *other* pipeline and predates `mastering_branches.py`'s current form entirely.

---

## 2. Current architecture

**Routing** (`MaterialClassifier.classify`, only two thresholds decide the branch):

| Condition | Branch |
|---|---|
| `LUFS > -12` and `crest < 13 dB` | `CompressedLoudBranch` |
| `LUFS > -12` and `crest ≥ 13 dB` | `DynamicLoudBranch` |
| `LUFS ≤ -12` | `QuietBranch` |

**Stage chains:**

- **CompressedLoud**: notches → RMS expansion (skipped if crest < 8) → stereo → harmonic exciter → clarity → presence → air → safety-limiter. HF stages run at `intensity × 0.7`.
- **DynamicLoud**: notches → stereo → exciter → clarity → presence → air → safety-limiter. HF stages run at `intensity × 0.5`.
- **Quiet**: notches → makeup gain → bass enhancement/de-mask → sub-bass control → transient shaper → mid-warmth → exciter (crest-attenuated) → clarity (with vocal-mask trigger) → presence → air → adaptive soft-clip → stereo → loudness maximizer → local normalize.

Only `QuietBranch` ever touches bass, sub-bass, transients, mid-warmth, or the loudness maximizer — the two loud branches' only enhancement is gentle HF shelving plus stereo widening.

Every HF stage (exciter/clarity/presence/air) multiplies its boost by up to **four independent restraints** stacked together: the branch intensity factor (0.5–0.7 on loud material) × `min(intensity, 1.0)` × a shared `hf_lift` budget (0.3–1.0, from `hf_budget.py`) × an inverse content-factor (`1 - ramp(existing_band_content)`, so bands that already look "healthy" get pushed toward zero boost).

Several stages (bass, sub-bass, mid-warmth, clarity) are hard **no-ops inside a tolerance band** around the reference-set median (e.g. bass 0.35–0.55 of spectral energy, sub-bass ≤0.13, clarity deficit ≤0.015). A track sitting inside all of these bands — i.e. an already reasonably-balanced, "typical" master — receives **zero** low/mid/clarity EQ by design.

---

## 3. Tuning history (chronological, with exact numeric deltas)

| Date | Commit | Change | Effect |
|---|---|---|---|
| 2026-01-09 | `cd2d8fc4` | "Gentler audio processing to preserve dynamics and clarity" | Earliest recorded instance of the same pattern: reduce aggressiveness to fix a harshness/dynamics complaint. |
| 2026-01-12 | `12fac530` | Replaced hard thresholds with smooth curves throughout mastering | Introduced the "ramp/inverse-factor" gating style that underlies today's tolerance-band no-ops. |
| 2026-02-14 | `d6bdd7ef` | Extracted CompressedLoud/DynamicLoud/Quiet as a strategy-pattern branch split | Current 3-branch architecture born. |
| 2026-05-20 | `c55d008f`, `53e9cece`, `2a162a99` | Added notches/transients/clarity/cascade-exciter stages; "evidence-based tolerance bands" for bass & clarity | This is where today's docstrings ("reduced from -6→-9 dB", "notch count 5→3", "notch depth -5→-4 dB", "bass cut -3→-2 dB") originate — i.e. these specific reductions predate the June sessions the team remembers as "the tuning." |
| 2026-06-01 | `c4a7d31f` | Decomposed `simple_mastering.py` into the `stages/` package (11 modules) | Structural only, no magnitude change. |
| 2026-06-02 | `0445aff3` | HF overdrive/bass saturation/transients/stereo/loudness fix (charlyfito1 case: dark, bass-heavy, narrow, -16.8 LUFS, 13.9 crest) | New `hf_budget.py` shared ceiling; capped `intensity = min(intensity, 1.0)` on all 4 HF stages (previously the Quiet branch fed them intensity up to 1.2×, i.e. this *removed* an existing overdrive); flipped bass soft-clip from *lowering* threshold on bass-heavy material to *raising* it; stereo `max_expansion` raised 0.08→0.13 (an increase, not a cut) and narrow sources widen more. |
| 2026-06-02 | `1069e743` | Protect high-DR dynamics in Quiet branch; handle >2ch audio | Added crest-keyed exciter attenuation (full below 12 dB crest, ramping to ×0.15 above 22 dB) and soft-clip bypass above 22 dB crest. |
| 2026-06-02 | `6d36e666` | Multi-window LUFS + True Peak guard | **Accuracy fix, not a cap**: single-90s-window LUFS (RMSE 1.96, max error 9.2 dB) replaced with median-of-3-window estimate (RMSE 1.07, max error 3.6 dB). This alone removed up to ~9 dB of *erroneous* extra makeup gain that had been firing on inaccurate LUFS reads — i.e. some of what felt like "more mastering" before this fix was a measurement bug, not a deliberate effect. |
| 2026-06-09 | `afa700e1` | Restore competitive loudness for quiet high-DR material (Oktubre case: -19 LUFS, 18-21 dB crest, coming out only +1-3 dB louder) | **New stage added** (`loudness_maximizer.py`), not a reduction: pushes gain toward -15.5 LUFS target for anything below -14 LUFS competitive threshold, capped by crest headroom and a 10 dB max push. |
| 2026-06-09 | `0e544ee3` | Unmask buried vocals + preserve drum punch (Gulp 1985 case: vocal 6-9 dB under bass) | New vocal-mask de-mask/clarity-lift stages (net effect: *more* processing on this specific problem, not less), but also added `LOUDNESS_MAX_CREST_REDUCTION_DB = 3.0`, which **caps how much the newly-added loudness maximizer above is allowed to push** — a real ceiling introduced on top of a feature added the same week. |
| 2026-06-10 → 2026-06-28 | `a9df2a7f`, `eb3d2013`, `c70af27e`, `e350bf67`, `6387d245` | Filter-floor fix, temp-dir cleanup, zero-phase HP, NaN/Inf guards, copy-not-alias in transient shaper | Correctness-only; no magnitude/aggressiveness effect. |

**One likely unintentional dulling bug found in this pass**: `stages/air_enhancement.py` hardcodes `max_boost_db = 1.5` internally and never reads `MAX_AIR_BOOST_DB = 2.5` from `mastering_config.py`. That is a ~40% silent cap on air-band boost versus what the config declares as the intended ceiling. This looks like config/code drift, not a deliberate decision — worth confirming and fixing regardless of the broader dulling question.

---

## 4. Working hypothesis on why the overall effect shrank

None of the individual June fixes reads, in isolation, like an across-the-board cut — most either added new gates for a *specific* pathology (dark/bass-heavy, buried-vocal) or, in the loudness-maximizer and stereo-expansion cases, **increased** treatment. The dulling most plausibly comes from **compounding**, not any single change:

1. **Every fix so far was validated against one named problem track** (charlyfito1, Oktubre, Gulp 1985 — all documented in memory/`mastering-engine-tuning.md`), each an outlier on some axis (darkness, LUFS/crest combination, vocal masking). There is no evidence in the repo of any fix being checked against a broad sample of *already-decent* masters to confirm it didn't also flatten their treatment. The fixes are locally correct and globally unverified.
2. **The four independent HF restraints are multiplicative**, not additive — a loud-branch track already discounted to 0.5-0.7× intensity, times a partially-tapered `hf_lift`, times an inverse content-factor that trends toward zero as the source's presence/air already look adequate, can land at a small fraction of the nominal max boost even though no single gate looks severe on its own.
3. **Tolerance-band no-ops mean "typical" material (by construction) gets zero bass/sub/mid/clarity EQ.** As the reference-set medians used to define those bands get refined (as happened 2026-05-20 with "evidence-based tolerance bands"), the definition of "typical" — and therefore the no-op zone — can silently widen, which would look exactly like "less improvement on most tracks" without any single commit being the culprit.
4. **The loud branches (which cover any track above -12 LUFS, i.e. most commercially loud modern masters) never invoke bass, sub-bass, transient, mid-warmth, or loudness-maximizer stages at all.** Their entire enhancement budget is HF shelving (already discounted per #2) plus stereo widening. If "the algorithm doesn't do much anymore" is specifically about already-loud source material, this by-design narrowness is the direct explanation, not a regression.

---

## 5. What's NOT yet known / documentation gaps

- **No current before/after quality metrics exist for `SimpleMastering`.** The only quantified baseline in `docs/` (Nov 2025) measured the *other*, now-superseded pipeline and can't be used as a reference point.
- **No broad/representative test corpus was used to validate the June fixes** — each was checked against the one track that motivated it (per `mastering-engine-tuning.md` memory), not against a "typical material" control set. We don't know the enhancement magnitude (LUFS lift, DR change, spectral tilt, stereo width delta) the algorithm currently produces on a normal, non-outlier mix.
- **The prior iteration harnesses referenced in memory no longer exist**: `/tmp/audit/iterate.py`, `diag_gulp.py`, `gulp_all.py`, `gulp_beforeafter.py` were all under `/tmp/audit/`, which has since been reused by an unrelated session (now full of JIRA/Atlassian audit dumps) — `/tmp` is not persistent storage. These would need to be rewritten from scratch to reproduce prior measurements.
- **No definition of "the overall improvement" as a number.** The user's complaint is currently qualitative ("much smaller"). We don't have a target effect size (e.g. "+X LUFS on average", "+Y dB clarity lift on typical rock/pop masters") to measure against.

---

## 6. Empirical confirmation — Gulp (1985) + Oktubre (1986) full-album test (2026-07-08)

Per the user's request, I ran `auto_master.py` on both full albums from `/mnt/Musica/Musica/Patricio Rey y sus Redonditos de Ricota/` (the same two 1980s Argentine rock records already used as tuning fixtures — Gulp's track 07 for the buried-vocal fix, Oktubre for the loudness-undertreatment fix). All 21 tracks (12 Gulp + 9 Oktubre) were mastered and measured against source using the project's own ITU-R BS.1770-4 `LoudnessMeter` (full-file integration, not the sampling-strategy fingerprint proxy — the fingerprint's `lufs` field read 3-4 dB quieter than the true measurement on this material, confirming the under-read the Oktubre fix's memory note already warned about).

**Results (all 21 tracks, true BS.1770 LUFS + broadband crest, full file):**

| | Source | Master | Δ |
|---|---|---|---|
| Integrated LUFS (mean) | -17.75 | -13.93 | **+3.82 dB** (range +1.97 to +6.94) |
| Crest factor dB (mean) | 18.98 | 17.90 | **-1.08 dB** (range +0.39 to -3.04) |
| True peak (master) | — | ~-0.50 dBTP on 20/21 tracks | pinned at the `QuietBranch` local-normalize ceiling |

Two numbers confirm the hypothesis directly:

- **21/21 tracks (100%)** have source crest factor inside the **12-22 dB exciter/soft-clip attenuation ramp** added in `1069e743` specifically to protect Oktubre (a single high-DR outlier at the time). That ramp was designed as a guard for unusually dynamic vintage material — on this two-album sample it is not an edge case, it is the entire distribution. Every track gets the exciter and soft-clip pulled back toward their weakest settings (down to ×0.15 wet / bypassed) by a gate meant to fire rarely.
- Only **10/21 (48%)** masters reach the -14 LUFS "competitive" threshold (`LOUDNESS_COMPETITIVE_LUFS`) that would let a track exit the loudness-maximizer path; the rest land at -14.0 to -15.3, i.e. the maximizer's own `LOUDNESS_TARGET_LUFS = -15.5` ceiling — which is itself well below every reference engineer's range documented in [MASTERING_QUALITY_VALIDATION.md](../guides/MASTERING_QUALITY_VALIDATION.md) (Andy Wallace -11 to -9, Quincy Jones -12 to -10, even the "audiophile" Steven Wilson reference is -14 to -11).
- Crest barely moves (mean -1.08 dB; several tracks it goes to the cap of `LOUDNESS_MAX_CREST_REDUCTION_DB = 3.0` but most don't even reach that — the exciter/soft-clip crest-ramp is limiting first). Post-master crest of ~18 dB is far above the reference-engineer DR range (9-14 dB per the same validation doc). This is measurable, not impressionistic: the masters gain loudness almost entirely through gain, with negligible added punch/tightness — which reads as "same shape, just turned up" rather than "mastered," and plausibly IS the "contrary to the old production sound" the user is hearing (period rock masters of this era were comparatively punchier/more compressed than a flat gain-up of the raw tape transfer).

**Conclusion**: this is no longer just a hypothesis from reading the code — on a concrete, real two-album sample, the guard rails added to fix one Oktubre-shaped outlier (`1069e743`, `afa700e1`, `0e544ee3`) turn out to blanket-cover this entire era/genre of material. The "dulling" is real and reproducible on this corpus, and its mechanism is now identified precisely: the crest-keyed attenuation ramp's boundaries (12-22 dB) and the loudness maximizer's target (-15.5 LUFS) were calibrated against a single reference track, not against the wider population of high-crest vintage rock they also gate.

Rendered masters + raw before/after numbers for all 21 tracks are in the scratchpad (`mastering_test/gulp/`, `mastering_test/oktubre/`, `ab_report.txt`, `lufs_true_report.txt`) for anyone who wants to listen before changing thresholds.

---

## 7. Recalibration (2026-07-08, same session)

Per the user's direction ("probably miscalibrated... dynamics are a huge part of the recording sound we want to improve on... compensate between dimensions"), built a persistent multi-dimensional regression harness (`research/scripts/mastering_calibration_harness.py`) covering: `charlyfito1` (the original HF/bass-overdrive fixture), two compressed/dynamic-loud tracks from the existing pytest suite (Iron Maiden, Stratovarius — must stay untouched, outside `QuietBranch`), two more quiet-branch tracks from that same suite (Porcupine Tree, Blind Guardian — catch collateral effects on material not yet profiled), and the full Gulp + Oktubre albums (21 tracks). Every run measures true BS.1770 LUFS + crest source→master for all cases, plus voice/bass ratio for Gulp/07 specifically (the buried-vocal fixture).

**Attempt 1 (reverted): widen the exciter/soft-clip crest-attenuation ramp.** Raised `CLIP_RELAX_CREST`/`CLIP_BYPASS_CREST` in `mastering_branches.py` from 18/22 dB to 20/26 dB, reasoning that the ramp added in `1069e743` was calibrated on one track and (per §6) covers this entire genre. Measured effect: **negligible** — Gulp dLUFS mean 3.73→3.70, dCrest mean -0.61→-0.60; Oktubre dLUFS mean 3.94→3.74, dCrest -1.70→-1.57. Root cause: the soft-clipper's knee (threshold ≈ -2 to -0.5 dB, ceiling ≈ 0.92-0.99) is gentle enough that shifting where it starts relaxing barely changes its output — it was never the dominant lever. Reverted to 18/22 (see comment in `mastering_branches.py`); this is documented here specifically so nobody re-attempts the same fix expecting a different result.

**Attempt 2 (kept): raise the loudness-maximizer's own target/cap.** Traced the actual bottleneck: `loudness_maximizer.py`'s push formula is `(LOUDNESS_TARGET_LUFS - source_lufs) * undermastered`. With the old `LOUDNESS_TARGET_LUFS = -15.5`, most of this corpus (true source LUFS -15.6 to -19.6) computed a push near or under the 0.5 dB audible floor — the stage was a **near-permanent no-op** for exactly the material it was built for; the loudness gain we measured in §6 came almost entirely from the branch's own final peak-normalize, not this stage. Changed in `mastering_config.py`:
- `LOUDNESS_TARGET_LUFS`: -15.5 → **-12.5** (near the measured 'competitive' cluster already used for `LOUDNESS_COMPETITIVE_LUFS`)
- `LOUDNESS_MAX_CREST_REDUCTION_DB`: 3.0 → **6.0** (the old cap was binding hardest on exactly the highest-crest tracks that had the most room to trade before sounding flat; `LOUDNESS_MIN_CREST_DB` = 11 dB remains the hard floor against crushing)

**Measured result (full harness re-run):**

| Category | dLUFS before → after | dCrest before → after |
|---|---|---|
| Gulp (12 tracks) | +3.73 → **+4.69** mean | -0.61 → **-1.73** mean |
| Oktubre (9 tracks) | +3.94 → **+5.42** mean | -1.70 → **-3.13** mean |
| Porcupine Tree + Blind Guardian (quiet_other, 2 tracks) | +2.55 → +3.71 mean | -1.75 → -2.63 mean |
| Iron Maiden + Stratovarius (out of scope, 2 tracks) | unchanged | unchanged |
| charlyfito1 (outlier_dark, 1 track) | unchanged (strict no-op both times — its true LUFS, ~-13.6, is already at/above `LOUDNESS_COMPETITIVE_LUFS`, so the maximizer never engages regardless of target/cap) | unchanged |

Post-master crest now runs ~13.0-18.1 dB across Gulp/Oktubre (down from ~15.1-19.7 dB before recalibration) — real, audible dynamics/punch improvement, though still above the 9-14 dB "world-class reference" band in `MASTERING_QUALITY_VALIDATION.md`, so there's headroom for a further pass if wanted.

**Cross-dimension checks (the "compensate between dimensions" ask):**
- **HF/bass-overdrive (charlyfito1)**: provably unaffected — the file's own true LUFS sits above `LOUDNESS_COMPETITIVE_LUFS`, so `loudness_maximizer` is a strict no-op for it both before and after; none of its other stages (exciter, bass, presence, air) read either changed constant.
- **Buried-vocal (Gulp/07 "Te voy a Atornillar")**: voice/bass ratio source -5.59 dB → master **-1.56 dB** (vocal now much closer to bass level, not buried) — improved, not regressed, alongside the +3.52 dB LUFS lift and -1.47 dB crest reduction on that same track.
- **Out-of-scope branches (Iron Maiden, Stratovarius — CompressedLoud/DynamicLoud)**: byte-identical before/after, confirming the change is fully contained to `QuietBranch`.
- **Existing pytest suite** (`tests/regression/test_mastering_regression.py`): 4 failed / 2 passed, unchanged from the pre-existing baseline noted in project memory — all 4 failures assert on the *source* fingerprint's own LUFS/crest/bass_pct/stage-list (i.e. input classification, computed by code this change never touches), not on anything `loudness_maximizer` or `mastering_config.py` affects. No new failures introduced.

**Net**: this is a real, measured, cross-checked improvement — not another guess. Harness + raw JSON for all three runs (before, crest-ramp attempt, loudness-recalibration) are in the session scratchpad for anyone who wants to re-verify or extend to more tracks.

---

## 8. Still open

§7's recalibration is applied and cross-checked, not just proposed. What's left:

1. **Whether to push further.** Post-master crest is now ~13-18 dB across Gulp/Oktubre — better, but still above the 9-14 dB "world-class reference" band in [MASTERING_QUALITY_VALIDATION.md](../guides/MASTERING_QUALITY_VALIDATION.md) (written for the other pipeline, `HybridProcessor` — whether that's the right target for `SimpleMastering`'s vintage-material path is itself a judgment call, not just a number to hit). A second, smaller pass on the same two constants could get closer if that's the goal.
2. **The `air_enhancement.py` hardcoded 1.5 dB vs. declared 2.5 dB config bug (§3)** is still unfixed — untouched by this recalibration, independent small correctness fix whenever wanted.
3. Whether to run this same before/after harness against a broader, non-Redonditos sample (different genre/era) before considering this closed, since everything validated so far is either the two original albums or four tracks from the existing pytest suite.
