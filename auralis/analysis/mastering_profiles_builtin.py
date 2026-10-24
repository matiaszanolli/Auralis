"""
Pre-defined mastering profiles (split from mastering_profile.py, #5838): the
data half of the profile system, kept apart from the classes that define it.
"""

from .mastering_profile import DetectionRules, MasteringProfile, ProcessingTargets

# Pre-defined profiles based on analysis
PROFILE_SODA_STEREO = MasteringProfile(
    profile_id="live-rock-preservation-v1",
    name="Live Rock - Preservation Mastering",
    detection_rules=DetectionRules(
        loudness_min=-15,
        loudness_max=-12,
        crest_min=9,
        crest_max=12,
        zcr_min=0.07,
        zcr_max=0.09,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-3.1,
        crest_change_db=0,  # Preserve
        centroid_change_hz=-77.5,
        description="Live performance with good quality: reduce loudness for headroom, preserve dynamics, subtle de-essing",
    ),
    source_albums=["Soda Stereo - Ruido Blanco (1987)"],
    training_tracks=9,
    confidence=0.92,
    release_type="live",
    genre_hint="rock",
    era_estimate=1987,
)

PROFILE_QUIET_REFERENCE = MasteringProfile(
    profile_id="quiet-reference-modernization-v1",
    name="Quiet Reference - Modernization",
    detection_rules=DetectionRules(
        loudness_min=-18.5,
        loudness_max=-16,
        crest_min=15,
        crest_max=18,
        zcr_min=0.06,
        zcr_max=0.08,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-1.0,
        crest_change_db=0.3,
        centroid_change_hz=300,
        target_loudness_db=-18.5,
        description="Professional reference master with excellent dynamics: minimal loudness change, preserve crest, add modern presence",
    ),
    source_albums=["Dio - The Last In Line (1984)"],
    training_tracks=9,
    confidence=0.88,
    release_type="professional",
    genre_hint="metal",
    era_estimate=1984,
)

PROFILE_DAMAGED_RESTORATION = MasteringProfile(
    profile_id="damaged-studio-restoration-v1",
    name="Damaged Studio - Restoration",
    detection_rules=DetectionRules(
        loudness_min=-14,
        loudness_max=-11,
        crest_min=9,
        crest_max=11,
        zcr_min=0.09,
        zcr_max=0.12,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-1.3,
        crest_change_db=2.0,
        centroid_change_hz=-245,
        description="Poorly recorded/over-compressed studio: expand dynamics, aggressive EQ for artifact removal, accept higher noise floor",
    ),
    source_albums=["Destruction - All Hell Breaks Loose (2000)"],
    training_tracks=12,
    confidence=0.85,
    release_type="damaged",
    genre_hint="metal",
    era_estimate=2000,
)

PROFILE_HOLY_DIVER = MasteringProfile(
    profile_id="quiet-commercial-restoration-v1",
    name="Quiet Commercial - Loudness Restoration",
    detection_rules=DetectionRules(
        loudness_min=-17.5,
        loudness_max=-16,
        crest_min=16,
        crest_max=18,
        zcr_min=0.08,
        zcr_max=0.10,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=5.5,
        crest_change_db=-5.4,
        centroid_change_hz=335,
        target_loudness_db=-11.7,
        description="Quiet reference master from 1980s Japanese pressing: aggressive modernization with loudness restoration and compression",
    ),
    source_albums=["Dio - Holy Diver (1983)"],
    training_tracks=9,
    confidence=0.90,
    release_type="reference",
    genre_hint="metal",
    era_estimate=1986,
)

# BUILT-IN PROFILES FOR PRIORITY 1-3 IMPROVEMENTS

PROFILE_HIRES_MASTERS = MasteringProfile(
    profile_id="hires-masters-modernization-v1",
    name="Hi-Res Masters - Modernization with Expansion",
    detection_rules=DetectionRules(
        loudness_min=-16.5,
        loudness_max=-13,
        crest_min=12,
        crest_max=15,
        zcr_min=0.06,
        zcr_max=0.09,
        centroid_min=2800,
        centroid_max=4200,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-0.93,      # PRIORITY 1 FIX: Quiet reduction, not aggressive
        crest_change_db=1.4,            # PRIORITY 1 FIX: Expand dynamics (was predicting compression)
        centroid_change_hz=100,         # PRIORITY 2 FIX: Selective brightening
        target_loudness_db=-14.5,
        description="Modern Hi-Res remaster philosophy: quiet loudness reduction, dynamic expansion, selective EQ brightening to add clarity",
    ),
    source_albums=[
        "Michael Jackson - Dangerous (Hi-Res Masters)",
        "Quincy Jones mastering philosophy (1991-2025 comparison)",
    ],
    training_tracks=7,
    confidence=0.75,  # Lower confidence due to hybrid nature
    release_type="remaster",
    genre_hint="pop/funk",
    era_estimate=2025,
    notes="Derived from multi-style test suite of 7 Michael Jackson tracks. Represents modern approach: undo loudness wars while recovering dynamics.",
)

PROFILE_BRIGHT_MASTERS = MasteringProfile(
    profile_id="bright-masters-spectral-v1",
    name="Bright Masters - High-Frequency Emphasis",
    detection_rules=DetectionRules(
        loudness_min=-15.5,
        loudness_max=-12.5,
        crest_min=12,
        crest_max=16,
        zcr_min=0.08,
        zcr_max=0.11,
        centroid_min=3300,  # PRIORITY 2: Spectral profiling
        centroid_max=4400,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-1.0,
        crest_change_db=1.2,
        centroid_change_hz=130,         # PRIORITY 2 FIX: Significant brightening
        description="Contemporary pop/funk remaster: add presence and clarity via high-frequency lift (+100-180 Hz centroid shift)",
    ),
    source_albums=[
        "Michael Jackson - Black Or White",
        "Modern remaster targets (presence-focused)",
    ],
    training_tracks=2,
    confidence=0.72,
    release_type="remaster",
    genre_hint="pop/funk",
    era_estimate=2025,
    notes="PRIORITY 2: Spectral profiling. Identifies and applies selective brightening to add clarity and modernity.",
)

PROFILE_WARM_MASTERS = MasteringProfile(
    profile_id="warm-masters-spectral-v1",
    name="Warm Masters - Low-Frequency Emphasis",
    detection_rules=DetectionRules(
        loudness_min=-16,
        loudness_max=-13.5,
        crest_min=12,
        crest_max=15,
        zcr_min=0.06,
        zcr_max=0.08,
        centroid_min=2800,  # PRIORITY 2: Darker tone range
        centroid_max=3600,
    ),
    processing_targets=ProcessingTargets(
        loudness_change_db=-0.8,
        crest_change_db=1.1,
        centroid_change_hz=-80,         # PRIORITY 2 FIX: Subtle warmth via de-essing
        description="Intimate pop/soul remaster: preserve warmth, gentle dynamic expansion, subtle de-essing for natural tone",
    ),
    source_albums=[
        "Michael Jackson - In The Closet",
        "Soul/ballad preservation masters",
    ],
    training_tracks=2,
    confidence=0.70,
    release_type="remaster",
    genre_hint="pop/soul",
    era_estimate=2025,
    notes="PRIORITY 2: Spectral profiling. Preserves warm tone while adding modern polish via dynamic expansion.",
)
