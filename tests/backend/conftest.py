"""
Backend Test Configuration

Provides fixtures and configuration for backend testing.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add backend to Python path for imports
backend_path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests.

    This fixture ensures pytest-asyncio works correctly.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_track():
    """Create a mock track object"""
    from unittest.mock import Mock

    track = Mock()
    track.id = 1
    track.filepath = str(Path(__file__).parent / "fixtures" / "test_audio.mp3")
    track.duration = 238.5
    track.title = "Test Track"
    track.artist = "Test Artist"
    track.album = "Test Album"
    track.album_id = 1

    return track


@pytest.fixture
def sample_audio():
    """
    Generate sample audio data for testing.

    Returns:
        tuple: (audio_data, sample_rate)
            - audio_data: numpy array (samples, channels) for stereo
            - sample_rate: int (44100)
    """
    import numpy as np

    sample_rate = 44100
    duration = 1.0  # 1 second
    samples = int(sample_rate * duration)

    # Generate 440 Hz sine wave (A4 note)
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    return audio_stereo, sample_rate


@pytest.fixture
def sample_audio_long():
    """
    Generate longer sample audio (30 seconds) for chunk testing.

    Returns:
        tuple: (audio_data, sample_rate)
    """
    import numpy as np

    sample_rate = 44100
    duration = 30.0  # 30 seconds
    samples = int(sample_rate * duration)

    # Generate 440 Hz sine wave
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    return audio_stereo, sample_rate


# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest with asyncio settings"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
