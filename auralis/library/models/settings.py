"""
Settings Models
~~~~~~~~~~~~~~~

Models for user settings and preferences

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserSettings(Base, TimestampMixin):  # type: ignore[misc]
    """Model for user settings and preferences."""
    __tablename__ = 'user_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Library Settings
    scan_folders: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of folder paths
    file_types: Mapped[Optional[str]] = mapped_column(Text, default='mp3,flac,wav,m4a,ogg,aac,wma')  # Comma-separated
    auto_scan: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_interval: Mapped[int] = mapped_column(Integer, default=3600)  # Seconds

    # Playback Settings
    crossfade_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    crossfade_duration: Mapped[float] = mapped_column(Float, default=5.0)  # Seconds
    gapless_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    replay_gain_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    volume: Mapped[float] = mapped_column(Float, default=0.8)  # 0.0-1.0

    # Audio Settings
    output_device: Mapped[Optional[str]] = mapped_column(String, default='default')
    bit_depth: Mapped[int] = mapped_column(Integer, default=16)  # 16, 24, 32
    sample_rate: Mapped[int] = mapped_column(Integer, default=44100)  # Hz

    # Interface Settings
    theme: Mapped[Optional[str]] = mapped_column(String, default='dark')
    language: Mapped[Optional[str]] = mapped_column(String, default='en')
    show_visualizations: Mapped[bool] = mapped_column(Boolean, default=True)
    mini_player_on_close: Mapped[bool] = mapped_column(Boolean, default=False)

    # Enhancement Settings
    default_preset: Mapped[Optional[str]] = mapped_column(String, default='adaptive')
    auto_enhance: Mapped[bool] = mapped_column(Boolean, default=False)
    enhancement_intensity: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0-1.0

    # Advanced Settings
    cache_size: Mapped[int] = mapped_column(Integer, default=1024)  # MB
    max_concurrent_scans: Mapped[int] = mapped_column(Integer, default=4)
    enable_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    debug_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary"""
        import json

        # Parse scan_folders from JSON if it exists
        scan_folders_list = []
        if self.scan_folders:
            try:
                scan_folders_list = json.loads(self.scan_folders)
            except Exception:
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
