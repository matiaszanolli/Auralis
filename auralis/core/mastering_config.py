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
    """Maximum bass enhancement boost (when bass content is well below target)"""

    MAX_BASS_CUT_DB: float = 2.0
    """Maximum bass de-mud cut (bell @ 150 Hz, when bass is well above target).
    Applied as a bell — not a shelf — so the kick fundamental and sub-bass are
    preserved while the muddy bass body (100-220 Hz) is tamed. Reduced from
    -3 dB because live folk/world recordings can legitimately have 50-60%
    bass; we want to gently tame mud, not fight the source's character."""

    # === EVIDENCE-BASED TOLERANCE BANDS (derived from n=27 reference set across 8 genres) ===
    # Philosophy: do nothing while the source sits inside a *natural variance band*
    # (p25-p75 across well-mastered records). Only correct when outside. This
    # respects per-genre character — a jazz record's natural Bass at 30% and a
    # reggae record's at 58% should both pass through untouched.

    BASS_TARGET_PCT: float = 0.46
    """Median bass share across the 27-track reference set (was 0.22 — the old
    value was a 'pop-master' fiction; real records, even bright ones, sit much
    higher). Used as the natural-fit center for diagnostics; tolerance band is
    BASS_TOL_LOW / BASS_TOL_HIGH."""

    BASS_TOL_LOW: float = 0.35
    """Lower edge of the bass tolerance band (p25 across reference). Below this
    the boost path engages."""

    BASS_TOL_HIGH: float = 0.55
    """Upper edge of the bass tolerance band (p75 across reference). Above this
    the de-mud cut engages."""

    BASS_BOOST_RANGE_PCT: float = 0.20
    """How far BELOW the tolerance band counts as 'maximum deficit'. At
    bass_pct = (BASS_TOL_LOW - this), we hit max boost."""

    BASS_CUT_RANGE_PCT: float = 0.20
    """How far ABOVE the tolerance band counts as 'maximum excess'. At
    bass_pct = (BASS_TOL_HIGH + this), we hit max cut. Live folk/world
    tracks at 55-60% bass now fall *inside* the band → no action."""

    BASS_DEMUD_LOW_HZ: float = 100.0
    """Lower bound of the de-mud bell"""

    BASS_DEMUD_HIGH_HZ: float = 220.0
    """Upper bound of the de-mud bell. 100-220 Hz brackets the live-recording
    'boxiness' zone without touching kick fundamental (50-80 Hz) or sub-bass."""

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

    EXCITER_MAX_WET_DB: float = -9.0
    """Wet ceiling (parallel mix). -9 dB ≈ 35% wet for fully-dark material at
    intensity 1.0. Reduced from -6 dB after A/B analysis showed the previous
    setting produced a +7 dB peak at 5 kHz on dark sources, contributing to
    a +9 dB spectral tilt that listeners perceived as 'high-passed'. -9 dB
    still delivers obvious 'crispness' lift without the over-correction."""

    EXCITER_MIN_WET_DB: float = -18.0
    """Wet floor at the activation threshold (just-barely-dark material)."""

    EXCITER_DARKNESS_ACTIVATE: float = 0.55
    """Darkness threshold below which exciter is bypassed. Computed from
    presence_pct + air_pct + spectral_rolloff. 0 = fully dark, 1 = fully bright"""

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

    # =========================================================================
    # Resonance Notcher (de-mud / de-honk)
    # =========================================================================
    # Surgical narrow notches in 150-1200 Hz to tame room modes and recording
    # resonances that mask midrange detail. Only fires on prominent peaks,
    # so clean recordings see no intervention.

    NOTCH_MIN_FREQ_HZ: float = 150.0
    """Lower bound of resonance search range"""

    NOTCH_MAX_FREQ_HZ: float = 1200.0
    """Upper bound. Above this, sharp peaks are usually instrument timbre."""

    NOTCH_MIN_PROMINENCE_DB: float = 8.0
    """Minimum peak prominence above local floor to count as a resonance"""

    NOTCH_MAX_COUNT: int = 3
    """Cap on simultaneous notches. 5 notches clustered in one band can
    cumulatively scoop the band; 3 keeps the surgical character."""

    NOTCH_MAX_DEPTH_DB: float = -4.0
    """Strongest cut allowed at the most-prominent peak. -5 dB combined with
    Q=6 cumulatively scoops the band when 3 notches cluster; -4 dB stays
    audible-as-de-emphasis without over-cutting the broad band."""

    NOTCH_MIN_BAND_HEALTH: float = 0.6
    """Skip notches whose target band is below this health (band_pct/target).
    Below this threshold the band is already severely deficient — adding a
    notch makes it worse. A/B data on Cerca de la revolución showed -2.2 pp
    Mid scoop on a source where Mid was at 12.8% vs 24% target (health 0.53),
    even with proportional depth scaling. Skipping entirely below 0.6 is
    safer than gouging an already-thin band."""

    NOTCH_CAPPED_HEALTH: float = 0.7
    """Below this band health (but above NOTCH_MIN_BAND_HEALTH), the notch
    is allowed but its depth is hard-capped to NOTCH_LOW_HEALTH_CAP_DB.
    We acknowledge the resonance exists but tread lightly."""

    NOTCH_LOW_HEALTH_CAP_DB: float = -1.0
    """Hard cap on notch depth in the cautious health zone (0.6-0.7)."""

    # =========================================================================
    # Transient Shaper (kick / bass attack restoration)
    # =========================================================================
    # Restores attack on compressed low-end. Activates when the band's
    # measured crest factor suggests it's been levelled (compressed sustain).

    TRANSIENT_BASS_LOW_HZ: float = 60.0
    """Lower bound of bass band for transient shaping (kick fundamental)"""

    TRANSIENT_BASS_HIGH_HZ: float = 250.0
    """Upper bound of bass band — includes kick body and low bass notes"""

    TRANSIENT_LO_MID_LOW_HZ: float = 250.0
    """Lower bound of lo-mid band (kick beater, snare body)"""

    TRANSIENT_LO_MID_HIGH_HZ: float = 500.0
    """Upper bound of lo-mid band"""

    TRANSIENT_MAX_BOOST_DB: float = 5.0
    """Maximum attack boost at peak transient moments (×intensity)"""

    TRANSIENT_ACTIVATE_CREST_DB: float = 20.0
    """Below this overall-crest, transients are considered worth shaping.
    Most real-world tracks have crest 10-18 dB; 20 dB threshold ensures we
    engage on nearly all material and bypass only the most pristine acoustic
    recordings. Strength ramps smoothly down as crest approaches the threshold."""

    # =========================================================================
    # Clarity Boost (Up-Mid bell for vocal/snare definition)
    # =========================================================================
    # Separate from the broad presence band. Targets 1.5-3.5 kHz, where vocal
    # consonants and snare attack live. Activates when Up-Mid energy is below
    # CLARITY_TARGET_PCT.

    CLARITY_LOW_HZ: float = 1500.0
    """Lower bound of clarity bell"""

    CLARITY_HIGH_HZ: float = 3500.0
    """Upper bound of clarity bell"""

    CLARITY_TARGET_PCT: float = 0.055
    """Median Up-Mid share across the 27-track reference set (was 0.12 —
    'pop-master' fiction). Real records sit at 5.5% Up-Mid; even bright prog
    tracks max out around 12%."""

    CLARITY_TOL_LOW: float = 0.015
    """Lower edge of the Up-Mid tolerance band (p25 across reference). Below
    this the clarity boost engages. Above this — i.e., already inside the
    natural variance band — do nothing."""

    CLARITY_BOOST_RANGE_PCT: float = 0.015
    """How far below CLARITY_TOL_LOW counts as 'maximum deficit'. At
    upper_mid_pct = 0, we hit max boost."""

    CLARITY_MAX_BOOST_DB: float = 2.0
    """Maximum clarity boost for severely deficient sources. Reduced further
    based on evidence-based Up-Mid distribution: even adding +2 dB to a 0%-
    source brings it only marginally toward the 5.5% median, while bigger
    boosts visibly over-tilt the spectrum."""

    # =========================================================================
    # Sub-Bass Control (continuous curve, like bass balance)
    # =========================================================================
    # Smooth ramp from target outward. Wide range so that even bass-forward
    # live recordings (with legitimately high sub-bass content from kick and
    # upright bass fundamentals) get only modest treatment.

    SUB_TARGET_PCT: float = 0.087
    """Median sub-band share across the 27-track reference set. Higher than
    the previous 0.07 because real records (even non-electronic genres) carry
    more sub content than studio-pop references suggested."""

    SUB_TOL_HIGH: float = 0.13
    """Upper edge of the sub tolerance band (p75 across reference). Below
    this — i.e., inside the natural range — no action. Above this the cut
    engages smoothly. Note: the lower edge isn't enforced; thin sub is
    a stylistic choice (jazz can be at 0.6% sub naturally)."""

    SUB_CUT_RANGE_PCT: float = 0.20
    """How far ABOVE SUB_TOL_HIGH counts as 'maximum excess'. Sub at 33%
    (= 0.13 + 0.20) hits full cut; reference tracks at 12-15% sit inside
    the band and get no cut."""

    MAX_SUB_CUT_DB: float = -1.2
    """Maximum sub-bass parallel cut. Slightly gentler than before because
    the tolerance band already filters out most legitimate sub content."""

    SUB_HP_ACTIVATE_PCT: float = 0.33
    """HP only fires above this sub-content threshold — well above the p90
    of the reference distribution (22.9%) and into 'truly excessive' rumble
    territory. Previously 0.25, which still triggered on dense electronic
    tracks; 0.33 reserves it for genuine sub-rumble pathology."""

    SUBBASS_HP_FREQ_HZ: float = 25.0
    """High-pass cutoff for rumble removal. Lowered from 35 to 25 Hz so
    kick fundamentals (50-80 Hz) are well clear of the filter's rolloff."""

    SUBBASS_HP_ORDER: int = 1
    """Filter order for sub-bass HP. 1st-order = 6 dB/oct (gentle) instead
    of the previous 2nd-order (12 dB/oct), so the rolloff above the cutoff
    is much shallower."""

    # =========================================================================
    # Progress Reporting
    # =========================================================================

    PROGRESS_REPORT_INTERVAL_CHUNKS: int = 5
    """Report progress every N chunks during processing"""
