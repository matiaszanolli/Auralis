"""
Reference-mode job wiring — issue #4735.

`create_job()` stored `reference_path` into `job.settings` only when
`mode == "hybrid"`. `_execute_job` reads that one key for BOTH reference-
consuming modes, so every `mode="reference"` job lost its reference, fell into
the "fall back to adaptive" branch, and called `processor.process(audio)` with
`reference=None` — while `_build_config` had already switched the config into
reference mode. `HybridProcessor._process_impl` dispatches on:

    if is_reference_mode() and reference is not None: ...
    elif is_adaptive_mode(): ...
    elif is_hybrid_mode(): ...
    else: raise ValueError(f"Invalid processing mode: ...")

With reference mode set and reference None, none of the three arms match, so
every reference-mastering job raised `ValueError: Invalid processing mode:
reference` — surfaced to the client as a generic bad-input error.

The "fall back to adaptive" comment was also untrue: nothing moved the config
back to adaptive, which is precisely why the fallback raised instead of
falling back.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingEngine  # noqa: E402


def _bare_engine() -> ProcessingEngine:
    """A ProcessingEngine with just enough state for create_job()."""
    engine = ProcessingEngine.__new__(ProcessingEngine)
    engine.temp_dir = Path(tempfile.mkdtemp())
    engine.jobs = {}
    engine._jobs_lock = asyncio.Lock()
    return engine


async def _create(mode: str, reference_path: str | None):
    return await ProcessingEngine.create_job(
        _bare_engine(),
        input_path="/tmp/input.wav",
        settings={},
        mode=mode,
        reference_path=reference_path,
    )


class TestReferencePathIsStored:
    """The defect: the write was gated on hybrid, the read serves both."""

    @pytest.mark.asyncio
    async def test_reference_mode_keeps_the_reference_path(self):
        job = await _create("reference", "/tmp/ref.wav")
        assert job.settings.get("reference_path") == "/tmp/ref.wav"

    @pytest.mark.asyncio
    async def test_hybrid_mode_still_keeps_the_reference_path(self):
        job = await _create("hybrid", "/tmp/ref.wav")
        assert job.settings.get("reference_path") == "/tmp/ref.wav"

    @pytest.mark.asyncio
    async def test_adaptive_mode_does_not_store_a_reference(self):
        """Adaptive consumes no reference; storing one would be misleading."""
        job = await _create("adaptive", "/tmp/ref.wav")
        assert job.settings.get("reference_path") is None

    @pytest.mark.asyncio
    async def test_no_reference_supplied_stores_nothing(self):
        for mode in ("reference", "hybrid", "adaptive"):
            job = await _create(mode, None)
            assert job.settings.get("reference_path") is None, mode


class TestProcessorDispatch:
    """The downstream consequence the missing key produced."""

    @staticmethod
    def _audio(seed: int, scale: float = 0.1) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return (rng.standard_normal((44100, 2)) * scale).astype(np.float32)

    def test_reference_mode_without_reference_raises(self):
        """Pin the exact pre-fix failure, so a regression is unambiguous."""
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        config = UnifiedConfig()
        config.set_processing_mode("reference")
        processor = HybridProcessor(config)

        with pytest.raises(ValueError, match="Invalid processing mode"):
            processor.process(self._audio(0))

    def test_reference_mode_with_reference_processes(self):
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        config = UnifiedConfig()
        config.set_processing_mode("reference")
        processor = HybridProcessor(config)

        audio = self._audio(0)
        result = processor.process(audio, self._audio(1, scale=0.3))

        assert isinstance(result, np.ndarray)
        assert len(result) == len(audio)

    def test_restoring_adaptive_makes_the_fallback_actually_fall_back(self):
        """What the else-branch now does before calling process(audio)."""
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        config = UnifiedConfig()
        config.set_processing_mode("reference")
        processor = HybridProcessor(config)

        # Without this line the same call raises (see the test above).
        processor.config.set_processing_mode("adaptive")

        audio = self._audio(0)
        result = processor.process(audio)
        assert len(result) == len(audio)


class TestRequestValidation:
    """Router-boundary guards added alongside the wiring fix."""

    def test_mode_rejects_unknown_values(self):
        from pydantic import ValidationError
        from routers.processing_api import ProcessingSettings

        with pytest.raises(ValidationError):
            ProcessingSettings(mode="bogus")

    @pytest.mark.parametrize("mode", ["adaptive", "reference", "hybrid"])
    def test_mode_accepts_the_three_real_modes(self, mode):
        from routers.processing_api import ProcessingSettings

        assert ProcessingSettings(mode=mode).mode == mode

    def test_default_mode_is_adaptive(self):
        from routers.processing_api import ProcessingSettings

        assert ProcessingSettings().mode == "adaptive"
