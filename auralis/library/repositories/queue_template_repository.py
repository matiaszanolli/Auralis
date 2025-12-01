# -*- coding: utf-8 -*-

"""
Queue Template Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for queue template persistence and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import QueueTemplate


class QueueTemplateRepository:
    """Repository for queue template CRUD operations"""

    def __init__(self, session_factory):
        """
        Initialize queue template repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def create(self, name: str, track_ids: List[int], is_shuffled: bool = False,
               repeat_mode: str = 'off', description: Optional[str] = None,
               tags: Optional[List[str]] = None) -> QueueTemplate:
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
            return template
        finally:
            session.close()

    def get_by_id(self, template_id: int) -> Optional[QueueTemplate]:
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
            return template
        finally:
            session.close()

    def get_all(self, sort_by: str = 'created_at', ascending: bool = False) -> List[QueueTemplate]:
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
            return templates
        finally:
            session.close()

    def get_favorites(self) -> List[QueueTemplate]:
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
            return templates
        finally:
            session.close()

    def get_by_tag(self, tag: str) -> List[QueueTemplate]:
        """
        Get templates by tag

        Args:
            tag: Tag to search for

        Returns:
            List of matching QueueTemplate objects
        """
        session = self.get_session()
        try:
            templates = session.query(QueueTemplate).all()
            matching = []

            for template in templates:
                try:
                    tags = json.loads(template.tags) if template.tags else []
                    if tag in tags:
                        matching.append(template)
                except (json.JSONDecodeError, TypeError):
                    pass

            return matching
        finally:
            session.close()

    def update(self, template_id: int, **kwargs) -> Optional[QueueTemplate]:
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

            # Update fields
            for key, value in kwargs.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            session.commit()
            session.refresh(template)
            return template
        finally:
            session.close()

    def toggle_favorite(self, template_id: int) -> Optional[QueueTemplate]:
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

            template.is_favorite = not template.is_favorite
            session.commit()
            session.refresh(template)
            return template
        finally:
            session.close()

    def increment_load_count(self, template_id: int) -> Optional[QueueTemplate]:
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

            template.load_count += 1
            template.last_loaded = datetime.utcnow()
            session.commit()
            session.refresh(template)
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

    def to_dict(self, template: QueueTemplate) -> Dict[str, Any]:
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

    def search(self, query: str) -> List[QueueTemplate]:
        """
        Search templates by name or description

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        session = self.get_session()
        try:
            query_lower = query.lower()
            templates = session.query(QueueTemplate).filter(
                (QueueTemplate.name.ilike(f'%{query}%')) |
                (QueueTemplate.description.ilike(f'%{query}%'))
            ).all()
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
