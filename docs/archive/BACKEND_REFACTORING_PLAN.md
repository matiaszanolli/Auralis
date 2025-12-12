# Backend Playback Engine Refactoring Plan

**Status**: Architecture Analysis Complete | **Phase**: 3+ Roadmap
**Version**: 1.0 | **Last Updated**: 2025-12-05

## Executive Summary

The Auralis web backend has grown to **8,278 lines across multiple monolithic files** with significant architectural debt from rapid development phases (Phases 1-3 streaming consolidation). This plan proposes a **systematic refactoring** to achieve:

- **Single Responsibility**: Each module handles one clear concern
- **Testability**: Clear interfaces between components
- **Maintainability**: Reduced coupling and duplicate logic
- **Performance**: Optimized processing pipeline with caching strategies
- **Scalability**: Foundation for multi-track processing, concurrent operations

---

## 1. Playback Engine Architecture Analysis

### Current System Overview

```
User Request (Web)
    ↓
FastAPI Router (player.py, enhancement.py)
    ↓
PlayerStateManager ← → ConnectionManager (WebSocket)
    ↓
ChunkedAudioProcessor ← ChunkedAudioProcessor instances per track
    ↓
HybridProcessor (DSP from auralis.core)
    ↓
Filesystem Cache (temp/auralis_chunks/)
```

### 1.1 File Responsibilities (Current)

#### **chunked_processor.py (1,071 lines)** - CRITICAL MONOLITH
**Primary Responsibility**: Chunk-based audio processing for streaming playback

**Current Responsibilities** (too many):
1. Audio metadata loading and chunk boundary calculation
2. Chunk processing with DSP (HybridProcessor integration)
3. File signature generation and cache validation
4. Crossfading between chunk boundaries
5. Level smoothing and transition management
6. Intensity blending (dry/wet mix)
7. Fingerprint extraction and caching
8. Mastering targets generation and application
9. Context-aware processing (leading/trailing context)
10. WAV/PCM encoding and file I/O
11. Async processing coordination with locks
12. Last content profile tracking for API

**Distinct Responsibilities (should be extracted)**:
- **Chunk lifecycle**: loading, trimming, concatenation
- **Level management**: RMS calculation, smooth transitions, gain tracking
- **Fingerprint operations**: extraction, caching, target generation
- **Encoding**: WAV output formatting
- **Processing state**: shared processor instance management
- **Mastering recommendation**: engine initialization and caching

---

## 2. Monolithic Files Ranking (Refactoring Priority)

### Rank 1: CRITICAL (Foundational - Must Refactor First)

#### **chunked_processor.py (1,071 lines, 12 responsibilities)**
**Distinct Concerns**:
  - Chunk lifecycle (loading, boundary handling)
  - Level management (RMS, smoothing, gain)
  - Processing orchestration (sync/async coordination)
  - Encoding (WAV output)
  - Fingerprint operations (extraction, caching, targets)
  - State management (processor instance, content profiles)
**Estimated Split**: 6-8 focused modules (150-250 lines each)
**Breaking Changes**: High (public API changes)

#### **main.py (791 lines, 10 responsibilities)**
**Distinct Concerns**:
  - FastAPI app setup
  - Middleware configuration
  - Component initialization
  - Router registration
  - Startup/shutdown logic
  - Settings endpoints
  - Processing endpoints
  - Static file serving
**Estimated Split**: 4-5 focused modules
**Breaking Changes**: None if done carefully

#### **routers/player.py (968 lines, 9 responsibilities)**
**Distinct Concerns**:
  - Queue management operations
  - Playback control logic
  - State synchronization
  - Track loading workflow
  - Mastering recommendations
  - Buffer management
  - WebSocket broadcasting
  - Error handling
**Estimated Split**: 3-4 service classes + thin router (300-400 lines)
**Breaking Changes**: None (API endpoints unchanged)

---

## 3. Proposed Unified Architecture

### 3.1 New Module Organization

```
auralis-web/backend/
├── core/
│   ├── __init__.py
│   ├── processor_manager.py          # ← NEW: Processor lifecycle
│   ├── chunk_processor.py            # ← REFACTORED from chunked_processor
│   ├── chunk_boundaries.py           # ← NEW: Chunk math and alignment
│   ├── level_manager.py              # ← NEW: RMS, smoothing, gains
│   └── encoding/
│       ├── __init__.py
│       └── wav_encoder.py            # ← EXTRACTED: WAV output
│
├── audio/
│   ├── __init__.py
│   ├── stream_controller.py          # ← REFACTORED from audio_stream_controller
│   ├── pcm_encoder.py                # ← NEW: Frame splitting, base64
│   └── cache.py                      # ← NEW: Chunk caching strategy
│
├── services/
│   ├── __init__.py
│   ├── playback_service.py           # ← NEW: Play/pause/seek logic
│   ├── queue_service.py              # ← NEW: Queue operations
│   ├── enhancement_service.py        # ← NEW: Preset/intensity logic
│   ├── recommendation_service.py     # ← EXTRACTED: Mastering recommendations
│   └── preprocessing_service.py      # ← EXTRACTED from enhancement.py
│
├── routers/
│   ├── __init__.py
│   ├── player.py                     # ← REFACTORED: Thin API layer
│   ├── [others unchanged]
│
├── config/
│   ├── __init__.py
│   ├── app.py                        # ← EXTRACTED: FastAPI setup
│   ├── settings.py                   # ← EXTRACTED: Global settings
│   ├── middleware.py                 # ← EXTRACTED: Middleware setup
│   └── startup.py                    # ← EXTRACTED: Component initialization
│
└── main.py                           # ← SIMPLIFIED: 100 lines max
```

---

## 4. Phase 3+ Implementation Roadmap

### Phase 3: ChunkedProcessor Refactoring (~3 weeks)

#### Week 1: Foundation
1. Create `core/chunk_boundaries.py` with ChunkBoundaryManager
2. Create `core/level_manager.py` with LevelManager
3. Create `core/processor_manager.py` with ProcessorManager
4. Create `core/encoding/wav_encoder.py`

#### Week 2: Refactor Core
5. Refactor `core/chunk_processor.py`
6. Update AudioStreamController
7. Create facade wrapper for backward compatibility

#### Week 3: Integration & Testing
8. Fix all import paths
9. Integration testing
10. Performance validation

### Phase 4: Main.py Consolidation (~2 weeks)
1. Extract configuration modules
2. Extract startup logic
3. Extract routers
4. Simplify main.py

### Phase 5: Player Router Refactoring (~2 weeks)
1. Create PlaybackService
2. Create QueueService
3. Create RecommendationService
4. Refactor routers/player.py

### Phase 6: Audio Pipeline (~2 weeks)
1. Refactor AudioStreamController
2. Extract PCMEncoder
3. Extract ChunkCache

---

## Testing Strategy Throughout Refactoring

### Unit Tests (Per Module)
- **ChunkBoundaryManager**: 15 tests (boundary calculations, overlap)
- **LevelManager**: 10 tests (RMS, smoothing, history)
- **ProcessorManager**: 8 tests (caching, lifecycle)
- **WAVEncoder**: 6 tests (format, bit depth)
- **ChunkProcessor**: 12 tests (processing, dependencies)
- **PlaybackService**: 15 tests (play, pause, seek, state)
- **QueueService**: 12 tests (add, remove, reorder)
- **StreamController**: 10 tests (orchestration, error handling)

**Total**: ~90 unit tests (~1-2 minute suite)

### Integration Tests (Preserved)
- End-to-end playback workflow
- Streaming via WebSocket
- State synchronization
- Enhancement preset changes
- Concurrent chunk processing

**Target**: All existing integration tests pass without modification

---

## Critical Files for Implementation

- `/mnt/data/src/matchering/auralis-web/backend/chunked_processor.py` - Core logic to refactor (1,071 lines)
- `/mnt/data/src/matchering/auralis-web/backend/routers/player.py` - Business logic extraction (968 lines)
- `/mnt/data/src/matchering/auralis-web/backend/main.py` - Configuration consolidation (791 lines)
- `/mnt/data/src/matchering/auralis-web/backend/audio_stream_controller.py` - Orchestration refactor (457 lines)

---

## Conclusion

This refactoring plan addresses **architectural debt** accumulated during rapid development. The **6-phase approach** progressively extracts responsibilities while maintaining backward compatibility and testing coverage.

**Key Principles**:
- Single responsibility per module
- Clear interfaces between components
- Comprehensive testing at each step
- Backward compatibility until fully migrated
- Performance validation throughout

**Timeline**: ~9-12 weeks for full implementation
**Breaking Changes**: None externally; internal APIs clean
**Benefit**: Maintainable, testable, extensible foundation for Phase 4+
