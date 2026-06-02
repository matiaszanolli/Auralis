"""Harmonic Exciter Stage — generate upper-octave harmonics for dark sources."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import HarmonicExciter
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    presence_pct: float,
    air_pct: float,
    spectral_rolloff: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Generate upper-octave harmonics for dark / bandwidth-limited sources.

    Shelf EQ can only amplify what already exists. For lo-fi captures or
    low-bitrate audio where everything above ~6 kHz has been brick-walled,
    this stage saturates a midrange donor band and high-passes the result,
    mixing the newly generated harmonics in parallel.

    Activates only when the spectrum is genuinely dark — bright material is
    untouched. Optionally cascades a second exciter pass for very dark sources.

    Args:
        audio: Audio array [channels, samples]
        presence_pct: Fingerprint presence percentage (4-6 kHz, 0-1)
        air_pct: Fingerprint air percentage (6-20 kHz, 0-1)
        spectral_rolloff: Frequency below which most energy lies (0-1, normalized)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for exciter constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if exciter did not engage
    """
    # Brightness metric: weighted blend of HF energy and spectrum rolloff.
    # presence/air most diagnostic; rolloff only contributes above 60% Nyquist.
    rolloff_brightness = max(0.0, (spectral_rolloff - 0.60) / 0.40)
    brightness = float(np.clip(
        presence_pct * 2.0 + air_pct * 3.0 + rolloff_brightness * 0.4,
        0.0, 1.0,
    ))
    darkness = 1.0 - brightness

    activate_threshold = 1.0 - config.EXCITER_DARKNESS_ACTIVATE
    if darkness < activate_threshold:
        return audio.copy(), None

    excite_factor = SmoothCurveUtilities.ramp_to_s_curve(darkness, activate_threshold, 1.0)

    min_wet_db = config.EXCITER_MIN_WET_DB
    max_wet_db = config.EXCITER_MAX_WET_DB * intensity
    if max_wet_db < min_wet_db:
        max_wet_db = min_wet_db
    wet_db = min_wet_db + (max_wet_db - min_wet_db) * excite_factor

    drive_db = config.EXCITER_DRIVE_DB * (0.7 + 0.3 * excite_factor)

    processed = HarmonicExciter.apply(
        audio,
        sample_rate=sample_rate,
        wet_db=wet_db,
        drive_db=drive_db,
        donor_low_hz=config.EXCITER_DONOR_LOW_HZ,
        donor_high_hz=config.EXCITER_DONOR_HIGH_HZ,
        hp_cutoff_hz=config.EXCITER_HP_CUTOFF_HZ,
        asymmetry=config.EXCITER_ASYMMETRY,
    )

    # Cascade pass: Stage 1 harmonics (4-8 kHz) become donor for Stage 2,
    # pushing new harmonics into 8-16 kHz for broader brightness.
    cascade_wet_db = None
    if config.EXCITER_CASCADE_ENABLED:
        cascade_wet_db = wet_db + config.EXCITER_CASCADE_WET_OFFSET_DB
        processed = HarmonicExciter.apply(
            processed,
            sample_rate=sample_rate,
            wet_db=cascade_wet_db,
            drive_db=config.EXCITER_CASCADE_DRIVE_DB,
            donor_low_hz=config.EXCITER_CASCADE_DONOR_LOW_HZ,
            donor_high_hz=config.EXCITER_CASCADE_DONOR_HIGH_HZ,
            hp_cutoff_hz=config.EXCITER_CASCADE_HP_CUTOFF_HZ,
            asymmetry=config.EXCITER_ASYMMETRY,
        )

    if verbose:
        cascade_msg = (f", cascade {cascade_wet_db:+.1f} dB"
                       if cascade_wet_db is not None else "")
        print(
            f"   Harmonic exciter: {wet_db:+.1f} dB wet, "
            f"{drive_db:.1f} dB drive (darkness {darkness:.2f}){cascade_msg}"
        )

    return processed, {
        'stage': 'harmonic_exciter',
        'wet_db': wet_db,
        'drive_db': drive_db,
        'darkness': darkness,
    }
