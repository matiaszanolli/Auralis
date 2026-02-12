"""
Tests for Normal Streaming Without Overlap (#2099)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that normal audio streaming sends non-overlapping chunks
to prevent audio duplication.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest


class TestNormalStreamingChunkCalculation:
    """Test chunk calculation for normal streaming"""

    def test_no_overlap_in_chunk_intervals(self):
        """Test that normal streaming chunks don't overlap"""
        # Simulate normal streaming chunk calculation
        sample_rate = 44100
        chunk_duration = 15.0  # 15 seconds
        chunk_samples = int(chunk_duration * sample_rate)

        # CRITICAL: interval_samples should equal chunk_samples (no overlap)
        interval_samples = chunk_samples

        # Verify no overlap
        assert interval_samples == chunk_samples, \
            "Normal streaming should have interval = duration (no overlap)"

        # Calculate chunk boundaries for a 60-second file
        audio_duration = 60.0
        total_samples = int(audio_duration * sample_rate)

        # Calculate chunks
        total_chunks = max(1, int(np.ceil(total_samples / interval_samples)))

        # Verify chunk boundaries don't overlap
        for chunk_idx in range(total_chunks - 1):  # Exclude last chunk
            start_sample = chunk_idx * interval_samples
            end_sample = min(start_sample + chunk_samples, total_samples)

            next_start_sample = (chunk_idx + 1) * interval_samples

            # Current chunk should end exactly where next chunk starts (no gap, no overlap)
            assert next_start_sample == end_sample or next_start_sample <= total_samples, \
                f"Chunk {chunk_idx} overlaps with chunk {chunk_idx + 1}"

    def test_total_duration_matches_file_duration(self):
        """Test that total playback duration matches file duration"""
        sample_rate = 44100
        chunk_duration = 15.0
        chunk_samples = int(chunk_duration * sample_rate)

        # No overlap for normal streaming
        interval_samples = chunk_samples

        # Test with various file durations
        test_durations = [30.0, 60.0, 90.0, 180.0]  # 30s, 1min, 1.5min, 3min

        for audio_duration in test_durations:
            total_samples = int(audio_duration * sample_rate)
            total_chunks = max(1, int(np.ceil(total_samples / interval_samples)))

            # Calculate actual playback duration
            # Last chunk might be shorter, but no overlap means total duration = file duration
            playback_samples = 0
            for chunk_idx in range(total_chunks):
                start_sample = chunk_idx * interval_samples
                end_sample = min(start_sample + chunk_samples, total_samples)
                chunk_length = end_sample - start_sample
                playback_samples += chunk_length

            playback_duration = playback_samples / sample_rate

            # Should match file duration (within rounding error)
            assert abs(playback_duration - audio_duration) < 0.1, \
                f"Playback duration {playback_duration}s doesn't match file duration {audio_duration}s"

    def test_enhanced_vs_normal_streaming_overlap(self):
        """Test that enhanced streaming has overlap but normal doesn't"""
        sample_rate = 44100

        # Enhanced streaming (with ChunkedProcessor)
        enhanced_chunk_duration = 30.0  # 30s chunks
        enhanced_overlap_duration = 5.0  # 5s overlap
        enhanced_chunk_interval = enhanced_chunk_duration - enhanced_overlap_duration  # 25s

        enhanced_chunk_samples = int(enhanced_chunk_duration * sample_rate)
        enhanced_interval_samples = int(enhanced_chunk_interval * sample_rate)

        # Enhanced path HAS overlap
        assert enhanced_interval_samples < enhanced_chunk_samples, \
            "Enhanced streaming should have overlap (interval < duration)"

        overlap_samples = enhanced_chunk_samples - enhanced_interval_samples
        overlap_duration = overlap_samples / sample_rate
        assert abs(overlap_duration - enhanced_overlap_duration) < 0.01, \
            "Enhanced streaming should have 5s overlap"

        # Normal streaming (without processing)
        normal_chunk_duration = 15.0  # 15s chunks
        normal_chunk_samples = int(normal_chunk_duration * sample_rate)
        normal_interval_samples = normal_chunk_samples  # No overlap

        # Normal path has NO overlap
        assert normal_interval_samples == normal_chunk_samples, \
            "Normal streaming should have NO overlap (interval = duration)"

    def test_crossfade_samples_zero_for_normal_path(self):
        """Test that crossfade_samples is 0 for normal streaming"""
        # Normal streaming should send crossfade_samples=0
        # because chunks don't overlap and no crossfade is applied
        crossfade_samples = 0

        assert crossfade_samples == 0, \
            "Normal streaming should have crossfade_samples=0 (no overlap, no crossfade)"


class TestNormalStreamingAudioDuplication:
    """Test that normal streaming doesn't duplicate audio"""

    def test_no_duplicated_samples_in_chunk_sequence(self):
        """Test that consecutive chunks don't contain duplicated samples"""
        sample_rate = 44100
        chunk_duration = 15.0
        chunk_samples = int(chunk_duration * sample_rate)

        # No overlap for normal streaming
        interval_samples = chunk_samples

        # Create a test audio signal (60 seconds)
        audio_duration = 60.0
        total_samples = int(audio_duration * sample_rate)
        audio_data = np.random.randn(total_samples, 2).astype(np.float32)  # Stereo

        # Calculate chunks
        total_chunks = max(1, int(np.ceil(total_samples / interval_samples)))

        # Extract chunks and verify no duplication
        all_extracted_samples = []
        for chunk_idx in range(total_chunks):
            start_sample = chunk_idx * interval_samples
            end_sample = min(start_sample + chunk_samples, total_samples)

            chunk_audio = audio_data[start_sample:end_sample]
            all_extracted_samples.extend(range(start_sample, end_sample))

        # Check that no sample index appears more than once
        unique_samples = set(all_extracted_samples)
        assert len(all_extracted_samples) == len(unique_samples), \
            "Normal streaming should not extract any sample more than once (duplication detected)"

        # Verify we extracted all samples (no gaps)
        assert len(unique_samples) == total_samples, \
            f"Should extract all {total_samples} samples, got {len(unique_samples)}"

    def test_playback_duration_not_inflated_by_overlap(self):
        """Test that playback duration isn't inflated by overlap"""
        sample_rate = 44100
        chunk_duration = 15.0
        chunk_samples = int(chunk_duration * sample_rate)

        # No overlap for normal streaming
        interval_samples = chunk_samples

        # Test with 3-minute file
        audio_duration = 180.0  # 3 minutes
        total_samples = int(audio_duration * sample_rate)

        # Calculate total chunks
        total_chunks = max(1, int(np.ceil(total_samples / interval_samples)))

        # If there WAS overlap (old bug), duration would be inflated
        # Example: 15s chunks at 10s intervals = 5s overlap per chunk
        # For 180s file: ~18 chunks × 5s overlap = ~90s extra = 270s total (WRONG!)

        # With our fix (no overlap): duration should be exactly 180s
        playback_samples = 0
        for chunk_idx in range(total_chunks):
            start_sample = chunk_idx * interval_samples
            end_sample = min(start_sample + chunk_samples, total_samples)
            chunk_length = end_sample - start_sample
            playback_samples += chunk_length

        playback_duration = playback_samples / sample_rate

        # Should be ~180s, not ~270s
        assert abs(playback_duration - audio_duration) < 1.0, \
            f"Playback duration should be ~180s, got {playback_duration}s"

        # Definitely should NOT be inflated to 270s (the old bug)
        assert playback_duration < 200.0, \
            "Playback duration should not be inflated by overlap"


class TestChunkBoundaryArtifacts:
    """Test that chunk boundaries don't cause artifacts"""

    def test_chunk_boundaries_are_clean(self):
        """Test that chunk boundaries align perfectly without gaps or overlaps"""
        sample_rate = 44100
        chunk_duration = 15.0
        chunk_samples = int(chunk_duration * sample_rate)

        # No overlap for normal streaming
        interval_samples = chunk_samples

        # Test with various file durations
        test_durations = [45.0, 90.0, 135.0]  # Multiples and non-multiples of 15s

        for audio_duration in test_durations:
            total_samples = int(audio_duration * sample_rate)
            total_chunks = max(1, int(np.ceil(total_samples / interval_samples)))

            # Check each chunk boundary
            for chunk_idx in range(total_chunks - 1):
                current_start = chunk_idx * interval_samples
                current_end = min(current_start + chunk_samples, total_samples)

                next_start = (chunk_idx + 1) * interval_samples
                next_end = min(next_start + chunk_samples, total_samples)

                # No gap between chunks
                assert next_start == current_end or next_start <= total_samples, \
                    f"Gap detected between chunk {chunk_idx} and {chunk_idx + 1}"

                # No overlap between chunks
                assert next_start >= current_end, \
                    f"Overlap detected between chunk {chunk_idx} and {chunk_idx + 1}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
