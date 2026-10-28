"""
Every ProcessingParameters field is read by a stage, or declared reporting-only (#5576)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The generator produced ``dynamics_blend``, ``limiter_params``,
``peak_target_db`` and more that nothing consumed, so tuning them (or the
reporting that displays them) looked like it steered the audio and did not.
Adding a field now means either reading it in a ContinuousMode stage or naming
it in ``REPORTING_ONLY_FIELDS``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import dataclasses
import re
from pathlib import Path

from auralis.core.processing.continuous_space_types import ProcessingParameters
from auralis.core.processing.processing_parameter_readers import REPORTING_ONLY_FIELDS

_PROCESSING = Path(__file__).resolve().parents[3] / "auralis/core/processing"
# The modules that run the stages and read params.* (continuous_mode.py only
# composes the mixins).
_STAGE_SOURCES = ("continuous_stages.py", "continuous_dsp_ops.py")


def _stage_source() -> str:
    return "\n".join((_PROCESSING / name).read_text() for name in _STAGE_SOURCES)


def test_every_field_is_read_by_a_stage_or_declared_reporting_only():
    source = _stage_source()
    fields = {f.name for f in dataclasses.fields(ProcessingParameters)}

    unread = {
        name for name in fields - REPORTING_ONLY_FIELDS
        if not re.search(rf"\bparams\.{name}\b|getattr\(params, '{name}'", source)
    }

    assert not unread, (
        f"ProcessingParameters fields no stage reads: {sorted(unread)}. Read them "
        f"in a ContinuousMode stage or add them to REPORTING_ONLY_FIELDS."
    )


def test_reporting_only_fields_really_have_no_stage_reader():
    """A field that gains a reader must leave the allowlist, or it stays
    mislabelled as having no effect."""
    source = _stage_source()

    wrongly_listed = {
        name for name in REPORTING_ONLY_FIELDS
        if re.search(rf"\bparams\.{name}\b|getattr\(params, '{name}'", source)
    }

    assert not wrongly_listed, f"now read by a stage, drop from the allowlist: {sorted(wrongly_listed)}"
    assert REPORTING_ONLY_FIELDS <= {f.name for f in dataclasses.fields(ProcessingParameters)}
