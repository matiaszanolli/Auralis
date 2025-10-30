# Beta.8 Roadmap - MSE Frontend Migration

**Target**: Complete the MSE frontend migration to unlock instant preset switching

**Status**: Planning (Beta.7 in progress)

**Key Insight**: The backend foundation is 95% complete! Only frontend integration is missing.

---

## ✅ **Already Complete in Beta.6**

### 25D Audio Fingerprint System
- ✅ 7 specialized analyzers extracting 25 dimensions
- ✅ Integrated into HybridProcessor for intelligent parameter selection
- ✅ Validated on real tracks (Exodus, Rush, Steven Wilson)
- ✅ See: `docs/sessions/oct26_fingerprint_system/`

### .25d Sidecar File Format
- ✅ **5,251x speedup** for fingerprint extraction (31s → 6ms cached)
- ✅ JSON sidecar format (1.35 KB per file)
- ✅ `SidecarManager` class (342 lines) with validation
- ✅ Automatic cache detection and writing
- ✅ Portable metadata that travels with audio files
- ✅ **Production ready** - shipped in Beta.6
- ✅ See: `25D_SIDECAR_IMPLEMENTATION_COMPLETE.md`

### MSE Backend Streaming
- ✅ `/api/mse_streaming/` and `/api/unified_streaming/` endpoints
- ✅ WebM/Opus encoding pipeline
- ✅ Multi-tier buffer system (L1/L2/L3) with 99 MB total cache
- ✅ Branch predictor for learning user preset switching patterns
- ✅ ChunkedAudioProcessor with 30s chunks + 3s crossfade
- ✅ See: Beta.4 implementation (Oct 27, 2025)

---

## 🎯 **P0 - THE CRITICAL BLOCKER**

### 1. Complete MSE Frontend Integration
**Goal**: Enable instant preset switching with progressive streaming

**Current State**:
- ✅ Backend MSE endpoints ready (`/api/mse_streaming/`, `/api/unified_streaming/`)
- ✅ Multi-tier buffer system (L1/L2/L3) implemented
- ✅ WebM/Opus encoding pipeline ready
- ❌ Frontend still uses HTML5 `<audio>` with full files
- ❌ No progressive chunk loading

**Implementation**:
1. **Update `BottomPlayerBarConnected.tsx`** to use Media Source Extensions API
   - Replace `<audio src={url}>` with MSE SourceBuffer
   - Load initial chunk immediately (< 100ms playback start)
   - Progressive chunk fetching from `/api/mse_streaming/chunk/{track_id}/{chunk_idx}`
   - Handle chunk transitions with seamless buffering

2. **Preset Switching Logic**
   - On preset change: fetch new chunk from multi-tier buffer
   - If cached (L1/L2/L3): < 10ms switch time
   - If uncached: 100-200ms (immediate processing + serve)
   - Branch predictor learns user patterns for pre-caching

3. **Testing**
   - Unit tests for MSE buffer management
   - Integration tests for chunk transitions
   - Performance benchmarks (target: < 100ms preset switch)

**Estimated Effort**: 16-24 hours
**Dependencies**: None (backend ready)

---

### 2. ~~25D Fingerprint Progressive Analysis~~
**Status**: ✅ **NOT NEEDED** - .25d sidecar files already provide instant loading

**Why skip this**:
- .25d files load in 6ms (vs 31s analysis)
- 5,251x speedup already achieved
- Progressive analysis adds complexity without benefit
- Current system: analyze once, cache forever in .25d file

### 3. ~~.25d File Format~~
**Status**: ✅ **ALREADY COMPLETE** - Production ready since Beta.6

**Current implementation**:
- ✅ JSON sidecar format (`track.flac.25d`)
- ✅ `SidecarManager` class handles read/write/validation
- ✅ Automatic cache detection in `FingerprintExtractor`
- ✅ 5,251x speedup (31s → 6ms)
- ✅ All 25 fingerprint dimensions stored
- ✅ File size: 1.35 KB per track
- ✅ See: `25D_SIDECAR_IMPLEMENTATION_COMPLETE.md`

---

## 🎨 **P1 - Enhanced User Experience**

### 4. Fingerprint Visualization
**Goal**: Show users the 25D acoustic profile of their music

**Features**:
- Spider/radar chart of 7 frequency dimensions
- Dynamics meter (LUFS, crest, bass/mid ratio)
- Temporal rhythm visualization
- Genre similarity graph

**Estimated Effort**: 8-12 hours

---

### 5. Smart Preset Recommendations
**Goal**: Auto-recommend presets based on 25D fingerprint

**Logic**:
- High dynamics + wide stereo → "gentle" preset
- Brick-walled (low crest) → "expand dynamics" preset
- Bass-heavy → "warm" preset
- Presence-heavy → "bright" preset
- High transient density → "punchy" preset

**Estimated Effort**: 6-8 hours

---

### 6. Cross-Genre Music Discovery
**Goal**: "Find songs like this" based on 25D similarity

**Implementation**:
- K-NN graph builder (already exists: `FingerprintSimilaritySystem`)
- Euclidean distance in 25D space
- UI: "Similar tracks" section in track details
- Playlist generation: "Create playlist from similar tracks"

**Estimated Effort**: 12-16 hours
**Dependencies**: .25d file format, library-wide fingerprint cache

---

## 📊 **P2 - Advanced Features**

### 7. Continuous Enhancement Space
**Goal**: Interpolate between presets based on fingerprint characteristics

**Concept**:
- Presets are discrete points in parameter space
- Use 25D fingerprint to compute weighted blend of presets
- Enable "custom" preset that adapts per-track

**Estimated Effort**: 16-20 hours

---

### 8. Real-Time Adaptive Processing
**Goal**: Adjust processing parameters dynamically during playback

**Features**:
- Detect section changes (verse/chorus/bridge)
- Adapt EQ/dynamics per section
- Preserve intentional loudness variation

**Estimated Effort**: 20-24 hours

---

## 🔬 **P3 - Research & Validation**

### 9. Genre Profile Research
**Goal**: Build validated genre profiles from fingerprint analysis

**Process**:
- Analyze 100+ tracks per genre (rock, metal, jazz, classical, electronic)
- Generate statistical profiles (mean, std, ranges)
- Validate preset performance per genre
- Document findings

**Estimated Effort**: 24-32 hours
**Dependencies**: .25d file format, batch analysis tools

---

### 10. Mastering Quality Validation
**Goal**: Ensure processing preserves musical intent

**Metrics**:
- Dynamic range preservation (EBU R128)
- Frequency response accuracy
- Stereo field preservation
- Transient preservation

**Estimated Effort**: 16-20 hours

---

## 📅 **Revised Timeline Estimate**

**Total Estimated Effort**: 72-112 hours (~1.5-2.5 weeks full-time)

**Massive reduction** because .25d and 25D fingerprints are already complete!

**Suggested Phases**:

**Phase 1 (Week 1)**: P0 - MSE Frontend Migration
- Complete MSE integration in BottomPlayerBarConnected.tsx
- Enable progressive chunk loading
- Implement preset switching with multi-tier buffer
- Testing and validation

**Phase 2 (Week 2)**: P1 - User Experience
- Fingerprint visualization (spider charts, meters)
- Smart preset recommendations
- Music discovery ("Find similar tracks")

**Phase 3 (Week 3, optional)**: P2 - Advanced Features
- Continuous enhancement space
- Real-time adaptive processing
- Genre profile research

---

## 🎯 **Success Metrics**

1. **Preset switching**: < 100ms (vs current 2-5s)
2. **Playback start**: < 100ms first chunk load
3. **Fingerprint extraction**: < 1s per track (progressive)
4. **Music discovery accuracy**: > 80% user satisfaction
5. **Processing quality**: Pass EBU R128 validation

---

## 🚀 **Quick Wins for Beta.7** (Before Beta.8)

Since we're mid-Beta.7, let's include some quick fixes:

1. **Fix current preset switching** (2-4 hours)
   - Use cached full files properly
   - Enable proactive buffering
   - Target: 2-5s → < 1s for cached presets

2. **Document MSE architecture** (2 hours)
   - Explain Beta.4 MSE system
   - Why frontend wasn't migrated
   - Roadmap for Beta.8 completion

3. **Create .25d examples** (2 hours)
   - Generate .25d files for sample tracks
   - Add to research/data/fingerprints/
   - Show format in action

**Total Quick Wins**: 6-8 hours

---

## 📝 **Notes**

- **Beta.4 MSE backend** is production-ready (Oct 27, 2025)
- **25D fingerprint system** is validated (Oct 26, 2025)
- **.25d sidecar files** are production-ready (Beta.6, Oct 29, 2025)
- **Multi-tier buffer** is implemented but not connected to playback
- **Frontend migration** is the ONLY critical blocker

**The foundation is already 95% complete - we just need MSE frontend integration!**

---

## 🚀 **Priority for Beta.7 Hotfix**

Before starting Beta.8, let's fix the current preset switching issue:

### Quick Fix: Cached File Approach (DONE)
- ✅ Modified `/api/player/stream/` to check for cached full files first
- ✅ Only processes if cache miss
- ✅ Proactive buffering of other presets in background
- ⏱️ Expected: First preset switch ~2-5s, subsequent switches < 1s (if cached)

**This buys us time** to do the MSE migration properly in Beta.8 without rushing.

---

## 🎯 **The Big Picture**

**What we have**:
1. ✅ 25D acoustic fingerprinting (7 analyzers, 25 dimensions)
2. ✅ .25d sidecar caching (5,251x speedup)
3. ✅ Intelligent parameter selection (fingerprint-driven processing)
4. ✅ MSE backend streaming (WebM/Opus chunks)
5. ✅ Multi-tier buffer (L1/L2/L3 with branch prediction)
6. ✅ Chunked processing (30s chunks, 3s crossfade)

**What's missing**:
1. ❌ MSE frontend integration (still using HTML5 `<audio>` tag)

**Once MSE frontend is complete**, Auralis will have:
- ⚡ **Instant preset switching** (< 100ms)
- 🎵 **Instant playback start** (< 100ms first chunk)
- 🧠 **Intelligent pre-caching** (branch predictor learns patterns)
- 💾 **Massive library performance** (5,251x fingerprint speedup)
- 🎨 **Cross-genre discovery** (25D similarity matching)

**This is a transformative release.** The backend is world-class - we just need to connect the frontend.
