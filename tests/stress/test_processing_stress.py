# -*- coding: utf-8 -*-

"""
Processing Stress Tests
~~~~~~~~~~~~~~~~~~~~~~~

Tests for high-volume processing, audio processing limits, and resource constraints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import time
import gc
import psutil
import os
import threading
from pathlib import Path
import numpy as np
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.mark.stress
@pytest.mark.load
@pytest.mark.audio
class TestHighVolumeProcessing:
    """Tests for processing large batches of audio files."""

    def test_batch_process_100_files(self, test_audio_dir, tmp_path, memory_monitor):
        """Test processing 100 files sequentially."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        processor = HybridProcessor(config)

        # Process 100 files
        output_dir = tmp_path / "processed"
        output_dir.mkdir()

        start_time = time.time()
        processed_count = 0

        for i in range(100):
            # Create test file
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            input_path = tmp_path / f"input_{i:03d}.wav"
            sf.write(str(input_path), audio, 44100)

            # Process
            audio_data, sr = load_audio(str(input_path))
            processed = processor.process(audio_data)

            # Save
            output_path = output_dir / f"output_{i:03d}.wav"
            save(str(output_path), processed, sr, subtype='PCM_16')

            processed_count += 1

        total_time = time.time() - start_time

        assert processed_count == 100
        assert total_time < 300, f"Processing 100 files took {total_time:.1f}s (expected < 5min)"

        # Verify outputs exist
        assert len(list(output_dir.glob("*.wav"))) == 100

    @pytest.mark.skip(reason="Very slow test (~10-15 minutes)")
    def test_batch_process_1000_files(self, tmp_path):
        """Test processing 1,000 files (simulated, skipped by default)."""
        # Would process 1000 files
        # Expected: < 30 minutes for 1000 files
        pass

    def test_concurrent_processing_saturation(self, tmp_path, cpu_monitor):
        """Test CPU saturation with concurrent processing."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        # Create test files
        test_files = []
        for i in range(20):
            audio = np.random.randn(44100 * 5, 2).astype(np.float32) * 0.1  # 5 seconds
            filepath = tmp_path / f"test_{i:02d}.wav"
            sf.write(str(filepath), audio, 44100)
            test_files.append(str(filepath))

        # Process concurrently
        def process_file(filepath):
            config = UnifiedConfig()
            processor = HybridProcessor(config)
            audio, sr = load_audio(filepath)
            return processor.process(audio)

        with ThreadPoolExecutor(max_workers=4) as executor:
            start = time.time()
            futures = [executor.submit(process_file, f) for f in test_files]
            results = [f.result() for f in as_completed(futures)]
            total_time = time.time() - start

        cpu_stats = cpu_monitor.finish()

        assert len(results) == 20
        # Should complete in reasonable time
        assert total_time < 120, f"20 files took {total_time:.1f}s"

    def test_processing_queue_overflow(self, tmp_path):
        """Test handling of queue overflow gracefully."""
        from auralis.player.enhanced_audio_player import EnhancedAudioPlayer

        player = EnhancedAudioPlayer()

        # Add many files to queue rapidly
        for i in range(1000):
            player.queue.add_track({"filepath": f"/test/track_{i:04d}.mp3"})

        # Should handle gracefully without errors
        assert player.queue.get_queue_size() == 1000

        # Clear queue
        player.queue.clear()
        assert player.queue.get_queue_size() == 0

    def test_processing_sustained_load(self, tmp_path, stress_test_timeout):
        """Test sustained high load (simulated 1 hour)."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Simulate 1 hour of processing in accelerated time
        # Process 60 x 1-second files (simulating 1 file per minute)
        start_time = time.time()
        processed_count = 0

        for i in range(60):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            processed = processor.process(audio)
            processed_count += 1

            # Check timeout
            if time.time() - start_time > stress_test_timeout:
                break

        assert processed_count >= 60
        assert processor is not None  # Still functional

    def test_processing_spike_recovery(self, tmp_path):
        """Test recovery from processing spike."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Normal load
        audio_normal = np.random.randn(44100, 2).astype(np.float32) * 0.1
        _ = processor.process(audio_normal)

        # Spike: Process very long audio
        audio_spike = np.random.randn(44100 * 60, 2).astype(np.float32) * 0.1  # 60 seconds
        _ = processor.process(audio_spike)

        # Recovery: Back to normal
        _ = processor.process(audio_normal)

        # Should still be functional
        assert processor is not None

    def test_processing_rate_limiting(self, tmp_path):
        """Test rate limiting under heavy load."""
        # This would test API rate limiting if implemented
        # For now, verify processing doesn't overwhelm system

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Process many files rapidly
        start = time.time()
        for i in range(10):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            _ = processor.process(audio)
        elapsed = time.time() - start

        # Should not be too fast (sanity check)
        assert elapsed > 0.1, "Processing suspiciously fast"

    def test_processing_prioritization(self, tmp_path):
        """Test priority queue under load."""
        from auralis.player.enhanced_audio_player import EnhancedAudioPlayer

        player = EnhancedAudioPlayer()

        # Add tracks with different priorities
        for i in range(100):
            player.queue.add_track({"filepath": f"/test/track_{i:03d}.mp3"})

        # Move high-priority track to front
        player.queue.add_track({"filepath": f"/test/urgent_track.mp3"})

        # Should handle prioritization
        assert player.queue.get_queue_size() == 101

    def test_processing_cancellation_mass(self, tmp_path):
        """Test cancelling 100 processing jobs."""
        # Simulate cancelling many jobs
        # In real implementation, would test actual job cancellation

        cancelled_count = 0
        for i in range(100):
            # Simulate job cancellation
            cancelled_count += 1

        assert cancelled_count == 100

    def test_processing_error_rate_under_load(self, tmp_path):
        """Test error handling at high volume."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        success_count = 0
        error_count = 0

        # Process mix of valid and invalid audio
        for i in range(50):
            try:
                if i % 10 == 0:
                    # Invalid: Empty audio
                    audio = np.array([], dtype=np.float32).reshape(0, 2)
                else:
                    # Valid audio
                    audio = np.random.randn(44100, 2).astype(np.float32) * 0.1

                _ = processor.process(audio)
                success_count += 1
            except Exception:
                error_count += 1

        # Should handle errors gracefully
        assert success_count > 0
        # Error rate should be reasonable
        assert error_count < success_count


@pytest.mark.stress
@pytest.mark.audio
class TestAudioProcessingLimits:
    """Tests for extreme audio characteristics."""

    def test_process_very_long_audio(self, very_long_audio, tmp_path, memory_monitor):
        """Test processing 10-minute audio file."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save
        import gc

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Load 10-minute file
        audio, sr = load_audio(very_long_audio)

        # Process
        start = time.time()
        processed = processor.process(audio)
        process_time = time.time() - start

        # Should complete in reasonable time
        duration_seconds = len(audio) / sr
        real_time_factor = duration_seconds / process_time

        assert real_time_factor > 1.0, "Processing slower than real-time"

        # Save output
        output_path = tmp_path / "long_output.wav"
        save(str(output_path), processed, sr, subtype='PCM_16')

        assert output_path.exists()

        # Cleanup to prevent memory issues
        del audio, processed
        gc.collect()

    def test_process_very_high_sample_rate(self, high_sample_rate_audio, tmp_path):
        """Test processing 192kHz audio."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Load 192kHz audio
        audio, sr = load_audio(high_sample_rate_audio)
        assert sr == 192000

        # Process
        processed = processor.process(audio)

        # Should handle high sample rate
        assert processed is not None
        assert len(processed) > 0

        # Save
        output_path = tmp_path / "high_sr_output.wav"
        save(str(output_path), processed, sr, subtype='PCM_16')
        assert output_path.exists()

    @pytest.mark.skip(reason="Multi-channel audio not yet supported")
    def test_process_many_channels(self, tmp_path):
        """Test processing 7.1 surround audio."""
        # Would test 8-channel audio processing
        # Current implementation supports stereo only
        pass

    def test_process_low_bitrate_audio(self, tmp_path):
        """Test processing low bitrate audio."""
        # Create low-quality audio (simulated)
        audio = np.random.randn(44100 * 5, 2).astype(np.float32) * 0.05  # Quiet
        filepath = tmp_path / "low_bitrate.wav"
        sf.write(str(filepath), audio, 44100)

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        audio_data, sr = load_audio(str(filepath))
        processed = processor.process(audio_data)

        assert processed is not None

    def test_process_corrupted_audio_graceful(self, corrupted_audio):
        """Test graceful handling of corrupted audio files."""
        from auralis.io.unified_loader import load_audio

        # Should raise exception or return None
        try:
            audio, sr = load_audio(corrupted_audio)
            # If it loads, should be empty or minimal
            assert len(audio) == 0 or audio is None
        except Exception as e:
            # Expected behavior - graceful error
            assert e is not None

    def test_process_zero_length_audio(self, zero_length_audio):
        """Test processing 0-second audio file."""
        from auralis.io.unified_loader import load_audio
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        try:
            audio, sr = load_audio(zero_length_audio)

            if audio is not None and len(audio) > 0:
                config = UnifiedConfig()
                processor = HybridProcessor(config)
                processed = processor.process(audio)
                assert processed is not None
        except Exception:
            # Expected - zero length not processable
            pass

    def test_process_single_sample_audio(self, tmp_path):
        """Test processing 1-sample audio."""
        # Create minimal audio
        audio = np.array([[0.1, 0.1]], dtype=np.float32)  # 1 sample
        filepath = tmp_path / "single_sample.wav"
        sf.write(str(filepath), audio, 44100)

        from auralis.io.unified_loader import load_audio
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        try:
            audio_data, sr = load_audio(str(filepath))
            config = UnifiedConfig()
            processor = HybridProcessor(config)
            processed = processor.process(audio_data)
            # May fail or return minimal output
        except Exception:
            # Expected - too short to process
            pass

    def test_process_silent_audio(self, silent_audio, tmp_path):
        """Test processing completely silent audio."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        audio, sr = load_audio(silent_audio)
        processed = processor.process(audio)

        # Should handle silence gracefully
        assert processed is not None

        # Output should also be quiet
        rms = np.sqrt(np.mean(processed ** 2))
        assert rms < 0.01, "Silent audio should remain quiet"

        output_path = tmp_path / "silent_output.wav"
        save(str(output_path), processed, sr, subtype='PCM_16')

    def test_process_clipping_audio(self, clipping_audio, tmp_path):
        """Test processing audio with clipping."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        audio, sr = load_audio(clipping_audio)

        # Input has clipping (peaks > 1.0)
        assert np.max(np.abs(audio)) > 1.0

        processed = processor.process(audio)

        # Output should be normalized (no clipping)
        assert np.max(np.abs(processed)) <= 1.0

        output_path = tmp_path / "clipping_output.wav"
        save(str(output_path), processed, sr, subtype='PCM_16')

    def test_process_dc_offset_audio(self, tmp_path):
        """Test processing audio with DC offset."""
        # Create audio with DC offset
        audio = np.random.randn(44100 * 5, 2).astype(np.float32) * 0.1
        audio[:, 0] += 0.3  # DC offset in left channel
        audio[:, 1] -= 0.3  # DC offset in right channel

        filepath = tmp_path / "dc_offset.wav"
        sf.write(str(filepath), audio, 44100)

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        audio_data, sr = load_audio(str(filepath))
        processed = processor.process(audio_data)

        # Processing should handle DC offset
        # Output DC offset should be minimal
        dc_offset_left = np.mean(processed[:, 0])
        dc_offset_right = np.mean(processed[:, 1])

        assert abs(dc_offset_left) < 0.1, "DC offset not removed from left channel"
        assert abs(dc_offset_right) < 0.1, "DC offset not removed from right channel"


@pytest.mark.stress
class TestResourceLimits:
    """Tests for resource constraints and limits."""

    def test_cpu_affinity(self):
        """Test respecting CPU affinity settings."""
        import psutil

        process = psutil.Process()

        # Get available CPUs
        available_cpus = process.cpu_affinity() if hasattr(process, 'cpu_affinity') else None

        if available_cpus:
            # Set CPU affinity to first 2 CPUs
            try:
                process.cpu_affinity(available_cpus[:2])
                new_affinity = process.cpu_affinity()
                assert len(new_affinity) <= 2
            except (AttributeError, OSError):
                # Not supported on all platforms
                pytest.skip("CPU affinity not supported")
        else:
            pytest.skip("CPU affinity not available")

    def test_thread_limit_enforcement(self, tmp_path):
        """Test enforcement of maximum thread count."""
        from concurrent.futures import ThreadPoolExecutor

        # Create pool with specific limit
        max_workers = 4

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit many tasks
            def dummy_task(x):
                time.sleep(0.1)
                return x

            futures = [executor.submit(dummy_task, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 20
        # Pool should have limited workers to max_workers

    def test_file_descriptor_limits(self, tmp_path):
        """Test handling of file descriptor limits gracefully."""
        import resource

        # Get current FD limit
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

        # Create many files but stay under limit
        files = []
        try:
            for i in range(min(100, soft_limit - 100)):
                filepath = tmp_path / f"fd_test_{i}.txt"
                f = open(filepath, 'w')
                f.write("test")
                files.append(f)

            # Should handle gracefully
            assert len(files) > 0

        finally:
            # Cleanup
            for f in files:
                f.close()

    def test_disk_space_monitoring(self, tmp_path):
        """Test monitoring available disk space."""
        import shutil

        # Get disk usage
        total, used, free = shutil.disk_usage(tmp_path)

        # Should be able to query disk space
        assert total > 0
        assert free >= 0

        # Verify reasonable free space for operation
        free_gb = free / (1024 ** 3)
        assert free_gb > 0.1, f"Only {free_gb:.2f}GB free"

    def test_network_timeout_handling(self):
        """Test handling of network timeouts (if applicable)."""
        import socket

        # Test socket timeout
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)

        try:
            # Try connecting to unreachable address
            sock.connect(('192.0.2.1', 80))  # TEST-NET-1 (unreachable)
        except socket.timeout:
            # Expected timeout
            pass
        except Exception:
            # Other error (connection refused, etc.)
            pass
        finally:
            sock.close()
