"""
Mastering Chunked Processing Loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reads a file in overlapping chunks, runs each through
SimpleMasteringPipeline._process, assembles the output with an equal-power
crossfade at chunk boundaries, applies a True Peak guard, and streams the
result to the output WAV.

Extracted from simple_mastering.py's _master_file_impl "Step 3" (#4072).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf

from .mastering_process_chunk import compute_peak_db

if TYPE_CHECKING:
    from .mastering_config import SimpleMasteringConfig
    from .simple_mastering import SimpleMasteringPipeline


def process_chunks(
    pipeline: 'SimpleMasteringPipeline',
    input_path: Path,
    output_path: str,
    sr: int,
    total_frames: int,
    fingerprint: dict,
    intensity: float,
    config: 'SimpleMasteringConfig',
    verbose: bool,
) -> tuple[dict, int]:
    """
    Process the whole file in chunks and write the result to output_path.

    Returns:
        (info, chunks_processed) — info is the processing-stages dict from
        the first chunk (matches original behavior: info is only updated
        once, from chunk 0).
    """
    # Equal-power crossfade between chunks for seamless transitions.
    # Adjacent chunks both process the overlap region, then we blend
    # with cosine curves to maintain perceived loudness through the join.
    crossfade_samples = int(sr * config.CROSSFADE_DURATION_SEC)

    # Process and write in streaming mode
    chunk_size = sr * config.CHUNK_DURATION_SEC
    info = {'stages': []}

    # Every processing path yields stereo: mono is expanded to 2 channels
    # (see the `chunk.ndim == 1` branch below) and >2ch sources are downmixed
    # to L+R, so the output sink is always opened with 2 channels. Using
    # `min(channels, 2)` here opened a 1-channel sink for mono input and then
    # crashed with a shape mismatch on the first stereo write (#4494).
    out_channels = 2
    with sf.SoundFile(str(input_path)) as audio_file:
        with sf.SoundFile(
            output_path,
            mode='w',
            samplerate=sr,
            channels=out_channels,
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
                elif chunk.ndim == 2 and chunk.shape[1] > 2:
                    # Multi-channel (e.g. 5.1 surround): take L+R only.
                    # soundfile yields (samples, channels) at this point.
                    chunk = chunk[:, :2]

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
                peak_db = compute_peak_db(chunk)

                # Process chunk (includes overlap tail for crossfading)
                processed_chunk, chunk_info = pipeline._process(
                    chunk, fingerprint, peak_db, intensity, sr, verbose=False
                )

                # True Peak guard (empirically validated — June 2026 study):
                # 74 % of outputs exceeded 0 dBFS True Peak (avg +0.77 dBFS)
                # because the harmonic exciter generates near-Nyquist content
                # that causes intersample reconstruction peaks even when sample
                # peaks are held at 0.97.  4× oversampled peak measurement +
                # proportional gain reduction caps True Peak at -0.5 dBFS.
                try:
                    from scipy.signal import resample_poly as _rsp
                    _TP_CEILING = 10 ** (-0.5 / 20)     # −0.5 dBFS = 0.9441
                    _chunk_4x = _rsp(processed_chunk, 4, 1, axis=1)
                    _tp = float(np.max(np.abs(_chunk_4x)))
                    if _tp > _TP_CEILING:
                        processed_chunk = processed_chunk * (_TP_CEILING / _tp)
                except Exception:
                    pass   # best-effort; never let this path break the pipeline

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

                if verbose and chunks_processed % config.PROGRESS_REPORT_INTERVAL_CHUNKS == 0:
                    progress = (chunks_processed / total_chunks) * 100
                    print(f"   Progress: {progress:.0f}% ({chunks_processed}/{total_chunks} chunks)")

    return info, chunks_processed
