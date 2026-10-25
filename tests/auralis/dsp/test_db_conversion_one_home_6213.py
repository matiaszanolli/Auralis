"""
db_to_amplitude is the one dB->linear inverse (#6213)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#5785 created amplitude_to_db and unified the scalar forward conversion, but
~29 inline ``10 ** (x / 20)`` sites and the three-names situation (floored
to_db, DBConversion wrapper, amplitude_to_db) remained. This pins the new
inverse, the retirement of both alternates, and value-identity of the
migrated core sites.
"""

import math

import numpy as np
import pytest

from auralis.dsp.utils.conversion import (
    amplitude_to_db,
    db_to_amplitude,
    peak_db,
)


def test_db_to_amplitude_round_trips_amplitude_to_db():
    for x in (1e-4, 0.01, 0.37, 0.5, 0.9, 1.0):
        assert db_to_amplitude(amplitude_to_db(x)) == pytest.approx(x, rel=1e-12)


def test_db_to_amplitude_basics():
    assert db_to_amplitude(0.0) == 1.0
    assert db_to_amplitude(6.0) == pytest.approx(10 ** (6 / 20), rel=1e-12)
    assert db_to_amplitude(-6.0) == pytest.approx(10 ** (-6 / 20), rel=1e-12)


def test_floored_to_db_is_gone():
    import auralis.dsp.utils.conversion as conv
    assert not hasattr(conv, 'to_db')


def test_dbconversion_wrapper_is_retired():
    import inspect
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    assert not (root / 'auralis/core/processing/base/db_conversion.py').exists()
    import re as _re
    for p in (root / 'auralis').rglob('*.py'):  # auralis/ only — not tests
        text = p.read_text()
        code = '\n'.join(
            l for l in text.splitlines()
            if not l.strip().startswith('#') and not l.strip().startswith('*')
        )
        assert 'DBConversion' not in code, p


def test_migrated_core_sites_are_value_identical():
    """The migrated 10**(x/20) sites keep their exact values."""
    # chunk_assembly: TP ceiling -0.5 dBFS == the old literal's result
    assert db_to_amplitude(-0.5) == 10 ** (-0.5 / 20)
    assert db_to_amplitude(0.27) == 10 ** (0.27 / 20)  # overshoot ratio
    # parallel_eq helper's boost tail
    boost_db = -3.0
    assert db_to_amplitude(boost_db) - 1.0 == 10 ** (boost_db / 20) - 1.0


def test_spectral_crest_matches_the_old_floored_result():
    from auralis.dsp.utils.spectral import crest_factor
    rng = np.random.default_rng(1)
    audio = (rng.standard_normal(8000) * 0.2).astype(np.float64)
    crest = crest_factor(audio)
    peak = np.max(np.abs(audio))
    rms = math.sqrt(float(np.mean(audio ** 2)))
    assert crest == pytest.approx(20 * np.log10(peak / rms), rel=1e-12)
    assert peak_db(audio, silence_db=-96.0) == pytest.approx(
        amplitude_to_db(peak, silence_db=-96.0)
    )
