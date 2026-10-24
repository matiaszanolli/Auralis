"""
Real-time chain uses the track's actual sample rate (#5729).

AudioFileManager.sample_rate follows the loaded file (no resampling), but
get_audio_chunk never told the real-time chain: the compressor and
transient enhancer were built once for config.sample_rate, so a 48/96 kHz
track got mis-scaled attack/release timing and transient windows, and the
CPU-usage stats divided by the wrong rate. The chain is now reconfigured
whenever the incoming chunk's rate differs from the DSP's current rate,
which also covers gapless swaps to a track at another rate.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.player.config import PlayerConfig
from auralis.player.player_streaming_mixin import PlayerStreamingMixin
from auralis.player.realtime.auto_master import AutoMasterProcessor
from auralis.player.realtime.processor import RealtimeProcessor

SR_DEFAULT = 44100
SR_TRACK = 48000


def _config() -> PlayerConfig:
    return PlayerConfig(sample_rate=SR_DEFAULT, enable_auto_mastering=True)


def test_auto_master_rebuilds_dsp_on_rate_change() -> None:
    auto_master = AutoMasterProcessor(_config())
    assert auto_master.compressor.sample_rate == SR_DEFAULT

    auto_master.set_sample_rate(SR_TRACK)
    assert auto_master.compressor.sample_rate == SR_TRACK
    assert auto_master.transient_enhancer.sample_rate == SR_TRACK


def test_attack_release_coefficients_track_the_rate() -> None:
    """The acceptance case: coefficients must correspond to 48 kHz, i.e.
    attack_coeff = exp(-1 / (attack_ms * 0.001 * 48000)), not the 44.1 kHz
    value the chain was originally built with."""
    at_default = AutoMasterProcessor(_config()).compressor.gain_follower.attack_coeff
    at_48k = AutoMasterProcessor(_config())
    at_48k.set_sample_rate(SR_TRACK)
    expected = np.exp(-1.0 / (20.0 * 0.001 * SR_TRACK))
    assert at_48k.compressor.gain_follower.attack_coeff == pytest.approx(expected)
    assert at_default != pytest.approx(expected)


def test_set_sample_rate_is_noop_when_unchanged() -> None:
    auto_master = AutoMasterProcessor(_config())
    compressor = auto_master.compressor
    auto_master.set_sample_rate(SR_DEFAULT)
    assert auto_master.compressor is compressor


def test_processor_reconfigures_chain_and_stats_use_real_rate() -> None:
    processor = RealtimeProcessor(_config())
    processor.set_effect_enabled("auto_mastering", True)
    processor.auto_master.set_enabled(True)

    durations: list[float] = []
    orig_record = processor.performance_monitor.record_processing_time

    def spy_record(processing_time: float, chunk_duration: float) -> None:
        durations.append(chunk_duration)
        orig_record(processing_time, chunk_duration)

    processor.performance_monitor.record_processing_time = spy_record

    chunk = np.zeros((1024, 2), dtype=np.float32)
    processor.process_chunk(chunk, sample_rate=SR_TRACK)

    assert processor.auto_master.compressor.sample_rate == SR_TRACK
    assert durations == [1024 / SR_TRACK]


def test_get_audio_chunk_passes_file_rate_to_processor(monkeypatch) -> None:
    """The wiring fix: the streaming mixin hands the file manager's real
    rate to process_chunk on every chunk."""

    class Harness(PlayerStreamingMixin):
        pass

    h = Harness()
    h.config = PlayerConfig(sample_rate=SR_DEFAULT, buffer_size=512)
    h.auto_advance = False
    h._auto_advancing = threading.Event()
    h._advance_generation = 0
    h._stop_requested = threading.Event()
    h._cleanup_in_progress = threading.Event()
    h._advance_thread = None
    h.playback = MagicMock()
    h.playback.is_playing.return_value = True
    h.playback.read_and_advance_position.return_value = 0

    fm = MagicMock()
    fm._audio_lock = threading.RLock()
    fm.is_loaded.return_value = True
    fm.get_total_samples.return_value = 44100 * 30
    fm.sample_rate = SR_TRACK  # file's rate differs from config's
    fm.get_audio_chunk.return_value = np.zeros((512, 2), dtype=np.float32)
    h.file_manager = fm

    h.queue = MagicMock()
    h.queue.has_next_track.return_value = False

    h.processor = MagicMock()
    h.processor.process_chunk.return_value = np.zeros((512, 2), dtype=np.float32)

    h.get_audio_chunk()

    assert h.processor.process_chunk.call_count == 1
    args = h.processor.process_chunk.call_args.args
    assert args[1] == SR_TRACK
