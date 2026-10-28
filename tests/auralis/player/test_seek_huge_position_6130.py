"""AudioPlayer.seek() clamps huge finite positions instead of overflowing (#6130).

``int(position_seconds * sample_rate)`` was evaluated before the clamp. A finite
position above ~4e303 s multiplies to ``inf`` and ``int(inf)`` raised
OverflowError (a WebSocket seek then surfaced as internal_error). The clamp now
happens in the float domain, so the seek lands on the last sample.
"""

import pytest

from auralis.player.enhanced_audio_player import AudioPlayer

SR = 44100
TOTAL = 10 * SR


@pytest.fixture
def player(get_repository_factory_callable):
    p = AudioPlayer(get_repository_factory=get_repository_factory_callable)
    p.file_manager.is_loaded = lambda: True
    p.file_manager.get_total_samples = lambda: TOTAL
    p.file_manager.sample_rate = SR
    seen: list[tuple[int, int]] = []
    p.playback.seek = lambda value, max_samples: (seen.append((value, max_samples)), True)[1]
    p._seen = seen  # type: ignore[attr-defined]
    return p


@pytest.mark.parametrize("seconds", [1e300, 1.7e308, float("inf")])
def test_a_huge_position_seeks_to_the_end(player, seconds):
    assert player.seek(seconds) is True
    assert player._seen == [(TOTAL, TOTAL)]


@pytest.mark.parametrize("seconds", [-1e300, -5.0, float("-inf")])
def test_a_negative_position_seeks_to_the_start(player, seconds):
    assert player.seek(seconds) is True
    assert player._seen == [(0, TOTAL)]


def test_an_ordinary_position_is_unchanged(player):
    assert player.seek(2.5) is True
    assert player._seen == [(int(2.5 * SR), TOTAL)]
