"""
Regression test for #3463 — fingerprint scheduling on all track-load paths.

The generation-counter fix from #3445 originally lived inline in
``AudioPlayer.load_file()`` only. The library-load path and the gapless
``next_track`` path bypassed it, so adaptive mastering kept the previous
track's fingerprint and any in-flight fingerprint thread for the previous
file could land on the new track.

These tests assert that every public entry point that swaps audio_data also
bumps ``_track_generation`` and spawns a fingerprint loader.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestFingerprintScheduling:
    """All track-load entry points must schedule a fingerprint load."""

    @pytest.fixture
    def player_with_mocks(self, enhanced_player):
        """Enhanced player with file_manager / integration / gapless mocked."""
        with patch.object(enhanced_player, "_schedule_fingerprint_load") as schedule, \
             patch.object(enhanced_player.file_manager, "load_file", return_value=True), \
             patch.object(enhanced_player.playback, "load_and_stop"), \
             patch.object(enhanced_player.gapless, "start_prebuffering"), \
             patch.object(enhanced_player.integration, "_notify_callbacks"):
            yield enhanced_player, schedule

    def test_load_file_schedules_fingerprint(self, player_with_mocks):
        player, schedule = player_with_mocks
        assert player.load_file("/fake/path/A.wav") is True
        schedule.assert_called_once_with("/fake/path/A.wav")

    def test_load_track_from_library_schedules_fingerprint(self, player_with_mocks):
        player, schedule = player_with_mocks
        # Simulate IntegrationManager.load_track_from_library() setting
        # current_file as a side effect.
        def fake_load_track(track_id: int) -> bool:
            player.file_manager.current_file = f"/library/track_{track_id}.flac"
            return True

        with patch.object(player.integration, "load_track_from_library",
                          side_effect=fake_load_track):
            assert player.load_track_from_library(42) is True
        schedule.assert_called_once_with("/library/track_42.flac")

    def test_next_track_via_gapless_schedules_fingerprint(self, player_with_mocks):
        player, schedule = player_with_mocks
        # advance_with_prebuffer succeeds and the file_manager now points at
        # the new prebuffered file.
        def fake_advance(was_playing: bool) -> bool:
            del was_playing  # signature must match advance_with_prebuffer
            player.file_manager.current_file = "/queue/track_B.flac"
            return True

        with patch.object(player.gapless, "advance_with_prebuffer",
                          side_effect=fake_advance), \
             patch.object(player.integration, "record_track_completion"), \
             patch.object(player.playback, "seek"), \
             patch.object(player.playback, "is_playing", return_value=False), \
             patch.object(player.playback, "is_stopped", return_value=True), \
             patch.object(player.file_manager, "get_total_samples", return_value=0):
            assert player.next_track() is True
        schedule.assert_called_once_with("/queue/track_B.flac")

    def test_generation_increments_distinctly_across_paths(self, enhanced_player):
        """Sanity check: each scheduler call bumps _track_generation once."""
        starting = enhanced_player._track_generation

        # Patch out the thread spawn so we only measure the counter behavior.
        with patch("auralis.player.enhanced_audio_player.threading.Thread"):
            enhanced_player._schedule_fingerprint_load("/a.wav")
            enhanced_player._schedule_fingerprint_load("/b.wav")
            enhanced_player._schedule_fingerprint_load("/c.wav")

        assert enhanced_player._track_generation == starting + 3
