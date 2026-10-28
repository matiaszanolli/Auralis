"""Engine navigation reads the path key production queue entries actually carry (#5563).

QueueController.set_queue stores ``{'filepath': ...}``; the engine's gapless / previous / prebuffer
code read only ``file_path`` and ``path``, so on a production queue a gapless advance found "no file
path" and never prebuffered.
"""

import pytest

from auralis.player.components.queue_navigation import _track_matches
from auralis.player.gapless_prebuffer import PrebufferMixin
from auralis.player.queue_controller import QueueController
from auralis.player.queue_entry import entry_path


@pytest.mark.parametrize("entry", [
    {"filepath": "/m/a.flac"},
    {"file_path": "/m/a.flac"},
    {"path": "/m/a.flac"},
])
def test_every_key_spelling_is_read(entry):
    assert entry_path(entry) == "/m/a.flac"


def test_entries_without_a_path_have_none():
    assert entry_path({"id": 3}) is None
    assert entry_path({"filepath": ""}) is None
    assert entry_path(None) is None


def test_a_production_queue_entry_has_a_path_for_the_engine():
    controller = QueueController(lambda: None)
    controller.set_queue(["/m/a.flac", "/m/b.flac"], 0)

    assert entry_path(controller.peek_next_track()) == "/m/b.flac"


def test_entries_match_on_filepath_when_ids_are_absent():
    assert _track_matches({"filepath": "/m/a.flac"}, {"filepath": "/m/a.flac"})
    assert not _track_matches({"filepath": "/m/a.flac"}, {"filepath": "/m/b.flac"})
    assert PrebufferMixin._entries_match({"filepath": "/m/a.flac"}, {"filepath": "/m/a.flac"})


def test_two_entries_with_neither_id_nor_path_do_not_match_on_none():
    assert not PrebufferMixin._entries_match({"title": "x"}, {"title": "y"})
    assert not _track_matches({"title": "x"}, {"title": "y"})
