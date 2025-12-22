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
import numpy as np
from typing import Dict, Tuple, Optional
from pathlib import Path

import librosa
import soundfile as sf

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from ..dsp.basic import amplify, normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..dsp.utils.adaptive_loudness import AdaptiveLoudnessControl


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
        processed, info = self._process(audio, fingerprint, peak_db, intensity, verbose)
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
        verbose: bool
    ) -> Tuple[np.ndarray, Dict]:
        """Core processing logic."""

        lufs = fp.get('lufs', -14.0)
        crest_db = fp.get('crest_db', 12.0)
        bass_pct = fp.get('bass_pct', 0.15)
        transient_density = fp.get('transient_density', 0.5)

        info = {'stages': []}
        processed = audio.copy()

        # Adaptive intensity based on dynamics + loudness
        effective_intensity = self._calculate_intensity(intensity, lufs, crest_db)

        # STAGE 1: Peak reduction for quiet-but-hot material
        if lufs < -14.0 and peak_db > -3.0:
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

        elif lufs > -12.0:
            # Dynamic loud → pass-through
            if verbose:
                print(f"   Dynamic loud → preserving original")
            info['stages'].append({'stage': 'passthrough'})

        else:
            # Quiet material → full processing
            makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
                lufs, effective_intensity, crest_db, bass_pct, transient_density, peak_db
            )

            # Apply makeup gain with 1 dB safety margin for headroom
            makeup_gain = max(0.0, makeup_gain - 2.0)
            if makeup_gain > 0.0:
                if verbose:
                    print(f"   Makeup gain: +{makeup_gain:.1f} dB")
                processed = amplify(processed, makeup_gain)
                info['stages'].append({'stage': 'makeup_gain', 'gain_db': makeup_gain})

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

            # Final normalization
            target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(lufs)
            adapted_peak = max(0.80, min(0.95, target_peak - (0.05 * loudness_factor)))

            if bass_pct > 0.15:
                adapted_peak -= 0.02 * min(1.0, (bass_pct - 0.15) / 0.25)

            if verbose:
                print(f"   Normalize: {adapted_peak*100:.0f}% peak")

            processed = normalize(processed, adapted_peak)
            info['stages'].append({'stage': 'normalize', 'target_peak': adapted_peak})

        info['effective_intensity'] = effective_intensity
        return processed, info

    def _calculate_intensity(self, base: float, lufs: float, crest_db: float) -> float:
        """Calculate effective intensity from base + audio characteristics."""
        if crest_db > 15:
            if lufs < -13.0:
                return base * 1.2  # Quiet + dynamic → boost
            elif lufs > -11.0:
                return base * 0.6  # Loud + dynamic → preserve
            return base * 0.85
        elif crest_db < 8:
            return base * 0.5  # Already compressed
        return base

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
