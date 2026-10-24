"""
Adaptive Mastering Engine

The core classification and recommendation system that:
1. Analyzes incoming audio to extract fingerprints
2. Compares against known mastering profiles
3. Recommends appropriate mastering strategy
4. Predicts processing targets
5. Tracks predictions vs. actual results for continuous learning

This replaces preset-based mastering with adaptive profile matching.
"""

from .mastering_fingerprint import MasteringFingerprint
from .mastering_profile import MasteringProfile, MasteringProfileDatabase
from .mastering_profiles_builtin import (
    PROFILE_BRIGHT_MASTERS,
    PROFILE_DAMAGED_RESTORATION,
    PROFILE_HIRES_MASTERS,
    PROFILE_HOLY_DIVER,
    PROFILE_QUIET_REFERENCE,
    PROFILE_SODA_STEREO,
    PROFILE_WARM_MASTERS,
)
from .mastering_recommendation import MasteringRecommendation, ProfileWeight


class AdaptiveMasteringEngine:
    """
    Core engine for adaptive mastering classification.

    Usage:
        engine = AdaptiveMasteringEngine()
        fingerprint = MasteringFingerprint.from_audio_file("track.flac")
        recommendation = engine.recommend(fingerprint)
        print(recommendation.summary())
    """

    def __init__(self) -> None:
        self.profile_db = MasteringProfileDatabase()
        self._init_default_profiles()

    def _init_default_profiles(self) -> None:
        """Initialize with default profiles from analysis."""
        self.profile_db.add_profile(PROFILE_SODA_STEREO)
        self.profile_db.add_profile(PROFILE_QUIET_REFERENCE)
        self.profile_db.add_profile(PROFILE_DAMAGED_RESTORATION)
        self.profile_db.add_profile(PROFILE_HOLY_DIVER)

        # Priority improvements profiles (from multi-style test suite)
        self.profile_db.add_profile(PROFILE_HIRES_MASTERS)
        self.profile_db.add_profile(PROFILE_BRIGHT_MASTERS)
        self.profile_db.add_profile(PROFILE_WARM_MASTERS)

    def recommend(self, fingerprint: MasteringFingerprint, top_k: int = 3) -> MasteringRecommendation:
        """
        Get mastering recommendation for a fingerprint.

        Args:
            fingerprint: Audio fingerprint to analyze
            top_k: Number of alternative profiles to consider

        Returns:
            MasteringRecommendation with primary profile and alternatives
        """
        # Rank profiles by similarity
        rankings = self.profile_db.rank_profiles(fingerprint, top_k=top_k)

        if not rankings:
            # Fallback: recommend based on loudness alone
            return self._fallback_recommendation()

        # Primary profile is top match
        primary_profile, confidence = rankings[0]

        # Alternatives are remaining matches
        alternatives = [profile for profile, _ in rankings[1:]] if len(rankings) > 1 else []

        # Build recommendation
        rec = MasteringRecommendation(
            primary_profile=primary_profile,
            confidence_score=confidence,
            alternative_profiles=alternatives,
            predicted_loudness_change=primary_profile.processing_targets.loudness_change_db,
            predicted_crest_change=primary_profile.processing_targets.crest_change_db,
            predicted_centroid_change=primary_profile.processing_targets.centroid_change_hz,
        )

        # Generate reasoning
        rec.reasoning = self._generate_reasoning(fingerprint, confidence)

        return rec

    def recommend_weighted(self, fingerprint: MasteringFingerprint, confidence_threshold: float = 0.4, top_k: int = 3) -> MasteringRecommendation:
        """
        Get weighted mastering recommendation for hybrid mastering scenarios.

        When the top profile has low confidence, blends multiple profiles
        proportionally to their match scores for better hybrid recommendations.

        Args:
            fingerprint: Audio fingerprint to analyze
            confidence_threshold: If top profile confidence is below this, create blend
            top_k: Number of profiles to consider for weighting

        Returns:
            MasteringRecommendation with weighted_profiles if hybrid, else primary only
        """
        # Get top ranking profiles
        rankings = self.profile_db.rank_profiles(fingerprint, top_k=top_k)

        if not rankings:
            return self._fallback_recommendation()

        primary_profile, confidence = rankings[0]
        alternatives = [profile for profile, _ in rankings[1:]] if len(rankings) > 1 else []

        # If confidence is high, return single-profile recommendation
        if confidence >= confidence_threshold:
            rec = MasteringRecommendation(
                primary_profile=primary_profile,
                confidence_score=confidence,
                alternative_profiles=alternatives,
                predicted_loudness_change=primary_profile.processing_targets.loudness_change_db,
                predicted_crest_change=primary_profile.processing_targets.crest_change_db,
                predicted_centroid_change=primary_profile.processing_targets.centroid_change_hz,
            )
            rec.reasoning = self._generate_reasoning(fingerprint, confidence)
            return rec

        # Low confidence: create weighted blend from top N profiles
        weighted_profiles = []
        total_confidence = sum(conf for _, conf in rankings)

        # Calculate weights proportional to confidence scores
        for profile, conf in rankings:
            if conf > 0:  # Only include profiles with positive match
                weight = conf / total_confidence
                weighted_profiles.append(ProfileWeight(profile=profile, weight=weight))

        # Calculate blended processing targets
        blended_loudness = sum(pw.profile.processing_targets.loudness_change_db * pw.weight
                              for pw in weighted_profiles)
        blended_crest = sum(pw.profile.processing_targets.crest_change_db * pw.weight
                           for pw in weighted_profiles)
        blended_centroid = sum(pw.profile.processing_targets.centroid_change_hz * pw.weight
                              for pw in weighted_profiles)

        # Build recommendation with weighted profiles
        rec = MasteringRecommendation(
            primary_profile=primary_profile,
            confidence_score=confidence,
            alternative_profiles=alternatives,
            weighted_profiles=weighted_profiles,
            predicted_loudness_change=blended_loudness,
            predicted_crest_change=blended_crest,
            predicted_centroid_change=blended_centroid,
        )

        # Generate reasoning for hybrid recommendation
        reasons = []
        reasons.append(f"Hybrid mastering detected (low single-profile confidence: {confidence:.0%})")
        reasons.append(f"Blend: " + " + ".join(f"{pw.profile.name}({pw.weight:.0%})" for pw in weighted_profiles))
        rec.reasoning = " → ".join(reasons)

        return rec

    def _fallback_recommendation(self) -> MasteringRecommendation:
        """Fallback when no profiles match."""
        # Default to quiet-reference profile for safety
        profile = self.profile_db.get_profile("quiet-reference-modernization-v1")
        if not profile:
            profile = PROFILE_QUIET_REFERENCE

        return MasteringRecommendation(
            primary_profile=profile,
            confidence_score=0.5,
            predicted_loudness_change=0.0,
            predicted_crest_change=0.0,
            predicted_centroid_change=0.0,
            reasoning="No strong profile match found. Using conservative defaults.",
        )

    def _generate_reasoning(self, fingerprint: MasteringFingerprint,
                           confidence: float) -> str:
        """Generate human-readable explanation."""
        reasons = []

        # Loudness assessment
        if fingerprint.loudness_dbfs < -18:
            reasons.append(f"Very quiet original ({fingerprint.loudness_dbfs:.1f} dBFS)")
        elif fingerprint.loudness_dbfs > -12:
            reasons.append(f"Loud original ({fingerprint.loudness_dbfs:.1f} dBFS)")
        else:
            reasons.append(f"Moderate loudness ({fingerprint.loudness_dbfs:.1f} dBFS)")

        # Dynamics assessment
        if fingerprint.crest_db > 16:
            reasons.append("Excellent dynamic range (likely reference quality)")
        elif fingerprint.crest_db < 10:
            reasons.append("Heavily compressed (potential over-compression)")
        else:
            reasons.append(f"Normal compression ({fingerprint.crest_db:.1f} dB crest)")

        # Noise assessment
        if fingerprint.zero_crossing_rate > 0.095:
            reasons.append("Noisy/artifact-heavy (damaged source)")
        elif fingerprint.zero_crossing_rate < 0.07:
            reasons.append("Clean recording (low noise floor)")
        else:
            reasons.append("Normal noise level")

        # Tone assessment
        if fingerprint.spectral_centroid > 3500:
            reasons.append("Bright/harsh tone (may need de-essing)")
        elif fingerprint.spectral_centroid < 2800:
            reasons.append("Dark/warm tone (needs presence boost)")
        else:
            reasons.append("Balanced tone")

        reasoning = " + ".join(reasons)
        reasoning += f" → Match confidence: {confidence:.0%}"

        return reasoning

    def add_profile(self, profile: MasteringProfile) -> None:
        """Add a new profile to the engine."""
        self.profile_db.add_profile(profile)

    def list_profiles(self) -> list[MasteringProfile]:
        """List all available profiles."""
        return self.profile_db.list_profiles()

    def describe_profile(self, profile_id: str) -> str:
        """Get description of a specific profile."""
        return self.profile_db.describe_profile(profile_id)


# Example usage and testing
if __name__ == "__main__":
    pass

    print("Adaptive Mastering Engine Example")
    print("=" * 60)

    # Create engine
    engine = AdaptiveMasteringEngine()

    # Show available profiles
    print("\nAvailable Profiles:")
    print("-" * 60)
    for profile in engine.list_profiles():
        print(f"  • {profile.name} (v{profile.version})")
        print(f"    Confidence: {profile.confidence:.0%}")
        print()

    # Example: recommend for a fingerprint matching Holy Diver characteristics
    print("\nExample Recommendation (Holy Diver-like audio):")
    print("-" * 60)

    from .mastering_fingerprint import MasteringFingerprint

    # Create a sample fingerprint with Holy Diver characteristics
    sample_fp = MasteringFingerprint(
        loudness_dbfs=-17.0,
        peak_dbfs=-0.1,
        crest_db=17.0,
        spectral_centroid=3100,
        spectral_rolloff=6200,
        zero_crossing_rate=0.084,
        spectral_spread=3200,
    )

    rec = engine.recommend(sample_fp)
    print(rec.summary())

    print("\n" + "=" * 60)
    print("Engine ready for integration with Auralis")
