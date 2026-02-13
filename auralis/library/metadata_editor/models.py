"""
Metadata Models
~~~~~~~~~~~~~~~

Data structures for metadata editing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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
