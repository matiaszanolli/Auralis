"""
Auralis Library Scanner Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular library scanning system

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

# Models (imported from parent package)
from ..scan_models import AudioFileInfo, ScanResult

# Main scanner
from .scanner import LibraryScanner

__all__ = [
    'LibraryScanner',
    'ScanResult',
    'AudioFileInfo',
]
