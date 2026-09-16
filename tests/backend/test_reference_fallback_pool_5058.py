"""
The missing-reference fallback must not poison the processor pool (#5058)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`execute_job`'s fallback switched the pooled processor's config to
"adaptive" and never switched it back. HybridProcessor keeps its config by
reference, so the processor went back into ProcessorPool under the
reference/hybrid key with an adaptive config, and the next job WITH a
reference silently ran adaptive.

Also pinned: the router rejects a hybrid job without a reference (as it
already did for reference mode), and the upload endpoint, which takes no
reference at all, rejects both modes.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import io
import json
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.job_config import create_processor_config
from core.job_execution import execute_job
from core.job_models import ProcessingJob
from core.processor_pool import ProcessorPool
from routers import processing_api, processing_upload
from routers.processing_models import ProcessingSettings, ProcessRequest

SAMPLE_RATE = 8000


class _SpyProcessor:
    """Stands in for HybridProcessor: records the mode each call ran under."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.calls: list[tuple[str, bool]] = []

    def process(self, audio: np.ndarray, reference: np.ndarray | None = None) -> np.ndarray:
        self.calls.append((self.config.adaptive.mode, reference is not None))
        return audio.copy()

    def reset_dynamics(self) -> None: ...
    def reset_psychoacoustic_eq(self) -> None: ...
    def reset_limiter(self) -> None: ...
    def close(self) -> None: ...


def _engine() -> MagicMock:
    engine = MagicMock()
    engine._notify_progress = AsyncMock()
    engine.processing_timeout = 30.0
    engine._cancel_events = {}
    return engine


async def _run(pool: ProcessorPool, tmp_path: Path, name: str, reference: str | None) -> _SpyProcessor:
    """One job through the same acquire → execute → return path as process_job."""
    settings: dict[str, Any] = {"reference_path": reference} if reference else {}
    job = ProcessingJob(name, "/unused.wav", str(tmp_path / f"{name}.wav"), settings, mode="hybrid")
    audio = np.zeros((SAMPLE_RATE, 2), dtype=np.float32)
    config = create_processor_config(job, SAMPLE_RATE)
    processor = await pool.get_or_create(job.mode, config)
    await execute_job(_engine(), job, audio, SAMPLE_RATE, processor)
    await pool.cleanup(job.job_id, job.mode, config, processor, poisoned=False)
    return cast(_SpyProcessor, processor)


class TestFallbackDoesNotPoisonThePool:

    async def test_reference_job_after_a_fallback_still_uses_its_reference(self, tmp_path: Path) -> None:
        reference = tmp_path / "ref.wav"
        sf.write(str(reference), np.zeros((SAMPLE_RATE, 2), dtype=np.float32), SAMPLE_RATE)

        async def create(config: Any) -> _SpyProcessor:
            return _SpyProcessor(config)

        pool = ProcessorPool(create_processor=create)

        first = await _run(pool, tmp_path, "no-ref", reference=None)
        second = await _run(pool, tmp_path, "with-ref", reference=str(reference))

        assert second is first, "the second job should reuse the pooled processor"
        # The fallback ran adaptive; the next job ran hybrid with its reference.
        assert first.calls == [("adaptive", False), ("hybrid", True)]
        assert first.config.is_hybrid_mode()


class TestSubmitTimeRejection:

    async def test_hybrid_without_reference_is_422(self) -> None:
        engine = MagicMock()
        engine.create_job = AsyncMock()
        request = ProcessRequest(input_path="/in.wav", settings=ProcessingSettings(mode="hybrid"))

        with patch.object(processing_api, "validate_file_path", side_effect=lambda p, **_kw: Path(p)), \
             pytest.raises(HTTPException) as exc_info:
            await processing_api.process_audio(request, engine=engine)

        assert exc_info.value.status_code == 422
        assert "hybrid" in exc_info.value.detail
        engine.create_job.assert_not_called()

    @pytest.mark.parametrize("mode", ["reference", "hybrid"])
    async def test_upload_rejects_modes_that_need_a_reference(self, mode: str) -> None:
        engine = MagicMock()
        engine.create_job = AsyncMock()
        upload = UploadFile(file=io.BytesIO(b"RIFF" + b"\0" * 64), filename="a.wav")

        with patch.object(processing_upload, "_write_upload") as write, \
             pytest.raises(HTTPException) as exc_info:
            await processing_upload.upload_and_process(
                file=upload, settings=json.dumps({"mode": mode}), engine=engine,
            )

        assert exc_info.value.status_code == 422
        write.assert_not_called()
        engine.create_job.assert_not_called()

    def test_adaptive_does_not_require_a_reference(self) -> None:
        assert ProcessingSettings(mode="adaptive").requires_reference is False
