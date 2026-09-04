"""
Track Model
~~~~~~~~~~~

ORM model for audio tracks (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .album import Album
    from .artist import Artist
    from .fingerprint import SimilarityGraph, TrackFingerprint
    from .genre import Genre
    from .playlist import Playlist

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

from ._helpers import _safe_collection, _safe_scalar
from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist


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
            album = _safe_scalar(self, 'album')
            album_title = album.title if album else None
            album_artwork = None
            if album and album.artwork_path:
                album_artwork = f"/api/albums/{album.id}/artwork"

            artist_names = [
                artist.name for artist in _safe_collection(self, 'artists')
            ]
            genre_names = [genre.name for genre in _safe_collection(self, 'genres')]

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
