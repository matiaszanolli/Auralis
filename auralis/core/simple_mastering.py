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

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from ..dsp.basic import amplify, normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ..dsp.utils.stereo import adjust_stereo_width_multiband
from .processing.base import ExpansionStrategies


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
        Master an audio file with adaptive processing using chunked processing.

        Memory-efficient: Processes audio in chunks instead of loading entire file.

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

        # Step 2: Get audio metadata without loading full file
        if verbose:
            print("\n🎵 Loading metadata...")

        step_start = time.perf_counter()
        with sf.SoundFile(str(input_path)) as audio_file:
            sr = audio_file.samplerate
            total_frames = len(audio_file)
            channels = audio_file.channels
            duration = total_frames / sr

        timings['load_metadata'] = time.perf_counter() - step_start

        if verbose:
            print(f"   Sample rate: {sr} Hz")
            print(f"   Duration: {duration:.1f}s")
            print(f"   Channels: {channels}")
            self._print_fingerprint(fingerprint)

        # Step 3: Process in chunks (memory efficient)
        if verbose:
            print("\n⚡ Processing (chunked)...")

        step_start = time.perf_counter()

        # Process and write in streaming mode
        chunk_size = sr * 30  # 30 seconds per chunk
        info = {'stages': []}

        with sf.SoundFile(str(input_path)) as audio_file:
            with sf.SoundFile(
                output_path,
                mode='w',
                samplerate=sr,
                channels=channels,
                subtype='PCM_24'
            ) as output_file:
                chunks_processed = 0
                total_chunks = int(np.ceil(total_frames / chunk_size))

                # Calculate peak from first chunk for adaptive processing
                audio_file.seek(0)
                first_chunk = audio_file.read(chunk_size)
                if first_chunk.ndim == 1:
                    first_chunk = np.stack([first_chunk, first_chunk]).T
                peak_db = self._peak_db(first_chunk.T)

                # Reset to start for full processing
                audio_file.seek(0)

                while True:
                    # Read chunk
                    chunk = audio_file.read(chunk_size)
                    if chunk.size == 0:
                        break

                    # Ensure float32
                    chunk = chunk.astype(np.float32)

                    # Ensure stereo (channels, samples) format
                    if chunk.ndim == 1:
                        chunk = np.stack([chunk, chunk]).T

                    # Convert to (channels, samples) for processing
                    if chunk.shape[0] > chunk.shape[1]:  # (samples, channels)
                        chunk = chunk.T

                    # Process chunk
                    processed_chunk, chunk_info = self._process(
                        chunk, fingerprint, peak_db, intensity, sr, verbose=False
                    )

                    # Update info from first chunk
                    if chunks_processed == 0:
                        info = chunk_info

                    # Convert back to (samples, channels) for writing
                    if processed_chunk.shape[0] < processed_chunk.shape[1]:
                        processed_chunk = processed_chunk.T

                    # Write chunk
                    output_file.write(processed_chunk)

                    chunks_processed += 1
                    if verbose and chunks_processed % 5 == 0:
                        progress = (chunks_processed / total_chunks) * 100
                        print(f"   Progress: {progress:.0f}% ({chunks_processed}/{total_chunks} chunks)")

        timings['processing'] = time.perf_counter() - step_start

        timings['total'] = time.perf_counter() - total_start

        if verbose:
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"   ✅ Exported: {size_mb:.1f} MB")
            print(f"   📦 Processed {chunks_processed} chunks")
            print(f"\n🎉 Complete! Output: {output_path}")

        if time_metrics:
            self._print_time_metrics(timings, duration)

        result = {
            'input': str(input_path),
            'output': output_path,
            'fingerprint': fingerprint,
            'processing': info,
            'chunks_processed': chunks_processed
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
        """Core processing logic using all 25D fingerprint dimensions."""

        # Dynamics (3D)
        lufs = fp.get('lufs', -14.0)
        crest_db = fp.get('crest_db', 12.0)
        bass_mid_ratio = fp.get('bass_mid_ratio', 0.0)

        # Frequency (7D) - all bands
        sub_bass_pct = fp.get('sub_bass_pct', 0.05)
        bass_pct = fp.get('bass_pct', 0.15)
        low_mid_pct = fp.get('low_mid_pct', 0.10)
        mid_pct = fp.get('mid_pct', 0.20)
        upper_mid_pct = fp.get('upper_mid_pct', 0.25)
        presence_pct = fp.get('presence_pct', 0.15)
        air_pct = fp.get('air_pct', 0.10)

        # Temporal (4D)
        tempo_bpm = fp.get('tempo_bpm', 120.0)
        rhythm_stability = fp.get('rhythm_stability', 0.5)
        transient_density = fp.get('transient_density', 0.5)
        silence_ratio = fp.get('silence_ratio', 0.0)

        # Spectral (3D) - brightness indicators
        spectral_centroid = fp.get('spectral_centroid', 0.5)
        spectral_rolloff = fp.get('spectral_rolloff', 0.5)
        spectral_flatness = fp.get('spectral_flatness', 0.5)

        # Harmonic (3D)
        harmonic_ratio = fp.get('harmonic_ratio', 0.5)
        pitch_stability = fp.get('pitch_stability', 0.5)
        chroma_energy = fp.get('chroma_energy', 0.5)

        # Variation (3D)
        dynamic_range_variation = fp.get('dynamic_range_variation', 0.5)
        loudness_variation_std = fp.get('loudness_variation_std', 0.0)
        peak_consistency = fp.get('peak_consistency', 0.5)

        # Stereo (2D)
        stereo_width = fp.get('stereo_width', 0.5)
        phase_correlation = fp.get('phase_correlation', 1.0)

        info = {'stages': []}
        processed = audio.copy()

        # Adaptive intensity based on dynamics + loudness
        effective_intensity = self._calculate_intensity(intensity, lufs, crest_db)

        # STAGE 1: Gentle peak reduction for clipping prevention only
        # Only intervene when peak is dangerously close to or above 0 dBFS
        # Uses smooth S-curve to avoid filtering effect - just prevents actual clipping
        if peak_db > -0.5:
            # Smooth curve: gentle near threshold, stronger for severe clipping
            # clip_severity: 0 at -0.5 dB, 1 at +2 dB
            clip_severity = np.clip((peak_db + 0.5) / 2.5, 0.0, 1.0)
            # S-curve for smooth transition (cosine)
            smooth_factor = 0.5 * (1.0 - np.cos(np.pi * clip_severity))

            # Target: -0.5 to -2.0 dB based on severity (much gentler than old -3.0 floor)
            # peak at -0.5 → target -0.5 (no change)
            # peak at 0 → target ~-0.6 (gentle 0.6 dB reduction)
            # peak at +1 → target ~-1.5 (1.5 dB reduction from 0 dBFS)
            # peak at +2 → target -2.0 (max reduction)
            target_peak = -0.5 - smooth_factor * 1.5

            if verbose:
                print(f"   Peak reduction: {peak_db:.1f} → {target_peak:.1f} dB")

            processed, peak_db = self._reduce_peaks(processed, peak_db, target_peak)
            info['stages'].append({'stage': 'peak_reduction', 'target': target_peak, 'result': peak_db})

        # STAGE 2: Handle based on 2D Loudness-War Restraint Principle
        if lufs > -12.0 and crest_db < 13.0:
            # Compressed loud material - use RMS reduction expansion (not peak enhancement)
            # Peak enhancement boosts all peaks including bass, causing muddiness
            # RMS reduction increases crest factor without inflating low-frequency transients

            if crest_db < 8.0:
                # Hyper-compressed (crest < 8 dB): skip expansion entirely
                # This material is intentionally brick-walled, respect the artistic choice
                if verbose:
                    print(f"   Hyper-compressed (LUFS {lufs:.1f}, crest {crest_db:.1f}) → skip expansion")
                info['stages'].append({'stage': 'skip_expansion', 'reason': 'hyper_compressed'})
            else:
                # Moderately compressed (8-13 dB): gentle RMS reduction expansion
                # Target: restore ~2 dB of crest factor via RMS reduction
                target_crest_increase = min(2.0, 13.0 - crest_db)  # Cap at 2 dB
                expansion_amount = 0.5  # Conservative application

                if verbose:
                    print(f"   Compressed loud (LUFS {lufs:.1f}, crest {crest_db:.1f}) → RMS expansion +{target_crest_increase:.1f} dB")

                # Apply RMS reduction expansion (reduces level, increases crest without bass pump)
                exp_params = {
                    'target_crest_increase': target_crest_increase,
                    'amount': expansion_amount
                }
                processed = ExpansionStrategies.apply_rms_reduction_expansion(processed, exp_params)
                info['stages'].append({'stage': 'rms_expansion', 'target_crest': target_crest_increase})

            # Stereo expansion for narrow mixes (brightness-aware)
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose, bass_pct,
                spectral_centroid, air_pct, phase_correlation
            )
            if width_info:
                info['stages'].append(width_info)

            # Pre-EQ headroom: attenuate before spectral boosts to prevent limiter from
            # clipping HF transients. The output normalization will restore level.
            # This preserves spectral balance better than post-EQ limiting.
            pre_eq_headroom_db = -2.0  # Reserve 2 dB for EQ boosts
            pre_eq_gain = 10 ** (pre_eq_headroom_db / 20)
            processed = processed * pre_eq_gain

            # Spectral enhancements (presence & air) for all paths
            processed, presence_info = self._apply_presence_enhancement(
                processed, presence_pct, upper_mid_pct, effective_intensity * 0.7, sample_rate, verbose
            )
            if presence_info:
                info['stages'].append(presence_info)

            processed, air_info = self._apply_air_enhancement(
                processed, air_pct, spectral_rolloff, effective_intensity * 0.7, sample_rate, verbose
            )
            if air_info:
                info['stages'].append(air_info)

            # Safety peak limit after enhancements (only catches outliers now)
            processed = self._apply_safety_limiter(processed, verbose)

            # Mark for unified output normalization
            needs_output_normalize = True

        elif lufs > -12.0:
            # Dynamic loud → pass-through with optional stereo expansion
            if verbose:
                print(f"   Dynamic loud → preserving original")
            info['stages'].append({'stage': 'passthrough'})

            # Stereo expansion for narrow mixes (brightness-aware)
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose, bass_pct,
                spectral_centroid, air_pct, phase_correlation
            )
            if width_info:
                info['stages'].append(width_info)

            # Pre-EQ headroom: attenuate before spectral boosts to prevent limiter from
            # clipping HF transients. The output normalization will restore level.
            pre_eq_headroom_db = -2.0  # Reserve 2 dB for EQ boosts
            pre_eq_gain = 10 ** (pre_eq_headroom_db / 20)
            processed = processed * pre_eq_gain

            # Spectral enhancements (presence & air) - even for well-mastered tracks
            processed, presence_info = self._apply_presence_enhancement(
                processed, presence_pct, upper_mid_pct, effective_intensity * 0.5, sample_rate, verbose
            )
            if presence_info:
                info['stages'].append(presence_info)

            processed, air_info = self._apply_air_enhancement(
                processed, air_pct, spectral_rolloff, effective_intensity * 0.5, sample_rate, verbose
            )
            if air_info:
                info['stages'].append(air_info)

            # Safety peak limit after enhancements (only catches outliers now)
            processed = self._apply_safety_limiter(processed, verbose)

            # Mark for unified output normalization
            needs_output_normalize = True

        else:
            # Quiet material → full processing
            needs_output_normalize = False  # Quiet branch has its own normalization
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

            # Sub-bass control - tighten rumble or add sub-harmonics
            processed, sub_bass_info = self._apply_sub_bass_control(
                processed, sub_bass_pct, bass_pct, effective_intensity, sample_rate, verbose
            )
            if sub_bass_info:
                info['stages'].append(sub_bass_info)

            # Mid-range warmth for thin mixes (200-2kHz body)
            processed, warmth_info = self._apply_mid_warmth(
                processed, low_mid_pct, mid_pct, effective_intensity, sample_rate, verbose
            )
            if warmth_info:
                info['stages'].append(warmth_info)

            # Presence enhancement for dull mixes (2-6kHz boost)
            processed, presence_info = self._apply_presence_enhancement(
                processed, presence_pct, upper_mid_pct, effective_intensity, sample_rate, verbose
            )
            if presence_info:
                info['stages'].append(presence_info)

            # Air enhancement for dark mixes (6-20kHz sparkle)
            processed, air_info = self._apply_air_enhancement(
                processed, air_pct, spectral_rolloff, effective_intensity, sample_rate, verbose
            )
            if air_info:
                info['stages'].append(air_info)

            # Soft clipping with multi-dimensional awareness
            loudness_factor = max(0.0, min(1.0, (-11.0 - lufs) / 9.0))
            threshold_db = -2.0 + (1.5 * (1.0 - loudness_factor))
            ceiling = 0.92 + (0.07 * loudness_factor)

            # Harmonic preservation - gentler clipping for tonal/harmonic content
            # High harmonic_ratio + pitch_stability = vocals, classical, melodic content
            harmonic_preservation = (harmonic_ratio * 0.7 + pitch_stability * 0.3)
            if harmonic_preservation > 0.6:
                # Smooth curve: 0.6-1.0 increases gentleness
                curve_pos = (harmonic_preservation - 0.6) / 0.4
                harmonic_factor = 0.5 * (1.0 - np.cos(np.pi * curve_pos))
                threshold_db += 0.5 * harmonic_factor  # Raise threshold (less clipping)
                ceiling += 0.03 * harmonic_factor  # Higher ceiling
                if verbose:
                    print(f"   🎼 Harmonic preservation ({harmonic_preservation:.2f})")

            # Variation awareness - gentler on inconsistent material
            # High dynamic_range_variation or low peak_consistency = needs gentle touch
            variation_metric = dynamic_range_variation * 0.6 + (1.0 - peak_consistency) * 0.4
            if variation_metric > 0.5:
                # Smooth curve: 0.5-1.0 increases gentleness
                curve_pos = (variation_metric - 0.5) / 0.5
                variation_factor = 0.5 * (1.0 - np.cos(np.pi * curve_pos))
                threshold_db += 0.4 * variation_factor  # Gentler clipping for varied material
                if verbose:
                    print(f"   📊 Variation preservation ({variation_metric:.2f})")

            # Spectral flatness awareness - noisy/percussive vs tonal
            # High flatness (noisy) = less aggressive processing
            if spectral_flatness > 0.6:
                # Smooth curve: 0.6-1.0 reduces processing
                curve_pos = (spectral_flatness - 0.6) / 0.4
                flatness_factor = 0.5 * (1.0 - np.cos(np.pi * curve_pos))
                threshold_db += 0.3 * flatness_factor  # Gentler on noisy material
                if verbose:
                    print(f"   🔊 Noise-aware processing ({spectral_flatness:.2f})")

            # Gentle bass-aware adjustments using smooth curve
            # Previous exponential curve was too aggressive - crushing dynamics
            #
            # bass_x: normalized 0.0 at 20% bass → 1.0 at 70% bass
            bass_x = np.clip((bass_pct - 0.20) / 0.50, 0.0, 1.0)
            # Smooth S-curve using cosine for gradual onset
            bass_intensity = 0.5 * (1.0 - np.cos(np.pi * bass_x))

            # Gentler adjustments to preserve dynamics
            # At 60% bass: bass_intensity ≈ 0.65
            threshold_db -= 1.5 * bass_intensity  # Up to -1.5 dB headroom (was -3.0)
            ceiling -= 0.05 * bass_intensity  # Ceiling from 0.92 down to 0.87 (was 0.80)

            threshold_linear = 10 ** (threshold_db / 20.0)

            if verbose:
                print(f"   Soft clip: {threshold_db:.1f} dB, ceiling {ceiling*100:.0f}%")

            processed = soft_clip(processed, threshold=threshold_linear, ceiling=ceiling)
            info['stages'].append({'stage': 'soft_clip', 'threshold_db': threshold_db})

            # Stereo expansion for narrow mixes (brightness-aware)
            processed, width_info = self._apply_stereo_expansion(
                processed, stereo_width, effective_intensity, sample_rate, verbose, bass_pct,
                spectral_centroid, air_pct, phase_correlation
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

        # STAGE 3: Unified output normalization for loud material
        # Ensures consistent output levels across all branches
        if needs_output_normalize:
            # Light normalization for already-mastered material
            # Target slightly below 0 dBFS to leave headroom for playback
            output_target = 0.95

            current_peak = np.max(np.abs(processed))
            if current_peak < output_target * 0.9:  # Only normalize if significantly below target
                processed = normalize(processed, output_target)
                if verbose:
                    gain_db = 20 * np.log10(output_target / current_peak)
                    print(f"   Output normalize: +{gain_db:.1f} dB → {output_target*100:.0f}% peak")
                info['stages'].append({'stage': 'output_normalize', 'target_peak': output_target})

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

    def _apply_safety_limiter(
        self,
        audio: np.ndarray,
        verbose: bool,
        ceiling: float = 0.98
    ) -> np.ndarray:
        """
        Apply transparent safety limiting after spectral enhancements.

        Uses soft clipping for more musical limiting than simple scaling.
        Only affects peaks above the threshold - leaves the rest untouched.

        Args:
            audio: Audio array [2, samples]
            verbose: Print progress
            ceiling: Maximum output level (default 0.98 = -0.18 dBFS)

        Returns:
            Limited audio array
        """
        current_peak = np.max(np.abs(audio))

        if current_peak <= ceiling:
            return audio  # No limiting needed

        # Use soft clip with threshold slightly below ceiling for smooth knee
        threshold = ceiling * 0.95  # Start limiting ~0.4 dB before ceiling
        processed = soft_clip(audio, threshold=threshold, ceiling=ceiling)

        if verbose:
            reduction_db = 20 * np.log10(ceiling / current_peak)
            print(f"   Safety limiter: {reduction_db:.1f} dB reduction")

        return processed

    def _apply_stereo_expansion(
        self,
        audio: np.ndarray,
        current_width: float,
        intensity: float,
        sample_rate: int,
        verbose: bool,
        bass_pct: float = 0.3,
        spectral_centroid: float = 0.5,
        air_pct: float = 0.1,
        phase_correlation: float = 1.0
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply gentle adaptive stereo expansion with brightness preservation.

        CONSERVATIVE: Very narrow mixes (< 20%) are likely intentional production choices.
        Only apply subtle widening to avoid unnatural "thin" sound from excessive multiband expansion.

        Uses gentle frequency-dependent expansion:
        - Lows (<200Hz): No expansion - keeps kick/bass punchy
        - Low-mids (200-2kHz): Minimal expansion - preserves body
        - High-mids (2k-8kHz): Gentle expansion - subtle width
        - Highs (>8kHz): Reduced expansion - avoids thin/hollow sound

        NEW: Much more conservative to prevent "extremely expanded but thin" artifacts.

        Args:
            audio: Stereo audio [2, samples]
            current_width: Fingerprint stereo_width (0=mono, 1=wide)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress
            bass_pct: Bass content percentage (for multiband weighting)
            spectral_centroid: Brightness indicator 0-1 (higher = brighter)
            air_pct: High-frequency air content 0-1
            phase_correlation: Stereo phase correlation (-1 to +1)

        Returns:
            (processed_audio, stage_info or None if no expansion applied)
        """
        # Smooth curve-based approach: respect narrow mixes, gentle widening only
        # Use continuous curves throughout - no hard cutoffs

        # 1. Width-based curve: narrower mixes get LESS expansion (they're likely intentional)
        # Smooth transition from 0% width (mono) to 40% width (moderate stereo)
        if current_width >= 0.40:
            return audio, None  # Already has decent width

        # Safety: Smooth phase correlation curve (not a hard threshold)
        # Poor phase correlation reduces expansion smoothly
        if phase_correlation < 0.3:
            # Below 0.3 phase correlation, skip entirely
            if verbose:
                print(f"   ⚠️  Skipping stereo expansion (poor phase correlation: {phase_correlation:.2f})")
            return audio, None

        # Phase correlation factor: 0.3-0.7 fades in smoothly, 0.7+ = full
        if phase_correlation < 0.7:
            phase_factor = (phase_correlation - 0.3) / 0.4  # 0.0 at 0.3, 1.0 at 0.7
            phase_factor = 0.5 * (1.0 - np.cos(np.pi * phase_factor))  # S-curve
        else:
            phase_factor = 1.0

        # 2. Width expansion curve: bell curve with peak at 25% width
        # Very narrow (<15%) and moderate (>35%) get less expansion
        # Sweet spot at 20-30% width gets most expansion

        if current_width < 0.15:
            # Extremely narrow: smooth ramp up from 0% to 15%
            # 0% width = 0.0 factor, 15% width = 0.3 factor
            width_curve = current_width / 0.15  # 0.0 → 1.0
            width_curve = 0.5 * (1.0 - np.cos(np.pi * width_curve))  # Smooth S-curve
            narrowness_factor = 0.3 * width_curve  # Scale to max 0.3
        elif current_width < 0.30:
            # Sweet spot: 15-30% width, peak expansion potential
            # Bell curve peaks at 22.5%
            center = 0.225
            width_offset = current_width - center
            # Gaussian-like bell curve
            narrowness_factor = 0.6 * np.exp(-(width_offset**2) / (2 * 0.05**2))
        else:
            # Moderate width: 30-40%, smooth fade out
            fade_curve = (0.40 - current_width) / 0.10  # 1.0 at 30%, 0.0 at 40%
            fade_curve = np.clip(fade_curve, 0.0, 1.0)
            fade_curve = 0.5 * (1.0 + np.cos(np.pi * (1.0 - fade_curve)))  # Smooth fade
            narrowness_factor = 0.3 * fade_curve

        # 3. Brightness preservation curve - reduce expansion for bright tracks
        # High spectral centroid or air content = already bright, be gentle
        brightness_metric = max(spectral_centroid, air_pct * 2.0)  # 0-1

        # Smooth curve: 0.6-1.0 brightness reduces expansion smoothly
        if brightness_metric > 0.6:
            brightness_curve = (brightness_metric - 0.6) / 0.4  # 0.0 at 0.6, 1.0 at 1.0
            brightness_curve = 0.5 * (1.0 - np.cos(np.pi * brightness_curve))  # S-curve
            brightness_factor = 1.0 - (0.5 * brightness_curve)  # 1.0 → 0.5 smoothly
            if verbose:
                print(f"   💡 Brightness preservation ({brightness_metric:.2f}, factor: {brightness_factor:.2f})")
        else:
            brightness_factor = 1.0

        # Combine all smooth curves multiplicatively
        combined_factor = narrowness_factor * phase_factor * brightness_factor

        # Conservative base expansion - much gentler than before
        max_expansion = 0.08 * intensity
        expansion_amount = max_expansion * combined_factor

        if expansion_amount < 0.01:
            return audio, None  # Too small to matter

        width_factor = 0.5 + expansion_amount

        # Transpose for multiband function which expects [samples, 2]
        audio_t = audio.T
        expanded = adjust_stereo_width_multiband(
            audio_t, width_factor, sample_rate,
            original_width=current_width,
            bass_content=bass_pct
        )
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
        # Using PARALLEL processing to avoid phase cancellation at crossover
        shelf_freq = 100.0
        nyquist = sample_rate / 2
        normalized_freq = min(0.99, max(0.01, shelf_freq / nyquist))

        # Extract low frequencies only (don't split - keep original intact)
        sos_lp = butter(2, normalized_freq, btype='low', output='sos')
        low_band = sosfilt(sos_lp, audio, axis=1)

        # Add boosted low frequencies ON TOP of original (parallel processing)
        # This avoids phase cancellation from HP+LP recombination
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0  # How much extra gain to add
        processed = audio + low_band * boost_diff

        if verbose:
            print(f"   Bass enhance: +{boost_db:.1f} dB below 100Hz")

        return processed, {
            'stage': 'bass_enhance',
            'boost_db': boost_db,
            'bass_pct': bass_pct
        }

    def _apply_sub_bass_control(
        self,
        audio: np.ndarray,
        sub_bass_pct: float,
        bass_pct: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive sub-bass control (20-60Hz).

        High sub-bass → tighten (reduce rumble)
        Low sub-bass + decent bass → already good, skip
        Low sub-bass + low bass → enhance together via bass_enhancement

        Uses smooth curves throughout.
        """
        # Smooth curve: only act if sub-bass is excessive (> 8%)
        if sub_bass_pct < 0.08:
            return audio, None  # Sub-bass is fine or already handled by bass enhancement

        # Smooth cosine curve for rumble reduction
        # 8-15% sub-bass: gradual increase in reduction
        curve_position = np.clip((sub_bass_pct - 0.08) / 0.07, 0.0, 1.0)  # 0.0 at 8%, 1.0 at 15%
        rumble_factor = 0.5 * (1.0 - np.cos(np.pi * curve_position))

        # Calculate reduction amount (gentle)
        max_reduction_db = -2.0 * intensity  # Max -2dB reduction
        reduction_db = max_reduction_db * rumble_factor

        if abs(reduction_db) < 0.3:
            return audio, None

        # Apply gentle high-pass at 30Hz to reduce rumble
        cutoff_freq = 30.0
        nyquist = sample_rate / 2
        normalized_freq = min(0.99, max(0.01, cutoff_freq / nyquist))

        # Very gentle slope (1st order)
        sos = butter(1, normalized_freq, btype='high', output='sos')
        processed = sosfilt(sos, audio, axis=1)

        # Blend with original based on reduction amount
        blend_factor = abs(reduction_db) / 2.0  # 0.0-1.0
        processed = processed * blend_factor + audio * (1.0 - blend_factor)

        if verbose:
            print(f"   Sub-bass tighten: {reduction_db:.1f} dB @ <30Hz")

        return processed, {
            'stage': 'sub_bass_control',
            'reduction_db': reduction_db,
            'sub_bass_pct': sub_bass_pct
        }

    def _apply_mid_warmth(
        self,
        audio: np.ndarray,
        low_mid_pct: float,
        mid_pct: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive mid-range warmth (200-2kHz body).

        Low mids → add warmth and body
        Good mids → skip

        Uses smooth curves throughout.
        """
        # Combine low-mid and mid for overall body content
        body_content = (low_mid_pct + mid_pct) / 2.0

        # Smooth cosine curve: boost from 0% to 25% body content
        if body_content >= 0.25:
            return audio, None  # Already has good body

        # Smooth S-curve
        curve_position = body_content / 0.25  # 0.0 at 0%, 1.0 at 25%
        body_factor = 0.5 * (1.0 + np.cos(np.pi * curve_position))  # 1.0 → 0.0

        # Calculate boost
        max_boost_db = 1.5 * intensity  # Gentler than presence
        boost_db = max_boost_db * body_factor

        if boost_db < 0.3:
            return audio, None

        # Apply gentle boost at 200-2kHz (body zone)
        # Using PARALLEL processing to avoid phase cancellation at crossover
        nyquist = sample_rate / 2

        # Extract mid band only (don't split - keep original intact)
        low_cutoff = 200.0 / nyquist
        high_cutoff = min(2000.0 / nyquist, 0.99)
        sos_bp = butter(2, [low_cutoff, high_cutoff], btype='band', output='sos')
        mid_band = sosfilt(sos_bp, audio, axis=1)

        # Add boosted mid frequencies ON TOP of original (parallel processing)
        # This avoids phase cancellation from BP+BS recombination
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0
        processed = audio + mid_band * boost_diff

        if verbose:
            print(f"   Mid warmth: +{boost_db:.1f} dB @ 200-2kHz")

        return processed, {
            'stage': 'mid_warmth',
            'boost_db': boost_db,
            'body_content': body_content
        }

    def _apply_presence_enhancement(
        self,
        audio: np.ndarray,
        presence_pct: float,
        upper_mid_pct: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive presence enhancement for dull mixes (2-6kHz boost).

        Boosts presence frequencies to add clarity, definition, and forward character.
        Targets the frequency range where consonants, attack transients, and definition live.

        Uses smooth curves throughout - no hard thresholds.

        Args:
            audio: Stereo audio [2, samples]
            presence_pct: Fingerprint presence percentage (4-6kHz, 0-1)
            upper_mid_pct: Fingerprint upper-mid percentage (2-4kHz, 0-1)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress

        Returns:
            (processed_audio, stage_info or None if no enhancement applied)
        """
        # Combine presence and upper-mid to get overall 2-6kHz content
        presence_content = (presence_pct + upper_mid_pct) / 2.0

        # Smooth cosine curve: boost from 0% to 30% presence, fade out smoothly
        # No boost at 30%+, full potential boost at 0%, smooth transition between
        if presence_content >= 0.30:
            return audio, None  # Already has good presence

        # Smooth S-curve using cosine for natural transition
        # Maps 0.0-0.30 to 1.0-0.0 smoothly
        curve_position = presence_content / 0.30  # 0.0 at 0%, 1.0 at 30%
        presence_factor = 0.5 * (1.0 + np.cos(np.pi * curve_position))  # 1.0 → 0.0

        # Calculate boost based on smooth presence deficiency curve
        max_boost_db = 2.0 * intensity
        boost_db = max_boost_db * presence_factor

        if boost_db < 0.3:
            return audio, None  # Too small to matter

        # Boost presence band (2-8kHz) centered around 4kHz
        # Using PARALLEL processing to avoid phase cancellation at crossover
        nyquist = sample_rate / 2

        # Extract presence band only (don't split - keep original intact)
        low_cutoff = 2000.0 / nyquist
        high_cutoff = min(8000.0 / nyquist, 0.99)
        sos_bp = butter(2, [low_cutoff, high_cutoff], btype='band', output='sos')
        presence_band = sosfilt(sos_bp, audio, axis=1)

        # Add boosted presence ON TOP of original (parallel processing)
        # This avoids phase cancellation from BP+BS recombination
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0
        processed = audio + presence_band * boost_diff

        if verbose:
            print(f"   Presence enhance: +{boost_db:.1f} dB @ 2-6kHz")

        return processed, {
            'stage': 'presence_enhance',
            'boost_db': boost_db,
            'presence_content': presence_content
        }

    def _apply_air_enhancement(
        self,
        audio: np.ndarray,
        air_pct: float,
        spectral_rolloff: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Apply adaptive air enhancement for dark mixes (6-20kHz sparkle).

        Boosts high frequencies to add air, sparkle, and openness.
        Uses spectral_rolloff to detect if high frequencies naturally roll off.

        Uses smooth curves throughout - no hard thresholds.

        Args:
            audio: Stereo audio [2, samples]
            air_pct: Fingerprint air percentage (6-20kHz, 0-1)
            spectral_rolloff: Frequency where most energy is below (0-1, normalized)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress

        Returns:
            (processed_audio, stage_info or None if no enhancement applied)
        """
        # Low air_pct or low spectral_rolloff = dark mix needing air
        darkness_factor = (1.0 - air_pct) * 0.6 + (1.0 - spectral_rolloff) * 0.4

        # Smooth S-curve: boost increases as darkness increases
        # darkness 0.0-0.4: minimal/no boost (bright tracks)
        # darkness 0.4-1.0: smooth ramp to full boost (dark tracks)
        if darkness_factor < 0.4:
            return audio, None  # Already bright

        # Smooth cosine curve from 0.4 (no boost) to 1.0 (full boost)
        curve_position = (darkness_factor - 0.4) / 0.6  # 0.0 at 0.4, 1.0 at 1.0
        air_factor = 0.5 * (1.0 - np.cos(np.pi * curve_position))  # 0.0 → 1.0 smoothly

        # Calculate boost based on smooth darkness curve
        max_boost_db = 1.5 * intensity
        boost_db = max_boost_db * air_factor

        if boost_db < 0.3:
            return audio, None  # Too small to matter

        # Design a high-shelf filter at 8kHz
        # Using PARALLEL processing to avoid phase cancellation at crossover
        shelf_freq = 8000.0
        nyquist = sample_rate / 2
        normalized_freq = min(0.99, max(0.01, shelf_freq / nyquist))

        # Extract high frequencies only (don't split - keep original intact)
        sos_hp = butter(2, normalized_freq, btype='high', output='sos')
        high_band = sosfilt(sos_hp, audio, axis=1)

        # Add boosted highs ON TOP of original (parallel processing)
        # This avoids phase cancellation from HP+LP recombination
        boost_linear = 10 ** (boost_db / 20)
        boost_diff = boost_linear - 1.0
        processed = audio + high_band * boost_diff

        if verbose:
            print(f"   Air enhance: +{boost_db:.1f} dB above 8kHz")

        return processed, {
            'stage': 'air_enhance',
            'boost_db': boost_db,
            'darkness_factor': darkness_factor
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
