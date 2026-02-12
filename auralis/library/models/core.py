# -*- coding: utf-8 -*-

"""
Core Database Models
~~~~~~~~~~~~~~~~~~~~

Core models for tracks, albums, artists, genres, and playlists

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist


class Track(Base, TimestampMixin):  # type: ignore[misc]
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

    # 25D Fingerprint analysis
    fingerprint_status = Column(String, default='pending')  # pending, processing, complete, error
    fingerprint_computed_at = Column(DateTime)  # When fingerprint was last computed
    fingerprint_error_message = Column(Text)  # Error message if extraction failed
    fingerprint_vector = Column(Text)  # Serialized 25D fingerprint (JSON)

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

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert track to dictionary for API/GUI use.

        Returns album artwork as API URL instead of filesystem path.
        """
        try:
            # Safe access to relationship attributes
            album_title = None
            album_artwork = None
            try:
                album_title = self.album.title if self.album else None
                # Convert filesystem path to API URL if artwork exists
                if self.album and hasattr(self.album, 'artwork_path') and self.album.artwork_path:
                    album_artwork = f"/api/albums/{self.album.id}/artwork"
            except:
                album_title = None
                album_artwork = None

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
                'artwork_url': album_artwork,  # Standardized field name (was album_art)
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


class Album(Base, TimestampMixin):  # type: ignore[misc]
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

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert album to dictionary.

        Returns artwork_path as API URL instead of filesystem path
        to prevent leaking internal paths and enable browser loading.
        """
        # Convert filesystem path to API URL if artwork exists
        artwork_url = None
        if self.artwork_path:
            artwork_url = f"/api/albums/{self.id}/artwork"

        return {
            'id': self.id,
            'title': self.title,
            'artist_id': self.artist_id,
            'year': self.year,
            'total_tracks': self.total_tracks,
            'total_discs': self.total_discs,
            'artwork_path': artwork_url,  # API URL, not filesystem path
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'mastering_consistency': self.mastering_consistency,
            'artist': self.artist.name if self.artist else None,
            'track_count': len(self.tracks),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Artist(Base, TimestampMixin):  # type: ignore[misc]
    """Model for artists."""
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    normalized_name = Column(String, index=True)  # Canonical form for duplicate detection

    # Artist statistics
    total_plays = Column(Integer, default=0)
    avg_mastering_quality = Column(Float)

    # Artwork metadata (Phase 2: Real artist imagery)
    artwork_url = Column(Text)  # External URL to artist image
    artwork_source = Column(String)  # 'musicbrainz', 'discogs', 'lastfm', etc.
    artwork_fetched_at = Column(DateTime)  # Last fetch timestamp

    # Relationships
    albums = relationship("Album", back_populates="artist")
    tracks = relationship("Track", secondary=track_artist, back_populates="artists")

    def to_dict(self) -> Dict[str, Any]:
        """Convert artist to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'normalized_name': self.normalized_name,
            'total_plays': self.total_plays,
            'avg_mastering_quality': self.avg_mastering_quality,
            'album_count': len(self.albums),
            'track_count': len(self.tracks),
            'artwork_url': self.artwork_url,  # Include artwork URL
            'artwork_source': self.artwork_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Genre(Base, TimestampMixin):  # type: ignore[misc]
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

    def to_dict(self) -> Dict[str, Any]:
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


class Playlist(Base, TimestampMixin):  # type: ignore[misc]
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

    def to_dict(self) -> Dict[str, Any]:
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


class QueueState(Base, TimestampMixin):  # type: ignore[misc]
    """
    Model for persisting playback queue state.

    Stores the current playback queue configuration including:
    - List of tracks in queue
    - Current playback index
    - Shuffle mode state
    - Repeat mode setting
    """
    __tablename__ = 'queue_state'

    id = Column(Integer, primary_key=True)

    # Queue composition - stored as JSON list of track IDs
    # Example: "[1, 5, 3, 7]" - order matters
    track_ids = Column(Text, default='[]', nullable=False)

    # Current playback position in queue
    current_index = Column(Integer, default=0, nullable=False)

    # Shuffle mode toggle
    is_shuffled = Column(Boolean, default=False, nullable=False)

    # Repeat mode: 'off', 'all', or 'one'
    repeat_mode = Column(String, default='off', nullable=False)

    # Timestamp for optimistic sync detection
    synced_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert queue state to dictionary"""
        import json
        try:
            parsed_track_ids = json.loads(self.track_ids) if self.track_ids else []  # type: ignore[arg-type]
            track_ids: List[int] = parsed_track_ids if isinstance(parsed_track_ids, list) else []
        except (json.JSONDecodeError, TypeError):
            track_ids = []

        return {
            'id': self.id,
            'track_ids': track_ids,
            'current_index': self.current_index,
            'is_shuffled': self.is_shuffled,
            'repeat_mode': self.repeat_mode,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'QueueState':
        """Create QueueState from dictionary"""
        import json
        state = QueueState()
        state.track_ids = json.dumps(data.get('track_ids', []))  # type: ignore[assignment]
        state.current_index = int(data.get('current_index', 0))  # type: ignore[assignment]
        state.is_shuffled = bool(data.get('is_shuffled', False))  # type: ignore[assignment]
        state.repeat_mode = str(data.get('repeat_mode', 'off'))  # type: ignore[assignment]
        return state


class QueueHistory(Base, TimestampMixin):  # type: ignore[misc]
    """
    Model for tracking queue state history for undo/redo operations.

    Stores snapshots of queue state at each operation, limiting to 20 most recent
    for memory efficiency while preserving undo/redo functionality.
    """
    __tablename__ = 'queue_history'

    id = Column(Integer, primary_key=True)

    # Reference to queue state (for tracking which queue this history belongs to)
    queue_state_id = Column(Integer, ForeignKey('queue_state.id'), nullable=False)

    # Type of operation that triggered this history entry
    # Valid values: 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear'
    operation = Column(String, nullable=False)

    # Full snapshot of queue state before the operation
    # Stored as JSON to capture: track_ids, current_index, is_shuffled, repeat_mode
    state_snapshot = Column(Text, nullable=False)

    # Optional metadata about the operation
    # For 'add'/'remove': contains index or track_id
    # For 'reorder': contains fromIndex and toIndex
    # For 'shuffle': contains shuffle_mode info
    operation_metadata = Column(Text, default='{}')

    def to_dict(self) -> Dict[str, Any]:
        """Convert history entry to dictionary"""
        import json
        try:
            parsed_snapshot = json.loads(self.state_snapshot) if self.state_snapshot else {}  # type: ignore[arg-type]
            state_snapshot: Dict[str, Any] = parsed_snapshot if isinstance(parsed_snapshot, dict) else {}
        except (json.JSONDecodeError, TypeError):
            state_snapshot = {}

        try:
            parsed_metadata = json.loads(self.operation_metadata) if self.operation_metadata else {}  # type: ignore[arg-type]
            operation_metadata: Dict[str, Any] = parsed_metadata if isinstance(parsed_metadata, dict) else {}
        except (json.JSONDecodeError, TypeError):
            operation_metadata = {}

        return {
            'id': self.id,
            'queue_state_id': self.queue_state_id,
            'operation': self.operation,
            'state_snapshot': state_snapshot,
            'operation_metadata': operation_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'QueueHistory':
        """Create QueueHistory from dictionary"""
        import json
        entry = QueueHistory()
        entry.queue_state_id = int(data.get('queue_state_id', 1))  # type: ignore[assignment]
        entry.operation = str(data.get('operation', 'set'))  # type: ignore[assignment]
        entry.state_snapshot = json.dumps(data.get('state_snapshot', {}))  # type: ignore[assignment]
        entry.operation_metadata = json.dumps(data.get('operation_metadata', {}))  # type: ignore[assignment]
        return entry


class QueueTemplate(Base, TimestampMixin):  # type: ignore[misc]
    """
    Model for saving and restoring queue configurations (templates).

    Allows users to save their current queue configuration and restore it later.
    Templates include tracks, shuffle mode, and repeat mode settings.
    """
    __tablename__ = 'queue_template'

    id = Column(Integer, primary_key=True)

    # Template name for user identification
    name = Column(String, nullable=False)

    # Track IDs in the template queue
    track_ids = Column(Text, default='[]', nullable=False)

    # Shuffle setting when template was saved
    is_shuffled = Column(Boolean, default=False, nullable=False)

    # Repeat mode when template was saved
    repeat_mode = Column(String, default='off', nullable=False)

    # Optional description/notes about the template
    description = Column(Text, nullable=True)

    # Template tags for organization
    tags = Column(Text, default='[]', nullable=False)

    # Whether this is a favorite/starred template
    is_favorite = Column(Boolean, default=False, nullable=False)

    # Number of times this template has been loaded
    load_count = Column(Integer, default=0, nullable=False)

    # Last time this template was loaded
    last_loaded = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary"""
        import json
        try:
            parsed_track_ids = json.loads(self.track_ids) if self.track_ids else []  # type: ignore[arg-type]
            track_ids: List[int] = parsed_track_ids if isinstance(parsed_track_ids, list) else []
        except (json.JSONDecodeError, TypeError):
            track_ids = []

        try:
            parsed_tags = json.loads(self.tags) if self.tags else []  # type: ignore[arg-type]
            tags: List[str] = parsed_tags if isinstance(parsed_tags, list) else []
        except (json.JSONDecodeError, TypeError):
            tags = []

        return {
            'id': self.id,
            'name': self.name,
            'track_ids': track_ids,
            'is_shuffled': self.is_shuffled,
            'repeat_mode': self.repeat_mode,
            'description': self.description,
            'tags': tags,
            'is_favorite': self.is_favorite,
            'load_count': self.load_count,
            'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'QueueTemplate':
        """Create QueueTemplate from dictionary"""
        import json
        template = QueueTemplate()
        template.name = str(data.get('name', 'Untitled Template'))  # type: ignore[assignment]
        template.track_ids = json.dumps(data.get('track_ids', []))  # type: ignore[assignment]
        template.is_shuffled = bool(data.get('is_shuffled', False))  # type: ignore[assignment]
        template.repeat_mode = str(data.get('repeat_mode', 'off'))  # type: ignore[assignment]
        template.description = data.get('description', None)  # type: ignore[assignment]
        template.tags = json.dumps(data.get('tags', []))  # type: ignore[assignment]
        template.is_favorite = bool(data.get('is_favorite', False))  # type: ignore[assignment]
        return template
