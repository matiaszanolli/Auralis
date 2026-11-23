"""
Auralis I/O Module
~~~~~~~~~~~~~~~~~

Audio input/output and result handling

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Refactored from Matchering 2.0 by Sergree and contributors
"""

from . import sndfile_guard

# Before any read: only the containers Auralis uses reach the bundled libsndfile (#6512).
sndfile_guard.install()

from .loader import load  # noqa: E402
from .results import Result, pcm16, pcm24  # noqa: E402
from .saver import save  # noqa: E402

__all__ = ["load", "save", "Result", "pcm16", "pcm24"]
