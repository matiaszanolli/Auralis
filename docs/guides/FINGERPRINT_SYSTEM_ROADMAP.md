# Audio Fingerprint Graph System: Implementation Roadmap

**Date**: October 26, 2025
**Goal**: Build music similarity graph from acoustic fingerprints
**Vision**: "Calculate songs related by 'musicality' and measure accuracy vs user preferences"

---

## Implementation Phases

### Phase 1: Fingerprint Extraction (Foundation)

**Goal**: Extract 25D acoustic fingerprint from any audio file

**Components**:

1. **Frequency Distribution Analyzer** (7D)
   - Already have basic version (sub-bass, bass, low-mid, mid, upper-mid, presence, air)
   - Enhance with more precise FFT analysis
   - Add frequency masking consideration
   - File: `auralis/analysis/fingerprint/frequency_analyzer.py`

2. **Dynamics Analyzer** (2D)
   - Already have: LUFS, crest factor
   - Enhance: Use proper ITU-R BS.1770-4 LUFS (not RMS estimate)
   - File: `auralis/analysis/fingerprint/dynamics_analyzer.py`

3. **Temporal/Rhythmic Analyzer** (4D) ← NEW
   - Tempo detection (BPM)
   - Rhythm stability (beat consistency)
   - Transient density (drum/percussion detection)
   - Silence ratio (space in music)
   - Library: `librosa` for tempo/beat tracking
   - File: `auralis/analysis/fingerprint/temporal_analyzer.py`

4. **Spectral Character Analyzer** (3D) ← NEW
   - Spectral centroid (brightness)
   - Spectral rolloff (high-frequency content)
   - Spectral flatness (noise vs tonal)
   - Already available in librosa
   - File: `auralis/analysis/fingerprint/spectral_analyzer.py`

5. **Harmonic Content Analyzer** (3D) ← NEW
   - Harmonic ratio (tonal vs atonal)
   - Pitch stability (in-tune vs dissonant)
   - Chroma energy (tonal complexity)
   - Library: `librosa` for harmonic analysis
   - File: `auralis/analysis/fingerprint/harmonic_analyzer.py`

6. **Dynamic Variation Analyzer** (3D) ← NEW
   - Dynamic range variation over time
   - Loudness variation std dev
   - Peak consistency
   - File: `auralis/analysis/fingerprint/variation_analyzer.py`

7. **Stereo Field Analyzer** (2D)
   - Stereo width
   - Phase correlation
   - Already implemented in `auralis/analysis/phase_correlation.py`
   - File: `auralis/analysis/fingerprint/stereo_analyzer.py`

**Deliverable**: `AudioFingerprintAnalyzer` class that returns 25D vector

**Estimated Effort**: 2-3 weeks

---

### Phase 2: Database & Storage

**Goal**: Store fingerprints efficiently, query quickly

**Components**:

1. **Database Schema**
   - `track_fingerprints` table (25 columns + metadata)
   - Indexes on frequently queried dimensions
   - File: `auralis/library/migrations/add_fingerprints.py`

2. **Fingerprint Repository**
   - CRUD operations for fingerprints
   - Batch insert/update for library scanning
   - File: `auralis/library/repositories/fingerprint_repository.py`

3. **Library Scanner Integration**
   - Extend existing scanner to extract fingerprints
   - Progress tracking for large libraries
   - Background processing (don't block UI)
   - File: `auralis/library/scanner.py` (extend)

**Deliverable**: Fingerprints stored in database, accessible via repository

**Estimated Effort**: 1 week

---

### Phase 3: Distance Calculation & Graph Construction

**Goal**: Calculate pairwise distances, build similarity graph

**Components**:

1. **Distance Calculator**
   - Weighted Euclidean distance in 25D space
   - Configurable dimension weights
   - Normalization of dimensions to 0-1 scale
   - File: `auralis/analysis/similarity/distance_calculator.py`

2. **Graph Builder**
   - Threshold-based edge creation
   - Efficient all-pairs distance computation
   - Option: Use approximate nearest neighbors (FAISS) for large libraries
   - File: `auralis/analysis/similarity/graph_builder.py`

3. **Graph Storage**
   - SQLite table: `song_similarities` (pairwise distances)
   - Cache in-memory graph using NetworkX
   - Option: Export to graph database (Neo4j) for very large libraries
   - File: `auralis/library/repositories/similarity_repository.py`

**Deliverable**: Similarity graph for entire library

**Estimated Effort**: 1-2 weeks

---

### Phase 4: Recommendation Engine

**Goal**: Query graph for similar songs, return ranked recommendations

**Components**:

1. **Similarity Query Engine**
   - Find K nearest neighbors in fingerprint space
   - Rank by distance/similarity score
   - Filter by user preferences (optional)
   - File: `auralis/analysis/similarity/recommendation_engine.py`

2. **API Endpoints**
   - `GET /api/recommendations/{track_id}` - Get similar songs
   - `GET /api/recommendations/batch` - Get recommendations for multiple tracks
   - `POST /api/recommendations/feedback` - User feedback on recommendation
   - File: `auralis-web/backend/routers/recommendations.py`

3. **User Feedback Storage**
   - Table: `recommendation_feedback` (liked, played, rating)
   - Track which recommendations users accept/reject
   - File: `auralis/library/repositories/feedback_repository.py`

**Deliverable**: Working recommendation API

**Estimated Effort**: 1 week

---

### Phase 5: Validation & Tuning

**Goal**: Measure accuracy, tune dimension weights

**Components**:

1. **Accuracy Metrics**
   - Precision @ K (how many of top K are liked?)
   - Distance-preference correlation (do closer songs get liked more?)
   - Coverage (what % of library gets recommended?)
   - File: `auralis/analysis/similarity/metrics.py`

2. **Dimension Weight Tuning**
   - Learn optimal weights from user feedback
   - Gradient descent on user preference data
   - Personalized weights per user
   - File: `auralis/analysis/similarity/weight_tuner.py`

3. **A/B Testing Framework**
   - Compare acoustic similarity vs genre-based recommendations
   - Measure which gets higher acceptance rate
   - File: `auralis/analysis/similarity/ab_testing.py`

**Deliverable**: Validated system with measured accuracy

**Estimated Effort**: 2 weeks

---

### Phase 6: Visualization & UI

**Goal**: User-facing features to explore music space

**Components**:

1. **2D Music Space Visualization**
   - t-SNE or UMAP projection of 25D fingerprints
   - Interactive scatter plot (click to play)
   - Color by genre/era/user rating
   - Library: `scikit-learn` for dimensionality reduction, `plotly` for interactive plots
   - File: `auralis-web/frontend/src/components/MusicSpaceVisualization.tsx`

2. **Similar Songs UI**
   - "Songs like this" section in track details
   - Similarity score display
   - "Why is this similar?" explanation (dimension breakdown)
   - File: `auralis-web/frontend/src/components/SimilarSongsPanel.tsx`

3. **Discovery Mode**
   - "Explore music space" feature
   - Random walk through graph
   - "Find something new based on this"
   - File: `auralis-web/frontend/src/components/DiscoveryMode.tsx`

**Deliverable**: User-facing recommendation features

**Estimated Effort**: 2-3 weeks

---

### Phase 7: Enhancement Integration

**Goal**: Recommend enhancements based on similar songs user likes

**Components**:

1. **Enhancement Target Selection**
   - User: "I like this song, enhance my library to sound like it"
   - Framework: Find user's songs closest to target in fingerprint space
   - Apply enhancement vector to move toward target
   - File: `auralis/analysis/similarity/enhancement_recommender.py`

2. **Batch Enhancement**
   - "Enhance all my thrash metal to sound like Steven Wilson"
   - Find all tracks similar to Exodus original
   - Apply sub-bass power enhancement pattern
   - File: `auralis/processing/batch_enhancement.py`

3. **Smart Preset Selection**
   - Instead of manual preset choice, recommend based on similar tracks
   - "Songs like this were enhanced with pattern X"
   - File: `auralis/analysis/similarity/preset_recommender.py`

**Deliverable**: Integrated recommendation + mastering workflow

**Estimated Effort**: 1-2 weeks

---

## Technology Stack

### Core Libraries

```python
# Audio analysis
librosa >= 0.10.0        # Tempo, rhythm, spectral, harmonic features
soundfile >= 0.12.0      # Audio I/O
numpy >= 1.24.0          # Numerical operations
scipy >= 1.10.0          # Signal processing

# Graph & similarity
networkx >= 3.0          # Graph construction and queries
scikit-learn >= 1.3.0    # Distance metrics, dimensionality reduction

# Optional (for large libraries)
faiss-cpu >= 1.7.0       # Approximate nearest neighbors (fast!)
umap-learn >= 0.5.0      # Better dimensionality reduction than t-SNE

# Database
sqlalchemy >= 2.0.0      # ORM
sqlite3                  # Database (built-in)

# Optimization
numba >= 0.58.0          # JIT compilation for distance calculations
```

### Frontend Libraries

```typescript
// Visualization
plotly.js >= 2.27.0      // Interactive charts
d3.js >= 7.8.0           // Custom visualizations

// UI
react >= 18.2.0
material-ui >= 5.14.0
```

---

## Performance Considerations

### For Large Libraries (10k+ tracks)

**Problem**: 10k tracks = 50M pairwise distances = computationally expensive

**Solutions**:

1. **Approximate Nearest Neighbors (ANN)**
   - Use FAISS library
   - Build index: O(n log n)
   - Query K neighbors: O(log n)
   - Trade-off: ~95% accuracy, 100x speedup

2. **Sparse Graph**
   - Don't store all pairwise distances
   - Only store K nearest neighbors per song
   - Threshold: Only edges with similarity > 0.7
   - Reduces storage from O(n²) to O(nk)

3. **Batch Processing**
   - Process fingerprint extraction in background
   - Update graph incrementally (new songs only)
   - Don't recalculate existing similarities

4. **Caching**
   - Cache frequent queries (recommendations for popular songs)
   - Precompute top 100 recommendations per song
   - Update cache nightly

---

## Validation Plan

### Experiment 1: Cross-Genre Similarity

**Hypothesis**: Acoustic similarity finds connections genre tags miss

**Method**:
1. Cluster songs by fingerprint (no genre info)
2. Count mixed-genre clusters
3. Measure cluster purity

**Success Criteria**:
- At least 30% of clusters have mixed genres
- Examples: Steven Wilson + Enhanced Exodus in same cluster

---

### Experiment 2: Recommendation Accuracy

**Hypothesis**: Acoustic similarity predicts user preference better than genre tags

**Method**:
1. A/B test: 50% users get acoustic recommendations, 50% get genre-based
2. Measure acceptance rate (user plays recommended song)
3. Compare precision @ 10

**Success Criteria**:
- Acoustic recommendations: > 70% acceptance
- Genre-based recommendations: < 50% acceptance
- Acoustic wins by > 20 percentage points

---

### Experiment 3: Dimension Importance

**Hypothesis**: Frequency dimensions matter more than temporal dimensions for perceived similarity

**Method**:
1. Set all frequency weights to 0, keep only temporal
2. Measure recommendation accuracy
3. Compare to full fingerprint
4. Repeat for each dimension group

**Success Criteria**:
- Frequency-only: > 60% accuracy (good)
- Temporal-only: < 40% accuracy (weak)
- Confirms frequency is most important

---

## Milestones

### Milestone 1: Basic Fingerprint Extraction (Week 4)
- ✅ Extract 25D fingerprint from audio
- ✅ Store in database
- ✅ Tested on 100+ diverse tracks

### Milestone 2: Similarity Graph (Week 7)
- ✅ Calculate all pairwise distances
- ✅ Build graph with threshold
- ✅ Query K nearest neighbors

### Milestone 3: Recommendation API (Week 9)
- ✅ API endpoint working
- ✅ Returns ranked recommendations
- ✅ Tested on user library

### Milestone 4: Validation (Week 12)
- ✅ Accuracy > 70% precision @ 10
- ✅ User feedback collection working
- ✅ Dimension weights tuned

### Milestone 5: UI Integration (Week 16)
- ✅ "Similar songs" panel in track view
- ✅ Music space visualization
- ✅ User can explore recommendations

### Milestone 6: Enhancement Integration (Week 18)
- ✅ "Enhance like this song" feature
- ✅ Batch enhancement working
- ✅ Complete recommendation + mastering workflow

---

## Success Metrics

### Technical Metrics

```
Fingerprint extraction:
  - Speed: < 1 second per track (real-time factor > 100x)
  - Accuracy: Reproduce manual analysis within ±5%

Graph construction:
  - Build time: < 1 hour for 10k tracks
  - Query time: < 100ms for K=10 neighbors

Recommendation quality:
  - Precision @ 10: > 70%
  - Distance-preference correlation: r > 0.6
  - Coverage: > 80% of library gets recommended
```

### User Metrics

```
Engagement:
  - > 50% of users try recommendations
  - > 30% of users play recommended songs
  - > 20% of users use "enhance like this" feature

Satisfaction:
  - > 4.0 / 5.0 rating for recommendation quality
  - > 70% say "I discovered new music"
  - > 60% say "Recommendations sound similar"
```

---

## Next Steps (Immediate)

### Priority 1: Proof of Concept

**Goal**: Validate the concept with minimal implementation

**Tasks**:
1. Extract fingerprints from our 10 analyzed reference tracks
2. Calculate all pairwise distances
3. Verify predictions:
   - Steven Wilson 2024 ≈ Exodus Remaster (distance < 0.20)
   - Rush 1977 ≈ Rush 1989 (distance < 0.15)
   - Death Magnetic ≈ Dio 2005 (distance < 0.10)

**File**: `scripts/fingerprint_proof_of_concept.py`

**Estimated Effort**: 2-3 days

---

### Priority 2: Extend Fingerprint Analyzer

**Goal**: Implement missing dimensions (temporal, spectral, harmonic)

**Tasks**:
1. Add librosa dependency
2. Implement tempo/rhythm analyzer
3. Implement spectral analyzer
4. Implement harmonic analyzer
5. Test on diverse music (metal, classical, electronic)

**Files**:
- `auralis/analysis/fingerprint/__init__.py`
- `auralis/analysis/fingerprint/temporal_analyzer.py`
- `auralis/analysis/fingerprint/spectral_analyzer.py`
- `auralis/analysis/fingerprint/harmonic_analyzer.py`

**Estimated Effort**: 1 week

---

### Priority 3: Database Schema

**Goal**: Store fingerprints persistently

**Tasks**:
1. Create migration: `add_track_fingerprints.py`
2. Add `FingerprintRepository` class
3. Integrate with library scanner
4. Test on small library (100 tracks)

**Files**:
- `auralis/library/migrations/add_fingerprints.py`
- `auralis/library/repositories/fingerprint_repository.py`

**Estimated Effort**: 3-4 days

---

## Research Questions for Future

1. **Optimal Number of Dimensions**
   - Is 25D the right size?
   - Can we reduce to 15D without losing accuracy?
   - Which dimensions can be removed?

2. **Temporal vs Static Fingerprint**
   - Current: Static average over entire track
   - Alternative: Time-varying fingerprint (capture song structure)
   - Trade-off: Complexity vs information

3. **Genre Emergence**
   - Do genre clusters emerge naturally from fingerprints?
   - Can we auto-label genres from acoustic clusters?
   - Compare to human-assigned genre tags

4. **Cultural Differences**
   - Do different cultures/regions cluster differently?
   - Can we detect cultural fingerprints?
   - Example: Japanese city pop vs Western pop

5. **Evolution Over Time**
   - How do fingerprints change across decades?
   - Can we track loudness war in fingerprint space?
   - Visualize music evolution timeline

---

## Summary

**The Vision**:
> "Each song has a unique fingerprint in this multidimensional field, and in this way we can start working with graphs, calculating songs related by 'musicality' and measure how accurate is compared with what people actually wants to hear."

**The Implementation**:
1. Extract 25D acoustic fingerprint from every song
2. Build similarity graph (songs = nodes, acoustic distance = edges)
3. Recommend songs based on position in continuous space
4. Validate against user preferences
5. Tune dimension weights from feedback
6. Integrate with mastering (enhance toward similar songs user likes)

**The Killer Feature**:
- **Recommendation engine that UNDERSTANDS what music sounds like**
- NOT genre tags, NOT user behavior
- PURE acoustic similarity in continuous multi-dimensional space

**Timeline**: 18 weeks from start to full system

**Next Action**: Build proof of concept with our 10 reference tracks (2-3 days)

---

*Roadmap Date: October 26, 2025*
*Implementation Phase: Planning Complete, Ready to Build*
*Core Innovation: Music recommendation by acoustic fingerprint in continuous space*
