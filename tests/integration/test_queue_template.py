"""
Test Queue Template Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for queue template persistence and CRUD operations.

Tests verify:
- Template creation and storage
- Template retrieval and filtering
- Template updates (name, description, settings)
- Favorite/star functionality
- Load count tracking
- Template deletion
- Search and tag operations
"""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test database setup
TEST_DB_PLACEHOLDER = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DB_PATH = TEST_DB_PLACEHOLDER.name
TEST_DB_PLACEHOLDER.close()


@pytest.fixture
def test_db():
    """Create isolated test database"""
    engine = create_engine(f'sqlite:///{TEST_DB_PATH}')

    # Create tables
    from auralis.library.models import Base
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    Path(TEST_DB_PATH).unlink(missing_ok=True)


@pytest.fixture
def template_repo(test_db):
    """Create QueueTemplateRepository with test database"""
    from auralis.library.repositories import QueueTemplateRepository
    Session = sessionmaker(bind=create_engine(f'sqlite:///{TEST_DB_PATH}'))
    return QueueTemplateRepository(Session)


class TestQueueTemplateBasics:
    """Test basic template CRUD operations"""

    def test_create_template(self, template_repo):
        """Creating a template should store it in database"""
        template = template_repo.create(
            name='My Queue',
            track_ids=[1, 2, 3, 4, 5],
            is_shuffled=False,
            repeat_mode='off'
        )

        assert template is not None
        assert template.name == 'My Queue'
        assert json.loads(template.track_ids) == [1, 2, 3, 4, 5]
        assert template.is_shuffled is False
        assert template.repeat_mode == 'off'

    def test_create_with_description_and_tags(self, template_repo):
        """Template should support description and tags"""
        template = template_repo.create(
            name='Workout Mix',
            track_ids=[10, 20, 30],
            description='High energy tracks for workouts',
            tags=['workout', 'high-energy', 'playlist']
        )

        assert template.description == 'High energy tracks for workouts'
        stored_tags = json.loads(template.tags)
        assert stored_tags == ['workout', 'high-energy', 'playlist']

    def test_get_template_by_id(self, template_repo):
        """Should retrieve template by ID"""
        created = template_repo.create('Test Template', [1, 2, 3])
        retrieved = template_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.name == 'Test Template'
        assert retrieved.id == created.id

    def test_get_nonexistent_template(self, template_repo):
        """Getting nonexistent template should return None"""
        result = template_repo.get_by_id(9999)
        assert result is None

    def test_invalid_repeat_mode_raises_error(self, template_repo):
        """Invalid repeat_mode should raise ValueError"""
        with pytest.raises(ValueError, match="Invalid repeat_mode"):
            template_repo.create(
                name='Bad Template',
                track_ids=[1, 2, 3],
                repeat_mode='invalid'
            )


class TestQueueTemplateRetrieval:
    """Test template retrieval and listing"""

    def test_get_all_templates(self, template_repo):
        """Should retrieve all templates"""
        template_repo.create('Template 1', [1, 2, 3])
        template_repo.create('Template 2', [4, 5, 6])
        template_repo.create('Template 3', [7, 8, 9])

        templates = template_repo.get_all()

        assert len(templates) == 3

    def test_get_all_sorted_by_name(self, template_repo):
        """Should sort templates alphabetically by name"""
        template_repo.create('Zebra Queue', [1])
        template_repo.create('Alpha Queue', [2])
        template_repo.create('Beta Queue', [3])

        templates = template_repo.get_all(sort_by='name', ascending=True)

        names = [t.name for t in templates]
        assert names == ['Alpha Queue', 'Beta Queue', 'Zebra Queue']

    def test_get_all_sorted_by_created_date(self, template_repo):
        """Should sort by creation date (newest first)"""
        t1 = template_repo.create('Template 1', [1])
        t2 = template_repo.create('Template 2', [2])
        t3 = template_repo.create('Template 3', [3])

        templates = template_repo.get_all(sort_by='created_at')

        ids = [t.id for t in templates]
        assert ids == [t3.id, t2.id, t1.id]  # Newest first

    def test_get_templates_by_tag(self, template_repo):
        """Should retrieve templates with specific tag"""
        template_repo.create('Workout 1', [1], tags=['workout', 'cardio'])
        template_repo.create('Workout 2', [2], tags=['workout', 'strength'])
        template_repo.create('Relaxing', [3], tags=['relaxation'])

        workout_templates = template_repo.get_by_tag('workout')

        assert len(workout_templates) == 2

    def test_get_favorites(self, template_repo):
        """Should retrieve only favorite templates"""
        t1 = template_repo.create('Favorite 1', [1])
        t2 = template_repo.create('Favorite 2', [2])
        template_repo.create('Not Favorite', [3])

        template_repo.toggle_favorite(t1.id)
        template_repo.toggle_favorite(t2.id)

        favorites = template_repo.get_favorites()

        assert len(favorites) == 2

    def test_get_template_count(self, template_repo):
        """Should return correct template count"""
        assert template_repo.get_count() == 0

        template_repo.create('Template 1', [1])
        assert template_repo.get_count() == 1

        template_repo.create('Template 2', [2])
        assert template_repo.get_count() == 2


class TestQueueTemplateUpdates:
    """Test template update operations"""

    def test_update_template_name(self, template_repo):
        """Should update template name"""
        template = template_repo.create('Old Name', [1, 2, 3])
        updated = template_repo.update(template.id, name='New Name')

        assert updated.name == 'New Name'
        assert json.loads(updated.track_ids) == [1, 2, 3]  # Other fields unchanged

    def test_update_multiple_fields(self, template_repo):
        """Should update multiple fields"""
        template = template_repo.create('Original', [1, 2, 3], is_shuffled=False)
        updated = template_repo.update(
            template.id,
            name='Updated',
            track_ids=[4, 5, 6],
            is_shuffled=True,
            repeat_mode='all'
        )

        assert updated.name == 'Updated'
        assert json.loads(updated.track_ids) == [4, 5, 6]
        assert updated.is_shuffled is True
        assert updated.repeat_mode == 'all'

    def test_update_nonexistent_template(self, template_repo):
        """Updating nonexistent template should return None"""
        result = template_repo.update(9999, name='Updated')
        assert result is None

    def test_toggle_favorite(self, template_repo):
        """Should toggle favorite status"""
        template = template_repo.create('Test', [1, 2, 3])

        assert template.is_favorite is False

        toggled = template_repo.toggle_favorite(template.id)
        assert toggled.is_favorite is True

        toggled_again = template_repo.toggle_favorite(template.id)
        assert toggled_again.is_favorite is False

    def test_increment_load_count(self, template_repo):
        """Should increment load count and update last_loaded"""
        template = template_repo.create('Test', [1, 2, 3])
        assert template.load_count == 0
        assert template.last_loaded is None

        updated = template_repo.increment_load_count(template.id)

        assert updated.load_count == 1
        assert updated.last_loaded is not None

        updated_again = template_repo.increment_load_count(template.id)
        assert updated_again.load_count == 2


class TestQueueTemplateDeletion:
    """Test template deletion"""

    def test_delete_template(self, template_repo):
        """Should delete template from database"""
        template = template_repo.create('To Delete', [1, 2, 3])

        assert template_repo.get_count() == 1

        success = template_repo.delete(template.id)

        assert success is True
        assert template_repo.get_count() == 0
        assert template_repo.get_by_id(template.id) is None

    def test_delete_nonexistent_template(self, template_repo):
        """Deleting nonexistent template should return False"""
        result = template_repo.delete(9999)
        assert result is False

    def test_delete_all_templates(self, template_repo):
        """Should delete all templates"""
        template_repo.create('Template 1', [1])
        template_repo.create('Template 2', [2])
        template_repo.create('Template 3', [3])

        assert template_repo.get_count() == 3

        count_deleted = template_repo.delete_all()

        assert count_deleted == 3
        assert template_repo.get_count() == 0


class TestQueueTemplateSearch:
    """Test template search functionality"""

    def test_search_by_name(self, template_repo):
        """Should search templates by name"""
        template_repo.create('Workout Queue', [1])
        template_repo.create('Relaxing Queue', [2])
        template_repo.create('Focus Session', [3])

        results = template_repo.search('Workout')

        assert len(results) == 1
        assert results[0].name == 'Workout Queue'

    def test_search_by_description(self, template_repo):
        """Should search templates by description"""
        template_repo.create('Template 1', [1], description='Perfect for morning runs')
        template_repo.create('Template 2', [2], description='Great for coding sessions')
        template_repo.create('Template 3', [3], description='Best workout music')

        results = template_repo.search('workout')

        assert len(results) == 1
        assert 'workout' in results[0].description.lower()

    def test_search_case_insensitive(self, template_repo):
        """Search should be case insensitive"""
        template_repo.create('UPPER CASE', [1])

        results = template_repo.search('upper')

        assert len(results) == 1


class TestQueueTemplateData:
    """Test template data handling"""

    def test_to_dict_conversion(self, template_repo):
        """Template should convert to dictionary"""
        template = template_repo.create(
            'Test Template',
            [1, 2, 3],
            is_shuffled=True,
            repeat_mode='all',
            description='Test description',
            tags=['test', 'demo']
        )

        dict_repr = template_repo.to_dict(template)

        assert dict_repr['name'] == 'Test Template'
        assert dict_repr['track_ids'] == [1, 2, 3]
        assert dict_repr['is_shuffled'] is True
        assert dict_repr['repeat_mode'] == 'all'
        assert dict_repr['description'] == 'Test description'
        assert dict_repr['tags'] == ['test', 'demo']

    def test_to_dict_handles_none(self, template_repo):
        """to_dict should handle None gracefully"""
        dict_repr = template_repo.to_dict(None)

        assert dict_repr['name'] == ''
        assert dict_repr['track_ids'] == []
        assert dict_repr['is_shuffled'] is False
        assert dict_repr['repeat_mode'] == 'off'

    def test_large_track_list(self, template_repo):
        """Should handle large track lists"""
        large_list = list(range(1, 1001))  # 1000 tracks

        template = template_repo.create('Large Queue', large_list)
        retrieved = template_repo.get_by_id(template.id)

        persisted_ids = json.loads(retrieved.track_ids)
        assert len(persisted_ids) == 1000
        assert persisted_ids == large_list


class TestQueueTemplateIntegration:
    """Integration tests for complete workflows"""

    def test_create_load_and_update(self, template_repo):
        """Complete workflow: create, load, update"""
        # Create template
        template = template_repo.create(
            'My Queue',
            [1, 2, 3],
            description='My favorite songs'
        )

        # Load template
        template_repo.increment_load_count(template.id)

        # Update it
        updated = template_repo.update(
            template.id,
            name='My Updated Queue',
            track_ids=[4, 5, 6, 7]
        )

        # Verify
        retrieved = template_repo.get_by_id(template.id)
        assert retrieved.name == 'My Updated Queue'
        assert json.loads(retrieved.track_ids) == [4, 5, 6, 7]
        assert retrieved.load_count == 1

    def test_manage_favorite_templates(self, template_repo):
        """Workflow for managing favorite templates"""
        t1 = template_repo.create('Queue 1', [1, 2, 3])
        t2 = template_repo.create('Queue 2', [4, 5, 6])
        t3 = template_repo.create('Queue 3', [7, 8, 9])

        # Mark some as favorites
        template_repo.toggle_favorite(t1.id)
        template_repo.toggle_favorite(t3.id)

        favorites = template_repo.get_favorites()

        assert len(favorites) == 2
        favorite_ids = [t.id for t in favorites]
        assert t1.id in favorite_ids
        assert t3.id in favorite_ids
        assert t2.id not in favorite_ids
