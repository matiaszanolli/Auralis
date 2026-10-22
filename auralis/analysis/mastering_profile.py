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

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from .fingerprint.metrics import MetricUtils

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
    centroid_min: float | None = None  # Optional centroid bounds
    centroid_max: float | None = None

    def matches(self, fingerprint: Any) -> bool:
        """Check if a fingerprint matches these rules."""
        return (
            self.loudness_min <= fingerprint.loudness_dbfs <= self.loudness_max and
            self.crest_min <= fingerprint.crest_db <= self.crest_max and
            self.zcr_min <= fingerprint.zero_crossing_rate <= self.zcr_max and
            (self.centroid_min is None or fingerprint.spectral_centroid >= self.centroid_min) and
            (self.centroid_max is None or fingerprint.spectral_centroid <= self.centroid_max)
        )

    def similarity_score(self, fingerprint: Any, confidence_weight: float = 1.0) -> float:
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
    target_loudness_db: float | None = None  # Absolute target (if known)
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

    source_albums: list[str] = field(default_factory=list)    # Training sources
    training_tracks: int = 0           # Number of tracks used to derive this
    confidence: float = 0.85           # Confidence level (0-1)
    version: str = "1.0"               # Version for tracking improvements
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    updated: str = field(default_factory=lambda: datetime.now().isoformat())

    # Historical metadata
    release_type: str | None = None  # e.g., "live", "studio", "damaged", "reference"
    genre_hint: str | None = None    # e.g., "rock", "metal", "pop"
    era_estimate: int | None = None  # Estimated original recording year

    notes: str = ""                    # Additional context

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'MasteringProfile':
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


class MasteringProfileDatabase:
    """
    In-memory database of mastering profiles with versioning.

    Supports:
    - Loading profiles from YAML files
    - Saving updated profiles
    - Querying profiles by characteristics
    - Ranking profiles by similarity to incoming audio
    """

    def __init__(self) -> None:
        self.profiles: dict[str, MasteringProfile] = {}
        self.profile_history: dict[str, list[MasteringProfile]] = {}  # For versioning

    def add_profile(self, profile: MasteringProfile) -> None:
        """Add a profile to the database."""
        if profile.profile_id not in self.profile_history:
            self.profile_history[profile.profile_id] = []
        self.profile_history[profile.profile_id].append(profile)
        self.profiles[profile.profile_id] = profile
        print(f"Added profile: {profile.name} (v{profile.version})")

    def rank_profiles(self, fingerprint: Any, top_k: int = 5) -> list[tuple[MasteringProfile, float]]:
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
    def from_yaml_file(cls, file_path: str) -> 'MasteringProfileDatabase':
        """Load profiles from a YAML file."""
        db = cls()

        with open(file_path) as f:
            data = yaml.safe_load(f)

        for profile_data in data.get('profiles', []):
            profile = MasteringProfile.from_dict(profile_data)
            db.add_profile(profile)

        return db

    def list_profiles(self) -> list[MasteringProfile]:
        """Get all profiles sorted by ID."""
        return sorted(self.profiles.values(), key=lambda p: p.profile_id)

    def get_profile(self, profile_id: str) -> MasteringProfile | None:
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
