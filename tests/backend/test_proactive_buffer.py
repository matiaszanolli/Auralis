"""
Tests for Proactive Buffer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the proactive buffering system for instant preset switching.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.proactive_buffer import AVAILABLE_PRESETS, PRELOAD_CHUNKS


class TestProactiveBufferConstants:
    """Tests for module constants"""

    def test_available_presets(self):
        """Test AVAILABLE_PRESETS constant.

        Only 'adaptive' ships now (#4861 follow-up narrowed the enhancement
        preset system to a single preset); 'gentle'/'warm'/'bright'/'punchy'
        are gone, not just unlisted.
        """
        assert isinstance(AVAILABLE_PRESETS, list)
        assert AVAILABLE_PRESETS == ["adaptive"]

    def test_preload_chunks(self):
        """Test PRELOAD_CHUNKS constant"""
        assert isinstance(PRELOAD_CHUNKS, int)
        assert PRELOAD_CHUNKS == 3  # 90 seconds (3 x 30s)
        assert PRELOAD_CHUNKS > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
