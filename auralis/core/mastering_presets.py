"""
Mastering Preset Tuning Tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calibrated default-value tables for the specialized correction stages of
SimpleMasteringPipeline: the resonance notcher, transient shaping,
clarity/vocal-unmasking bells, sub-bass control, and the continuous
loudness/crest response.

Split out of ``mastering_config.py`` (#4511) — these are the tuning tables
for the pipeline's secondary, corrective DSP stages, as opposed to the
foundational schema (target loudness, chunking, EQ frequencies, primary
boost limits, harmonic exciter) that stays in ``mastering_config.py``.
``SimpleMasteringConfig``
inherits from :class:`MasteringPresetDefaults` so every field below remains
a plain flat attribute on ``SimpleMasteringConfig`` instances — the split is
purely organizational and changes no public behavior.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


@dataclass
class MasteringPresetDefaults:
    """
    Tuning tables for SimpleMasteringPipeline's secondary correction stages.

    Not meant to be instantiated directly — composed into
    :class:`~auralis.core.mastering_config.SimpleMasteringConfig` via
    inheritance so callers keep a single flat config object.
    """

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

    NOTCH_HEALTH_RESPONSE_CENTER: float = 0.65
    """Center of the smooth band-health attenuation response."""

    NOTCH_HEALTH_RESPONSE_WIDTH: float = 0.08
    """Width of the smooth band-health response."""

    NOTCH_SOFT_MAX_DEPTH_DB: float = 2.5
    """Scale of the tanh per-notch depth compressor."""

    NOTCH_SOFT_BAND_BUDGET_DB: float = 4.0
    """Scale of the tanh cumulative-depth compressor for clustered notches."""

    NOTCH_LOW_PROTECTION_CENTER_HZ: float = 300.0
    """Center of the smooth transition from protected bass fundamentals to
    ordinary midrange resonance treatment."""

    NOTCH_LOW_PROTECTION_WIDTH_HZ: float = 100.0
    """Width of the low-frequency notch-protection transition."""

    NOTCH_LOW_PROTECTION_FLOOR: float = 0.15
    """Smallest fraction of a detected notch depth retained near the bottom of
    the search range. The Q increases by the complementary amount."""

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
    # Vocal Unmasking (bass-vs-voice imbalance, distinct from absolute Up-Mid)
    # =========================================================================
    # The clarity bell historically fired only on an ABSOLUTE Up-Mid deficit
    # (upper_mid < CLARITY_TOL_LOW = 1.5%). That misses the common defect of a
    # vocal buried by a DOMINANT bass even though Up-Mid is nominally "fine":
    # Patricio Rey's Gulp sits at bass 60% / mid 5% / Up-Mid 4% — the voice is
    # 6-9 dB under the bass yet Up-Mid is above the 1.5% floor, so clarity never
    # engaged. These constants add a second, RELATIVE trigger keyed on the
    # bass-to-voice energy ratio, so the bell lifts the vocal presence band
    # whenever the voice is masked — while leaving balanced bass-heavy genres
    # (reggae/folk, ratio ~2) untouched.

    VOCAL_MASK_RATIO_LOW: float = 3.0
    """bass_pct / (mid_pct + upper_mid_pct) above which the voice is considered
    masked by the bass. Reference well-mastered records sit at ~2.0 (bass 0.46 /
    voice 0.226); 3.0 leaves normal material alone and engages only on genuine
    burial. Gulp's masked tracks sit at 6-9."""

    VOCAL_MASK_RATIO_RANGE: float = 3.0
    """Ratio span above VOCAL_MASK_RATIO_LOW that maps to maximum unmasking.
    At ratio = (LOW + this) = 6.0 the lift is full. Tightened from 4.0 so
    moderately-masked tracks (Gulp's 'Te voy', ratio 5.3) reach most of the
    correction instead of sitting mid-ramp — calibrated against well-mastered
    references whose voice/bass sits at -1 to +2 dB (Dio +2.0, Gilmour -0.6)."""

    VOCAL_MASK_MAX_BOOST_DB: float = 4.0
    """Max clarity-bell lift on the vocal presence band when fully masked.
    Higher than CLARITY_MAX_BOOST_DB because unburying a voice that is 6-9 dB
    under the bass needs more than the gentle absolute-deficit nudge. 4 dB lifts
    the most-masked tracks (Gulp 'Te voy') meaningfully while the easier cases
    (La Bestia) only reach a Dio-like +1-2 dB voice/bass, not honky."""

    VOCAL_MASK_CUT_LOW_HZ: float = 150.0
    """Lower bound of the complementary 'de-mask' cut applied to the bass when a
    vocal is masked. Sits above the kick fundamental (50-120 Hz) so the low-end
    weight is preserved while the upper-bass/low-mid mud that masks the vocal
    body is reduced."""

    VOCAL_MASK_CUT_HIGH_HZ: float = 450.0
    """Upper bound of the de-mask cut — the boxy 150-450 Hz region where bass
    energy upward-masks the vocal."""

    VOCAL_MASK_BASS_CUT_DB: float = 3.5
    """Max depth of the de-mask cut at full masking severity. Works with the
    clarity boost from the other side: lift the voice AND lower the masker, so
    extremely bass-dominant tracks (Gulp at 60% bass) unbury without an
    unnatural narrow presence spike."""

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
    # Continuous loudness / crest response
    # =========================================================================
    # Trades some crest factor for level via a transparent push-then-limit.
    # Source LUFS and crest remain continuous measurements throughout; no
    # recording category or activation cutoff is used.
    #
    # WHY THIS EXISTS: the continuous path's makeup gain is capped (crest > 15 dB)
    # and then zeroed (peaks already near 0 dBFS) for high-crest material, and
    # the final stage is a pure peak-normalize — which pins output loudness to
    # ``peak - crest``. A vintage rock record at -22 LUFS / 18 dB crest with
    # peaks near full scale therefore came out only ~1-3 dB louder than the
    # source ("almost no treatment"). The cure is to REDUCE the crest factor
    # (the only lever that moves loudness once peaks are at the ceiling), which
    # is exactly what a brick-wall limiter fed with pre-gain does.
    #
    LOUDNESS_TARGET_LUFS: float = -14.5
    """Loudness anchor for the smooth positive-gap response, not a category
    boundary and not the final output LUFS."""

    LOUDNESS_RESPONSE_SOFTNESS_DB: float = 0.75
    """Width of the softplus transition around the loudness anchor. The response
    has no zero-gain side and no clipped full-strength side."""

    LOUDNESS_GAP_CLOSURE_FACTOR: float = 0.5
    """Fraction of the smooth positive loudness gap that is closed. At 0.5,
    relative loudness differences between recordings are reduced, not erased."""

    LOUDNESS_MIN_CREST_DB: float = 11.0
    """Crest-factor floor. The push is clamped so output crest never falls below
    this — guarantees the result stays clearly dynamic (no loudness-war
    crushing). 11 dB is still markedly more dynamic than brickwalled masters
    (~6-8 dB) while permitting a real loudness lift."""

    LOUDNESS_MAX_PUSH_DB: float = 10.0
    """Signal-safety ceiling on the push gain."""

    LOUDNESS_MAX_CREST_REDUCTION_DB: float = 4.0
    """Signal-safety cap on how much crest reduction the stage can approach."""

    LOUDNESS_LIMITER_CEILING_DB: float = -1.0
    """Brick-wall limiter ceiling. The downstream final normalize lifts the peak
    back toward the output target, and the per-chunk True-Peak guard in
    master_file caps inter-sample peaks at -0.5 dBFS."""

    LOUDNESS_LIMITER_RELEASE_MS: float = 60.0
    """Limiter release. Long enough to avoid pumping on sustained low end,
    short enough to recover between transients on punchy rock material."""

    # =========================================================================
    # Progress Reporting
    # =========================================================================

    PROGRESS_REPORT_INTERVAL_CHUNKS: int = 5
    """Report progress every N chunks during processing"""
