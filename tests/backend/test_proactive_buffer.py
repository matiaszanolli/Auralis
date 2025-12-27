"""
Tests for Proactive Buffer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the proactive buffering system for instant preset switching.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from proactive_buffer import AVAILABLE_PRESETS, PRELOAD_CHUNKS


class TestProactiveBufferConstants:
    """Tests for module constants"""

    def test_available_presets(self):
        """Test AVAILABLE_PRESETS constant"""
        assert isinstance(AVAILABLE_PRESETS, list)
        assert len(AVAILABLE_PRESETS) > 0
        assert "adaptive" in AVAILABLE_PRESETS
        assert "gentle" in AVAILABLE_PRESETS
        assert "warm" in AVAILABLE_PRESETS
        assert "bright" in AVAILABLE_PRESETS
        assert "punchy" in AVAILABLE_PRESETS

    def test_preload_chunks(self):
        """Test PRELOAD_CHUNKS constant"""
        assert isinstance(PRELOAD_CHUNKS, int)
        assert PRELOAD_CHUNKS == 3  # 90 seconds (3 x 30s)
        assert PRELOAD_CHUNKS > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
