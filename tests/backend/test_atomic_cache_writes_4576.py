"""Cache WAVs are written atomically and validated on hit (#4576).

Every producer of a cached chunk WAV used to write directly to the final,
content-addressed cache filename, and the hit path gated on `Path.exists()`
alone. A crash mid-write left a truncated file at exactly the key the cache
looks up, and served it as a hit forever: cache keys embed CACHE_VERSION, track
id, file signature, preset and intensity, so the poisoned entry survived
restarts and only a manual cache clear recovered. Nothing logged, because the
file *was* there — the one place in the backend where a failure produced
durable wrong audio rather than a transient error.
"""

import os
import struct
import sys
import time
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from core.encoding.atomic_io import (  # noqa: E402
    PARTIAL_SUFFIX,
    PARTIAL_MAX_AGE_SECONDS,
    atomic_save_audio,
    cleanup_partial_files,
    is_partial_path,
    is_wav_complete,
)


def _wav_bytes(n_samples: int = 100) -> bytes:
    """A minimal but valid 16-bit mono RIFF/WAVE file."""
    data = b"\x00\x01" * n_samples
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, 44100, 88200, 2, 16)
    body = b"WAVE" + fmt + struct.pack("<4sI", b"data", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


class TestWavCompletenessGate:
    """The gate that evicts entries poisoned before this fix shipped."""

    def test_accepts_a_complete_wav(self, tmp_path):
        p = tmp_path / "good.wav"
        p.write_bytes(_wav_bytes())
        assert is_wav_complete(p) is True

    def test_rejects_a_truncated_wav(self, tmp_path):
        """The exact poison case: header promises more than the file holds."""
        full = _wav_bytes()
        p = tmp_path / "short.wav"
        p.write_bytes(full[: len(full) // 2])
        assert is_wav_complete(p) is False

    def test_rejects_an_empty_or_header_only_file(self, tmp_path):
        empty = tmp_path / "empty.wav"
        empty.write_bytes(b"")
        assert is_wav_complete(empty) is False

        stub = tmp_path / "stub.wav"
        stub.write_bytes(b"RIFF")
        assert is_wav_complete(stub) is False

    def test_rejects_a_non_riff_file(self, tmp_path):
        p = tmp_path / "junk.wav"
        p.write_bytes(b"NOTAWAVE" + b"\x00" * 100)
        assert is_wav_complete(p) is False

    def test_rejects_a_missing_file(self, tmp_path):
        assert is_wav_complete(tmp_path / "nope.wav") is False

    def test_tolerates_trailing_chunks(self, tmp_path):
        """Only truncation is poison; extra trailing bytes are fine."""
        p = tmp_path / "extra.wav"
        p.write_bytes(_wav_bytes() + b"LIST" + b"\x00" * 32)
        assert is_wav_complete(p) is True


class TestStageAndReplace:
    """#5208: these exercised the deleted `atomic_write_bytes` wrapper.

    Retargeted onto `atomic_save_audio`, the only remaining entry point, so
    the `_stage_and_replace` behaviour they pin (crash-safety, overwrite of a
    poisoned entry, destination-directory creation) is still covered.
    """

    @staticmethod
    def _write(data: bytes):
        return lambda staged: Path(staged).write_bytes(data)

    def test_writes_the_complete_file(self, tmp_path):
        p = tmp_path / "chunk.wav"
        payload = _wav_bytes()
        atomic_save_audio(p, self._write(payload))

        assert p.read_bytes() == payload
        assert is_wav_complete(p)

    def test_leaves_nothing_behind_when_the_write_fails(self, tmp_path, monkeypatch):
        """A killed write must leave either no file or a complete one."""
        p = tmp_path / "chunk.wav"

        real_write_bytes = Path.write_bytes

        def _explode(self, data):
            if is_partial_path(self):
                raise OSError("simulated crash mid-write")
            return real_write_bytes(self, data)

        monkeypatch.setattr(Path, "write_bytes", _explode)

        with pytest.raises(OSError):
            atomic_save_audio(p, self._write(_wav_bytes()))

        assert not p.exists(), "a partial file was published at the canonical path"
        assert list(tmp_path.glob(f"*{PARTIAL_SUFFIX}*")) == [], "staging file leaked"

    def test_overwrites_an_existing_poisoned_file_completely(self, tmp_path):
        p = tmp_path / "chunk.wav"
        p.write_bytes(b"RIFF\x00\x00")          # pre-existing truncated entry
        assert not is_wav_complete(p)

        atomic_save_audio(p, self._write(_wav_bytes()))
        assert is_wav_complete(p)

    def test_creates_the_destination_directory(self, tmp_path):
        p = tmp_path / "nested" / "deeper" / "chunk.wav"
        atomic_save_audio(p, self._write(_wav_bytes()))
        assert is_wav_complete(p)


class TestAtomicSaveAudio:

    def test_publishes_only_after_the_save_callable_succeeds(self, tmp_path):
        p = tmp_path / "full.wav"

        def _save(staged: str) -> None:
            assert staged != str(p), "the callable must receive the STAGED path"
            assert is_partial_path(Path(staged))
            Path(staged).write_bytes(_wav_bytes())

        atomic_save_audio(p, _save)
        assert is_wav_complete(p)

    def test_no_file_at_canonical_path_when_the_save_raises(self, tmp_path):
        p = tmp_path / "full.wav"

        def _save(staged: str) -> None:
            Path(staged).write_bytes(b"RIFF partial")
            raise RuntimeError("encoder blew up")

        with pytest.raises(RuntimeError):
            atomic_save_audio(p, _save)

        assert not p.exists()
        assert list(tmp_path.glob(f"*{PARTIAL_SUFFIX}*")) == []

    def test_round_trips_through_the_real_saver(self, tmp_path):
        """End-to-end against auralis.io.saver, not a stub."""
        from auralis.io.saver import save as save_audio

        p = tmp_path / "real.wav"
        audio = np.zeros((4410, 2), dtype=np.float32)
        atomic_save_audio(p, lambda staged: save_audio(staged, audio, 44100, subtype="PCM_16"))

        assert is_wav_complete(p)


class TestPartialCleanup:

    def test_removes_stale_partials(self, tmp_path):
        (tmp_path / f".chunk.wav.abc{PARTIAL_SUFFIX}").write_bytes(b"junk")
        (tmp_path / f".chunk.wav.def{PARTIAL_SUFFIX}").write_bytes(b"junk")
        keep = tmp_path / "chunk.wav"
        keep.write_bytes(_wav_bytes())

        assert cleanup_partial_files(tmp_path) == 2
        assert keep.exists()
        assert list(tmp_path.glob(f"*{PARTIAL_SUFFIX}*")) == []

    def test_min_age_spares_a_partial_that_may_still_be_in_flight(self, tmp_path):
        """#5208: the age bar is what makes the sweep safe to run while
        another live backend owns the chunk cache. A staging file is
        indistinguishable by name from one that instance is still filling, so
        deleting a fresh one would break its os.replace()."""
        fresh = tmp_path / f".chunk.wav.fresh{PARTIAL_SUFFIX}"
        fresh.write_bytes(b"in flight")
        stale = tmp_path / f".chunk.wav.stale{PARTIAL_SUFFIX}"
        stale.write_bytes(b"orphan")
        old_mtime = time.time() - (PARTIAL_MAX_AGE_SECONDS * 2)
        os.utime(stale, (old_mtime, old_mtime))

        assert cleanup_partial_files(tmp_path, PARTIAL_MAX_AGE_SECONDS) == 1
        assert fresh.exists(), "an in-flight staging file was reaped"
        assert not stale.exists()

    def test_zero_min_age_reaps_everything(self, tmp_path):
        """The owning caller passes 0 and must clear even a just-written one."""
        (tmp_path / f".chunk.wav.fresh{PARTIAL_SUFFIX}").write_bytes(b"x")
        assert cleanup_partial_files(tmp_path) == 1

    def test_sweeps_a_real_staged_name(self, tmp_path):
        """Staged files are dotfiles; Path.glob must still match them.

        `glob.glob` skips a leading dot, so a sweep written with that module
        would silently no-op. This pins the name produced by the real writer
        rather than a hand-made fixture."""
        seen = []

        def _save(staged: str) -> None:
            seen.append(Path(staged))
            raise RuntimeError("die mid-write, but leave the file behind")

        # Suppress _stage_and_replace's own best-effort unlink so a staged
        # file survives the failure, standing in for a process killed mid-write.
        with pytest.raises(RuntimeError):
            with mock.patch.object(Path, "unlink", lambda self, **kw: None):
                atomic_save_audio(tmp_path / "chunk.wav", _save)

        assert seen and seen[0].exists(), "fixture did not leave a staged file"
        assert cleanup_partial_files(tmp_path) == 1
        assert not seen[0].exists()

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert cleanup_partial_files(tmp_path / "nope") == 0

    def test_staged_file_keeps_the_real_extension(self):
        """soundfile infers the container from the extension (#4576).

        A staged name ending in a bare '.part' makes auralis.io.saver.save
        raise "unable to get format from file extension", which would have
        broken every encode_and_save call in production.
        """
        from auralis.io.saver import save as save_audio
        import tempfile as _tf

        d = Path(_tf.mkdtemp())
        seen: list[Path] = []

        def _save(staged: str) -> None:
            seen.append(Path(staged))
            save_audio(staged, np.zeros((128, 2), dtype=np.float32), 44100, subtype="PCM_16")

        atomic_save_audio(d / "chunk.wav", _save)

        assert seen and seen[0].suffix == ".wav", "staged file lost its extension"
        assert is_partial_path(seen[0]), "staged file is not identifiable as a partial"

    def test_staged_file_is_not_matched_by_the_chunk_cleanup_patterns(self, tmp_path):
        """WAVEncoder.cleanup_track_chunks must not see staging files."""
        final = tmp_path / "track_7_sig_adaptive_1.0_0.wav"
        seen: list[Path] = []

        def _save(staged: str) -> None:
            seen.append(Path(staged))
            Path(staged).write_bytes(_wav_bytes())

        atomic_save_audio(final, _save)

        staged_name = seen[0].name
        matches = [p.name for p in tmp_path.glob("track_7_sig_*.wav")]
        assert staged_name not in matches
        assert final.name in matches


class TestEncodeAndSaveErrorClassification:
    """A write failure inside WAVEncoder.encode_and_save must classify as an
    encoding failure, not a generic read failure (#4919).

    core/encoding/wav_encoder.py used to raise a bare OSError on write
    failure, identical to the exception type processing_engine's
    _ERROR_CATEGORIES uses for read failures — and WAVEncoderError (checked
    FIRST, specifically so encoding failures beat the generic OSError
    classification) was never raised, so the misclassification always won.
    """

    def test_write_failure_raises_wav_encoder_error_not_bare_oserror(self, tmp_path, monkeypatch):
        from core.encoding.wav_encoder import WAVEncoder
        from core.encoding import WAVEncoderError

        encoder = WAVEncoder(tmp_path)
        audio = np.zeros((128, 2), dtype=np.float32)

        monkeypatch.setattr(
            "core.encoding.wav_encoder.save_audio",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )

        with pytest.raises(WAVEncoderError):
            encoder.encode_and_save(audio, 44100, tmp_path / "chunk.wav")

    def test_error_taxonomy_reports_encoding_failure_not_read_failure(self, tmp_path, monkeypatch):
        from core.encoding.wav_encoder import WAVEncoder
        from core.processing_engine import _safe_error_message

        encoder = WAVEncoder(tmp_path)
        audio = np.zeros((128, 2), dtype=np.float32)

        monkeypatch.setattr(
            "core.encoding.wav_encoder.save_audio",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )

        try:
            encoder.encode_and_save(audio, 44100, tmp_path / "chunk.wav")
            pytest.fail("expected encode_and_save to raise")
        except Exception as e:
            message = _safe_error_message(e)

        assert message == "Audio encoding failed", (
            f"got {message!r} — a write failure must not surface as a read failure"
        )


class TestCacheManagerGatesAgree:
    """Both gates must treat a truncated file the same way (#4576)."""

    def test_get_cached_chunk_path_evicts_a_truncated_entry(self, tmp_path):
        from core.chunk_cache_manager import ChunkCacheManager

        bad = tmp_path / "chunk.wav"
        bad.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")   # truncated

        cache: dict = {"k": str(bad)}
        mgr = ChunkCacheManager(cache)

        assert mgr.get_cached_chunk_path("k") is None, "served a truncated WAV as a hit"
        assert "k" not in cache, "poisoned entry was not evicted"

    def test_get_cached_chunk_path_serves_a_complete_entry(self, tmp_path):
        from core.chunk_cache_manager import ChunkCacheManager

        good = tmp_path / "chunk.wav"
        good.write_bytes(_wav_bytes())

        mgr = ChunkCacheManager({"k": str(good)})
        assert mgr.get_cached_chunk_path("k") == good

    def test_cache_chunk_path_refuses_to_record_a_truncated_file(self, tmp_path):
        from core.chunk_cache_manager import ChunkCacheManager

        bad = tmp_path / "chunk.wav"
        bad.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

        cache: dict = {}
        ChunkCacheManager(cache).cache_chunk_path("k", bad)

        assert "k" not in cache, (
            "a truncated file was recorded as a cache entry — the read gate "
            "would evict it, so the two gates disagree"
        )

    def test_cache_chunk_path_records_a_complete_file(self, tmp_path):
        from core.chunk_cache_manager import ChunkCacheManager

        good = tmp_path / "chunk.wav"
        good.write_bytes(_wav_bytes())

        cache: dict = {}
        ChunkCacheManager(cache).cache_chunk_path("k", good)
        assert cache["k"] == str(good)
