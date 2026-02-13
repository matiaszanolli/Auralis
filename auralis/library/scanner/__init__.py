"""
Auralis Library Scanner Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular library scanning system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Models (imported from parent package)
from ..scan_models import AudioFileInfo, ScanResult
from .audio_analyzer import AudioAnalyzer
from .batch_processor import BatchProcessor

# Configuration
from .config import (
    AUDIO_EXTENSIONS,
    DEFAULT_BATCH_SIZE,
    HASH_CHUNK_SIZE,
    SKIP_DIRECTORIES,
)
from .duplicate_detector import DuplicateDetector

# Components (for advanced usage)
from .file_discovery import FileDiscovery
from .metadata_extractor import MetadataExtractor

# Main scanner
from .scanner import LibraryScanner

__all__ = [
    # Main class
    'LibraryScanner',
    # Models
    'ScanResult',
    'AudioFileInfo',
    # Components
    'FileDiscovery',
    'AudioAnalyzer',
    'MetadataExtractor',
    'BatchProcessor',
    'DuplicateDetector',
    # Configuration
    'AUDIO_EXTENSIONS',
    'SKIP_DIRECTORIES',
    'DEFAULT_BATCH_SIZE',
    'HASH_CHUNK_SIZE',
]
