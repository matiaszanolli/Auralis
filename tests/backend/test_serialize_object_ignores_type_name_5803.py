"""
serialize_object() does not look at the object's class name (#5803).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It used to skip ``to_dict()`` for any class whose name contained "Mock", so what
an endpoint returned depended on how a test double (or, in principle, a real
model) happened to be named. The decision is now purely behavioural: use
``to_dict()`` when it returns a dict, otherwise project the fallback fields.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.serializers import serialize_object  # noqa: E402


class MockLikeModel:
    """A real class that merely has "Mock" in its name and a real to_dict()."""

    id = 7

    def to_dict(self):
        return {"id": self.id, "from": "to_dict"}


def test_a_class_named_mock_still_uses_its_own_to_dict():
    assert serialize_object(MockLikeModel(), {"id": None}) == {"id": 7, "from": "to_dict"}


def test_an_unconfigured_mock_falls_back_to_the_field_map():
    # MagicMock().to_dict() returns another MagicMock, not a dict, so the
    # getattr path is taken -- exactly as before the name check was removed.
    row = MagicMock()
    row.title = "Song"

    result = serialize_object(row, {"title": "Unknown", "duration": 0})

    assert result["title"] == "Song"
    assert result["duration"] == 0  # a Mock attribute is sanitised to the default


def test_a_mock_with_a_configured_to_dict_is_honoured():
    row = MagicMock()
    row.to_dict.return_value = {"id": 1}

    assert serialize_object(row, {"id": None}) == {"id": 1}


def test_a_raising_to_dict_falls_back_instead_of_propagating():
    class Broken:
        id = 3

        def to_dict(self):
            raise RuntimeError("detached")

    assert serialize_object(Broken(), {"id": None}) == {"id": 3}
