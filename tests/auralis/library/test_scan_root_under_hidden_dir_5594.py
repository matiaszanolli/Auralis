"""A scan root under a hidden or excluded directory still finds its files (#5594).

should_skip_path tested EVERY component of the absolute path for a leading dot and
every ancestor against SKIP_DIRECTORIES, not just the part below the scan root, so
`~/.local/share/music` (or a root inside `node_modules`/`.git`) skipped every file
and reported a clean, empty scan. Directories below the root are filtered by name
while descending; the root and its ancestors are the user's choice.
"""

import pytest

from auralis.library.scanner.config import SKIP_DIRECTORIES
from auralis.library.scanner.file_discovery import FileDiscovery

HIDDEN_ANCESTOR = ".local"
EXCLUDED_ANCESTOR = sorted(SKIP_DIRECTORIES)[0]


def _tree(root):
    (root / "album").mkdir(parents=True)
    (root / "a.flac").write_bytes(b"")
    (root / "album" / "b.flac").write_bytes(b"")
    return root


def _names(root, recursive=True):
    return sorted(p.rsplit("/", 1)[-1] for p in FileDiscovery().discover_audio_files(str(root), recursive=recursive))


@pytest.mark.parametrize("ancestor", [HIDDEN_ANCESTOR, EXCLUDED_ANCESTOR])
def test_a_root_below_a_hidden_or_excluded_ancestor_is_scanned(tmp_path, ancestor):
    root = _tree(tmp_path / ancestor / "share" / "music")

    assert _names(root) == ["a.flac", "b.flac"]
    assert _names(root, recursive=False) == ["a.flac"]


def test_a_hidden_file_is_still_skipped(tmp_path):
    root = _tree(tmp_path / ".local" / "music")
    (root / ".hidden.flac").write_bytes(b"")
    (root / "album" / ".also.flac").write_bytes(b"")

    assert _names(root) == ["a.flac", "b.flac"]
    assert _names(root, recursive=False) == ["a.flac"]


def test_hidden_and_excluded_subdirectories_below_the_root_are_still_skipped(tmp_path):
    root = _tree(tmp_path / "music")
    for name in (".git", ".cache", EXCLUDED_ANCESTOR):
        (root / name).mkdir()
        (root / name / "skip.flac").write_bytes(b"")

    assert _names(root) == ["a.flac", "b.flac"]


def test_should_skip_path_judges_only_the_files_own_name(tmp_path):
    discovery = FileDiscovery()
    assert discovery.should_skip_path(tmp_path / ".local" / "music" / "a.flac") is False
    assert discovery.should_skip_path(tmp_path / "music" / ".a.flac") is True
