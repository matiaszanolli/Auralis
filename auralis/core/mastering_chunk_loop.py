"""
Mastering Chunked Processing Loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reads a file in overlapping chunks, runs each through
SimpleMasteringPipeline._process, assembles the output with an equal-gain
(raised-cosine) crossfade at chunk boundaries, applies a True Peak guard, and
streams the result to the output WAV.

Extracted from simple_mastering.py's _master_file_impl "Step 3" (#4072).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.dsp.utils.conversion import db_to_amplitude
import os
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import soundfile as sf

from .mastering_chunk_assembly import (
    apply_true_peak_guard,
    assemble_write_region,
    merge_stage_info,
    read_chunk,
    true_peak_4x,
)
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
        (info, chunks_processed) — info is chunk 0's processing dict with
        the stages run by later chunks merged in (de-duplicated), so a
        stage that only engaged on a loud later chunk is still reported.
    """
    # Equal-gain (raised-cosine) crossfade between chunks for seamless
    # transitions. Adjacent chunks both process the *same* overlap region of
    # source samples, so their outputs are highly correlated — equal-gain is
    # the correct blend here (sin^2 + cos^2 == 1, amplitude sum = 1).
    # Do NOT switch to sin/cos (true equal-power, amplitude-squared sum = 1):
    # that's for blending uncorrelated material (e.g. different tracks) and
    # would introduce an audible +3 dB bulge at the midpoint of every chunk
    # boundary here. See #4966.
    crossfade_samples = int(sr * config.CROSSFADE_DURATION_SEC)

    # Process and write in streaming mode
    chunk_size = sr * config.CHUNK_DURATION_SEC

    # Every processing path yields stereo: mono is expanded to 2 channels
    # (see the `chunk.ndim == 1` branch below) and >2ch sources are downmixed
    # to L+R, so the output sink is always opened with 2 channels. Using
    # `min(channels, 2)` here opened a 1-channel sink for mono input and then
    # crashed with a shape mismatch on the first stereo write (#4494).
    out_channels = 2

    # Stage on the same filesystem, then os.replace() onto the final name only
    # after every chunk is written (#5109).
    #
    # The loop below has no per-chunk try/except, so any raise — the
    # validate_audio_finite(..., repair=False) in mastering_process_chunk.py, an
    # _assert_finite in mastering_branches/continuous.py, a DSP stage — used to
    # propagate while sf.SoundFile's __exit__ still finalised a syntactically
    # valid header over whatever had been written. The result was a truncated
    # but perfectly readable file sitting at the exact requested output path,
    # indistinguishable from a finished master. Neither caller in auto_master.py
    # removed it: master_folder appends to failed_files and moves on, leaving
    # the partial file among its successful neighbours under the expected name.
    #
    # os.replace is atomic within a filesystem, so a reader sees the complete
    # file or no file — never a prefix. The temp lives in the destination
    # directory to keep the rename on one filesystem (a cross-device rename is
    # not atomic and raises), and keeps the real extension because soundfile
    # infers the container format from it. Same shape as the backend's
    # encoding/atomic_io.py (#4576), reimplemented rather than imported:
    # auralis-web is not an importable package from the engine, and depending
    # on the web backend from auralis/ would invert the layering.

    # #5694: measurement pre-pass. The chain's file-level gain is keyed to the
    # INPUT peak (prepare_file's _song_peak_db), but the stages in between
    # (makeup gain, EQ shelves, exciter, loudness maximizer) do NOT preserve
    # the peak: for quiet sources the chain already lifts the peak toward the
    # ceiling and the input-keyed gain is applied on top, leaving the final
    # np.clip as the only protection — hard clipping. Instead of assuming a
    # peak-transfer ratio, run the identical render once with no sink, measure
    # the actual final signal, and derive ONE uniform correction from it.
    # Constant, so #5559's macro-dynamics invariant (a quiet movement is not
    # raised to the loudest section's level) is untouched.
    _, _, measured_sample_peak, measured_true_peak = _render_to_sink(
        pipeline, input_path, None, sr, total_frames, fingerprint,
        intensity, config, verbose, crossfade_samples, chunk_size,
        out_channels,
    )
    _tp_ceiling = db_to_amplitude(-0.5)
    correction_gain = min(
        1.0,
        0.99 / max(measured_sample_peak, 1e-9),
        _tp_ceiling / max(measured_true_peak, 1e-9),
    )
    if verbose and correction_gain < 1.0:
        print(
            f"   Two-pass peak correction: {20 * np.log10(correction_gain):+.2f} dB "
            f"(measured sample peak {measured_sample_peak:.3f}, "
            f"true peak {measured_true_peak:.3f})"
        )

    final_path = Path(output_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp always makes its inode mode 0600. Since os.replace preserves that
    # inode, published masters also become owner-only regardless of umask
    # (#5592). Create the file at 0666 inside a private 0700 stage directory:
    # os.open applies the current process umask atomically, without reading or
    # temporarily changing the process-wide (and thread-sensitive) umask.
    with tempfile.TemporaryDirectory(
        dir=str(final_path.parent), prefix=f".{final_path.stem}."
    ) as stage_dir:
        tmp_path = Path(stage_dir) / f"render.part{final_path.suffix}"
        tmp_fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        os.close(tmp_fd)
        info, chunks_processed, _, _ = _render_to_sink(
            pipeline, input_path, tmp_path, sr, total_frames, fingerprint,
            intensity, config, verbose, crossfade_samples, chunk_size,
            out_channels, correction_gain=correction_gain,
        )
        # The renderer has closed SoundFile by now. Flush the complete staged
        # bytes before replacing the visible destination (cf. #4576).
        with tmp_path.open("rb") as staged:
            os.fsync(staged.fileno())
        os.replace(tmp_path, final_path)
        # TemporaryDirectory also removes staged files on all exceptions,
        # including KeyboardInterrupt, while leaving an earlier master intact.

    return info, chunks_processed


def _render_to_sink(
    pipeline: 'SimpleMasteringPipeline',
    input_path: Path,
    output_path: Path | None,
    sr: int,
    total_frames: int,
    fingerprint: dict[str, Any],
    intensity: float,
    config: 'SimpleMasteringConfig',
    verbose: bool,
    crossfade_samples: int,
    chunk_size: int,
    out_channels: int,
    correction_gain: float = 1.0,
) -> tuple[dict[str, Any], int, float, float]:
    """Render every chunk into ``output_path``. Raises if the render is short.

    Split out of process_chunks so the staging/rename lives in one place and
    this stays the pure render (#5109).

    ``output_path=None`` is the measurement pass of the two-pass render
    (#5694): identical processing, nothing written; instead the maximum
    sample peak and 4x-oversampled true peak of the would-be output (the
    post-assembly, PRE-clip signal) are accumulated and returned alongside
    the info, so process_chunks can derive one uniform correction gain.

    ``correction_gain`` (#5694) is a constant multiplier applied after the
    True Peak guard; constant so macro-dynamics (#5559) are untouched, and
    linear so it commutes with the crossfade assembly.
    """
    info: dict[str, Any] | None = None
    measured_sample_peak = 0.0
    measured_true_peak = 0.0

    # The pipeline is deterministic per chunk for a given file (no cross-chunk
    # DSP state; `_notches` is written once per file by prepare and only
    # read), so the measurement pass reproduces this render's outputs
    # exactly — that is what makes a two-pass gain correction sound.
    with sf.SoundFile(str(input_path)) as audio_file:
        with (
            nullcontext(None) if output_path is None
            else sf.SoundFile(
                str(output_path),
                mode='w',
                samplerate=sr,
                channels=out_channels,
                subtype='PCM_24'
            )
        ) as output_file:
            chunks_processed = 0
            total_chunks = int(np.ceil(total_frames / chunk_size))

            prev_tail = None  # Previous chunk's processed overlap tail
            read_pos = 0

            while read_pos < total_frames:
                core_samples = min(chunk_size, total_frames - read_pos)
                is_last = (read_pos + core_samples >= total_frames)

                chunk = read_chunk(
                    audio_file, read_pos, core_samples, total_frames, crossfade_samples, is_last
                )
                if chunk is None:
                    break

                # Compute peak_db per chunk so the peak-reduction gate correctly
                # engages on loud sections even when the track starts quietly (fixes
                # #2402: stale first-chunk peak caused missed limiting on loud choruses).
                peak_db = compute_peak_db(chunk)

                # Process chunk (includes overlap tail for crossfading)
                processed_chunk, chunk_info = pipeline._process(
                    chunk, fingerprint, peak_db, intensity, sr, verbose=False
                )
                processed_chunk = apply_true_peak_guard(pipeline, processed_chunk)

                # #5694: the uniform two-pass correction (1.0 in the
                # measurement pass itself).
                if correction_gain != 1.0:
                    processed_chunk = processed_chunk * correction_gain

                # #3700: sample-count invariant — crossfade slice arithmetic
                # below assumes _process() preserves the time axis. A future
                # DSP regression (resampling, time-stretch, IIR padding bug)
                # would otherwise silently corrupt the chunk boundary.
                if processed_chunk.shape[1] != chunk.shape[1]:
                    raise RuntimeError(
                        f"DSP sample-count violation: input {chunk.shape[1]} "
                        f"-> output {processed_chunk.shape[1]}"
                    )

                info = merge_stage_info(info, chunk_info)

                # Assemble output with crossfading at chunk boundaries.
                write_region, new_tail = assemble_write_region(
                    processed_chunk, prev_tail, chunks_processed == 0, core_samples, is_last
                )

                # Convert back to (samples, channels) for writing.
                # write_region is always (channels, samples) after processing,
                # so unconditional transpose is correct here too (issue #2292).
                write_region = write_region.T

                if output_file is None:
                    # Measurement pass (#5694): record the final pre-clip
                    # signal's peaks. Post-assembly so crossfade constructive
                    # interference (#3660) is included; pre-clip so the number
                    # is what the write clamp would see.
                    measured_sample_peak = max(
                        measured_sample_peak, float(np.max(np.abs(write_region)))
                    )
                    measured_true_peak = max(
                        measured_true_peak, true_peak_4x(write_region)
                    )
                else:
                    # #3660: explicit clamp to [-1.0, 1.0] before PCM_24 encode —
                    # mirrors the saver.py fix from #3471. Crossfade
                    # constructive interference at chunk boundaries can push
                    # samples slightly out of range; libsndfile's implicit
                    # clipping behaviour varies across builds.
                    write_region = np.clip(write_region, -1.0, 1.0)

                    output_file.write(write_region)
                # Commit new tail only after the write succeeds (or, in the
                # measurement pass, after the equivalent bookkeeping): if
                # anything raises, prev_tail retains the last-good value
                # (#2429).
                prev_tail = new_tail

                chunks_processed += 1
                read_pos += core_samples

                if verbose and chunks_processed % config.PROGRESS_REPORT_INTERVAL_CHUNKS == 0:
                    progress = (chunks_processed / total_chunks) * 100
                    print(f"   Progress: {progress:.0f}% ({chunks_processed}/{total_chunks} chunks)")

    # The `chunk.size == 0` break above exits without raising, which would
    # otherwise publish a short file as a finished master — the same outcome
    # #5109 is about, reached without an exception. read_pos advances by
    # core_samples every iteration and core_samples is
    # min(chunk_size, total_frames - read_pos), so a complete render always
    # performs exactly ceil(total_frames / chunk_size) iterations; a shortfall
    # means the source read returned nothing while frames remained.
    if chunks_processed != total_chunks:
        raise RuntimeError(
            f"Mastering render is short: wrote {chunks_processed} of "
            f"{total_chunks} chunks for '{input_path}'. The source stopped "
            f"yielding samples before {total_frames} frames were read."
        )

    return (
        info if info is not None else {'stages': []},
        chunks_processed,
        measured_sample_peak,
        measured_true_peak,
    )

