"""
Regression: the 4 *UnavailableError classes in routers/errors.py are now
actually raised, not just hand-copied as literal strings (#5400).

routers/errors.py defined LibraryManagerUnavailableError,
AudioPlayerUnavailableError, PlayerStateUnavailableError, and
ConnectionManagerUnavailableError, but no production code ever raised any of
them -- call sites in dependencies.py, library_scan.py, and player.py each
hand-retyped the exact message as a plain HTTPException(503, "...") string
instead, so a future edit to one copy could silently drift from the class it
was meant to mirror.

services/queue_service.py's evidence sites named in the issue had already
migrated to the (architecturally distinct, ValueError-based) ServiceUnavailable
taxonomy from services/errors.py by the time this fix landed -- confirmed via
grep, left untouched here as already-correct.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.errors import (  # noqa: E402
    AudioPlayerUnavailableError,
    ConnectionManagerUnavailableError,
    LibraryManagerUnavailableError,
    PlayerStateUnavailableError,
)
from routers.dependencies import (  # noqa: E402
    require_audio_player,
    require_connection_manager,
    require_player_state_manager,
)

_BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"

# The exact hand-rolled pattern this issue eliminates, checked in the 3 files
# the issue's evidence names (queue_service.py is deliberately excluded --
# see module docstring).
_HAND_ROLLED_RE = re.compile(
    r'raise HTTPException\(status_code=503, detail="'
    r'(Library manager|Audio player|Player state manager|Connection manager) not available"\)'
)

# routers/player.py was split into player_*.py siblings (#5472); the check
# covers all of them, since the 503 guards moved into player_deps.py /
# player_playback.py.
_CHECKED_FILES = [
    "routers/dependencies.py",
    "routers/library_scan.py",
    *sorted(str(p.relative_to(_BACKEND)) for p in (_BACKEND / "routers").glob("player*.py")),
]


def test_no_hand_rolled_message_duplicates_a_typed_class():
    """Acceptance criterion: no hand-rolled string duplicates a message a
    typed class already encodes, in any of the 3 router files this issue
    named."""
    assert {"routers/player.py", "routers/player_deps.py"} <= set(_CHECKED_FILES)
    for rel in _CHECKED_FILES:
        source = (_BACKEND / rel).read_text()
        assert not _HAND_ROLLED_RE.search(source), (
            f"{rel} still hand-rolls a 503 message a typed *UnavailableError "
            f"class already encodes — #5400 regressed"
        )


class TestDependenciesRaiseTypedClasses:
    """WIRING: the require_* dependency guards actually raise the typed
    classes now, not a bare HTTPException."""

    def test_require_audio_player_raises_typed_class(self):
        with pytest.raises(AudioPlayerUnavailableError) as exc_info:
            require_audio_player(lambda: None)
        assert exc_info.value.status_code == 503

    def test_require_player_state_manager_raises_typed_class(self):
        with pytest.raises(PlayerStateUnavailableError) as exc_info:
            require_player_state_manager(lambda: None)
        assert exc_info.value.status_code == 503

    def test_require_connection_manager_raises_typed_class(self):
        with pytest.raises(ConnectionManagerUnavailableError) as exc_info:
            require_connection_manager(None)
        assert exc_info.value.status_code == 503


def test_library_manager_unavailable_error_is_importable_and_used():
    """Sanity: the class this test file didn't already exercise via a helper
    function (library_scan.py/player.py raise it inline, not via a
    dependencies.py require_* wrapper) still round-trips correctly."""
    err = LibraryManagerUnavailableError()
    assert err.status_code == 503
    assert "library manager" in err.detail.lower()
