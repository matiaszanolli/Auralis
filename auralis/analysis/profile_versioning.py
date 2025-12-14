"""
Profile Versioning System

Tracks profile evolution over time as new training data arrives.
Maintains complete history for auditing and rollback.

Features:
1. Version profiles (v1.0 → v1.1 → v2.0, etc.)
2. Track training data sources for each version
3. Maintain change history and confidence improvements
4. Support profile rollback and comparison
5. Validate version compatibility
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from .mastering_profile import MasteringProfile


@dataclass
class ProfileVersion:
    """A single version of a mastering profile with metadata."""

    version: str  # e.g., "1.0", "1.1", "2.0"
    profile: MasteringProfile
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    improved_from: Optional[str] = None  # Previous version (e.g., "1.0" if this is "1.1")
    improvement_reason: str = ""  # Why this version improved
    training_source: str = ""  # Album/source that triggered improvement
    confidence_change: float = 0.0  # Change in confidence (e.g., +0.05)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'version': self.version,
            'profile': self.profile.to_dict(),
            'created_at': self.created_at,
            'improved_from': self.improved_from,
            'improvement_reason': self.improvement_reason,
            'training_source': self.training_source,
            'confidence_change': self.confidence_change,
        }


class ProfileVersionManager:
    """
    Manages profile versioning and history.

    Typical workflow:
    1. Create ProfileVersion for new profile (v1.0)
    2. Add to manager: manager.add_version(profile_id, profile_version)
    3. When training data improves profile: manager.create_improved_version(...)
    4. Maintain history for auditing
    """

    def __init__(self, history_dir: Optional[str] = None):
        """
        Initialize version manager.

        Args:
            history_dir: Directory to persist version history (optional)
        """
        self.histories: Dict[str, List[ProfileVersion]] = {}
        self.current_versions: Dict[str, ProfileVersion] = {}
        self.history_dir = history_dir

    def add_version(self, profile_id: str, version: ProfileVersion) -> None:
        """
        Add a profile version.

        Args:
            profile_id: Unique profile identifier
            version: ProfileVersion to add
        """
        if profile_id not in self.histories:
            self.histories[profile_id] = []

        self.histories[profile_id].append(version)
        self.current_versions[profile_id] = version

        print(
            f"Added version {version.version} for profile {profile_id} "
            f"(confidence: {version.profile.confidence:.0%})"
        )

    def create_improved_version(
        self,
        profile_id: str,
        improved_profile: MasteringProfile,
        improvement_reason: str,
        training_source: str,
        confidence_change: float = 0.0,
    ) -> ProfileVersion:
        """
        Create a new version from an improved profile.

        Args:
            profile_id: Profile to improve
            improved_profile: Updated profile with improvements
            improvement_reason: Why this improvement was made
            training_source: Album/source that triggered improvement
            confidence_change: Change in confidence (e.g., +0.05)

        Returns:
            New ProfileVersion (automatically becomes current)
        """
        current = self.current_versions.get(profile_id)
        if not current:
            raise ValueError(f"No current version for profile {profile_id}")

        # Calculate new version number
        next_version = self._increment_version(current.version)

        version = ProfileVersion(
            version=next_version,
            profile=improved_profile,
            improved_from=current.version,
            improvement_reason=improvement_reason,
            training_source=training_source,
            confidence_change=confidence_change,
        )

        self.add_version(profile_id, version)
        return version

    @staticmethod
    def _increment_version(current_version: str) -> str:
        """
        Increment version number (semantic versioning).

        Examples:
            "1.0" → "1.1"
            "1.9" → "2.0"
            "2.3" → "2.4"
        """
        parts = current_version.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid version format: {current_version}")

        major, minor = int(parts[0]), int(parts[1])

        # Increment minor version
        minor += 1

        # Roll over to next major if minor reaches 10
        if minor >= 10:
            major += 1
            minor = 0

        return f"{major}.{minor}"

    def get_version(self, profile_id: str, version: str) -> Optional[ProfileVersion]:
        """
        Get a specific version of a profile.

        Args:
            profile_id: Profile identifier
            version: Version string (e.g., "1.0", "1.1")

        Returns:
            ProfileVersion or None if not found
        """
        if profile_id not in self.histories:
            return None

        for pv in self.histories[profile_id]:
            if pv.version == version:
                return pv

        return None

    def get_current_version(self, profile_id: str) -> Optional[ProfileVersion]:
        """Get the current (latest) version of a profile."""
        return self.current_versions.get(profile_id)

    def get_history(self, profile_id: str) -> List[ProfileVersion]:
        """Get complete version history for a profile."""
        return self.histories.get(profile_id, [])

    def list_profiles(self) -> List[str]:
        """List all profiles being versioned."""
        return list(self.current_versions.keys())

    def compare_versions(
        self, profile_id: str, version1: str, version2: str
    ) -> Dict[str, Any]:
        """
        Compare two versions of a profile.

        Args:
            profile_id: Profile identifier
            version1: First version (e.g., "1.0")
            version2: Second version (e.g., "1.1")

        Returns:
            Dictionary of changes between versions
        """
        v1 = self.get_version(profile_id, version1)
        v2 = self.get_version(profile_id, version2)

        if not v1 or not v2:
            raise ValueError(f"Version not found for profile {profile_id}")

        changes = {
            'version1': version1,
            'version2': version2,
            'loudness_change_diff': (
                v2.profile.processing_targets.loudness_change_db
                - v1.profile.processing_targets.loudness_change_db
            ),
            'crest_change_diff': (
                v2.profile.processing_targets.crest_change_db
                - v1.profile.processing_targets.crest_change_db
            ),
            'centroid_change_diff': (
                v2.profile.processing_targets.centroid_change_hz
                - v1.profile.processing_targets.centroid_change_hz
            ),
            'confidence_change': v2.profile.confidence - v1.profile.confidence,
            'detection_rules_changed': (
                v1.profile.detection_rules != v2.profile.detection_rules
            ),
            'improvement_reason': v2.improvement_reason,
            'training_source': v2.training_source,
        }

        return changes

    def export_history(self, output_path: str) -> None:
        """
        Export complete version history to JSON.

        Args:
            output_path: Path to save history file
        """
        data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'profiles': {},
        }

        for profile_id, versions in self.histories.items():
            data['profiles'][profile_id] = {
                'current_version': self.current_versions[profile_id].version,
                'version_count': len(versions),
                'versions': [v.to_dict() for v in versions],
            }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported version history for {len(self.histories)} profiles to {output_path}")

    def import_history(self, input_path: str) -> None:
        """
        Import version history from JSON.

        Args:
            input_path: Path to history file
        """
        with open(input_path, 'r') as f:
            data = json.load(f)

        count = 0
        for profile_id, profile_data in data['profiles'].items():
            for version_data in profile_data['versions']:
                profile = MasteringProfile.from_dict(version_data['profile'])
                version = ProfileVersion(
                    version=version_data['version'],
                    profile=profile,
                    created_at=version_data['created_at'],
                    improved_from=version_data.get('improved_from'),
                    improvement_reason=version_data.get('improvement_reason', ''),
                    training_source=version_data.get('training_source', ''),
                    confidence_change=version_data.get('confidence_change', 0.0),
                )
                self.add_version(profile_id, version)
                count += 1

        print(f"Imported {count} versions for {len(data['profiles'])} profiles")

    def summary(self) -> str:
        """Generate summary of all versioned profiles."""
        lines = [
            'Profile Version Summary',
            '=' * 70,
        ]

        for profile_id in sorted(self.current_versions.keys()):
            current = self.current_versions[profile_id]
            history = self.histories[profile_id]

            lines.append(f'\n{current.profile.name}')
            lines.append(f'  ID: {profile_id}')
            lines.append(f'  Current: v{current.version} ({current.profile.confidence:.0%})')
            lines.append(f'  Versions: {len(history)}')

            if len(history) > 1:
                for v in history[:-1]:
                    lines.append(f'    • v{v.version}: {v.improvement_reason or "Initial"}')

        return '\n'.join(lines)


# Example usage and testing
if __name__ == '__main__':
    print('Profile Versioning System - Ready for deployment')
