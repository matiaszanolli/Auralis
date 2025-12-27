"""
Edge Case Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures and configuration for edge case testing.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.library.models import Base


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    db_path = temp_file.name

    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def get_session():
        return Session()

    yield get_session

    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def temp_file():
    """Create temporary file."""
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp_path = temp.name
    temp.close()

    yield temp_path

    try:
        os.unlink(temp_path)
    except Exception:
        pass
