"""
End-to-End Integration Test: HTTP API -> ProcessingEngine -> HybridProcessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fixes #3819 (BE-TC-2). Every existing test of `routers/processing_api.py`
injects a `Mock(spec=ProcessingEngine)` — no test drives a real
`ProcessingEngine.process_job()` through a real `HybridProcessor.process()`
by way of the actual HTTP routes. That gap is exactly the class of bug that
shipped as #3489 (`process()` returns a bare `np.ndarray`; code that assumed
a `.audio`/`.lufs` result object silently raised `AttributeError` on every
successful job, routed through a catch-all "unexpected error" branch, and no
test caught it because the engine itself was always mocked).

This test uploads a real WAV via `POST /api/processing/upload-and-process`,
runs it through a live `ProcessingEngine` (real worker loop, real
`HybridProcessor`, real save), polls `GET /api/processing/job/{id}` until
COMPLETED, downloads via `GET /api/processing/job/{id}/download`, and
verifies the output is a decodable WAV with the same sample count as the
input. One test catches the entire class of #3489-style regressions.

:license: GPLv3
"""

import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingEngine
from routers.processing_api import create_processing_router


def _make_wav_bytes(tmp_path: Path, duration: float = 2.0, sample_rate: int = 44100) -> tuple[bytes, np.ndarray]:
    """Write a real sine-wave stereo WAV to disk and return (bytes, samples)."""
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo = np.column_stack([mono, mono])

    wav_path = tmp_path / "input.wav"
    sf.write(str(wav_path), stereo, sample_rate, subtype="PCM_16")
    return wav_path.read_bytes(), stereo


@pytest.mark.integration
@pytest.mark.audio
@pytest.mark.slow
@pytest.mark.asyncio
async def test_upload_and_process_end_to_end_with_real_engine(tmp_path):
    """Real ProcessingEngine + real HybridProcessor, driven entirely through
    the FastAPI HTTP routes (no mocks anywhere in the pipeline)."""
    engine = ProcessingEngine(max_concurrent_jobs=1)
    app = FastAPI()
    app.include_router(create_processing_router(lambda: engine))

    worker_task = asyncio.create_task(engine.start_worker())
    try:
        wav_bytes, input_samples = _make_wav_bytes(tmp_path)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            settings = json.dumps({"mode": "adaptive", "output_format": "wav", "bit_depth": 16})
            files = {"file": ("input.wav", wav_bytes, "audio/wav")}
            data = {"settings": settings}

            submit_resp = await client.post(
                "/api/processing/upload-and-process", files=files, data=data
            )
            assert submit_resp.status_code == 200, submit_resp.text
            job_id = submit_resp.json()["job_id"]

            status: dict | None = None
            for _ in range(300):  # up to ~30s of real DSP processing
                status_resp = await client.get(f"/api/processing/job/{job_id}")
                assert status_resp.status_code == 200
                status = status_resp.json()
                if status["status"] in ("completed", "failed"):
                    break
                await asyncio.sleep(0.1)

            assert status is not None
            assert status["status"] == "completed", status

            result_data = status["result_data"]
            assert result_data["sample_rate"] == 44100
            assert result_data["format"] == "wav"
            assert result_data["bit_depth"] == 16

            download_resp = await client.get(f"/api/processing/job/{job_id}/download")
            assert download_resp.status_code == 200
            assert download_resp.headers["content-type"] == "audio/wav"

            output_path = tmp_path / "downloaded_output.wav"
            output_path.write_bytes(download_resp.content)

            output_audio, output_sr = sf.read(str(output_path))
            assert output_sr == 44100
            assert len(output_audio) == len(input_samples), (
                "processed output sample count must match input "
                f"(input={len(input_samples)}, output={len(output_audio)})"
            )
            assert np.isfinite(output_audio).all()
    finally:
        await engine.stop_worker()
        if not worker_task.done():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
