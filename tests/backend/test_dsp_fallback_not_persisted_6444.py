"""A degraded DSP fallback is served, but never stored as the chunk's mastered render (#6444).

``apply_enhancement`` returns the unprocessed input when the processor returns None or non-finite
output, and ``process_chunk_core`` substitutes 100 ms of silence when trimming leaves nothing.
Neither reported it, so ``render_chunk`` encoded the result and recorded it under the exact key a
successful render uses: every replay, seek-back and later stream then got the degraded chunk until
a restart. A fresh processor would most likely have rendered it fine.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "auralis-web" / "backend"))

from core.audio_processing_pipeline import AudioProcessingPipeline  # noqa: E402
from core.chunk_stream_state import DspFallbackError  # noqa: E402
from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402

from auralis.io.saver import save as save_audio  # noqa: E402

SR = 44100


@pytest.fixture
def processor(tmp_path):
    t = np.linspace(0, 20.0, 20 * SR)
    tone = np.sin(2 * np.pi * 440.0 * t)
    path = tmp_path / "tone.wav"
    save_audio(str(path), np.column_stack([tone, tone]), SR, subtype="PCM_16")
    return ChunkedAudioProcessor(track_id=1, filepath=str(path), preset="adaptive", intensity=1.0, chunk_cache={})


def _dsp(output):
    """A stand-in HybridProcessor whose process() returns ``output`` (or echoes its input)."""
    fake = MagicMock()
    fake.process.side_effect = (lambda audio: audio.copy()) if output == "echo" else (lambda audio: output)
    return fake


def _nan_like(audio):
    return np.full_like(audio, np.nan)


def _render(processor, dsp):
    with patch.object(processor, "hybrid_processor", return_value=dsp):
        return processor.process_chunk(0)


@pytest.mark.parametrize("bad", ["none", "nan", "inf"])
def test_a_fallback_render_is_served_but_not_cached(processor, bad):
    def broken(audio):
        return {"none": None, "nan": _nan_like(audio), "inf": np.full_like(audio, np.inf)}[bad]

    dsp = MagicMock()
    dsp.process.side_effect = broken

    path, audio = _render(processor, dsp)

    assert path == ""
    assert audio.shape[0] > 0
    assert np.all(np.isfinite(audio))
    assert processor._lookup_cached_chunk(0) is None
    assert not processor._get_chunk_path(0).exists()


def test_the_next_request_rerenders_on_a_fresh_processor_and_that_is_cached(processor):
    broken = MagicMock()
    broken.process.side_effect = lambda audio: None
    fallback_path, fallback_audio = _render(processor, broken)
    assert processor.processor is None, "the leased processor was not discarded"

    healthy = _dsp("echo")
    path, audio = _render(processor, healthy)

    healthy.process.assert_called_once()
    assert path != "" and Path(path).exists()
    assert processor._lookup_cached_chunk(0) is not None
    assert len(audio) == len(fallback_audio), "the sample count must not depend on the fallback"


def test_a_healthy_render_is_still_persisted(processor):
    path, _audio = _render(processor, _dsp("echo"))

    assert path != "" and Path(path).exists()
    assert processor._lookup_cached_chunk(0) is not None


def test_a_chunk_that_trims_to_nothing_is_not_persisted(processor):
    with patch.object(processor._boundary_manager, "trim_context", side_effect=lambda audio, _i: audio[:0]):
        path, audio = _render(processor, _dsp("echo"))

    assert path == ""
    assert audio.shape[0] > 0
    assert processor._lookup_cached_chunk(0) is None
    assert not processor._get_chunk_path(0).exists()


def test_get_wav_chunk_path_refuses_to_publish_a_fallback_as_the_durable_file(processor):
    broken = MagicMock()
    broken.process.side_effect = lambda audio: None

    with patch.object(processor, "hybrid_processor", return_value=broken):
        with pytest.raises(DspFallbackError):
            processor.get_wav_chunk_path(0)

    assert not processor._get_chunk_path(0).exists()
    assert processor._lookup_cached_chunk(0) is None
    assert processor.processor is None, "the leased processor was not discarded"


class TestApplyEnhancementReportsFallbacks:
    AUDIO = np.full((2000, 2), 0.1, dtype=np.float32)

    def _run(self, processor_output):
        reasons: list[str] = []
        fake = MagicMock()
        fake.process.return_value = processor_output
        result = AudioProcessingPipeline.apply_enhancement(self.AUDIO, fake, on_fallback=reasons.append)
        return result, reasons

    def test_none_output(self):
        result, reasons = self._run(None)
        assert result is self.AUDIO
        assert reasons == ["processor returned None"]

    def test_non_finite_output(self):
        result, reasons = self._run(np.full_like(self.AUDIO, np.nan))
        assert result is self.AUDIO
        assert reasons == ["processor output was not finite"]

    def test_finite_output_reports_nothing(self):
        result, reasons = self._run(self.AUDIO * 0.5)
        assert reasons == []
        assert np.allclose(result, self.AUDIO * 0.5)

    def test_a_processor_returning_its_input_object_is_not_a_fallback(self):
        result, reasons = self._run(self.AUDIO)
        assert result is self.AUDIO
        assert reasons == []
