"""
Quiet Branch
~~~~~~~~~~~~

Processing strategy for quiet material needing makeup gain (#4252).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ...dsp.basic import amplify, normalize
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ..mastering_config import SimpleMasteringConfig
from ..stages.hf_budget import hf_lift_factor
from ..utils import FingerprintUnpacker, StageRecorder
from .base import ProcessingBranch
from .soft_clip_params import compute_soft_clip_threshold


class QuietBranch(ProcessingBranch):
    """
    Handle quiet material (LUFS <= -12).

    Needs full processing with makeup gain, comprehensive frequency shaping,
    and adaptive soft clipping.

    Processing steps:
    1. Calculate adaptive makeup gain
    2. Apply makeup gain
    3. Bass enhancement
    4. Sub-bass control
    5. Mid warmth
    6. Presence + air enhancements
    7. Adaptive soft clipping (multi-dimensional awareness)
    8. Stereo width expansion
    9. Peak normalize to target LUFS

    Self-normalizes (soft-clip then branch-local ``normalize``) and opts OUT of
    the unified pipeline normalization (``needs_output_normalize=False``) to
    avoid double-normalizing — the mirror-opposite of the loud branches. See
    ``ProcessingBranch`` for the full canonical stage order and the gain-staging
    contract (#4103).
    """

    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Apply quiet material processing."""

        from ...dsp.dynamics.soft_clipper import soft_clip

        processed = audio.copy()
        recorder = StageRecorder()

        # Crest-factor thresholds shared between exciter attenuation and the
        # soft-clip bypass/relax logic further below.
        #
        # 2026-07-08 calibration note: widening these to 20/26 (from 18/22) was
        # tried and measured to have negligible effect (<0.15 dB on both LUFS
        # and crest across the Gulp 1985 + Oktubre 1986 albums) — the
        # soft-clipper's knee is gentle enough that where it starts relaxing
        # barely changes its output. Reverted; see mastering_config.py's
        # LOUDNESS_* constants for the change that actually moved these
        # numbers (docs/sessions/MASTERING_ALGORITHM_DULLING_RESEARCH_2026-07-08.md).
        CLIP_BYPASS_CREST = 22.0   # ≥ this → skip soft_clip, minimal exciter
        CLIP_RELAX_CREST  = 18.0   # ≥ this → relax soft_clip knee, reduce exciter

        # Resonance notches first — surgical narrow cuts in 150-1200 Hz so all
        # subsequent EQ stages see the post-notch energy balance. No-op if no
        # resonances were detected for this file.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        # Calculate adaptive makeup gain
        makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
            unpacker.lufs, effective_intensity, unpacker.crest_db,
            unpacker.bass_pct, unpacker.transient_density, peak_db
        )

        # Apply makeup gain with modest safety margin for headroom
        makeup_gain = max(0.0, makeup_gain - 0.5)
        if makeup_gain > 0.0:
            if verbose:
                print(f"   Makeup gain: +{makeup_gain:.1f} dB")
            processed = amplify(processed, makeup_gain)
            recorder.add({'stage': 'makeup_gain', 'gain_db': makeup_gain})

        # Bass enhancement OR de-congestion (bidirectional based on bass_pct).
        # mid_pct/upper_mid_pct feed the de-mask cut that lowers the masking
        # bass when the voice is buried (paired with the clarity-boost lift).
        processed, bass_info = self.pipeline._apply_bass_enhancement(
            processed, unpacker.bass_pct, effective_intensity, sample_rate, verbose,
            unpacker.mid_pct, unpacker.upper_mid_pct
        )
        recorder.add(bass_info)

        # Sub-bass control - tighten rumble (with HP for bursty rumble)
        processed, sub_bass_info = self.pipeline._apply_sub_bass_control(
            processed, unpacker.sub_bass_pct, unpacker.bass_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(sub_bass_info)

        # Transient shaper — restore attack on compressed kick/bass. Applied
        # after bass EQ (so we shape the final levels) but before mid-warmth
        # (so the warmth doesn't sustain over the restored attacks).
        processed, transient_info = self.pipeline._apply_transient_shaper(
            processed, unpacker.bass_pct, unpacker.low_mid_pct,
            unpacker.crest_db, effective_intensity, sample_rate, verbose
        )
        recorder.add(transient_info)

        # Mid-range warmth for thin mixes
        processed, warmth_info = self.pipeline._apply_mid_warmth(
            processed, unpacker.low_mid_pct, unpacker.mid_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(warmth_info)

        processed = self._assert_finite(processed, "Quiet after low-end/warmth")

        # Shared HF lift budget — restrains exciter + clarity + presence + air
        # from stacking into fizz on HF-dead sources (was +6 dB relative presence
        # lift on dark material). See DynamicLoudBranch for rationale.
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter — generate new HF content for bandwidth-limited or
        # dark sources. Runs after mid-warmth (donor band is now shaped) and
        # before presence/air (so those shelves can lift the new harmonics).
        # Engages only when air/presence/rolloff indicate genuinely dark material.
        #
        # High-DR attenuation: tracks with large crest factors have wide dynamic
        # swing — they are naturally expressive, not crushed. Adding heavy
        # harmonic generation raises RMS while peaks are controlled by normalize,
        # reducing the crest factor and making the track sound compressed.
        # Scale exciter intensity down for high-DR sources proportionally.
        # Thresholds are shared with the soft-clip bypass block below so that
        # both decisions track the same measurement:
        #   crest < 12 dB               → full exciter (compressed sources benefit most)
        #   crest 12 dB–CLIP_RELAX_CREST  → blend 1.0 → 0.5 (gentle ramp)
        #   crest CLIP_RELAX_CREST–CLIP_BYPASS_CREST → blend 0.5 → 0.15 (conservative; avoid RMS inflation)
        #   crest ≥ CLIP_BYPASS_CREST   → 0.15x cap (near-bypass; truly wide-dynamic sources)
        if unpacker.crest_db >= CLIP_BYPASS_CREST:
            exciter_intensity = effective_intensity * 0.15
        elif unpacker.crest_db >= CLIP_RELAX_CREST:
            blend = (unpacker.crest_db - CLIP_RELAX_CREST) / (CLIP_BYPASS_CREST - CLIP_RELAX_CREST)
            exciter_intensity = effective_intensity * (0.5 - blend * (0.5 - 0.15))
        elif unpacker.crest_db >= 12.0:
            blend = (unpacker.crest_db - 12.0) / (CLIP_RELAX_CREST - 12.0)
            exciter_intensity = effective_intensity * (1.0 - blend * 0.5)
        else:
            exciter_intensity = effective_intensity       # < 12 dB: full intensity

        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            exciter_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for vocal/snare definition. Sits between
        # the exciter (which fed new harmonics into 4-8 kHz) and the presence
        # shelf (which lifts 2-8 kHz broadly). The clarity bell narrows the
        # focus to 1.5-3.5 kHz where consonants and attack-snap live. bass_pct/
        # mid_pct enable the relative vocal-masking trigger (voice buried under
        # a dominant bass), which the absolute Up-Mid deficit alone misses.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift,
            unpacker.bass_pct, unpacker.mid_pct
        )
        recorder.add(clarity_info)

        # Presence enhancement for dull mixes
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        # Air enhancement for dark mixes
        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        processed = self._assert_finite(processed, "Quiet after spectral")

        # Soft clipping with multi-dimensional awareness. The loudness-scaled
        # base plus the harmonic/variation/flatness/bass preservation
        # adjustments are computed in compute_soft_clip_threshold (#4252); the
        # high-DR bypass/relax decision and the soft_clip call stay here.
        threshold_db, ceiling = compute_soft_clip_threshold(unpacker, config, verbose)

        # High-DR bypass: when the source has large dynamic range (high crest
        # factor), the soft clipper acts as a heavy limiter and crushes the
        # transients that define the recording's character (orchestral swells,
        # live acoustic events, expressive dynamics). For these sources the gain
        # normalisation alone is sufficient — no saturation needed.
        # CLIP_BYPASS_CREST / CLIP_RELAX_CREST are defined at the top of this
        # method (shared with the exciter attenuation block).
        if unpacker.crest_db >= CLIP_BYPASS_CREST:
            if verbose:
                print(f"   Soft clip bypassed (crest {unpacker.crest_db:.1f} dB — high-DR source)")
            recorder.add({'stage': 'soft_clip', 'threshold_db': 'bypassed (high-DR)', 'crest_db': unpacker.crest_db})
        else:
            if unpacker.crest_db >= CLIP_RELAX_CREST:
                # Blend from current threshold toward 0 dB as crest → BYPASS
                dr_blend = (unpacker.crest_db - CLIP_RELAX_CREST) / (CLIP_BYPASS_CREST - CLIP_RELAX_CREST)
                threshold_db  = threshold_db  + dr_blend * (0.0 - threshold_db)
                ceiling       = ceiling       + dr_blend * (0.97 - ceiling)

            threshold_linear = 10 ** (threshold_db / 20.0)
            if verbose:
                print(f"   Soft clip: {threshold_db:.1f} dB, ceiling {ceiling*100:.0f}%")
            processed = soft_clip(processed, threshold=threshold_linear, ceiling=ceiling)
            recorder.add({'stage': 'soft_clip', 'threshold_db': threshold_db})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.bass_pct, unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Loudness maximizer — competitive loudness for genuinely UNDER-MASTERED
        # sources (quiet AND high-crest, e.g. vintage/lo-fi rock at -22 LUFS).
        # The makeup gain above is capped/zeroed for high-crest material and the
        # final peak-normalize pins loudness to (peak - crest), so without this
        # such tracks came out only ~1-3 dB louder than source. Reducing the
        # crest factor (push-then-limit) is the only lever that raises loudness
        # once peaks are at the ceiling. Strict no-op for already-competitive
        # sources (LUFS >= LOUDNESS_COMPETITIVE_LUFS), so the well-mastered
        # 'good' tier is untouched. Runs AFTER stereo expansion so the limiter
        # also catches any mid/side peaks the widening introduced, and BEFORE
        # the final normalize which lifts the limited peak back to the ceiling.
        # Prefer the accurate ITU-R BS.1770 loudness measured per-file in
        # master_file; fall back to the fingerprint values on the direct
        # _process() path (e.g. unit tests) where it was not measured.
        src_lufs = self.pipeline._source_lufs
        src_crest = self.pipeline._source_crest_db
        processed, loudness_info = self.pipeline._apply_loudness_maximizer(
            processed,
            src_lufs if src_lufs is not None else unpacker.lufs,
            src_crest if src_crest is not None else unpacker.crest_db,
            sample_rate, verbose
        )
        recorder.add(loudness_info)

        # Final normalization — competitive loudness, dynamics protected.
        #
        # A pure peak-normalize is gain only, so crest factor (transient punch)
        # is preserved exactly: we can push the ceiling up for a competitive
        # ~ -14 LUFS master WITHOUT crushing dynamics. The previous target
        # (~0.84 peak, pulled down further for bass) left the "master" QUIETER
        # than the source — backwards. We now normalize quiet material close to
        # full scale and let the write-stage hard clip + soft clipper above
        # handle the few remaining peaks. The earlier bass-aware peak reduction
        # is dropped: the bass is now kept clean by the soft-clip threshold
        # raise, so there's no reason to throw away level for it.
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(unpacker.lufs)
        # target_peak is 0.85 (loud) … 0.90 (quiet); lift it toward the ceiling.
        adapted_peak = float(np.clip(target_peak + 0.07, 0.90, 0.97))

        if verbose:
            print(f"   Normalize: {adapted_peak*100:.0f}% peak (competitive, crest-preserving)")

        processed = normalize(processed, adapted_peak)
        recorder.add({'stage': 'normalize', 'target_peak': adapted_peak})

        processed = self._assert_finite(processed, "Quiet after soft-clip/stereo/normalize")

        # Return without normalization flag (quiet branch does its own)
        info = recorder.to_dict()
        info['needs_output_normalize'] = False
        return processed, info
