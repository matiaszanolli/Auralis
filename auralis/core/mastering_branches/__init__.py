"""
Mastering Processing Branches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    **OFFLINE CLI SUBSYSTEM — not on the shipped app's audio path (#4873).**
    Part of ``SimpleMasteringPipeline``, whose sole entry point is the root
    ``auto_master.py`` CLI. See ``core/simple_mastering.py`` for the full
    rationale. Note the name collision: this ``ContinuousMasteringBranch`` is
    NOT ``core/processing/continuous_mode.py``'s ``ContinuousMode``, which is
    what the shipped app actually runs.

Shared base and the single continuous mastering path.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .base import ProcessingBranch
from .continuous import ContinuousMasteringBranch

__all__ = [
    "ContinuousMasteringBranch",
    "ProcessingBranch",
]
