"""A warm leased processor renders a chunk exactly like a freshly built one (#6542).

``ProcessorFactory.acquire()`` popped a released instance with its limiter gain
reduction, EQ smoothing and last-run analysis untouched, so a chunk rendered
without pre-roll (chunk 0, a seek target) started from wherever the previous
stream stopped, and that render went into the durable chunk cache. A warm
instance is now reset when it is leased again.
"""

import sys
from pathlib import Path

import numpy as np

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.processor_factory import ProcessorFactory  # noqa: E402

from auralis.core.config import UnifiedConfig  # noqa: E402

SR = 44100


def _tone(seconds: float, amplitude: float, freq: float, seed: int) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    noise = np.random.default_rng(seed).standard_normal(t.size) * 0.05
    mono = amplitude * np.sin(2 * np.pi * freq * t) + amplitude * noise
    return np.stack([mono, mono], axis=1).astype(np.float32)


def test_a_rereleased_processor_renders_chunk_zero_like_a_fresh_one():
    factory = ProcessorFactory()
    lease = dict(track_id=6542, preset="adaptive", config=UnifiedConfig(internal_sample_rate=SR))
    chunk0 = _tone(3.0, 0.2, 220.0, seed=1)

    first = factory.acquire(**lease)
    fresh_render = first.process(chunk0.copy())
    first.process(_tone(3.0, 0.98, 4000.0, seed=2))  # the previous stream ends somewhere loud and bright
    factory.release_lease(first, track_id=lease["track_id"], preset=lease["preset"], config=lease["config"])

    warm = factory.acquire(**lease)
    assert warm is first, "the released instance was not reused, so this test proves nothing"
    warm_render = warm.process(chunk0.copy())

    np.testing.assert_array_equal(warm_render, fresh_render)
