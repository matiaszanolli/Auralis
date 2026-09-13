"""
Player Callbacks Mixin
~~~~~~~~~~~~~~~~~~~~~~

Effects toggles, callback registration/dispatch, playback/queue
introspection, and shuffle/repeat toggles for AudioPlayer, extracted from
enhanced_audio_player.py (#4249). These are read/notify surfaces layered on
top of the other components rather than transport or queue-navigation
actions in their own right.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable
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

    def set_auto_master_profile(self, profile: str) -> None:
        """Set auto-mastering profile"""
        self.integration.set_auto_master_profile(profile)

    # ========== Callbacks and State (delegates to various components) ==========

    def add_callback(self, callback: Callable[..., Any]) -> None:
        """Add callback for state updates"""
        # Route through IntegrationManager only — it already bridges
        # PlaybackController state changes via _on_playback_state_change,
        # enriches the dict, and forwards to integration.callbacks.
        # Adding to playback.callbacks directly would invoke cb twice per event
        # (fixes #2471).
        self.integration.add_callback(callback)

    def _notify_callbacks(self, info: dict[str, Any] | None = None) -> None:
        """
        Notify all registered callbacks with current playback information.

        Args:
            info: Optional custom playback info dict to pass to callbacks.
                  If not provided, uses get_playback_info()
        """
        if info is None:
            info = self.get_playback_info()
        self.integration._notify_callbacks(info)

    def get_playback_info(self) -> dict[str, Any]:
        """
        Get comprehensive playback information.

        Returns a flattened view alongside the full nested structure.

        #5233: despite the name, this isn't preserving compatibility with
        any external caller — its only in-repo consumer is this mixin's own
        `_notify_callbacks()`, feeding callbacks registered via
        `add_callback()`. `auralis-web/backend` never calls either method;
        WebSocket state pushes go through `audio_stream_controller.py`
        instead. Remaining callers are test-only. If this callback-
        registration path (`add_callback`/`_notify_callbacks`/
        `get_playback_info`) is ever found to have no production consumer
        at all, it's a dead-code deletion candidate in its own right — not
        attempted here, since this fix's remit is the misleading framing,
        not removing the mechanism.
        """
        full_info = self.integration.get_playback_info()

        # Flattened top-level keys alongside the full nested structure below
        # (kept for whatever reads either shape today; see the note above).
        return {
            'state': full_info['playback']['state'],
            'position_seconds': full_info['playback']['position_seconds'],
            'duration_seconds': full_info['playback']['duration_seconds'],
            'current_file': full_info['playback']['current_file'],
            'is_playing': full_info['playback']['is_playing'],
            'playback': full_info['playback'],
            'queue': full_info['queue'],
            'library': full_info['library'],
            'processing': full_info['processing'],
            'session': full_info['session'],
        }

    def get_queue_info(self) -> dict[str, Any]:
        """Get detailed queue information"""
        return self.queue.get_queue_info()

    # ========== Shuffle and Repeat (delegates to QueueController) ==========

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode"""
        self.queue.set_shuffle(enabled)
        # Shuffle reorders the queue, so the prebuffered next track is stale (fixes #2154)
        self.gapless.invalidate_prebuffer()
        self.integration._notify_callbacks({'action': 'shuffle_changed', 'enabled': enabled})

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        self.queue.set_repeat(enabled)
        # Repeat changes what the "next" track is (wraps to start) — invalidate (fixes #2154)
        self.gapless.invalidate_prebuffer()
        self.integration._notify_callbacks({'action': 'repeat_changed', 'enabled': enabled})
