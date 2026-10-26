"""
Regression tests: process_adaptive / process_reference cache identity and
per-call state (#6087).

The cache keyed on ``id(config)`` while building each processor from a deep
copy, so a freed config's address could be handed to an unrelated config that
then received the first one's processor (wrong sample rate / EQ mapping), and
every call on a shared processor inherited the previous master's limiter and EQ
state.
"""

import gc
from unittest.mock import MagicMock

import numpy as np
import pytest

import auralis.core.hybrid_processor_singleton as hp_module
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor

SAMPLE_RATE = 44100


@pytest.fixture(autouse=True)
def _clean_cache():
    hp_module._processor_cache.clear()
    yield
    for processor in list(hp_module._processor_cache.values()):
        processor.close()
    hp_module._processor_cache.clear()


def _config(rate: int) -> UnifiedConfig:
    config = UnifiedConfig()
    config.internal_sample_rate = rate
    return config


def _music(seconds: float, seed: int, level: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    tone = np.sin(2 * np.pi * (110 + 40 * seed) * t)
    audio = level * (0.7 * tone + 0.3 * rng.standard_normal(t.size))
    return np.column_stack([audio, 0.9 * audio]).astype(np.float32)


class TestCacheIdentity:
    def test_reused_config_address_never_returns_the_freed_configs_processor(self):
        first = hp_module._get_or_create_processor(_config(44100), "adaptive")
        assert first.config.internal_sample_rate == 44100

        # Free the config and allocate new ones until CPython reuses its address
        # (the issue's repro hits it within ~30 tries); the assertion holds for
        # every allocation, reused address or not.
        reused = False
        for _ in range(200):
            gc.collect()
            candidate = _config(96000)
            processor = hp_module._get_or_create_processor(candidate, "adaptive")
            assert processor.config.internal_sample_rate == 96000
            assert processor is not first
            reused = reused or any(
                key.startswith(f"{id(candidate)}_") for key in hp_module._processor_cache
            )
            del candidate, processor
            hp_module._processor_cache.pop(next(reversed(hp_module._processor_cache)))
        assert reused is False  # keys are content hashes, never addresses

    def test_equal_content_shares_one_processor_and_different_content_does_not(self):
        a = hp_module._get_or_create_processor(_config(44100), "adaptive")
        same = hp_module._get_or_create_processor(_config(44100), "adaptive")
        other = hp_module._get_or_create_processor(_config(96000), "adaptive")

        assert same is a
        assert other is not a

    def test_mode_still_separates_entries(self):
        adaptive = hp_module._get_or_create_processor(None, "adaptive")
        reference = hp_module._get_or_create_processor(None, "reference")

        assert adaptive is not reference
        assert set(hp_module._processor_cache) == {"default_adaptive", "default_reference"}


class TestPerCallState:
    def test_state_is_reset_before_every_call(self, monkeypatch):
        processor = MagicMock()
        processor._process_lock = __import__("threading").RLock()
        processor.process.return_value = np.zeros((4, 2))
        monkeypatch.setattr(hp_module, "_get_or_create_processor", lambda config, mode: processor)

        hp_module.process_adaptive(np.zeros((4, 2)))
        hp_module.process_reference(np.zeros((4, 2)), np.zeros((4, 2)))

        assert processor.reset_psychoacoustic_eq.call_count == 2
        assert processor.reset_limiter.call_count == 2
        assert processor.reset_run_state.call_count == 2
        names = [c[0] for c in processor.method_calls]
        # Each call: resets first, then process.
        assert names[:4] == ["reset_psychoacoustic_eq", "reset_limiter", "reset_run_state", "process"]

    def test_second_unrelated_input_matches_a_fresh_processor(self):
        loud_first = _music(2.0, seed=1, level=0.9)
        unrelated = _music(2.0, seed=2, level=0.05)

        hp_module.process_adaptive(loud_first)
        after_first = hp_module.process_adaptive(unrelated)

        fresh_config = UnifiedConfig()
        fresh_config.set_processing_mode("adaptive")
        fresh = HybridProcessor(fresh_config)
        try:
            expected = fresh.process(unrelated)
        finally:
            fresh.close()

        assert after_first.shape == unrelated.shape
        np.testing.assert_allclose(after_first, expected, atol=1e-6)
