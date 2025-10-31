# -*- coding: utf-8 -*-

"""
Auralis Library Scanner Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular library scanning system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Main scanner
from .scanner import LibraryScanner

# Components (for advanced usage)
from .file_discovery import FileDiscovery
from .audio_analyzer import AudioAnalyzer
from .metadata_extractor import MetadataExtractor
from .batch_processor import BatchProcessor
from .duplicate_detector import DuplicateDetector

# Models (imported from parent package)
from ..scan_models import ScanResult, AudioFileInfo

# Configuration
from .config import (
    AUDIO_EXTENSIONS,
    SKIP_DIRECTORIES,
    DEFAULT_BATCH_SIZE,
    HASH_CHUNK_SIZE
)

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
