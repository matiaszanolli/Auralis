"""
Regression Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides fixtures for regression testing.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.io.saver import save
from auralis.library.models import Base


@pytest.fixture
def temp_db():
    """Create temporary database."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    db_path = temp_file.name

    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def get_session():
        return Session()

    yield get_session

    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def temp_audio_dir():
    """Create temporary directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def test_audio_file(temp_audio_dir):
    """Create standard test audio file."""
    sample_rate = 44100
    duration = 5.0
    audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
    filepath = os.path.join(temp_audio_dir, 'test.wav')
    save(filepath, audio, sample_rate, subtype='PCM_16')
    return filepath
