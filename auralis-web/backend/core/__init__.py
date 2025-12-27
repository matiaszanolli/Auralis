"""
Core audio processing modules for Auralis.

Extracted from monolithic chunked_processor.py to improve maintainability and testability.
"""

from .chunk_boundaries import ChunkBoundaryManager
from .encoding import WAVEncoder
from .level_manager import LevelManager
from .processor_manager import ProcessorManager

__all__ = [
    'ChunkBoundaryManager',
    'LevelManager',
    'ProcessorManager',
    'WAVEncoder',
]
