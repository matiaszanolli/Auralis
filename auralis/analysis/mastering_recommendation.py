"""
Mastering recommendation value types (split from adaptive_mastering_engine.py,
#5838): a weighted profile and the blended recommendation built from them.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .mastering_profile import MasteringProfile


@dataclass
class ProfileWeight:
    """A profile with its weight in a blended recommendation."""
    profile: MasteringProfile
    weight: float  # 0-1, sum of all weights = 1.0


@dataclass
class MasteringRecommendation:
    """Recommendation for mastering an audio track."""

    primary_profile: MasteringProfile        # Best matching profile
    confidence_score: float                  # How confident we are (0-1)
    predicted_loudness_change: float         # Predicted RMS change (dB)
    predicted_crest_change: float           # Predicted crest change (dB)
    predicted_centroid_change: float        # Predicted centroid change (Hz)

    alternative_profiles: list[MasteringProfile] = field(default_factory=list)
    reasoning: str = ""                     # Explanation for the recommendation
    weighted_profiles: list[ProfileWeight] = field(default_factory=list)  # Blended profiles (if hybrid)
    created: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'primary_profile_id': self.primary_profile.profile_id,
            'primary_profile_name': self.primary_profile.name,
            'confidence_score': self.confidence_score,
            'predicted_loudness_change': self.predicted_loudness_change,
            'predicted_crest_change': self.predicted_crest_change,
            'predicted_centroid_change': self.predicted_centroid_change,
            'reasoning': self.reasoning,
            'created': self.created,
            'alternative_profiles': [
                {'id': p.profile_id, 'name': p.name} for p in self.alternative_profiles
            ],
        }

        # Add weighted profiles if this is a hybrid recommendation
        if self.weighted_profiles:
            result['weighted_profiles'] = [
                {'profile_id': pw.profile.profile_id, 'profile_name': pw.profile.name, 'weight': pw.weight}
                for pw in self.weighted_profiles
            ]

        return result

    def to_response(self, track_id: int) -> dict[str, Any]:
        """Serialize for API responses (REST + WS), keyed to a track.

        Single source of truth for the recommendation payload shape. Wraps
        :meth:`to_dict` and adds the two fields every API consumer requires
        but the dataclass cannot know on its own:

        - ``track_id`` — the track the recommendation is for.
        - ``is_hybrid`` — whether this is a blended (weighted) recommendation.

        Also guarantees ``weighted_profiles`` is always present (empty list
        when not hybrid) so the field is never undefined for clients that
        declare it required.

        Used by both the REST endpoint and the WS broadcast so the two paths
        honor an identical contract (fixes #3840 — the REST path previously
        returned ``to_dict()`` raw, omitting ``is_hybrid``/``track_id``).
        """
        result = self.to_dict()
        result['track_id'] = track_id
        result['is_hybrid'] = bool(self.weighted_profiles)
        result.setdefault('weighted_profiles', [])
        return result

    def summary(self) -> str:
        """Human-readable summary of recommendation."""
        lines = []

        # Show weighted profiles if hybrid recommendation
        if self.weighted_profiles:
            lines.append(f"Blended Profile (Hybrid Mastering):")
            for pw in self.weighted_profiles:
                lines.append(f"  {pw.profile.name}: {pw.weight:.0%}")
            lines.append(f"")

        lines.extend([
            f"Profile: {self.primary_profile.name}",
            f"Confidence: {self.confidence_score:.0%}",
            f"Expected Changes:",
            f"  Loudness: {self.predicted_loudness_change:+.2f} dB",
            f"  Crest:    {self.predicted_crest_change:+.2f} dB",
            f"  Centroid: {self.predicted_centroid_change:+.1f} Hz",
            f"",
            f"Strategy: {self.primary_profile.processing_targets.description}",
            f"",
            f"Reasoning: {self.reasoning}",
        ])

        if self.alternative_profiles:
            lines.append(f"")
            lines.append(f"Alternative Profiles:")
            for profile in self.alternative_profiles:
                lines.append(f"  - {profile.name}")

        return "\n".join(lines)
