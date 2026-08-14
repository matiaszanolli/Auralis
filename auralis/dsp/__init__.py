"""
Auralis DSP Module
~~~~~~~~~~~~~~~~~

Digital Signal Processing algorithms for audio mastering

This package deliberately exports **nothing** at the top level: import the
submodule you need (``auralis.dsp.basic``, ``auralis.dsp.eq``,
``auralis.dsp.dynamics``, ``auralis.dsp.utils``) rather than expecting a
package-level entry point.

#4867 removed the previous sole export, ``stages.main`` — a Matchering-2.0
lineage reference-matching routine (LUFS/RMS match, soft clip) with zero
callers anywhere in the app, the offline ``auto_master.py`` CLI, or the
scripts. Naming it as this package's public API implied ``auralis.dsp`` had a
pipeline entry point; it does not. The real entry points are
``auralis.core.hybrid_processor.HybridProcessor.process()`` for the shipped
app and ``auralis.core.simple_mastering`` for the offline CLI.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

__all__: list[str] = []