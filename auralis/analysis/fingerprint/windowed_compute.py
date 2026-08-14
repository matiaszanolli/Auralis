#!/usr/bin/env python3

"""
Windowed Fingerprint Computation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The single implementation of the 25D fingerprint's load / crop / window-select /
analyze sequence (#4595).

Two independent implementations used to exist: the batch library-scan path
(`services/fingerprint_extractor.py`) truncated to the first 90 s from the start
and ran a single-window analysis, while the on-demand path
(`fingerprint_service.py`) used the empirically validated body+probe strategy.
Whichever path wrote the DB row first won permanently — and the background queue
almost always ran first, so essentially every track in a scanned library was
stamped with the less accurate fingerprint.

Both paths now call `compute_windowed_fingerprint()`, so they cannot drift again.
This holds at the call-site level only if the function's own internal branches
also agree — #4994 fixed a case where they didn't: the `audio is None` branch
used the body+probe strategy below, but the pre-loaded-audio branch instead did
a plain start-crop with no probe correction. Both branches now share the exact
same windowing math (see `_crop_and_resample()` below).

Windowing strategy (validated June 2026, 34 tracks): full 25D analysis on the
BODY window at 50 % of duration, plus two lightweight 30 s probes at 25 % / 75 %;
`lufs` and `crest_db` are replaced with the median across all three.
Single-window LUFS RMSE 1.96 dB / max 9.2 dB → multi-window 1.07 dB / max 3.6 dB.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Frequency band keys that must sum to ~1.0 in a valid fingerprint.
_BAND_PCT_KEYS: tuple[str, ...] = (
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct',
)


# Seconds decoded ahead of a bounded FFmpeg window and then trimmed off, so the
# samples handed to the analyzer are identical to the same span of a full decode
# (#5110). 0.5 s was measured as sufficient for bit-exact agreement on MP3;
# 1.0 s carries margin for other codecs at negligible cost against a 90 s window.
_SEEK_PREROLL_S = 1.0


def _band_pct_valid(fp: dict[str, Any]) -> bool:
    """Return True if the seven frequency-band fractions sum to 1 ± 0.05."""
    total = float(sum(fp.get(k, 0.0) for k in _BAND_PCT_KEYS))
    return 0.95 <= total <= 1.05


def _sanitize_non_finite(fingerprint: dict[str, Any], label: str) -> list[str]:
    """Replace NaN/Inf dimensions with 0.0 in place; return the names replaced.

    Reinstates the guard added for #2531, which lived in
    ``AudioFingerprintAnalyzer.analyze()`` until ``871356f7`` ("route
    fingerprinting through in-process Rust engine") replaced that analyzer
    wholesale without porting it (#5103). Nothing downstream re-checked, so a
    single NaN sample in decoded audio reached ``track_fingerprints`` unguarded
    and stayed there: ``_prepare_for_storage()`` validates dimension *count*
    only, ``upsert()`` validates column *names* only, and the read-time
    ``_band_pct_valid()`` check inspects only the 7 band percentages — so a NaN
    ``lufs`` reads back as "valid" forever.

    The Rust layer cannot catch this on its own: ``estimate_lufs()``'s silence
    early-return is ``if rms < 1e-10``, and ``NaN < 1e-10`` is false in
    IEEE-754, so NaN flows straight past it and ``.clamp(-120.0, 0.0)`` is a
    no-op on NaN (``vendor/auralis-dsp/src/dsp_math.rs:11-40``). This is the
    single choke point every producer converges on.

    Replace-and-warn rather than reject: it preserves the "always produce a
    fingerprint" contract every caller is written against, so a poisoned file
    degrades to a comparable-but-wrong row that is logged, rather than
    retry-looping forever in ``FingerprintExtractionQueue``.
    """
    replaced: list[str] = []
    for key, value in fingerprint.items():
        if not isinstance(value, (int, float, np.number)) or isinstance(value, bool):
            continue
        try:
            if not math.isfinite(float(value)):
                fingerprint[key] = 0.0
                replaced.append(key)
        except (TypeError, ValueError, OverflowError):
            # Non-coercible values are not fingerprint dimensions; leave them
            # for the completeness/schema checks to reject.
            continue

    if replaced:
        logger.warning(
            f"Fingerprint for {label} contained {len(replaced)} non-finite "
            f"dimension(s), replaced with 0.0: {sorted(replaced)}. "
            f"Check the source file and the contributing analyzers."
        )
    return replaced


def _numpy_to_python(obj: Any) -> Any:
    """Recursively convert NumPy types to native Python types.

    #3765: NumPy types outside the handled set fail loud rather than passing
    through verbatim and silently breaking JSON serialisation downstream.
    """
    if isinstance(obj, dict):
        return {k: _numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_numpy_to_python(v) for v in obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    elif isinstance(obj, np.generic):
        raise TypeError(
            f"Cannot serialise NumPy type {type(obj).__name__}; "
            f"add an explicit branch to _numpy_to_python()."
        )
    return obj


def compute_windowed_fingerprint(
    analyzer: Any,
    audio_path: Path,
    audio: np.ndarray | None = None,
    sr: int | None = None
) -> dict[str, Any] | None:
    """Compute fingerprint using AudioFingerprintAnalyzer."""
    try:
        import librosa

        # Load audio if not provided.
        # Use 22050 Hz (librosa's native analysis rate) to halve data for 44.1 kHz files.
        # Cap at 90 s — sufficient for a stable 25D fingerprint with the sampling strategy.
        #
        # Multi-window fingerprinting strategy (empirically validated June 2026):
        #
        # Loading only a single 90 s window from the track creates a systematic
        # negative LUFS bias when that window lands on an ambient/instrumental intro.
        # Validation study (34 tracks) showed single-window RMSE vs actual LUFS =
        # 1.96 dB, max error = 9.2 dB (Gilmour Shine On: -23.5 vs -14.3 LUFS).
        #
        # Fix: run the full 25D analysis on the BODY window (50 % of track duration),
        # then probe two additional 30 s windows at 25 % and 75 %. Replace fp['lufs']
        # and fp['crest_db'] with the median across all three probes.
        # Result: RMSE drops to 1.07 dB (-45 %), max error to 3.6 dB (-61 %).
        #
        # The body window (50 %) is used for the full spectral analysis because
        # it is most likely to represent the track's timbral character.  The 25 %
        # and 75 % probes are mono + fast — no full 25D analysis needed.
        _target_sr = 22050
        _probe_s   = 30.0   # length of each lightweight probe window
        _body_s    = 90.0   # length of the full-analysis (body) window

        if audio is None or sr is None:
            # Get total duration without loading audio
            try:
                import soundfile as _sf
                with _sf.SoundFile(str(audio_path)) as _f:
                    _total_s = len(_f) / _f.samplerate
            except Exception:
                _total_s = None

            # Body window: centred on 50 % of track duration
            if _total_s is not None:
                _body_offset = min(_total_s * 0.50, max(0.0, _total_s - _body_s))
            else:
                _body_offset = 0.0

            from auralis.io.formats import FFMPEG_FORMATS
            if audio_path.suffix.lower() in FFMPEG_FORMATS:
                # libsndfile can't decode AAC/MP3/etc — load via ffmpeg.
                #
                # #5110: decode only the windows actually analysed. This branch
                # used to decode the ENTIRE file, resample the ENTIRE buffer,
                # and only then crop to 150 s — the opposite of the two sibling
                # branches (the libsndfile one seeks via librosa.load's
                # offset/duration; the pre-loaded one crops before resampling,
                # with a docstring about avoiding full-duration allocation). For
                # a 2-hour podcast that was up to ~50x the necessary CPU with a
                # peak footprint in the GB range, multiplied by the extraction
                # queue's concurrency. It also made
                # fingerprint_extractor.py's claim that this function "never
                # materialises the whole decoded file" false for exactly the
                # formats most libraries are made of.
                from auralis.io.loaders import load_with_ffmpeg
                from auralis.io.loaders.ffmpeg_loader import _probe_audio
                import tempfile

                def _decode_window(
                    tmp_dir: str, offset_s: float | None, dur_s: float | None
                ) -> np.ndarray:
                    """Decode one bounded span and return it as (channels, samples).

                    Decodes _SEEK_PREROLL_S ahead of the window and trims it off
                    by exact sample count. A bounded MP3/AAC decode starting
                    cold at the seek point differs from the same span of a full
                    decode — the codec needs a few frames to converge (bit
                    reservoir, filterbank state). Measured on a real MP3, a
                    zero-pre-roll window drifted up to 1.1% on crest_db and
                    ~1% on transient_density; with 0.5 s of pre-roll the samples
                    are bit-identical to the full-decode span.

                    That is what keeps this a pure performance change: stored
                    fingerprints stay comparable with newly computed ones, so no
                    FINGERPRINT_ALGORITHM_VERSION bump (and no library-wide
                    re-fingerprint) is required.
                    """
                    preroll = 0.0
                    if offset_s is not None and offset_s > 0:
                        preroll = min(_SEEK_PREROLL_S, offset_s)
                        offset_s = offset_s - preroll
                        if dur_s is not None:
                            dur_s = dur_s + preroll

                    win, win_sr = load_with_ffmpeg(
                        audio_path, tmp_dir, offset=offset_s, duration=dur_s
                    )
                    # Trim at the NATIVE rate, before resampling — resampling
                    # would make the sample count no longer map to preroll.
                    if preroll > 0:
                        win = win[int(round(preroll * win_sr)):]
                    if win.ndim == 2:
                        win = win.T
                    if win_sr != _target_sr:
                        if win.ndim == 2:
                            win = np.stack([
                                librosa.resample(
                                    win[ch].astype(np.float32),
                                    orig_sr=win_sr, target_sr=_target_sr,
                                )
                                for ch in range(win.shape[0])
                            ])
                        else:
                            win = librosa.resample(
                                win.astype(np.float32),
                                orig_sr=win_sr, target_sr=_target_sr,
                            )
                    return win

                # Duration from ffprobe rather than from a decoded buffer — the
                # window offsets need it *before* anything is decoded, and the
                # soundfile probe above cannot open these containers.
                _probe = _probe_audio(audio_path)
                _total_s = _probe.get('duration')

                with tempfile.TemporaryDirectory() as tmp:
                    if not _total_s or _total_s <= 0:
                        # ffprobe gave no duration (rare: true-VBR without a
                        # header). Fall back to decoding from the start and
                        # bounding by length — still avoids the full file.
                        logger.debug(
                            f"No probed duration for {audio_path.name}; "
                            f"decoding a bounded head window instead"
                        )
                        audio = _decode_window(tmp, None, _body_s)
                        _probe_audios = []
                    else:
                        _body_offset = min(
                            _total_s * 0.50, max(0.0, _total_s - _body_s)
                        )
                        audio = _decode_window(tmp, _body_offset, _body_s)
                        # Lightweight LUFS/crest probes at 25 % and 75 %
                        _probe_audios = [
                            _decode_window(
                                tmp,
                                min(_frac * _total_s, max(0.0, _total_s - _probe_s)),
                                _probe_s,
                            )
                            for _frac in (0.25, 0.75)
                        ]

                # Rounding safety at the target rate (works for 1-D and 2-D).
                audio = audio[..., :int(_target_sr * _body_s)]
                sr = _target_sr
            else:
                audio, sr = librosa.load(
                    str(audio_path), sr=_target_sr, mono=False,
                    offset=_body_offset, duration=_body_s,
                )
                sr = int(sr)
                # Lightweight probes: mono is sufficient for LUFS/crest estimation
                _probe_audios = []
                if _total_s is not None:
                    for _frac in [0.25, 0.75]:
                        _poff = min(_frac * _total_s, max(0.0, _total_s - _probe_s))
                        try:
                            _pa, _ = librosa.load(
                                str(audio_path), sr=_target_sr, mono=True,
                                offset=_poff, duration=_probe_s,
                            )
                            _probe_audios.append(_pa)
                        except Exception:
                            pass
        else:
            # #4994: share the exact body+probe windowing strategy the
            # fresh-load branch above uses, instead of the less-accurate
            # start-crop + no correction this branch used to do — the two
            # branches disagreeing defeated #4595's "cannot drift again"
            # guarantee for any future caller that passes pre-loaded audio.
            _orig_sr = sr
            _raw_audio = audio
            _total_s = _raw_audio.shape[-1] / _orig_sr

            def _crop_and_resample(buf: np.ndarray, offset_s: float, dur_s: float) -> np.ndarray:
                """Crop [offset_s, offset_s + dur_s) at the ORIGINAL sample
                rate, then resample to _target_sr. Crop-before-resample
                avoids an O(duration) resample + full-duration float32
                allocation on a multi-hour buffer — the same #4116/#4499
                OOM/latency class the old start-crop-only code avoided."""
                start = int(_orig_sr * offset_s)
                end = start + int(_orig_sr * dur_s)
                cropped = buf[..., start:end]
                if _orig_sr == _target_sr:
                    return cropped
                if cropped.ndim == 1:
                    return librosa.resample(cropped.astype(np.float32), orig_sr=_orig_sr, target_sr=_target_sr)
                return np.stack([
                    librosa.resample(cropped[ch].astype(np.float32), orig_sr=_orig_sr, target_sr=_target_sr)
                    for ch in range(cropped.shape[0])
                ])

            # Body window: centred on 50 % of duration, same as fresh-load.
            _body_offset = min(_total_s * 0.50, max(0.0, _total_s - _body_s))
            audio = _crop_and_resample(_raw_audio, _body_offset, _body_s)
            sr = _target_sr
            # Rounding safety at the target rate (works for 1-D and 2-D).
            audio = audio[..., :int(_target_sr * _body_s)]

            # Lightweight LUFS/crest probes at 25 % / 75 %, cropped from the
            # same pre-loaded buffer — feeds the multi-window correction
            # below exactly like the fresh-load branch's _probe_audios.
            _probe_audios = []
            for _frac in [0.25, 0.75]:
                _poff = min(_frac * _total_s, max(0.0, _total_s - _probe_s))
                _probe_audios.append(_crop_and_resample(_raw_audio, _poff, _probe_s))

        # Ensure float64 for PyO3 compatibility
        audio = audio.astype(np.float64)

        # Downmix >2-channel audio to stereo before fingerprinting.
        # librosa.load(mono=False) returns (channels, samples) for any channel count.
        # The fingerprint analyzer only handles mono/stereo — its shape-detection
        # heuristic (shape[0] <= 2 → channels-first) misclassifies a 6-ch array
        # as having 6 samples, causing a false "too short" rejection.
        # Taking the first two channels (L+R) is sufficient for timbral analysis;
        # the C/Ls/Rs channels are correlated with L+R in well-mixed surround content.
        if audio.ndim == 2 and audio.shape[0] > 2:
            audio = audio[:2, :]

        # Compute fingerprint from the body window
        fingerprint = analyzer.analyze(audio, sr)

        # Multi-window LUFS/crest correction — replace the body-window
        # estimates with the median across the body + two probe windows.
        # Validated empirically: reduces LUFS RMSE from 1.96 → 1.07 dB,
        # max error from 9.2 → 3.6 dB (June 2026 study, 31 tracks).
        try:
            if '_probe_audios' in dir() and _probe_audios and fingerprint:
                def _rms_lufs_crest(a: np.ndarray) -> tuple[float, float]:
                    """Return (lufs_approx, crest_db) from a mono/stereo array."""
                    mono = np.mean(a, axis=0) if a.ndim == 2 else a
                    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
                    if rms < 1e-9:
                        return -70.0, 0.0
                    peak = float(np.max(np.abs(mono)))
                    lufs = 20.0 * np.log10(rms) - 0.691   # K-weighted proxy
                    crest = 20.0 * np.log10(peak / max(rms, 1e-9))
                    return lufs, crest

                # Body window (already analyzed)
                lufs_body, crest_body = _rms_lufs_crest(audio.astype(np.float64))
                all_lufs  = [lufs_body]
                all_crest = [crest_body]

                for _pa in _probe_audios:
                    _pl, _pc = _rms_lufs_crest(_pa.astype(np.float64))
                    if _pl > -70.0:   # skip silent probes
                        all_lufs.append(_pl)
                        all_crest.append(_pc)

                if len(all_lufs) >= 2:
                    fingerprint['lufs']     = float(np.median(all_lufs))
                    fingerprint['crest_db'] = float(np.median(all_crest))
        except Exception:
            pass   # multi-window correction is best-effort; body window is fine

        # #3767: validate completeness before returning. `analyze()`
        # returns {} from its outer except-all on any exception
        # (audio_fingerprint_analyzer.py:314). The downstream
        # `get_or_compute` check `if fingerprint:` already skips
        # empty dicts (so they don't reach the cache), but an
        # incomplete fingerprint (e.g., 12 of 25 dimensions) would
        # be truthy and get cached as if valid. The official
        # fingerprint dimensionality is 25; anything less is a
        # partial result that should be re-tried, not cached.
        if fingerprint and len(fingerprint) < 25:
            logger.warning(
                f"Incomplete fingerprint for {audio_path.name}: "
                f"{len(fingerprint)} of 25 dimensions present — discarding"
            )
            return None

        # #5103: last guard before the value leaves this function. Every
        # persistence path — the DB row via _prepare_for_storage/upsert, the
        # .25d sidecar, and mastering-target selection — converges here, and
        # none of them re-check finiteness downstream.
        if fingerprint:
            _sanitize_non_finite(fingerprint, audio_path.name)

        # Convert numpy types to JSON-safe Python types
        fingerprint_clean: dict[str, Any] = _numpy_to_python(fingerprint)

        return fingerprint_clean

    except Exception as e:
        logger.error(f"Fingerprint computation failed: {e}")
        return None
