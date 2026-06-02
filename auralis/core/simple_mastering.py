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
from scipy.signal import butter, sosfilt

from ..analysis.fingerprint.fingerprint_service import FingerprintService
from ..dsp.basic import normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..utils.audio_validation import sanitize_audio, validate_audio_finite
from .dsp import Notch, ResonanceNotcher
from .mastering_branches import MaterialClassifier
from .mastering_config import SimpleMasteringConfig
from .stages import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    mid_warmth,
    presence_enhancement,
    resonance_notches as resonance_notches_stage,
    safety_limiter,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)
from .utils import FingerprintUnpacker, SmoothCurveUtilities


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
        # cannot cross-contaminate between tracks. Two concurrent
        # invocations would otherwise race: thread A writes its notches,
        # thread B overwrites them, then both chunk loops apply B's
        # notches to A's audio (and vice versa). RLock so internal
        # methods can re-acquire if a future refactor calls them
        # recursively. Cross-instance parallelism is unaffected — only
        # the same-instance reuse pattern is serialised.
        self._process_lock = threading.RLock()

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
        # #3715: hold `_process_lock` across the entire master_file
        # invocation. The per-file `_notches` instance attribute is
        # written at line ~134 and read by `_apply_resonance_notches`
        # for every chunk; without serialisation, two concurrent
        # master_file calls on the same instance overwrite each
        # other's notches and cross-contaminate the chunk processing
        # for both tracks.
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
        timings: dict[str, float] = {}
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
            input_path = _tmp_wav
        else:
            input_path = orig_path

        # Step 1: Get fingerprint (uses orig_path so cache hits still work)
        if verbose:
            print(f"📂 Input: {orig_path.name}")
            print(f"📂 Output: {Path(output_path).name}")
            print("\n🔍 Fingerprinting...")

        step_start = time.perf_counter()
        fingerprint = self.fingerprint_service.get_or_compute(orig_path)
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

        # Step 2b: Detect resonances once per file.
        # Run on a representative 30s window from the middle of the file —
        # avoids loading the full file but gives enough data for the FFT
        # averaging to find stable spectral peaks. The same notch list is
        # applied to every chunk during processing.
        self._notches = []
        step_start = time.perf_counter()
        notch_sample_seconds = 30
        notch_window = min(total_frames, sr * notch_sample_seconds)
        notch_start = max(0, (total_frames - notch_window) // 2)
        with sf.SoundFile(str(input_path)) as audio_file:
            audio_file.seek(notch_start)
            notch_sample = audio_file.read(notch_window).astype(np.float32)
        # SoundFile returns (samples, channels); ResonanceNotcher handles both
        # mono and stereo input internally.
        detected = ResonanceNotcher.detect(
            notch_sample,
            sample_rate=sr,
            min_freq=self.config.NOTCH_MIN_FREQ_HZ,
            max_freq=self.config.NOTCH_MAX_FREQ_HZ,
            min_prominence_db=self.config.NOTCH_MIN_PROMINENCE_DB,
            max_notches=self.config.NOTCH_MAX_COUNT,
            max_depth_db=self.config.NOTCH_MAX_DEPTH_DB,
        )

        # Band-context awareness: scale each notch's depth by the energy
        # share of the band it lands in. If the target band is already
        # under-represented (e.g. Mid at 10% vs 24% target), full-depth
        # notching gouges an already-deficient band — so we shrink the cut
        # proportionally. Notch on a well-energized band → full depth;
        # notch on a deficient band → reduced depth (or skipped entirely
        # below NOTCH_MIN_BAND_HEALTH).
        self._notches = self._contextualize_notches(detected, fingerprint)
        timings['detect_notches'] = time.perf_counter() - step_start
        if verbose:
            if self._notches:
                print(f"\n🎯 Resonance notches detected ({len(self._notches)}):")
                for n in self._notches:
                    print(f"   {n.freq_hz:6.0f} Hz   {n.depth_db:+5.1f} dB (Q={n.q:.1f})")
            elif detected:
                # Resonances exist but all skipped by band-context filter
                print(f"\n🎯 Resonances detected but skipped — target bands too deficient")
                print(f"   ({len(detected)} candidates: " +
                      ", ".join(f"{n.freq_hz:.0f}Hz" for n in detected) + ")")
            else:
                print("\n🎯 No prominent resonances detected — skipping notch stage")

        # Step 3: Process in chunks (memory efficient)
        if verbose:
            print("\n⚡ Processing (chunked)...")

        step_start = time.perf_counter()

        # Equal-power crossfade between chunks for seamless transitions.
        # Adjacent chunks both process the overlap region, then we blend
        # with cosine curves to maintain perceived loudness through the join.
        crossfade_samples = int(sr * self.config.CROSSFADE_DURATION_SEC)

        # Process and write in streaming mode
        chunk_size = sr * self.config.CHUNK_DURATION_SEC
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

                prev_tail = None  # Previous chunk's processed overlap tail
                read_pos = 0

                while read_pos < total_frames:
                    core_samples = min(chunk_size, total_frames - read_pos)
                    is_last = (read_pos + core_samples >= total_frames)

                    # Read core + overlap so both chunks process the boundary
                    audio_file.seek(read_pos)
                    if is_last:
                        chunk = audio_file.read(core_samples)
                    else:
                        overlap_after = min(
                            crossfade_samples,
                            total_frames - read_pos - core_samples
                        )
                        chunk = audio_file.read(core_samples + overlap_after)

                    if chunk.size == 0:
                        break

                    # Ensure float32
                    chunk = chunk.astype(np.float32)

                    # Ensure stereo (channels, samples) format
                    if chunk.ndim == 1:
                        chunk = np.stack([chunk, chunk]).T

                    # Convert to (channels, samples) for processing.
                    # soundfile always yields (samples, channels), as does the
                    # mono→stereo path above, so we always need to transpose here.
                    # The old heuristic `shape[0] > shape[1]` silently failed for
                    # square arrays like (2, 2) — 2-sample stereo — because 2 > 2
                    # is False (issue #2292).
                    chunk = chunk.T

                    # Compute peak_db per chunk so the peak-reduction gate correctly
                    # engages on loud sections even when the track starts quietly (fixes
                    # #2402: stale first-chunk peak caused missed limiting on loud choruses).
                    peak_db = self._peak_db(chunk)

                    # Process chunk (includes overlap tail for crossfading)
                    processed_chunk, chunk_info = self._process(
                        chunk, fingerprint, peak_db, intensity, sr, verbose=False
                    )

                    # #3700: sample-count invariant — crossfade slice arithmetic
                    # below assumes _process() preserves the time axis. A future
                    # DSP regression (resampling, time-stretch, IIR padding bug)
                    # would otherwise silently corrupt the chunk boundary.
                    assert processed_chunk.shape[1] == chunk.shape[1], (
                        f"DSP sample-count violation: input {chunk.shape[1]} "
                        f"-> output {processed_chunk.shape[1]}"
                    )

                    # Update info from first chunk
                    if chunks_processed == 0:
                        info = chunk_info

                    # Assemble output with crossfading at chunk boundaries.
                    # new_tail stages the next prev_tail value and is only committed
                    # to prev_tail after output_file.write() succeeds (#2429).
                    new_tail = None

                    if chunks_processed == 0:
                        # First chunk: write core, save overlap tail
                        if is_last:
                            write_region = processed_chunk
                        else:
                            write_region = processed_chunk[:, :core_samples]
                            new_tail = processed_chunk[:, core_samples:].copy()
                    elif prev_tail is not None:
                        # Crossfade head of this chunk with previous tail
                        head_len = min(prev_tail.shape[1], processed_chunk.shape[1])

                        if head_len == 0:
                            # Empty overlap tail — skip crossfade, concatenate directly
                            # (fixes #2157: np.linspace(..., 0) produces empty array
                            # and silently drops samples at the chunk boundary)
                            if is_last:
                                write_region = processed_chunk
                            else:
                                write_region = processed_chunk[:, :core_samples]
                                new_tail = processed_chunk[:, core_samples:].copy()
                        else:
                            head = processed_chunk[:, :head_len]

                            # Equal-power crossfade (cosine curves maintain loudness).
                            # #3684: compute the fade ramps in the chunk's
                            # dtype so the multiply with prev_tail/head does
                            # not promote crossfaded → float64.
                            chunk_dtype = processed_chunk.dtype
                            t = np.linspace(0.0, np.pi / 2, head_len, dtype=chunk_dtype)
                            fade_in = np.sin(t) ** 2
                            fade_out = np.cos(t) ** 2
                            crossfaded = prev_tail[:, :head_len] * fade_out + head * fade_in

                            if is_last:
                                body = processed_chunk[:, head_len:]
                                write_region = np.concatenate([crossfaded, body], axis=1)
                            else:
                                body = processed_chunk[:, head_len:core_samples]
                                write_region = np.concatenate([crossfaded, body], axis=1)
                                # Guard against silent sample drift at chunk boundaries (#2515)
                                assert write_region.shape[1] == core_samples, (
                                    f"Crossfade write_region mismatch: expected {core_samples} "
                                    f"samples, got {write_region.shape[1]}"
                                )
                                new_tail = processed_chunk[:, core_samples:].copy()
                    else:
                        # No previous tail (safety fallback)
                        if is_last:
                            write_region = processed_chunk
                        else:
                            write_region = processed_chunk[:, :core_samples]
                            new_tail = processed_chunk[:, core_samples:].copy()

                    # Convert back to (samples, channels) for writing.
                    # write_region is always (channels, samples) after processing,
                    # so unconditional transpose is correct here too (issue #2292).
                    write_region = write_region.T

                    # #3660: explicit clamp to [-1.0, 1.0] before PCM_24 encode —
                    # mirrors the saver.py fix from #3471. Crossfade
                    # constructive interference at chunk boundaries can push
                    # samples slightly out of range; libsndfile's implicit
                    # clipping behaviour varies across builds.
                    write_region = np.clip(write_region, -1.0, 1.0)

                    output_file.write(write_region)
                    # Commit new tail only after write succeeds: if concatenate or
                    # write raises, prev_tail retains the last-good value (#2429).
                    prev_tail = new_tail

                    chunks_processed += 1
                    read_pos += core_samples

                    if verbose and chunks_processed % self.config.PROGRESS_REPORT_INTERVAL_CHUNKS == 0:
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

        if _tmp_dir is not None:
            _tmp_dir.cleanup()

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

    def _process(
        self,
        audio: np.ndarray,
        fp: dict,
        peak_db: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Core processing logic using all 25D fingerprint dimensions."""

        # Unpack fingerprint using type-safe unpacker
        unpacker = FingerprintUnpacker.from_dict(fp)

        info = {'stages': []}
        processed = audio.copy()

        # Validate input audio for NaN/Inf (fail fast on corrupted input)
        processed = validate_audio_finite(processed, context="simple mastering input", repair=False)

        # Adaptive intensity based on dynamics + loudness
        effective_intensity = self._calculate_intensity(intensity, unpacker.lufs, unpacker.crest_db)

        # STAGE 1: Gentle peak reduction for clipping prevention only
        # Only intervene when peak is dangerously close to or above 0 dBFS
        # Uses smooth S-curve to avoid filtering effect - just prevents actual clipping
        if peak_db > self.config.PEAK_REDUCTION_THRESHOLD_DB:
            # Smooth curve: gentle near threshold, stronger for severe clipping
            # clip_severity: 0 at threshold, 1 at threshold + range
            smooth_factor = SmoothCurveUtilities.ramp_to_s_curve(
                peak_db,
                self.config.PEAK_REDUCTION_THRESHOLD_DB,
                self.config.PEAK_REDUCTION_THRESHOLD_DB + self.config.PEAK_CLIP_SEVERITY_RANGE_DB
            )

            # Target: threshold to max_target based on severity
            peak_range = abs(self.config.MAX_TARGET_PEAK_REDUCTION_DB - self.config.PEAK_REDUCTION_THRESHOLD_DB)
            target_peak = self.config.PEAK_REDUCTION_THRESHOLD_DB - smooth_factor * peak_range

            if verbose:
                print(f"   Peak reduction: {peak_db:.1f} → {target_peak:.1f} dB")

            processed, peak_db = self._reduce_peaks(processed, peak_db, target_peak)
            info['stages'].append({'stage': 'peak_reduction', 'target': target_peak, 'result': peak_db})

        # STAGE 2: Classify material and dispatch to appropriate processing branch
        material_type = MaterialClassifier.classify(unpacker.lufs, unpacker.crest_db, self.config)
        branch = MaterialClassifier.get_branch(material_type, self)

        if verbose:
            print(f"   Material type: {material_type}")

        # Delegate to branch-specific processing
        processed, branch_info = branch.apply(
            processed, unpacker, peak_db, effective_intensity, sample_rate, self.config, verbose
        )

        # Merge branch stages into main info
        info['stages'].extend(branch_info.get('stages', []))
        needs_output_normalize = branch_info.get('needs_output_normalize', False)

        # STAGE 3: Unified output normalization for loud material
        # Always normalize to compensate for pre-EQ headroom and RMS expansion
        if needs_output_normalize:
            # Target slightly below 0 dBFS to leave headroom for playback
            output_target = 0.95

            current_peak = np.max(np.abs(processed))
            # Normalize in both directions — boost quiet material AND reduce hot
            # peaks above the target ceiling (fixes #2306: was only normalizing UP).
            if current_peak > 0:
                processed = normalize(processed, output_target)
                if verbose:
                    gain_db = 20 * np.log10(output_target / current_peak)
                    direction = "+" if gain_db >= 0 else ""
                    print(f"   Output normalize: {direction}{gain_db:.1f} dB → {output_target*100:.0f}% peak")
                info['stages'].append({'stage': 'output_normalize', 'target_peak': output_target})

        # Validate output for NaN/Inf (graceful handling for production resilience)
        processed = sanitize_audio(processed, context="simple mastering output")

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
    ) -> tuple[np.ndarray, float]:
        """Surgical peak reduction via soft clipping."""
        if current_db <= target_db:
            return audio, current_db

        threshold = 10 ** (target_db / 20.0)
        processed = soft_clip(audio, threshold=threshold, ceiling=min(0.99, threshold * 1.05))
        return processed, self._peak_db(processed)

    def _apply_safety_limiter(
        self, audio: np.ndarray, verbose: bool, ceiling: float = 0.98
    ) -> np.ndarray:
        return safety_limiter.apply(audio, verbose, ceiling=ceiling)

    def _contextualize_notches(self, notches: list[Notch], fingerprint: dict) -> list[Notch]:
        """
        Filter and scale each notch's depth based on the target band's health.

        Three regimes (driven by `band_pct / band_target` ratio):

        - **health ≥ NOTCH_CAPPED_HEALTH (≥0.7)**: full notch — band is well-
          energized, scaling depth proportionally is safe.
        - **NOTCH_MIN_BAND_HEALTH ≤ health < NOTCH_CAPPED_HEALTH (0.6-0.7)**:
          allow the notch but hard-cap its depth to NOTCH_LOW_HEALTH_CAP_DB
          (e.g. -1 dB). The resonance is real but we tread lightly because
          the band is borderline thin.
        - **health < NOTCH_MIN_BAND_HEALTH (<0.6)**: skip entirely. Notching
          an already-deficient band makes the perceived scoop worse than
          leaving the resonance alone.

        These thresholds were tuned from A/B analysis on a source where Mid
        was at 53% of target — proportional scaling alone still produced
        -2.2 pp of additional Mid scoop, contributing to the perceived
        'high-passed' sound.
        """
        if not notches:
            return notches

        # Map (low, high) Hz → fingerprint key name → reference target (median
        # across n=27 reference tracks across 8 genres). The previous values
        # were "pop-master" theoretical numbers; these are measured medians
        # from actual well-mastered records. Critically: presence/brillance/air
        # targets used to be 11%/6%/4% which made even normal records appear
        # "deficient" — now correctly set to ~1.5%/0.4%/0.1%.
        BAND_LOOKUP = [
            ((20, 60),       'sub_bass_pct',   0.087),
            ((60, 250),      'bass_pct',       0.460),
            ((250, 500),     'low_mid_pct',    0.136),
            ((500, 2000),    'mid_pct',        0.171),
            ((2000, 4000),   'upper_mid_pct',  0.055),
            ((4000, 8000),   'presence_pct',   0.015),
            ((8000, 12000),  'brilliance_pct', 0.004),
            ((12000, 24000), 'air_pct',        0.001),
        ]

        out: list[Notch] = []
        for n in notches:
            # Find which band this notch lands in
            band_pct = None
            band_target = None
            for (lo, hi), key, tgt in BAND_LOOKUP:
                if lo <= n.freq_hz < hi:
                    band_pct = fingerprint.get(key, tgt)
                    band_target = tgt
                    break

            if band_pct is None or band_target is None:
                out.append(n)
                continue

            # Health metric: ratio of actual to target energy share, capped at 1.0.
            # 1.0 = well-energized band, 0.5 = half-energized, etc.
            health = min(1.0, band_pct / band_target) if band_target > 0 else 1.0

            if health < self.config.NOTCH_MIN_BAND_HEALTH:
                # Band is severely deficient — leave the resonance alone.
                continue

            # Proportional scaling for moderately-deficient bands. The 0.7+
            # zone gets full proportional depth; the 0.6-0.7 zone is capped
            # to a hard floor regardless of the configured max depth.
            scaled_depth = n.depth_db * health

            if health < self.config.NOTCH_CAPPED_HEALTH:
                # Cap to the low-health cap (compare absolute values; both negative)
                if abs(scaled_depth) > abs(self.config.NOTCH_LOW_HEALTH_CAP_DB):
                    scaled_depth = self.config.NOTCH_LOW_HEALTH_CAP_DB

            out.append(Notch(freq_hz=n.freq_hz, depth_db=scaled_depth, q=n.q))

        return out

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
    ) -> tuple[np.ndarray, dict | None]:
        return clarity_boost.apply(audio, upper_mid_pct, intensity, sample_rate, verbose, self.config, hf_lift)

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
    ) -> tuple[np.ndarray, dict | None]:
        return bass_enhancement.apply(audio, bass_pct, intensity, sample_rate, verbose, self.config)

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

    @staticmethod
    def _peak_db(audio: np.ndarray) -> float:
        """Calculate peak level in dB."""
        peak = np.max(np.abs(audio))
        return 20 * np.log10(peak) if peak > 0 else -96.0

    @staticmethod
    def _print_fingerprint(fp: dict) -> None:
        """Print key fingerprint metrics organized by category."""
        print(f"\n📊 Fingerprint (25D):")

        # Dynamics (3D) - Critical for loudness/compression decisions
        lufs = fp.get('lufs', -14.0)
        crest_db = fp.get('crest_db', 12.0)
        bass_mid_ratio = fp.get('bass_mid_ratio', 0.0)

        # Classify material type based on LUFS + Crest
        if lufs > -12.0 and crest_db < 13.0:
            if crest_db < 8.0:
                material_type = "Hyper-compressed loud"
            else:
                material_type = "Compressed loud"
        elif lufs > -12.0:
            material_type = "Dynamic loud"
        else:
            material_type = "Quiet"

        print(f"   🔊 Dynamics: {material_type}")
        print(f"      LUFS: {lufs:.1f} dB  │  Crest: {crest_db:.1f} dB  │  Bass/Mid: {bass_mid_ratio:.2f}")

        # Frequency (7D) - Spectral balance
        sub_bass_pct = fp.get('sub_bass_pct', 0.05)
        bass_pct = fp.get('bass_pct', 0.15)
        low_mid_pct = fp.get('low_mid_pct', 0.10)
        mid_pct = fp.get('mid_pct', 0.20)
        upper_mid_pct = fp.get('upper_mid_pct', 0.25)
        presence_pct = fp.get('presence_pct', 0.15)
        air_pct = fp.get('air_pct', 0.10)

        print(f"   🎚️  Frequency Balance:")
        print(f"      Sub: {sub_bass_pct:.0%}  │  Bass: {bass_pct:.0%}  │  Lo-Mid: {low_mid_pct:.0%}  │  Mid: {mid_pct:.0%}")
        print(f"      Up-Mid: {upper_mid_pct:.0%}  │  Presence: {presence_pct:.0%}  │  Air: {air_pct:.0%}")

        # Temporal (4D) - Rhythm and dynamics
        tempo_bpm = fp.get('tempo_bpm', 120.0)
        rhythm_stability = fp.get('rhythm_stability', 0.5)
        transient_density = fp.get('transient_density', 0.5)
        silence_ratio = fp.get('silence_ratio', 0.0)

        print(f"   🥁 Temporal:")
        print(f"      Tempo: {tempo_bpm:.0f} BPM  │  Rhythm: {rhythm_stability:.0%}  │  Transients: {transient_density:.0%}  │  Silence: {silence_ratio:.0%}")

        # Spectral (3D) - Brightness and noise characteristics
        spectral_centroid = fp.get('spectral_centroid', 0.5)
        spectral_rolloff = fp.get('spectral_rolloff', 0.5)
        spectral_flatness = fp.get('spectral_flatness', 0.5)

        # Interpret brightness
        if spectral_centroid > 0.6 and spectral_rolloff > 0.6:
            brightness = "Bright"
        elif spectral_centroid < 0.4 and spectral_rolloff < 0.4:
            brightness = "Dark"
        else:
            brightness = "Neutral"

        print(f"   ✨ Spectral: {brightness}")
        print(f"      Centroid: {spectral_centroid:.0%}  │  Rolloff: {spectral_rolloff:.0%}  │  Flatness: {spectral_flatness:.0%}")

        # Harmonic (3D) - Tonality
        harmonic_ratio = fp.get('harmonic_ratio', 0.5)
        pitch_stability = fp.get('pitch_stability', 0.5)
        chroma_energy = fp.get('chroma_energy', 0.5)

        # Classify harmonic content
        avg_harmonic = (harmonic_ratio + pitch_stability) / 2
        if avg_harmonic > 0.7:
            tonality = "Highly tonal"
        elif avg_harmonic > 0.5:
            tonality = "Tonal"
        elif avg_harmonic > 0.3:
            tonality = "Mixed"
        else:
            tonality = "Percussive/Noisy"

        print(f"   🎼 Harmonic: {tonality}")
        print(f"      Harmonic: {harmonic_ratio:.0%}  │  Pitch: {pitch_stability:.0%}  │  Chroma: {chroma_energy:.0%}")

        # Stereo (2D)
        stereo_width = fp.get('stereo_width', 0.5)
        phase_correlation = fp.get('phase_correlation', 1.0)

        # Classify stereo field
        if stereo_width < 0.3:
            stereo_type = "Narrow"
        elif stereo_width < 0.6:
            stereo_type = "Normal"
        else:
            stereo_type = "Wide"

        print(f"   🎧 Stereo: {stereo_type}")
        print(f"      Width: {stereo_width:.0%}  │  Phase Corr: {phase_correlation:.2f}")

        # Variation (3D) - Consistency metrics
        dynamic_range_variation = fp.get('dynamic_range_variation', 0.5)
        loudness_variation_std = fp.get('loudness_variation_std', 0.0)
        peak_consistency = fp.get('peak_consistency', 0.5)

        print(f"   📊 Variation:")
        print(f"      DR Var: {dynamic_range_variation:.0%}  │  Loudness σ: {loudness_variation_std:.1f}  │  Peak Cons: {peak_consistency:.0%}")

    @staticmethod
    def _print_time_metrics(timings: dict[str, float], duration_sec: float) -> None:
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
