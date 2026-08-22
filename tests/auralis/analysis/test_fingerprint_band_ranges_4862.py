"""
BAND_RANGES_HZ must match the DSP that actually does the split — issue #4862
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`schema.BAND_RANGES_HZ` is documentation-as-code: it records where the 7-band
energy split falls, but the split itself happens in Rust, driven by the `freqs`
edge array in `vendor/auralis-dsp/src/frequency_analysis.rs`. Nothing tied the
two together, and they drifted — the schema claimed presence was 4-6 kHz and air
6-20 kHz while the DSP used 4-8 kHz and 8-20 kHz.

That mattered only because `BAND_RANGES_HZ` has no consumers today. The moment
one appears — the docstring anticipates EQ targeting — it would compute against
a 2 kHz-wide slice of the spectrum that no band actually occupies, with nothing
to signal the mismatch.

So rather than restate the corrected numbers (which drifts again the same way),
these parse the edge array out of the Rust source and compare. If either side
moves, this fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from auralis.analysis.fingerprint.schema import BAND_RANGES_HZ

_RUST_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "vendor" / "auralis-dsp" / "src" / "frequency_analysis.rs"
)

# The band order the Rust `distribution` array is written in, which is also the
# order its 8 edges bracket. `FrequencyBands` declares the same sequence.
_BAND_ORDER = (
    "sub_bass_pct", "bass_pct", "low_mid_pct", "mid_pct",
    "upper_mid_pct", "presence_pct", "air_pct",
)


def _rust_band_edges() -> list[float]:
    """Pull `let freqs = [...]` out of frequency_analysis.rs."""
    source = _RUST_SOURCE.read_text()
    match = re.search(r"let freqs\s*=\s*\[([^\]]+)\]", source)
    assert match, (
        f"Could not find the `let freqs = [...]` edge array in {_RUST_SOURCE}. "
        "If it was renamed or restructured, update this test — do not delete it: "
        "it is the only thing keeping BAND_RANGES_HZ honest (#4862)."
    )
    return [float(part.strip()) for part in match.group(1).split(",") if part.strip()]


def test_rust_declares_one_more_edge_than_bands() -> None:
    """Sanity-check the parse before anything is compared against it."""
    edges = _rust_band_edges()
    assert len(edges) == len(_BAND_ORDER) + 1, edges
    assert edges == sorted(edges), "band edges must be ascending"


def test_schema_covers_exactly_the_seven_bands() -> None:
    assert tuple(BAND_RANGES_HZ) == _BAND_ORDER


@pytest.mark.parametrize("index,band", enumerate(_BAND_ORDER))
def test_each_band_matches_the_rust_edges(index: int, band: str) -> None:
    edges = _rust_band_edges()
    expected = (edges[index], edges[index + 1])
    assert BAND_RANGES_HZ[band] == expected, (
        f"{band} is documented as {BAND_RANGES_HZ[band]} but the DSP splits it "
        f"at {expected}. Fix whichever side is wrong — they must agree (#4862)."
    )


def test_bands_are_contiguous_and_cover_the_audible_range() -> None:
    """No gaps and no overlaps: each band starts where the previous one ended."""
    ranges = [BAND_RANGES_HZ[band] for band in _BAND_ORDER]
    for (_, upper), (lower, _) in zip(ranges, ranges[1:]):
        assert upper == lower

    assert ranges[0][0] == 20.0
    assert ranges[-1][1] == 20000.0


def test_the_specific_pair_that_had_drifted() -> None:
    """The regression itself, spelled out so the diff is legible."""
    assert BAND_RANGES_HZ["presence_pct"] == (4000.0, 8000.0)
    assert BAND_RANGES_HZ["air_pct"] == (8000.0, 20000.0)
