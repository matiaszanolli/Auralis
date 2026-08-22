"""
Simple Mastering Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration constants for SimpleMasteringPipeline.

Centralizes all magic numbers for easier tuning and A/B testing.

The specialized correction-stage tuning tables (resonance notcher, transient
shaper, clarity boost, vocal unmasking, sub-bass control, continuous
loudness/crest response, progress reporting) live in ``mastering_presets.py``
(#4511) and are pulled in via inheritance below, so ``SimpleMasteringConfig``
still exposes every field as a single flat, backward-compatible attribute
namespace.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass

from .mastering_presets import MasteringPresetDefaults

__all__ = ["SimpleMasteringConfig", "MasteringPresetDefaults"]


@dataclass
class SimpleMasteringConfig(MasteringPresetDefaults):
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

    Inherits the specialized correction-stage tuning tables (resonance
    notcher, transient shaper, clarity boost, vocal unmasking, sub-bass
    control, continuous loudness/crest response, progress reporting) from
    :class:`~auralis.core.mastering_presets.MasteringPresetDefaults`
    (#4511) — every field from both classes is a plain flat attribute here,
    so ``SimpleMasteringConfig()`` behaves exactly as it did as one module.
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

    QUALITY_EVALUATION_ENABLED: bool = True
    """Attach advisory before/after measurements to file-master results."""

    QUALITY_EVALUATION_WINDOW_SEC: float = 8.0
    """Duration of each evenly distributed quality-evaluation window."""

    QUALITY_EVALUATION_WINDOW_COUNT: int = 5
    """Number of source/output windows included in the measurement."""

    # =========================================================================
    # Pre-EQ Headroom
    # =========================================================================

    PRE_EQ_HEADROOM_DB: float = -2.0
    """Headroom reserved before EQ boosts to prevent limiter clipping"""

    # =========================================================================
    # Enhancement Frequencies (Hz)
    # =========================================================================

    BASS_SHELF_HZ: float = 120.0
    """Low-shelf corner for continuous bass balance and counterweight."""

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

    MAX_BASS_BALANCE_DB: float = 1.0
    """Asymptotic signed low-shelf correction around the corpus bass median."""

    BASS_BALANCE_SCALE_PCT: float = 0.1609933274688325
    """Robust IQR-derived bass-share scale measured over 508 sources."""

    MAX_BASS_COUNTERWEIGHT_DB: float = 0.8
    """Maximum extra low-shelf weight for strongly bright-leaning sources."""

    BASS_TILT_LOG_MEDIAN: float = -1.370043455149401
    """Median log((upper-mid + presence) / bass), measured over 508 sources."""

    BASS_TILT_LOG_SCALE: float = 0.8176371745003234
    """Robust IQR-derived scale of the 508-source high-to-bass log ratio."""

    BASS_TILT_EPSILON: float = 1e-6
    """Numerical stabilizer for the high-to-bass log ratio."""

    BASS_COUNTERWEIGHT_CENTER_Z: float = 0.75
    """Smooth-response center in robust corpus deviations above the median."""

    BASS_COUNTERWEIGHT_WIDTH_Z: float = 0.75
    """Width of the continuous counterweight response in robust deviations."""

    BASS_TARGET_PCT: float = 0.4560661315917969
    """Median bass share measured over the deterministic 508-source corpus."""

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
    # Generates upper-octave harmonics from midrange for bandwidth-limited
    # sources where shelf EQ has nothing to lift (e.g. low-bitrate audio that
    # has been brick-walled below 8 kHz). The wet level follows the continuous,
    # corpus-calibrated spectral response; no source threshold activates it.

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

    EXCITER_MAX_WET_DB: float = -12.0
    """Wet ceiling before continuous intensity/spectral-need attenuation."""

    EXCITER_MIN_WET_DB: float = -21.0
    """Wet base at the smallest spectral-need values."""

    EXCITER_CASCADE_ENABLED: bool = True
    """Run a second-pass exciter on Stage 1's output. Stage 1 generates
    harmonics 4-8 kHz from the 1-5.5 kHz donor. Stage 2 uses those new
    4-8 kHz harmonics as its donor to generate further harmonics in
    8-16 kHz, extending the 'brightness' across the full upper spectrum
    instead of concentrating it in 4-7 kHz. Empirically lifts Brilliance
    (8-12 kHz) by +3 dB on very dark sources where a single pass barely
    reaches above 8 kHz."""

    EXCITER_CASCADE_DONOR_LOW_HZ: float = 3000.0
    """Lower bound of cascade donor (overlaps with Stage 1's output range)."""

    EXCITER_CASCADE_DONOR_HIGH_HZ: float = 8000.0
    """Upper bound of cascade donor — the post-Stage-1 region with new content."""

    EXCITER_CASCADE_HP_CUTOFF_HZ: float = 8000.0
    """High-pass on Stage 2 — keep only the newly-newly-generated harmonics
    (above the cascade donor band)."""

    EXCITER_CASCADE_DRIVE_DB: float = 12.0
    """Stage 2 drive. Slightly less than Stage 1 because the donor is already
    saturated content; less drive = lower-order harmonics = cleaner sound."""

    EXCITER_CASCADE_WET_OFFSET_DB: float = -3.0
    """Stage 2 wet is computed as Stage 1 wet + this offset. The cascade
    is a secondary effect and should be quieter than the primary stage."""
