"""The library watcher rescans only for events that can change a scan's result (#6164)."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.scanner_event_filter import is_relevant_event  # noqa: E402
from services.scanner_watchdog import _DebounceHandler  # noqa: E402


def _event(src, dest="", directory=False):
    return SimpleNamespace(src_path=src, dest_path=dest, is_directory=directory)


@pytest.mark.parametrize("path", [
    "/music/a/song.flac", "/music/a/SONG.MP3", "/music/a/track.opus", "/music/a/Cover.JPG", "/music/a/folder.webp",
])
def test_audio_and_cover_files_trigger_a_rescan(path):
    assert is_relevant_event(_event(path))


@pytest.mark.parametrize("path", [
    "/music/a/song.flac.part", "/music/a/.song.flac.swp", "/music/a/notes.txt", "/music/a/song.flac~", "/music/a/Thumbs.db",
])
def test_partial_swap_and_unrelated_files_do_not(path):
    assert not is_relevant_event(_event(path))


def test_a_directory_event_always_counts_except_inside_the_apps_own_space():
    assert is_relevant_event(_event("/music/new album", directory=True))
    assert not is_relevant_event(_event("/tmp/auralis_stream_123_x", directory=True))


def test_the_apps_own_temp_files_never_count_even_with_an_audio_suffix(tmp_path, monkeypatch):
    monkeypatch.setenv("AURALIS_DATA_DIR", str(tmp_path / "data"))
    assert not is_relevant_event(_event("/tmp/auralis_stream_42_chunk.wav"))
    assert not is_relevant_event(_event("/tmp/auralis_seekable_x.wav"))
    assert not is_relevant_event(_event(str(tmp_path / "data" / "chunks" / "a.wav")))


def test_a_rename_into_an_audio_name_counts_through_the_destination():
    assert is_relevant_event(_event("/music/a/song.flac.part", dest="/music/a/song.flac"))


class _Loop:
    def __init__(self):
        self.calls = 0

    def call_soon_threadsafe(self, fn):
        self.calls += 1


def test_the_handler_only_schedules_a_scan_for_relevant_events():
    loop = _Loop()
    handler = _DebounceHandler(trigger_fn=None, loop=loop)

    handler.on_created(_event("/music/a/song.flac.part"))
    handler.on_deleted(_event("/music/a/notes.txt"))
    assert loop.calls == 0

    handler.on_created(_event("/music/a/song.flac"))
    handler.on_moved(_event("/music/a/x", dest="/music/b/x", directory=True))
    assert loop.calls == 2
