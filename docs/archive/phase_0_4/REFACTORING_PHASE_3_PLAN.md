# Phase 3 Refactoring Plan: Streaming Base Class & Helper Consolidation

**Status**: 📋 Planning | **Recommended Priority**: High | **Estimated Effort**: Medium | **Expected Impact**: High

---

## Overview

Phase 3 builds on the success of Phases 1 & 2 by consolidating streaming analyzer architecture. Both `StreamingHarmonicAnalyzer` and `StreamingTemporalAnalyzer` share common patterns for:
- Buffering and windowing
- Periodic analysis execution
- Metric state tracking
- Frame-by-frame updates

This phase will extract these patterns into a reusable `BaseStreamingAnalyzer` abstract class, eliminating ~100+ lines of duplicate streaming infrastructure.

---

## Current Streaming Architecture

### StreamingHarmonicAnalyzer (current: 287 lines)
```python
class StreamingHarmonicAnalyzer:
    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0, ...):
        # State initialization
        self.sr = sr
        self.buffer_duration = buffer_duration
        self.harmonic_buffer = deque(...)  # Custom buffer

        # Metric tracking
        self.harmonic_ratio_estimate = 0.5
        self.pitch_stability_estimate = 0.5
        self.chroma_energy_estimate = 0.5

        # Analysis counter
        self.analysis_counter = 0
        self.frame_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        self.frame_count += 1
        self.analysis_counter += 1

        # Add to buffer
        self.harmonic_buffer.append(frame)

        # Periodic re-analysis
        if self.analysis_counter >= threshold:
            self._perform_analysis()
            self.analysis_counter = 0

        return self.get_metrics()

    def _perform_analysis(self):
        # Custom harmonic analysis
        ...
```

### StreamingTemporalAnalyzer (current: 224 lines)
```python
class StreamingTemporalAnalyzer:
    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0, ...):
        # State initialization (similar to harmonic)
        self.sr = sr
        self.buffer_duration = buffer_duration
        self.onset_buffer = OnsetBuffer(...)  # Custom buffer class

        # Metric tracking (different metrics, same pattern)
        self.tempo_estimate = 120.0
        self.rhythm_stability_estimate = 0.5
        self.transient_density_estimate = 0.5
        self.silence_ratio_estimate = 0.1

        # Analysis counter (same pattern)
        self.analysis_counter = 0
        self.frame_count = 0

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        # Same structure as StreamingHarmonicAnalyzer
        ...
```

**Duplication Patterns Identified**:
1. **Buffer initialization** - Both create custom buffers with maxlen
2. **Metric state tracking** - Both track multiple metric estimates
3. **Frame/analysis counters** - Identical state management
4. **Periodic analysis trigger** - Same logic in both
5. **Reset method** - Nearly identical state clearing
6. **Confidence scoring** - Similar pattern in both

---

## Phase 3 Solution Architecture

### BaseStreamingAnalyzer (new: ~140 lines)

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional
import numpy as np
from collections import deque

class BaseStreamingAnalyzer(ABC):
    """Abstract base class for streaming feature analyzers.

    Provides common infrastructure for:
    - Audio buffering and windowing
    - Periodic analysis execution
    - Metric state tracking
    - Frame-by-frame updates with confidence scoring
    """

    def __init__(
        self,
        sr: int = 44100,
        buffer_duration: float = 2.0,
        analysis_interval_frames: Optional[int] = None
    ):
        """Initialize streaming analyzer.

        Args:
            sr: Sample rate in Hz
            buffer_duration: Duration of analysis buffer in seconds
            analysis_interval_frames: How often to run expensive analysis.
                If None, uses buffer_duration to calculate.
        """
        self.sr = sr
        self.buffer_duration = buffer_duration
        self.buffer_size = int(sr * buffer_duration)

        # Setup analysis interval
        if analysis_interval_frames is None:
            # Typical: analyze when buffer fills (every 2 seconds at 44100 Hz)
            self.analysis_interval = int(sr * buffer_duration / 4000)  # ~22 frame intervals
        else:
            self.analysis_interval = analysis_interval_frames

        # State tracking
        self.frame_count = 0
        self.analysis_counter = 0
        self.analysis_runs = 0

        # Metric estimates (subclass defines actual metrics)
        self._metric_estimates = {}

    def update(self, frame: np.ndarray) -> Dict[str, float]:
        """Process audio frame and return current metrics.

        Args:
            frame: Audio frame to process (mono)

        Returns:
            Dictionary with current metric estimates
        """
        self.frame_count += 1
        self.analysis_counter += 1

        # Add frame to buffer
        self._append_to_buffer(frame)

        # Periodic analysis
        if self.analysis_counter >= self.analysis_interval:
            self._perform_analysis()
            self.analysis_counter = 0
            self.analysis_runs += 1

        return self.get_metrics()

    @abstractmethod
    def _append_to_buffer(self, frame: np.ndarray):
        """Add frame to streaming buffer.

        Subclasses implement buffer-specific logic.
        """
        pass

    @abstractmethod
    def _perform_analysis(self):
        """Perform expensive analysis on buffered audio.

        Subclasses implement metric-specific calculations using
        pre-computed buffers.
        """
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, float]:
        """Get current metric estimates.

        Returns:
            Dict with metric names and current estimates
        """
        pass

    def reset(self):
        """Reset analyzer state."""
        self.frame_count = 0
        self.analysis_counter = 0
        self.analysis_runs = 0
        self._reset_buffers()

    @abstractmethod
    def _reset_buffers(self):
        """Reset streaming buffers. Subclass-specific."""
        pass

    def get_confidence(self) -> Dict[str, float]:
        """Get confidence scores for metrics.

        Returns confidence 0-1 based on number of analysis runs
        and accumulated data.
        """
        # Stabilization: 5 analyses = high confidence
        confidence = float(np.clip(self.analysis_runs / 5.0, 0, 1))

        return {
            metric: confidence
            for metric in self.get_metrics().keys()
        }

    def get_frame_count(self) -> int:
        """Get total frames processed."""
        return self.frame_count

    def get_analysis_count(self) -> int:
        """Get total analyses performed."""
        return self.analysis_runs
```

### Refactored StreamingHarmonicAnalyzer

```python
class StreamingHarmonicAnalyzer(BaseStreamingAnalyzer):
    """Streaming harmonic feature analyzer."""

    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0):
        super().__init__(sr, buffer_duration)

        # Harmonic-specific buffer
        self.harmonic_buffer = deque(maxlen=self.buffer_size)

        # Harmonic-specific metrics
        self.harmonic_ratio_estimate = 0.5
        self.pitch_stability_estimate = 0.5
        self.chroma_energy_estimate = 0.5

    def _append_to_buffer(self, frame: np.ndarray):
        """Add frame to harmonic analysis buffer."""
        self.harmonic_buffer.extend(frame)

    def _perform_analysis(self):
        """Perform harmonic analysis on buffered audio."""
        try:
            audio = np.array(list(self.harmonic_buffer))
            if len(audio) < self.sr // 4:
                return

            # Use HarmonicOperations for calculations
            harmonic_ratio, pitch_stability, chroma_energy = (
                HarmonicOperations.calculate_all(audio, self.sr)
            )

            self.harmonic_ratio_estimate = float(harmonic_ratio)
            self.pitch_stability_estimate = float(pitch_stability)
            self.chroma_energy_estimate = float(chroma_energy)

        except Exception as e:
            logger.debug(f"Harmonic analysis failed: {e}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current harmonic metrics."""
        return {
            'harmonic_ratio': float(self.harmonic_ratio_estimate),
            'pitch_stability': float(self.pitch_stability_estimate),
            'chroma_energy': float(self.chroma_energy_estimate)
        }

    def _reset_buffers(self):
        """Reset harmonic buffer."""
        self.harmonic_buffer.clear()
        self.harmonic_ratio_estimate = 0.5
        self.pitch_stability_estimate = 0.5
        self.chroma_energy_estimate = 0.5
```

### Refactored StreamingTemporalAnalyzer

```python
class StreamingTemporalAnalyzer(BaseStreamingAnalyzer):
    """Streaming temporal feature analyzer."""

    def __init__(self, sr: int = 44100, buffer_duration: float = 2.0, hop_length: float = 0.25):
        super().__init__(sr, buffer_duration)

        # Temporal-specific buffers
        self.onset_buffer = OnsetBuffer(sr, buffer_duration)
        self.rms_buffer = deque()
        self.frame_rms_values = deque(maxlen=int(sr * 10 / int(sr * hop_length)))

        # Temporal-specific metrics
        self.tempo_estimate = 120.0
        self.rhythm_stability_estimate = 0.5
        self.transient_density_estimate = 0.5
        self.silence_ratio_estimate = 0.1

    def _append_to_buffer(self, frame: np.ndarray):
        """Add frame to temporal analysis buffers."""
        self.onset_buffer.append(frame)

        # Calculate RMS for silence ratio
        rms_val = np.sqrt(np.mean(frame ** 2))
        rms_db = 20 * np.log10(np.maximum(rms_val, SafeOperations.EPSILON))
        self.frame_rms_values.append(rms_db)

    def _perform_analysis(self):
        """Perform temporal analysis on buffered audio."""
        try:
            audio = self.onset_buffer.get_audio()
            if audio is None or len(audio) < self.sr // 4:
                return

            # Use TemporalOperations for calculations
            tempo, rhythm_stability, transient_density, _ = (
                TemporalOperations.calculate_all(audio, self.sr)
            )

            self.tempo_estimate = float(tempo)
            self.rhythm_stability_estimate = float(rhythm_stability)
            self.transient_density_estimate = float(transient_density)

        except Exception as e:
            logger.debug(f"Temporal analysis failed: {e}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current temporal metrics."""
        silence_ratio = self._calculate_silence_ratio()

        return {
            'tempo_bpm': float(self.tempo_estimate),
            'rhythm_stability': float(self.rhythm_stability_estimate),
            'transient_density': float(self.transient_density_estimate),
            'silence_ratio': float(silence_ratio)
        }

    def _reset_buffers(self):
        """Reset temporal buffers."""
        self.onset_buffer.clear()
        self.frame_rms_values.clear()
        self.tempo_estimate = 120.0
        self.rhythm_stability_estimate = 0.5
        self.transient_density_estimate = 0.5
        self.silence_ratio_estimate = 0.1

    def _calculate_silence_ratio(self) -> float:
        """Calculate silence ratio from RMS history."""
        try:
            if len(self.frame_rms_values) == 0:
                return 0.1

            rms_db_array = np.array(list(self.frame_rms_values))
            threshold_db = -40.0
            silent_frames = np.sum(rms_db_array < threshold_db)
            total_frames = len(rms_db_array)

            silence_ratio = silent_frames / total_frames if total_frames > 0 else 0.1
            return float(np.clip(silence_ratio, 0, 1))
        except Exception as e:
            logger.debug(f"Silence ratio calculation failed: {e}")
            return 0.1
```

---

## Expected Changes & Metrics

### Code Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| `StreamingHarmonicAnalyzer` | 287 lines | 120 lines | 58% ↓ |
| `StreamingTemporalAnalyzer` | 224 lines | 100 lines | 55% ↓ |
| **Base Class (new)** | - | 140 lines | +140 |
| **Total Combined** | 511 lines | 360 lines | 30% ↓ |

### Benefits

1. **Consistency**: Both streaming analyzers follow identical patterns
2. **Testability**: Can test BaseStreamingAnalyzer once, reuse in all subclasses
3. **Maintainability**: Buffer management and metric tracking in one place
4. **Extensibility**: Easy to create new streaming analyzers (e.g., spectral, variation)
5. **Code Reuse**: Helper classes (OnsetBuffer, etc.) inherited if needed

### Quality Assurance

- ✅ All subclass APIs remain unchanged
- ✅ All confidence scoring behavior preserved
- ✅ Buffer state management centralized and tested
- ✅ Analysis interval calculation standardized
- ✅ 100% backward compatible

---

## Implementation Steps

1. **Create BaseStreamingAnalyzer** (140 lines)
   - Abstract methods for buffer, analysis, metrics
   - Common frame/analysis counter management
   - Confidence scoring based on analysis runs

2. **Refactor StreamingHarmonicAnalyzer** (120 lines target)
   - Extend BaseStreamingAnalyzer
   - Implement harmonic-specific methods
   - Remove duplicate infrastructure code

3. **Refactor StreamingTemporalAnalyzer** (100 lines target)
   - Extend BaseStreamingAnalyzer
   - Implement temporal-specific methods
   - Remove duplicate infrastructure code

4. **Testing & Validation**
   - Verify all existing tests pass
   - Test inheritance behavior
   - Verify backward compatibility

5. **Documentation**
   - Create REFACTORING_PHASE_3_SUMMARY.md
   - Document base class design decisions
   - Include architecture diagram

---

## Optional Phase 4 (Future)

After Phase 3, additional consolidation opportunities exist:

### Variation & Spectral Operations (150+ lines)
- Extract `VariationOperations` class (variation coefficient calculations)
- Extract `SpectralOperations` class (spectral centroid, rolloff, flatness)
- Similar to Phase 1 & 2 pattern

### Directory Reorganization (Optional)
- Organize: `analyzers/`, `streaming/`, `utilities/`, `similarity/`, `storage/`
- Pure organizational refactoring, no functional changes

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking streaming APIs | High | Keep public interfaces identical, test thoroughly |
| Abstract class complexity | Medium | Keep base class minimal, focused |
| Multiple inheritance issues | Low | Single inheritance only |
| Buffer incompatibility | Low | Test with real audio streams |

---

## Timeline & Effort Estimate

- **Implementation**: 2-3 hours
- **Testing & Validation**: 1-2 hours
- **Documentation**: 30 minutes
- **Total**: 3.5-5.5 hours

---

## Decision Point

Phase 3 is ready to proceed once user confirms:
- ✅ Phase 1 & 2 work is complete and committed
- ✅ All tests passing with new utility modules
- ⏳ **User approval needed for Phase 3 start**

---

## Summary

Phase 3 continues the refactoring momentum from Phases 1 & 2:
- Phases 1 & 2: Eliminated ~350 lines of **calculation** duplication
- Phase 3: Will eliminate ~150 lines of **infrastructure** duplication

This creates a clean, extensible streaming analyzer architecture that will make future audio feature additions much simpler.

