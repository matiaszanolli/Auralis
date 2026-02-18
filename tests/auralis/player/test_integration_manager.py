"""
Tests for IntegrationManager (#2304)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers:
- Constructor: attribute initialisation, playback callback registration
- add_callback / _notify_callbacks: delivery, error isolation
- _get_repos: raises RuntimeError when factory unavailable
- load_track_from_library: track-not-found, file-load failure, success path,
  auto_reference_selection toggle
- _auto_select_reference: recommended_reference (exists / missing / load-fails),
  similar-track fallback, no-reference-found case
- set_effect_enabled / set_auto_master_profile: delegate + callback notification
- get_playback_info: correct structure
- record_track_completion: counter increment + callback
- _get_position_seconds: returns 0.0 when no audio_data
- _on_playback_state_change: enriches state dict with file info
- cleanup: resets processor effects
"""

from unittest.mock import MagicMock, call, patch

import pytest

from auralis.player.integration_manager import IntegrationManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_track(
    *,
    track_id: int = 1,
    title: str = "Test Track",
    filepath: str = "/music/test.flac",
    recommended_reference: str | None = None,
    artists: list | None = None,
) -> MagicMock:
    """Build a minimal Track-like mock."""
    track = MagicMock()
    track.id = track_id
    track.title = title
    track.filepath = filepath
    track.recommended_reference = recommended_reference
    track.artists = artists or []
    track.to_dict.return_value = {
        'id': track_id,
        'title': title,
        'filepath': filepath,
    }
    return track


def _make_manager(
    *,
    auto_reference_selection: bool = True,
    factory_returns: object = None,
    factory_raises: Exception | None = None,
) -> IntegrationManager:
    """Build IntegrationManager with all dependencies mocked."""
    playback = MagicMock()
    file_manager = MagicMock()
    file_manager.audio_data = None
    file_manager.sample_rate = 44100
    file_manager.current_file = None
    file_manager.get_duration.return_value = 0.0

    queue = MagicMock()
    queue.get_queue_info.return_value = {}

    processor = MagicMock()
    processor.get_processing_info.return_value = {}

    if factory_raises is not None:
        get_factory = MagicMock(side_effect=factory_raises)
    else:
        get_factory = MagicMock(return_value=factory_returns)

    manager = IntegrationManager(
        playback=playback,
        file_manager=file_manager,
        queue=queue,
        processor=processor,
        get_repository_factory=get_factory,
    )
    manager.auto_reference_selection = auto_reference_selection
    return manager


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_initial_state(self):
        m = _make_manager()
        assert m.current_track is None
        assert m.auto_reference_selection is True
        assert m.callbacks == []
        assert m.tracks_played == 0
        assert m.total_play_time == 0.0

    def test_registers_playback_callback(self):
        """PlaybackController.add_callback must be called once at init."""
        m = _make_manager()
        m.playback.add_callback.assert_called_once_with(m._on_playback_state_change)


# ---------------------------------------------------------------------------
# Callback management
# ---------------------------------------------------------------------------

class TestCallbacks:
    def test_add_callback_appended(self):
        m = _make_manager()
        cb = MagicMock()
        m.add_callback(cb)
        assert cb in m.callbacks

    def test_notify_calls_all_callbacks(self):
        m = _make_manager()
        cb1, cb2 = MagicMock(), MagicMock()
        m.add_callback(cb1)
        m.add_callback(cb2)
        payload = {'action': 'test'}
        m._notify_callbacks(payload)
        cb1.assert_called_once_with(payload)
        cb2.assert_called_once_with(payload)

    def test_notify_isolates_callback_errors(self):
        """A raising callback must not prevent subsequent callbacks from firing."""
        m = _make_manager()
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        m.add_callback(bad_cb)
        m.add_callback(good_cb)
        m._notify_callbacks({'action': 'test'})
        good_cb.assert_called_once()


# ---------------------------------------------------------------------------
# _get_repos
# ---------------------------------------------------------------------------

class TestGetRepos:
    def test_returns_factory_when_available(self):
        factory = MagicMock()
        m = _make_manager(factory_returns=factory)
        assert m._get_repos() is factory

    def test_raises_when_factory_returns_none(self):
        m = _make_manager(factory_returns=None)
        with pytest.raises(RuntimeError, match="Repository factory not available"):
            m._get_repos()

    def test_raises_when_factory_raises_type_error(self):
        m = _make_manager(factory_raises=TypeError("bad"))
        with pytest.raises(RuntimeError, match="Repository factory not available"):
            m._get_repos()

    def test_raises_when_factory_raises_attribute_error(self):
        m = _make_manager(factory_raises=AttributeError("missing"))
        with pytest.raises(RuntimeError, match="Repository factory not available"):
            m._get_repos()


# ---------------------------------------------------------------------------
# load_track_from_library
# ---------------------------------------------------------------------------

class TestLoadTrackFromLibrary:
    def test_returns_false_when_track_not_found(self):
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = None
        m = _make_manager(factory_returns=factory)
        assert m.load_track_from_library(99) is False

    def test_returns_false_when_file_load_fails(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_file.return_value = False
        assert m.load_track_from_library(1) is False

    def test_success_sets_current_track(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory, auto_reference_selection=False)
        m.file_manager.load_file.return_value = True
        m.load_track_from_library(1)
        assert m.current_track is track

    def test_success_records_play(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory, auto_reference_selection=False)
        m.file_manager.load_file.return_value = True
        m.load_track_from_library(1)
        factory.tracks.record_play.assert_called_once_with(1)

    def test_success_fires_track_loaded_callback(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory, auto_reference_selection=False)
        m.file_manager.load_file.return_value = True
        cb = MagicMock()
        m.add_callback(cb)
        m.load_track_from_library(1)
        cb.assert_called_once()
        event = cb.call_args[0][0]
        assert event['action'] == 'track_loaded'
        assert event['track'] == track.to_dict()

    def test_auto_reference_selection_enabled_calls_auto_select(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory, auto_reference_selection=True)
        m.file_manager.load_file.return_value = True
        with patch.object(m, '_auto_select_reference') as mock_auto:
            m.load_track_from_library(1)
            mock_auto.assert_called_once_with(track)

    def test_auto_reference_selection_disabled_skips_auto_select(self):
        track = _make_track()
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        m = _make_manager(factory_returns=factory, auto_reference_selection=False)
        m.file_manager.load_file.return_value = True
        with patch.object(m, '_auto_select_reference') as mock_auto:
            m.load_track_from_library(1)
            mock_auto.assert_not_called()

    def test_returns_false_and_does_not_raise_on_exception(self):
        m = _make_manager(factory_raises=RuntimeError("db down"))
        assert m.load_track_from_library(1) is False


# ---------------------------------------------------------------------------
# _auto_select_reference
# ---------------------------------------------------------------------------

class TestAutoSelectReference:
    def test_uses_recommended_reference_when_file_exists_and_loads(self):
        ref_path = "/music/reference.flac"
        track = _make_track(recommended_reference=ref_path)
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([], 0)
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_reference.return_value = True
        cb = MagicMock()
        m.add_callback(cb)

        with patch("os.path.exists", return_value=True):
            m._auto_select_reference(track)

        m.file_manager.load_reference.assert_called_once_with(ref_path)
        cb.assert_called_once()
        event = cb.call_args[0][0]
        assert event['action'] == 'reference_loaded'
        assert event['reference_file'] == ref_path

    def test_skips_recommended_reference_when_file_missing(self):
        """When recommended_reference path does not exist, fall through to similar."""
        ref_path = "/music/missing.flac"
        track = _make_track(recommended_reference=ref_path)
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([], 0)
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_reference.return_value = True

        with patch("os.path.exists", return_value=False):
            m._auto_select_reference(track)

        # load_reference should NOT have been called for the missing file
        m.file_manager.load_reference.assert_not_called()

    def test_skips_recommended_reference_when_load_fails(self):
        """When load_reference returns False, fall through to similar tracks."""
        ref_path = "/music/reference.flac"
        track = _make_track(recommended_reference=ref_path)
        similar = _make_track(track_id=2, filepath="/music/similar.flac")
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([similar], 1)
        m = _make_manager(factory_returns=factory)

        # First call (recommended) fails, second call (similar) succeeds
        m.file_manager.load_reference.side_effect = [False, True]

        with patch("os.path.exists", return_value=True):
            m._auto_select_reference(track)

        assert m.file_manager.load_reference.call_count == 2

    def test_falls_back_to_similar_tracks(self):
        """When recommended_reference is None, use find_similar()."""
        track = _make_track(recommended_reference=None)
        sim1 = _make_track(track_id=2, filepath="/music/sim1.flac")
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([sim1], 1)
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_reference.return_value = True
        cb = MagicMock()
        m.add_callback(cb)

        with patch("os.path.exists", return_value=True):
            m._auto_select_reference(track)

        m.file_manager.load_reference.assert_called_once_with(sim1.filepath)
        factory.tracks.find_similar.assert_called_once_with(track, limit=3)
        event = cb.call_args[0][0]
        assert event['action'] == 'reference_loaded'

    def test_stops_at_first_loadable_similar_track(self):
        """Only the first loadable similar track should be used."""
        track = _make_track(recommended_reference=None)
        sim1 = _make_track(track_id=2, filepath="/music/sim1.flac")
        sim2 = _make_track(track_id=3, filepath="/music/sim2.flac")
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([sim1, sim2], 2)
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_reference.return_value = True

        with patch("os.path.exists", return_value=True):
            m._auto_select_reference(track)

        m.file_manager.load_reference.assert_called_once_with(sim1.filepath)

    def test_skips_nonexistent_similar_track_files(self):
        """Similar tracks whose files don't exist must be skipped."""
        track = _make_track(recommended_reference=None)
        missing = _make_track(track_id=2, filepath="/music/missing.flac")
        present = _make_track(track_id=3, filepath="/music/present.flac")
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([missing, present], 2)
        m = _make_manager(factory_returns=factory)
        m.file_manager.load_reference.return_value = True

        def _exists(p):
            return p == "/music/present.flac"

        with patch("os.path.exists", side_effect=_exists):
            m._auto_select_reference(track)

        m.file_manager.load_reference.assert_called_once_with(present.filepath)

    def test_no_reference_fires_no_callback(self):
        """When no reference can be found, no callback is fired."""
        track = _make_track(recommended_reference=None)
        factory = MagicMock()
        factory.tracks.find_similar.return_value = ([], 0)
        m = _make_manager(factory_returns=factory)
        cb = MagicMock()
        m.add_callback(cb)

        with patch("os.path.exists", return_value=False):
            m._auto_select_reference(track)

        cb.assert_not_called()

    def test_exception_in_auto_select_does_not_propagate(self):
        """Errors inside _auto_select_reference must not bubble up."""
        track = _make_track(recommended_reference=None)
        factory = MagicMock()
        factory.tracks.find_similar.side_effect = RuntimeError("db error")
        m = _make_manager(factory_returns=factory)
        # Must not raise
        m._auto_select_reference(track)


# ---------------------------------------------------------------------------
# Effect and profile control
# ---------------------------------------------------------------------------

class TestEffectAndProfile:
    def test_set_effect_enabled_delegates_to_processor(self):
        m = _make_manager()
        m.set_effect_enabled("reverb", True)
        m.processor.set_effect_enabled.assert_called_once_with("reverb", True)

    def test_set_effect_enabled_fires_callback(self):
        m = _make_manager()
        cb = MagicMock()
        m.add_callback(cb)
        m.set_effect_enabled("eq", False)
        event = cb.call_args[0][0]
        assert event['action'] == 'effect_changed'
        assert event['effect'] == 'eq'
        assert event['enabled'] is False

    def test_set_auto_master_profile_delegates_to_processor(self):
        m = _make_manager()
        m.set_auto_master_profile("transparent")
        m.processor.set_auto_master_profile.assert_called_once_with("transparent")

    def test_set_auto_master_profile_fires_callback(self):
        m = _make_manager()
        cb = MagicMock()
        m.add_callback(cb)
        m.set_auto_master_profile("warm")
        event = cb.call_args[0][0]
        assert event['action'] == 'profile_changed'
        assert event['profile'] == 'warm'


# ---------------------------------------------------------------------------
# get_playback_info
# ---------------------------------------------------------------------------

class TestGetPlaybackInfo:
    def test_returns_expected_top_level_keys(self):
        m = _make_manager()
        m.playback.state.value = 'stopped'
        m.playback.is_playing.return_value = False
        info = m.get_playback_info()
        assert set(info.keys()) == {'playback', 'queue', 'library', 'processing', 'session'}

    def test_library_section_contains_current_track(self):
        m = _make_manager()
        m.playback.state.value = 'stopped'
        m.playback.is_playing.return_value = False
        info = m.get_playback_info()
        assert info['library']['current_track'] is None
        assert info['library']['auto_reference_selection'] is True

    def test_session_section_tracks_played(self):
        m = _make_manager()
        m.playback.state.value = 'stopped'
        m.playback.is_playing.return_value = False
        m.tracks_played = 5
        info = m.get_playback_info()
        assert info['session']['tracks_played'] == 5


# ---------------------------------------------------------------------------
# record_track_completion
# ---------------------------------------------------------------------------

class TestRecordTrackCompletion:
    def test_increments_counter(self):
        m = _make_manager()
        m.record_track_completion()
        assert m.tracks_played == 1
        m.record_track_completion()
        assert m.tracks_played == 2

    def test_fires_track_completed_callback(self):
        m = _make_manager()
        cb = MagicMock()
        m.add_callback(cb)
        m.record_track_completion()
        event = cb.call_args[0][0]
        assert event['action'] == 'track_completed'
        assert event['tracks_played'] == 1


# ---------------------------------------------------------------------------
# _get_position_seconds
# ---------------------------------------------------------------------------

class TestGetPositionSeconds:
    def test_returns_zero_when_no_audio_data(self):
        m = _make_manager()
        m.file_manager.audio_data = None
        assert m._get_position_seconds() == 0.0

    def test_computes_position_from_playback_and_sample_rate(self):
        m = _make_manager()
        m.file_manager.audio_data = object()  # any non-None value
        m.file_manager.sample_rate = 44100
        m.playback.position = 44100  # 1 second at 44100 Hz
        assert m._get_position_seconds() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _on_playback_state_change
# ---------------------------------------------------------------------------

class TestOnPlaybackStateChange:
    def test_enriches_state_with_file_info(self):
        m = _make_manager()
        m.file_manager.current_file = "/music/track.flac"
        m.file_manager.get_duration.return_value = 180.0
        m.file_manager.audio_data = None
        cb = MagicMock()
        m.add_callback(cb)

        m._on_playback_state_change({'state': 'playing'})

        event = cb.call_args[0][0]
        assert event['state'] == 'playing'
        assert event['current_file'] == "/music/track.flac"
        assert event['duration_seconds'] == 180.0
        assert event['current_track'] is None

    def test_handles_none_state_info(self):
        """None input must be treated as empty dict (no AttributeError)."""
        m = _make_manager()
        m.file_manager.audio_data = None
        cb = MagicMock()
        m.add_callback(cb)
        m._on_playback_state_change(None)
        cb.assert_called_once()

    def test_includes_current_track_dict(self):
        track = _make_track()
        m = _make_manager()
        m.current_track = track
        m.file_manager.audio_data = None
        cb = MagicMock()
        m.add_callback(cb)
        m._on_playback_state_change({})
        event = cb.call_args[0][0]
        assert event['current_track'] == track.to_dict()


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_calls_processor_reset_all_effects(self):
        m = _make_manager()
        m.cleanup()
        m.processor.reset_all_effects.assert_called_once()
