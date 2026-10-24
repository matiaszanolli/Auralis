"""
MFCC / Chroma / Tonnetz / Mel Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The librosa-based spectral-description half of FeatureExtractor (#6273);
each function takes the extractor (sample_rate, n_mfcc…) as first argument.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None


def _extract_mfcc(extractor, self, audio: np.ndarray) -> list[float]:
    """Extract MFCC features (simplified)"""
    spectrum = np.fft.fft(audio[:4096])
    magnitude = np.abs(spectrum[:2049])

    mel_filters = extractor._mel_filterbank

    mel_energies = []
    for filt in mel_filters:
        energy = np.sum(magnitude * filt)
        mel_energies.append(max(energy, 1e-10))

    log_energies = np.log(mel_energies)

    mfcc = []
    for i in range(extractor.n_mfcc):
        component = 0.0
        for j, log_energy in enumerate(log_energies):
            component += log_energy * np.cos(np.pi * i * (j + 0.5) / len(log_energies))
        mfcc.append(float(component))

    return mfcc

def _extract_chroma(extractor, self, audio: np.ndarray) -> list[float]:
    """Extract chroma features"""
    spectrum = np.fft.fft(audio[:4096])
    magnitude = np.abs(spectrum[:2049])
    freqs = np.fft.fftfreq(4096, 1/extractor.sample_rate)[:2049]

    chroma = np.zeros(12)

    for i, freq in enumerate(freqs):
        if freq > 80:
            midi_note = 12 * np.log2(freq / 440.0) + 69
            chroma_bin = int(midi_note) % 12
            chroma[chroma_bin] += magnitude[i]

    total_energy = np.sum(chroma)
    if total_energy > 0:
        chroma = chroma / total_energy

    return chroma.tolist()

def _extract_tonnetz(extractor, self, audio: np.ndarray) -> list[float]:
    """Extract tonnetz features"""
    chroma = np.array(extractor._extract_chroma(audio))
    tonnetz = np.zeros(6)

    tonnetz[0] = np.sum(chroma * np.cos(np.arange(12) * 7 * np.pi / 6))
    tonnetz[1] = np.sum(chroma * np.sin(np.arange(12) * 7 * np.pi / 6))
    tonnetz[2] = np.sum(chroma * np.cos(np.arange(12) * 3 * np.pi / 2))
    tonnetz[3] = np.sum(chroma * np.sin(np.arange(12) * 3 * np.pi / 2))
    tonnetz[4] = np.sum(chroma * np.cos(np.arange(12) * 2 * np.pi / 3))
    tonnetz[5] = np.sum(chroma * np.sin(np.arange(12) * 2 * np.pi / 3))

    return tonnetz.tolist()
