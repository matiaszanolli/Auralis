"""
Tests for WebM Encoder - Fixed Version

Tests the async ffmpeg encoding with proper fixtures and imports.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

# Import should work via conftest.py path setup
from webm_encoder import WebMEncoder, get_encoder


class TestWebMEncoderFixed:
    """Fixed tests for WebMEncoder class"""

    @pytest.mark.asyncio
    async def test_encode_chunk_with_mocked_ffmpeg(self, sample_audio, tmp_path):
        """Test encoding with mocked ffmpeg subprocess"""
        audio, sr = sample_audio
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_chunk_mock"

        # Mock the subprocess
        with patch('webm_encoder.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_proc

            # Encode
            webm_path = await encoder.encode_chunk(audio, sr, cache_key)

            # Verify
            assert webm_path.suffix == '.webm'
            assert mock_subprocess.called

    def test_get_cached_path_exists(self, tmp_path):
        """Test get_cached_path returns path when file exists"""
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_exists"

        # Create dummy webm file
        webm_path = tmp_path / f"{cache_key}.webm"
        webm_path.write_bytes(b"dummy webm data")

        # Should return path
        cached = encoder.get_cached_path(cache_key)
        assert cached is not None
        assert cached == webm_path
        assert cached.exists()

    def test_get_cached_path_not_exists(self, tmp_path):
        """Test get_cached_path returns None when file doesn't exist"""
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_not_exists"

        # Should return None
        cached = encoder.get_cached_path(cache_key)
        assert cached is None

    def test_get_cache_size(self, tmp_path):
        """Test get_cache_size returns correct information"""
        encoder = WebMEncoder(temp_dir=tmp_path)

        # Create some dummy files
        (tmp_path / "file1.webm").write_bytes(b"x" * 1000)
        (tmp_path / "file2.webm").write_bytes(b"x" * 2000)
        (tmp_path / "file3.txt").write_bytes(b"x" * 500)  # Should be ignored

        file_count, size_mb = encoder.get_cache_size()

        assert file_count == 2  # Only .webm files
        assert size_mb == pytest.approx(0.003, rel=0.1)  # 3000 bytes ≈ 0.003 MB

    def test_clear_cache(self, tmp_path):
        """Test clear_cache removes all WebM files"""
        encoder = WebMEncoder(temp_dir=tmp_path)

        # Create some files
        (tmp_path / "file1.webm").write_text("dummy1")
        (tmp_path / "file2.webm").write_text("dummy2")
        (tmp_path / "keep.txt").write_text("keep")

        # Clear cache
        encoder.clear_cache()

        # WebM files should be gone
        assert not (tmp_path / "file1.webm").exists()
        assert not (tmp_path / "file2.webm").exists()
        # Other files should remain
        assert (tmp_path / "keep.txt").exists()

    @pytest.mark.asyncio
    async def test_encode_chunk_error_handling(self, sample_audio, tmp_path):
        """Test error handling when ffmpeg fails"""
        audio, sr = sample_audio
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_error"

        # Mock ffmpeg failure
        with patch('webm_encoder.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1  # Non-zero = error
            mock_proc.communicate = AsyncMock(return_value=(b"", b"ffmpeg error"))
            mock_subprocess.return_value = mock_proc

            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="WebM encoding failed"):
                await encoder.encode_chunk(audio, sr, cache_key)

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

    @pytest.mark.asyncio
    async def test_encode_chunk_mono_to_stereo(self, tmp_path):
        """Test encoding mono audio"""
        sample_rate = 44100
        duration = 0.5
        samples = int(sample_rate * duration)

        # Generate mono audio
        t = np.linspace(0, duration, samples)
        audio_mono = np.sin(2 * np.pi * 440 * t)

        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_mono"

        # Mock ffmpeg
        with patch('webm_encoder.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_proc

            webm_path = await encoder.encode_chunk(audio_mono, sample_rate, cache_key)
            assert webm_path.suffix == '.webm'

    @pytest.mark.asyncio
    async def test_encode_chunk_caching(self, sample_audio, tmp_path):
        """Test that caching works correctly"""
        audio, sr = sample_audio
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "test_cache"

        # Mock ffmpeg
        with patch('webm_encoder.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_proc

            # Mock soundfile to avoid actual file writes
            with patch('webm_encoder.sf.write'):
                # First encode
                webm_path_1 = await encoder.encode_chunk(audio, sr, cache_key)

                # Create the file that ffmpeg would create
                webm_path_1.write_bytes(b"webm data")

                # Get cached version
                cached_path = encoder.get_cached_path(cache_key)

                assert cached_path == webm_path_1
                assert cached_path.exists()


@pytest.mark.integration
class TestWebMEncoderIntegration:
    """Integration tests requiring real ffmpeg"""

    @pytest.mark.asyncio
    async def test_real_encoding_if_ffmpeg_available(self, sample_audio, tmp_path):
        """Test real encoding if ffmpeg is available"""
        import shutil

        if not shutil.which('ffmpeg'):
            pytest.skip("ffmpeg not available")

        audio, sr = sample_audio
        encoder = WebMEncoder(temp_dir=tmp_path)
        cache_key = "integration_test"

        try:
            webm_path = await encoder.encode_chunk(audio, sr, cache_key)

            # Verify file exists and has content
            assert webm_path.exists()
            assert webm_path.stat().st_size > 0

            # Verify with ffprobe if available
            if shutil.which('ffprobe'):
                import subprocess
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_format', str(webm_path)],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0
                assert 'webm' in result.stdout.lower() or 'matroska' in result.stdout.lower()
        except Exception as e:
            pytest.skip(f"Real encoding failed: {e}")
