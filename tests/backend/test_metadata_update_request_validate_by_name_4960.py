"""
Regression test for #4960
~~~~~~~~~~~~~~~~~~~~~~~~~~

``MetadataUpdateRequest.model_config`` used the deprecated ``populate_by_name``
key. Pydantic 2.11 supersedes it with ``validate_by_name``/``validate_by_alias``.
This asserts the model still accepts input both by field name (``track``) and
by alias (``track_number``) after the config was updated, preserving the
original dual-input behavior.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.metadata import MetadataUpdateRequest  # noqa: E402


def test_accepts_input_by_field_name():
    model = MetadataUpdateRequest.model_validate({"track": 5, "disc": 1, "title": "T"})
    assert model.track == 5
    assert model.disc == 1


def test_accepts_input_by_alias():
    model = MetadataUpdateRequest.model_validate(
        {"track_number": 5, "disc_number": 1, "title": "T"}
    )
    assert model.track == 5
    assert model.disc == 1


def test_extra_fields_still_forbidden():
    import pydantic

    try:
        MetadataUpdateRequest.model_validate({"bogus_field": 1})
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("expected extra='forbid' to reject an unknown field")
