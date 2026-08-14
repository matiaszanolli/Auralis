# -*- coding: utf-8 -*-

"""
EQSettings rejects odd fft_size at construction time (#4985)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Hermitian-mirror step shared by ``apply_eq_mono``,
``_apply_eq_mono_vectorized``, and ``_apply_eq_mono_parallel``/``_sequential``
(``spectrum[num_bins:] *= gain_curve[1:-1][::-1]``) is length-consistent only
for an even ``fft_size`` — for odd ``fft_size`` the two sides of the multiply
have mismatched lengths and raise a broadcast ``ValueError`` deep in the FFT
chain. Not reachable today (``EQSettings.fft_size`` defaults to 4096 and
the deleted ``RealtimeAdaptiveEQ`` always set ``buffer_size * 2``, always
even — #4873) — but
``fft_size`` is a caller-supplied int with no validation. This guards the
construction site with a clear, fail-fast error instead.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest

from auralis.dsp.eq.psychoacoustic_eq import EQSettings


def test_odd_fft_size_rejected_at_construction():
    with pytest.raises(ValueError, match="fft_size must be even"):
        EQSettings(fft_size=4097)


def test_even_fft_size_still_accepted():
    settings = EQSettings(fft_size=4096)
    assert settings.fft_size == 4096
