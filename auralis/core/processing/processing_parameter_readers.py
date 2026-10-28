"""
Which ProcessingParameters fields a DSP stage actually reads (#5576)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``peak_target_db``, ``dynamics_blend``, ``limiter_params`` and ``expansion_params`` are
produced for display and for the fixed-target schema contract but are not read by any DSP
stage: the ContinuousMode chain takes its peak from ``AdaptiveLoudnessControl``, builds its
limiter from constants, and no longer runs an expansion stage (#5561). Tuning them does not
change the audio. Likewise only ``ratio`` and ``amount`` of ``compression_params`` and the
gains/blend of ``eq_curve`` are applied.

A test pins that every other field has a reader, so anything added to the dataclass must be
read by a ContinuousMode stage or be named here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

REPORTING_ONLY_FIELDS = frozenset({
    'peak_target_db', 'dynamics_blend', 'limiter_params', 'expansion_params',
})
