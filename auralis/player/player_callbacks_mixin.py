"""
Player Callbacks Mixin
~~~~~~~~~~~~~~~~~~~~~~

Effects toggles, queue introspection, and shuffle/repeat toggles for AudioPlayer, extracted from
enhanced_audio_player.py (#4249). These are read/notify surfaces layered on
top of the other components rather than transport or queue-navigation
actions in their own right.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .gapless_playback_engine import GaplessPlaybackEngine
from .integration_manager import IntegrationManager
from .queue_controller import QueueController


class PlayerCallbacksMixin:
    """Effects/callbacks/introspection/shuffle-repeat, delegating to components.

    Instance state below is initialized by AudioPlayer.__init__ or provided
    by sibling mixins, not here — declared here only so type checkers know
    this mixin depends on it.
    """

    integration: IntegrationManager
    queue: QueueController
    gapless: GaplessPlaybackEngine

    # ========== Effects Control (delegates to IntegrationManager) ==========

    def set_effect_enabled(self, effect_name: str, enabled: bool) -> None:
        """Enable/disable specific DSP effects"""
        self.integration.set_effect_enabled(effect_name, enabled)

    # ========== Introspection (delegates to QueueController) ==========

    def get_queue_info(self) -> dict[str, Any]:
        """Get detailed queue information"""
        return self.queue.get_queue_info()

    # ========== Shuffle and Repeat (delegates to QueueController) ==========

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode"""
        # QueueController invalidates the prebuffer itself (#2154, #5508).
        self.queue.set_shuffle(enabled)
        self.integration._notify_callbacks({'action': 'shuffle_changed', 'enabled': enabled})

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        self.queue.set_repeat(enabled)
        self.integration._notify_callbacks({'action': 'repeat_changed', 'enabled': enabled})
