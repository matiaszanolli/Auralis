"""Harmonic Exciter Stage — generate upper-octave harmonics when HF is sparse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from ..dsp import HarmonicExciter
from . import no_op

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
    config: SimpleMasteringConfig,
    hf_lift: float = 1.0,
) -> tuple[np.ndarray, dict[str, Any] | None]:
    """Generate upper-octave harmonics with a continuous corpus-calibrated mix.

    Shelf EQ can only amplify what already exists. For lo-fi captures or
    low-bitrate audio where everything above ~6 kHz has been brick-walled,
    this stage saturates a midrange donor band and high-passes the result,
    mixing the newly generated harmonics in parallel.

    ``hf_lift`` is the shared continuous spectral-need coordinate. It scales the
    wet signal in linear amplitude, so a value approaching zero really does
    approach the dry signal. Scaling a negative dB value by intensity would do
    the opposite: lower intensity would make the wet level *less* negative and
    therefore louder.

    Args:
        audio: Audio array [channels, samples]
        presence_pct: Retained for the stable stage-call interface.
        air_pct: Retained for the stable stage-call interface.
        spectral_rolloff: Retained for the stable stage-call interface.
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for exciter constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if exciter did not engage
    """
    del presence_pct, air_pct, spectral_rolloff

    intensity = float(np.clip(intensity, 0.0, 1.0))
    spectral_need = float(np.clip(hf_lift, 0.0, 1.0))
    wet_mix = intensity * spectral_need
    if wet_mix <= np.finfo(np.float64).eps:
        return no_op(audio)

    base_wet_db = (
        config.EXCITER_MIN_WET_DB
        + (config.EXCITER_MAX_WET_DB - config.EXCITER_MIN_WET_DB)
        * spectral_need
    )
    wet_db = base_wet_db + 20.0 * np.log10(wet_mix)
    drive_db = config.EXCITER_DRIVE_DB * (0.7 + 0.3 * spectral_need)

    # Mirror HarmonicExciter.apply()'s own bypass conditions here so a stage
    # that will do nothing reports it honestly via no_op() (stage_info=None)
    # instead of returning a stage_info dict claiming wet_db/drive_db applied
    # when the exciter never ran (#4900). The eps guard above only rejects
    # wet_mix <= 0; any wet_mix below ~1e-3 still lands wet_db <= -60 here.
    if wet_db <= -60.0:
        return no_op(audio)
    nyquist = sample_rate / 2.0
    low_norm = min(0.99, max(0.01, config.EXCITER_DONOR_LOW_HZ / nyquist))
    high_norm = min(0.99, max(0.01, config.EXCITER_DONOR_HIGH_HZ / nyquist))
    if low_norm >= high_norm:
        # Degenerate donor band (e.g. very low sample rate) — no exciter possible.
        return no_op(audio)

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
            f"{drive_db:.1f} dB drive (spectral need {spectral_need:.2f})"
            f"{cascade_msg}"
        )

    return processed, {
        'stage': 'harmonic_exciter',
        'wet_db': wet_db,
        'drive_db': drive_db,
        'spectral_need': spectral_need,
    }
