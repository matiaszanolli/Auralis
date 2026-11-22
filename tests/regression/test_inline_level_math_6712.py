"""Inline RMS / dB arithmetic stays on the shared helpers (#6712, follow-up to #6597).

Scalar RMS goes through ``auralis.dsp.basic.rms`` and scalar dB conversions through
``amplitude_to_db`` / ``db_to_amplitude`` / ``rms_db`` in
``auralis.dsp.utils.conversion``, so the silence convention is decided in one place.
The allowlist holds the helpers' own definitions and the per-sample / per-band
ARRAY conversions the scalar helpers do not take; each such site carries a
comment saying so. A new inline site must use a helper or join the allowlist with
a reason.
"""

import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = ("auralis", "auralis-web/backend")

INLINE_RMS = re.compile(r"np\.sqrt\(np\.mean\(.*\*\* ?2")
INLINE_DB = re.compile(r"20 ?\* ?np\.log10|10 \*\* \(")

ALLOWED = Counter({
    # The helpers themselves.
    ("auralis/dsp/basic.py", "rms"): 1,
    # A docstring describing the pre-#4101 NaN behaviour, not code.
    ("auralis-web/backend/core/audio_validation.py", "rms"): 1,
    # Per-band / per-sample arrays (each line says so).
    ("auralis/analysis/spectrum_weighting.py", "db"): 2,
    ("auralis/analysis/spectrum_operations.py", "db"): 1,
    ("auralis/dsp/eq/filters.py", "db"): 1,
    ("auralis/core/processing/base/compression_expansion.py", "db"): 2,
})
EXEMPT_FILES = {"auralis/dsp/utils/conversion.py"}


def _inline_sites() -> Counter:
    found: Counter = Counter()
    for root in ROOTS:
        for path in (REPO / root).rglob("*.py"):
            rel = path.relative_to(REPO).as_posix()
            if rel in EXEMPT_FILES:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if INLINE_RMS.search(line):
                    found[(rel, "rms")] += 1
                if INLINE_DB.search(line):
                    found[(rel, "db")] += 1
    return found


def test_no_new_inline_rms_or_db_math():
    unexpected = {site: n for site, n in _inline_sites().items() if n > ALLOWED[site]}
    assert not unexpected, (
        "inline RMS / dB arithmetic outside the shared helpers; use dsp.basic.rms or "
        f"dsp.utils.conversion (or allowlist a deliberate array site with a reason): {unexpected}"
    )


def test_allowlist_has_no_stale_entries():
    found = _inline_sites()
    stale = {site: n for site, n in ALLOWED.items() if found[site] < n}
    assert not stale, f"allowlisted sites that no longer exist; lower or drop them: {stale}"
