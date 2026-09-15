"""
Auralis Library Scanner Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular library scanning system

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

# The single source of truth for scannable formats (#4109); scanner.config
# re-exports it too, but implicitly, which mypy rejects here.
from auralis.io.formats import AUDIO_EXTENSIONS

# Models (imported from parent package)
from ..scan_models import AudioFileInfo, ScanResult
from .audio_analyzer import AudioAnalyzer
from .batch_processor import BatchProcessor

# Configuration
from .config import (
    DEFAULT_BATCH_SIZE,
    HASH_CHUNK_SIZE,
    SKIP_DIRECTORIES,
)

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
    # Configuration
    'AUDIO_EXTENSIONS',
    'SKIP_DIRECTORIES',
    'DEFAULT_BATCH_SIZE',
    'HASH_CHUNK_SIZE',
]
