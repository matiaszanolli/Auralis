"""
Mastering Profile System for Adaptive Audio Processing

A "mastering profile" represents a learned pattern from successful Matchering
remasters. It encodes:

1. Detection Rules: How to identify incoming audio that matches this profile
2. Processing Targets: What changes to make (loudness, spectral, dynamics)
3. Training Data: Which albums/tracks led to this profile
4. Versioning: Track improvements over time as new data arrives

The adaptive engine compares incoming fingerprints against profiles to find
the best matching mastering strategy, rather than using preset configurations.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
from pathlib import Path
import numpy as np
from .fingerprint.common_metrics import MetricUtils

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class DetectionRules:
    """Rules for classifying incoming audio to this profile."""

    loudness_min: float  # Minimum RMS loudness in dBFS
    loudness_max: float  # Maximum RMS loudness in dBFS
    crest_min: float     # Minimum crest factor in dB
    crest_max: float     # Maximum crest factor in dB
    zcr_min: float       # Minimum zero crossing rate
    zcr_max: float       # Maximum zero crossing rate
    centroid_min: Optional[float] = None  # Optional centroid bounds
    centroid_max: Optional[float] = None

    def matches(self, fingerprint) -> bool:
        """Check if a fingerprint matches these rules."""
        return (
            self.loudness_min <= fingerprint.loudness_dbfs <= self.loudness_max and
            self.crest_min <= fingerprint.crest_db <= self.crest_max and
            self.zcr_min <= fingerprint.zero_crossing_rate <= self.zcr_max and
            (self.centroid_min is None or fingerprint.spectral_centroid >= self.centroid_min) and
            (self.centroid_max is None or fingerprint.spectral_centroid <= self.centroid_max)
        )

    def similarity_score(self, fingerprint, confidence_weight: float = 1.0) -> float:
        """
        Calculate how well a fingerprint matches these rules (0-1).

        Considers all dimensions and normalizes each to a 0-1 range.
        """
        scores = []

        # Loudness match (absolute distance from center)
        loud_center = (self.loudness_min + self.loudness_max) / 2
        loud_range = (self.loudness_max - self.loudness_min) / 2
        loud_dist = abs(fingerprint.loudness_dbfs - loud_center) / max(loud_range, 0.1)
        # Normalize distance to similarity using MetricUtils
        loud_score = max(0, 1 - MetricUtils.normalize_to_range(loud_dist, 2.0, clip=True))
        scores.append(loud_score)

        # Crest match
        crest_center = (self.crest_min + self.crest_max) / 2
        crest_range = (self.crest_max - self.crest_min) / 2
        crest_dist = abs(fingerprint.crest_db - crest_center) / max(crest_range, 0.1)
        crest_score = max(0, 1 - MetricUtils.normalize_to_range(crest_dist, 2.0, clip=True))
        scores.append(crest_score)

        # ZCR match
        zcr_center = (self.zcr_min + self.zcr_max) / 2
        zcr_range = (self.zcr_max - self.zcr_min) / 2
        zcr_dist = abs(fingerprint.zero_crossing_rate - zcr_center) / max(zcr_range, 0.01)
        zcr_score = max(0, 1 - MetricUtils.normalize_to_range(zcr_dist, 2.0, clip=True))
        scores.append(zcr_score)

        # Centroid match (if specified)
        if self.centroid_min is not None and self.centroid_max is not None:
            cent_center = (self.centroid_min + self.centroid_max) / 2
            cent_range = (self.centroid_max - self.centroid_min) / 2
            cent_dist = abs(fingerprint.spectral_centroid - cent_center) / max(cent_range, 100)
            cent_score = max(0, 1 - MetricUtils.normalize_to_range(cent_dist, 2.0, clip=True))
            scores.append(cent_score)

        # Return average score with confidence weight
        avg_score = np.mean(scores) if scores else 0.0
        return float(avg_score * confidence_weight)


@dataclass
class ProcessingTargets:
    """Expected changes after mastering."""

    loudness_change_db: float      # Expected RMS change
    crest_change_db: float         # Expected crest factor change
    centroid_change_hz: float      # Expected centroid shift
    target_loudness_db: Optional[float] = None  # Absolute target (if known)
    description: str = ""          # Human-readable strategy description


@dataclass
class MasteringProfile:
    """
    Complete mastering profile: detection rules + processing targets + metadata.

    Example profiles from analysis:
    - "live-rock-preservation": Live recordings, preserve dynamics, reduce loudness slightly
    - "quiet-reference-modernization": Reference-quality quiet masters, add loudness + compression
    - "damaged-restoration": Over-compressed or damaged studio, expand dynamics, aggressive EQ
    - "professional-light-touch": Already well-mastered, minimal intervention + air
    """

    profile_id: str                    # Unique identifier
    name: str                          # Human-readable name
    detection_rules: DetectionRules    # How to classify incoming audio
    processing_targets: ProcessingTargets  # What changes to make

    source_albums: List[str] = field(default_factory=list)    # Training sources
    training_tracks: int = 0           # Number of tracks used to derive this
    confidence: float = 0.85           # Confidence level (0-1)
    version: str = "1.0"               # Version for tracking improvements
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    updated: str = field(default_factory=lambda: datetime.now().isoformat())

    # Historical metadata
    release_type: Optional[str] = None  # e.g., "live", "studio", "damaged", "reference"
    genre_hint: Optional[str] = None    # e.g., "rock", "metal", "pop"
    era_estimate: Optional[int] = None  # Estimated original recording year

    notes: str = ""                    # Additional context

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'profile_id': self.profile_id,
            'name': self.name,
            'detection_rules': asdict(self.detection_rules),
            'processing_targets': asdict(self.processing_targets),
            'source_albums': self.source_albums,
            'training_tracks': self.training_tracks,
            'confidence': self.confidence,
            'version': self.version,
            'created': self.created,
            'updated': self.updated,
            'release_type': self.release_type,
            'genre_hint': self.genre_hint,
            'era_estimate': self.era_estimate,
            'notes': self.notes,
        }

    def to_yaml_str(self) -> str:
        """Convert to YAML string (or JSON if YAML not available)."""
        data = self.to_dict()
        if yaml:
            return yaml.dump(data, default_flow_style=False, sort_keys=False)
        else:
            return json.dumps(data, indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> "MasteringProfile":
        """Create from dictionary."""
        dr = DetectionRules(**data['detection_rules'])
        pt = ProcessingTargets(**data['processing_targets'])

        return cls(
            profile_id=data['profile_id'],
            name=data['name'],
            detection_rules=dr,
            processing_targets=pt,
            source_albums=data.get('source_albums', []),
            training_tracks=data.get('training_tracks', 0),
            confidence=data.get('confidence', 0.85),
            version=data.get('version', '1.0'),
            created=data.get('created', datetime.now().isoformat()),
            updated=data.get('updated', datetime.now().isoformat()),
            release_type=data.get('release_type'),
            genre_hint=data.get('genre_hint'),
            era_estimate=data.get('era_estimate'),
            notes=data.get('notes', ''),
        )

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> "MasteringProfile":
        """Create from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)


class MasteringProfileDatabase:
    """
    In-memory database of mastering profiles with versioning.

    Supports:
    - Loading profiles from YAML files
    - Saving updated profiles
    - Querying profiles by characteristics
    - Ranking profiles by similarity to incoming audio
    """

    def __init__(self):
        self.profiles: Dict[str, MasteringProfile] = {}
        self.profile_history: Dict[str, List[MasteringProfile]] = {}  # For versioning

    def add_profile(self, profile: MasteringProfile) -> None:
        """Add a profile to the database."""
        if profile.profile_id not in self.profile_history:
            self.profile_history[profile.profile_id] = []
        self.profile_history[profile.profile_id].append(profile)
        self.profiles[profile.profile_id] = profile
        print(f"Added profile: {profile.name} (v{profile.version})")

    def rank_profiles(self, fingerprint, top_k: int = 5) -> List[Tuple[MasteringProfile, float]]:
        """
        Rank profiles by similarity to incoming fingerprint.

        Returns:
            List of (profile, similarity_score) tuples, sorted by score descending
        """
        rankings = []

        for profile_id, profile in self.profiles.items():
            score = profile.detection_rules.similarity_score(fingerprint)
            if score > 0:  # Only include profiles with non-zero score
                rankings.append((profile, score))

        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)

        return rankings[:top_k]

    def find_best_profile(self, fingerprint) -> Optional[Tuple[MasteringProfile, float]]:
        """Find the single best matching profile."""
        rankings = self.rank_profiles(fingerprint, top_k=1)
        return rankings[0] if rankings else None

    def to_yaml_file(self, file_path: str) -> None:
        """Save all profiles to a YAML file."""
        data = {
            'version': '1.0',
            'generated': datetime.now().isoformat(),
            'profile_count': len(self.profiles),
            'profiles': [profile.to_dict() for profile in self.profiles.values()],
        }

        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml_file(cls, file_path: str) -> "MasteringProfileDatabase":
        """Load profiles from a YAML file."""
        db = cls()

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        for profile_data in data.get('profiles', []):
            profile = MasteringProfile.from_dict(profile_data)
            db.add_profile(profile)

        return db

    def list_profiles(self) -> List[MasteringProfile]:
        """Get all profiles sorted by ID."""
        return sorted(self.profiles.values(), key=lambda p: p.profile_id)

    def get_profile(self, profile_id: str) -> Optional[MasteringProfile]:
        """Get a specific profile by ID."""
        return self.profiles.get(profile_id)

    def describe_profile(self, profile_id: str) -> str:
        """Get human-readable description of a profile."""
        profile = self.get_profile(profile_id)
        if not profile:
            return f"Profile '{profile_id}' not found"

        lines = [
            f"Profile: {profile.name}",
            f"ID: {profile.profile_id}",
            f"Version: {profile.version}",
            f"Confidence: {profile.confidence:.0%}",
            f"",
            f"Detection Rules:",
            f"  Loudness: {profile.detection_rules.loudness_min:.1f} to {profile.detection_rules.loudness_max:.1f} dBFS",
            f"  Crest: {profile.detection_rules.crest_min:.1f} to {profile.detection_rules.crest_max:.1f} dB",
            f"  ZCR: {profile.detection_rules.zcr_min:.4f} to {profile.detection_rules.zcr_max:.4f}",
            f"",
            f"Processing Targets:",
            f"  Loudness Change: {profile.processing_targets.loudness_change_db:+.2f} dB",
            f"  Crest Change: {profile.processing_targets.crest_change_db:+.2f} dB",
            f"  Centroid Change: {profile.processing_targets.centroid_change_hz:+.1f} Hz",
            f"",
            f"Training Data:",
            f"  Albums: {', '.join(profile.source_albums) if profile.source_albums else '(none yet)'}",
            f"  Tracks: {profile.training_tracks}",
            f"",
            f"Strategy: {profile.processing_targets.description}",
        ]

        return "\n".join(lines)


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

# NEW PROFILES FOR PRIORITY 1-3 IMPROVEMENTS

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
