"""
intensity is not part of the processor cache key (#4707).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ProcessorCacheKey`` included ``intensity`` and ``get_or_create`` forwarded it,
but the constructed ``HybridProcessor`` was never told about it: the method
applies only ``config.mastering_profile = preset.lower()`` plus optional
mastering targets. Intensity is realised downstream as a dry/wet blend on the
processor's *output* (``core/audio_processing_pipeline.py``).

Two calls differing only in intensity therefore built two byte-identical
processors and consumed two of the 32 LRU slots, so an intensity slider sweep
evicted genuinely distinct ``(track, preset)`` processors and forced redundant
200-500 ms constructions — each spinning up a fresh 5-thread fingerprint
executor (#3746).

Contrast ``targets_hash``, which #3720 added precisely because targets DO change
the constructed processor. That is the distinction these tests pin.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processor_factory import ProcessorCacheKey, ProcessorFactory  # noqa: E402


class TestKeyShape:
    def test_intensity_is_not_a_field(self):
        assert "intensity" not in ProcessorCacheKey._fields

    def test_the_remaining_fields_are_the_consumed_ones(self):
        assert ProcessorCacheKey._fields == (
            "track_id", "preset", "config_hash", "targets_hash",
        )

    def test_keys_differing_only_in_intensity_cannot_be_expressed(self):
        """The type itself now makes the bug unrepresentable."""
        with pytest.raises(TypeError):
            ProcessorCacheKey(  # type: ignore[call-arg]
                track_id=1, preset="adaptive", intensity=0.5,
                config_hash="h", targets_hash="none",
            )


class TestCacheSharing:
    """Acceptance criterion: two calls differing only in intensity share one
    processor."""

    @staticmethod
    def _factory_with_mocks(n: int):
        factory = ProcessorFactory()
        mocks = [MagicMock(name=f"processor_{i}") for i in range(n)]
        return factory, mocks

    def test_same_track_and_preset_at_different_intensities_reuses_one_processor(self):
        from auralis.core.config import UnifiedConfig

        factory, mocks = self._factory_with_mocks(4)
        with patch(
            "auralis.core.hybrid_processor.HybridProcessor", side_effect=mocks
        ) as ctor, patch.object(UnifiedConfig, "set_processing_mode"):
            config = UnifiedConfig()
            first = factory.get_or_create(
                track_id=7, preset="adaptive", intensity=0.5, config=config
            )
            second = factory.get_or_create(
                track_id=7, preset="adaptive", intensity=0.9, config=config
            )

        assert first is second, "an intensity change built a second processor"
        assert ctor.call_count == 1, (
            f"constructed {ctor.call_count} processors for one (track, preset) — "
            "intensity is still diluting the cache"
        )

    def test_an_intensity_sweep_occupies_one_slot(self):
        """The eviction pressure this issue is about."""
        from auralis.core.config import UnifiedConfig

        factory, mocks = self._factory_with_mocks(12)
        with patch(
            "auralis.core.hybrid_processor.HybridProcessor", side_effect=mocks
        ) as ctor, patch.object(UnifiedConfig, "set_processing_mode"):
            config = UnifiedConfig()
            for step in range(10):
                factory.get_or_create(
                    track_id=7, preset="adaptive",
                    intensity=step / 10.0, config=config,
                )

        assert ctor.call_count == 1
        assert len(factory._processor_cache) == 1, (
            f"a 10-step intensity sweep left {len(factory._processor_cache)} "
            "cache entries; it should leave 1"
        )


class TestStillDistinguishesRealDifferences:
    """Dropping a key field must not over-share."""

    @staticmethod
    def _run(calls):
        from auralis.core.config import UnifiedConfig

        factory = ProcessorFactory()
        mocks = [MagicMock(name=f"p{i}") for i in range(len(calls) + 2)]
        with patch(
            "auralis.core.hybrid_processor.HybridProcessor", side_effect=mocks
        ) as ctor, patch.object(UnifiedConfig, "set_processing_mode"):
            for kwargs in calls:
                factory.get_or_create(config=UnifiedConfig(), **kwargs)
        return ctor.call_count

    def test_different_presets_still_get_distinct_processors(self):
        count = self._run([
            {"track_id": 7, "preset": "adaptive", "intensity": 1.0},
            {"track_id": 7, "preset": "warm", "intensity": 1.0},
        ])
        assert count == 2

    def test_different_tracks_still_get_distinct_processors(self):
        count = self._run([
            {"track_id": 7, "preset": "adaptive", "intensity": 1.0},
            {"track_id": 8, "preset": "adaptive", "intensity": 1.0},
        ])
        assert count == 2

    def test_different_mastering_targets_still_get_distinct_processors(self):
        """#3720 must survive: targets DO change the constructed processor."""
        count = self._run([
            {"track_id": 7, "preset": "adaptive", "intensity": 1.0,
             "mastering_targets": {"lufs": -14.0}},
            {"track_id": 7, "preset": "adaptive", "intensity": 1.0,
             "mastering_targets": {"lufs": -9.0}},
        ])
        assert count == 2, (
            "targets_hash stopped distinguishing processors — #3720 regressed"
        )
