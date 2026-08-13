"""
Atomic `.25d` writes, shared by both writers (#4638 + #4508)

Both `.25d` writers opened their destination in ``'w'`` and streamed
``json.dump()`` into it. ``'w'`` truncates immediately, so an interruption
destroyed the previously-valid file *as well as* failing to produce the new one —
and with ``indent=2`` the payload spans several write syscalls, widening the
window. The two writers are:

  * ``SidecarManager.write`` (#4638) — ``<audiofile>.25d``, written **next to the
    user's audio file**, so leftover junk is user-visible;
  * ``FingerprintStorage.save`` (#4508) — ``~/.auralis/fingerprints/<hash>.25d``.

They were the same defect in two places, so per #4638 they now share one helper
(``auralis.utils.atomic_write.write_json_atomic``) rather than two copies that
drift apart. Fixing one without the other leaves the bug half-fixed.

The temp file must live in the *destination's* directory: ``os.replace()`` is
atomic only within a filesystem, and a music library is frequently on a different
mount (external drive, NAS) than ``/tmp``.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.library.sidecar_manager import SidecarManager
from auralis.utils.atomic_write import ATOMIC_TMP_PREFIX, write_json_atomic

PAYLOAD = {"version": "2.0", "fingerprint": {f"dim_{i}": i * 1.5 for i in range(25)}}


def _leftovers(directory: Path) -> list[str]:
    """Anything in `directory` that looks like an abandoned temp file."""
    return [p.name for p in directory.iterdir() if p.name.startswith(ATOMIC_TMP_PREFIX)]


class TestWriteJsonAtomic:
    """Unit behaviour of the shared helper."""

    def test_writes_the_payload(self, tmp_path):
        target = tmp_path / "out.25d"

        write_json_atomic(target, PAYLOAD)

        assert json.loads(target.read_text(encoding="utf-8")) == PAYLOAD

    def test_leaves_no_temp_file_on_success(self, tmp_path):
        target = tmp_path / "out.25d"

        write_json_atomic(target, PAYLOAD)

        assert _leftovers(tmp_path) == []
        assert [p.name for p in tmp_path.iterdir()] == ["out.25d"]

    def test_a_failed_write_preserves_the_previous_file(self, tmp_path):
        """The core of both issues: 'w' had already truncated it by now."""
        target = tmp_path / "out.25d"
        write_json_atomic(target, PAYLOAD)
        original = target.read_text(encoding="utf-8")

        with patch("json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                write_json_atomic(target, {"replacement": True})

        assert target.read_text(encoding="utf-8") == original, (
            "an interrupted write damaged the previously-valid file (#4638/#4508)"
        )

    def test_a_failed_write_leaves_no_temp_file(self, tmp_path):
        """Leftover junk in the user's music directory is user-visible."""
        target = tmp_path / "out.25d"
        write_json_atomic(target, PAYLOAD)

        with patch("json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                write_json_atomic(target, {"replacement": True})

        assert _leftovers(tmp_path) == []

    def test_a_serialization_failure_also_cleans_up(self, tmp_path):
        """ValueError, not OSError — the finally block must cover both."""
        target = tmp_path / "out.25d"

        with pytest.raises((ValueError, TypeError)):
            write_json_atomic(target, {"bad": object()})

        assert _leftovers(tmp_path) == []
        assert not target.exists()

    def test_temp_file_is_created_in_the_destination_directory(self, tmp_path):
        """Guard on cross-filesystem os.replace(): NOT the system temp dir."""
        target = tmp_path / "nested" / "out.25d"
        target.parent.mkdir()
        seen: list[Path] = []

        real_ntf = __import__("tempfile").NamedTemporaryFile

        def spy(*args, **kwargs):
            seen.append(Path(kwargs["dir"]))
            return real_ntf(*args, **kwargs)

        with patch("auralis.utils.atomic_write.tempfile.NamedTemporaryFile", side_effect=spy):
            write_json_atomic(target, PAYLOAD)

        assert seen == [target.parent], (
            f"temp file directory was {seen}, not the destination's parent — "
            "os.replace() is only atomic within one filesystem, and music "
            "libraries are often on a different mount than /tmp"
        )

    def test_fsyncs_before_replacing(self, tmp_path):
        """Without the fsync, os.replace can be durable while the contents are
        not — a power loss then leaves a correctly-named empty file, which looks
        valid and is worse than a torn write."""
        target = tmp_path / "out.25d"
        order: list[str] = []
        real_fsync, real_replace = os.fsync, os.replace

        with (
            patch("auralis.utils.atomic_write.os.fsync",
                  side_effect=lambda fd: (order.append("fsync"), real_fsync(fd))[1]),
            patch("auralis.utils.atomic_write.os.replace",
                  side_effect=lambda a, b: (order.append("replace"), real_replace(a, b))[1]),
        ):
            write_json_atomic(target, PAYLOAD)

        assert order == ["fsync", "replace"]

    def test_replace_is_used_rather_than_a_direct_open(self, tmp_path):
        target = tmp_path / "out.25d"

        with patch("auralis.utils.atomic_write.os.replace") as replace:
            write_json_atomic(target, PAYLOAD)

        assert replace.call_count == 1

    def test_sort_keys_and_indent_are_honoured(self, tmp_path):
        """FingerprintStorage.save writes sort_keys=True; output must match."""
        target = tmp_path / "out.25d"

        write_json_atomic(target, {"b": 1, "a": 2}, indent=2, sort_keys=True)

        text = target.read_text(encoding="utf-8")
        assert text.index('"a"') < text.index('"b"')
        assert "\n  " in text

    def test_nan_is_permitted_by_default(self, tmp_path):
        """Deliberate: adopting the helper is a pure atomicity change, so what
        gets written must not move. Non-finite dimensions are already rejected on
        read by #4910, so a NaN degrades to a cache miss, not to bad data."""
        target = tmp_path / "out.25d"

        write_json_atomic(target, {"x": float("nan")})

        assert "NaN" in target.read_text(encoding="utf-8")

    def test_nan_can_be_rejected_on_request(self, tmp_path):
        target = tmp_path / "out.25d"

        with pytest.raises(ValueError):
            write_json_atomic(target, {"x": float("inf")}, allow_nan=False)

        assert _leftovers(tmp_path) == []


class TestSidecarManagerWriteIsAtomic:
    """#4638 — the sidecar next to the user's audio file."""

    @pytest.fixture
    def audio(self, tmp_path) -> Path:
        f = tmp_path / "track.flac"
        f.write_bytes(b"not really audio, but it needs a size and an mtime")
        return f

    def test_interrupted_write_preserves_the_existing_sidecar(self, audio):
        mgr = SidecarManager()
        assert mgr.write(audio, {"fingerprint": {"a": 1.0}}) is True
        before = mgr.read(audio)
        assert before is not None

        with patch("json.dump", side_effect=OSError("kill -9 mid-scan")):
            assert mgr.write(audio, {"fingerprint": {"a": 2.0}}) is False

        after = mgr.read(audio)
        assert after == before, (
            "the previously-valid sidecar was destroyed by a failed write — "
            "'w' truncates before the first byte is written (#4638)"
        )

    def test_failed_write_returns_false_and_leaves_no_temp_file(self, audio, tmp_path):
        mgr = SidecarManager()

        with patch("json.dump", side_effect=OSError("disk full")):
            assert mgr.write(audio, {"fingerprint": {"a": 1.0}}) is False

        assert _leftovers(tmp_path) == [], (
            "a temp file was abandoned in the user's music directory"
        )

    def test_successful_write_leaves_only_the_sidecar(self, audio, tmp_path):
        mgr = SidecarManager()

        assert mgr.write(audio, {"fingerprint": {"a": 1.0}}) is True

        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "track.flac", "track.flac.25d",
        ]

    def test_round_trips_content_unchanged(self, audio):
        """The atomic path must not alter content or encoding."""
        mgr = SidecarManager()
        data = {"fingerprint": {"lufs": -14.5, "crest_db": 9.25}, "metadata": {"n": "é"}}

        assert mgr.write(audio, data) is True
        read_back = mgr.read(audio)

        assert read_back is not None
        assert read_back["fingerprint"] == data["fingerprint"]
        assert read_back["metadata"]["n"] == "é"


class TestFingerprintStorageSaveIsAtomic:
    """#4508 — the sibling writer, sharing the same helper."""

    def test_interrupted_save_preserves_the_existing_cache_entry(self, tmp_path, monkeypatch):
        cache_dir = tmp_path / "fingerprints"
        cache_dir.mkdir()
        monkeypatch.setattr(FingerprintStorage, "_get_cache_dir", staticmethod(lambda: cache_dir))
        audio = tmp_path / "track.flac"
        audio.write_bytes(b"audio")

        path = FingerprintStorage.save(audio, {"lufs": -14.0}, {"gain": 1.0})
        original = path.read_text(encoding="utf-8")

        with patch("json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                FingerprintStorage.save(audio, {"lufs": -99.0}, {"gain": 9.0})

        assert path.read_text(encoding="utf-8") == original, (
            "a failed save discarded an already-computed fingerprint (#4508)"
        )

    def test_failed_save_leaves_no_temp_file(self, tmp_path, monkeypatch):
        cache_dir = tmp_path / "fingerprints"
        cache_dir.mkdir()
        monkeypatch.setattr(FingerprintStorage, "_get_cache_dir", staticmethod(lambda: cache_dir))
        audio = tmp_path / "track.flac"
        audio.write_bytes(b"audio")

        with patch("json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                FingerprintStorage.save(audio, {"lufs": -14.0}, {"gain": 1.0})

        assert _leftovers(cache_dir) == []

    def test_save_still_round_trips_through_load(self, tmp_path, monkeypatch):
        """Integration: the atomic path must not alter content or encoding.

        `load()` requires the complete DIMENSION_SCHEMA to be present, so build a
        full 25-dimension fingerprint rather than a stub — a partial one is
        rejected as invalid regardless of how it was written.
        """
        from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA

        cache_dir = tmp_path / "fingerprints"
        cache_dir.mkdir()
        monkeypatch.setattr(FingerprintStorage, "_get_cache_dir", staticmethod(lambda: cache_dir))
        audio = tmp_path / "track.flac"
        audio.write_bytes(b"audio")

        fingerprint = {name: float(i) for i, name in enumerate(DIMENSION_SCHEMA)}
        FingerprintStorage.save(audio, fingerprint, {"gain": 1.0})
        loaded = FingerprintStorage.load(audio)

        assert loaded is not None, "the atomically-written cache entry did not load"
        loaded_fingerprint, targets = loaded
        assert loaded_fingerprint == fingerprint
        assert targets["gain"] == 1.0


class TestBothWritersShareOneImplementation:
    """SIBLING: two copies of this logic is what produced two issues."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "auralis/library/sidecar_manager.py",
            "auralis/analysis/fingerprint/fingerprint_storage.py",
        ],
    )
    def test_no_writer_open_codes_a_truncating_write(self, module_path):
        source = Path(module_path).read_text(encoding="utf-8")

        assert "write_json_atomic" in source, (
            f"{module_path} no longer uses the shared atomic writer (#4638/#4508)"
        )
        offenders = [
            ln.strip() for ln in source.splitlines()
            if ("open(" in ln and ("'w'" in ln or '"w"' in ln))
        ]
        assert offenders == [], (
            f"{module_path} still opens a destination in truncating mode: {offenders}"
        )
