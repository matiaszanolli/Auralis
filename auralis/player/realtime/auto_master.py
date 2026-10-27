"""
Auto Master Processor
~~~~~~~~~~~~~~~~~~~~~

Automatic mastering with genre-aware processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.core.utils import fingerprint_default
import threading
from typing import Any

import numpy as np

from ...dsp.dynamics import AdaptiveCompressor
from ...dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer
from ...dsp.dynamics.settings import CompressorSettings
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ...utils.logging import debug, info, warning
from ...core.utils.fingerprint_unpacker import FingerprintUnpacker
from ..config import PlayerConfig
from .peak_ceiling import StreamingPeakCeiling


class AutoMasterProcessor:
    """
    Automatic mastering with fingerprint-aware adaptive processing.

    Supports two processing modes:
    1. Profile-based (fallback): Static gains per profile
    2. Fingerprint-adaptive (preferred): Content-aware gains from 25D analysis
    """

    def __init__(self, config: PlayerConfig):
        self._lock = threading.Lock()
        self.config = config
        self.enabled = False

        # Fingerprint and adaptive parameters
        self.fingerprint: dict[str, Any] | None = None
        self.adaptive_params: dict[str, Any] | None = None

        # DSP components are built for the configured rate and rebuilt by
        # set_sample_rate() when a loaded track's actual rate differs
        # (#5729) — the timing constants (attack/release, transient
        # window) are sample-rate-derived and silently mis-scaled at any
        # other rate.
        self._sample_rate = config.sample_rate
        self.compressor = self._build_compressor(self._sample_rate)
        self.transient_enhancer = LowMidTransientEnhancer(sample_rate=self._sample_rate)
        self.use_transient_enhancement = True

        # Adaptive peak ceiling as a per-sample envelope carried across chunks
        # (#5721), not a per-chunk `target_peak / current_peak` scalar.
        self.peak_ceiling = StreamingPeakCeiling(self._sample_rate)

        debug("AutoMasterProcessor initialized")

    def _build_compressor(self, sample_rate: int) -> AdaptiveCompressor:
        """Build the stateful compressor that prevents gain pumping.

        Settings prioritize transient preservation to avoid kick/bass
        harmonic overlap: high threshold and very gentle ratio so only very
        loud peaks are compressed, slow attack to let transients breathe
        through, long release for smooth recovery, and a wide soft knee
        for an ultra-smooth curve. No lookahead (real-time).
        """
        comp_settings = CompressorSettings(
            threshold_db=-24.0,
            ratio=1.3,
            attack_ms=20.0,
            release_ms=200.0,
            knee_db=10.0,
            makeup_gain_db=0.0,
            enable_lookahead=False
        )
        return AdaptiveCompressor(comp_settings, sample_rate)

    def set_sample_rate(self, sample_rate: int) -> None:
        """Reconfigure the DSP chain for a track's actual sample rate.

        Called with every processed chunk's rate; a no-op unless the rate
        actually changed (e.g. after load or a gapless swap to a track at
        another rate). Rebuilds the compressor and transient enhancer —
        their envelopes re-adapt within one attack/release cycle (~220 ms).
        """
        with self._lock:
            if sample_rate == self._sample_rate:
                return
            info(f"Auto-master sample rate changed: {self._sample_rate} -> {sample_rate} Hz; "
                 "rebuilding compressor and transient enhancer")
            self._sample_rate = sample_rate
            self.compressor = self._build_compressor(sample_rate)
            self.transient_enhancer = LowMidTransientEnhancer(sample_rate=sample_rate)
            self.peak_ceiling.set_sample_rate(sample_rate)

    def set_enabled(self, enabled: bool) -> None:
        """Thread-safe setter for enabled flag (#3356)."""
        with self._lock:
            self.enabled = enabled

    def set_fingerprint(self, fingerprint: dict[str, Any]) -> None:
        """
        Set 25D fingerprint for adaptive processing.

        Args:
            fingerprint: 25D fingerprint dictionary from FingerprintService
        """
        # Generate params outside lock (pure computation, no side effects)
        params = self._generate_adaptive_parameters(fingerprint)
        with self._lock:
            self.fingerprint = fingerprint
            self.adaptive_params = params
        info(f"Auto-master fingerprint set: LUFS {fingerprint.get('lufs', fingerprint_default('lufs')):.1f}, "
             f"crest {fingerprint.get('crest_db', fingerprint_default('crest_db')):.1f} dB")

    def clear_fingerprint(self) -> None:
        """Clear track-specific adaptive state and use profile mastering."""
        with self._lock:
            self.fingerprint = None
            self.adaptive_params = None
        info("Auto-master fingerprint cleared; using profile-based mastering")

    def _generate_adaptive_parameters(
        self,
        fingerprint: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate content-aware processing parameters from fingerprint.

        Same logic as auto_master.py's generate_adaptive_parameters()
        """
        # Extract key fingerprint metrics
        fp = FingerprintUnpacker.from_dict(fingerprint)
        lufs = fp.lufs
        crest_db = fp.crest_db

        # Calculate adaptive makeup gain using centralized logic
        makeup_gain_db, reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs=lufs,
            intensity=1.0,
            crest_factor_db=crest_db,
        )

        # Calculate adaptive compression ratio based on dynamic range
        if crest_db > 15:  # High dynamic range
            compression_ratio = 1.5  # Gentle compression
        elif crest_db > 12:  # Moderate dynamic range
            compression_ratio = 2.0
        else:  # Low dynamic range (already compressed)
            compression_ratio = 2.5

        # Calculate adaptive target peak
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(lufs)

        return {
            'makeup_gain_db': makeup_gain_db,
            'compression_ratio': compression_ratio,
            'target_peak': target_peak,
            'reasoning': reasoning,
        }

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic mastering with fingerprint-aware adaptive processing"""
        with self._lock:
            return self._process_locked(audio)

    def _process_locked(self, audio: np.ndarray) -> np.ndarray:
        """Inner processing — caller must hold self._lock."""
        if not self.enabled:
            return audio

        processed = audio.copy()

        # Apply stateful compression with the compressor's linked per-sample
        # peak envelope. Its gentle settings preserve transients without an
        # inert, caller-selected detection mode.
        processed, _ = self.compressor.process(processed)

        # Determine which gain to apply
        if self.adaptive_params is not None:
            # Use fingerprint-adaptive gain
            makeup_gain_db = self.adaptive_params['makeup_gain_db']
            debug(f"Applying adaptive gain: {makeup_gain_db:.1f} dB")
        else:
            # No fingerprint yet: unity gain. (#5586: the retired warm/bright/
            # punchy profile table averaged to exactly this for 'balanced',
            # so the audible fallback is unchanged by its removal.)
            makeup_gain_db = 0.0
            debug("No fingerprint set: applying unity gain")

        # Apply gain with clipping protection measured on post-compression audio,
        # not the raw input — using the pre-compression peak would over-penalise
        # material that the compressor has already brought under control (#2310).
        # Cap gain to available headroom so the expected output peak never exceeds
        # 0.98 (-0.18 dBFS). The old proportional-attenuation approach (floored at
        # 0.8×) could not prevent clipping when peaks were already near 0 dBFS.
        processed_peak = np.max(np.abs(processed))
        if processed_peak > 0 and makeup_gain_db > 0:
            max_safe_gain_db = 20 * np.log10(0.98 / processed_peak)
            if makeup_gain_db > max_safe_gain_db:
                debug(f"Capped gain {makeup_gain_db:.1f} → {max(max_safe_gain_db, 0.0):.1f} dB "
                      f"(headroom protection, peak {20*np.log10(processed_peak):.1f} dBFS)")
                makeup_gain_db = max(max_safe_gain_db, 0.0)

        # Apply makeup gain in linear scale
        if makeup_gain_db != 0:
            gain_linear = 10 ** (makeup_gain_db / 20.0)
            processed *= gain_linear

        # Optional: Apply low-mid transient enhancement for quiet, dynamic material
        # This restores punch to bass, piano, vocals after compression
        if self.use_transient_enhancement and self.fingerprint is not None:
            # #6219: a partial fingerprint falls back to the table defaults
            # (-14 LUFS / 12 dB crest), not 0 — with 0 the quiet-and-dynamic
            # gate below could never fire for missing keys.
            lufs = self.fingerprint.get('lufs', fingerprint_default('lufs'))
            crest_db = self.fingerprint.get('crest_db', fingerprint_default('crest_db'))

            # Enhance for quiet + dynamic material (1990s style)
            if lufs < -13.0 and crest_db > 14.0:
                debug(f"Applying low-mid transient enhancement (LUFS {lufs:.1f}, crest {crest_db:.1f} dB)")
                try:
                    # Use moderate intensity for real-time (not aggressive like batch)
                    transient_intensity = 0.35  # Subtle, not overwhelming
                    # 50 ms window at the track's actual rate (#5729), not
                    # the configured one.
                    attack_samples = int(self._sample_rate * 0.05)
                    processed = self.transient_enhancer.enhance_transients(
                        processed,
                        intensity=transient_intensity,
                        attack_samples=attack_samples
                    )
                    debug(f"Transient enhancement applied (intensity: {transient_intensity:.2f})")
                except Exception as e:
                    warning(f"Transient enhancement failed: {e}")

        # Apply adaptive peak ceiling from fingerprint parameters.
        # target_peak is computed by _generate_adaptive_parameters() but was never
        # consumed here — quieter sources got a higher ceiling (0.90) while loud
        # sources got a tighter one (0.85), acting as a final safety net that
        # accounts for transient enhancement potentially adding back peak energy.
        if self.adaptive_params is not None:
            target_peak = self.adaptive_params['target_peak']
            current_peak = np.max(np.abs(processed))
            if current_peak > target_peak:
                debug(f"Adaptive peak ceiling: {20*np.log10(current_peak):.1f} → "
                      f"{20*np.log10(target_peak):.1f} dBFS")
            processed = self.peak_ceiling.apply(processed, target_peak)

        return processed

    def get_stats(self) -> dict[str, Any]:
        """Get auto-master statistics"""
        with self._lock:
            return self._get_stats_locked()

    def _get_stats_locked(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'has_fingerprint': self.fingerprint is not None,
            'adaptive_params': self.adaptive_params,
            'transient_enhancement_enabled': self.use_transient_enhancement,
        }
