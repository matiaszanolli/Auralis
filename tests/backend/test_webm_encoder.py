"""
Tests for WebM Encoder

Tests the async ffmpeg encoding to WebM/Opus format for MSE streaming.
"""

import asyncio
import shutil

# Import the module to test
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))

from webm_encoder import WebMEncoder, get_encoder


@pytest.fixture
def encoder():
    """Create a WebMEncoder instance with temporary directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        encoder = WebMEncoder(temp_dir=temp_dir)
        yield encoder
        # Cleanup is automatic with temp_dir


@pytest.fixture
def sample_audio():
    """Generate sample audio data (1 second, 44.1kHz stereo)"""
    sample_rate = 44100
    duration = 1.0  # seconds
    samples = int(sample_rate * duration)

    # Generate a simple sine wave (440 Hz)
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make stereo
    audio_stereo = np.column_stack([audio, audio])

    return audio_stereo, sample_rate


class TestWebMEncoder:
    """Tests for WebMEncoder class"""

    @pytest.mark.asyncio
    async def test_encode_chunk_success(self, encoder, sample_audio):
        """Test successful encoding of audio chunk to WebM"""
        audio, sr = sample_audio
        cache_key = "test_chunk_1"

        # Encode audio
        webm_path = await encoder.encode_chunk(audio, sr, cache_key)

        # Verify output file exists
        assert webm_path.exists()
        assert webm_path.suffix == '.webm'
        assert webm_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_encode_chunk_bitrate(self, encoder, sample_audio):
        """Test encoding with different bitrates"""
        audio, sr = sample_audio

        # Test different bitrates
        bitrates = ['64k', '128k', '256k']
        sizes = []

        for bitrate in bitrates:
            cache_key = f"test_bitrate_{bitrate}"
            webm_path = await encoder.encode_chunk(audio, sr, cache_key, bitrate=bitrate)
            sizes.append(webm_path.stat().st_size)

        # Higher bitrate should result in larger file
        assert sizes[0] < sizes[1] < sizes[2], "File sizes should increase with bitrate"

    @pytest.mark.asyncio
    async def test_encode_chunk_caching(self, encoder, sample_audio):
        """Test that encoding results are cached"""
        audio, sr = sample_audio
        cache_key = "test_cache"

        # First encode
        webm_path_1 = await encoder.encode_chunk(audio, sr, cache_key)
        mtime_1 = webm_path_1.stat().st_mtime

        # Second encode with same cache_key
        await asyncio.sleep(0.1)  # Small delay to ensure different mtime
        webm_path_2 = await encoder.encode_chunk(audio, sr, cache_key)
        mtime_2 = webm_path_2.stat().st_mtime

        # Should be same file (cached)
        assert webm_path_1 == webm_path_2
        # mtime should be same (not re-encoded)
        assert mtime_1 == mtime_2

    def test_get_cached_path_exists(self, encoder, sample_audio):
        """Test get_cached_path returns path when file exists"""
        audio, sr = sample_audio
        cache_key = "test_exists"

        # Create a dummy webm file
        webm_path = encoder.temp_dir / f"{cache_key}.webm"
        webm_path.write_text("dummy")

        # Should return path
        cached = encoder.get_cached_path(cache_key)
        assert cached is not None
        assert cached == webm_path

    def test_get_cached_path_not_exists(self, encoder):
        """Test get_cached_path returns None when file doesn't exist"""
        cache_key = "test_not_exists"

        # Should return None
        cached = encoder.get_cached_path(cache_key)
        assert cached is None

    def test_get_cache_size(self, encoder):
        """Test get_cache_size returns correct information"""
        # Create some dummy files
        (encoder.temp_dir / "file1.webm").write_bytes(b"x" * 1000)
        (encoder.temp_dir / "file2.webm").write_bytes(b"x" * 2000)
        (encoder.temp_dir / "file3.txt").write_bytes(b"x" * 500)  # Should be ignored

        file_count, size_mb = encoder.get_cache_size()

        assert file_count == 2  # Only .webm files
        assert size_mb == pytest.approx(0.003, rel=0.1)  # 3000 bytes ≈ 0.003 MB

    def test_clear_cache(self, encoder):
        """Test clear_cache removes all WebM files"""
        # Create some files
        (encoder.temp_dir / "file1.webm").write_text("dummy1")
        (encoder.temp_dir / "file2.webm").write_text("dummy2")
        (encoder.temp_dir / "keep.txt").write_text("keep")

        # Clear cache
        encoder.clear_cache()

        # WebM files should be gone
        assert not (encoder.temp_dir / "file1.webm").exists()
        assert not (encoder.temp_dir / "file2.webm").exists()
        # Other files should remain
        assert (encoder.temp_dir / "keep.txt").exists()

    @pytest.mark.asyncio
    async def test_encode_chunk_mono_audio(self, encoder):
        """Test encoding mono audio"""
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)

        # Generate mono audio
        t = np.linspace(0, duration, samples)
        audio_mono = np.sin(2 * np.pi * 440 * t)

        cache_key = "test_mono"
        webm_path = await encoder.encode_chunk(audio_mono, sample_rate, cache_key)

        assert webm_path.exists()
        assert webm_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_encode_chunk_error_handling(self, encoder):
        """Test error handling with invalid audio data"""
        # Empty audio
        audio_empty = np.array([])
        sample_rate = 44100
        cache_key = "test_error"

        with pytest.raises(RuntimeError, match="WebM encoding failed"):
            await encoder.encode_chunk(audio_empty, sample_rate, cache_key)

    @pytest.mark.asyncio
    async def test_encode_chunk_concurrent(self, encoder, sample_audio):
        """Test concurrent encoding operations"""
        audio, sr = sample_audio

        # Encode multiple chunks concurrently
        tasks = [
            encoder.encode_chunk(audio, sr, f"concurrent_{i}")
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        assert all(path.exists() for path in results)
        assert all(path.stat().st_size > 0 for path in results)


class TestGetEncoder:
    """Tests for get_encoder singleton function"""

    def test_get_encoder_singleton(self):
        """Test that get_encoder returns the same instance"""
        encoder1 = get_encoder()
        encoder2 = get_encoder()

        assert encoder1 is encoder2

    def test_get_encoder_creates_temp_dir(self):
        """Test that get_encoder creates temp directory"""
        encoder = get_encoder()

        assert encoder.temp_dir.exists()
        assert encoder.temp_dir.is_dir()


@pytest.mark.integration
class TestWebMEncoderIntegration:
    """Integration tests with real ffmpeg"""

    @pytest.mark.asyncio
    async def test_encode_real_audio_file(self, encoder, tmp_path):
        """Test encoding a real audio file"""
        # Create a real WAV file using soundfile
        try:
            import soundfile as sf
        except ImportError:
            pytest.skip("soundfile not installed")

        # Generate audio
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio = np.sin(2 * np.pi * 440 * t)
        audio_stereo = np.column_stack([audio, audio])

        # Encode to WebM
        cache_key = "integration_test"
        webm_path = await encoder.encode_chunk(audio_stereo, sample_rate, cache_key)

        # Verify file is valid WebM using ffprobe (if available)
        import shutil as sh
        if sh.which('ffprobe'):
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_format', str(webm_path)],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, "ffprobe should recognize the file"
            assert 'matroska,webm' in result.stdout.lower() or 'webm' in result.stdout.lower()
        else:
            pytest.skip("ffprobe not available for validation")
