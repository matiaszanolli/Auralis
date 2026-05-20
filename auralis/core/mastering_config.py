"""
Simple Mastering Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration constants for SimpleMasteringPipeline.

Centralizes all magic numbers for easier tuning and A/B testing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


@dataclass
class SimpleMasteringConfig:
    """
    Configuration constants for SimpleMasteringPipeline.

    This class consolidates all tuning parameters previously scattered
    as magic numbers throughout simple_mastering.py. Centralizing these
    values enables:
    - Easy A/B testing (swap config instances)
    - Single source of truth for tuning
    - Semantic names for better documentation
    - User-configurable presets in future

    All values are derived from the original simple_mastering.py implementation.
    """

    # =========================================================================
    # Target Loudness
    # =========================================================================

    TARGET_LUFS: float = -11.0
    """Target loudness for normalized output (LUFS)"""

    # =========================================================================
    # Chunked Processing
    # =========================================================================

    CHUNK_DURATION_SEC: int = 30
    """Duration of each processing chunk in seconds"""

    CROSSFADE_DURATION_SEC: float = 3.0
    """Duration of crossfade between chunks in seconds"""

    # =========================================================================
    # Material Classification Thresholds
    # =========================================================================

    COMPRESSED_LOUD_THRESHOLD_LUFS: float = -12.0
    """LUFS threshold for loud material classification"""

    HYPER_COMPRESSED_THRESHOLD_CREST: float = 8.0
    """Crest factor threshold for hyper-compressed material (skip expansion)"""

    MODERATE_COMPRESSED_MIN_CREST: float = 13.0
    """Crest factor threshold for moderate compression (apply gentle expansion)"""

    # =========================================================================
    # Pre-EQ Headroom
    # =========================================================================

    PRE_EQ_HEADROOM_DB: float = -2.0
    """Headroom reserved before EQ boosts to prevent limiter clipping"""

    # =========================================================================
    # Enhancement Frequencies (Hz)
    # =========================================================================

    BASS_SHELF_HZ: float = 100.0
    """Low-shelf frequency for bass enhancement"""

    SUB_BASS_CUTOFF_HZ: float = 60.0
    """Cutoff frequency for sub-bass control"""

    MID_BODY_LOW_HZ: float = 200.0
    """Lower bound for mid-range body enhancement"""

    MID_BODY_HIGH_HZ: float = 2000.0
    """Upper bound for mid-range body enhancement"""

    PRESENCE_LOW_HZ: float = 2000.0
    """Lower bound for presence enhancement"""

    PRESENCE_HIGH_HZ: float = 8000.0
    """Upper bound for presence enhancement"""

    AIR_SHELF_HZ: float = 8000.0
    """High-shelf frequency for air enhancement"""

    # =========================================================================
    # Adaptive Soft Clipping Curve Parameters
    # =========================================================================

    HARMONIC_PRESERVATION_THRESHOLD: float = 0.6
    """Harmonic ratio threshold for preserving harmonic content in soft clipping"""

    VARIATION_PRESERVATION_THRESHOLD: float = 0.5
    """Dynamic variation threshold for preserving variation in soft clipping"""

    FLATNESS_PRESERVATION_THRESHOLD: float = 0.6
    """Spectral flatness threshold for preserving flatness in soft clipping"""

    # =========================================================================
    # Peak Reduction Safety Margins
    # =========================================================================

    PEAK_REDUCTION_THRESHOLD_DB: float = -0.5
    """Peak threshold above which gentle reduction is applied"""

    MAX_TARGET_PEAK_REDUCTION_DB: float = -2.0
    """Maximum target peak after reduction (floor)"""

    PEAK_CLIP_SEVERITY_RANGE_DB: float = 2.5
    """Range for calculating clip severity (from threshold to max severity)"""

    # =========================================================================
    # Intensity Multipliers (per branch)
    # =========================================================================

    COMPRESSED_LOUD_INTENSITY_FACTOR: float = 0.7
    """Intensity multiplier for presence/air in compressed loud branch"""

    DYNAMIC_LOUD_INTENSITY_FACTOR: float = 0.5
    """Intensity multiplier for presence/air in dynamic loud branch"""

    QUIET_INTENSITY_FACTOR: float = 1.0
    """Intensity multiplier for presence/air in quiet branch"""

    # =========================================================================
    # RMS Expansion Parameters
    # =========================================================================

    MAX_TARGET_CREST_INCREASE_DB: float = 2.0
    """Maximum crest factor increase for RMS reduction expansion"""

    RMS_EXPANSION_AMOUNT: float = 0.5
    """Conservative expansion amount for RMS reduction"""

    # =========================================================================
    # Soft Clipping Curve Parameters (Quiet Branch)
    # =========================================================================

    SOFT_CLIP_BASE_KNEE: float = 0.6
    """Base knee position for soft clipping curve"""

    SOFT_CLIP_BASE_THRESHOLD: float = 0.4
    """Base threshold position for soft clipping curve"""

    # =========================================================================
    # Enhancement Boost Limits
    # =========================================================================

    MAX_BASS_BOOST_DB: float = 2.0
    """Maximum bass enhancement boost"""

    MAX_SUB_BASS_CUT_DB: float = -1.0
    """Maximum sub-bass cut (negative boost)"""

    MAX_MID_BOOST_DB: float = 1.5
    """Maximum mid warmth boost"""

    MAX_PRESENCE_BOOST_DB: float = 2.0
    """Maximum presence boost"""

    MAX_AIR_BOOST_DB: float = 2.5
    """Maximum air enhancement boost"""

    # =========================================================================
    # Harmonic Exciter
    # =========================================================================
    # Generates upper-octave harmonics from midrange for bandwidth-limited /
    # dark sources where shelf EQ has nothing to lift (e.g. low-bitrate audio
    # that has been brick-walled below 8 kHz). Disabled for material that
    # already has natural high-frequency content.

    EXCITER_DONOR_LOW_HZ: float = 1000.0
    """Lower bound of donor bandpass for harmonic generation"""

    EXCITER_DONOR_HIGH_HZ: float = 5500.0
    """Upper bound of donor bandpass. Wider donor → harmonics reach further up
    the spectrum (3rd harmonic of 5.5 kHz lands in air). Pulling this above
    the HP cutoff is intentional — the HP still rejects the original donor band,
    only the *newly generated* harmonics pass through to mix with dry."""

    EXCITER_HP_CUTOFF_HZ: float = 4500.0
    """High-pass on saturated signal — keeps only newly generated harmonics"""

    EXCITER_DRIVE_DB: float = 15.0
    """Pre-gain into the saturator. Higher = richer harmonics + more IMD"""

    EXCITER_ASYMMETRY: float = 0.3
    """Saturator bias (0 = odd harmonics only; 0.3 adds tube-like even harmonics)"""

    EXCITER_MAX_WET_DB: float = -6.0
    """Wet ceiling (parallel mix). -6 dB ≈ 50% wet for fully-dark material at
    intensity 1.0; -12 dB ≈ 25% wet. Used as the *ceiling* of a darkness-scaled
    ramp, so bright material stays gentle while dark/bandwidth-limited sources
    get a real lift."""

    EXCITER_MIN_WET_DB: float = -18.0
    """Wet floor at the activation threshold (just-barely-dark material)."""

    EXCITER_DARKNESS_ACTIVATE: float = 0.55
    """Darkness threshold below which exciter is bypassed. Computed from
    presence_pct + air_pct + spectral_rolloff. 0 = fully dark, 1 = fully bright"""

    # =========================================================================
    # Progress Reporting
    # =========================================================================

    PROGRESS_REPORT_INTERVAL_CHUNKS: int = 5
    """Report progress every N chunks during processing"""
