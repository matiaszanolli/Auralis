"""
Simple Mastering Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

Minimal-dependency mastering facade for CLI tools like auto_master.py.
Uses existing DSP components without requiring full HybridProcessor setup.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from . import mastering_chunk_loop, mastering_diagnostics, mastering_prepare
from .dsp import Notch
from .mastering_config import SimpleMasteringConfig
from .mastering_process_chunk import process_chunk
from .stages import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    loudness_maximizer,
    mid_warmth,
    presence_enhancement,
    resonance_notches as resonance_notches_stage,
    safety_limiter,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)


class SimpleMasteringPipeline:
    """
    Lightweight mastering pipeline for CLI/batch processing.

    Uses fingerprint-driven adaptive parameters without full HybridProcessor.
    """

    def __init__(self, config: SimpleMasteringConfig | None = None):
        self._fingerprint_service: FingerprintService | None = None
        self.config = config or SimpleMasteringConfig()
        self._fp_service_lock = threading.Lock()  # Protects lazy init (fixes #2434)
        # Per-file resonance notches. Populated by master_file before chunked
        # processing, consumed by _apply_resonance_notches. Cleared at the start
        # of each master_file call so notches don't leak between files in batch.
        self._notches: list[Notch] = []
        # #3715: serialise concurrent master_file()/process() calls on the
        # SAME instance so the per-file `_notches` write-then-read pattern
        # cannot cross-contaminate between tracks (thread A's notches
        # overwritten by thread B before A's chunk loop reads them, or
        # vice versa). RLock so internal methods can re-acquire if a
        # future refactor calls them recursively; cross-instance
        # parallelism is unaffected.
        self._process_lock = threading.RLock()
        # Per-file accurate ITU-R BS.1770 loudness, measured once in
        # master_file (mastering_prepare.prepare_file) and consumed by the
        # QuietBranch loudness maximizer — the fingerprint's `lufs` is a
        # non-K-weighted RMS proxy that under-reads high-DR material by
        # 3-5 dB. None on the direct _process() test path, where the
        # branch falls back to the fingerprint value.
        self._source_lufs: float | None = None
        self._source_crest_db: float | None = None
        # Per-file whole-song peak (dB), measured once in master_file, used
        # ONLY as the headroom reference for the QuietBranch makeup-gain
        # clamp — NOT for Stage 1's per-chunk clip prevention, which
        # correctly keeps using each chunk's own peak. None on the direct
        # _process() test path, where the per-chunk peak is the fallback.
        self._song_peak_db: float | None = None

    @property
    def fingerprint_service(self) -> FingerprintService:
        """Lazy-init fingerprint service (thread-safe, fixes #2434)."""
        with self._fp_service_lock:
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
    ) -> dict:
        """
        Master an audio file with adaptive processing using chunked processing.
        Memory-efficient: processes audio in chunks instead of loading entire file.

        Args:
            input_path: Input audio file
            output_path: Output WAV file
            intensity: Processing intensity 0.0-1.0
            verbose: Print progress
            time_metrics: Print detailed timing for each step (development only)

        Returns:
            Dict with processing info
        """
        # #3715: hold `_process_lock` across the entire master_file
        # invocation. The per-file `_notches` instance attribute is
        # written by mastering_prepare.prepare_file and read by
        # `_apply_resonance_notches` for every chunk; without
        # serialisation, two concurrent master_file calls on the same
        # instance would cross-contaminate notches between tracks.
        with self._process_lock:
            return self._master_file_impl(
                input_path, output_path, intensity, verbose, time_metrics
            )

    def _master_file_impl(
        self,
        input_path: str,
        output_path: str,
        intensity: float = 1.0,
        verbose: bool = True,
        time_metrics: bool = False,
    ) -> dict:
        """Inner implementation called under `_process_lock` (#3715)."""
        total_start = time.perf_counter()

        import tempfile as _tempfile

        orig_path = Path(input_path)
        if not orig_path.exists():
            raise FileNotFoundError(f"Input not found: {orig_path}")

        # Pre-convert FFmpeg-only formats (mp3, m4a, aac …) to a temporary
        # WAV so sf.SoundFile calls work without modification throughout.
        # We keep orig_path for fingerprint cache lookups (the cache key is
        # the original file path, not the transient temp WAV).
        from ..io.formats import FFMPEG_FORMATS
        _tmp_dir: _tempfile.TemporaryDirectory | None = None
        if orig_path.suffix.lower() in FFMPEG_FORMATS:
            from ..io.loaders import load_with_ffmpeg
            _tmp_dir = _tempfile.TemporaryDirectory()
            _tmp_wav = Path(_tmp_dir.name) / (orig_path.stem + "_dec.wav")
            _raw, _raw_sr = load_with_ffmpeg(orig_path, _tmp_dir.name)
            sf.write(str(_tmp_wav), _raw, _raw_sr, subtype="PCM_24")
            resolved_input_path = _tmp_wav
        else:
            resolved_input_path = orig_path
        try:
            prep = mastering_prepare.prepare_file(
                self, orig_path, resolved_input_path, output_path, verbose
            )
            fingerprint = prep['fingerprint']
            sr = prep['sr']
            total_frames = prep['total_frames']
            channels = prep['channels']
            duration = prep['duration']
            timings: dict[str, float] = prep['timings']

            # Step 3: Process in chunks (memory efficient)
            if verbose:
                print("\n⚡ Processing (chunked)...")

            step_start = time.perf_counter()
            info, chunks_processed = mastering_chunk_loop.process_chunks(
                self, resolved_input_path, output_path, sr, total_frames,
                channels, fingerprint, intensity, self.config, verbose,
            )
            timings['processing'] = time.perf_counter() - step_start
            timings['total'] = time.perf_counter() - total_start

            if verbose:
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                print(f"   ✅ Exported: {size_mb:.1f} MB")
                print(f"   📦 Processed {chunks_processed} chunks")
                print(f"\n🎉 Complete! Output: {output_path}")

            if time_metrics:
                mastering_diagnostics.print_time_metrics(timings, duration)

            result = {
                'input': str(orig_path),
                'output': output_path,
                'fingerprint': fingerprint,
                'processing': info,
                'chunks_processed': chunks_processed
            }

            if time_metrics:
                result['timings'] = timings

            return result
        finally:
            if _tmp_dir is not None:
                _tmp_dir.cleanup()

    def _process(
        self,
        audio: np.ndarray,
        fp: dict,
        peak_db: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Core processing logic using all 25D fingerprint dimensions.

        Thin delegate to mastering_process_chunk.process_chunk (#4072).
        Kept as a method (not inlined) because tests/auralis/core/
        test_nan_detection.py calls pipeline._process(...) directly.
        """
        return process_chunk(self, audio, fp, peak_db, intensity, sample_rate, verbose)

    def _apply_safety_limiter(
        self, audio: np.ndarray, verbose: bool, ceiling: float = 0.98
    ) -> np.ndarray:
        return safety_limiter.apply(audio, verbose, ceiling=ceiling)

    def _apply_loudness_maximizer(
        self, audio: np.ndarray, source_lufs: float, source_crest_db: float,
        sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict | None]:
        return loudness_maximizer.apply(
            audio, source_lufs, source_crest_db, sample_rate, verbose, self.config
        )

    def _apply_resonance_notches(
        self, audio: np.ndarray, sample_rate: int, verbose: bool
    ) -> tuple[np.ndarray, dict | None]:
        return resonance_notches_stage.apply(audio, sample_rate, self._notches, verbose)

    def _apply_transient_shaper(
        self, audio: np.ndarray, bass_pct: float, low_mid_pct: float,
        crest_db: float, intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict | None]:
        return transient_shaper.apply(audio, bass_pct, low_mid_pct, crest_db, intensity, sample_rate, verbose, self.config)

    def _apply_clarity_boost(
        self, audio: np.ndarray, upper_mid_pct: float, intensity: float,
        sample_rate: int, verbose: bool, hf_lift: float = 1.0,
        bass_pct: float = 0.0, mid_pct: float = 0.0,
    ) -> tuple[np.ndarray, dict | None]:
        return clarity_boost.apply(audio, upper_mid_pct, intensity, sample_rate, verbose, self.config, hf_lift, bass_pct, mid_pct)

    def _apply_stereo_expansion(
        self, audio: np.ndarray, current_width: float, intensity: float,
        sample_rate: int, verbose: bool, bass_pct: float = 0.3,
        spectral_centroid: float = 0.5, air_pct: float = 0.1,
        phase_correlation: float = 1.0,
    ) -> tuple[np.ndarray, dict | None]:
        return stereo_expansion.apply(audio, current_width, intensity, sample_rate, verbose,
                                       bass_pct=bass_pct, spectral_centroid=spectral_centroid,
                                       air_pct=air_pct, phase_correlation=phase_correlation)

    def _apply_bass_enhancement(
        self, audio: np.ndarray, bass_pct: float, intensity: float,
        sample_rate: int, verbose: bool,
        mid_pct: float = 0.0, upper_mid_pct: float = 0.0,
    ) -> tuple[np.ndarray, dict | None]:
        return bass_enhancement.apply(audio, bass_pct, intensity, sample_rate, verbose, self.config, mid_pct, upper_mid_pct)

    def _apply_sub_bass_control(
        self, audio: np.ndarray, sub_bass_pct: float, bass_pct: float,
        intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict | None]:
        return sub_bass_control.apply(audio, sub_bass_pct, bass_pct, intensity, sample_rate, verbose, self.config)

    def _apply_mid_warmth(
        self, audio: np.ndarray, low_mid_pct: float, mid_pct: float,
        intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict | None]:
        return mid_warmth.apply(audio, low_mid_pct, mid_pct, intensity, sample_rate, verbose, self.config)

    def _apply_presence_enhancement(
        self, audio: np.ndarray, presence_pct: float, upper_mid_pct: float,
        intensity: float, sample_rate: int, verbose: bool, hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict | None]:
        return presence_enhancement.apply(audio, presence_pct, upper_mid_pct, intensity, sample_rate, verbose, self.config, hf_lift)

    def _apply_harmonic_exciter(
        self, audio: np.ndarray, presence_pct: float, air_pct: float,
        spectral_rolloff: float, intensity: float, sample_rate: int, verbose: bool,
        hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict | None]:
        return harmonic_exciter.apply(audio, presence_pct, air_pct, spectral_rolloff, intensity, sample_rate, verbose, self.config, hf_lift)

    def _apply_air_enhancement(
        self, audio: np.ndarray, air_pct: float, spectral_rolloff: float,
        intensity: float, sample_rate: int, verbose: bool, hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict | None]:
        return air_enhancement.apply(audio, air_pct, spectral_rolloff, intensity, sample_rate, verbose, self.config, hf_lift)

# Factory function
def create_simple_mastering_pipeline() -> SimpleMasteringPipeline:
    """Create a simple mastering pipeline instance."""
    return SimpleMasteringPipeline()
