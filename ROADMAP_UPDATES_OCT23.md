# Roadmap Updates - October 23, 2025

Three new features have been added to the Auralis development roadmap based on user request. All additions are in **Phase 4: Advanced Playback Features**.

---

## 1. Track Metadata Editing & Management (HIGH PRIORITY)

**Location**: Phase 4.1
**Timeline**: 4-5 days
**Priority**: 🔴 HIGH

### Summary
Allow users to edit and manage track metadata directly within Auralis, eliminating the need for external tools.

### Key Features
- **Individual & Batch Editing**: Edit single tracks or multiple tracks at once
- **Complete Metadata Support**: Title, Artist, Album, Track#, Year, Genre, BPM, Lyrics, Comments, and format-specific tags
- **Format Support**: MP3, FLAC, M4A, OGG, WAV (using mutagen library)
- **Advanced Features**:
  - Auto-populate from filename patterns
  - Fetch metadata from MusicBrainz/Discogs
  - Tag cleanup tools (trim whitespace, fix capitalization)
  - Preview changes before saving
  - Backup before editing (optional)

### API Endpoints
- `PUT /api/library/tracks/:id/metadata` - Update track metadata
- `GET /api/library/tracks/:id/metadata/formats` - Get available format-specific tags
- `POST /api/library/tracks/batch/metadata` - Batch metadata update

### UI Components
- **EditMetadataDialog**: Form with all metadata fields, validation, preview
- **Batch Editor**: Edit multiple tracks with common fields
- **Context Menu**: Right-click → "Edit Metadata" (Ctrl+E)
- **Track Detail View**: Inline editing for quick changes

### Impact
Essential for music library management. Users can maintain clean, organized metadata without leaving Auralis or using external tag editors like Kid3, EasyTAG, or MusicBrainz Picard.

---

## 2. Smart Chunk Shaping (MEDIUM PRIORITY)

**Location**: Phase 4.2
**Timeline**: 5-7 days
**Priority**: ⚠️ MEDIUM

### Summary
Improve chunked streaming by using intelligent chunk boundaries based on audio content (mood, energy, silence) rather than fixed 30-second intervals.

### Technical Approach
Replace fixed-time chunks with content-aware boundaries:

1. **Analyze audio waveform** for natural break points
2. **Detect silent sections** (below -60dB threshold)
3. **Identify mood/energy transitions** using RMS and spectral changes
4. **Detect tempo changes** and beat boundaries
5. **Optimize chunk sizes** (15-45s range)

### New Module: AdaptiveChunkShaper
```python
# Proposed API
analyze_chunk_points(audio, sr, min_chunk=15s, max_chunk=45s)
detect_mood_changes(audio, sr)
find_silent_regions(audio, sr, threshold=-60dB)
align_to_beats(audio, sr, boundaries)  # optional
```

### Integration
- Integrates with existing **ChunkedAudioProcessor** (already implemented in Phase 1.5)
- Cache chunk boundaries per track in database (avoid re-analysis)
- Fallback to fixed 30s chunks if analysis fails or for short tracks (<90s)
- Configurable via settings (enable/disable smart chunking)

### Benefits
- **More natural listening**: No splits in the middle of vocals or prominent sounds
- **Fewer audible artifacts**: Crossfades occur at natural transitions
- **Better UX**: Chunks align with musical structure
- **Minimal overhead**: Analysis completes in <1s per track

### Performance Criteria
- Chunk sizes: 15-45 seconds (streaming efficient, memory safe)
- Analysis time: <1 second per track
- Performance impact: <10% overhead
- Crossfades: Still seamless at new boundaries

---

## 3. Mastering Algorithm Performance Review (LOW-MEDIUM PRIORITY)

**Location**: Phase 5.1
**Timeline**: 7-10 days (4 phases)
**Priority**: 📊 LOW-MEDIUM

### Summary
Conduct comprehensive review of the adaptive mastering algorithm to identify performance bottlenecks and optimization opportunities.

**Note**: Current performance is already excellent (52.8x real-time, 197x with optimizations). This review is about finding additional gains and ensuring we haven't missed easy optimizations.

### Four-Phase Approach

#### Phase 1: Profiling & Analysis (3-4 days)
- Profile entire processing pipeline (HybridProcessor, DSP stages, content analysis)
- Memory profiling (identify leaks, track NumPy allocations)
- Identify hotspots (CPU-intensive operations)
- Benchmark current performance (by file size, format, preset)
- **Tools**: cProfile, line_profiler, py-spy, memory_profiler

#### Phase 2: Algorithm Review (2-3 days)
- Review adaptive mastering algorithm logic:
  - ContentAnalyzer efficiency
  - AdaptiveTargetGenerator complexity
  - Genre classification overhead (ML model)
  - Psychoacoustic EQ (26 critical bands)
  - Dynamics processing (envelope followers, compression, limiting)
- Review DSP implementations (FFT, filters, resampling, stereo)
- Compare with reference implementations (librosa, scipy.signal, pydub)

#### Phase 3: Optimization Implementation (2-3 days)
**Investigate these potential optimizations**:

- **NumPy/SciPy**: In-place operations, vectorization, optimized functions
- **FFT**: Use FFTW via pyfftw (faster), cache FFT plans, optimal sizes, parallelize stereo
- **Caching**: Cache content analysis, genre classification, FFT intermediates
- **Parallel Processing**: Parallelize stereo channels, batch operations, chunk processing
- **Algorithm Simplifications**:
  - Reduce psychoacoustic EQ from 26 to 18 bands (still perceptually accurate)
  - Simplify genre classification for real-time
  - Optimize envelope follower (reduce oversampling)
  - Skip analysis steps for low-intensity processing
- **Memory**: More aggressive memory pooling, float32 vs float64, release intermediate arrays

#### Phase 4: Testing & Validation (1-2 days)
- Benchmark each optimization (measure speedup)
- Audio quality verification (PESQ, VISQOL scores)
- A/B test original vs optimized output (should be identical or imperceptibly different)
- Verify no test suite regressions
- **Documentation**: Create MASTERING_ALGORITHM_PERFORMANCE.md report

### Success Criteria
- Comprehensive profiling report completed
- At least 3 significant bottlenecks identified
- At least 2 optimizations implemented and tested
- **Performance improvement**: 10-20% on common use cases
- Audio quality maintained (verified by objective metrics)
- No regressions in existing test suite
- Documentation updated with findings

### Impact
- Faster processing (10-20% speedup target)
- Lower CPU usage
- Better battery life on laptops
- Identify future optimization opportunities

### Risk
Medium - Requires careful testing to ensure audio quality is maintained. Any algorithm changes must be validated to ensure they don't degrade output quality.

---

## Roadmap Context

These features fit into the overall roadmap structure:

- **Phase 0** (URGENT): WebSocket/REST architecture fixes
- **Phase 1** (80% complete): Favorites ✅, Playlists ✅, Album Art ✅, Queue ✅, Real-time Enhancement ✅
- **Phase 2** (Future): Albums View, Artists View, Recently Played
- **Phase 3** (Future): Settings System, Library Folder Management
- **Phase 4** (Updated): **Track Metadata ✨**, **Smart Chunk Shaping ✨**, Gapless, Crossfade ✅, Equalizer, Lyrics
- **Phase 5** (Updated): **Performance Review ✨**, Real-time Analysis, Batch Processing, A/B Comparison, Export
- **Phase 6-8** (Future): UI Polish, Performance, Platform-Specific Features

---

## Implementation Priority

Based on the priorities assigned:

### Immediate Next Steps (After Phase 0 fixes)
1. **Track Metadata Editing** (HIGH) - Essential library management feature
2. Complete any remaining Phase 1 items

### Medium-Term
3. **Smart Chunk Shaping** (MEDIUM) - UX improvement for streaming
4. Phase 2 features (Albums/Artists views)

### Long-Term Review
5. **Mastering Algorithm Performance Review** (LOW-MEDIUM) - Optimization work
6. Other Phase 5 professional features

---

## Files Modified

- **docs/design/AURALIS_ROADMAP.md**:
  - Updated "Last Updated" to October 23, 2025
  - Added Phase 4.1: Track Metadata Editing (HIGH PRIORITY)
  - Added Phase 4.2: Smart Chunk Shaping (MEDIUM PRIORITY)
  - Renumbered existing Phase 4 items (4.3 Gapless, 4.4 Crossfade ✅, 4.5 Equalizer, 4.6 Lyrics)
  - Added Phase 5.1: Mastering Algorithm Performance Review (LOW-MEDIUM PRIORITY)
  - Renumbered existing Phase 5 items (5.2+ shifted down)
  - Updated Phase 4 timeline from "2-3 weeks" to "3-4 weeks" (added 1 week)
  - Updated Phase 5 timeline from "3-4 weeks" to "4-5 weeks" (added 1 week)

---

## Next Actions

1. **Review and approve** these roadmap additions
2. **Prioritize** against existing Phase 0 urgent items (WebSocket/REST fixes)
3. **Schedule** implementation based on priorities:
   - Phase 0 fixes (4-7 days) - URGENT, should complete first
   - Track Metadata Editing (4-5 days) - HIGH priority after Phase 0
   - Smart Chunk Shaping (5-7 days) - MEDIUM priority
   - Performance Review (7-10 days) - LOW-MEDIUM priority, can be deferred

4. **Consider dependencies**:
   - Track Metadata requires no dependencies (can start anytime)
   - Smart Chunk Shaping requires ChunkedAudioProcessor (already exists from Phase 1.5)
   - Performance Review is standalone research/optimization work

---

**Document Created**: October 23, 2025
**Roadmap File**: [docs/design/AURALIS_ROADMAP.md](docs/design/AURALIS_ROADMAP.md)
**Status**: Ready for review and implementation scheduling
