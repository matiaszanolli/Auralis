"""
Regression: PlayerConfig.buffer_size defaults to the value its only
production caller actually uses (#5421).

PlayerConfig.buffer_size defaulted to 4410 (100ms at 44.1kHz), but the only
production construction site with an explicit argument
(config/startup.py::_init_audio_player) always passed buffer_size=1024
(~23ms). The default was latent -- harmless only because that caller always
overrode it -- and would have silently grown the realtime buffer 4x,
changing latency characteristics with no visible error, if that explicit
argument were ever dropped. enhanced_audio_player.py's `config = PlayerConfig()`
fallback (reached when no config is passed in) would have picked up the
wrong default too.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.player.config import PlayerConfig  # noqa: E402


def test_default_buffer_size_matches_the_only_real_caller():
    """config/startup.py::_init_audio_player is the only production
    construction site with an explicit buffer_size, and it always passes
    1024 -- the default must agree."""
    config = PlayerConfig()
    assert config.buffer_size == 1024


def test_fallback_construction_in_enhanced_audio_player_is_sane():
    """enhanced_audio_player.py:95's `config = PlayerConfig()` fallback path
    (used when no config is explicitly passed to EnhancedAudioPlayer) must
    now produce the same buffer size the real startup path uses, not a
    silently-4x-larger one."""
    import inspect

    from auralis.player.enhanced_audio_player import AudioPlayer

    source = inspect.getsource(AudioPlayer.__init__)
    assert "PlayerConfig()" in source, (
        "enhanced_audio_player.py's fallback construction site moved or was "
        "renamed — update this test to point at the new location"
    )

    # The fallback constructs PlayerConfig with no arguments, so it inherits
    # exactly the class default asserted above.
    assert PlayerConfig().buffer_size == 1024


def test_explicit_override_still_works():
    """The default changing must not affect callers that pass their own
    value explicitly."""
    config = PlayerConfig(buffer_size=2048)
    assert config.buffer_size == 2048
