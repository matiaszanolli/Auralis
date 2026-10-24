"""
Regression test for #4960
~~~~~~~~~~~~~~~~~~~~~~~~~~

``MetadataUpdateRequest.model_config`` used the deprecated ``populate_by_name``
key. Pydantic 2.11 supersedes it with ``validate_by_name``/``validate_by_alias``
(#4960); the dual-name tolerance itself (``track``/``track_number``) later went
with #6260 — the app's only payload builder sends the tag names ``track``/
``disc``, so the model now accepts one name per field and rejects the alias
spelling as an unknown key.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.metadata_models import MetadataUpdateRequest  # noqa: E402


def test_accepts_input_by_field_name():
    model = MetadataUpdateRequest.model_validate({"track": 5, "disc": 1, "title": "T"})
    assert model.track == 5
    assert model.disc == 1


def test_rejects_the_alias_spelling_no_producer_sends():
    import pydantic

    try:
        MetadataUpdateRequest.model_validate(
            {"track_number": 5, "disc_number": 1, "title": "T"}
        )
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("expected the alias spelling to be rejected")


def test_extra_fields_still_forbidden():
    import pydantic

    try:
        MetadataUpdateRequest.model_validate({"bogus_field": 1})
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("expected extra='forbid' to reject an unknown field")
