# -*- coding: utf-8 -*-

"""
AdaptationEngine state sizing and return-value aliasing (#4980)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defects in ``AdaptationEngine``, part of the unwired ``RealtimeAdaptiveEQ``
chain (#4615):

- Its state arrays were hardcoded to 26 elements ("26 critical bands"), but
  ``create_critical_bands()`` actually builds 25 bands from 26 Bark edges —
  index 25 was permanently unused. Arrays are now sized from
  ``len(create_critical_bands())``, matching the pattern already used by
  ``PsychoacousticEQ``.
- ``analyze_and_adapt`` returned the live, mutable
  ``adaptation_state['current_gains']`` array rather than a copy — the next
  call's in-place update would silently mutate a reference the caller still
  held.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from auralis.dsp.eq.critical_bands import create_critical_bands
from auralis.dsp.realtime_adaptive_eq.adaptation_engine import AdaptationEngine
from auralis.dsp.realtime_adaptive_eq.settings import RealtimeEQSettings


def _spectrum_analysis(num_bands: int) -> dict:
    return {
        'band_energies': np.full(num_bands, -20.0),
        'masking_thresholds': np.full(num_bands, -40.0),
    }


def test_state_arrays_sized_to_actual_critical_band_count():
    num_bands = len(create_critical_bands())
    engine = AdaptationEngine(RealtimeEQSettings())

    assert engine.adaptation_state['target_gains'].shape == (num_bands,)
    assert engine.adaptation_state['current_gains'].shape == (num_bands,)
    assert engine.adaptation_state['adaptation_speed'].shape == (num_bands,)


def test_analyze_and_adapt_returns_copy_not_live_array():
    num_bands = len(create_critical_bands())
    engine = AdaptationEngine(RealtimeEQSettings())

    first = engine.analyze_and_adapt(_spectrum_analysis(num_bands))
    internal_before = engine.adaptation_state['current_gains'].copy()

    assert first is not engine.adaptation_state['current_gains']

    # Mutating the caller's copy must not affect engine-internal state.
    first[:] = 999.0
    assert np.array_equal(engine.adaptation_state['current_gains'], internal_before)

    # A second call must not be affected by the first call's returned array
    # having been mutated by the caller.
    second = engine.analyze_and_adapt(_spectrum_analysis(num_bands))
    assert not np.array_equal(second, first)
