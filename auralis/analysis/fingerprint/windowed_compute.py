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

Windowing strategy (validated June 2026, 34 tracks): full 25D analysis on the
BODY window at 50 % of duration, plus two lightweight 30 s probes at 25 % / 75 %;
`lufs` and `crest_db` are replaced with the median across all three.
Single-window LUFS RMSE 1.96 dB / max 9.2 dB → multi-window 1.07 dB / max 3.6 dB.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Frequency band keys that must sum to ~1.0 in a valid fingerprint.
_BAND_PCT_KEYS: tuple[str, ...] = (
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct',
)


def _band_pct_valid(fp: dict[str, Any]) -> bool:
    """Return True if the seven frequency-band fractions sum to 1 ± 0.05."""
    total = float(sum(fp.get(k, 0.0) for k in _BAND_PCT_KEYS))
    return 0.95 <= total <= 1.05


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
        if audio is None or sr is None:
            _target_sr = 22050
            _probe_s   = 30.0   # length of each lightweight probe window
            _body_s    = 90.0   # length of the full-analysis (body) window

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
                # libsndfile can't decode AAC/MP3/etc — load via ffmpeg then resample.
                from auralis.io.loaders import load_with_ffmpeg
                import tempfile, os
                with tempfile.TemporaryDirectory() as tmp:
                    raw_audio, raw_sr = load_with_ffmpeg(audio_path, tmp)
                # raw_audio is (samples, channels) or (samples,); convert to (channels, samples)
                if raw_audio.ndim == 2:
                    raw_audio = raw_audio.T
                if raw_sr != _target_sr:
                    if raw_audio.ndim == 2:
                        raw_audio = np.stack([
                            librosa.resample(raw_audio[ch].astype(np.float32), orig_sr=raw_sr, target_sr=_target_sr)
                            for ch in range(raw_audio.shape[0])
                        ])
                    else:
                        raw_audio = librosa.resample(raw_audio.astype(np.float32), orig_sr=raw_sr, target_sr=_target_sr)
                _total_s    = raw_audio.shape[-1] / _target_sr
                _body_offset = min(_total_s * 0.50, max(0.0, _total_s - _body_s))
                _body_start  = int(_target_sr * _body_offset)
                _body_end    = _body_start + int(_target_sr * _body_s)
                audio = raw_audio[..., _body_start:_body_end]
                # Lightweight LUFS/crest probes at 25 % and 75 %
                _probe_fracs = [0.25, 0.75]
                _probe_audios = []
                for _frac in _probe_fracs:
                    _ps = int(_target_sr * min(_frac * _total_s, max(0.0, _total_s - _probe_s)))
                    _pe = _ps + int(_target_sr * _probe_s)
                    _pa = raw_audio[..., _ps:_pe]
                    _probe_audios.append(_pa)
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
            # Normalize pre-loaded audio to match file-load parameters (#2457).
            # Ensures fingerprints are comparable regardless of loading path.
            _target_sr = 22050
            _max_samples = int(_target_sr * 90.0)
            # Crop to ~90 s at the ORIGINAL sample rate BEFORE resampling.
            # Resampling the whole buffer and cropping afterwards was an
            # O(duration) resample + full-duration float32 allocation on a
            # multi-hour pre-loaded buffer, only to discard all but the first
            # 90 s — reopening the #4116 OOM/latency class (#4499). This
            # matches the crop-then-resample order at every other entry point
            # (MasteringFingerprint.from_audio_file, AudioFingerprintAnalyzer).
            audio = audio[..., :int(sr * 90.0)]
            if sr != _target_sr:
                # Resample to target sr.
                if audio.ndim == 1:
                    audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=_target_sr)
                else:
                    audio = np.stack([
                        librosa.resample(audio[ch].astype(np.float32), orig_sr=sr, target_sr=_target_sr)
                        for ch in range(audio.shape[0])
                    ])
                sr = _target_sr
            # Final exact cap at 90 s in the target rate (rounding safety;
            # works for both 1-D and 2-D audio).
            audio = audio[..., :_max_samples]

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

        # Convert numpy types to JSON-safe Python types
        fingerprint_clean: dict[str, Any] = _numpy_to_python(fingerprint)

        return fingerprint_clean

    except Exception as e:
        logger.error(f"Fingerprint computation failed: {e}")
        return None
