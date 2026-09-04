"""Content-aware file signature regression coverage (#5256)."""

import os
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_cache_manager import ChunkCacheManager  # noqa: E402
from core.chunk_path_cache import ChunkPathCache  # noqa: E402
from core.file_signature import FileSignatureService  # noqa: E402


def test_same_size_same_mtime_rewrite_changes_signature(tmp_path: Path) -> None:
    source = tmp_path / "track.flac"
    source.write_bytes(b"a" * (FileSignatureService.CONTENT_SAMPLE_BYTES * 3))
    original_stat = source.stat()
    original = FileSignatureService.generate(str(source))

    source.write_bytes(b"b" * original_stat.st_size)
    os.utime(
        source,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    rewritten = FileSignatureService.generate(str(source))

    assert source.stat().st_size == original_stat.st_size
    assert source.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert rewritten != original


def test_signature_format_and_unchanged_file_stability(tmp_path: Path) -> None:
    source = tmp_path / "short.wav"
    source.write_bytes(b"RIFF" + b"\0" * 32)

    first = FileSignatureService.generate(str(source))
    second = FileSignatureService.generate(str(source))

    assert first == second
    assert len(first) == 8
    assert all(character in "0123456789abcdef" for character in first)


def test_same_size_edit_misses_existing_chunk_path_cache(tmp_path: Path) -> None:
    source = tmp_path / "track.raw"
    source.write_bytes(b"a" * (FileSignatureService.CONTENT_SAMPLE_BYTES * 3))
    original_stat = source.stat()
    old_signature = FileSignatureService.generate(str(source))

    wav_encoder = MagicMock()
    wav_encoder.get_chunk_path.side_effect = (
        lambda track_id, file_signature, preset, intensity, chunk_index: tmp_path
        / f"{track_id}_{file_signature}_{preset}_{intensity}_{chunk_index}.wav"
    )
    cache_manager = ChunkCacheManager({})
    old_cache = ChunkPathCache(
        track_id=1,
        file_signature=old_signature,
        preset="adaptive",
        intensity=1.0,
        wav_encoder=wav_encoder,
        cache_manager=cache_manager,
    )
    old_chunk = old_cache.get_chunk_path(0)
    with wave.open(str(old_chunk), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44_100)
        output.writeframes(b"\0\0" * 100)
    old_cache.store(0, old_chunk)
    assert old_cache.lookup_cached(0) == old_chunk

    source.write_bytes(b"b" * original_stat.st_size)
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    new_signature = FileSignatureService.generate(str(source))
    new_cache = ChunkPathCache(
        track_id=1,
        file_signature=new_signature,
        preset="adaptive",
        intensity=1.0,
        wav_encoder=wav_encoder,
        cache_manager=cache_manager,
    )

    assert new_signature != old_signature
    assert new_cache.lookup_cached(0) is None
