"""Mastering output staging must preserve normal file creation permissions (#5592).

This stdlib-only focused test isolates the file publication step from DSP
dependencies while executing the real mastering_chunk_loop.process_chunks.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[3] / "auralis/core/mastering_chunk_loop.py"


def _load_stage_module():
    fake_peak = types.ModuleType("auralis.core.mastering_process_chunk")
    fake_peak.compute_peak_db = lambda audio: 0.0
    stubbed = {
        "auralis": types.ModuleType("auralis"),
        "auralis.core": types.ModuleType("auralis.core"),
        "auralis.core.mastering_process_chunk": fake_peak,
        "numpy": types.ModuleType("numpy"),
        "soundfile": types.ModuleType("soundfile"),
    }
    with mock.patch.dict(sys.modules, stubbed):
        spec = importlib.util.spec_from_file_location(
            "auralis.core.mastering_chunk_loop", SOURCE,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load mastering chunk loop")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _publish(module, output: Path, payload: bytes = b"completed master"):
    config = types.SimpleNamespace(CROSSFADE_DURATION_SEC=0.1, CHUNK_DURATION_SEC=1)

    def render(*args):
        # The real renderer reopens the precreated inode and closes it before
        # publication; replace it with a deterministic write to that same path.
        Path(args[2]).write_bytes(payload)
        return {"stages": ["test"]}, 1

    with mock.patch.object(module, "_render_to_sink", side_effect=render):
        return module.process_chunks(None, Path("unused.wav"), str(output), 8000,
                                     1, {}, 1.0, config, False)


@unittest.skipUnless(os.name == "posix", "POSIX file mode and umask required")
class MasteringStageModeTests(unittest.TestCase):
    def test_new_master_is_readable_under_normal_umask(self):
        module = _load_stage_module()
        old_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory() as root:
                output = Path(root) / "published.wav"
                self.assertEqual(_publish(module, output)[1], 1)
                self.assertEqual(output.stat().st_mode & 0o777, 0o644)
                self.assertEqual(output.read_bytes(), b"completed master")
        finally:
            os.umask(old_umask)

    def test_private_umask_is_respected_without_world_readability(self):
        module = _load_stage_module()
        old_umask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory() as root:
                output = Path(root) / "published.wav"
                _publish(module, output)
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        finally:
            os.umask(old_umask)

    def test_staged_master_is_synced_before_atomic_rename(self):
        module = _load_stage_module()
        order = []
        actual_sync, actual_replace = os.fsync, os.replace

        def synced(fd):
            order.append("fsync")
            return actual_sync(fd)

        def replaced(source, destination):
            order.append("replace")
            self.assertTrue(Path(source).exists())
            return actual_replace(source, destination)

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "published.wav"
            with mock.patch.object(module.os, "fsync", side_effect=synced), mock.patch.object(
                module.os, "replace", side_effect=replaced
            ):
                _publish(module, output)
            self.assertEqual(order, ["fsync", "replace"])

    def test_render_failure_preserves_existing_master_and_removes_stage(self):
        module = _load_stage_module()
        config = types.SimpleNamespace(CROSSFADE_DURATION_SEC=0.1, CHUNK_DURATION_SEC=1)
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "published.wav"
            output.write_bytes(b"original")
            with mock.patch.object(module, "_render_to_sink", side_effect=ValueError("DSP fail")):
                with self.assertRaisesRegex(ValueError, "DSP fail"):
                    module.process_chunks(None, Path("unused.wav"), str(output),
                                          8000, 1, {}, 1.0, config, False)
            self.assertEqual(output.read_bytes(), b"original")
            self.assertEqual([p.name for p in Path(root).iterdir()], ["published.wav"])


if __name__ == "__main__":
    unittest.main()
