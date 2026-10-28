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
# The publication step lives in this stdlib-only module (moved out of the loop
# in #5839); loading it by path keeps the real implementation under test.
ATOMIC_SOURCE = Path(__file__).resolve().parents[3] / "auralis/utils/atomic_write.py"


def _load_stage_module():
    fake_peak = types.ModuleType("auralis.core.mastering_process_chunk")
    fake_peak.compute_peak_db = lambda audio: 0.0
    fake_assembly = types.ModuleType("auralis.core.mastering_chunk_assembly")
    for name in (
        "apply_true_peak_guard", "assemble_write_region", "count_chunks", "merge_stage_info",
        "next_core_samples", "read_chunk",
    ):
        setattr(fake_assembly, name, lambda *args, **kwargs: None)
    # #5694: the loop's measurement pass reads the 4x-oversampled peak from
    # here as well.
    fake_assembly.true_peak_4x = lambda *args, **kwargs: 0.0
    fake_assembly.two_pass_correction_gain = lambda *args, **kwargs: 1.0
    atomic_spec = importlib.util.spec_from_file_location(
        "auralis.utils.atomic_write", ATOMIC_SOURCE,
    )
    if atomic_spec is None or atomic_spec.loader is None:
        raise RuntimeError("cannot load atomic_write")
    atomic_write = importlib.util.module_from_spec(atomic_spec)
    atomic_spec.loader.exec_module(atomic_write)
    stubbed = {
        "auralis.utils": types.ModuleType("auralis.utils"),
        "auralis.utils.atomic_write": atomic_write,
        "auralis.core.mastering_chunk_assembly": fake_assembly,
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

    def render(*args, **kwargs):
        # The real renderer reopens the precreated inode and closes it before
        # publication; replace it with a deterministic write to that same path.
        # #5694: _render_to_sink returns (info, chunks, sample_peak, true_peak)
        # — measured peaks under the ceilings so no correction engages and
        # this test stays focused on publication semantics. The measurement
        # pass passes output_path=None and must not write anything.
        if args[2] is not None:
            Path(args[2]).write_bytes(payload)
        return {"stages": [{"stage": "test"}]}, 1, 0.5, 0.5

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
            with mock.patch.object(os, "fsync", side_effect=synced), mock.patch.object(
                os, "replace", side_effect=replaced
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
