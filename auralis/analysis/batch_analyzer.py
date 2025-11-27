"""
Batch Analysis Framework

Converts analysis results (markdown, raw audio) into structured mastering profiles.
Enables iterative refinement of the adaptive mastering engine through real-world data.

Features:
1. Analyze album directories to extract fingerprints
2. Compare originals vs. remasters to calculate deltas
3. Build mastering profiles from analysis results
4. Version profiles for continuous improvement
5. Export/import profiles as YAML for persistence
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime
import numpy as np

from .mastering_fingerprint import MasteringFingerprint, analyze_album, compare_albums
from .mastering_profile import (
    MasteringProfile,
    MasteringProfileDatabase,
    DetectionRules,
    ProcessingTargets,
)


@dataclass
class AlbumAnalysisResult:
    """Complete analysis of an album (original + remaster comparison)."""

    album_name: str
    year: int
    release_type: str  # "live", "studio", "damaged", "reference", etc.
    genre: str

    # Original audio metrics (averaged across tracks)
    orig_loudness: float
    orig_crest: float
    orig_centroid: float
    orig_rolloff: float
    orig_zcr: float
    orig_spread: float

    # Remaster audio metrics (if available)
    remaster_loudness: Optional[float] = None
    remaster_crest: Optional[float] = None
    remaster_centroid: Optional[float] = None
    remaster_rolloff: Optional[float] = None
    remaster_zcr: Optional[float] = None
    remaster_spread: Optional[float] = None

    # Calculated changes
    loudness_change: Optional[float] = None
    crest_change: Optional[float] = None
    centroid_change: Optional[float] = None
    rolloff_change: Optional[float] = None
    zcr_change: Optional[float] = None
    spread_change: Optional[float] = None

    # Track count
    track_count: int = 0

    # Analysis metadata
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 0.85
    notes: str = ""

    def calculate_changes(self) -> None:
        """Calculate delta metrics if remaster available."""
        if self.remaster_loudness is not None:
            self.loudness_change = self.remaster_loudness - self.orig_loudness
        if self.remaster_crest is not None:
            self.crest_change = self.remaster_crest - self.orig_crest
        if self.remaster_centroid is not None:
            self.centroid_change = self.remaster_centroid - self.orig_centroid
        if self.remaster_rolloff is not None:
            self.rolloff_change = self.remaster_rolloff - self.orig_rolloff
        if self.remaster_zcr is not None:
            self.zcr_change = self.remaster_zcr - self.orig_zcr
        if self.remaster_spread is not None:
            self.spread_change = self.remaster_spread - self.orig_spread

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'album_name': self.album_name,
            'year': self.year,
            'release_type': self.release_type,
            'genre': self.genre,
            'track_count': self.track_count,
            'original': {
                'loudness_dbfs': float(self.orig_loudness),
                'crest_db': float(self.orig_crest),
                'centroid_hz': float(self.orig_centroid),
                'rolloff_hz': float(self.orig_rolloff),
                'zcr': float(self.orig_zcr),
                'spread_hz': float(self.orig_spread),
            },
            'remaster': {
                'loudness_dbfs': float(self.remaster_loudness) if self.remaster_loudness else None,
                'crest_db': float(self.remaster_crest) if self.remaster_crest else None,
                'centroid_hz': float(self.remaster_centroid) if self.remaster_centroid else None,
                'rolloff_hz': float(self.remaster_rolloff) if self.remaster_rolloff else None,
                'zcr': float(self.remaster_zcr) if self.remaster_zcr else None,
                'spread_hz': float(self.remaster_spread) if self.remaster_spread else None,
            } if self.remaster_loudness else None,
            'changes': {
                'loudness_db': float(self.loudness_change) if self.loudness_change else None,
                'crest_db': float(self.crest_change) if self.crest_change else None,
                'centroid_hz': float(self.centroid_change) if self.centroid_change else None,
                'rolloff_hz': float(self.rolloff_change) if self.rolloff_change else None,
                'zcr': float(self.zcr_change) if self.zcr_change else None,
                'spread_hz': float(self.spread_change) if self.spread_change else None,
            } if self.loudness_change is not None else None,
            'analyzed_at': self.analyzed_at,
            'confidence': float(self.confidence),
            'notes': self.notes,
        }


class BatchAnalyzer:
    """
    Batch analysis framework for converting audio analysis into mastering profiles.

    Workflow:
    1. Analyze album directories (with MasteringFingerprint)
    2. Compare originals vs. remasters
    3. Build mastering profiles from patterns
    4. Version and track improvements
    5. Export for integration with adaptive engine
    """

    def __init__(self):
        self.analyses: Dict[str, AlbumAnalysisResult] = {}
        self.profiles: Dict[str, MasteringProfile] = {}
        self.profile_db = MasteringProfileDatabase()

    def analyze_album_pair(
        self,
        album_name: str,
        year: int,
        release_type: str,
        genre: str,
        original_dir: str,
        remaster_dir: Optional[str] = None,
        notes: str = "",
    ) -> AlbumAnalysisResult:
        """
        Analyze an album (original and optionally remaster).

        Args:
            album_name: Album name (e.g., "Dio - Holy Diver")
            year: Recording year
            release_type: "live", "studio", "damaged", "reference", etc.
            genre: Genre (e.g., "rock", "metal", "pop")
            original_dir: Directory with original audio files
            remaster_dir: Directory with remastered audio (optional)
            notes: Additional notes about the album

        Returns:
            AlbumAnalysisResult with fingerprints and metrics
        """
        # Analyze original
        orig_analysis = analyze_album(original_dir)

        # Extract averages from album analysis
        orig_stats = orig_analysis['statistics']

        result = AlbumAnalysisResult(
            album_name=album_name,
            year=year,
            release_type=release_type,
            genre=genre,
            orig_loudness=orig_stats['avg_loudness'],
            orig_crest=orig_stats['avg_crest'],
            orig_centroid=orig_stats['avg_centroid'],
            orig_rolloff=orig_stats['avg_rolloff'],
            orig_zcr=orig_stats['avg_zcr'],
            orig_spread=orig_stats['avg_spread'],
            track_count=orig_analysis['track_count'],
            confidence=0.85,
            notes=notes,
        )

        # Analyze remaster if available
        if remaster_dir:
            remaster_analysis = analyze_album(remaster_dir)
            remaster_stats = remaster_analysis['statistics']

            result.remaster_loudness = remaster_stats['avg_loudness']
            result.remaster_crest = remaster_stats['avg_crest']
            result.remaster_centroid = remaster_stats['avg_centroid']
            result.remaster_rolloff = remaster_stats['avg_rolloff']
            result.remaster_zcr = remaster_stats['avg_zcr']
            result.remaster_spread = remaster_stats['avg_spread']

        # Calculate changes
        result.calculate_changes()

        # Store in analyses
        self.analyses[album_name] = result

        return result

    def build_profile_from_analysis(
        self,
        analysis: AlbumAnalysisResult,
        profile_id: str,
        profile_name: str,
        confidence: float = 0.85,
        version: str = "1.0",
    ) -> MasteringProfile:
        """
        Build a mastering profile from analysis results.

        Args:
            analysis: AlbumAnalysisResult to convert
            profile_id: Unique profile ID
            profile_name: Human-readable profile name
            confidence: Profile confidence (0-1)
            version: Profile version

        Returns:
            MasteringProfile ready for database
        """
        # Detection rules based on original metrics
        detection_rules = DetectionRules(
            loudness_min=analysis.orig_loudness - 1.5,
            loudness_max=analysis.orig_loudness + 1.5,
            crest_min=analysis.orig_crest - 2.0,
            crest_max=analysis.orig_crest + 2.0,
            zcr_min=analysis.orig_zcr - 0.02,
            zcr_max=analysis.orig_zcr + 0.02,
            centroid_min=analysis.orig_centroid - 200,
            centroid_max=analysis.orig_centroid + 200,
        )

        # Processing targets based on changes (if remaster available)
        if analysis.loudness_change is not None:
            processing_targets = ProcessingTargets(
                loudness_change_db=analysis.loudness_change,
                crest_change_db=analysis.crest_change or 0.0,
                centroid_change_hz=analysis.centroid_change or 0.0,
                target_loudness_db=analysis.remaster_loudness,
                description=self._generate_strategy_description(analysis),
            )
        else:
            # No remaster available - estimate based on type
            processing_targets = ProcessingTargets(
                loudness_change_db=self._estimate_loudness_change(analysis),
                crest_change_db=self._estimate_crest_change(analysis),
                centroid_change_hz=self._estimate_centroid_change(analysis),
                description=f"Estimated strategy for {analysis.release_type} recording",
            )

        # Build profile
        profile = MasteringProfile(
            profile_id=profile_id,
            name=profile_name,
            detection_rules=detection_rules,
            processing_targets=processing_targets,
            source_albums=[analysis.album_name],
            training_tracks=analysis.track_count,
            confidence=confidence,
            version=version,
            release_type=analysis.release_type,
            genre_hint=analysis.genre,
            era_estimate=analysis.year,
            notes=analysis.notes,
        )

        self.profiles[profile_id] = profile
        return profile

    def _generate_strategy_description(self, analysis: AlbumAnalysisResult) -> str:
        """Generate human-readable strategy description from analysis."""
        parts = []

        # Loudness strategy
        if analysis.loudness_change:
            if analysis.loudness_change > 3:
                parts.append("aggressive modernization with loudness restoration")
            elif analysis.loudness_change > 1:
                parts.append("moderate loudness boost")
            elif analysis.loudness_change < -2:
                parts.append("significant loudness reduction for headroom")
            else:
                parts.append("minimal loudness change")

        # Crest strategy
        if analysis.crest_change:
            if abs(analysis.crest_change) < 1:
                parts.append("preserve dynamics")
            elif analysis.crest_change > 1:
                parts.append("expand dynamics")
            else:
                parts.append("add compression")

        # Centroid strategy
        if analysis.centroid_change:
            if analysis.centroid_change > 200:
                parts.append("significant brightening")
            elif analysis.centroid_change > 50:
                parts.append("add presence and air")
            elif analysis.centroid_change < -100:
                parts.append("aggressive de-essing")
            else:
                parts.append("subtle EQ adjustment")

        strategy = ", ".join(parts) if parts else "standard mastering"
        return f"{analysis.release_type.capitalize()} recording: {strategy}"

    def _estimate_loudness_change(self, analysis: AlbumAnalysisResult) -> float:
        """Estimate loudness change based on release type and original loudness."""
        # Quiet reference masters (< -18 dBFS) get light touch
        if analysis.orig_loudness < -18:
            return -1.0
        # Quiet but modernizable (-17 to -15 dBFS)
        elif analysis.orig_loudness < -15:
            return 3.0  # Modernize
        # Moderate loudness (-14 to -12 dBFS)
        elif analysis.orig_loudness < -12:
            return -2.0  # Decompress
        # Loud (> -12 dBFS)
        else:
            return -3.0

    def _estimate_crest_change(self, analysis: AlbumAnalysisResult) -> float:
        """Estimate crest factor change based on original metrics."""
        if analysis.orig_crest < 10:
            return 2.0  # Expand compressed audio
        elif analysis.orig_crest > 16:
            return -1.0  # Compress dynamic audio for loudness
        else:
            return 0.5  # Minimal compression

    def _estimate_centroid_change(self, analysis: AlbumAnalysisResult) -> float:
        """Estimate centroid change based on original brightness."""
        if analysis.orig_centroid > 3500:
            return -150  # De-ess bright audio
        elif analysis.orig_centroid < 3000:
            return 300  # Brighten dark audio
        else:
            return 100  # Moderate brightening

    def export_profiles_yaml(self, output_path: str) -> None:
        """Export all built profiles to YAML file."""
        try:
            import yaml
        except ImportError:
            print("Warning: yaml not available, using JSON instead")
            return self.export_profiles_json(output_path)

        db = MasteringProfileDatabase()
        for profile in self.profiles.values():
            db.add_profile(profile)

        db.to_yaml_file(output_path)
        print(f"Exported {len(self.profiles)} profiles to {output_path}")

    def export_profiles_json(self, output_path: str) -> None:
        """Export all built profiles to JSON file."""
        data = {
            'version': '1.0',
            'generated': datetime.now().isoformat(),
            'profile_count': len(self.profiles),
            'profiles': [profile.to_dict() for profile in self.profiles.values()],
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(self.profiles)} profiles to {output_path}")

    def export_analyses_json(self, output_path: str) -> None:
        """Export all analysis results to JSON file."""
        data = {
            'version': '1.0',
            'generated': datetime.now().isoformat(),
            'analysis_count': len(self.analyses),
            'analyses': [analysis.to_dict() for analysis in self.analyses.values()],
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(self.analyses)} analyses to {output_path}")

    def list_analyses(self) -> List[AlbumAnalysisResult]:
        """List all completed analyses."""
        return list(self.analyses.values())

    def list_profiles(self) -> List[MasteringProfile]:
        """List all built profiles."""
        return list(self.profiles.values())

    def summary(self) -> str:
        """Generate summary of all analyses and profiles."""
        lines = [
            "Batch Analysis Summary",
            "=" * 60,
            f"\nAnalyses: {len(self.analyses)}",
        ]

        for analysis in self.analyses.values():
            lines.append(f"  • {analysis.album_name} ({analysis.year}, {analysis.release_type})")
            if analysis.loudness_change:
                lines.append(f"    Loudness: {analysis.loudness_change:+.2f} dB")

        lines.extend([
            f"\nProfiles: {len(self.profiles)}",
        ])

        for profile in self.profiles.values():
            lines.append(f"  • {profile.name} (v{profile.version})")

        return "\n".join(lines)


if __name__ == "__main__":
    print("Batch Analyzer - Ready to convert analyses into profiles")
