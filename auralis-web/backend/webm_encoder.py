"""
WebM Encoder for MSE Progressive Streaming

Encodes audio chunks to WebM/Opus format for efficient MSE streaming.
Uses ffmpeg for encoding with optimized settings.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class WebMEncoder:
    """
    Encodes audio to WebM/Opus format for MSE streaming.

    Features:
    - High-quality Opus encoding (128kbps VBR)
    - Async encoding with ffmpeg
    - Automatic cleanup of temporary files
    - Error handling and logging
    """

    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "auralis_webm_cache"
        self.temp_dir.mkdir(exist_ok=True)
        logger.info(f"WebM encoder initialized, temp dir: {self.temp_dir}")

    async def encode_chunk(
        self,
        audio: np.ndarray,
        sample_rate: int,
        cache_key: str,
        bitrate: str = "128k"
    ) -> Path:
        """
        Encode audio chunk to WebM/Opus format.

        Args:
            audio: Audio data as numpy array (samples x channels)
            sample_rate: Sample rate in Hz
            cache_key: Unique identifier for caching
            bitrate: Target bitrate (default: 128k)

        Returns:
            Path to encoded WebM file

        Raises:
            RuntimeError: If encoding fails
        """
        try:
            # Create temp WAV file
            temp_wav = self.temp_dir / f"{cache_key}_temp.wav"
            output_webm = self.temp_dir / f"{cache_key}.webm"

            # Save audio to temporary WAV
            logger.debug(f"Writing temp WAV: {temp_wav}")
            sf.write(str(temp_wav), audio, sample_rate)

            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-i', str(temp_wav),
                '-c:a', 'libopus',           # Opus codec
                '-b:a', bitrate,              # Target bitrate
                '-vbr', 'on',                 # Variable bitrate
                '-compression_level', '10',   # Max compression
                '-application', 'audio',      # Optimize for audio (not voip)
                '-frame_duration', '20',      # 20ms frames (good for music)
                '-y',                         # Overwrite output
                '-loglevel', 'error',         # Suppress ffmpeg output
                str(output_webm)
            ]

            # Run ffmpeg asynchronously
            logger.debug(f"Encoding to WebM: {output_webm}")
            start_time = asyncio.get_event_loop().time()

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"ffmpeg encoding failed: {error_msg}")
                raise RuntimeError(f"WebM encoding failed: {error_msg}")

            # Calculate encoding time
            encoding_time = asyncio.get_event_loop().time() - start_time

            # Get file sizes for logging
            wav_size = temp_wav.stat().st_size / (1024 * 1024)  # MB
            webm_size = output_webm.stat().st_size / (1024 * 1024)  # MB
            compression_ratio = (1 - webm_size / wav_size) * 100 if wav_size > 0 else 0

            logger.info(
                f"WebM encoding complete: {cache_key} "
                f"({wav_size:.2f}MB → {webm_size:.2f}MB, "
                f"{compression_ratio:.1f}% compression, "
                f"{encoding_time:.2f}s)"
            )

            # Clean up temporary WAV
            temp_wav.unlink(missing_ok=True)

            return output_webm

        except Exception as e:
            logger.error(f"Error encoding WebM chunk: {e}", exc_info=True)
            # Clean up on error
            if temp_wav.exists():
                temp_wav.unlink(missing_ok=True)
            raise RuntimeError(f"WebM encoding failed: {str(e)}")

    def get_cached_path(self, cache_key: str) -> Optional[Path]:
        """
        Check if WebM file exists in cache.

        Args:
            cache_key: Unique identifier

        Returns:
            Path if exists, None otherwise
        """
        webm_path = self.temp_dir / f"{cache_key}.webm"
        if webm_path.exists():
            logger.debug(f"WebM cache HIT: {cache_key}")
            return webm_path
        return None

    def clear_cache(self):
        """
        Clear all cached WebM files.
        """
        try:
            count = 0
            for webm_file in self.temp_dir.glob("*.webm"):
                webm_file.unlink()
                count += 1
            logger.info(f"Cleared {count} WebM cache files")
        except Exception as e:
            logger.error(f"Error clearing WebM cache: {e}")

    def get_cache_size(self) -> tuple[int, float]:
        """
        Get cache statistics.

        Returns:
            (file_count, total_size_mb)
        """
        try:
            files = list(self.temp_dir.glob("*.webm"))
            total_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
            return len(files), total_size
        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0, 0.0


# Global encoder instance
_encoder: Optional[WebMEncoder] = None


def get_encoder() -> WebMEncoder:
    """
    Get global WebM encoder instance (singleton).
    """
    global _encoder
    if _encoder is None:
        _encoder = WebMEncoder()
    return _encoder


async def encode_audio_to_webm(
    audio: np.ndarray,
    sample_rate: int,
    cache_key: str
) -> Path:
    """
    Convenience function to encode audio to WebM.

    Args:
        audio: Audio data
        sample_rate: Sample rate
        cache_key: Unique identifier

    Returns:
        Path to encoded WebM file
    """
    encoder = get_encoder()

    # Check cache first
    cached_path = encoder.get_cached_path(cache_key)
    if cached_path:
        return cached_path

    # Encode
    return await encoder.encode_chunk(audio, sample_rate, cache_key)
