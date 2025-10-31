# -*- coding: utf-8 -*-

"""
Fingerprint Models
~~~~~~~~~~~~~~~~~~

Models for 25D audio fingerprints and similarity graph

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class TrackFingerprint(Base, TimestampMixin):
    """Model for 25D audio fingerprints used in similarity analysis.

    Stores multi-dimensional acoustic fingerprints for cross-genre music
    discovery and intelligent recommendations.

    Fingerprint Dimensions (25D):
    - Frequency Distribution (7D): Energy distribution across frequency bands
    - Dynamics (3D): Loudness and dynamic range characteristics
    - Temporal (4D): Rhythm, tempo, and temporal patterns
    - Spectral (3D): Brightness, tonal vs percussive characteristics
    - Harmonic (3D): Harmonic content and pitch stability
    - Variation (3D): Dynamic and loudness variation over time
    - Stereo (2D): Stereo width and phase correlation
    """
    __tablename__ = 'track_fingerprints'

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Frequency Distribution (7 dimensions)
    sub_bass_pct = Column(Float, nullable=False)     # % energy in sub-bass (20-60 Hz)
    bass_pct = Column(Float, nullable=False)          # % energy in bass (60-250 Hz)
    low_mid_pct = Column(Float, nullable=False)       # % energy in low-mids (250-500 Hz)
    mid_pct = Column(Float, nullable=False)           # % energy in mids (500-2k Hz)
    upper_mid_pct = Column(Float, nullable=False)     # % energy in upper-mids (2k-4k Hz)
    presence_pct = Column(Float, nullable=False)      # % energy in presence (4k-6k Hz)
    air_pct = Column(Float, nullable=False)           # % energy in air (6k-20k Hz)

    # Dynamics (3 dimensions)
    lufs = Column(Float, nullable=False)              # Integrated loudness (LUFS)
    crest_db = Column(Float, nullable=False)          # Crest factor in dB
    bass_mid_ratio = Column(Float, nullable=False)    # Bass to mid energy ratio

    # Temporal (4 dimensions)
    tempo_bpm = Column(Float, nullable=False)         # Detected tempo in BPM
    rhythm_stability = Column(Float, nullable=False)  # Rhythm consistency (0-1)
    transient_density = Column(Float, nullable=False) # Transients per second
    silence_ratio = Column(Float, nullable=False)     # % below -60 dB

    # Spectral (3 dimensions)
    spectral_centroid = Column(Float, nullable=False) # Brightness
    spectral_rolloff = Column(Float, nullable=False)  # 85% energy frequency
    spectral_flatness = Column(Float, nullable=False) # Tonality vs noise

    # Harmonic (3 dimensions)
    harmonic_ratio = Column(Float, nullable=False)    # Harmonic vs percussive
    pitch_stability = Column(Float, nullable=False)   # Pitch consistency
    chroma_energy = Column(Float, nullable=False)     # Chroma strength

    # Variation (3 dimensions)
    dynamic_range_variation = Column(Float, nullable=False)  # DR variation
    loudness_variation_std = Column(Float, nullable=False)   # Loudness STD
    peak_consistency = Column(Float, nullable=False)         # Peak consistency

    # Stereo (2 dimensions)
    stereo_width = Column(Float, nullable=False)      # Stereo width (0-1)
    phase_correlation = Column(Float, nullable=False) # Phase correlation

    # Metadata
    fingerprint_version = Column(Integer, nullable=False, default=1)

    # Relationship
    track = relationship("Track", backref="fingerprint", uselist=False)

    def to_dict(self) -> dict:
        """Convert fingerprint to dictionary"""
        return {
            'id': self.id,
            'track_id': self.track_id,
            # Frequency (7D)
            'frequency': {
                'sub_bass_pct': self.sub_bass_pct,
                'bass_pct': self.bass_pct,
                'low_mid_pct': self.low_mid_pct,
                'mid_pct': self.mid_pct,
                'upper_mid_pct': self.upper_mid_pct,
                'presence_pct': self.presence_pct,
                'air_pct': self.air_pct,
            },
            # Dynamics (3D)
            'dynamics': {
                'lufs': self.lufs,
                'crest_db': self.crest_db,
                'bass_mid_ratio': self.bass_mid_ratio,
            },
            # Temporal (4D)
            'temporal': {
                'tempo_bpm': self.tempo_bpm,
                'rhythm_stability': self.rhythm_stability,
                'transient_density': self.transient_density,
                'silence_ratio': self.silence_ratio,
            },
            # Spectral (3D)
            'spectral': {
                'spectral_centroid': self.spectral_centroid,
                'spectral_rolloff': self.spectral_rolloff,
                'spectral_flatness': self.spectral_flatness,
            },
            # Harmonic (3D)
            'harmonic': {
                'harmonic_ratio': self.harmonic_ratio,
                'pitch_stability': self.pitch_stability,
                'chroma_energy': self.chroma_energy,
            },
            # Variation (3D)
            'variation': {
                'dynamic_range_variation': self.dynamic_range_variation,
                'loudness_variation_std': self.loudness_variation_std,
                'peak_consistency': self.peak_consistency,
            },
            # Stereo (2D)
            'stereo': {
                'stereo_width': self.stereo_width,
                'phase_correlation': self.phase_correlation,
            },
            'fingerprint_version': self.fingerprint_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_vector(self) -> list:
        """Convert fingerprint to 25D vector for distance calculations.

        Returns:
            List of 25 float values in fixed order
        """
        return [
            # Frequency (7D)
            self.sub_bass_pct,
            self.bass_pct,
            self.low_mid_pct,
            self.mid_pct,
            self.upper_mid_pct,
            self.presence_pct,
            self.air_pct,
            # Dynamics (3D)
            self.lufs,
            self.crest_db,
            self.bass_mid_ratio,
            # Temporal (4D)
            self.tempo_bpm,
            self.rhythm_stability,
            self.transient_density,
            self.silence_ratio,
            # Spectral (3D)
            self.spectral_centroid,
            self.spectral_rolloff,
            self.spectral_flatness,
            # Harmonic (3D)
            self.harmonic_ratio,
            self.pitch_stability,
            self.chroma_energy,
            # Variation (3D)
            self.dynamic_range_variation,
            self.loudness_variation_std,
            self.peak_consistency,
            # Stereo (2D)
            self.stereo_width,
            self.phase_correlation,
        ]


class SimilarityGraph(Base, TimestampMixin):
    """Model for K-nearest neighbors similarity graph.

    Stores pre-computed similarity relationships for fast queries.
    Each row represents an edge in the similarity graph.
    """
    __tablename__ = 'similarity_graph'

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False)
    similar_track_id = Column(Integer, ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False)
    distance = Column(Float, nullable=False)
    similarity_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)  # 1=most similar, 2=second most, etc.

    # Relationships
    track = relationship("Track", foreign_keys=[track_id], backref="similar_tracks")
    similar_track = relationship("Track", foreign_keys=[similar_track_id])

    def to_dict(self) -> dict:
        """Convert similarity edge to dictionary"""
        return {
            'id': self.id,
            'track_id': self.track_id,
            'similar_track_id': self.similar_track_id,
            'distance': self.distance,
            'similarity_score': self.similarity_score,
            'rank': self.rank,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
