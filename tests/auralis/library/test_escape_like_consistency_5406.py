"""
Regression: track/album/artist/genre search repositories must call the
shared escape_like() helper instead of carrying their own inline copy of
the LIKE-escaping expression (#5406).

escape_like() was added to base.py by #5171 specifically to be the single
place a future LIKE-escaping fix (the #2405 bug class) needs to land. Its
own docstring named these 4 sites as an intentionally-deferred mechanical
follow-up — this pins that follow-up so the split-brain can't silently
reappear.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.library.repositories.base import escape_like  # noqa: E402

_REPO_DIR = Path(__file__).parent.parent.parent.parent / "auralis" / "library" / "repositories"

_SEARCH_FILES = [
    "track_repository_search.py",
    "album_repository.py",
    "artist_repository.py",
    "genre_repository.py",
]

# The exact inline chain escape_like() replaces — matches the docstring's own
# grep pattern, restricted to files other than base.py itself.
_INLINE_CHAIN_RE = re.compile(
    r"replace\(\s*'\\\\'\s*,\s*'\\\\\\\\'\s*\)"
    r"\.replace\(\s*'%'\s*,\s*'\\\\%'\s*\)"
    r"\.replace\(\s*'_'\s*,\s*'\\\\_'\s*\)"
)


def test_no_inline_escape_chain_outside_base():
    """CONSISTENCY / acceptance criterion: 0 hits for the inline chain in
    any repository file other than base.py's own definition."""
    for name in _SEARCH_FILES:
        source = (_REPO_DIR / name).read_text()
        assert not _INLINE_CHAIN_RE.search(source), (
            f"{name} still carries an inline LIKE-escape chain instead of "
            f"calling escape_like() — #5406 regressed"
        )


def test_all_four_repositories_import_escape_like():
    """WIRING: each of the 4 named sites actually imports the helper."""
    for name in _SEARCH_FILES:
        source = (_REPO_DIR / name).read_text()
        assert "escape_like" in source, (
            f"{name} does not reference escape_like() at all"
        )


def test_escape_like_still_neutralises_metacharacters():
    """The helper itself, unchanged by this issue, still does its job —
    guards against a future edit to escape_like() breaking every caller
    silently now that they all share it."""
    assert escape_like("50%_off\\path") == "50\\%\\_off\\\\path"
    assert escape_like("plain query") == "plain query"
