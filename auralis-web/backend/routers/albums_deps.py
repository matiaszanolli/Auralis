"""
Albums router dependency plumbing (split from albums.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .repo_deps import RepositoryFactoryDeps

_repo_deps = RepositoryFactoryDeps("albums")
