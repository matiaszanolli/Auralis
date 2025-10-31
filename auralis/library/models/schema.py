# -*- coding: utf-8 -*-

"""
Schema Models
~~~~~~~~~~~~~

Models for database schema version tracking

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Text

from .base import Base


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
