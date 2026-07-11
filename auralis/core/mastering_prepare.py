"""
Mastering File Preparation
~~~~~~~~~~~~~~~~~~~~~~~~~~

Per-file setup for SimpleMasteringPipeline.master_file(): fingerprinting,
metadata loading, resonance-notch detection + band-context depth scaling,
accurate ITU-R BS.1770 loudness measurement, and a whole-song peak pre-scan.

Extracted from simple_mastering.py's _master_file_impl (#4072) — this is
pure once-per-file setup, run before the chunked processing loop
(mastering_chunk_loop.process_chunks) begins.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf

from . import mastering_diagnostics
from .dsp import ResonanceNotcher
from .mastering_notch_context import contextualize_notches

if TYPE_CHECKING:
    from .simple_mastering import SimpleMasteringPipeline


def measure_window_loudness(
    window: np.ndarray, sample_rate: int
) -> tuple[float | None, float | None]:
    """Accurate ITU-R BS.1770 integrated LUFS + broadband crest on a window.

    Used to drive the loudness maximizer instead of the fingerprint's
    RMS-proxy LUFS (which under-reads high-dynamic-range material). The
    window is the representative middle slice already loaded for resonance
    detection. Returns (None, None) on any failure so callers fall back to
    the fingerprint value.

    Args:
        window: Audio (samples, channels) or (samples,), float.
        sample_rate: Sample rate in Hz.

    Returns:
        (integrated_lufs, crest_db) or (None, None) if measurement failed
        or the window was too short/silent.
    """
    try:
        from ..analysis.loudness_meter import LoudnessMeter

        if window.size == 0:
            return None, None

        meter = LoudnessMeter(sample_rate=sample_rate)
        block = meter.block_size
        for start in range(0, len(window), block):
            chunk = window[start:start + block]
            if len(chunk) >= block // 2:
                meter.measure_chunk(chunk)
        lufs = meter.finalize_measurement().integrated_lufs
        if not np.isfinite(lufs):
            return None, None

        mono = np.mean(window, axis=1) if window.ndim == 2 else window
        rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
        peak = float(np.max(np.abs(mono)))
        crest = (20.0 * np.log10(peak / rms)) if rms > 1e-9 and peak > 0 else None
        return float(lufs), crest
    except Exception:
        return None, None


def prepare_file(
    pipeline: 'SimpleMasteringPipeline',
    orig_path: Path,
    input_path: Path,
    output_path: str,
    verbose: bool,
) -> dict:
    """
    Run once-per-file setup: fingerprint, metadata, resonance-notch
    detection + band-context scaling, accurate loudness measurement, and a
    whole-song peak pre-scan.

    Side effect: sets pipeline._notches, pipeline._source_lufs,
    pipeline._source_crest_db, pipeline._song_peak_db — consumed later by
    branch processing during the chunk loop
    (mastering_process_chunk.process_chunk).

    Returns:
        dict with fingerprint, sr, total_frames, channels, duration, and a
        timings dict covering the steps run here (fingerprint,
        load_metadata, detect_notches, measure_song_peak).
    """
    timings: dict[str, float] = {}
    config = pipeline.config

    # Step 1: Get fingerprint (uses orig_path so cache hits still work)
    if verbose:
        print(f"📂 Input: {orig_path.name}")
        print(f"📂 Output: {Path(output_path).name}")
        print("\n🔍 Fingerprinting...")

    step_start = time.perf_counter()
    fingerprint = pipeline.fingerprint_service.get_or_compute(orig_path)
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
        mastering_diagnostics.print_fingerprint(fingerprint)

    # Step 2b: Detect resonances once per file.
    # Run on a representative 30s window from the middle of the file —
    # avoids loading the full file but gives enough data for the FFT
    # averaging to find stable spectral peaks. The same notch list is
    # applied to every chunk during processing.
    pipeline._notches = []
    pipeline._source_lufs = None
    pipeline._source_crest_db = None
    pipeline._song_peak_db = None
    step_start = time.perf_counter()
    notch_sample_seconds = 30
    notch_window = min(total_frames, sr * notch_sample_seconds)
    notch_start = max(0, (total_frames - notch_window) // 2)
    with sf.SoundFile(str(input_path)) as audio_file:
        audio_file.seek(notch_start)
        notch_sample = audio_file.read(notch_window).astype(np.float32)

    # Accurate ITU-R BS.1770 integrated loudness + crest on the same
    # representative window. Drives the QuietBranch loudness maximizer's
    # makeup decision (the fingerprint's RMS-proxy LUFS under-reads
    # high-DR material by 3-5 dB). Best-effort: leaves None on failure and
    # the branch falls back to the fingerprint value.
    pipeline._source_lufs, pipeline._source_crest_db = measure_window_loudness(
        notch_sample, sr
    )

    # SoundFile returns (samples, channels); ResonanceNotcher handles both
    # mono and stereo input internally.
    detected = ResonanceNotcher.detect(
        notch_sample,
        sample_rate=sr,
        min_freq=config.NOTCH_MIN_FREQ_HZ,
        max_freq=config.NOTCH_MAX_FREQ_HZ,
        min_prominence_db=config.NOTCH_MIN_PROMINENCE_DB,
        max_notches=config.NOTCH_MAX_COUNT,
        max_depth_db=config.NOTCH_MAX_DEPTH_DB,
    )

    # Band-context awareness: scale each notch's depth by the energy
    # share of the band it lands in. If the target band is already
    # under-represented (e.g. Mid at 10% vs 24% target), full-depth
    # notching gouges an already-deficient band — so we shrink the cut
    # proportionally. Notch on a well-energized band → full depth;
    # notch on a deficient band → reduced depth (or skipped entirely
    # below NOTCH_MIN_BAND_HEALTH).
    pipeline._notches = contextualize_notches(detected, fingerprint, config)
    timings['detect_notches'] = time.perf_counter() - step_start
    if verbose:
        if pipeline._notches:
            print(f"\n🎯 Resonance notches detected ({len(pipeline._notches)}):")
            for n in pipeline._notches:
                print(f"   {n.freq_hz:6.0f} Hz   {n.depth_db:+5.1f} dB (Q={n.q:.1f})")
        elif detected:
            # Resonances exist but all skipped by band-context filter
            print(f"\n🎯 Resonances detected but skipped — target bands too deficient")
            print(f"   ({len(detected)} candidates: " +
                  ", ".join(f"{n.freq_hz:.0f}Hz" for n in detected) + ")")
        else:
            print("\n🎯 No prominent resonances detected — skipping notch stage")

    # Step 2c: Whole-song peak, scanned once up front.
    # 2026-07-08: the QuietBranch makeup-gain headroom clamp (see
    # AdaptiveLoudnessControl.calculate_adaptive_gain) used to receive
    # each chunk's OWN peak_db, computed fresh per 30s chunk in the
    # loop below. That's correct for Stage 1's per-chunk clip
    # prevention (a chunk's own peak is exactly what must not clip),
    # but wrong for the gain-staging decision: a song's quiet verse
    # chunk would get its full makeup gain while a loud chorus chunk
    # — same song, same target loudness — got clamped down hard
    # because ITS peak happened to be high, producing an audible
    # level inconsistency between sections instead of one consistent
    # gain for the whole song. Scanning once here and using this
    # value (not the per-chunk one) for that specific headroom check
    # fixes the inconsistency and is still fully clip-safe: it's the
    # max peak that will ever occur, so no chunk's headroom is
    # under-estimated.
    step_start = time.perf_counter()
    song_peak_linear = 0.0
    scan_block_frames = sr * config.CHUNK_DURATION_SEC
    with sf.SoundFile(str(input_path)) as audio_file:
        while True:
            block = audio_file.read(scan_block_frames)
            if block.size == 0:
                break
            block_peak = float(np.max(np.abs(block)))
            if block_peak > song_peak_linear:
                song_peak_linear = block_peak
    pipeline._song_peak_db = (
        20 * np.log10(song_peak_linear) if song_peak_linear > 0 else -96.0
    )
    timings['measure_song_peak'] = time.perf_counter() - step_start

    return {
        'fingerprint': fingerprint,
        'sr': sr,
        'total_frames': total_frames,
        'channels': channels,
        'duration': duration,
        'timings': timings,
    }
