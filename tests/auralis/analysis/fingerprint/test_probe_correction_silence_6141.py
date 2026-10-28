"""Silent windows are left out of the probe-correction median (#6141).

A silent body window used to enter the median as the -70 LUFS / 0 dB sentinel,
and a probe quieter than -70 LUFS was dropped as "silent".
"""

import numpy as np

from auralis.analysis.fingerprint.windowed_compute import _apply_probe_correction

SR = 44100


def _tone(amplitude, seconds=1.0):
    t = np.arange(int(SR * seconds)) / SR
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[None, :]


def _silence(seconds=1.0):
    return np.zeros((1, int(SR * seconds)), dtype=np.float32)


def test_silent_body_does_not_pull_the_median_toward_minus_70():
    fingerprint = {'lufs': -120.0, 'crest_db': 0.0}

    _apply_probe_correction(fingerprint, _silence(), [_tone(0.3), _tone(0.3), _silence()])

    # median of the two real probes only: -10.4 dB-ish, not the -42 the sentinel gave
    assert -15.0 < fingerprint['lufs'] < -8.0
    assert 2.0 < fingerprint['crest_db'] < 4.0


def test_quiet_but_not_silent_probe_still_counts():
    fingerprint = {'lufs': -30.0, 'crest_db': 3.0}

    _apply_probe_correction(fingerprint, _tone(0.3), [_tone(0.00015)])  # about -76 LUFS

    assert fingerprint['lufs'] < -30.0  # the quiet probe took part in the median


def test_one_measurable_window_leaves_the_fingerprint_alone():
    fingerprint = {'lufs': -20.0, 'crest_db': 5.0}

    _apply_probe_correction(fingerprint, _tone(0.3), [_silence(), _silence()])

    assert fingerprint == {'lufs': -20.0, 'crest_db': 5.0}
