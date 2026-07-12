"""
Regression tests for core.env_config.get_int_env (#3917).

Covers the shared helper used to make MAX_CONCURRENT_STREAMS,
_SEND_QUEUE_MAXSIZE, _PROCESSOR_CACHE_MAX, and _FINGERPRINT_WORKERS
tunable via environment variables without a code edit + rebuild.
"""

from __future__ import annotations

import pytest

from core.env_config import get_int_env


def test_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("AURALIS_TEST_VAR", raising=False)
    assert get_int_env("AURALIS_TEST_VAR", 42) == 42


def test_returns_parsed_override_when_set(monkeypatch):
    monkeypatch.setenv("AURALIS_TEST_VAR", "99")
    assert get_int_env("AURALIS_TEST_VAR", 42) == 99


def test_falls_back_to_default_on_unparseable_value(monkeypatch, caplog):
    monkeypatch.setenv("AURALIS_TEST_VAR", "not-a-number")
    with caplog.at_level("WARNING"):
        assert get_int_env("AURALIS_TEST_VAR", 42) == 42
    assert "not a valid integer" in caplog.text


def test_falls_back_to_default_below_min_value(monkeypatch, caplog):
    monkeypatch.setenv("AURALIS_TEST_VAR", "0")
    with caplog.at_level("WARNING"):
        assert get_int_env("AURALIS_TEST_VAR", 42, min_value=1) == 42
    assert "below minimum" in caplog.text


def test_accepts_value_at_min_value(monkeypatch):
    monkeypatch.setenv("AURALIS_TEST_VAR", "1")
    assert get_int_env("AURALIS_TEST_VAR", 42, min_value=1) == 1


@pytest.mark.parametrize("raw", ["", "  ", "12.5", "1e3", "abc"])
def test_falls_back_to_default_on_various_unparseable_values(monkeypatch, raw):
    monkeypatch.setenv("AURALIS_TEST_VAR", raw)
    assert get_int_env("AURALIS_TEST_VAR", 42) == 42
