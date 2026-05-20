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
from ..dsp.basic import amplify, normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ..dsp.utils.stereo import adjust_stereo_width_multiband
from ..utils.audio_validation import sanitize_audio, validate_audio_finite
from .dsp import HarmonicExciter, ParallelEQUtilities
from .mastering_branches import MaterialClassifier
from .mastering_config import SimpleMasteringConfig
from .processing.base import ExpansionStrategies
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
        timings: dict[str, float] = {}
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

                            # Equal-power crossfade (cosine curves maintain loudness)
                            t = np.linspace(0.0, np.pi / 2, head_len)
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
    ) -> tuple[np.ndarray, dict | None]:
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
            phase_factor = SmoothCurveUtilities.ramp_to_s_curve(
                phase_correlation, 0.3, 0.7
            )
        else:
            phase_factor = 1.0

        # 2. Width expansion curve: bell curve with peak at 25% width
        # Very narrow (<15%) and moderate (>35%) get less expansion
        # Sweet spot at 20-30% width gets most expansion

        if current_width < 0.15:
            # Extremely narrow: smooth ramp up from 0% to 15%
            width_curve = SmoothCurveUtilities.ramp_to_s_curve(
                current_width, 0.0, 0.15
            )
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
            # Inverted S-curve (1.0 at 0.30, 0.0 at 0.40)
            fade_curve = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(
                current_width, 0.30, 0.40
            )
            narrowness_factor = 0.3 * fade_curve

        # 3. Brightness preservation curve - reduce expansion for bright tracks
        # High spectral centroid or air content = already bright, be gentle
        brightness_metric = max(spectral_centroid, air_pct * 2.0)  # 0-1

        # Smooth S-curve: 0.6-1.0 brightness reduces expansion
        if brightness_metric > 0.6:
            brightness_curve = SmoothCurveUtilities.ramp_to_s_curve(
                brightness_metric, 0.6, 1.0
            )
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
    ) -> tuple[np.ndarray, dict | None]:
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

        # Apply parallel low-shelf boost using utility
        processed = ParallelEQUtilities.apply_low_shelf_boost(
            audio,
            boost_db=boost_db,
            freq_hz=self.config.BASS_SHELF_HZ,
            sample_rate=sample_rate
        )

        if verbose:
            print(f"   Bass enhance: +{boost_db:.1f} dB below {self.config.BASS_SHELF_HZ:.0f}Hz")

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
    ) -> tuple[np.ndarray, dict | None]:
        """
        Apply adaptive sub-bass control (20-60Hz).

        High sub-bass → tighten (reduce rumble)
        Low sub-bass + decent bass → already good, skip
        Low sub-bass + low bass → enhance together via bass_enhancement

        Uses PARALLEL processing pattern for precise dB control:
        - Extract sub-bass band with LP filter
        - Apply reduction gain to extracted band
        - Add the reduction DIFFERENCE on top of original

        This gives precise dB control unlike HP+blend which can cause -10dB+ loss.
        """
        # Smooth curve: only act if sub-bass is excessive (> 8%)
        if sub_bass_pct < 0.08:
            return audio, None  # Sub-bass is fine or already handled by bass enhancement

        # Smooth curve for rumble reduction
        rumble_factor = SmoothCurveUtilities.ramp_to_s_curve(
            sub_bass_pct, 0.08, 0.15
        )

        # Calculate reduction amount (gentle)
        max_reduction_db = -2.0 * intensity  # Max -2dB reduction
        reduction_db = max_reduction_db * rumble_factor

        if abs(reduction_db) < 0.3:
            return audio, None

        # Apply parallel low-shelf reduction (negative boost)
        processed = ParallelEQUtilities.apply_low_shelf_boost(
            audio,
            boost_db=reduction_db,  # Negative value for reduction
            freq_hz=self.config.SUB_BASS_CUTOFF_HZ,
            sample_rate=sample_rate
        )

        if verbose:
            print(f"   Sub-bass tighten: {reduction_db:.1f} dB @ <{self.config.SUB_BASS_CUTOFF_HZ:.0f}Hz")

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
    ) -> tuple[np.ndarray, dict | None]:
        """
        Apply adaptive mid-range warmth (200-2kHz body).

        Low mids → add warmth and body
        Good mids → skip

        Uses smooth curves throughout.
        """
        # Combine low-mid and mid for overall body content
        body_content = (low_mid_pct + mid_pct) / 2.0

        # Smooth curve: boost from 0% to 25% body content
        if body_content >= 0.25:
            return audio, None  # Already has good body

        # Inverted S-curve (1.0 at 0%, 0.0 at 25%)
        body_factor = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(
            body_content, 0.0, 0.25
        )

        # Calculate boost
        max_boost_db = 1.5 * intensity  # Gentler than presence
        boost_db = max_boost_db * body_factor

        if boost_db < 0.3:
            return audio, None

        # Apply parallel bandpass boost at 200-2kHz (body zone)
        processed = ParallelEQUtilities.apply_bandpass_boost(
            audio,
            boost_db=boost_db,
            low_hz=self.config.MID_BODY_LOW_HZ,
            high_hz=self.config.MID_BODY_HIGH_HZ,
            sample_rate=sample_rate
        )

        if verbose:
            print(f"   Mid warmth: +{boost_db:.1f} dB @ {self.config.MID_BODY_LOW_HZ:.0f}-{self.config.MID_BODY_HIGH_HZ:.0f}Hz")

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
    ) -> tuple[np.ndarray, dict | None]:
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

        # Smooth curve: boost from 0% to 30% presence
        if presence_content >= 0.30:
            return audio, None  # Already has good presence

        # Inverted S-curve (1.0 at 0%, 0.0 at 30%)
        presence_factor = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(
            presence_content, 0.0, 0.30
        )

        # Calculate boost based on smooth presence deficiency curve
        max_boost_db = 2.0 * intensity
        boost_db = max_boost_db * presence_factor

        if boost_db < 0.3:
            return audio, None  # Too small to matter

        # Apply parallel bandpass boost at presence range (2-8kHz)
        processed = ParallelEQUtilities.apply_bandpass_boost(
            audio,
            boost_db=boost_db,
            low_hz=self.config.PRESENCE_LOW_HZ,
            high_hz=self.config.PRESENCE_HIGH_HZ,
            sample_rate=sample_rate
        )

        if verbose:
            print(f"   Presence enhance: +{boost_db:.1f} dB @ {self.config.PRESENCE_LOW_HZ:.0f}-{self.config.PRESENCE_HIGH_HZ:.0f}Hz")

        return processed, {
            'stage': 'presence_enhance',
            'boost_db': boost_db,
            'presence_content': presence_content
        }

    def _apply_harmonic_exciter(
        self,
        audio: np.ndarray,
        presence_pct: float,
        air_pct: float,
        spectral_rolloff: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> tuple[np.ndarray, dict | None]:
        """
        Generate upper-octave harmonics for dark / bandwidth-limited sources.

        Shelf EQ can only amplify what already exists. For lo-fi captures or
        low-bitrate audio where everything above ~6 kHz has been brick-walled,
        the air/presence shelves are lifting near-silence and the result still
        sounds dull. This stage saturates a midrange donor band and high-passes
        the result, mixing the newly generated harmonics in parallel so the
        downstream presence/air shelves have something to work with.

        Activates only when the spectrum is genuinely dark — bright material is
        untouched.

        Args:
            audio: Stereo audio [2, samples]
            presence_pct: Fingerprint presence percentage (4-6 kHz, 0-1)
            air_pct: Fingerprint air percentage (6-20 kHz, 0-1)
            spectral_rolloff: Frequency below which most energy lies (0-1)
            intensity: Processing intensity 0.0-1.0
            sample_rate: Audio sample rate in Hz
            verbose: Print progress

        Returns:
            (processed_audio, stage_info or None if exciter did not engage)
        """
        # Brightness metric: weighted blend of HF energy and where the spectrum
        # rolls off. 0 = fully dark, 1 = fully bright. presence/air are most
        # diagnostic; spectral_rolloff only contributes once it's clearly in
        # bright territory (>60% of Nyquist ≈ >13 kHz at 44.1k). Below that,
        # rolloff just confirms darkness and shouldn't suppress excitation.
        rolloff_brightness = max(0.0, (spectral_rolloff - 0.60) / 0.40)
        brightness = (
            presence_pct * 2.0   # presence at 50% counts as fully bright
            + air_pct * 3.0      # air at ~33% counts as fully bright
            + rolloff_brightness * 0.4
        )
        brightness = float(np.clip(brightness, 0.0, 1.0))
        darkness = 1.0 - brightness

        # Only engage on genuinely dark material.
        activate_threshold = 1.0 - self.config.EXCITER_DARKNESS_ACTIVATE
        if darkness < activate_threshold:
            return audio, None

        # Smooth ramp from activate_threshold → 1.0 (fully dark)
        excite_factor = SmoothCurveUtilities.ramp_to_s_curve(
            darkness, activate_threshold, 1.0
        )

        # Wet level scales with darkness AND intensity. MIN_WET is the level
        # at the activation threshold (subtle); MAX_WET is the ceiling at
        # full darkness (obvious). Intensity scales the *ceiling* only, so the
        # floor stays audible even at low intensities.
        min_wet_db = self.config.EXCITER_MIN_WET_DB
        max_wet_db = self.config.EXCITER_MAX_WET_DB * intensity
        # Guard against intensity > 1.0 pushing max below min (e.g. with
        # extreme adaptive intensity, max_wet_db could become more negative).
        if max_wet_db < min_wet_db:
            max_wet_db = min_wet_db
        wet_db = min_wet_db + (max_wet_db - min_wet_db) * excite_factor

        # Drive also scales with darkness — darker source can take more drive
        # because the new harmonics have to fight more upstream rolloff.
        drive_db = self.config.EXCITER_DRIVE_DB * (0.7 + 0.3 * excite_factor)

        processed = HarmonicExciter.apply(
            audio,
            sample_rate=sample_rate,
            wet_db=wet_db,
            drive_db=drive_db,
            donor_low_hz=self.config.EXCITER_DONOR_LOW_HZ,
            donor_high_hz=self.config.EXCITER_DONOR_HIGH_HZ,
            hp_cutoff_hz=self.config.EXCITER_HP_CUTOFF_HZ,
            asymmetry=self.config.EXCITER_ASYMMETRY,
        )

        if verbose:
            print(
                f"   Harmonic exciter: {wet_db:+.1f} dB wet, "
                f"{drive_db:.1f} dB drive (darkness {darkness:.2f})"
            )

        return processed, {
            'stage': 'harmonic_exciter',
            'wet_db': wet_db,
            'drive_db': drive_db,
            'darkness': darkness,
        }

    def _apply_air_enhancement(
        self,
        audio: np.ndarray,
        air_pct: float,
        spectral_rolloff: float,
        intensity: float,
        sample_rate: int,
        verbose: bool
    ) -> tuple[np.ndarray, dict | None]:
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

        # Smooth S-curve from 0.4 to 1.0
        air_factor = SmoothCurveUtilities.ramp_to_s_curve(
            darkness_factor, 0.4, 1.0
        )

        # Calculate boost based on smooth darkness curve
        max_boost_db = 1.5 * intensity
        boost_db = max_boost_db * air_factor

        if boost_db < 0.3:
            return audio, None  # Too small to matter

        # Apply parallel high-shelf boost above 8kHz
        processed = ParallelEQUtilities.apply_high_shelf_boost(
            audio,
            boost_db=boost_db,
            freq_hz=self.config.AIR_SHELF_HZ,
            sample_rate=sample_rate
        )

        if verbose:
            print(f"   Air enhance: +{boost_db:.1f} dB above {self.config.AIR_SHELF_HZ:.0f}Hz")

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
