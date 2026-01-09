# -*- coding: utf-8 -*-

"""
Simple Mastering Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

Minimal-dependency mastering facade for CLI tools like auto_master.py.
Uses existing DSP components without requiring full HybridProcessor setup.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from ..dsp.basic import amplify, normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ..dsp.utils.stereo import adjust_stereo_width_multiband


class SimpleMasteringPipeline:
    """
    Lightweight mastering pipeline for CLI/batch processing.

    Uses fingerprint-driven adaptive parameters without full HybridProcessor.
    """

    # Target loudness
    TARGET_LUFS = -11.0

    def __init__(self):
        self._fingerprint_service: Optional[FingerprintService] = None

    @property
    def fingerprint_service(self) -> FingerprintService:
        """Lazy-init fingerprint service."""
        if self._fingerprint_service is None:
            self._fingerprint_service = FingerprintService(fingerprint_strategy="sampling")
        return self._fingerprint_service

    def master_file(
        self,
        input_path: str,
        output_path: str,
        intensity: float = 1.0,
        verbose: bool = True,
        time_metrics: bool = False
    ) -> Dict:
        """
        Master an audio file with adaptive processing.

        Args:
            input_path: Input audio file
            output_path: Output WAV file
            intensity: Processing intensity 0.0-1.0
            verbose: Print progress
            time_metrics: Print detailed timing for each step (development only)

        Returns:
            Dict with processing info
        """
        timings: Dict[str, float] = {}
        total_start = time.perf_counter()

        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input not found: {input_path}")

        # Step 1: Get fingerprint
        if verbose:
            print(f"📂 Input: {input_path.name}")
            print(f"📂 Output: {Path(output_path).name}")
            print("\n🔍 Fingerprinting...")

        step_start = time.perf_counter()
        fingerprint = self.fingerprint_service.get_or_compute(input_path)
        timings['fingerprint'] = time.perf_counter() - step_start

        if not fingerprint:
            raise RuntimeError("Failed to compute fingerprint")

        # Step 2: Load audio
        if verbose:
            print("\n🎵 Loading audio...")

        step_start = time.perf_counter()
        audio, sr = librosa.load(str(input_path), sr=None, mono=False)
        audio = audio.astype(np.float32)
        timings['load_audio'] = time.perf_counter() - step_start

        # Ensure stereo
        if audio.ndim == 1:
            audio = np.stack([audio, audio])

        peak_db = self._peak_db(audio)

        if verbose:
            print(f"   Sample rate: {sr} Hz")
            print(f"   Duration: {audio.shape[1] / sr:.1f}s")
            print(f"   Peak: {peak_db:.1f} dB")
            self._print_fingerprint(fingerprint)

        # Step 3: Process
        if verbose:
            print("\n⚡ Processing...")

        step_start = time.perf_counter()
        processed, info = self._process(audio, fingerprint, peak_db, intensity, sr, verbose)
        timings['processing'] = time.perf_counter() - step_start

        # Step 4: Export
        if verbose:
            print("\n💾 Exporting...")

        step_start = time.perf_counter()
        sf.write(output_path, processed.T, sr, subtype='PCM_24')
        timings['export'] = time.perf_counter() - step_start

        timings['total'] = time.perf_counter() - total_start

        if verbose:
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"   ✅ Exported: {size_mb:.1f} MB")
            print(f"\n🎉 Complete! Output: {output_path}")

        if time_metrics:
            self._print_time_metrics(timings, audio.shape[1] / sr)

        result = {
            'input': str(input_path),
            'output': output_path,
            'fingerprint': fingerprint,
            'processing': info
        }

        if time_metrics:
            result['timings'] = timings

        return result

    def _process(
        self,
        audio: np.ndarray,
        fp: Dict,
        peak_db: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Dict]:
        """Core processing logic."""

        lufs = fp.get('lufs', -14.0)
        crest_db = fp.get('crest_db', 12.0)
        bass_pct = fp.get('bass_pct', 0.15)
        transient_density = fp.get('transient_density', 0.5)
        stereo_width = fp.get('stereo_width', 0.5)

        info = {'stages': []}
        processed = audio.copy()

        # Adaptive intensity based on dynamics + loudness
        effective_intensity = self._calculate_intensity(intensity, lufs, crest_db)

        # STAGE 1: Peak reduction for material needing headroom
        # Calculate how much gain we'd ideally apply, then check if we have room
        ideal_gain = max(0.0, self.TARGET_LUFS - lufs)
        headroom_needed = ideal_gain - (0.0 - peak_db)  # peak_db is negative

        if peak_db > -3.0 and headroom_needed > 1.0:
            gain_needed = self.TARGET_LUFS - lufs
            target_peak = max(-8.0, min(-3.0, -1.5 - gain_needed * 0.7))

            if verbose:
                print(f"   Peak reduction: {peak_db:.1f} → {target_peak:.1f} dB")

            processed, peak_db = self._reduce_peaks(processed, peak_db, target_peak)
            info['stages'].append({'stage': 'peak_reduction', 'target': target_peak, 'result': peak_db})

        # STAGE 2: Handle based on 2D Loudness-War Restraint Principle
        if lufs > -12.0 and crest_db < 13.0:
            # Compressed loud → expand + gentle reduction
            if verbose:
                print(f"   Compressed loud (LUFS {lufs:.1f}, crest {crest_db:.1f}) → expansion")

            expansion = max(0.1, (13.0 - crest_db) / 10.0)
            processed = amplify(processed, -0.5)  # Gentle reduction
            info['stages'].append({'stage': 'expansion', 'factor': expansion})

            # Stereo expansion for narrow mixes
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose
            )
            if width_info:
                info['stages'].append(width_info)

            # Safety peak limit after stereo expansion (can add energy)
            current_peak = np.max(np.abs(processed))
            if current_peak > 0.99:
                processed = processed * (0.99 / current_peak)

        elif lufs > -12.0:
            # Dynamic loud → pass-through with optional stereo expansion
            if verbose:
                print(f"   Dynamic loud → preserving original")
            info['stages'].append({'stage': 'passthrough'})

            # Stereo expansion for narrow mixes
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose
            )
            if width_info:
                info['stages'].append(width_info)

            # Safety peak limit after stereo expansion (can add energy)
            current_peak = np.max(np.abs(processed))
            if current_peak > 0.99:
                processed = processed * (0.99 / current_peak)

        else:
            # Quiet material → full processing
            makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
                lufs, effective_intensity, crest_db, bass_pct, transient_density, peak_db
            )

            # Apply makeup gain with modest safety margin for headroom
            # After peak reduction, we have room - don't over-compensate
            makeup_gain = max(0.0, makeup_gain - 0.5)
            if makeup_gain > 0.0:
                if verbose:
                    print(f"   Makeup gain: +{makeup_gain:.1f} dB")
                processed = amplify(processed, makeup_gain)
                info['stages'].append({'stage': 'makeup_gain', 'gain_db': makeup_gain})

            # Bass enhancement for tracks lacking low-end
            # Applied before soft clipping so any peaks get handled gracefully
            processed, bass_info = self._apply_bass_enhancement(
                processed, bass_pct, effective_intensity, sample_rate, verbose
            )
            if bass_info:
                info['stages'].append(bass_info)

            # Soft clipping with loudness-scaled intensity
            loudness_factor = max(0.0, min(1.0, (-11.0 - lufs) / 9.0))
            threshold_db = -2.0 + (1.5 * (1.0 - loudness_factor))
            ceiling = 0.92 + (0.07 * loudness_factor)

            # Fluid bass-aware adjustments using exponential scaling
            # Exponential curve: gentle for moderate bass, aggressive for extreme bass
            # This provides better protection where it's actually needed
            #
            # bass_x: normalized 0.0 at 10% bass → 1.0 at 60% bass
            bass_x = np.clip((bass_pct - 0.10) / 0.50, 0.0, 1.0)
            # Exponential curve: (e^(k*x) - 1) / (e^k - 1), k controls steepness
            k = 3.0  # Higher k = more protection at high bass
            bass_intensity = (np.exp(k * bass_x) - 1) / (np.exp(k) - 1)

            # Scale adjustments fluidly based on bass intensity
            # Exponential means: 20% bass ≈ 0.05, 40% bass ≈ 0.26, 58% bass ≈ 0.85
            threshold_db -= 3.0 * bass_intensity  # Up to -3.0 dB headroom
            ceiling -= 0.12 * bass_intensity  # Ceiling from 0.99 down to 0.80

            threshold_linear = 10 ** (threshold_db / 20.0)

            if verbose:
                print(f"   Soft clip: {threshold_db:.1f} dB, ceiling {ceiling*100:.0f}%")

            processed = soft_clip(processed, threshold=threshold_linear, ceiling=ceiling)
            info['stages'].append({'stage': 'soft_clip', 'threshold_db': threshold_db})

            # Stereo expansion for narrow mixes
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose
            )
            if width_info:
                info['stages'].append(width_info)

            # Final normalization
            target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(lufs)
            adapted_peak = max(0.80, min(0.95, target_peak - (0.05 * loudness_factor)))

            # Smooth bass-aware peak reduction using continuous curve
            # Starts affecting at 10%, full effect at 40%+
            if bass_pct > 0.10:
                bass_peak_factor = np.clip((bass_pct - 0.10) / 0.30, 0.0, 1.0)
                # Cosine curve for smooth onset
                smooth_factor = 0.5 * (1.0 - np.cos(np.pi * bass_peak_factor))
                adapted_peak -= 0.025 * smooth_factor

            if verbose:
                print(f"   Normalize: {adapted_peak*100:.0f}% peak")

            processed = normalize(processed, adapted_peak)
            info['stages'].append({'stage': 'normalize', 'target_peak': adapted_peak})

        info['effective_intensity'] = effective_intensity
        return processed, info

    def _calculate_intensity(self, base: float, lufs: float, crest_db: float) -> float:
        """
        Calculate effective intensity from base + audio characteristics.

        Uses smooth interpolation instead of hard thresholds:
        - Crest factor determines dynamic range preservation needs
        - LUFS determines how much room we have to work with
        """
        # Smooth crest factor curve: 8 dB (compressed) → 15 dB (dynamic)
        # Maps to multiplier range based on material type
        crest_norm = np.clip((crest_db - 8.0) / 7.0, 0.0, 1.0)  # 0=compressed, 1=dynamic

        # LUFS factor: -13 (quiet) → -11 (loud)
        # Quiet material can handle more processing, loud needs preservation
        lufs_norm = np.clip((lufs + 13.0) / 2.0, 0.0, 1.0)  # 0=quiet, 1=loud

        # Intensity multiplier based on 2D space:
        # - Compressed (low crest): always reduce intensity (0.5-0.7)
        # - Dynamic + quiet: boost intensity (up to 1.2)
        # - Dynamic + loud: preserve (reduce to 0.6-0.8)
        if crest_norm < 0.3:
            # Compressed material: gentle processing regardless of loudness
            multiplier = 0.5 + crest_norm * 0.67  # 0.5 → 0.7
        else:
            # Dynamic material: depends on loudness
            # Quiet (lufs_norm=0): multiplier up to 1.2
            # Loud (lufs_norm=1): multiplier down to 0.6
            dynamic_range = 0.7 + (1.0 - crest_norm) * 0.5  # Base for dynamic material
            quiet_boost = (1.0 - lufs_norm) * 0.5  # Extra boost for quiet
            loud_reduction = lufs_norm * 0.4  # Reduction for loud
            multiplier = dynamic_range + quiet_boost - loud_reduction

        return base * np.clip(multiplier, 0.5, 1.2)

    def _reduce_peaks(
        self,
        audio: np.ndarray,
        current_db: float,
        target_db: float
    ) -> Tuple[np.ndarray, float]:
        """Surgical peak reduction via soft clipping."""
        if current_db <= target_db:
            return audio, current_db

        threshold = 10 ** (target_db / 20.0)
        processed = soft_clip(audio, threshold=threshold, ceiling=min(0.99, threshold * 1.05))
        return processed, self._peak_db(processed)

    def _apply_stereo_expansion(
        self,
        audio: np.ndarray,
        current_width: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive multiband stereo expansion for narrow mixes.

        Uses frequency-dependent expansion:
        - Lows (<200Hz): No expansion - keeps kick/bass punchy
        - Low-mids (200-2kHz): 50% expansion - body
        - High-mids (2k-8kHz): 100% expansion - presence
        - Highs (>8kHz): 120% expansion - air/sparkle

        Args:
            audio: Stereo audio [2, samples]
            current_width: Fingerprint stereo_width (0=mono, 1=wide)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress

        Returns:
            (processed_audio, stage_info or None if no expansion applied)
        """
        # Smooth expansion curve - no hard cutoff
        # Full expansion below 0.25, gradual fade from 0.25 to 0.55, none above 0.55
        if current_width >= 0.55:
            return audio, None  # Already wide enough

        # Smooth fade using cosine curve for natural transition
        # width 0.0-0.25: full expansion (narrowness_factor = 1.0)
        # width 0.25-0.55: smooth fade (narrowness_factor = 1.0 → 0.0)
        # width 0.55+: no expansion (narrowness_factor = 0.0)
        if current_width <= 0.25:
            narrowness_factor = 1.0
        else:
            # Cosine fade from 0.25 to 0.55
            fade_position = (current_width - 0.25) / 0.30  # 0.0 → 1.0
            narrowness_factor = 0.5 * (1.0 + np.cos(np.pi * fade_position))  # Smooth S-curve

        # Base expansion scaled by narrowness and intensity
        max_expansion = 0.225 * intensity  # Max at full intensity
        expansion_amount = max_expansion * narrowness_factor

        if expansion_amount < 0.02:
            return audio, None  # Too small to matter

        width_factor = 0.5 + expansion_amount

        # Transpose for multiband function which expects [samples, 2]
        audio_t = audio.T
        expanded = adjust_stereo_width_multiband(audio_t, width_factor, sample_rate)
        processed = expanded.T

        if verbose:
            expansion_pct = (width_factor - 0.5) * 200
            print(f"   Stereo expand: {current_width:.0%} → +{expansion_pct:.0f}% width (multiband)")

        return processed, {
            'stage': 'stereo_expand',
            'original_width': current_width,
            'width_factor': width_factor
        }

    def _apply_bass_enhancement(
        self,
        audio: np.ndarray,
        bass_pct: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive bass enhancement using a low-shelf filter.

        Boosts low frequencies for tracks that need more bass presence.
        The boost scales inversely with detected bass percentage - tracks
        with less bass get more boost.

        Uses a gentle low-shelf filter to avoid harsh transient artifacts
        from reverberant kick drums common in 80s productions.

        Args:
            audio: Stereo audio [2, samples]
            bass_pct: Fingerprint bass percentage (0-1)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress

        Returns:
            (processed_audio, stage_info or None if no enhancement applied)
        """
        # Smooth bass enhancement curve
        # Full boost below 20%, gradual fade from 20% to 50%, none above 50%
        if bass_pct >= 0.50:
            return audio, None  # Already bass-heavy

        # Smooth curve using cosine fade for natural transition
        # bass 0-20%: full boost potential
        # bass 20-50%: smooth fade
        if bass_pct <= 0.20:
            bass_factor = 1.0
        else:
            # Cosine fade from 0.20 to 0.50
            fade_position = (bass_pct - 0.20) / 0.30  # 0.0 → 1.0
            bass_factor = 0.5 * (1.0 + np.cos(np.pi * fade_position))

        # Calculate boost based on bass deficiency and fade factor
        # Max boost at very low bass (< 15%)
        max_boost_db = 2.5 * intensity * bass_factor
        bass_deficiency = max(0.0, 0.30 - bass_pct) / 0.30  # How much bass is missing
        boost_db = max_boost_db * bass_deficiency

        if boost_db < 0.5:
            return audio, None  # Too small to matter

        # Design a gentle low-shelf filter at 100Hz
        # Using a 2nd order Butterworth lowpass, then scaling the low content
        shelf_freq = 100.0
        nyquist = sample_rate / 2
        normalized_freq = min(0.99, max(0.01, shelf_freq / nyquist))

        # Extract low frequencies
        sos_lp = butter(2, normalized_freq, btype='low', output='sos')
        sos_hp = butter(2, normalized_freq, btype='high', output='sos')

        # Split into low and high bands
        low_band = sosfilt(sos_lp, audio, axis=1)
        high_band = sosfilt(sos_hp, audio, axis=1)

        # Apply boost to low band only
        boost_linear = 10 ** (boost_db / 20)
        low_boosted = low_band * boost_linear

        # Recombine
        processed = low_boosted + high_band

        if verbose:
            print(f"   Bass enhance: +{boost_db:.1f} dB below 100Hz")

        return processed, {
            'stage': 'bass_enhance',
            'boost_db': boost_db,
            'bass_pct': bass_pct
        }

    @staticmethod
    def _peak_db(audio: np.ndarray) -> float:
        """Calculate peak level in dB."""
        peak = np.max(np.abs(audio))
        return 20 * np.log10(peak) if peak > 0 else -96.0

    @staticmethod
    def _print_fingerprint(fp: Dict) -> None:
        """Print key fingerprint metrics."""
        print(f"\n📊 Fingerprint:")
        print(f"   LUFS: {fp.get('lufs', 0):.1f} dB")
        print(f"   Crest: {fp.get('crest_db', 0):.1f} dB")
        print(f"   Bass: {fp.get('bass_pct', 0):.0%}")
        print(f"   Width: {fp.get('stereo_width', 0.5):.0%}")
        print(f"   Tempo: {fp.get('tempo_bpm', 0):.0f} BPM")

    @staticmethod
    def _print_time_metrics(timings: Dict[str, float], duration_sec: float) -> None:
        """Print detailed timing breakdown (development only)."""
        print("\n⏱️  Time Metrics:")
        print("   ─────────────────────────────────────")

        # Individual steps
        for step, elapsed in timings.items():
            if step == 'total':
                continue
            pct = (elapsed / timings['total']) * 100
            print(f"   {step:<15} {elapsed:>7.2f}s  ({pct:>5.1f}%)")

        print("   ─────────────────────────────────────")
        print(f"   {'TOTAL':<15} {timings['total']:>7.2f}s  (100.0%)")

        # Real-time ratio
        realtime_ratio = duration_sec / timings['total']
        print(f"\n   Audio duration: {duration_sec:.1f}s")
        print(f"   Real-time ratio: {realtime_ratio:.1f}x")


# Factory function
def create_simple_mastering_pipeline() -> SimpleMasteringPipeline:
    """Create a simple mastering pipeline instance."""
    return SimpleMasteringPipeline()
