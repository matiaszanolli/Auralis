# Fingerprint Service Integration Guide

## Overview

A unified `FingerprintService` has been created to consolidate all fingerprinting logic used across the codebase. This eliminates duplication and provides a single interface for fingerprint retrieval with intelligent 3-tier caching.

**Current Status:**
- ✅ `FingerprintService` created: `auralis/analysis/fingerprint/fingerprint_service.py`
- ✅ `auto_master.py` refactored to use `FingerprintService`
- ⏳ **Pending:** Integration into player code

## The Problem

Three separate implementations currently handle fingerprinting:

1. **`AudioFingerprintAnalyzer`** - Core analysis (Python + PyO3)
2. **`FingerprintGenerator`** - Backend wrapper (pyrpc fingerprinting)
3. **`MasteringTargetService`** - Database loading wrapper

**Duplication identified:**
```python
# Same database lookup logic exists in multiple places:
# - FingerprintGenerator.get_or_generate()
# - MasteringTargetService.load_fingerprint_from_database()
# - ChunkedAudioProcessor._load_fingerprint()
```

**Result:** Inconsistent fingerprinting, maintenance burden, code duplication.

## The Solution: FingerprintService

### Single Interface
```python
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

service = FingerprintService()
fingerprint = service.get_or_compute(audio_path)  # Dict with 25D features
```

### 3-Tier Caching Strategy
```
get_or_compute(audio_path)
    ↓
1. Database (SQLite) - < 1ms
    ↓
2. .25d file cache - fast
    ↓
3. On-demand PyO3 computation - 500-2000ms
```

### Key Features
- **Automatic type conversion**: NumPy float32/float64 → Python float
- **JSON serialization**: All numpy types safely converted
- **Database caching**: Fingerprints stored in SQLite for persistent reuse
- **File caching**: Fallback to .25d JSON files if database unavailable
- **Computation on-demand**: Fresh fingerprints computed with PyO3 when needed

## Integration Steps

### Step 1: Update Backend Routes

**File:** `auralis-web/backend/routers/enhancement.py`

Replace duplicate logic with unified service:

```python
# BEFORE (current)
from auralis.library.models import Track
targets = mastering_target_service.get_targets_for_track(track_id)

# AFTER (with FingerprintService)
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

service = FingerprintService()
track = Track.query.get(track_id)
fingerprint = service.get_or_compute(Path(track.filepath))
```

**Changes needed:**
- `routers/enhancement.py` - Replace mastering_target_service calls
- `routers/system.py` - Use FingerprintService in play_enhanced handler
- Remove `mastering_target_service.py` entirely

### Step 2: Update Player Code

**File:** `auralis/player/enhanced_audio_player.py`

Add fingerprinting to `EnhancedAudioPlayer`:

```python
class EnhancedAudioPlayer:
    def __init__(self, ...):
        # ... existing init ...
        from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
        self.fingerprint_service = FingerprintService()

    def load_track_from_library(self, track):
        """Load track with fingerprinting for adaptive mastering."""
        audio, sr = self._load_audio(track.filepath)

        # Get fingerprint for content-aware processing
        fingerprint = self.fingerprint_service.get_or_compute(Path(track.filepath))

        # Pass fingerprint to processor
        self.realtime_processor.set_fingerprint(fingerprint)

        return audio, sr
```

### Step 3: Make AutoMasterProcessor Fingerprint-Aware

**File:** `auralis/player/realtime/auto_master.py`

Replace static profile gains with fingerprint-adaptive parameters:

```python
# BEFORE (current - static gains)
class AutoMasterProcessor:
    PROFILES = {
        'adaptive': {'eq_gain': 0.5, 'compression': 2.0},
        'gentle': {'eq_gain': 0.2, 'compression': 1.5},
        # ... hardcoded per profile
    }

# AFTER (fingerprint-aware)
class AutoMasterProcessor:
    def __init__(self):
        self.fingerprint = None
        self.adaptive_params = None

    def set_fingerprint(self, fingerprint: Dict):
        """Set fingerprint for adaptive parameter generation."""
        self.fingerprint = fingerprint
        self.adaptive_params = self._generate_adaptive_parameters(fingerprint)

    def _generate_adaptive_parameters(self, fingerprint: Dict) -> Dict:
        """Generate parameters from fingerprint (same logic as auto_master.py)."""
        from auralis.dsp.utils.adaptive_loudness import AdaptiveLoudnessControl

        lufs = fingerprint.get('lufs', -14.0)
        crest_db = fingerprint.get('crest_db', 12.0)
        bass_pct = fingerprint.get('bass_pct', 0.15)

        makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs=lufs,
            intensity=1.0,
            crest_factor_db=crest_db,
            bass_pct=bass_pct
        )

        return {
            'makeup_gain': makeup_gain,
            'compression_ratio': self._compute_compression_ratio(crest_db),
            'target_peak': self._compute_target_peak(lufs)
        }

    def process_chunk(self, audio: np.ndarray) -> np.ndarray:
        """Process chunk with adaptive parameters."""
        if self.adaptive_params is None:
            # Fallback to profile-based if no fingerprint
            return self._apply_profile(audio)

        # Apply fingerprint-aware adaptive processing
        return self._apply_adaptive(audio, self.adaptive_params)
```

### Step 4: Update RealtimeProcessor

**File:** `auralis/player/realtime/processor.py`

Pass fingerprints through the processing pipeline:

```python
class RealtimeProcessor:
    def set_fingerprint(self, fingerprint: Dict):
        """Set fingerprint for content-aware processing."""
        self.auto_master.set_fingerprint(fingerprint)

    def process_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """Process chunk with fingerprint-aware mastering."""
        # Already uses auto_master which now has fingerprint
        return self.auto_master.process(chunk)
```

### Step 5: Update Frontend

**File:** `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts`

The frontend already observes fingerprint progress via WebSocket. Ensure it's integrated:

```typescript
// Already implemented (line 424 in usePlayEnhanced.ts):
const handleFingerprintProgress = (status: string) => {
  setFingerprintStatus(status);  // 'analyzing' → 'complete'
};

// The UI already shows fingerprinting status during enhanced playback
```

## Migration Path

### Phase 1: Complete ✅
- Create `FingerprintService` consolidating all logic
- Update `auto_master.py` to use it
- Both have 3-tier caching (database → .25d file → compute)

### Phase 2: Backend Integration (Next)
1. Update `routers/system.py` to use `FingerprintService` for `play_enhanced`
2. Update `routers/enhancement.py` to use `FingerprintService`
3. Remove `mastering_target_service.py` (move logic to FingerprintService)
4. Remove `fingerprint_generator.py` wrapper (redundant now)

### Phase 3: Player Integration (Next)
1. Add fingerprinting to `EnhancedAudioPlayer.load_track_from_library()`
2. Make `AutoMasterProcessor` fingerprint-aware
3. Pass fingerprints through `RealtimeProcessor`
4. Test realtime playback with adaptive mastering

### Phase 4: Testing & Optimization
1. Benchmark fingerprinting performance with 3-tier caching
2. Verify realtime playback smoothness
3. A/B test adaptive vs. static profiles
4. Performance profiling of player memory/CPU usage

## Usage Examples

### In Player Code
```python
# Load track with adaptive mastering
player = EnhancedAudioPlayer()
player.load_track_from_library(track)  # Fingerprint loaded automatically
player.play()  # Uses fingerprint-aware adaptive mastering
```

### In Backend Routes
```python
# Get adaptive parameters for API response
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from pathlib import Path

service = FingerprintService()
fingerprint = service.get_or_compute(Path(track.filepath))

# Fingerprint is now available for parameter generation
# Same logic as auto_master.py
```

### In Scripts
```python
# Same pattern as auto_master.py
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

service = FingerprintService()
fingerprint = service.get_or_compute(Path("track.flac"))

# 3-tier cache automatically used:
# 1. Database lookup (if in library)
# 2. .25d file cache
# 3. On-demand PyO3 computation
```

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Fingerprinting Interfaces** | 3 separate implementations | 1 unified service |
| **Player Fingerprinting** | None (static profiles) | Automatic (adaptive) |
| **Duplication** | ~300 lines across 3 files | Single source of truth |
| **Cache Consistency** | Inconsistent across services | Guaranteed 3-tier consistency |
| **Maintenance** | Hard to update logic | Single point of update |
| **Performance** | Repeated computations | 3-tier caching prevents waste |

## Files Modified

- ✅ Created: `auralis/analysis/fingerprint/fingerprint_service.py` (unified service)
- ✅ Updated: `auto_master.py` (now uses FingerprintService)
- ⏳ To update: `auralis/player/enhanced_audio_player.py`
- ⏳ To update: `auralis/player/realtime/auto_master.py`
- ⏳ To update: `auralis/player/realtime/processor.py`
- ⏳ To remove: `auralis-web/backend/fingerprint_generator.py` (redundant)
- ⏳ To remove: `auralis-web/backend/core/mastering_target_service.py` (redundant)
- ⏳ To update: `auralis-web/backend/routers/system.py`
- ⏳ To update: `auralis-web/backend/routers/enhancement.py`

## Testing

```bash
# Test unified service
python -c "
from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from pathlib import Path

service = FingerprintService()
fp = service.get_or_compute(Path('/path/to/track.flac'))
print(f'Fingerprint: {len(fp)} dimensions')
"

# Test auto_master.py with new service
python auto_master.py /path/to/track.flac -o /tmp/test.wav

# Verify caching (should be instant second run)
python auto_master.py /path/to/track.flac -o /tmp/test2.wav
```

## Questions?

Refer to:
- `auto_master.py` - Example of integrated fingerprinting + adaptive mastering
- `AudioFingerprintAnalyzer` - Core analysis logic (now wrapped by service)
- `FingerprintStorage` - File-level caching (.25d files)
- `AdaptiveLoudnessControl` - Adaptive parameter generation logic
