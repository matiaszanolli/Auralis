"""Personal preference layer - applies on top of base model.

This module implements user-specific mastering adjustments that layer on top of
the professionally-trained base detection model. It enables "binaural mastering"
where the system respects both technical excellence (base model) and personal
hearing characteristics (personal layer).

Philosophy:
  Base Model + Personal Preferences = Truly Personalized Mastering
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PersonalPreferences:
    """User's personal adjustments to base profiles.

    This class represents incremental adjustments the user has learned through
    feedback. These adjustments layer on top of the base model parameters,
    allowing the system to adapt to individual hearing characteristics,
    equipment, and preferences.

    Attributes:
        profile_adjustments: Per-profile EQ adjustments {param: dB_adjustment}
        centroid_preference: Brightness adjustment in Hz (-500 to +500)
        stereo_width_preference: Stereo adjustment (-0.2 to +0.2)
        confidence_adjustment: Trust detector more/less (-0.2 to +0.2)
        gear_profile: Type of listening equipment ("neutral", "bright_headphones", "dark_speakers")
        hearing_profile: Hearing sensitivity ("normal", "bass_sensitive", "treble_sensitive")
        metadata: Version, creation date, sample count used for learning
    """

    # Per-profile adjustments (e.g., {"studio_bass": +0.3, "metal_treble": -0.2})
    profile_adjustments: dict[str, float] = field(default_factory=dict)

    # Per-characteristic adjustments
    centroid_preference: float = 0.0  # -500 to +500 Hz adjustment
    stereo_width_preference: float = 0.0  # -0.2 to +0.2 adjustment
    confidence_adjustment: float = 0.0  # -0.2 to +0.2 adjustment

    # Gear/hearing characteristics
    gear_profile: str = "neutral"
    hearing_profile: str = "normal"

    # Metadata for tracking
    version: str = "1.0"
    created_at: str | None = None
    samples_analyzed: int = 0
    average_satisfaction: float = 0.0

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def apply_to_parameters(self, base_params: dict[str, Any]) -> dict[str, Any]:
        """Apply personal preferences to base model parameters.

        Args:
            base_params: Base model parameters from detector
                Expected keys: bass_adjustment_db, treble_adjustment_db, etc.

        Returns:
            Adjusted parameters with personal preferences applied
        """
        adjusted = base_params.copy()

        # Apply direct profile adjustments
        for param_name, adjustment_db in self.profile_adjustments.items():
            if param_name in adjusted:
                adjusted[param_name] += adjustment_db
            # Also handle alternative naming: "bass" vs "bass_adjustment_db"
            elif f"{param_name}_adjustment_db" in adjusted:
                adjusted[f"{param_name}_adjustment_db"] += adjustment_db

        # Apply spectral centroid preference (brightness/darkness)
        if self.centroid_preference != 0 and "target_spectral_centroid_hz" in adjusted:
            adjusted["target_spectral_centroid_hz"] += self.centroid_preference

        # Apply stereo width preference
        if self.stereo_width_preference != 0 and "stereo_width_target" in adjusted:
            adjusted["stereo_width_target"] += self.stereo_width_preference

        # Apply confidence adjustment (scales how much we trust the detector)
        if self.confidence_adjustment != 0 and "confidence" in adjusted:
            # Clamp confidence to valid range [0.0, 1.0]
            adjusted["confidence"] = max(
                0.0,
                min(1.0, adjusted["confidence"] + self.confidence_adjustment)
            )

        return adjusted

    def record_feedback(self, rating: int, comment: str = "") -> None:
        """Record user feedback to update satisfaction metrics.

        Args:
            rating: 1-5 star rating
            comment: Optional feedback text
        """
        # Update average satisfaction (simple running average)
        if self.samples_analyzed > 0:
            current_total = self.average_satisfaction * self.samples_analyzed
            new_total = current_total + rating
            self.samples_analyzed += 1
            self.average_satisfaction = new_total / self.samples_analyzed
        else:
            self.samples_analyzed = 1
            self.average_satisfaction = rating

    def get_summary(self) -> str:
        """Get human-readable summary of personal preferences.

        Returns:
            Formatted string describing current adjustments
        """
        lines = [
            f"\nPersonal Mastering Profile v{self.version}",
            "=" * 50,
        ]

        if self.samples_analyzed > 0:
            lines.append(
                f"Samples Analyzed: {self.samples_analyzed}"
            )
            lines.append(
                f"Average Satisfaction: {self.average_satisfaction:.1f}/5.0"
            )

        if self.profile_adjustments:
            lines.append("\nProfile Adjustments:")
            for param, value in sorted(self.profile_adjustments.items()):
                lines.append(f"  {param}: {value:+.2f} dB")

        if self.centroid_preference != 0:
            direction = "Brighter" if self.centroid_preference > 0 else "Darker"
            lines.append(f"\nBrightness: {direction} ({self.centroid_preference:+.0f} Hz)")

        if self.stereo_width_preference != 0:
            direction = "Wider" if self.stereo_width_preference > 0 else "Narrower"
            lines.append(f"Stereo Width: {direction} ({self.stereo_width_preference:+.2f})")

        if self.confidence_adjustment != 0:
            direction = "Trust" if self.confidence_adjustment > 0 else "Doubt"
            lines.append(f"Detector: {direction} {abs(self.confidence_adjustment):+.1%}")

        lines.append(f"Gear: {self.gear_profile} | Hearing: {self.hearing_profile}")
        lines.append("=" * 50)

        return "\n".join(lines)

    @staticmethod
    def load_or_create(user_data_dir: Path) -> PersonalPreferences:
        """Load personal preferences or create defaults.

        Args:
            user_data_dir: Directory where personal data is stored

        Returns:
            Loaded PersonalPreferences or new empty instance
        """
        prefs_file = user_data_dir / "personal" / "preferences" / "current.json"

        if prefs_file.exists():
            try:
                data = json.loads(prefs_file.read_text())
                return PersonalPreferences(**data)
            except (json.JSONDecodeError, TypeError) as e:
                # If file is corrupted, return defaults
                print(f"Warning: Could not load preferences from {prefs_file}: {e}")
                return PersonalPreferences()

        # Default: no adjustments
        return PersonalPreferences()

    def save(self, user_data_dir: Path, version: str | None = None) -> None:
        """Save personal preferences with version.

        Args:
            user_data_dir: Directory where to save data
            version: Version string (e.g., "1.1"). If None, auto-increment.
        """
        prefs_dir = user_data_dir / "personal" / "preferences"
        prefs_dir.mkdir(parents=True, exist_ok=True)

        # Auto-increment version if not provided
        if version is None:
            # Find latest version
            existing_files = list(prefs_dir.glob("personal_*.json"))
            if existing_files:
                # Extract version numbers and find max
                versions = []
                for f in existing_files:
                    try:
                        v = f.stem.split("_")[-1]  # e.g., "1.2" from "personal_1.2.json"
                        versions.append(v)
                    except (IndexError, ValueError):
                        continue
                if versions:
                    # Simple increment: bump patch version
                    major, minor = map(int, versions[-1].split("."))
                    version = f"{major}.{minor + 1}"
            if version is None:
                version = "1.0"

        # Update version and timestamp
        self.version = version
        self.created_at = datetime.now().isoformat()

        # Versioned file
        version_file = prefs_dir / f"personal_{version}.json"
        version_file.write_text(
            json.dumps(asdict(self), indent=2)
        )

        # Current pointer
        current_file = prefs_dir / "current.json"
        current_file.write_text(version_file.read_text())

    def export_for_sharing(self) -> dict[str, Any]:
        """Export profile for optional sharing (anonymized).

        Returns:
            Dictionary with shareable profile data (no identifying info)
        """
        return {
            "version": self.version,
            "adjustments": self.profile_adjustments,
            "brightness_preference": self.centroid_preference,
            "stereo_preference": self.stereo_width_preference,
            "confidence_adjustment": self.confidence_adjustment,
            "gear_profile": self.gear_profile,
            "hearing_profile": self.hearing_profile,
            "samples_analyzed": self.samples_analyzed,
            "average_satisfaction": self.average_satisfaction,
            # No timestamps or identifying data
        }

    @staticmethod
    def import_shared_profile(shared_data: dict[str, Any]) -> PersonalPreferences:
        """Import a shared profile from another user.

        This creates a new profile based on someone else's shared preferences,
        allowing users to start with proven adjustments.

        Args:
            shared_data: Dictionary from export_for_sharing()

        Returns:
            New PersonalPreferences instance
        """
        return PersonalPreferences(
            profile_adjustments=shared_data.get("adjustments", {}),
            centroid_preference=shared_data.get("brightness_preference", 0.0),
            stereo_width_preference=shared_data.get("stereo_preference", 0.0),
            confidence_adjustment=shared_data.get("confidence_adjustment", 0.0),
            gear_profile=shared_data.get("gear_profile", "neutral"),
            hearing_profile=shared_data.get("hearing_profile", "normal"),
            samples_analyzed=0,  # Reset - user will build their own from here
            average_satisfaction=0.0,
        )
