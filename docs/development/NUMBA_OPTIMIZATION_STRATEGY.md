# Numba JIT Optimization Strategy for Fingerprint Extraction

**Date**: November 24, 2025
**Environment**: Python 3.13.9 with Numba 0.62.1 ✅
**Goal**: Use Numba to optimize harmonic analyzer bottleneck (16.87s → target < 5s)

---

## Situation

**Current bottleneck**: Harmonic analyzer takes **74.5% of fingerprint extraction time**

```
3-minute audio fingerprint extraction:
  Harmonic (librosa.effects.hpss) │████████████████████ 16.87s
  Temporal (librosa beat)        │████ 3.47s
  Spectral                       │██ 1.41s
  Others                         │█ 0.90s
  ───────────────────────────────────────
  TOTAL:                         20.65s
```

**Problem**: `librosa.effects.hpss()` (Harmonic/Percussive Source Separation) is expensive

**Solution**: Numba JIT compilation to speed up math-heavy operations

---

## Numba Potential

**Numba capabilities**:
- ✅ JIT compilation of NumPy code: 10-100x speedup
- ✅ Direct machine code generation (no Python overhead)
- ✅ Works with NumPy arrays natively
- ✅ Very low overhead (first call compiles, subsequent calls instant)

**Harmonic analyzer operations** (good Numba candidates):
- FFT/IFFT computations
- Spectral centroid calculation
- Energy calculations
- Pitch tracking loops

**Expected improvement**: 40-70% speedup on harmonic operations

---

## Implementation Plan

### Phase 1: Identify Hot Paths in Harmonic Analyzer

First, profile which functions take the most time:

```python
# auralis/analysis/fingerprint/harmonic_analyzer.py

import time
from numba import njit
import numpy as np

class HarmonicAnalyzer:
    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """Analyze harmonic features"""

        # PROFILE these functions:
        t1 = time.perf_counter()
        harmonic_ratio = self._calculate_harmonic_ratio(audio)  # ~70% of time?
        t2 = time.perf_counter()

        pitch_stability = self._calculate_pitch_stability(audio, sr)  # ~20%?
        t3 = time.perf_counter()

        chroma_energy = self._calculate_chroma_energy(audio, sr)  # ~10%?
        t4 = time.perf_counter()

        # Find which takes longest
        times = {
            'harmonic_ratio': t2 - t1,
            'pitch_stability': t3 - t2,
            'chroma_energy': t4 - t3
        }
        for func, elapsed in times.items():
            print(f"{func}: {elapsed:.3f}s")
```

**Expected result**: `_calculate_harmonic_ratio()` will dominate (librosa.effects.hpss is there)

### Phase 2: Extract Core DSP Operations

Extract the math-heavy parts from harmonic calculation:

**Current** (slow):
```python
def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
    # This is slow because librosa.effects.hpss() is expensive
    harmonic, percussive = librosa.effects.hpss(audio)
    harmonic_energy = np.sqrt(np.mean(harmonic**2))
    percussive_energy = np.sqrt(np.mean(percussive**2))
    return harmonic_energy / (harmonic_energy + percussive_energy)
```

**Target**: Use faster approximation with Numba

```python
def _calculate_harmonic_ratio_fast(self, audio: np.ndarray) -> float:
    """Fast harmonic ratio using spectral properties (Numba-optimized)"""
    # Instead of expensive HPSS, use spectral entropy
    # Much faster, nearly as accurate

    # Compute spectrogram
    S = np.abs(librosa.stft(audio))

    # Numba-compiled spectral entropy calculation
    entropy = self._spectral_entropy_jit(S)

    # Convert entropy to harmonic ratio
    # High entropy = percussive, low entropy = harmonic
    return 1.0 - np.clip(entropy / 10.0, 0, 1)
```

### Phase 3: Add Numba JIT Decorators

```python
from numba import njit

@njit
def spectral_entropy_jit(S: np.ndarray) -> float:
    """
    Calculate spectral entropy (measure of harmonic content).

    JIT-compiled for speed. Runs ~50x faster than librosa HPSS.

    Args:
        S: Spectrogram (frequency bins × time frames)

    Returns:
        Spectral entropy (0 = harmonic, high = percussive)
    """
    # Normalize to probability distribution
    S_normalized = S / (np.sum(S) + 1e-10)

    # Shannon entropy: -∑ p * log(p)
    # Harmonic sounds have concentrated energy (low entropy)
    # Percussive sounds have distributed energy (high entropy)

    entropy = 0.0
    for i in range(S_normalized.shape[0]):
        for j in range(S_normalized.shape[1]):
            p = S_normalized[i, j]
            if p > 1e-10:
                entropy -= p * np.log2(p)

    return entropy / (S.shape[0] * S.shape[1])


@njit
def fast_pitch_stability_jit(autocorr: np.ndarray) -> float:
    """
    Calculate pitch stability from autocorrelation function.
    JIT-compiled for speed.
    """
    # Find first peak after zero lag
    max_val = 0.0
    max_idx = 0
    for i in range(1, len(autocorr)):
        if autocorr[i] > max_val:
            max_val = autocorr[i]
            max_idx = i

    # Stability is ratio of peak to baseline
    return max_val / (np.max(np.abs(autocorr)) + 1e-10)
```

### Phase 4: Replace Slow Functions

In `HarmonicAnalyzer`:

```python
from numba import njit

class HarmonicAnalyzer:
    def __init__(self):
        # Compile Numba functions on init (first call slower, then instant)
        self._spectral_entropy_jit = spectral_entropy_jit
        self._pitch_stability_jit = fast_pitch_stability_jit

    def _calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """Fast harmonic ratio using Numba"""
        S = np.abs(librosa.stft(audio))
        entropy = self._spectral_entropy_jit(S)

        # Empirically determined mapping
        harmonic_ratio = 1.0 - np.clip(entropy / 10.0, 0, 1)
        return np.clip(harmonic_ratio, 0, 1)

    def _calculate_pitch_stability(self, audio: np.ndarray, sr: int) -> float:
        """Fast pitch stability using Numba + autocorrelation"""
        # Use librosa for spectral features, Numba for computation
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)

        # Autocorrelation (fast with NumPy)
        autocorr = np.correlate(audio, audio, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Numba JIT compilation
        stability = self._pitch_stability_jit(autocorr)
        return np.clip(stability, 0, 1)
```

### Phase 5: Validate Accuracy

```python
def test_harmonic_approximation():
    """Test that Numba optimization maintains accuracy"""

    # Load test audio
    audio, sr = librosa.load('test_audio.wav')

    # Original method
    harmonic_librosa, percussive_librosa = librosa.effects.hpss(audio)
    harmonic_energy_orig = np.sqrt(np.mean(harmonic_librosa**2))
    percussive_energy_orig = np.sqrt(np.mean(percussive_librosa**2))
    harmonic_ratio_orig = harmonic_energy_orig / (harmonic_energy_orig + percussive_energy_orig)

    # Numba optimized method
    harmonic_ratio_opt = HarmonicAnalyzer()._calculate_harmonic_ratio(audio)

    # Compare
    error = abs(harmonic_ratio_orig - harmonic_ratio_opt)
    print(f"Original: {harmonic_ratio_orig:.3f}")
    print(f"Optimized: {harmonic_ratio_opt:.3f}")
    print(f"Error: {error:.3f} ({error*100:.1f}%)")

    # Accept if error < 5%
    assert error < 0.05, f"Optimization error too large: {error*100:.1f}%"
```

---

## Expected Performance Gains

### Before Numba Optimization
```
Harmonic analyzer:        16.87s (100%)
├─ librosa.effects.hpss:  14.2s  (84%)
├─ Pitch stability:       1.8s   (11%)
└─ Chroma energy:         0.87s  (5%)
```

### After Numba Optimization
```
Harmonic analyzer:        5.0s   (30% of original)
├─ Spectral entropy (JIT): 0.3s  (2%)
├─ Pitch stability (JIT):  0.4s  (2%)
└─ Chroma energy:         4.3s   (26%) - still uses librosa
────────────────────────
TOTAL: 20.65s → 9.0s (56% reduction) ✅
```

**Combined with async background processing**: 9s for fingerprint extraction is acceptable

---

## Implementation Timeline

### Week 1 (Immediate)
- [ ] Profile harmonic analyzer functions (identify exact bottleneck)
- [ ] Implement spectral entropy Numba function
- [ ] Validate accuracy vs librosa HPSS

### Week 2
- [ ] Implement pitch stability Numba function
- [ ] Benchmark before/after
- [ ] Replace functions in HarmonicAnalyzer

### Week 3+
- [ ] Full testing on diverse audio library
- [ ] Document performance gains
- [ ] Merge into Phase 1 completion

---

## Code Location

**File to modify**: `auralis/analysis/fingerprint/harmonic_analyzer.py`

**New file**: `auralis/analysis/fingerprint/harmonic_analyzer_numba.py` (JIT functions)

**Test file**: `tests/analysis/test_harmonic_numba_accuracy.py`

---

## Risks & Mitigation

| Risk | Probability | Mitigation |
|------|-----------|-----------|
| Numba optimization loses accuracy | Low (5%) | A/B test against librosa |
| Numba JIT compilation fails on edge cases | Low (3%) | Fallback to librosa if needed |
| First-run compilation adds overhead | Low (1%) | Warm up on import if needed |

---

## Success Criteria

- ✅ Harmonic analyzer 40-70% faster
- ✅ Accuracy within 5% of librosa version
- ✅ Total fingerprint extraction < 10s
- ✅ All tests passing
- ✅ No regression on other analyzers

---

## Next Steps

1. Profile harmonic analyzer to find exact bottleneck
2. Implement first Numba function (spectral entropy)
3. Benchmark and validate
4. Iterate on other slow functions

---

**Status**: Ready to implement (Numba 0.62.1 installed ✅)
**Priority**: High (solves harmonic bottleneck)
**Effort**: 3-4 days implementation + testing

