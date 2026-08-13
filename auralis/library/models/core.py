"""
Core Database Models
~~~~~~~~~~~~~~~~~~~~

Core models for tracks, albums, artists, genres, and playlists

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

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
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist

logger = logging.getLogger(__name__)


def _safe_collection(instance: Any, attr: str) -> list[Any]:
    """
    Read a relationship collection, degrading to `[]` instead of raising.

    Every `to_dict()` in this module runs on instances the repositories have
    `expunge()`d from their session, so a relationship that was not
    eager-loaded raises `DetachedInstanceError` on first access. The
    repositories' `selectinload()` options are the *primary* guarantee that
    these values are correct; this helper is the backstop that turns a missed
    eager-load into a degraded field rather than an unhandled 500 far from
    its cause (#4500, #4641).

    A miss is logged at WARNING so it is diagnosable — a silently-empty
    collection is exactly how #4500 hid for as long as it did. Callers that
    need to distinguish "empty" from "unavailable" must not rely on the
    returned length alone.
    """
    try:
        return list(getattr(instance, attr))
    except Exception:
        logger.warning(
            "%s.%s could not be loaded (detached instance?); "
            "reporting it as empty. The owning repository is missing a "
            "selectinload(%s.%s).",
            type(instance).__name__, attr, type(instance).__name__, attr,
        )
        return []


def _safe_scalar(instance: Any, attr: str) -> Any | None:
    """
    Read a scalar (many-to-one) relationship, degrading to `None`.

    Same rationale as :func:`_safe_collection` — see #4641.
    """
    try:
        return getattr(instance, attr)
    except Exception:
        logger.warning(
            "%s.%s could not be loaded (detached instance?); reporting None. "
            "The owning repository is missing a joinedload/selectinload(%s.%s).",
            type(instance).__name__, attr, type(instance).__name__, attr,
        )
        return None


class Track(Base, TimestampMixin):
    """Model for audio tracks."""
    __tablename__ = 'tracks'
    __table_args__ = (
        Index('ix_tracks_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # The path exactly as discovered — this is the string used to open the file,
    # so it must keep its real case.
    filepath: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # #4842: the value lookups actually compare. Derived by
    # auralis.library.path_key.make_filepath_key(), which case-folds on
    # Windows/macOS (case-insensitive filesystems) and preserves case on Linux.
    # `filepath`'s own unique constraint cannot prevent the duplicate this
    # guards, because it only rejects an *identical* string — two differently
    # cased spellings of one physical file pass it happily.
    #
    # Nullable so the v017->v018 migration can add the column before the
    # backfill runs; every write path populates it.
    filepath_key: Mapped[str | None] = mapped_column(String, unique=True, index=True)
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
    # passive_deletes=True defers child removal to the DB's ondelete='CASCADE'
    # (#4598). Both children declare track_id as nullable=False; without this
    # SQLAlchemy's unit-of-work loads them on delete and issues
    # `UPDATE ... SET track_id=NULL` first, violating the NOT NULL constraint —
    # so deleting any fingerprinted track raised IntegrityError, which
    # TrackRepository.delete()'s blanket except swallowed as a plain False.
    fingerprint: Mapped[TrackFingerprint | None] = relationship(
        "TrackFingerprint", back_populates="track", uselist=False, passive_deletes=True
    )
    similar_tracks: Mapped[list[SimilarityGraph]] = relationship(
        "SimilarityGraph", foreign_keys="[SimilarityGraph.track_id]",
        back_populates="track", passive_deletes=True
    )

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


class Album(Base, TimestampMixin):
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

    # Populated by AlbumRepository.get_all()/.search()/.get_recent() via
    # with_expression() so a list view can report these aggregates without
    # materialising every album's whole `tracks` collection (#4777, mirrors
    # Playlist.track_count_expr/#4554). Left as None on any query that does
    # not ask for them (e.g. get_by_id/get_by_title, which legitimately need
    # the full tracks collection anyway), in which case to_dict() falls back
    # to walking `tracks`.
    track_count_expr: Mapped[int | None] = query_expression()
    total_duration_expr: Mapped[float | None] = query_expression()

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

        # Guarded relationship read (#4641) — AlbumRepository eager-loads it
        # on the paths that need it, so this is the backstop, not the
        # mechanism.
        artist = _safe_scalar(self, 'artist')

        # Prefer the SQL-computed aggregates when the query supplied them
        # (#4777), so a paginated list view never has to load the tracks
        # collection just to count()/sum() it.
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            total_duration = self.total_duration_expr or 0
        else:
            tracks = _safe_collection(self, 'tracks')
            track_count = len(tracks)
            total_duration = sum(t.duration for t in tracks if t.duration)

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
            'artist': artist.name if artist else None,
            'track_count': track_count,
            'total_duration': total_duration,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Artist(Base, TimestampMixin):
    """Model for artists."""
    __tablename__ = 'artists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    normalized_name: Mapped[str | None] = mapped_column(String, index=True)  # Canonical form for duplicate detection

    # Artist statistics
    total_plays: Mapped[int] = mapped_column(Integer, default=0)
    avg_mastering_quality: Mapped[float | None] = mapped_column(Float)

    # Artwork metadata (Phase 2: Real artist imagery)
    #
    # DELIBERATE EXCEPTION (#4526): `artwork_url` here holds an ABSOLUTE EXTERNAL
    # URL and is passed through to clients unmodified — unlike Album.to_dict()
    # and Track.to_dict(), which both rewrite their artwork to a same-origin
    # `/api/.../artwork` path. Artists have no local artwork file to serve: the
    # fetchers in auralis/services/artwork_service.py resolve a third-party CDN
    # URL and store only that, so there is nothing behind an /api path to serve.
    #
    # The consequence is that `artwork_url` carries two incompatible kinds of
    # value across the API depending on which entity it came from. Anything
    # consuming it must not assume a same-origin path — see `withArtworkSize()`
    # in the frontend, which now requires an `/api/` prefix for exactly this
    # reason. The browser is allowed to load these hosts by the `img-src`
    # allowlist in auralis-web/backend/config/middleware.py; adding a new
    # artwork source means adding its CDN host there too, or the image is
    # silently blocked and the UI falls back to a placeholder.
    artwork_url: Mapped[str | None] = mapped_column(Text)  # External URL to artist image
    artwork_source: Mapped[str | None] = mapped_column(String)  # 'musicbrainz', 'discogs', 'lastfm', etc.
    artwork_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)  # Last fetch timestamp

    # Relationships
    albums: Mapped[list[Album]] = relationship("Album", back_populates="artist")
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_artist, back_populates="artists")

    # Populated by ArtistRepository.get_all()/.search() via with_expression()
    # so a list view can report these counts without hydrating every Track row
    # belonging to every artist on the page (#5084, mirroring
    # Album.track_count_expr/#4777). Left as None on any query that does not
    # ask for them (get_by_id/get_by_name legitimately need the collections
    # anyway), in which case to_dict() falls back to walking them.
    track_count_expr: Mapped[int | None] = query_expression()
    album_count_expr: Mapped[int | None] = query_expression()

    # Distinct genre names across the artist's tracks, set by
    # ArtistRepository's list reads from one grouped query (#5084). Not a
    # mapped column and not a query_expression: SQLite's group_concat cannot
    # take both DISTINCT and a separator, and a comma-joined string would be
    # ambiguous for a genre name containing a comma. ClassVar so SQLAlchemy's
    # annotation scanning leaves it alone; None means "this query did not ask
    # for genres", which is different from "this artist has none".
    genre_names: ClassVar[list[str] | None] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert artist to dictionary"""
        # Prefer the SQL-computed counts when the query supplied them (#5084);
        # otherwise fall back to guarded relationship reads (#4641 — see
        # Album.to_dict).
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            album_count = self.album_count_expr or 0
        else:
            track_count = len(_safe_collection(self, 'tracks'))
            album_count = len(_safe_collection(self, 'albums'))

        return {
            'id': self.id,
            'name': self.name,
            'normalized_name': self.normalized_name,
            'total_plays': self.total_plays,
            'avg_mastering_quality': self.avg_mastering_quality,
            'album_count': album_count,
            'track_count': track_count,
            'artwork_url': self.artwork_url,  # Include artwork URL
            'artwork_source': self.artwork_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Set by ArtistRepository's list reads (#5084) — see genre_names.
            'genres': self.genre_names,
        }


class Genre(Base, TimestampMixin):
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
            # Guarded relationship read (#4641) — see Album.to_dict.
            'track_count': len(_safe_collection(self, 'tracks')),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Playlist(Base, TimestampMixin):
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
    # #3725: order_by the explicit `position` column on the association
    # table so the list returned to consumers is deterministic and
    # matches what add_track / reorder_track wrote, instead of
    # depending on SQLAlchemy's implicit row-insertion ordering.
    tracks: Mapped[list[Track]] = relationship(
        "Track",
        secondary=track_playlist,
        back_populates="playlists",
        order_by=track_playlist.c.position,
    )

    # Populated by PlaylistRepository.get_all() via with_expression() so a list
    # view can report these aggregates without materialising every playlist's
    # whole `tracks` collection (#4554). Left as None on any query that does not
    # ask for them, in which case to_dict() falls back to walking `tracks`.
    track_count_expr: Mapped[int | None] = query_expression()
    total_duration_expr: Mapped[float | None] = query_expression()

    def to_dict(self) -> dict[str, Any]:
        """Convert playlist to dictionary"""
        # Prefer SQL-computed aggregates when the query supplied them (#4554),
        # so a paginated list view never has to load the tracks collection.
        # Guarded relationship read (#4641) — see Album.to_dict — otherwise.
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            total_duration = self.total_duration_expr or 0
        else:
            tracks = _safe_collection(self, 'tracks')
            track_count = len(tracks)
            total_duration = sum(track.duration for track in tracks if track.duration)

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_smart': self.is_smart,
            'smart_criteria': self.smart_criteria,
            'auto_master_enabled': self.auto_master_enabled,
            'mastering_profile': self.mastering_profile,
            'normalize_levels': self.normalize_levels,
            'track_count': track_count,
            'total_duration': total_duration,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Alias for frontend compatibility — frontend Playlist type uses modified_at (fixes #2269)
            'modified_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class QueueState(Base, TimestampMixin):
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


class QueueHistory(Base, TimestampMixin):
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
