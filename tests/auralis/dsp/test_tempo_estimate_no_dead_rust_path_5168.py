# -*- coding: utf-8 -*-

"""
Regression tests for #5168 — tempo_estimate's dead Rust fast path.

``tempo_estimate`` opened with a "try the Rust implementation first (3-5x
faster)" branch importing ``auralis.optimization.rust_integration``. That
module never existed, so the import raised ``ModuleNotFoundError`` on every
call and the enclosing ``except Exception`` swallowed it — nothing above
DEBUG, so it read as working.

The branch was removed rather than repointed at ``auralis_dsp.detect_tempo``,
because the premise was backwards: the Rust routine is ~25-29x *slower* than
the NumPy implementation (see the docstring for the measurements), and
``tempo_estimate`` is on the live analysis path.

These tests pin both halves so the branch cannot come back by copy-paste:
the module must not reference the phantom import path, and the function must
still return a correct BPM.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import importlib
import inspect

import numpy as np
import pytest

from auralis.dsp.utils import spectral
from auralis.dsp.utils.spectral import tempo_estimate

SAMPLE_RATE = 44100


def _click_track(bpm: float, seconds: float = 5.0, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Percussive clicks at a known BPM — an unambiguous onset train."""
    n = int(sample_rate * seconds)
    audio = np.zeros(n, dtype=np.float64)
    period = int(sample_rate * 60.0 / bpm)
    for start in range(0, n, period):
        length = min(2000, n - start)
        envelope = np.exp(-np.linspace(0.0, 20.0, length))
        tone = np.sin(2.0 * np.pi * 1000.0 * np.arange(length) / sample_rate)
        audio[start:start + length] += envelope * tone
    return audio


def test_module_does_not_reference_the_phantom_rust_import():
    """The import path that never existed must not reappear in executable code.

    Asserted against the source rather than by importing, because the original
    defect was precisely that the failed import was invisible at runtime.
    """
    source = inspect.getsource(spectral)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(('import ', 'from ')):
            assert 'rust_integration' not in stripped, (
                f"#5168: dead import is back: {stripped!r}"
            )


def test_optimization_rust_integration_really_does_not_exist():
    """Pin the fact the fix rests on, so a future module of that name is noticed."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('auralis.optimization.rust_integration')


@pytest.mark.parametrize('bpm', [90.0, 120.0, 140.0])
def test_tempo_estimate_recovers_a_known_bpm(bpm):
    """The surviving NumPy path lands in the right ballpark on a known BPM.

    The 15 % tolerance is deliberately loose and reflects measured behaviour,
    not an aspiration: on 20 s click tracks this implementation errs by 5-9 %
    (90 -> 96.4, 120 -> 126.4, 140 -> 152.4). That looseness is pre-existing —
    the function is documented as "rough tempo estimation" — and is out of
    scope for #5168, which is about the dead branch, not the estimator. The
    band is still tight enough to catch what matters here: a half- or
    double-tempo error, or a near-constant return.
    """
    estimated = tempo_estimate(_click_track(bpm, seconds=20.0), SAMPLE_RATE)
    assert estimated == pytest.approx(bpm, rel=0.15), (
        f"tempo_estimate returned {estimated:.2f} for a {bpm} BPM click track"
    )


def test_tempo_estimate_accepts_stereo():
    """Stereo input must not raise — the removed branch held the only ndim check."""
    mono = _click_track(120.0)
    stereo = np.column_stack([mono, mono])
    assert tempo_estimate(stereo, SAMPLE_RATE) > 0.0
