"""
Core Database Models
~~~~~~~~~~~~~~~~~~~~

Core models for tracks, albums, artists, genres, and playlists

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fingerprint import SimilarityGraph, TrackFingerprint

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist


class Track(Base, TimestampMixin):  # type: ignore[misc]
    """Model for audio tracks."""
    __tablename__ = 'tracks'
    __table_args__ = (
        Index('ix_tracks_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    duration: Mapped[float | None] = mapped_column(Float)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    bit_depth: Mapped[int | None] = mapped_column(Integer)
    bitrate: Mapped[int | None] = mapped_column(Integer)  # kbps; matches the field listed in TrackRepository.update (fixes #2411)
    channels: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str | None] = mapped_column(String)
    filesize: Mapped[int | None] = mapped_column(Integer)

    # Audio analysis data
    peak_level: Mapped[float | None] = mapped_column(Float)
    rms_level: Mapped[float | None] = mapped_column(Float)
    dr_rating: Mapped[float | None] = mapped_column(Float)  # Dynamic Range rating
    lufs_level: Mapped[float | None] = mapped_column(Float)  # LUFS loudness

    # Auralis-specific analysis
    mastering_quality: Mapped[float | None] = mapped_column(Float)  # Quality score 0-1
    recommended_reference: Mapped[str | None] = mapped_column(String)  # Best reference track path
    processing_profile: Mapped[str | None] = mapped_column(String)  # Optimal mastering profile

    # 25D Fingerprint analysis
    fingerprint_status: Mapped[str | None] = mapped_column(String, default='pending')  # pending, processing, complete, error
    fingerprint_computed_at: Mapped[datetime | None] = mapped_column(DateTime)  # When fingerprint was last computed
    fingerprint_error_message: Mapped[str | None] = mapped_column(Text)  # Error message if extraction failed
    fingerprint_vector: Mapped[str | None] = mapped_column(Text)  # Serialized 25D fingerprint (JSON)

    # Metadata
    album_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('albums.id'))
    track_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[str | None] = mapped_column(Text)
    lyrics: Mapped[str | None] = mapped_column(Text)  # Plain text or LRC format lyrics

    # Playback statistics
    play_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    last_played: Mapped[datetime | None] = mapped_column(DateTime)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relationships
    album: Mapped[Album | None] = relationship("Album", back_populates="tracks")
    artists: Mapped[list[Artist]] = relationship("Artist", secondary=track_artist, back_populates="tracks")
    genres: Mapped[list[Genre]] = relationship("Genre", secondary=track_genre, back_populates="tracks")
    playlists: Mapped[list[Playlist]] = relationship("Playlist", secondary=track_playlist, back_populates="tracks")
    fingerprint: Mapped[TrackFingerprint | None] = relationship("TrackFingerprint", back_populates="track", uselist=False)
    similar_tracks: Mapped[list[SimilarityGraph]] = relationship("SimilarityGraph", foreign_keys="[SimilarityGraph.track_id]", back_populates="track")

    def to_dict(self) -> dict[str, Any]:
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
            except Exception:
                album_title = None
                album_artwork = None

            artist_names = []
            try:
                artist_names = [artist.name for artist in self.artists]
            except Exception:
                artist_names = []

            genre_names = []
            try:
                genre_names = [genre.name for genre in self.genres]
            except Exception:
                genre_names = []

            return {
                'id': self.id,
                'title': self.title,
                'duration': self.duration,
                'sample_rate': self.sample_rate,
                'bit_depth': self.bit_depth,
                'bitrate': self.bitrate,
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
        except Exception:
            # Fallback for detached objects
            return {
                'id': getattr(self, 'id', None),
                'title': getattr(self, 'title', 'Unknown'),
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('artists.id'))
    year: Mapped[int | None] = mapped_column(Integer)
    total_tracks: Mapped[int | None] = mapped_column(Integer)
    total_discs: Mapped[int | None] = mapped_column(Integer)

    # Album artwork
    artwork_path: Mapped[str | None] = mapped_column(String)  # Path to extracted album artwork

    # Album-level analysis
    avg_dr_rating: Mapped[float | None] = mapped_column(Float)
    avg_lufs: Mapped[float | None] = mapped_column(Float)
    mastering_consistency: Mapped[float | None] = mapped_column(Float)  # How consistent the mastering is across tracks

    # Relationships
    artist: Mapped[Artist | None] = relationship("Artist", back_populates="albums")
    tracks: Mapped[list[Track]] = relationship("Track", back_populates="album")

    def to_dict(self) -> dict[str, Any]:
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
            'artwork_url': artwork_url,  # API URL, not filesystem path
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'mastering_consistency': self.mastering_consistency,
            'artist': self.artist.name if self.artist else None,
            'track_count': len(self.tracks),
            'total_duration': sum(t.duration for t in self.tracks if t.duration),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Artist(Base, TimestampMixin):  # type: ignore[misc]
    """Model for artists."""
    __tablename__ = 'artists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    normalized_name: Mapped[str | None] = mapped_column(String, index=True)  # Canonical form for duplicate detection

    # Artist statistics
    total_plays: Mapped[int] = mapped_column(Integer, default=0)
    avg_mastering_quality: Mapped[float | None] = mapped_column(Float)

    # Artwork metadata (Phase 2: Real artist imagery)
    artwork_url: Mapped[str | None] = mapped_column(Text)  # External URL to artist image
    artwork_source: Mapped[str | None] = mapped_column(String)  # 'musicbrainz', 'discogs', 'lastfm', etc.
    artwork_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)  # Last fetch timestamp

    # Relationships
    albums: Mapped[list[Album]] = relationship("Album", back_populates="artist")
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_artist, back_populates="artists")

    def to_dict(self) -> dict[str, Any]:
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Genre characteristics for auto-mastering
    preferred_profile: Mapped[str | None] = mapped_column(String, default='balanced')  # warm, bright, punchy, balanced
    typical_dr_range: Mapped[str | None] = mapped_column(String)  # "8-12" for example
    typical_lufs_range: Mapped[str | None] = mapped_column(String)  # "-14 to -10" for example

    # Relationships
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_genre, back_populates="genres")

    def to_dict(self) -> dict[str, Any]:
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_smart: Mapped[bool] = mapped_column(Boolean, default=False)
    smart_criteria: Mapped[str | None] = mapped_column(Text)  # JSON string for smart playlist rules

    # Playlist-level mastering settings
    auto_master_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mastering_profile: Mapped[str | None] = mapped_column(String, default='balanced')
    normalize_levels: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_playlist, back_populates="playlists")

    def to_dict(self) -> dict[str, Any]:
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
            # Alias for frontend compatibility — frontend Playlist type uses modified_at (fixes #2269)
            'modified_at': self.updated_at.isoformat() if self.updated_at else None,
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Queue composition - stored as JSON list of track IDs
    # Example: "[1, 5, 3, 7]" - order matters
    track_ids: Mapped[str] = mapped_column(Text, default='[]', nullable=False)

    # Current playback position in queue
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Shuffle mode toggle
    is_shuffled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Repeat mode: 'off', 'all', or 'one'
    repeat_mode: Mapped[str] = mapped_column(String, default='off', nullable=False)

    # Timestamp for optimistic sync detection
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert queue state to dictionary"""
        import json
        try:
            parsed_track_ids = json.loads(self.track_ids) if self.track_ids else []
            track_ids: list[int] = parsed_track_ids if isinstance(parsed_track_ids, list) else []
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
    def from_dict(data: dict[str, Any]) -> QueueState:
        """Create QueueState from dictionary"""
        import json
        state = QueueState()
        state.track_ids = json.dumps(data.get('track_ids', []))
        state.current_index = int(data.get('current_index', 0))
        state.is_shuffled = bool(data.get('is_shuffled', False))
        state.repeat_mode = str(data.get('repeat_mode', 'off'))
        return state


class QueueHistory(Base, TimestampMixin):  # type: ignore[misc]
    """
    Model for tracking queue state history for undo/redo operations.

    Stores snapshots of queue state at each operation, limiting to 20 most recent
    for memory efficiency while preserving undo/redo functionality.
    """
    __tablename__ = 'queue_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Reference to queue state (for tracking which queue this history belongs to)
    queue_state_id: Mapped[int] = mapped_column(Integer, ForeignKey('queue_state.id'), nullable=False)

    # Type of operation that triggered this history entry
    # Valid values: 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear'
    operation: Mapped[str] = mapped_column(String, nullable=False)

    # Full snapshot of queue state before the operation
    # Stored as JSON to capture: track_ids, current_index, is_shuffled, repeat_mode
    state_snapshot: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional metadata about the operation
    # For 'add'/'remove': contains index or track_id
    # For 'reorder': contains fromIndex and toIndex
    # For 'shuffle': contains shuffle_mode info
    operation_metadata: Mapped[str | None] = mapped_column(Text, default='{}')

    def to_dict(self) -> dict[str, Any]:
        """Convert history entry to dictionary"""
        import json
        try:
            parsed_snapshot = json.loads(self.state_snapshot) if self.state_snapshot else {}
            state_snapshot: dict[str, Any] = parsed_snapshot if isinstance(parsed_snapshot, dict) else {}
        except (json.JSONDecodeError, TypeError):
            state_snapshot = {}

        try:
            parsed_metadata = json.loads(self.operation_metadata) if self.operation_metadata else {}
            operation_metadata: dict[str, Any] = parsed_metadata if isinstance(parsed_metadata, dict) else {}
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
    def from_dict(data: dict[str, Any]) -> QueueHistory:
        """Create QueueHistory from dictionary"""
        import json
        entry = QueueHistory()
        entry.queue_state_id = int(data.get('queue_state_id', 1))
        entry.operation = str(data.get('operation', 'set'))
        entry.state_snapshot = json.dumps(data.get('state_snapshot', {}))
        entry.operation_metadata = json.dumps(data.get('operation_metadata', {}))
        return entry


class QueueTemplate(Base, TimestampMixin):  # type: ignore[misc]
    """
    Model for saving and restoring queue configurations (templates).

    Allows users to save their current queue configuration and restore it later.
    Templates include tracks, shuffle mode, and repeat mode settings.
    """
    __tablename__ = 'queue_template'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Template name for user identification
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Track IDs in the template queue
    track_ids: Mapped[str] = mapped_column(Text, default='[]', nullable=False)

    # Shuffle setting when template was saved
    is_shuffled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Repeat mode when template was saved
    repeat_mode: Mapped[str] = mapped_column(String, default='off', nullable=False)

    # Optional description/notes about the template
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Template tags for organization
    tags: Mapped[str] = mapped_column(Text, default='[]', nullable=False)

    # Whether this is a favorite/starred template
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Number of times this template has been loaded
    load_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Last time this template was loaded
    last_loaded: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary"""
        import json
        try:
            parsed_track_ids = json.loads(self.track_ids) if self.track_ids else []
            track_ids: list[int] = parsed_track_ids if isinstance(parsed_track_ids, list) else []
        except (json.JSONDecodeError, TypeError):
            track_ids = []

        try:
            parsed_tags = json.loads(self.tags) if self.tags else []
            tags: list[str] = parsed_tags if isinstance(parsed_tags, list) else []
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
    def from_dict(data: dict[str, Any]) -> QueueTemplate:
        """Create QueueTemplate from dictionary"""
        import json
        template = QueueTemplate()
        template.name = str(data.get('name', 'Untitled Template'))
        template.track_ids = json.dumps(data.get('track_ids', []))
        template.is_shuffled = bool(data.get('is_shuffled', False))
        template.repeat_mode = str(data.get('repeat_mode', 'off'))
        template.description = data.get('description', None)
        template.tags = json.dumps(data.get('tags', []))
        template.is_favorite = bool(data.get('is_favorite', False))
        return template
