# Auralis Research Task List

This document tracks research tasks needed to strengthen the technical paper and advance the project scientifically.

---

## Phase 1: Paper Preparation (Weeks 1-4)

### 1.1 Create Figures and Diagrams

**Status**: Not started
**Priority**: High
**Estimated effort**: 10-15 hours

**Tasks**:
- [ ] **Figure 1**: System architecture diagram (Frontend → Backend → Processing pipeline)
  - Tools: draw.io, Lucidchart, or TikZ (LaTeX)
  - Style: IEEE paper standard (grayscale-friendly, clear labels)

- [ ] **Figure 2**: Chunk processing timeline
  - X-axis: Time (0-1,200ms)
  - Y-axis: Processing stages (loading, features, EQ, dynamics, limiting, writing)
  - Visualize component breakdown from Appendix D.2

- [ ] **Figure 3**: Cache hit rate over time (1-hour session simulation)
  - X-axis: Time (minutes)
  - Y-axis: Hit rate (%)
  - Lines: L1, L2, L3, Overall
  - Show learning effect (hit rate increases over time)

- [ ] **Figure 4**: Preset switching latency distribution
  - Box plot: L1 hit, L2 hit, L3 hit, Cache miss
  - Median, quartiles, outliers
  - Highlight <100ms target threshold

- [ ] **Figure 5**: WebM encoding quality vs. bitrate
  - X-axis: Bitrate (96, 128, 192, 256 kbps)
  - Y-axis: File size (KB) and Quality score (MUSHRA estimate)
  - Dual Y-axis chart

- [ ] **Figure 6**: Branch prediction accuracy learning curve
  - X-axis: Number of preset switches
  - Y-axis: Prediction accuracy (%)
  - Show improvement from 35% → 68%

- [ ] **Figure 7**: Real-time factor comparison
  - Bar chart: Auralis (36.6x), Matchering (baseline), DAW plugins (hypothetical)
  - Error bars if multiple runs available

**Deliverables**: 7 publication-quality figures in PDF/PNG format

---

### 1.2 Collect Benchmark Data

**Status**: Partial (preliminary benchmarks exist)
**Priority**: High
**Estimated effort**: 8-12 hours

**Tasks**:
- [ ] **WebM encoding benchmark** (10+ runs per bitrate)
  - Bitrates: 96, 128, 192, 256 kbps
  - Metrics: File size, encoding time, quality estimate
  - Test tracks: 5+ diverse genres (30s chunks)
  - Script: `research/data/benchmark_webm_encoding.py`

- [ ] **HybridProcessor benchmark** (5+ runs per track)
  - Tracks: Iron Maiden (current), Rush, Exodus, Classical, Jazz
  - Metrics: Total time, component breakdown, real-time factor
  - Script: `research/data/benchmark_hybrid_processor.py`

- [ ] **Cache performance simulation** (100+ hours simulated listening)
  - User patterns: Exploratory (3-4 presets/track), Settled (1-2 presets/track)
  - Metrics: Hit rates (L1/L2/L3), average latency, memory usage
  - Script: `research/data/simulate_cache_performance.py`

- [ ] **Branch prediction accuracy** (1000+ preset switches)
  - Simulate various user behaviors (consistent, random, exploratory)
  - Metrics: Accuracy vs. switch count, confusion matrix
  - Script: `research/data/benchmark_branch_prediction.py`

**Deliverables**: CSV/JSON data files + summary statistics

---

### 1.3 Write Benchmark Scripts

**Status**: Not started
**Priority**: Medium
**Estimated effort**: 12-16 hours

**Tasks**:
- [ ] `research/data/benchmark_webm_encoding.py`
  - Load test audio files
  - Encode with multiple bitrates
  - Measure time, file size
  - Output: `webm_encoding_results.csv`

- [ ] `research/data/benchmark_hybrid_processor.py`
  - Load diverse test tracks
  - Process with multiple presets
  - Profile component timing
  - Output: `processing_performance.csv`

- [ ] `research/data/simulate_cache_performance.py`
  - Monte Carlo simulation (1000+ sessions)
  - Model user behavior patterns
  - Track cache hits/misses
  - Output: `cache_simulation_results.csv`

- [ ] `research/data/benchmark_branch_prediction.py`
  - Replay real preset switch logs (if available)
  - Or simulate user patterns
  - Measure prediction accuracy over time
  - Output: `branch_prediction_accuracy.csv`

- [ ] `research/data/run_all_benchmarks.sh`
  - Master script to run all benchmarks
  - Generate summary report

**Deliverables**: 5 Python scripts + shell script

---

### 1.4 Format Paper for Submission

**Status**: Draft complete (Markdown)
**Priority**: Medium
**Estimated effort**: 8-10 hours

**Tasks**:
- [ ] Convert Markdown to LaTeX (IEEE double-column format)
  - Use `pandoc` or manual conversion
  - Template: IEEE Conference/Journal LaTeX class

- [ ] Integrate figures
  - Convert to PDF/EPS for LaTeX
  - Write captions with proper citations

- [ ] Format references (BibTeX)
  - Cite Matchering, MSE spec, ITU-R BS.1770-4, etc.
  - Ensure consistent citation style

- [ ] Proofread and polish
  - Grammar, spelling, technical accuracy
  - Consistency in terminology
  - Remove informal language

- [ ] Prepare supplementary materials
  - Code repository link
  - Demo video (optional)
  - Dataset description

**Deliverables**: `auralis_paper.tex`, `auralis_paper.pdf`, `references.bib`

---

## Phase 2: Perceptual Validation (Weeks 5-8)

### 2.1 MUSHRA Listening Test

**Status**: Not started
**Priority**: High (critical for paper acceptance)
**Estimated effort**: 30-40 hours (including participant recruitment)

**Objective**: Validate that chunked processing is perceptually transparent compared to full-file processing.

**Design**:
- **Test type**: MUSHRA (Multiple Stimuli with Hidden Reference and Anchor)
- **Participants**: 15-20 trained listeners (musicians, audio engineers)
- **Tracks**: 10 diverse test cases (various genres, dynamic ranges)
- **Conditions**:
  1. Reference (unprocessed)
  2. Full-file processing (Warm preset)
  3. Chunked processing (Warm preset)
  4. Low-quality anchor (heavily compressed)
  5. Hidden reference (duplicate of condition 1)
- **Rating scale**: 0-100 (Bad to Excellent)
- **Hypothesis**: No significant difference between conditions 2 and 3 (p > 0.05)

**Tasks**:
- [ ] Prepare test stimuli (10 tracks × 5 conditions = 50 audio files)
- [ ] Set up MUSHRA interface (webMUSHRA or custom)
- [ ] Recruit participants (via university, audio forums)
- [ ] Conduct listening sessions (1-2 hours per participant)
- [ ] Analyze results (ANOVA, post-hoc tests)
- [ ] Write results section for paper

**Deliverables**: MUSHRA results data, statistical analysis, updated paper section

---

### 2.2 Preset Switching Latency Study

**Status**: Not started
**Priority**: Medium
**Estimated effort**: 15-20 hours

**Objective**: Determine perceptual threshold for "instant" preset switching.

**Design**:
- **Test type**: Paired comparison (Which is faster?)
- **Participants**: 10-15 casual listeners (non-experts)
- **Latencies tested**: 10ms, 50ms, 100ms, 200ms, 500ms
- **Question**: "Which preset switch felt instant?"
- **Hypothesis**: <100ms perceived as instant by 80%+ of users

**Tasks**:
- [ ] Build web interface for latency testing
- [ ] Simulate varying latencies (artificial delays)
- [ ] Recruit participants
- [ ] Analyze results (threshold detection)
- [ ] Update paper with findings

**Deliverables**: Latency threshold data, user preference statistics

---

### 2.3 Long-Term Listening Fatigue Study

**Status**: Not started
**Priority**: Low
**Estimated effort**: 20-30 hours (longitudinal study)

**Objective**: Ensure Auralis processing doesn't cause listening fatigue over extended sessions.

**Design**:
- **Test type**: Longitudinal survey
- **Participants**: 5-10 daily users (beta testers)
- **Duration**: 2 weeks
- **Metrics**: Self-reported fatigue, preference ratings, listening duration
- **Hypothesis**: No increase in fatigue vs. unprocessed audio

**Tasks**:
- [ ] Design survey instrument
- [ ] Recruit beta testers
- [ ] Collect daily logs
- [ ] Analyze trends
- [ ] Report findings

**Deliverables**: Fatigue study results, qualitative feedback

---

## Phase 3: Machine Learning Enhancements (Weeks 9-16)

### 3.1 Deep Learning Genre Classifier

**Status**: Not started
**Priority**: Medium
**Estimated effort**: 40-60 hours

**Objective**: Replace hand-crafted genre heuristics with learned embeddings.

**Approach**:
- Use pre-trained models: YAMNet (Google), OpenL3, or MusicNN
- Fine-tune on music dataset (GTZAN, Million Song Dataset)
- Extract embeddings for preset selection

**Tasks**:
- [ ] Survey existing models (YAMNet, OpenL3, MusicNN)
- [ ] Download pre-trained weights
- [ ] Implement embedding extraction
- [ ] Train classifier (genre → preset mapping)
- [ ] Evaluate accuracy on test set
- [ ] Integrate into Auralis pipeline

**Deliverables**: `ml_genre_classifier.py`, trained model weights, accuracy report

---

### 3.2 Reinforcement Learning for Preset Selection

**Status**: Not started
**Priority**: Low (research exploration)
**Estimated effort**: 60-80 hours

**Objective**: Automatically select presets based on user preferences (learn from interactions).

**Approach**:
- **Agent**: Preset selector
- **State**: Audio features (25D fingerprint) + user history
- **Action**: Select preset {Adaptive, Gentle, Warm, Bright, Punchy}
- **Reward**: User feedback (skip track = -1, explicit rating = +1, repeat listen = +0.5)
- **Algorithm**: Deep Q-Network (DQN) or Policy Gradient

**Tasks**:
- [ ] Design RL environment (OpenAI Gym-style)
- [ ] Collect user interaction logs (or simulate)
- [ ] Implement DQN/Policy Gradient
- [ ] Train agent (1000+ episodes)
- [ ] Evaluate against rule-based baseline
- [ ] Write research paper on RL-based mastering

**Deliverables**: RL agent, training code, results paper (separate publication)

---

### 3.3 Generative Preset Interpolation

**Status**: Not started
**Priority**: Low (exploratory)
**Estimated effort**: 40-50 hours

**Objective**: Smooth transitions between presets via latent space interpolation.

**Approach**:
- Train Variational Autoencoder (VAE) on preset parameter vectors
- Interpolate in latent space (z-space)
- Decode to smooth parameter transitions

**Tasks**:
- [ ] Collect preset parameter vectors (100+ combinations)
- [ ] Train VAE (encoder-decoder architecture)
- [ ] Implement latent space interpolation
- [ ] Evaluate perceptual smoothness
- [ ] Integrate into Auralis (crossfade between presets)

**Deliverables**: VAE model, interpolation demo, updated paper section

---

## Phase 4: System Enhancements (Weeks 17-24)

### 4.1 iOS Native App (Managed Media Source)

**Status**: Not started
**Priority**: High (user demand)
**Estimated effort**: 80-120 hours

**Objective**: Enable MSE-like functionality on iOS Safari using Managed Media Source (MMS).

**Tasks**:
- [ ] Research MMS API (HLS-compatible chunks)
- [ ] Convert WebM chunks to HLS (m3u8 playlists)
- [ ] Implement MMS player in iOS Safari
- [ ] Test on iPhone/iPad devices
- [ ] Measure latency, compare to Android MSE

**Deliverables**: iOS-compatible streaming, performance report

---

### 4.2 Android/iOS Native Apps

**Status**: Not started
**Priority**: Medium
**Estimated effort**: 100-150 hours

**Objective**: Build native mobile apps for better performance and UX.

**Tasks**:
- [ ] Design mobile UI (React Native or Flutter)
- [ ] Implement native audio processing (C++ core library)
- [ ] Build Android app (Kotlin + JNI)
- [ ] Build iOS app (Swift + C++ bridge)
- [ ] Test on various devices
- [ ] Publish to Google Play / App Store

**Deliverables**: Android APK, iOS IPA, published apps

---

### 4.3 Distributed Caching (Multi-Device Sync)

**Status**: Not started
**Priority**: Low (nice-to-have)
**Estimated effort**: 60-80 hours

**Objective**: Share cache entries across devices for seamless multi-device listening.

**Approach**:
- Cloud storage (AWS S3, Google Cloud Storage)
- Cache sync on device login
- Conflict resolution (last-write-wins or version vectors)

**Tasks**:
- [ ] Design cache sync protocol
- [ ] Implement cloud storage backend
- [ ] Build sync client (background service)
- [ ] Test multi-device scenarios
- [ ] Measure overhead (bandwidth, latency)

**Deliverables**: Distributed cache implementation, performance analysis

---

## Phase 5: Integration with Music Recommendation (Weeks 25-32)

### 5.1 Similarity-Based Discovery

**Status**: Not started (25D fingerprint ready)
**Priority**: Medium
**Estimated effort**: 40-60 hours

**Objective**: "Find tracks like this" based on acoustic fingerprint distance.

**Approach**:
- Compute pairwise distances (Euclidean, cosine similarity)
- Build k-NN index (Annoy, FAISS)
- Recommend top-k similar tracks

**Tasks**:
- [ ] Extract 25D fingerprints for all library tracks
- [ ] Build similarity index (Annoy or FAISS)
- [ ] Implement recommendation endpoint
- [ ] Evaluate relevance (user study)
- [ ] Integrate into UI ("More Like This" button)

**Deliverables**: Similarity search implementation, relevance metrics

---

### 5.2 Cross-Genre Recommendation

**Status**: Not started
**Priority**: Low (research exploration)
**Estimated effort**: 50-70 hours

**Objective**: Discover music from different genres with similar acoustic characteristics.

**Approach**:
- Use 25D fingerprint (genre-agnostic)
- Filter recommendations to exclude same genre
- Rank by acoustic similarity

**Tasks**:
- [ ] Build cross-genre index
- [ ] Implement recommendation algorithm
- [ ] User study: "Surprising but relevant" recommendations
- [ ] Write research paper (ISMIR submission)

**Deliverables**: Cross-genre recommender, user study results, ISMIR paper

---

### 5.3 Mood-Based Auto-Playlists

**Status**: Not started
**Priority**: Medium
**Estimated effort**: 30-40 hours

**Objective**: Generate playlists based on mood dimensions (energy, brightness, dynamics).

**Approach**:
- Map 25D fingerprint to mood dimensions (valence, arousal)
- Cluster tracks by mood
- Generate playlists ("Energetic Workout", "Calm Focus")

**Tasks**:
- [ ] Train mood classifier (Russell's circumplex model)
- [ ] Cluster tracks by mood
- [ ] Implement playlist generator
- [ ] User testing (preference ratings)

**Deliverables**: Mood-based playlist feature, user preference data

---

## Phase 6: Paper Submission and Publication (Weeks 33-40)

### 6.1 Select Target Venue

**Status**: Not started
**Priority**: High
**Estimated effort**: 2-4 hours (research deadlines)

**Options**:
1. **AES Convention** (Audio Engineering Society)
   - Deadline: Rolling (3-6 months before convention)
   - Format: 4-6 pages (AES format)
   - Audience: Audio engineers, acousticians

2. **ACM Multimedia**
   - Deadline: April (for October conference)
   - Format: 8-12 pages (ACM format)
   - Audience: Multimedia researchers, computer scientists

3. **IEEE ICASSP** (International Conference on Acoustics, Speech, and Signal Processing)
   - Deadline: October (for April conference)
   - Format: 4-6 pages (IEEE format)
   - Audience: Signal processing researchers

4. **ISMIR** (International Society for Music Information Retrieval)
   - Deadline: April (for November conference)
   - Format: 6 pages (ISMIR format)
   - Audience: MIR researchers, music technologists

**Tasks**:
- [ ] Review venue scopes and deadlines
- [ ] Decide on primary target (AES or ACM Multimedia)
- [ ] Prepare paper according to format
- [ ] Submit before deadline

**Deliverables**: Submitted paper, confirmation email

---

### 6.2 Respond to Reviews

**Status**: Pending submission
**Priority**: High (after submission)
**Estimated effort**: 20-40 hours

**Tasks**:
- [ ] Receive reviewer feedback (typically 3 reviewers)
- [ ] Address comments point-by-point
- [ ] Revise paper (fix issues, clarify ambiguities)
- [ ] Resubmit or submit to alternative venue if rejected

**Deliverables**: Revised paper, response letter

---

### 6.3 Prepare Presentation

**Status**: Not started
**Priority**: Medium (if accepted)
**Estimated effort**: 10-15 hours

**Tasks**:
- [ ] Create slides (Beamer LaTeX or PowerPoint)
- [ ] Prepare demo video (3-5 minutes)
- [ ] Rehearse presentation (15-20 minutes)
- [ ] Travel to conference (if in-person)

**Deliverables**: Presentation slides, demo video, conference talk

---

## Summary of Effort Estimates

| Phase | Priority | Estimated Effort |
|-------|----------|------------------|
| **1. Paper Preparation** | High | 38-53 hours |
| **2. Perceptual Validation** | High | 65-90 hours |
| **3. ML Enhancements** | Medium | 140-190 hours |
| **4. System Enhancements** | Medium | 240-350 hours |
| **5. Music Recommendation** | Medium | 120-170 hours |
| **6. Publication** | High | 32-59 hours |
| **Total** | | **635-912 hours** |

**Rough timeline**: 6-12 months (depending on parallel work)

---

## Prioritization for Immediate Paper Submission

**High priority (next 4-8 weeks)**:
1. Create figures (10-15 hours)
2. Collect benchmark data (8-12 hours)
3. Write benchmark scripts (12-16 hours)
4. Format paper for LaTeX (8-10 hours)
5. MUSHRA listening test (30-40 hours)
6. Respond to reviews (20-40 hours, after submission)

**Total for paper submission**: ~88-133 hours (2-3 months part-time work)

**Medium priority (after acceptance)**:
- ML enhancements (genre classifier, RL)
- iOS native app
- Music recommendation features

**Low priority (research exploration)**:
- Generative preset interpolation
- Distributed caching
- Cross-genre recommendation

---

## Progress Tracking

**Last updated**: October 27, 2025
**Current phase**: Phase 1 (Paper Preparation)
**Completed tasks**: Paper draft (v1.0)
**Next task**: Create figures and diagrams

---

## How to Contribute

If you'd like to help with research tasks:
1. Check this document for open tasks
2. Comment on GitHub issue (create one for each task)
3. Fork repository, work on task
4. Submit pull request with results (data, code, figures)
5. Get credited as co-author (if substantial contribution)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

---

**Questions?** Open an issue on GitHub or contact the research team.
