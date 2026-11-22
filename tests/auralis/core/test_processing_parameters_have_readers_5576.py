"""
Every ProcessingParameters field is read by a stage (#5576, #6650)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The generator produced ``dynamics_blend``, ``limiter_params``, ``peak_target_db`` and
``expansion_params`` that nothing consumed, so tuning them (or the reporting that displayed them)
looked like it steered the audio and did not. #5576 named them in an allowlist; #6650 deleted them.
A field added now must be read by a ContinuousMode stage.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import dataclasses
import re
from pathlib import Path

from auralis.core.processing.continuous_space_types import ProcessingParameters

_PROCESSING = Path(__file__).resolve().parents[3] / "auralis/core/processing"
# The modules that run the stages and read params.* (continuous_mode.py only
# composes the mixins).
_STAGE_SOURCES = ("continuous_stages.py", "continuous_dsp_ops.py")


def _stage_source() -> str:
    return "\n".join((_PROCESSING / name).read_text() for name in _STAGE_SOURCES)


def test_every_field_is_read_by_a_stage():
    source = _stage_source()
    fields = {f.name for f in dataclasses.fields(ProcessingParameters)}

    unread = {
        name for name in fields
        if not re.search(rf"\bparams\.{name}\b|getattr\(params, '{name}'", source)
    }

    assert not unread, (
        f"ProcessingParameters fields no stage reads: {sorted(unread)}. Read them in a "
        f"ContinuousMode stage, or do not add them."
    )

