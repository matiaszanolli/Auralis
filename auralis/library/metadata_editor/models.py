"""
Metadata Models
~~~~~~~~~~~~~~~

Data structures for metadata editing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class MetadataUpdate:
    """Represents a metadata update operation"""
    track_id: int
    filepath: str
    updates: dict[str, Any]
    backup: bool = True
