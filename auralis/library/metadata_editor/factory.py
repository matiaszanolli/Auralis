"""
Metadata Editor Factory
~~~~~~~~~~~~~~~~~~~~~~~

Factory function for creating metadata editor instances

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .metadata_editor import MetadataEditor


def create_metadata_editor() -> MetadataEditor:
    """
    Factory function to create metadata editor

    Returns:
        MetadataEditor instance
    """
    return MetadataEditor()
