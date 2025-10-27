# Auralis Master Roadmap

**Last Updated**: October 27, 2025
**Current Phase**: Post-Beta.2 Development
**Next Release**: Beta.3 (Target: TBD)

---

## 🎯 Current State (October 27, 2025)

### ✅ Completed Major Milestones

**Beta.2 Release (October 26, 2025)** - Production Quality
- ✅ Audio processing engine (52.8x real-time speed)
- ✅ Performance optimization (Numba JIT + vectorization)
- ✅ Multi-tier buffer system (L1/L2/L3 caching)
- ✅ Library management (50k+ tracks, pagination, caching)
- ✅ Desktop builds (AppImage, DEB, Windows)
- ✅ All Beta.1 critical bugs fixed (audio fuzziness, gapless playback, pagination)

**25D Audio Fingerprint System (October 27, 2025)** - ✨ NEW
- ✅ Core integration complete (Phase 1)
- ✅ ContentAnalyzer extracts 25D fingerprints
- ✅ AdaptiveTargetGenerator uses fingerprints for intelligent processing
- ✅ Validated on synthetic + real audio
- ✅ Production-ready, 100% backward compatible

---

## 🚀 Active Development Tracks

We have three parallel development tracks. Here's the prioritized roadmap:

---

## Track 1: MSE Progressive Streaming - 🚨 P0 CRITICAL

**Priority**: **MAXIMUM** - Blocking smooth user experience
**Status**: 🟡 Planning → Ready for implementation
**Effort**: 2-3 weeks focused development
**Impact**: Makes preset switching instant (20-50x faster)

### Problem

Current architecture forces 2-5 second pause when changing presets during playback. This severely impacts UX.

**Current Behavior**:
```
User clicks "Punchy" preset:
  1. Audio pauses ⏸️
  2. Backend processes entire track (2-5s) ⏳
  3. User waits... 😤
  4. Playback resumes ▶️
```

**Target Behavior**:
```
User clicks "Punchy" preset:
  1. Audio switches instantly ⚡ (<100ms)
  2. Multi-tier buffer serves pre-processed chunk
  3. User happy! 😊
```

### Implementation Plan

**Phase 1: Backend Chunk Streaming API** (2-3 days)
- New endpoint: `GET /api/player/stream/{track_id}/chunk/{chunk_idx}`
- Metadata endpoint: `GET /api/player/stream/{track_id}/metadata`
- Integrate with existing multi-tier buffer

**Phase 2: Frontend MSE Integration** (3-4 days)
- Replace HTML5 Audio with MSE
- Implement MSEPlayer class
- Progressive chunk loading
- Seamless preset switching

**Phase 3: Multi-Tier Buffer Integration** (1 day)
- Trigger buffer on playback
- Ensure L1/L2/L3 caches are utilized
- Preset prediction for cache warming

**Phase 4: Testing & Optimization** (2-3 days)
- Browser compatibility (Chrome, Firefox, Edge, Safari)
- Performance testing (target: <100ms preset switch)
- Edge cases (seeking, rapid switching, network errors)
- Fallback for browsers without MSE

### Success Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Preset switch latency | 2-5s | <100ms | **20-50x** |
| Initial playback | ~2s | ~500ms | **4x** |
| Memory usage | High | Low | **60-80%↓** |
| Cache hit rate | 0% | 80-90% | **∞** |

### Why P0?

- **User Impact**: CRITICAL - Affects core listening experience every session
- **Technical Readiness**: HIGH - Multi-tier buffer already built, just need MSE glue
- **Effort**: MEDIUM - 2-3 weeks, well-understood tech
- **Business Impact**: HIGH - Major UX differentiator

**Reference**: [docs/roadmaps/BETA3_ROADMAP.md](docs/roadmaps/BETA3_ROADMAP.md)

---

## Track 2: Advanced Fingerprint Features - 🎨 P1 HIGH VALUE

**Priority**: High value, but can run parallel to MSE work
**Status**: 🟢 Phase 1 Complete → Phase 2 ready
**Effort**: 12-18 weeks for full system
**Impact**: Revolutionary music discovery and adaptive processing

### Completed: Phase 1 - Core Integration ✅

**Date**: October 27, 2025
**Achievement**: 25D fingerprints now drive adaptive processing

**What Was Built**:
- ContentAnalyzer extracts 25D fingerprints (frequency, dynamics, temporal, spectral, harmonic, variation, stereo)
- AdaptiveTargetGenerator uses fingerprints for intelligent parameter selection
- Validated on synthetic + real audio
- 100% backward compatible

**Intelligent Processing Enabled**:
1. **Frequency-aware EQ** (7D): Precise bass/mid/treble adjustments based on actual distribution
2. **Dynamics-aware compression** (3D): Respects high DR, detects brick-walled material
3. **Temporal-aware processing** (4D): Preserves transients and rhythm
4. **Harmonic-aware intensity** (3D): Gentle on vocals, aggressive on percussion
5. **Stereo-aware width** (2D): Expands narrow mixes, checks phase correlation
6. **Variation-aware dynamics** (3D): Preserves intentional loudness variation

**Reference**: [docs/completed/FINGERPRINT_CORE_INTEGRATION.md](docs/completed/FINGERPRINT_CORE_INTEGRATION.md)

### Phase 2: Similarity Graph System (Next)

**Goal**: Build music similarity graph for cross-genre discovery

**Components**:

1. **Database & Storage** (1 week)
   - Add `track_fingerprints` table to schema
   - Fingerprint repository (CRUD)
   - Library scanner integration (extract fingerprints during scan)

2. **Distance Calculation** (2 weeks)
   - Weighted Euclidean distance (25D space)
   - Normalize dimensions for fair comparison
   - Distance calculation API

3. **Graph Construction** (2 weeks)
   - K-nearest neighbors graph (k=10-20)
   - Efficient graph storage
   - Query optimization

4. **Similarity API** (1 week)
   - `GET /api/tracks/{id}/similar` - Find similar tracks
   - `GET /api/tracks/cluster` - Graph-based clustering
   - Distance-based recommendations

5. **Frontend Integration** (1 week)
   - "Similar Tracks" section
   - Visual similarity graph
   - Cross-genre discovery UI

**Deliverable**: "Find songs like this" feature with acoustic similarity

**Estimated Effort**: 7 weeks

### Phase 3: Continuous Enhancement Space (Future)

**Goal**: Replace discrete presets with continuous parameter interpolation

**Concept**:
```
Current: 5 discrete presets (Adaptive, Gentle, Warm, Bright, Punchy)
Future: Infinite positions in 25D enhancement space

User can:
- Interpolate between any two tracks' characteristics
- Create custom enhancement profiles
- Real-time parameter adaptation
- Section-aware processing (verse vs chorus)
```

**Estimated Effort**: 6-8 weeks

**Reference**: [docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md](docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md)

---

## Track 3: Architecture Cleanup - 🧹 P1 TECH DEBT

**Priority**: Important for maintainability, not blocking features
**Status**: 🔴 Identified, not started
**Effort**: 1-2 weeks
**Impact**: Cleaner codebase, easier maintenance

### Identified Redundancies

Now that 25D fingerprints drive all processing, we have redundant components:

1. **SpectrumMapper** (in HybridProcessor)
   - **Issue**: Calculates "spectrum position" from basic analysis
   - **Redundant With**: Fingerprint-driven target generation
   - **Action**: Remove or consolidate into AdaptiveTargetGenerator

2. **Basic content analysis heuristics**
   - **Issue**: Simple if/else rules based on spectral centroid
   - **Redundant With**: Fingerprint's 7D frequency distribution
   - **Action**: Deprecate simple rules, keep only fingerprint path

3. **Genre-based processing profiles**
   - **Issue**: May be redundant with fingerprint-driven adaptation
   - **Keep or Remove?**: TBD - may still provide genre-specific "character"

### Cleanup Plan

**Phase 1: Analysis** (2 days)
- Audit all processing paths
- Identify redundant code
- Measure impact of removing each component

**Phase 2: Refactoring** (3-5 days)
- Remove SpectrumMapper or consolidate
- Deprecate simple heuristics
- Update tests

**Phase 3: Validation** (2-3 days)
- Ensure no regressions
- Performance testing
- Compare before/after output quality

**Total Effort**: 1-2 weeks

**When**: After MSE streaming is complete (don't block P0)

---

## 🎯 Beta.3 Release Criteria

Beta.3 can be released when:

1. ✅ MSE-based progressive streaming implemented
2. ✅ Preset switching < 100ms latency
3. ✅ Multi-tier buffer fully utilized
4. ✅ Works on Chrome/Firefox/Edge
5. ✅ No critical bugs
6. ✅ All Beta.2 features still working
7. ✅ Desktop binaries built for all platforms
8. ✅ Documentation updated

**Target Release**: 2-3 weeks after Beta.2 (mid-November 2025)

---

## 📊 Development Timeline

### Immediate Focus (Next 2-3 Weeks)

**Primary**: MSE Progressive Streaming (Track 1)
- Week 1: Backend chunk API + MSE prototyping
- Week 2: Frontend MSEPlayer + buffer integration
- Week 3: Testing, optimization, Beta.3 release

**Parallel** (if resources available): Fingerprint Phase 2 planning
- Database schema design
- Distance metric research

### Short Term (1-2 Months)

1. ✅ Beta.3 released with MSE streaming
2. 🎨 Fingerprint similarity graph (Phase 2)
   - Database integration
   - Distance calculation
   - "Find similar tracks" feature
3. 🧹 Architecture cleanup
   - Remove redundancies
   - Consolidate processing logic

### Medium Term (3-6 Months)

1. 🎨 Continuous enhancement space (Fingerprint Phase 3)
   - Interpolation between audio characteristics
   - Custom enhancement profiles
   - Real-time adaptation
2. 🚀 Beta.4+ planning
   - User feedback integration
   - Additional features
   - Performance optimization

---

## 🎨 Long-Term Vision (6-12 Months)

### Revolutionary Features Enabled by 25D System

1. **"Find songs like this"** - Cross-genre acoustic similarity
2. **Intelligent playlists** - Flow from track to track based on acoustic similarity
3. **Dynamic processing** - Adapt enhancement in real-time based on section analysis
4. **User learning** - Learn user preferences in 25D space
5. **Enhancement marketplace** - Share custom enhancement profiles
6. **A/B testing** - Compare enhancement strategies quantitatively

### Technical Foundation

- ✅ 25D fingerprint extraction (Phase 1 complete)
- 🟡 Similarity graph (Phase 2 in progress)
- 🔴 Continuous parameter space (Phase 3 planned)
- 🔴 Real-time adaptation (Phase 4 future)

---

## 📋 Priority Matrix

### P0 - Critical (Must Do Now)

1. **MSE Progressive Streaming** - Blocking user experience

### P1 - High Priority (Next)

1. **Fingerprint Similarity Graph** - High value, revolutionary feature
2. **Architecture Cleanup** - Tech debt, improves maintainability
3. **Desktop Binary Fixes** - Distribution reliability

### P2 - Medium Priority (Soon)

1. **UI/UX Polish** - Artwork, controls, loading states
2. **Additional Presets** - User-customizable presets
3. **Performance Optimization** - Further speedups

### P3 - Nice to Have (Later)

1. **Advanced Features** - Lyrics, visualizations, smart shuffle
2. **Documentation** - Expanded user/developer guides
3. **API Expansion** - Public API for third-party integrations

---

## 🔄 Process Notes

### Development Philosophy

1. **Move fast, clean up later** - Don't let perfect be the enemy of good
2. **Validate before optimizing** - Test with real audio, get user feedback
3. **Maintain backward compatibility** - Existing code should keep working
4. **Document as you go** - But don't block implementation

### When to Take Breaks for Cleanup

- After major milestones (e.g., post-Beta.3 release)
- When redundancies surface (like SpectrumMapper now)
- When tech debt starts slowing development
- Not during P0 critical work

### Quality Gates

- All tests must pass
- No critical regressions
- Real audio validation required
- Performance benchmarks checked

---

## 📚 Key Documents

### Completed Work
- [docs/completed/FINGERPRINT_CORE_INTEGRATION.md](docs/completed/FINGERPRINT_CORE_INTEGRATION.md) - 25D system integration
- [docs/sessions/oct26_beta2_release/](docs/sessions/oct26_beta2_release/) - Beta.2 release notes
- [docs/sessions/oct26_fingerprint_system/](docs/sessions/oct26_fingerprint_system/) - Fingerprint research

### Active Plans
- [docs/roadmaps/BETA3_ROADMAP.md](docs/roadmaps/BETA3_ROADMAP.md) - MSE streaming plan
- [docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md](docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md) - Full fingerprint vision
- [docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md](docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md) - Technical details

### Known Issues
- [BETA1_KNOWN_ISSUES.md](BETA1_KNOWN_ISSUES.md) - Resolved in Beta.2
- [docs/troubleshooting/PRESET_SWITCHING_LIMITATION.md](docs/troubleshooting/PRESET_SWITCHING_LIMITATION.md) - MSE will fix

---

## 🎯 Current Action Items

### This Week (October 27 - November 2)

**Priority 1**: MSE Progressive Streaming
- [ ] Backend chunk streaming API implementation
- [ ] Metadata endpoint
- [ ] MSE research and prototyping

**Priority 2**: Fingerprint Phase 2 Planning
- [ ] Database schema design
- [ ] Distance metric research
- [ ] API endpoint design

**Parallel**: Documentation
- [x] Fingerprint integration documentation
- [ ] Update CLAUDE.md with fingerprint usage
- [ ] MSE implementation guide

### Next Week (November 3-9)

**Priority 1**: MSE Continued
- [ ] Frontend MSEPlayer implementation
- [ ] Buffer integration
- [ ] Initial testing

---

## 🎊 Recent Wins

- ✅ **25D Fingerprint Integration** (Oct 27) - Revolutionary content-aware processing
- ✅ **Beta.2 Release** (Oct 26) - All critical bugs fixed, production quality
- ✅ **Performance Optimization** (Oct 24) - 52.8x real-time speed with Numba+vectorization
- ✅ **Multi-Tier Buffer** (Oct 25) - L1/L2/L3 caching system working

---

**Status**: Three active tracks, clear priorities, ready to execute
**Next Milestone**: Beta.3 with MSE streaming (2-3 weeks)
**Long-Term Vision**: Revolutionary music discovery powered by 25D fingerprints
