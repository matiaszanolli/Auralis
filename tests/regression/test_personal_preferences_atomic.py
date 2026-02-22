"""
Regression test: PersonalPreferences atomic write + file locking (#2376, #2212)

Verifies that PersonalPreferences.save() uses atomic writes (temp + os.replace)
and cross-platform file locking to prevent partial files from concurrent writers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import json
import os
import threading
from pathlib import Path

import pytest

from auralis.core.personal_preferences import (
    PersonalPreferences,
    _atomic_write,
)


class TestAtomicWrite:
    """Regression: _atomic_write must be crash-safe (#2212)."""

    def test_atomic_write_creates_file(self, tmp_path):
        path = tmp_path / "test.json"
        _atomic_write(path, '{"key": "value"}')
        assert path.exists()
        assert json.loads(path.read_text()) == {"key": "value"}

    def test_atomic_write_overwrites_existing(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text('{"old": true}')
        _atomic_write(path, '{"new": true}')
        assert json.loads(path.read_text()) == {"new": true}

    def test_no_partial_file_on_success(self, tmp_path):
        """After a successful write, no temp files should remain."""
        path = tmp_path / "test.json"
        _atomic_write(path, '{"data": 1}')

        temps = list(tmp_path.glob(".test.json.tmp*"))
        assert len(temps) == 0, f"Temp files left behind: {temps}"

    def test_uses_os_replace(self):
        """Atomic rename must use os.replace (atomic on all platforms)."""
        import inspect
        source = inspect.getsource(_atomic_write)
        assert "os.replace" in source, (
            "_atomic_write must use os.replace() for atomic rename"
        )


class TestConcurrentWrites:
    """Regression: concurrent saves must not corrupt preferences (#2212)."""

    def test_concurrent_saves_produce_valid_json(self, tmp_path):
        """Multiple threads saving simultaneously must not create partial JSON."""
        prefs_dir = tmp_path / "prefs"
        prefs_dir.mkdir()

        errors = []

        def save_prefs(thread_id):
            try:
                prefs = PersonalPreferences()
                prefs.bass_boost = float(thread_id)
                prefs.save(prefs_dir)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=save_prefs, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent save errors: {errors}"

        # Verify the final file is valid JSON
        for json_file in prefs_dir.glob("*.json"):
            content = json_file.read_text()
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                pytest.fail(f"Corrupted JSON in {json_file.name}: {e}")
