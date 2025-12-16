# Integration Plan: Fingerprinting + Mastering + Streaming Pipeline

**Status**: Planning Phase
**Priority**: Critical Path for Production Release
**Date**: 2025-12-16

---

## Overview

Integrate the complete audio mastering pipeline into the playback workflow:

```
User clicks Play
    ↓
[STEP 1] Fingerprint Lookup/Generation
    - Check database for cached fingerprint
    - If missing: Generate new fingerprint (gRPC server)
    - Store result in database
    ↓
[STEP 2] Adaptive Mastering Preparation
    - Load fingerprint data (LUFS, crest, spectral features)
    - Initialize AdaptiveMode with fingerprint context
    - Load 2D LWRP thresholds (-12.0 LUFS, 13.0 crest)
    ↓
[STEP 3] Chunk Processing with Mastering
    - Load audio chunk
    - Apply AdaptiveMode.process() with 2D LWRP logic
    - Cache processed chunk
    ↓
[STEP 4] WebSocket Streaming
    - Send PCM samples via WebSocket
    - Frontend plays via HTML5 Audio API
    ↓
User hears enhanced audio with 2D LWRP applied
```

---

## Current State Analysis

### What Exists ✅

1. **Chunked Processor** (`chunked_processor.py`)
   - Loads audio in 15-second chunks
   - Already loads fingerprints from `.25d` files
   - Has chunk caching infrastructure
   - Applies basic DSP processing

2. **Audio Stream Controller** (`audio_stream_controller.py`)
   - WebSocket streaming with SimpleChunkCache
   - Processes chunks on-demand
   - Handles client connections

3. **Adaptive Mode** (`auralis/core/processing/adaptive_mode.py`)
   - ✅ 2D LWRP integrated (Phase 6.1)
   - Spectrum-based processing
   - Dynamic range expansion
   - Full normalization pipeline

4. **Fingerprinting Infrastructure**
   - gRPC fingerprint server running
   - FingerprintRepository for database access
   - FingerprintStorage for `.25d` file I/O

### What's Missing ❌

1. **Database Fingerprint Lookup**
   - ChunkedProcessor tries to load `.25d` but doesn't check database
   - No fallback to DB if `.25d` missing
   - FingerprintRepository not integrated into playback flow

2. **Fingerprint-to-Mastering Bridge**
   - Fingerprint data not passed to AdaptiveMode
   - No connection between 25D fingerprint and processing parameters
   - Content analysis not using cached fingerprint results

3. **Mastering Engine Initialization**
   - AdaptiveMode needs fingerprint context for content-aware decisions
   - No setup of preset profiles based on fingerprint
   - No integration with 2D LWRP in playback pipeline

4. **Error Handling**
   - No graceful fallback if fingerprint unavailable
   - No retry logic for gRPC fingerprint server
   - No user feedback on processing delays

---

## Implementation Tasks

### Task 1: Fingerprint Lookup Integration
**File**: `auralis-web/backend/chunked_processor.py`
**Goal**: Check DB before computing new fingerprint

```python
# In ChunkedAudioProcessor.__init__():

# NEW: Try to get fingerprint from database first
from auralis.library.repositories.factory import RepositoryFactory

def _load_fingerprint(self):
    """Load fingerprint from database or .25d file"""

    # 1. Try database (fastest - cached result)
    try:
        repo_factory = RepositoryFactory()
        fingerprint_repo = repo_factory.create_fingerprint_repository()
        fp_data = fingerprint_repo.get_by_track_id(self.track_id)

        if fp_data:
            self.fingerprint = MasteringFingerprint.from_dict(fp_data)
            logger.info(f"✅ Loaded fingerprint from DB (track {self.track_id})")
            return
    except Exception as e:
        logger.warning(f"DB lookup failed: {e}, trying .25d file")

    # 2. Try .25d file (cached on disk)
    try:
        from auralis.analysis.fingerprint import FingerprintStorage
        cached_data = FingerprintStorage.load(Path(self.filepath))
        if cached_data:
            self.fingerprint = cached_data
            logger.info(f"✅ Loaded fingerprint from .25d file")
            return
    except Exception as e:
        logger.warning(f".25d load failed: {e}")

    # 3. If no cached fingerprint, set flag for lazy generation
    logger.info(f"No cached fingerprint for track {self.track_id}, will compute on demand")
    self.fingerprint = None
```

### Task 2: Adaptive Mastering Engine Initialization
**File**: `auralis-web/backend/chunked_processor.py`
**Goal**: Initialize AdaptiveMode with fingerprint context before chunk processing

```python
# NEW: In __init__(), after fingerprint loading:

def _init_adaptive_mastering(self):
    """Initialize adaptive mastering with fingerprint context"""

    from auralis.core.unified_config import UnifiedConfig
    from auralis.core.processing.adaptive_mode import AdaptiveMode
    from auralis.analysis.content_analyzer import ContentAnalyzer
    from auralis.analysis.adaptive_target_generator import AdaptiveTargetGenerator
    from auralis.analysis.spectrum_mapper import SpectrumMapper

    # Initialize config
    config = UnifiedConfig(
        mastering_profile=self.preset,
        internal_sample_rate=self.sample_rate or 44100
    )

    # Initialize component modules
    content_analyzer = ContentAnalyzer(config)
    target_generator = AdaptiveTargetGenerator(config)
    spectrum_mapper = SpectrumMapper(config)

    # Create adaptive mode processor
    self.adaptive_mastering = AdaptiveMode(
        config=config,
        content_analyzer=content_analyzer,
        target_generator=target_generator,
        spectrum_mapper=spectrum_mapper
    )

    logger.info(f"✅ Adaptive mastering engine initialized (preset: {self.preset})")
```

### Task 3: Integrate Mastering into Chunk Processing
**File**: `auralis-web/backend/chunked_processor.py`
**Goal**: Apply adaptive mastering (with 2D LWRP) to each processed chunk

```python
# In ChunkedAudioProcessor.process_chunk():

def process_chunk(self, chunk_idx: int) -> Tuple[np.ndarray, int]:
    """Process audio chunk with adaptive mastering + 2D LWRP"""

    # Load raw audio chunk
    audio_chunk = self._load_chunk(chunk_idx)

    # Initialize EQ processor for psychoacoustic EQ
    from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ
    eq_processor = PsychoacousticEQ()

    # Apply adaptive mastering with 2D LWRP
    processed_audio = self.adaptive_mastering.process(
        audio_chunk,
        eq_processor=eq_processor
    )

    # Print 2D LWRP decisions for debug (already in adaptive_mode.py)
    # [2D LWRP] Compressed loud material (LUFS -8.2 dB, crest 8.5 dB)
    # [2D LWRP] → Applying expansion factor 0.45 to restore dynamics

    return processed_audio, self.sample_rate
```

### Task 4: WebSocket Integration with Fingerprinting
**File**: `auralis-web/backend/routers/system.py` (WebSocket endpoint)
**Goal**: Ensure fingerprint is available before streaming

```python
# In play_enhanced WebSocket handler:

async def play_enhanced(data: dict):
    """Stream enhanced audio with fingerprinting + mastering"""

    track_id = data['track_id']
    preset = data.get('preset', 'adaptive')
    intensity = data.get('intensity', 1.0)

    # Get track metadata
    lib_manager = get_library_manager()
    track = lib_manager.get_track(track_id)

    if not track:
        await websocket.send_json({
            'type': 'audio_stream_error',
            'error': 'Track not found'
        })
        return

    # Load or generate fingerprint
    fingerprint = await _ensure_fingerprint(track_id, track.filepath)

    if not fingerprint:
        # No fingerprint available - fall back to basic processing
        logger.warning(f"No fingerprint for track {track_id}, using basic mastering")

    # Create chunked processor with fingerprint context
    processor = ChunkedAudioProcessor(
        track_id=track_id,
        filepath=track.filepath,
        preset=preset,
        intensity=intensity
    )

    # Stream processed audio
    await stream_enhanced_audio(
        websocket=websocket,
        processor=processor,
        track_duration=track.duration
    )
```

### Task 5: Fingerprint Generation on Demand
**File**: New utility: `auralis-web/backend/fingerprint_generator.py`
**Goal**: Async fingerprint generation with gRPC server

```python
# NEW FILE: auralis-web/backend/fingerprint_generator.py

import asyncio
import requests
from auralis.analysis.mastering_fingerprint import MasteringFingerprint

class FingerprintGenerator:
    """Manages fingerprint generation via gRPC server"""

    GRPC_SERVER_URL = "http://localhost:50051"  # gRPC server endpoint
    TIMEOUT = 60  # seconds

    @staticmethod
    async def get_or_generate(track_id: int, filepath: str) -> Optional[MasteringFingerprint]:
        """
        Get fingerprint from DB, or generate if missing.

        Returns:
            MasteringFingerprint or None if generation fails
        """

        # 1. Check database
        repo = FingerprintRepository(session_factory)
        fp_data = repo.get_by_track_id(track_id)
        if fp_data:
            return MasteringFingerprint.from_dict(fp_data)

        # 2. Generate via gRPC
        try:
            fingerprint = await FingerprintGenerator._generate_via_grpc(filepath)

            # 3. Store in database
            if fingerprint:
                repo.create(
                    track_id=track_id,
                    fingerprint_data=fingerprint.to_dict()
                )
                logger.info(f"✅ Generated and cached fingerprint for track {track_id}")

            return fingerprint

        except Exception as e:
            logger.error(f"Fingerprint generation failed: {e}")
            return None

    @staticmethod
    async def _generate_via_grpc(filepath: str) -> Optional[MasteringFingerprint]:
        """Call gRPC fingerprint server"""

        try:
            # Call gRPC server (async over HTTP)
            response = requests.post(
                f"{FingerprintGenerator.GRPC_SERVER_URL}/fingerprint",
                json={"filepath": filepath},
                timeout=FingerprintGenerator.TIMEOUT
            )

            if response.status_code == 200:
                fp_dict = response.json()
                return MasteringFingerprint.from_dict(fp_dict)

        except requests.exceptions.Timeout:
            logger.error("Fingerprint server timeout")
        except Exception as e:
            logger.error(f"gRPC call failed: {e}")

        return None
```

---

## Integration Sequence

### Phase 1: Database Integration (Priority 1)
1. ✅ Fix FingerprintRepository initialization (add session_factory)
2. ✅ Add fingerprint lookup to ChunkedAudioProcessor.__init__()
3. ✅ Add fallback to .25d file if DB missing
4. Test: Verify fingerprints load from DB before processing

### Phase 2: Mastering Engine Integration (Priority 1)
1. Initialize AdaptiveMode in ChunkedAudioProcessor
2. Connect fingerprint data to content analysis
3. Apply adaptive processing to each chunk (calls adaptive_mode.process())
4. Debug: Verify 2D LWRP decisions are printed for each chunk

### Phase 3: Fingerprint Generation (Priority 2)
1. Create FingerprintGenerator utility
2. Add async fingerprint generation on-demand
3. Store generated fingerprints in database
4. Test: Verify generation works when fingerprint missing

### Phase 4: WebSocket Integration (Priority 2)
1. Update play_enhanced handler to use fingerprinting
2. Pass fingerprint context to ChunkedAudioProcessor
3. Ensure error handling if fingerprinting fails
4. Test: Stream audio from cold cache (no fingerprint)

### Phase 5: Frontend Integration (Priority 3)
1. Update usePlayEnhanced hook to show mastering status
2. Display "Preparing mastering..." during fingerprinting
3. Show 2D LWRP decisions in debug console
4. Test: End-to-end playback with mastering

---

## File Changes Summary

### Modified Files

| File | Changes | Priority |
|------|---------|----------|
| `auralis-web/backend/chunked_processor.py` | Add fingerprint loading + adaptive mastering init | P1 |
| `auralis-web/backend/audio_stream_controller.py` | Pass fingerprint to ChunkedAudioProcessor | P1 |
| `auralis-web/backend/routers/system.py` | Update play_enhanced WebSocket handler | P1 |
| `auralis/core/processing/adaptive_mode.py` | ✅ Already integrated 2D LWRP | Done |

### New Files

| File | Purpose | Priority |
|------|---------|----------|
| `auralis-web/backend/fingerprint_generator.py` | Async fingerprint generation | P2 |
| `auralis-web/backend/fingerprint_cache_manager.py` | Multi-tier caching (DB + memory) | P3 |

---

## Testing Strategy

### Unit Tests
- [ ] Fingerprint lookup from DB
- [ ] AdaptiveMode initialization with preset
- [ ] Chunk processing with mastering applied
- [ ] Cache hit/miss behavior

### Integration Tests
- [ ] Full pipeline: Load → Fingerprint → Master → Stream
- [ ] Cold cache (no fingerprint) → generate → cache → reuse
- [ ] Error handling: Missing fingerprint server
- [ ] Multiple presets: Adaptive, Gentle, Warm, Bright, Punchy

### Manual Testing
- [ ] Stream Overkill "Old School" → Verify 2D LWRP applied
- [ ] Stream Slipknot live → Verify expansion factor
- [ ] Stream quiet material → Verify makeup gain applied
- [ ] Frontend playback → No audio gaps or artifacts

---

## Success Criteria

✅ **Phase 1 Complete When**:
- Fingerprints load from database for cached tracks
- ChunkedAudioProcessor initializes AdaptiveMode
- Chunk processing applies adaptive mastering
- 2D LWRP decisions logged for each chunk

✅ **Full Integration Complete When**:
- WebSocket streaming delivers processed audio
- Frontend plays enhanced audio without gaps
- All presets work (Adaptive, Gentle, Warm, Bright, Punchy)
- Fingerprinting on-demand works when cache miss
- User can hear the mastering effect (louder, better dynamics)

---

## Risk Assessment

### Risk: Fingerprint Server Timeout
**Impact**: Streaming delayed while waiting for fingerprinting
**Mitigation**: 60-second timeout, graceful fallback to unmastered audio

### Risk: Database Bottleneck
**Impact**: Slow fingerprint lookup on first play
**Mitigation**: In-memory cache in audio_stream_controller, async queries

### Risk: Chunk Processing Latency
**Impact**: Playback gaps if processing takes > 10 seconds
**Mitigation**: Background processing for future chunks, cache hit fast path

### Risk: 2D LWRP Over-Expansion
**Impact**: Audio distortion on already-loud material
**Mitigation**: ✅ Already validated on Slipknot + Overkill material

---

## Next Steps

1. Start with **Phase 1: Database Integration**
   - Fix FingerprintRepository initialization
   - Add DB lookup to ChunkedAudioProcessor
   - Verify fingerprint loads before processing

2. Continue with **Phase 2: Mastering Engine Integration**
   - Initialize AdaptiveMode
   - Apply adaptive processing to chunks
   - Verify 2D LWRP decisions in logs

3. Test end-to-end with real audio files
   - Loud compressed material (Overkill)
   - Dynamic loud material (Slipknot)
   - Quiet material (needs makeup gain)

---

**Status**: Ready for Implementation
**Target Completion**: Within 2-3 days of focused development
**Blocker**: FingerprintRepository session_factory initialization fix needed first
