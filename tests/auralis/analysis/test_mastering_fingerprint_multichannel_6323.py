"""MasteringFingerprint folds >2 channels like the 25D windows (#6323).

It took the first two channels of a 5.1 file and averaged them, so a signal that lives in the Center
channel measured as silence. The 25D fingerprint folds with the BS.775 matrix (Center and surrounds
included); the mastering fingerprint now does too.
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.mastering_fingerprint import MasteringFingerprint

SR = 22050


@pytest.fixture
def center_only_5_1(tmp_path):
    t = np.arange(5 * SR) / SR
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    audio = np.zeros((tone.size, 6), dtype=np.float32)
    audio[:, 2] = tone  # channel 3 of a 5.1 layout (FL FR FC LFE BL BR) is the Center
    path = tmp_path / "center_only.wav"
    sf.write(path, audio, SR, subtype="FLOAT")
    return path


def test_a_center_only_mix_is_not_read_as_silence(center_only_5_1):
    fp = MasteringFingerprint.from_audio_file(str(center_only_5_1), sr=SR)

    assert fp is not None
    assert fp.loudness_dbfs > -30.0  # the first two channels are silent; the BS.775 fold carries the Center
