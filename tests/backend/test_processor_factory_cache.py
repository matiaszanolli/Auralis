# -*- coding: utf-8 -*-

"""
Tests for ProcessorFactory config-based caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression tests for content-based config hashing (issue #2707).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from auralis.core.config.unified_config import UnifiedConfig
from core.processor_factory import ProcessorFactory


def test_config_hash_identical_for_equal_configs():
    """Two UnifiedConfig objects with same settings must produce the same hash."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig()
    config_b = UnifiedConfig()

    assert id(config_a) != id(config_b)
    assert factory._get_config_hash(config_a) == factory._get_config_hash(config_b)


def test_config_hash_differs_for_different_configs():
    """Configs with different settings must produce different hashes."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig(fft_size=4096)
    config_b = UnifiedConfig(fft_size=2048)

    assert factory._get_config_hash(config_a) != factory._get_config_hash(config_b)


def test_config_hash_none_returns_default():
    """None config must return the sentinel 'default' string."""
    factory = ProcessorFactory()
    assert factory._get_config_hash(None) == "default"


def test_get_or_create_reuses_processor_for_equal_configs():
    """Calling get_or_create twice with equivalent configs must return the same processor."""
    factory = ProcessorFactory()
    config_a = UnifiedConfig()
    config_b = UnifiedConfig()

    processor_a = factory.get_or_create(track_id=0, config=config_a)
    processor_b = factory.get_or_create(track_id=0, config=config_b)

    assert processor_a is processor_b
    assert len(factory._processor_cache) == 1
