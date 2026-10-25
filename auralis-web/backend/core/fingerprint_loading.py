"""
Fingerprint acquisition tiers (split from mastering_target_service.py, #5833):
database record, ``.25d`` sidecar, and extraction from audio. The service owns
the cache and the tier ordering; these functions only fetch.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint import AudioFingerprintAnalyzer, FingerprintStorage
from auralis.analysis.fingerprint.windows import FINGERPRINT_SAMPLE_RATE
from auralis.analysis.mastering_fingerprint import MasteringFingerprint
from mutagen import File as MutagenFile  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

# Maps a fingerprint (record, dict or MasteringFingerprint) to mastering targets.
TargetDeriver = Callable[[Any], dict[str, Any]]


def probe_file_properties(filepath: str) -> tuple[float, int]:
    """Cheap (duration_s, sample_rate) from a soundfile header read — no decode.

    The windowed fingerprint pipeline never materialises the full audio, so
    there is no decoded buffer to divide for the old len(audio)/sr fallback.
    FFmpeg-only formats (m4a/aac/wma) fail the header read and get
    (0.0, FINGERPRINT_SAMPLE_RATE); the windowed analysis itself decodes those independently.
    """
    try:
        import soundfile as sf
        with sf.SoundFile(str(filepath)) as f:
            return f.frames / f.samplerate, int(f.samplerate)
    except Exception:
        return 0.0, FINGERPRINT_SAMPLE_RATE


def load_from_database(
    get_fingerprints_repository: Callable[[], Any] | None,
    track_id: int,
) -> Any | None:
    """
    Load fingerprint from database (Tier 1 - fastest).

    Consolidates logic from chunked_processor._load_fingerprint_from_database().

    Args:
        get_fingerprints_repository: Returns the fingerprints repository, or
            None when none was wired (the lookup is skipped)
        track_id: Track ID to look up

    Returns:
        MasteringFingerprint instance or None if not found
    """
    # Require repository factory (dependency injection pattern)
    if get_fingerprints_repository is None:
        logger.debug("No fingerprints repository provided - skipping database lookup")
        return None

    try:
        # Get repository via dependency injection
        fingerprints_repo = get_fingerprints_repository()

        # Try to get fingerprint from database
        fp_record = fingerprints_repo.get_by_track_id(track_id)

        if fp_record:
            # Convert database record to MasteringFingerprint
            fp_dict = {
                'sub_bass_pct': fp_record.sub_bass_pct,
                'bass_pct': fp_record.bass_pct,
                'low_mid_pct': fp_record.low_mid_pct,
                'mid_pct': fp_record.mid_pct,
                'upper_mid_pct': fp_record.upper_mid_pct,
                'presence_pct': fp_record.presence_pct,
                'air_pct': fp_record.air_pct,
                'lufs': fp_record.lufs,
                'crest_db': fp_record.crest_db,
                'bass_mid_ratio': fp_record.bass_mid_ratio,
                'tempo_bpm': fp_record.tempo_bpm,
                'rhythm_stability': fp_record.rhythm_stability,
                'transient_density': fp_record.transient_density,
                'silence_ratio': fp_record.silence_ratio,
                'spectral_centroid': fp_record.spectral_centroid,
                'spectral_rolloff': fp_record.spectral_rolloff,
                'spectral_flatness': fp_record.spectral_flatness,
                'harmonic_ratio': fp_record.harmonic_ratio,
                'pitch_stability': fp_record.pitch_stability,
                'chroma_energy': fp_record.chroma_energy,
                'dynamic_range_variation': fp_record.dynamic_range_variation,
                'loudness_variation_std': fp_record.loudness_variation_std,
                'peak_consistency': fp_record.peak_consistency,
                'stereo_width': fp_record.stereo_width,
                'phase_correlation': fp_record.phase_correlation,
            }

            fingerprint = MasteringFingerprint(**fp_dict)
            logger.info(
                f"✅ Loaded fingerprint from database for track {track_id} "
                f"(LUFS: {fp_record.lufs:.1f}, Crest: {fp_record.crest_db:.1f})"
            )
            return fingerprint
        else:
            logger.debug(f"No fingerprint in database for track {track_id}")
            return None

    except Exception as e:
        logger.debug(f"Database fingerprint lookup failed for track {track_id}: {e}")
        return None


def load_from_file(
    filepath: str,
    derive_targets: TargetDeriver,
) -> tuple[Any, dict[str, Any] | None] | None:
    """
    Load fingerprint from .25d file (Tier 2 - fast).

    Args:
        filepath: Path to audio file (will look for .25d sidecar)
        derive_targets: Re-derives the mastering targets from the fingerprint

    Returns:
        Tuple of (fingerprint, mastering_targets) or None if not found
    """
    try:
        cached_data = FingerprintStorage.load(Path(filepath))
        if cached_data:
            fingerprint, mastering_targets = cached_data
            # Old-algorithm sidecars never reach here: FingerprintStorage.load
            # itself rejects a missing/old fingerprint_version stamp (#5697),
            # the one shared rule — this private copy of the check drifted
            # from the engine's tier-2 loader, which had none at all.
            # Targets are a pure function of the fingerprint, so re-derive them
            # rather than trusting the persisted copy. Sidecars written before
            # #5554 hold EQ targets computed with percent-scaled ideals (every
            # band saturated at the clamp), and those written before #5552
            # lack source_lufs. An empty dict means "not derived yet" and is
            # left for callers to fill.
            if mastering_targets and isinstance(fingerprint, dict):
                mastering_targets = derive_targets(fingerprint)
            logger.info(f"✅ Loaded fingerprint from .25d file for {Path(filepath).name}")
            return (fingerprint, mastering_targets)
        else:
            logger.debug(f"No .25d file found for {Path(filepath).name}")
            return None

    except Exception as e:
        logger.debug(f".25d file loading failed for {filepath}: {e}")
        return None


def extract_from_audio(
    filepath: str,
    derive_targets: TargetDeriver,
    save_to_file: bool = True,
) -> tuple[Any, dict[str, Any] | None] | None:
    """
    Extract fingerprint from audio file (Tier 3 - slow).

    Runs the shared windowed pipeline (compute_windowed_fingerprint):
    bounded 90s-body + 2x30s-probe decoding, #4595 LUFS/crest bias
    correction, and non-finite sanitization — identical to the batch
    library-scan fingerprint for the same file.

    Args:
        filepath: Path to audio file
        derive_targets: Derives the mastering targets from the fingerprint
        save_to_file: If True, save extracted fingerprint to .25d file

    Returns:
        Tuple of (fingerprint, mastering_targets) or None if extraction fails
    """
    try:
        logger.info(f"🔍 Extracting fingerprint from audio: {Path(filepath).name}")

        # Shared windowed pipeline (#5531): bounded 90s-body + 2x30s-probe
        # loading (no full-file decode of a multi-hour file), the #4595
        # body+probe LUFS/crest bias correction, and sanitize_non_finite
        # (via AudioFingerprintAnalyzer.analyze). The two fingerprint
        # producers used to call the raw Rust schema glue on a full-file
        # decode here — unsanitized, uncapped, and disagreeing with the
        # batch-scan fingerprint of the same track.
        from auralis.analysis.fingerprint.windowed_compute import (
            compute_windowed_fingerprint,
        )

        fingerprint_data: dict[str, Any] | None = compute_windowed_fingerprint(
            AudioFingerprintAnalyzer(), Path(filepath)
        )
        if not fingerprint_data:
            logger.warning(f"Windowed fingerprint extraction failed for {Path(filepath).name}")
            return None
        logger.info(f"✅ Extracted windowed fingerprint for {Path(filepath).name}")

        # Add metadata for .25d file. Duration/sample rate come from a
        # cheap header read — the windowed pipeline never materialises
        # the full audio to compute them from a decoded buffer.
        duration_value, sr = probe_file_properties(filepath)
        try:
            audio_file = MutagenFile(filepath)
            if audio_file:
                duration_value = float(audio_file.info.length)
        except Exception as e:
            logger.debug(f"Mutagen duration probe failed, keeping header probe: {e}", exc_info=True)

        fingerprint_data['_metadata'] = {
            'duration': duration_value,
            'sample_rate': sr
        }
        # Stamp the algorithm version so a later algorithm change makes
        # load_fingerprint_from_file reject this sidecar (#5556).
        fingerprint_data['fingerprint_version'] = FINGERPRINT_ALGORITHM_VERSION

        # Generate mastering targets from fingerprint
        mastering_targets = derive_targets(fingerprint_data)

        # Save to .25d file if requested
        if save_to_file:
            FingerprintStorage.save(Path(filepath), fingerprint_data, mastering_targets)
            logger.info(f"💾 Saved fingerprint to .25d file for {Path(filepath).name}")

        return (fingerprint_data, mastering_targets)

    except Exception as e:
        logger.error(f"Fingerprint extraction failed for {filepath}: {e}")
        logger.debug(traceback.format_exc())
        return None
