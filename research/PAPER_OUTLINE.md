# Auralis Technical Paper - Quick Outline

**Full Paper v2.0**: [paper/auralis_realtime_adaptive_mastering_v2.md](paper/auralis_realtime_adaptive_mastering_v2.md) (UPDATED Nov 1, 2025)
**Full Paper v1.0**: [paper/auralis_realtime_adaptive_mastering.md](paper/auralis_realtime_adaptive_mastering.md) (Original Oct 27, 2025)

---

## Abstract (200 words) - Updated v2.0

Production-ready real-time adaptive audio mastering system enabling **instant audio enhancement without reference tracks** through:
1. **25-dimensional acoustic fingerprint system** for cross-genre music analysis
2. **Portable .25d sidecar file format** delivering 5,251x speedup for repeated analysis
3. **Mathematical framework derived from real album analysis** (64+ tracks across 9 albums)
4. **Unified streaming architecture** (MSE + Multi-Tier Buffer)
5. **CPU-inspired hierarchical caching** with branch prediction

**Key Results**:
- <100ms preset switching latency (20-50x improvement)
- 36.6x real-time processing speed
- 5,251x fingerprint caching speedup (31s → 6ms)
- 91% cache hit rate during typical sessions
- 86% storage reduction through WebM/Opus encoding
- Production-ready: Beta.6 with 430+ tests (100% backend, 95.5% frontend)
- Real-world validation: 54,735 tracks

---

## 1. Introduction

### 1.1 Motivation
- Traditional mastering: offline, batch-oriented, requires reference tracks
- Streaming services: limited DSP control, no user customization
- **Gap**: No system enables instant preset switching during real-time playback

### 1.2 Challenges
1. Processing latency (full-file mastering takes seconds)
2. MSE format compatibility (requires WebM, not WAV)
3. Memory constraints (caching all presets prohibitively expensive)
4. Dual playback conflicts (MSE + HTML5 Audio race conditions)
5. Perceptual continuity (avoiding glitches during preset switches)

### 1.3 Contributions
1. **25-dimensional acoustic fingerprint system**: Comprehensive multidimensional audio analysis (frequency 7D, dynamics 3D, temporal 4D, spectral 3D, harmonic 3D, variation 3D, stereo 2D) enabling reference-free parameter selection
2. **.25d sidecar file format**: Portable, non-destructive metadata caching delivering 5,251x speedup (31s → 6ms) for fingerprint extraction
3. **Mathematical framework from real albums**: Data-driven insights from 64+ tracks (natural LUFS variation 10-20 dB, consistent crest factors ±2.4 dB, LUFS-frequency correlation r=+0.974)
4. **Unified streaming architecture**: Single endpoint, intelligent routing (MSE + Multi-Tier Buffer)
5. **Production validation**: Beta.6 with 430+ tests (100% backend, 95.5% frontend), validated on 54,735 real-world tracks

---

## 2. Background

### 2.1 Digital Audio Fundamentals
- PCM: 44.1 kHz sampling, 16/24-bit quantization
- Mastering: loudness normalization, EQ, dynamics, stereo enhancement

### 2.2 Matchering (Prior Art)
- Reference-based: matches target to reference characteristics
- Offline only: batch processing, no real-time support
- **Limitation**: No instant preset switching

### 2.3 Media Source Extensions (MSE)
- W3C spec for progressive streaming
- Requires containerized formats (WebM, MP4)
- 97% browser compatibility (Chrome, Firefox, Edge, Safari)

---

## 3. Methodology

### 3.1 System Architecture
```
Frontend (UnifiedPlayerManager)
    ↓
Unified Streaming Endpoint
    ├─ MSE Path (unenhanced) → WebM/Opus
    └─ MTB Path (enhanced) → Multi-Tier Buffer → WAV
```

### 3.2 Chunked Multidimensional Segmentation
- **Chunks**: 30-second duration (K = ⌈duration / 30⌉)
- **Features** (5D):
  1. Energy (RMS power)
  2. Brightness (spectral centroid)
  3. Dynamics (crest factor)
  4. Vocal presence (mid-frequency energy)
  5. Tempo energy (onset strength)
- **Context**: 1-second overlap for crossfading

### 3.1 25-Dimensional Acoustic Fingerprint System (NEW - v2.0)
- **Frequency Distribution (7D)**: Sub-bass, bass, low-mid, mid, upper-mid, presence, air percentages
- **Dynamics Characteristics (3D)**: LUFS, crest factor, bass/mid ratio
- **Temporal Characteristics (4D)**: Tempo, rhythm stability, transient density, silence ratio
- **Spectral Shape (3D)**: Spectral centroid, rolloff, flatness
- **Harmonic Content (3D)**: Harmonic ratio, pitch stability, chroma energy
- **Variation Characteristics (3D)**: Dynamic range variation, loudness variation, peak consistency
- **Stereo Imaging (2D)**: Stereo width, phase correlation

### 3.2 Mathematical Framework from Real Albums (NEW - v2.0)
- **Albums analyzed**: 64+ tracks across 9 albums (Steven Wilson, deadmau5, Metallica, AC/DC, etc.)
- **Discovery 1**: LUFS variation 10-20 dB within albums (natural, intentional)
- **Discovery 2**: Crest factor std ±2.4 dB (what's actually consistent)
- **Discovery 3**: LUFS↔Frequency correlation r=+0.974 (physics, not mastering)
- **Discovery 4**: Mid-dominance rare (only ~15% of tracks)

### 3.3 .25d Sidecar File Format (NEW - v2.0)
- **Format**: JSON, 1.35 KB typical, naming: `<audio_filename>.25d`
- **Validation**: File size, timestamp, format version, 25 dimensions present
- **Performance**: 31s → 6ms (5,251x speedup)
- **Storage**: 74 MB for 54,735 tracks (negligible)

### 3.4 Content Analysis Framework (Preserved from v1.0)
- **Spectral**: FFT, critical bands, psychoacoustic weighting
- **Dynamics**: RMS, peak, crest, LUFS (ITU-R BS.1770-4)
- **Temporal**: Onset detection, tempo, rhythm stability

### 3.4 Adaptive Target Generation
**Presets**:
1. Adaptive (default): Content-aware balanced enhancement
2. Gentle: Subtle corrections
3. Warm: Mid-bass boost, treble roll-off
4. Bright: Presence/air enhancement
5. Punchy: Tight bass, aggressive compression

---

## 4. Implementation

### 4.1 Backend Architecture

#### 4.1.1 Unified Streaming Endpoint
```python
GET /api/audio/stream/{track_id}/chunk/{chunk_idx}
    ?enhanced={bool}
    &preset={adaptive|warm|bright|punchy|gentle}
    &intensity={0.0-1.0}
```

**Routing**:
- `enhanced=false`: MSE path (WebM/Opus)
- `enhanced=true`: MTB path (WAV from cache/processing)

#### 4.1.2 WebM/Opus Encoder
- **ffmpeg**: libopus codec, 192 kbps VBR
- **Performance**: 300-600ms encoding (19-50x real-time)
- **Compression**: 86% size reduction (5.3 MB → 769 KB)

#### 4.1.3 Multi-Tier Buffer System
- **L1 Cache (18 MB)**: Current + next chunk, predicted presets → 0-50ms
- **L2 Cache (36 MB)**: Branch scenarios (>20% probability) → 150-200ms
- **L3 Cache (45 MB)**: Recent tracks, any preset → 500ms-2s

**Branch Predictor**:
- Transition matrix: P(next_preset | current_preset)
- Accuracy: 35% (cold start) → 68% (mature)

#### 4.1.4 Chunked Audio Processor
- Load chunk + 1s context
- Extract features → generate targets → process
- Trim context, save WAV, encode WebM

### 4.2 Frontend Architecture

#### 4.2.1 Unified Player Manager
- **MSEPlayerInternal**: MediaSource API, SourceBuffer, progressive loading
- **HTML5AudioPlayerInternal**: Standard Audio element, full file loading
- **Mode switching**: Save position → destroy old player → initialize new → seek → resume

#### 4.2.2 UI Component
- Enhancement toggle (MSE ↔ HTML5)
- Preset selector (5 presets)
- Intensity slider (0-100%)
- Mode indicator (⚡ Instant / 🎛️ Enhanced)

### 4.3 Testing
- **Backend**: 241+ tests, 100% pass rate
- **Coverage**: 75% unified_streaming, 38% webm_encoder, 100% multi_tier_buffer
- **Frontend**: Planned (85-90% target)

---

## 5. Results

### 5.1 Fingerprint Extraction Performance (NEW - v2.0)

| Component | Time | Notes |
|-----------|------|-------|
| Uncached extraction | 31.1s | Audio loading + analysis |
| **Cached (.25d)** | **6ms** | **JSON read + parse** |
| **Speedup** | **5,251x** | **31s → 6ms** |

**Batch extraction (100 tracks)**:
- 0% cache hit: 3,109s (~52min)
- 80% cache hit: 620s (~10min)
- 100% cache hit: 0.6s

**Full library (54,735 tracks)**:
- Uncached: 19.7 days
- 100% cached: 5.5 minutes (time saved: 19.7 days)

### 5.2 Similarity Search Performance (NEW - v2.0)

| Method | Time | Speedup | Notes |
|--------|------|---------|-------|
| Naive distance | 510ms | Baseline | 54,735 comparisons |
| Pre-filtering | 31ms | 16x faster | 4D range queries |
| K-NN graph | <1ms | 500x faster | Pre-computed edges |

**Real-world validation**: 54,735 tracks, 100% test pass rate (14/14 tests)

### 5.3 Preset Switching Latency (Preserved from v1.0)

| Scenario | Latency | Improvement |
|----------|---------|-------------|
| Traditional (full reprocess) | 6,350 ms | Baseline |
| Chunk (cold cache) | 1,800-2,500 ms | 2.5-3.5x |
| L3 cache hit | 500 ms | 12.7x |
| L2 cache hit | 150-200 ms | 31-42x |
| **L1 cache hit** | **10-50 ms** | **127-635x** ✅ |
| **MSE unenhanced** | **<100 ms** | **63x+** ✅ |

### 5.2 Processing Performance
- **Real-time factor**: 36.6x (232.7s track in 6.35s)
- **First chunk latency**: 800-1,200 ms
- **Memory**: 180 MB peak (60% reduction vs. full-file)

### 5.3 WebM Encoding
- **Size**: 769 KB (86% reduction from 5.3 MB WAV)
- **Time**: 300-600 ms
- **Quality**: Transparent at 192 kbps VBR

### 5.4 Cache Performance
- **Hit rates**: L1 45%, L2 28%, L3 18%, Miss 9%
- **Total cache hits**: 91%
- **Average latency**: 180 ms (weighted)

---

## 6. Discussion

### 6.1 Limitations
1. **Enhancement toggle latency**: 1-2s pause (mode switching)
2. **iOS Safari**: No MSE support (HTML5 Audio fallback)
3. **Perceptual validation**: Formal MUSHRA tests not yet conducted
4. **Genre tuning**: Generic presets may not be optimal for all genres

### 6.2 Edge Cases
- Corrupt audio: Graceful fallback to neutral features
- Rapid switching: 500ms debouncing, exploration mode detection
- Track deletion: Selective cache invalidation
- Memory pressure: Strict tier limits, LRU eviction

### 6.3 Perceptual Considerations
- Crossfade artifacts: Potential transient splitting, phase shifts
- Preset switching continuity: Abrupt parameter changes at chunk boundaries
- Loudness consistency: All presets target -14 LUFS

---

## 7. Future Work

### 7.1 Cross-Platform Stability
- macOS code signing, ARM64 builds
- Android/iOS native apps

### 7.2 Perceptual Testing
- MUSHRA: Chunked vs. full-file (target >4.0 transparency)
- ABX: Preset distinctness validation
- Loudness consistency studies

### 7.3 ML-Based Adaptation
- Deep learning genre classifier (YAMNet, OpenL3)
- Reinforcement learning for preset selection
- Personalized mastering models

### 7.4 Enhanced Caching
- Adaptive cache sizing (based on available memory)
- Predictive prefetching (time-of-day, genre patterns)
- Distributed caching across devices

### 7.5 Advanced Processing
- User-customizable presets
- Spectral masking-aware EQ
- AI-driven de-remastering (undo excessive compression)

### 7.6 Music Recommendation
- Similarity-based discovery (25D fingerprint distance)
- Cross-genre recommendations
- Mood-based auto-playlists

---

## 8. Conclusion

Auralis achieves **instant preset switching** (<100ms) during real-time playback through:
1. Unified streaming architecture (eliminates dual playback conflicts)
2. Chunked processing (sub-second latency)
3. Multi-tier caching (91% hit rate)
4. WebM/Opus encoding (86% size reduction)

**Impact**: Bridges gap between automatic mastering (Matchering) and real-time playback (streaming), enabling instant sonic experimentation during listening.

**Future**: Perceptual validation, ML personalization, cross-platform deployment, music recommendation integration.

---

## Appendices

### A. System Architecture Diagram
Complete system flow: Frontend → Unified Endpoint → MSE/MTB paths → Audio Processing → Cache layers

### B. Chunk Processing Flow
Step-by-step example: 8-chunk processing for 232.7s track

### C. Preset Switching Sequence Diagram
User interaction → Frontend → Backend → Cache lookup → Audio delivery (10-50ms)

### D. Performance Benchmarks
- WebM encoding (bitrate vs. quality)
- HybridProcessor (component timing)
- Cache simulation (hit rates, latency distributions)
- Branch prediction (learning curves)

---

## Target Venues

1. **AES (Audio Engineering Society)**: Convention paper or Journal of the AES
2. **ACM Multimedia**: Full paper (systems track)
3. **IEEE ICASSP**: Signal processing focus
4. **ISMIR**: Music information retrieval angle (25D fingerprint)

---

## Key Figures (To be created)

1. **System architecture diagram** (Frontend → Backend → Processing)
2. **Chunk processing timeline** (Latency breakdown per component)
3. **Cache hit rate vs. time** (Learning curve over 1-hour session)
4. **Preset switching latency distribution** (L1/L2/L3/Miss)
5. **WebM encoding quality vs. bitrate** (MUSHRA-style comparison)
6. **Branch prediction accuracy** (Accuracy vs. number of switches)
7. **Real-time factor comparison** (Auralis vs. Matchering vs. DAW plugins)

---

## Key Tables (Included in paper)

1. Preset switching latency comparison
2. Component-level processing time breakdown
3. WebM encoding performance metrics
4. Cache hit rates by tier
5. Branch prediction accuracy over time
6. Browser compatibility matrix

---

**Paper Status**: Draft v2.0 (November 1, 2025) - **MAJOR UPDATE**
**Word Count**: ~17,500 words (comprehensive technical paper)
**Target Length**: 10-15 pages (IEEE double-column format) or 20-25 pages (AES format)

**What's New in v2.0**:
- 25D acoustic fingerprint system (complete specification)
- .25d sidecar file format (5,251x speedup)
- Mathematical framework from real album analysis (64+ tracks)
- Production validation (Beta.6, 430+ tests, 54,735 tracks)
- Updated performance benchmarks with real measurements

Next steps: Create figures, collect benchmark data, conduct perceptual tests, submit to venue.
