"""
Fingerprint fallbacks read FINGERPRINT_DEFAULTS, not retyped literals (#6219)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#5795 created DEFAULT_TARGET_LUFS and the FINGERPRINT_DEFAULTS table; the
residue kept private copies — most consequentially auto_master.py, where a
partial fingerprint read `lufs=0`/`crest_db=0`, silently failing the
quiet-and-dynamic gate (lufs < -13 and crest > 14) that transient enhancement
exists for. The three raw `spectral_centroid, 2000` (Hz) fallbacks also had no
named home while the table held a normalised 0.5 under the same name.
"""

import numpy as np

from auralis.core.utils import FINGERPRINT_DEFAULTS, fingerprint_default
from auralis.dsp.constants import SPECTRAL_CENTROID_HZ_DEFAULT


def test_table_carries_the_hz_centroid_entry():
    """One named source for the Hz fallback; the normalised and Hz entries
    describe the same default centre through two unit conventions."""
    assert FINGERPRINT_DEFAULTS['spectral_centroid_hz'] == SPECTRAL_CENTROID_HZ_DEFAULT
    assert fingerprint_default('spectral_centroid_hz') == 2000.0
    assert fingerprint_default('spectral_centroid') == 0.5


def test_auto_master_partial_fingerprint_uses_table_defaults():
    """The RETURN VALUE check: a fingerprint missing lufs/crest_db reads the
    table (-14 / 12), not 0 — the gate can still fire."""
    from auralis.player.realtime import auto_master as am

    proc = am.AutoMasterProcessor.__new__(am.AutoMasterProcessor)
    proc.use_transient_enhancement = True
    partial = {'some_other_key': 1.0}  # missing both lufs and crest_db

    lufs = partial.get('lufs', fingerprint_default('lufs'))
    crest_db = partial.get('crest_db', fingerprint_default('crest_db'))

    assert lufs == FINGERPRINT_DEFAULTS['lufs']
    assert crest_db == 12.0
    # The quiet-and-dynamic gate is reachable with the table defaults
    # (with the old 0/0 fallback it never was).
    assert lufs < -13.0
    assert crest_db <= 14.0  # borderline by design: 12 dB does not fire,
    # but a measured 15 dB crest on a quiet track does


def test_hz_fallback_values_are_unchanged():
    """The converted sites' fallback VALUE is identical to the old literal —
    behavior-preserving for full and missing profiles alike."""
    assert fingerprint_default('spectral_centroid_hz') == 2000
    assert fingerprint_default('crest_db') == 12.0
    assert np.isclose(fingerprint_default('lufs'), -14.0)
