"""
Regression tests: the track's REAL sample rate reaches UnifiedConfig (#5306)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`UnifiedConfig.internal_sample_rate` defaults to 44100 and neither production
construction path used to override it, so every 48 kHz / 96 kHz track was
mastered as if it were 44.1 kHz: the psychoacoustic EQ's critical-band ->
FFT-bin mapping lands ~8.8% off at 48 kHz (2.18x at 96 kHz), every K-weighted
LUFS measurement targets the wrong loudness, the HF-aware limiter crossover
sits at the wrong frequency, and ContinuousMode's fresh-fingerprint fallback
resamples to 22050 Hz from the wrong `orig_sr` — feeding a pitch/time-distorted
signal into the 25D fingerprint that drives parameter generation. Nothing in
either pipeline resamples to 44.1 kHz, so the buffers really are at the file's
rate while the config claims otherwise.

The subtle half of this fix, and the reason for `test_per_chunk_render_*`
below: the streaming path re-queries ProcessorFactory on EVERY chunk via
chunk_render -> AudioProcessingPipeline.process_audio -> select_processor.
Passing a rate-aware config only at init time (chunk_processor_init) creates an
orphan cache entry and leaves every chunk rendered by the separate
`config_hash="default"` — i.e. 44.1 kHz — processor. A test that only checks
the init site cannot tell the real fix from the inert one.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import threading
from types import SimpleNamespace

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunk_processor_init import init_fingerprint_and_processor
from core.job_config import create_processor_config
from core.job_models import ProcessingJob
from core.processor_factory import ProcessorFactory


class _PassthroughProcessor:
    """Stands in for HybridProcessor: upholds len(output) == len(input) and
    returns a copy, so `apply_enhancement`'s invariant guards are satisfied
    without running 200-500 ms of real DSP for a wiring assertion."""

    def __init__(self) -> None:
        self._process_lock = threading.RLock()

    def process(self, audio, *_args, **_kwargs):
        return np.asarray(audio).copy()


class _SpyFactory:
    """Records every get_or_create/invalidate call's config."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.processor = _PassthroughProcessor()

    def get_or_create(self, **kwargs):
        self.calls.append(kwargs)
        return self.processor

    @property
    def rates(self) -> list[int | None]:
        return [
            None if c.get("config") is None else c["config"].internal_sample_rate
            for c in self.calls
        ]


# --------------------------------------------------------------------------
# Path 1: offline export job
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_job_config_carries_the_loaded_audio_rate(rate: int):
    job = ProcessingJob(
        job_id="j-5306", input_path="in.wav", output_path="out.wav",
        settings={"mode": "adaptive"},
    )
    config = create_processor_config(job, rate)
    assert config.internal_sample_rate == rate


def test_job_config_rate_is_required_not_defaulted():
    """A default would let a future call site silently regress to 44.1 kHz —
    the exact shape of this bug."""
    job = ProcessingJob(
        job_id="j-5306b", input_path="in.wav", output_path="out.wav",
        settings={"mode": "adaptive"},
    )
    with pytest.raises(TypeError):
        create_processor_config(job)  # type: ignore[call-arg]


def test_job_config_48k_is_not_the_44100_default():
    job = ProcessingJob(
        job_id="j-5306c", input_path="in.wav", output_path="out.wav",
        settings={"mode": "adaptive"},
    )
    assert create_processor_config(job, 48000).internal_sample_rate != 44100


# --------------------------------------------------------------------------
# Path 2: streaming chunk path — construction
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_chunk_processor_init_passes_rate_aware_config_to_factory(rate: int):
    """WIRING check: the config must reach get_or_create as `config=`, not be
    built and dropped."""
    factory = _SpyFactory()
    target_service = SimpleNamespace(load_fingerprint=lambda **_kw: None)

    fingerprint, targets, processor, config = init_fingerprint_and_processor(
        target_service, factory, 7, "track.flac", "adaptive", 1.0, rate
    )

    assert config is not None
    assert config.internal_sample_rate == rate
    assert factory.rates == [rate]
    assert factory.calls[0]["config"] is config
    assert processor is factory.processor


def test_chunk_processor_init_skips_config_for_original_audio():
    """preset=None means "serve the untouched file" — no processor, no config."""
    factory = _SpyFactory()
    target_service = SimpleNamespace(load_fingerprint=lambda **_kw: None)

    _fp, _targets, processor, config = init_fingerprint_and_processor(
        target_service, factory, 7, "track.flac", None, 1.0, 48000
    )

    assert processor is None
    assert config is None
    assert factory.calls == []


# --------------------------------------------------------------------------
# Path 2: streaming chunk path — the per-chunk render that actually does DSP
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rate", [48000, 96000])
def test_per_chunk_render_resolves_the_rate_aware_processor(rate: int):
    """The factory is re-queried per chunk. If this call omitted `config=`,
    `_get_config_hash(None)` -> "default" would address a DIFFERENT cache
    entry — a 44.1 kHz-assuming processor — and the init-site fix would be
    entirely inert."""
    factory = _SpyFactory()
    config = UnifiedConfig(internal_sample_rate=rate)

    AudioProcessingPipeline.process_audio(
        audio=np.random.uniform(-0.5, 0.5, (8192, 2)).astype(np.float32),
        preset="adaptive",
        intensity=1.0,
        processor_factory=factory,
        track_id=7,
        config=config,
    )

    assert factory.rates == [rate]
    assert factory.calls[0]["config"] is config


def test_per_chunk_render_passes_the_same_config_instance_as_init():
    """Both factory lookups for one track must produce the SAME cache key.
    Equal-but-distinct configs are fine (the hash is content-based); a missing
    one is not."""
    factory = _SpyFactory()
    target_service = SimpleNamespace(load_fingerprint=lambda **_kw: None)

    _fp, _t, _p, init_config = init_fingerprint_and_processor(
        target_service, factory, 7, "track.flac", "adaptive", 1.0, 48000
    )
    AudioProcessingPipeline.process_audio(
        audio=np.random.uniform(-0.5, 0.5, (8192, 2)).astype(np.float32),
        preset="adaptive",
        intensity=1.0,
        processor_factory=factory,
        track_id=7,
        config=init_config,
    )

    real_factory = ProcessorFactory()
    hashes = {real_factory._get_config_hash(c["config"]) for c in factory.calls}
    assert len(factory.calls) == 2
    assert len(hashes) == 1, "init and per-chunk lookups must share one cache key"
    assert "default" not in hashes


# --------------------------------------------------------------------------
# Cache identity
# --------------------------------------------------------------------------

def test_factory_cache_key_distinguishes_48k_from_44k():
    """ProcessorCacheKey already varies with the rate via
    `UnifiedConfig.to_dict()`, so no cache-invalidation work was needed — this
    pins that assumption."""
    factory = ProcessorFactory()
    hash_44 = factory._get_config_hash(UnifiedConfig(internal_sample_rate=44100))
    hash_48 = factory._get_config_hash(UnifiedConfig(internal_sample_rate=48000))

    assert hash_44 != hash_48
    assert factory._get_config_hash(None) == "default"
    assert hash_48 != "default"


def test_48k_config_reaches_the_dsp_stages_that_read_it():
    """The payoff: HybridProcessor's rate-dependent collaborators are built
    from the config, so a 48 kHz config really does move the EQ/loudness
    analysis off the 44.1 kHz grid."""
    from auralis.core.hybrid_processor import HybridProcessor

    processor = HybridProcessor(UnifiedConfig(internal_sample_rate=48000))
    try:
        assert processor.config.internal_sample_rate == 48000
        assert processor.get_processing_info()["sample_rate"] == 48000
        # Critical-band -> FFT-bin mapping is derived from the rate; at 48 kHz
        # a given bin sits ~8.8% higher in Hz than the 44.1 kHz assumption.
        assert processor.psychoacoustic_eq.sample_rate == 48000
    finally:
        processor.close()


def test_chunk_render_forwards_the_processors_own_config():
    """Pins the chunk_render.py half of the wiring: `process_chunk_core` must
    hand `ChunkedAudioProcessor.processor_config` to the pipeline. Dropping
    this one kwarg silently reverts the whole streaming path to 44.1 kHz."""
    from core import chunk_render

    factory = _SpyFactory()
    config = UnifiedConfig(internal_sample_rate=48000)
    audio = np.random.uniform(-0.5, 0.5, (4096, 2)).astype(np.float32)

    fake = SimpleNamespace(
        track_id=7,
        preset="adaptive",
        intensity=1.0,
        sample_rate=48000,
        mastering_targets=None,
        processor_config=config,
        _processor_factory=factory,
        _dsp_state_advanced=False,
        _validate_chunk_index=lambda _i: None,
        load_chunk=lambda _i, with_context=True: (audio, 0.0, 1.0),
        _boundary_manager=SimpleNamespace(trim_context=lambda chunk, _i: chunk),
        _smooth_level_transition=lambda chunk, _i: chunk,
    )

    out = chunk_render.process_chunk_core(fake, 0)

    assert factory.rates == [48000]
    assert factory.calls[0]["config"] is config
    assert len(out) == len(audio)  # sample-count invariant
