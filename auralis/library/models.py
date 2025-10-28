# -*- coding: utf-8 -*-

"""
Auralis Library Database Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database models for music library management
Integrated from existing library infrastructure

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Table, Boolean, func, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from pathlib import Path

Base = declarative_base()

# Association tables for many-to-many relationships
track_artist = Table(
    'track_artist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('artist_id', Integer, ForeignKey('artists.id'))
)

track_genre = Table(
    'track_genre', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('genre_id', Integer, ForeignKey('genres.id'))
)

track_playlist = Table(
    'track_playlist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('playlist_id', Integer, ForeignKey('playlists.id'))
)


class TimestampMixin:
    """Mixin to add creation and modification timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Track(Base, TimestampMixin):
    """Model for audio tracks."""
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    filepath = Column(String, nullable=False, unique=True)
    duration = Column(Float)
    sample_rate = Column(Integer)
    bit_depth = Column(Integer)
    channels = Column(Integer)
    format = Column(String)
    filesize = Column(Integer)

    # Audio analysis data
    peak_level = Column(Float)
    rms_level = Column(Float)
    dr_rating = Column(Float)  # Dynamic Range rating
    lufs_level = Column(Float)  # LUFS loudness

    # Auralis-specific analysis
    mastering_quality = Column(Float)  # Quality score 0-1
    recommended_reference = Column(String)  # Best reference track path
    processing_profile = Column(String)  # Optimal mastering profile

    # Metadata
    album_id = Column(Integer, ForeignKey('albums.id'))
    track_number = Column(Integer)
    disc_number = Column(Integer)
    year = Column(Integer)
    comments = Column(Text)
    lyrics = Column(Text)  # Plain text or LRC format lyrics

    # Playback statistics
    play_count = Column(Integer, default=0)
    last_played = Column(DateTime)
    skip_count = Column(Integer, default=0)
    favorite = Column(Boolean, default=False)

    # Relationships
    album = relationship("Album", back_populates="tracks")
    artists = relationship("Artist", secondary=track_artist, back_populates="tracks")
    genres = relationship("Genre", secondary=track_genre, back_populates="tracks")
    playlists = relationship("Playlist", secondary=track_playlist, back_populates="tracks")

    def to_dict(self) -> dict:
        """Convert track to dictionary for API/GUI use"""
        try:
            # Safe access to relationship attributes
            album_title = None
            try:
                album_title = self.album.title if self.album else None
            except:
                album_title = None

            artist_names = []
            try:
                artist_names = [artist.name for artist in self.artists]
            except:
                artist_names = []

            genre_names = []
            try:
                genre_names = [genre.name for genre in self.genres]
            except:
                genre_names = []

            return {
                'id': self.id,
                'title': self.title,
                'filepath': self.filepath,
                'duration': self.duration,
                'sample_rate': self.sample_rate,
                'bit_depth': self.bit_depth,
                'channels': self.channels,
                'format': self.format,
                'filesize': self.filesize,
                'peak_level': self.peak_level,
                'rms_level': self.rms_level,
                'dr_rating': self.dr_rating,
                'lufs_level': self.lufs_level,
                'mastering_quality': self.mastering_quality,
                'recommended_reference': self.recommended_reference,
                'processing_profile': self.processing_profile,
                'album_id': self.album_id,
                'track_number': self.track_number,
                'disc_number': self.disc_number,
                'year': self.year,
                'comments': self.comments,
                'lyrics': self.lyrics,
                'play_count': self.play_count,
                'last_played': self.last_played.isoformat() if self.last_played else None,
                'skip_count': self.skip_count,
                'favorite': self.favorite,
                'album': album_title,
                'artists': artist_names,
                'genres': genre_names,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            }
        except Exception as e:
            # Fallback for detached objects
            return {
                'id': getattr(self, 'id', None),
                'title': getattr(self, 'title', 'Unknown'),
                'filepath': getattr(self, 'filepath', ''),
                'duration': getattr(self, 'duration', 0),
                'sample_rate': getattr(self, 'sample_rate', 0),
                'channels': getattr(self, 'channels', 0),
                'format': getattr(self, 'format', 'Unknown'),
                'play_count': getattr(self, 'play_count', 0),
                'favorite': getattr(self, 'favorite', False),
                'album': None,
                'artists': [],
                'genres': [],
            }


class Album(Base, TimestampMixin):
    """Model for albums."""
    __tablename__ = 'albums'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    artist_id = Column(Integer, ForeignKey('artists.id'))
    year = Column(Integer)
    total_tracks = Column(Integer)
    total_discs = Column(Integer)

    # Album artwork
    artwork_path = Column(String)  # Path to extracted album artwork

    # Album-level analysis
    avg_dr_rating = Column(Float)
    avg_lufs = Column(Float)
    mastering_consistency = Column(Float)  # How consistent the mastering is across tracks

    # Relationships
    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album")

    def to_dict(self) -> dict:
        """Convert album to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'artist_id': self.artist_id,
            'year': self.year,
            'total_tracks': self.total_tracks,
            'total_discs': self.total_discs,
            'artwork_path': self.artwork_path,
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'mastering_consistency': self.mastering_consistency,
            'artist': self.artist.name if self.artist else None,
            'track_count': len(self.tracks),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Artist(Base, TimestampMixin):
    """Model for artists."""
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    # Artist statistics
    total_plays = Column(Integer, default=0)
    avg_mastering_quality = Column(Float)

    # Relationships
    albums = relationship("Album", back_populates="artist")
    tracks = relationship("Track", secondary=track_artist, back_populates="artists")

    def to_dict(self) -> dict:
        """Convert artist to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'total_plays': self.total_plays,
            'avg_mastering_quality': self.avg_mastering_quality,
            'album_count': len(self.albums),
            'track_count': len(self.tracks),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Genre(Base, TimestampMixin):
    """Model for music genres."""
    __tablename__ = 'genres'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    # Genre characteristics for auto-mastering
    preferred_profile = Column(String, default='balanced')  # warm, bright, punchy, balanced
    typical_dr_range = Column(String)  # "8-12" for example
    typical_lufs_range = Column(String)  # "-14 to -10" for example

    # Relationships
    tracks = relationship("Track", secondary=track_genre, back_populates="genres")

    def to_dict(self) -> dict:
        """Convert genre to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'preferred_profile': self.preferred_profile,
            'typical_dr_range': self.typical_dr_range,
            'typical_lufs_range': self.typical_lufs_range,
            'track_count': len(self.tracks),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Playlist(Base, TimestampMixin):
    """Model for playlists."""
    __tablename__ = 'playlists'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    is_smart = Column(Boolean, default=False)
    smart_criteria = Column(Text)  # JSON string for smart playlist rules

    # Playlist-level mastering settings
    auto_master_enabled = Column(Boolean, default=True)
    mastering_profile = Column(String, default='balanced')
    normalize_levels = Column(Boolean, default=True)

    # Relationships
    tracks = relationship("Track", secondary=track_playlist, back_populates="playlists")

    def to_dict(self) -> dict:
        """Convert playlist to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_smart': self.is_smart,
            'smart_criteria': self.smart_criteria,
            'auto_master_enabled': self.auto_master_enabled,
            'mastering_profile': self.mastering_profile,
            'normalize_levels': self.normalize_levels,
            'track_count': len(self.tracks),
            'total_duration': sum(track.duration for track in self.tracks if track.duration),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LibraryStats(Base, TimestampMixin):
    """Model for library-wide statistics."""
    __tablename__ = 'library_stats'

    id = Column(Integer, primary_key=True)
    total_tracks = Column(Integer, default=0)
    total_artists = Column(Integer, default=0)
    total_albums = Column(Integer, default=0)
    total_genres = Column(Integer, default=0)
    total_playlists = Column(Integer, default=0)
    total_duration = Column(Float, default=0.0)  # Total duration in seconds
    total_filesize = Column(Integer, default=0)  # Total filesize in bytes

    # Quality statistics
    avg_dr_rating = Column(Float)
    avg_lufs = Column(Float)
    avg_mastering_quality = Column(Float)

    # Last scan information
    last_scan_date = Column(DateTime)
    last_scan_duration = Column(Float)  # Scan duration in seconds
    files_scanned = Column(Integer, default=0)
    new_files_found = Column(Integer, default=0)

    def to_dict(self) -> dict:
        """Convert stats to dictionary"""
        return {
            'id': self.id,
            'total_tracks': self.total_tracks,
            'total_artists': self.total_artists,
            'total_albums': self.total_albums,
            'total_genres': self.total_genres,
            'total_playlists': self.total_playlists,
            'total_duration': self.total_duration,
            'total_duration_formatted': f"{self.total_duration // 3600:.0f}h {(self.total_duration % 3600) // 60:.0f}m",
            'total_filesize': self.total_filesize,
            'total_filesize_gb': self.total_filesize / (1024**3) if self.total_filesize else 0,
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'avg_mastering_quality': self.avg_mastering_quality,
            'last_scan_date': self.last_scan_date.isoformat() if self.last_scan_date else None,
            'last_scan_duration': self.last_scan_duration,
            'files_scanned': self.files_scanned,
            'new_files_found': self.new_files_found,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class UserSettings(Base, TimestampMixin):
    """Model for user settings and preferences."""
    __tablename__ = 'user_settings'

    id = Column(Integer, primary_key=True)

    # Library Settings
    scan_folders = Column(Text)  # JSON array of folder paths
    file_types = Column(Text, default='mp3,flac,wav,m4a,ogg,aac,wma')  # Comma-separated
    auto_scan = Column(Boolean, default=False)
    scan_interval = Column(Integer, default=3600)  # Seconds

    # Playback Settings
    crossfade_enabled = Column(Boolean, default=False)
    crossfade_duration = Column(Float, default=5.0)  # Seconds
    gapless_enabled = Column(Boolean, default=True)
    replay_gain_enabled = Column(Boolean, default=False)
    volume = Column(Float, default=0.8)  # 0.0-1.0

    # Audio Settings
    output_device = Column(String, default='default')
    bit_depth = Column(Integer, default=16)  # 16, 24, 32
    sample_rate = Column(Integer, default=44100)  # Hz

    # Interface Settings
    theme = Column(String, default='dark')
    language = Column(String, default='en')
    show_visualizations = Column(Boolean, default=True)
    mini_player_on_close = Column(Boolean, default=False)

    # Enhancement Settings
    default_preset = Column(String, default='adaptive')
    auto_enhance = Column(Boolean, default=False)
    enhancement_intensity = Column(Float, default=1.0)  # 0.0-1.0

    # Advanced Settings
    cache_size = Column(Integer, default=1024)  # MB
    max_concurrent_scans = Column(Integer, default=4)
    enable_analytics = Column(Boolean, default=False)
    debug_mode = Column(Boolean, default=False)

    def to_dict(self) -> dict:
        """Convert settings to dictionary"""
        import json

        # Parse scan_folders from JSON if it exists
        scan_folders_list = []
        if self.scan_folders:
            try:
                scan_folders_list = json.loads(self.scan_folders)
            except:
                scan_folders_list = []

        return {
            'id': self.id,
            # Library
            'scan_folders': scan_folders_list,
            'file_types': self.file_types.split(',') if self.file_types else [],
            'auto_scan': self.auto_scan,
            'scan_interval': self.scan_interval,
            # Playback
            'crossfade_enabled': self.crossfade_enabled,
            'crossfade_duration': self.crossfade_duration,
            'gapless_enabled': self.gapless_enabled,
            'replay_gain_enabled': self.replay_gain_enabled,
            'volume': self.volume,
            # Audio
            'output_device': self.output_device,
            'bit_depth': self.bit_depth,
            'sample_rate': self.sample_rate,
            # Interface
            'theme': self.theme,
            'language': self.language,
            'show_visualizations': self.show_visualizations,
            'mini_player_on_close': self.mini_player_on_close,
            # Enhancement
            'default_preset': self.default_preset,
            'auto_enhance': self.auto_enhance,
            'enhancement_intensity': self.enhancement_intensity,
            # Advanced
            'cache_size': self.cache_size,
            'max_concurrent_scans': self.max_concurrent_scans,
            'enable_analytics': self.enable_analytics,
            'debug_mode': self.debug_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


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


class SchemaVersion(Base):
    """Model for tracking database schema versions."""
    __tablename__ = 'schema_version'

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False, unique=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)
    migration_script = Column(Text)

    def to_dict(self) -> dict:
        """Convert schema version to dictionary"""
        return {
            'id': self.id,
            'version': self.version,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'description': self.description,
            'migration_script': self.migration_script,
        }