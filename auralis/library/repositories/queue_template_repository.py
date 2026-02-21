"""
Queue Template Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for queue template persistence and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable

from sqlalchemy.orm import Session

from ..models import QueueTemplate


class QueueTemplateRepository:
    """Repository for queue template CRUD operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize queue template repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def create(self, name: str, track_ids: list[int], is_shuffled: bool = False,
               repeat_mode: str = 'off', description: str | None = None,
               tags: list[str] | None = None) -> QueueTemplate:
        """
        Create a new queue template

        Args:
            name: Template name
            track_ids: List of track IDs in template
            is_shuffled: Shuffle mode setting
            repeat_mode: Repeat mode setting ('off', 'all', 'one')
            description: Optional template description
            tags: Optional list of tags for organization

        Returns:
            Created QueueTemplate object

        Raises:
            ValueError: If repeat_mode is invalid
        """
        if repeat_mode not in ('off', 'all', 'one'):
            raise ValueError(f"Invalid repeat_mode: {repeat_mode}")

        session = self.get_session()
        try:
            template = QueueTemplate(
                name=name,
                track_ids=json.dumps(track_ids),
                is_shuffled=is_shuffled,
                repeat_mode=repeat_mode,
                description=description,
                tags=json.dumps(tags or [])
            )

            session.add(template)
            session.commit()
            session.refresh(template)
            session.expunge(template)
            return template
        finally:
            session.close()

    def get_by_id(self, template_id: int) -> QueueTemplate | None:
        """
        Get template by ID

        Args:
            template_id: Template ID

        Returns:
            QueueTemplate or None if not found
        """
        session = self.get_session()
        try:
            template = session.query(QueueTemplate).filter(
                QueueTemplate.id == template_id
            ).first()
            if template:
                session.expunge(template)
            return template
        finally:
            session.close()

    def get_all(self, sort_by: str = 'created_at', ascending: bool = False) -> list[QueueTemplate]:
        """
        Get all templates with optional sorting

        Args:
            sort_by: Field to sort by ('name', 'created_at', 'load_count', 'updated_at')
            ascending: Sort direction (default: newest first for created_at)

        Returns:
            List of QueueTemplate objects
        """
        valid_sorts = ('name', 'created_at', 'load_count', 'updated_at')
        if sort_by not in valid_sorts:
            sort_by = 'created_at'

        session = self.get_session()
        try:
            query = session.query(QueueTemplate)

            if sort_by == 'name':
                query = query.order_by(QueueTemplate.name.asc() if ascending else QueueTemplate.name.desc())
            elif sort_by == 'load_count':
                query = query.order_by(QueueTemplate.load_count.desc() if not ascending else QueueTemplate.load_count.asc())
            elif sort_by == 'updated_at':
                query = query.order_by(QueueTemplate.updated_at.desc() if not ascending else QueueTemplate.updated_at.asc())
            else:  # created_at
                query = query.order_by(QueueTemplate.created_at.desc() if not ascending else QueueTemplate.created_at.asc())

            templates = query.all()
            for template in templates:
                session.expunge(template)
            return templates
        finally:
            session.close()

    def get_favorites(self) -> list[QueueTemplate]:
        """
        Get all favorite templates

        Returns:
            List of favorite QueueTemplate objects
        """
        session = self.get_session()
        try:
            templates = session.query(QueueTemplate).filter(
                QueueTemplate.is_favorite == True
            ).order_by(QueueTemplate.created_at.desc()).all()
            for template in templates:
                session.expunge(template)
            return templates
        finally:
            session.close()

    def get_by_tag(self, tag: str) -> list[QueueTemplate]:
        """
        Get templates by tag

        Args:
            tag: Tag to search for

        Returns:
            List of matching QueueTemplate objects
        """
        session = self.get_session()
        try:
            # Use SQL LIKE on the JSON string to avoid loading the full table (fixes #2249).
            # Tags are stored as JSON arrays (e.g. '["rock", "chill"]'), so matching
            # the quoted tag value is sufficient and avoids false positives.
            templates = session.query(QueueTemplate).filter(
                QueueTemplate.tags.like(f'%"{tag}"%')
            ).all()
            for template in templates:
                session.expunge(template)
            return templates
        finally:
            session.close()

    def update(self, template_id: int, **kwargs: Any) -> QueueTemplate | None:
        """
        Update template fields

        Args:
            template_id: Template ID
            **kwargs: Fields to update (name, track_ids, is_shuffled, repeat_mode, description, tags, is_favorite)

        Returns:
            Updated QueueTemplate or None if not found

        Raises:
            ValueError: If repeat_mode is invalid
        """
        session = self.get_session()
        try:
            template = session.query(QueueTemplate).filter(
                QueueTemplate.id == template_id
            ).first()

            if not template:
                return None

            # Validate repeat_mode if provided
            if 'repeat_mode' in kwargs and kwargs['repeat_mode'] not in ('off', 'all', 'one'):
                raise ValueError(f"Invalid repeat_mode: {kwargs['repeat_mode']}")

            # Handle track_ids serialization
            if 'track_ids' in kwargs and isinstance(kwargs['track_ids'], list):
                kwargs['track_ids'] = json.dumps(kwargs['track_ids'])

            # Handle tags serialization
            if 'tags' in kwargs and isinstance(kwargs['tags'], list):
                kwargs['tags'] = json.dumps(kwargs['tags'])

            # Whitelist of mutable fields — prevents ORM internal state corruption
            # via _sa_instance_state, id, created_at, etc. (fixes #2240)
            ALLOWED_FIELDS = {
                'name', 'description', 'track_ids', 'is_shuffled',
                'repeat_mode', 'tags', 'is_favorite',
            }
            for key, value in kwargs.items():
                if key in ALLOWED_FIELDS:
                    setattr(template, key, value)

            session.commit()
            session.refresh(template)
            session.expunge(template)
            return template
        finally:
            session.close()

    def toggle_favorite(self, template_id: int) -> QueueTemplate | None:
        """
        Toggle favorite status for a template

        Args:
            template_id: Template ID

        Returns:
            Updated QueueTemplate or None if not found
        """
        session = self.get_session()
        try:
            template = session.query(QueueTemplate).filter(
                QueueTemplate.id == template_id
            ).first()

            if not template:
                return None

            template.is_favorite = not template.is_favorite  # type: ignore[assignment]
            session.commit()
            session.refresh(template)
            session.expunge(template)
            return template
        finally:
            session.close()

    def increment_load_count(self, template_id: int) -> QueueTemplate | None:
        """
        Increment the load count when template is loaded

        Args:
            template_id: Template ID

        Returns:
            Updated QueueTemplate or None if not found
        """
        session = self.get_session()
        try:
            template = session.query(QueueTemplate).filter(
                QueueTemplate.id == template_id
            ).first()

            if not template:
                return None

            template.load_count += 1  # type: ignore[assignment]
            template.last_loaded = datetime.now(timezone.utc)  # type: ignore[assignment]
            session.commit()
            session.refresh(template)
            session.expunge(template)
            return template
        finally:
            session.close()

    def delete(self, template_id: int) -> bool:
        """
        Delete a template

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        session = self.get_session()
        try:
            template = session.query(QueueTemplate).filter(
                QueueTemplate.id == template_id
            ).first()

            if not template:
                return False

            session.delete(template)
            session.commit()
            return True
        finally:
            session.close()

    def get_count(self) -> int:
        """
        Get total number of templates

        Returns:
            Total template count
        """
        session = self.get_session()
        try:
            count = session.query(QueueTemplate).count()
            return count
        finally:
            session.close()

    def to_dict(self, template: QueueTemplate) -> dict[str, Any]:
        """
        Convert QueueTemplate to dictionary

        Args:
            template: QueueTemplate object

        Returns:
            Dictionary representation of template
        """
        return template.to_dict() if template else {
            'name': '',
            'track_ids': [],
            'is_shuffled': False,
            'repeat_mode': 'off',
            'description': None,
            'tags': [],
            'is_favorite': False,
            'load_count': 0,
            'last_loaded': None,
        }

    def search(self, query: str) -> list[QueueTemplate]:
        """
        Search templates by name or description

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        session = self.get_session()
        try:
            query.lower()
            templates = session.query(QueueTemplate).filter(
                (QueueTemplate.name.ilike(f'%{query}%')) |
                (QueueTemplate.description.ilike(f'%{query}%'))
            ).all()
            for template in templates:
                session.expunge(template)
            return templates
        finally:
            session.close()

    def delete_all(self) -> int:
        """
        Delete all templates (dangerous operation)

        Returns:
            Number of templates deleted
        """
        session = self.get_session()
        try:
            count = session.query(QueueTemplate).count()
            session.query(QueueTemplate).delete()
            session.commit()
            return count
        finally:
            session.close()
