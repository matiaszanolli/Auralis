"""
Fingerprint window geometry has one home (#5797).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The 22050 Hz rate, 90 s body window, 30 s probe windows and the 25/50/75 %
positions were function-local variables in ``compute_windowed_fingerprint``,
with the rate and the 90 s duplicated in ``audio_fingerprint_analyzer``,
``mastering_fingerprint`` and the backend target service. The multi-window study
behind them showed LUFS bias moves with the window, so the library fingerprint and
the mastering fingerprint must not drift apart. They all read ``windows.py`` now.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
from pathlib import Path

import pytest

from auralis.analysis.fingerprint import windows
from auralis.analysis.fingerprint.windows import window_offset_s

_ROOT = Path(__file__).resolve().parents[4]


class TestWindowOffset:
    def test_places_the_window_at_the_fraction_of_the_track(self):
        assert window_offset_s(0.25, 400.0, 30.0) == 100.0

    def test_pulls_the_window_back_so_it_ends_at_the_track_end(self):
        # 75 % of 100 s is 75 s, but a 30 s window must start by 70 s.
        assert window_offset_s(0.75, 100.0, 30.0) == 70.0

    def test_a_track_shorter_than_the_window_starts_at_zero(self):
        assert window_offset_s(0.5, 20.0, 90.0) == 0.0

    def test_the_body_window_is_centred_by_the_same_rule(self):
        assert window_offset_s(windows.FINGERPRINT_BODY_POSITION, 1000.0, windows.FINGERPRINT_BODY_WINDOW_S) == 500.0


def test_the_documented_geometry_is_unchanged():
    # These values define the fingerprint; changing one shifts every stored LUFS.
    assert windows.FINGERPRINT_SAMPLE_RATE == 22050
    assert windows.FINGERPRINT_BODY_WINDOW_S == 90.0
    assert windows.FINGERPRINT_PROBE_WINDOW_S == 30.0
    assert windows.FINGERPRINT_BODY_POSITION == 0.50
    assert windows.FINGERPRINT_PROBE_POSITIONS == (0.25, 0.75)


@pytest.mark.parametrize(
    "rel",
    [
        "auralis/analysis/fingerprint/windowed_compute.py",
        "auralis/analysis/fingerprint/audio_fingerprint_analyzer.py",
        "auralis/analysis/mastering_fingerprint.py",
        "auralis-web/backend/core/mastering_target_service.py",
    ],
)
def test_no_module_retypes_the_geometry(rel):
    code = "\n".join(
        line for line in (_ROOT / rel).read_text().split("\n") if not line.lstrip().startswith("#")
    )
    assert not re.search(r"\b22050\b", code), rel
    assert not re.search(r"\b90\.0\b", code), rel
    assert not re.search(r"\(0\.25,\s*0\.75\)|\[0\.25,\s*0\.75\]", code), rel
