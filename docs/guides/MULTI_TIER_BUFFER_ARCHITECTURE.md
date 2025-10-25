# Multi-Tier Buffer Architecture Design
## CPU-Inspired Hierarchical Caching with Branch Prediction

### Executive Summary

This document proposes a sophisticated multi-tier buffering system inspired by CPU cache hierarchies (L1/L2/L3) with branch prediction for audio chunk processing. The goal is to achieve **near-instantaneous preset switching** and **predictive long-term caching** while maintaining memory efficiency.

**Key Innovation**: Use playback patterns, user behavior, and audio characteristics to predict which chunks and presets will be needed, similar to how CPUs predict branch outcomes.

---

## Current Architecture Analysis

### Existing System (Single-Tier)
```
Current Buffer Manager:
- Strategy: Keep current + next chunk for ALL presets
- Scope: 2 chunks × 5 presets = 10 chunks buffered
- Memory: ~60MB per track (30s chunks at 44.1kHz stereo)
- Latency: 0ms for buffered presets, 2-5s for unbuffered
```

**Limitations**:
1. **No prediction**: Buffers all presets equally regardless of usage patterns
2. **Fixed horizon**: Only looks ahead 1 chunk (30 seconds)
3. **Memory inefficient**: Buffers presets user rarely switches to
4. **No long-term planning**: Doesn't prepare for upcoming sections of track

---

## Proposed Multi-Tier Architecture

### Tier Hierarchy (Inspired by CPU Caches)

```
┌─────────────────────────────────────────────────────────────┐
│                    L1 Cache (Hot Buffer)                     │
│  Current chunk + next 1 chunk for HIGH-PROBABILITY presets   │
│  Latency: 0ms | Size: ~20MB | Hit Rate Target: 95%          │
└─────────────────────────────────────────────────────────────┘
                            ↓ miss
┌─────────────────────────────────────────────────────────────┐
│                L2 Cache (Warm Buffer)                        │
│  Next 2-4 chunks for PREDICTED presets + branch scenarios    │
│  Latency: 100-200ms | Size: ~80MB | Hit Rate Target: 90%    │
└─────────────────────────────────────────────────────────────┘
                            ↓ miss
┌─────────────────────────────────────────────────────────────┐
│            L3 Cache (Cold Buffer / Long-term)                │
│  Next 5-10 chunks for CURRENT preset (section-level)         │
│  Latency: 500ms-2s | Size: ~120MB | Hit Rate Target: 70%    │
└─────────────────────────────────────────────────────────────┘
                            ↓ miss
┌─────────────────────────────────────────────────────────────┐
│                   Disk / On-Demand Processing                │
│  Process from scratch when all caches miss                   │
│  Latency: 2-5s | Size: N/A                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tier Specifications

### L1 Cache (Hot Buffer) - Immediate Response
**Purpose**: Zero-latency preset switching for current playback position

**Contents**:
- Current chunk: **Top 2-3 predicted presets** (not all 5)
- Next chunk: **Top 1-2 predicted presets**

**Eviction Policy**: LRU (Least Recently Used)

**Size**: 4-6 chunks × ~3MB = **12-18MB**

**Prediction Logic**:
```python
def predict_l1_presets(user_history, current_preset, audio_features):
    """
    Predict which presets user is most likely to switch to RIGHT NOW.

    Factors:
    - Recent preset switches (last 5 minutes)
    - "Nearby" presets (gentle ↔ adaptive ↔ warm)
    - Audio section type (chorus might trigger 'punchy' switch)
    """
    predictions = {
        'current': 1.0,  # Always buffer current preset
        'adaptive': 0.8,  # High baseline (most used)
        'gentle': 0.3,
        'warm': 0.4,
        'bright': 0.2,
        'punchy': 0.5
    }

    # Adjust based on user behavior
    for preset in user_history.recent_switches:
        predictions[preset] *= 1.5

    # Audio-aware prediction
    if audio_features.energy > 0.7:  # High energy section
        predictions['punchy'] *= 2.0

    return sorted(predictions.items(), key=lambda x: x[1], reverse=True)[:3]
```

---

### L2 Cache (Warm Buffer) - Branch Prediction
**Purpose**: Handle "what if user switches preset in next 1-2 minutes?"

**Contents**:
- **Branch Scenario 1**: User switches to most likely preset (chunks 2-4)
- **Branch Scenario 2**: User switches to 2nd likely preset (chunks 2-3)
- **Branch Scenario 3**: User stays on current preset but jumps ahead (seek prediction)

**Eviction Policy**: Predictive LRU (evict lowest probability branches first)

**Size**: 8-12 chunks × ~3MB = **24-36MB**

**Branch Prediction Logic**:
```python
class BranchPredictor:
    """
    Predict future playback scenarios similar to CPU branch prediction.
    """

    def __init__(self):
        self.history = []  # Last 100 switches
        self.accuracy = {}  # Track prediction accuracy per scenario

    def predict_branches(self, position, preset, user_context):
        """
        Generate weighted list of possible future scenarios.

        Returns:
            List[(scenario_name, preset, chunk_range, probability)]
        """
        branches = [
            # Scenario 1: Stay on current preset (baseline)
            ("continue_current", preset, range(position+2, position+5), 0.6),

            # Scenario 2: Switch to trending preset
            ("switch_trending", self._get_trending_preset(),
             range(position+1, position+3), 0.25),

            # Scenario 3: User seeks forward (common in long tracks)
            ("seek_forward", preset, range(position+10, position+12), 0.1),

            # Scenario 4: Return to previous preset (toggle behavior)
            ("toggle_back", self._get_previous_preset(),
             range(position+1, position+2), 0.05)
        ]

        return branches

    def update_accuracy(self, predicted_branch, actual_outcome):
        """
        Update prediction model based on actual user behavior.
        Similar to CPU branch predictor training.
        """
        self.accuracy[predicted_branch] = 0.9 * self.accuracy.get(predicted_branch, 0.5) + 0.1 * (1.0 if actual_outcome else 0.0)
```

---

### L3 Cache (Cold Buffer) - Long-term Section Cache
**Purpose**: Prepare for extended listening without interruption

**Contents**:
- Next 5-10 chunks of **current preset only**
- Entire verse/chorus sections pre-buffered
- Low-priority background processing

**Eviction Policy**: Time-based (evict chunks older than 5 minutes)

**Size**: 10-15 chunks × ~3MB = **30-45MB**

**Use Cases**:
- Long uninterrupted listening sessions
- Network disconnection resilience (for future streaming)
- Commute/workout playlists

**Filling Strategy**:
```python
async def fill_l3_cache(self, track_id, current_chunk, preset):
    """
    Background task: Fill L3 with upcoming chunks.

    Runs at LOW priority (only when CPU/disk idle).
    """
    # Calculate smart horizon based on track length
    track_duration = self._get_track_duration(track_id)
    remaining_chunks = (track_duration - current_chunk * 30) / 30

    # Don't buffer entire 10-minute track, cap at 5 minutes ahead
    horizon = min(10, int(remaining_chunks))

    for offset in range(2, horizon):
        chunk_idx = current_chunk + offset

        # Only process if L1/L2 are satisfied and CPU is idle
        if not self._is_system_busy():
            await self._process_chunk_low_priority(track_id, preset, chunk_idx)
            await asyncio.sleep(1.0)  # Be nice to system
```

---

## Branch Prediction Strategies

### 1. Pattern-Based Prediction
**Track user behavior patterns over time**

```python
class UserBehaviorTracker:
    """
    Learn user's preset switching patterns.
    """

    def __init__(self):
        # Track: (from_preset, to_preset) -> frequency
        self.transition_matrix = defaultdict(lambda: defaultdict(int))

        # Track: time_of_day -> preferred_preset
        self.temporal_preferences = defaultdict(lambda: defaultdict(int))

        # Track: genre -> preferred_preset
        self.genre_preferences = defaultdict(lambda: defaultdict(int))

    def record_switch(self, from_preset, to_preset, context):
        """
        Record a preset switch with context.
        """
        self.transition_matrix[from_preset][to_preset] += 1

        hour = datetime.now().hour
        self.temporal_preferences[hour][to_preset] += 1

        if context.get('genre'):
            self.genre_preferences[context['genre']][to_preset] += 1

    def predict_next_preset(self, current_preset, context):
        """
        Predict most likely next preset based on learned patterns.

        Returns:
            List[(preset, probability)]
        """
        # Get transition probabilities
        transitions = self.transition_matrix[current_preset]
        total = sum(transitions.values())

        if total == 0:
            return [('adaptive', 0.5)]  # Default fallback

        probs = {p: count/total for p, count in transitions.items()}

        # Boost based on time of day
        hour = datetime.now().hour
        temporal = self.temporal_preferences[hour]
        if temporal:
            for preset, count in temporal.items():
                probs[preset] = probs.get(preset, 0) * 1.2

        return sorted(probs.items(), key=lambda x: x[1], reverse=True)
```

### 2. Audio-Content-Aware Prediction
**Predict based on upcoming audio characteristics**

```python
async def predict_by_audio_content(self, track_id, current_chunk, next_chunks=5):
    """
    Analyze upcoming audio to predict preset switches.

    Example: If next section is high-energy chorus, predict 'punchy' switch.
    """
    # Fast spectral analysis of next few chunks
    features = await self._analyze_upcoming_chunks(track_id, next_chunks)

    predictions = {}

    for chunk_idx, feature_set in features.items():
        # High energy → user might want 'punchy'
        if feature_set['energy'] > 0.75:
            predictions[chunk_idx] = {'punchy': 0.7, 'bright': 0.3}

        # Quiet/ambient section → user might want 'gentle' or 'warm'
        elif feature_set['energy'] < 0.3:
            predictions[chunk_idx] = {'gentle': 0.6, 'warm': 0.4}

        # Vocal-heavy section → user might want 'bright'
        elif feature_set['vocal_presence'] > 0.6:
            predictions[chunk_idx] = {'bright': 0.5, 'adaptive': 0.5}

    return predictions
```

### 3. Session-Based Prediction
**Track behavior within current listening session**

```python
class SessionPredictor:
    """
    Track patterns within current listening session.
    """

    def __init__(self):
        self.session_start = time.time()
        self.switches_in_session = []
        self.focus_mode_detected = False

    def detect_session_patterns(self):
        """
        Detect if user is in "exploration mode" or "settled mode".
        """
        recent_switches = self.switches_in_session[-10:]

        if len(recent_switches) > 5 and (time.time() - self.session_start) < 300:
            # Many switches in first 5 minutes = exploration mode
            return "exploration"

        elif len(recent_switches) < 2 and (time.time() - self.session_start) > 600:
            # Few switches over 10 minutes = settled/focus mode
            return "settled"

        return "normal"

    def adjust_predictions(self, base_predictions, session_mode):
        """
        Adjust buffer strategy based on session mode.
        """
        if session_mode == "exploration":
            # Exploration mode: Buffer MORE presets in L1 (wider coverage)
            return self._widen_l1_coverage(base_predictions)

        elif session_mode == "settled":
            # Settled mode: Focus L2/L3 on current preset (deeper coverage)
            return self._deepen_l3_coverage(base_predictions)

        return base_predictions
```

---

## Memory Management

### Total Memory Budget
- **L1**: 12-18MB (hot, always in memory)
- **L2**: 24-36MB (warm, evictable under pressure)
- **L3**: 30-45MB (cold, aggressive eviction)
- **Total**: **66-99MB per track** (vs. current ~60MB)

### Eviction Strategies

```python
class MemoryManager:
    """
    Manage buffer memory with smart eviction.
    """

    MAX_MEMORY_MB = 100  # Per-track limit

    def evict_on_pressure(self):
        """
        Evict buffers when memory pressure detected.
        """
        # Priority order: L3 → L2 → L1
        # Within each tier: lowest probability first

        if self._get_current_memory() > self.MAX_MEMORY_MB:
            # Step 1: Evict low-probability L3 chunks
            self._evict_l3_low_probability(target_mb=10)

        if self._get_current_memory() > self.MAX_MEMORY_MB * 0.9:
            # Step 2: Evict L2 branch scenarios < 10% probability
            self._evict_l2_unlikely_branches(threshold=0.1)

        if self._get_current_memory() > self.MAX_MEMORY_MB * 0.95:
            # Step 3: Emergency - evict L1 presets with 0 switches in session
            self._evict_l1_unused_presets()
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] Implement `MultiTierBufferManager` class with L1/L2/L3 separation
- [ ] Add `BranchPredictor` base class
- [ ] Implement simple pattern-based prediction (transition matrix)
- [ ] Add tests for tier promotion/demotion

### Phase 2: Branch Prediction (Week 2)
- [ ] Implement `UserBehaviorTracker` with persistent storage
- [ ] Add `SessionPredictor` for short-term pattern detection
- [ ] Implement adaptive prediction weight adjustment
- [ ] Add prediction accuracy metrics/logging

### Phase 3: Audio-Content-Aware Prediction (Week 3)
- [ ] Fast spectral analysis for upcoming chunks
- [ ] Genre/mood-based preset prediction
- [ ] Section detection (verse/chorus) for targeted buffering
- [ ] Integration with existing `ContentAnalyzer`

### Phase 4: Memory Optimization (Week 4)
- [ ] Implement smart eviction policies
- [ ] Add memory pressure monitoring
- [ ] Implement chunk compression for L3 cache
- [ ] Add configurable memory limits

### Phase 5: Monitoring & Tuning (Week 5)
- [ ] Add detailed metrics (hit rates per tier)
- [ ] Implement A/B testing framework for prediction strategies
- [ ] Add user-facing "cache status" indicator
- [ ] Performance benchmarking

---

## Performance Targets

| Metric | Current | Target (Multi-Tier) |
|--------|---------|---------------------|
| **Preset Switch Latency (L1 hit)** | 0ms | 0ms |
| **Preset Switch Latency (L2 hit)** | 2-5s | 100-200ms |
| **Preset Switch Latency (L3 hit)** | 2-5s | 500ms-1s |
| **L1 Hit Rate** | ~40% (2/5 presets) | **95%** |
| **L2 Hit Rate** | N/A | **90%** |
| **L3 Hit Rate** | N/A | **70%** |
| **Memory per Track** | 60MB | 66-99MB |
| **Prediction Accuracy** | N/A | **80%** (after learning) |

---

## Example Scenarios

### Scenario 1: First-Time User (Cold Start)
```
User starts playing track, never used Auralis before.

L1: [adaptive, gentle, warm] × chunks [0, 1]
L2: [bright, punchy] × chunks [1, 2] (exploratory coverage)
L3: [adaptive] × chunks [2-6] (default preset long-term)

Result: User gets instant switching to top 3 popular presets.
After 2-3 switches, system learns their preferences and adapts.
```

### Scenario 2: Experienced User with Patterns
```
User has switched 'adaptive' → 'punchy' 15 times in past sessions.
Currently on 'adaptive', listening to rock track.

L1: [adaptive, punchy] × chunks [5, 6]  ← High confidence
L2: [bright] × chunks [6, 7] + [adaptive] × [7-9]  ← Fallback + long-term
L3: [adaptive] × chunks [10-15]  ← Deep buffer

Result: Switch to 'punchy' is instant (L1 hit), others are 100-200ms (L2).
```

### Scenario 3: Exploration Mode
```
User switched presets 8 times in 3 minutes (exploring).

L1: ALL 5 presets × chunk [current]  ← Wide coverage
L2: Top 3 presets × chunks [current+1, current+2]
L3: Disabled (unpredictable behavior)

Result: Every switch is instant, but uses more L1 memory.
System detects "exploration mode" and adjusts buffer strategy.
```

---

## API Changes

### New Methods on `BufferManager`

```python
class MultiTierBufferManager(BufferManager):
    """
    Enhanced buffer manager with multi-tier caching.
    """

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get detailed cache statistics.

        Returns:
            {
                'l1': {'size_mb': 15, 'hit_rate': 0.95, 'chunks': 6},
                'l2': {'size_mb': 30, 'hit_rate': 0.88, 'chunks': 10},
                'l3': {'size_mb': 45, 'hit_rate': 0.72, 'chunks': 15},
                'predictions': {'accuracy': 0.82, 'confidence': 0.75}
            }
        """

    def predict_next_presets(self, context: Dict) -> List[Tuple[str, float]]:
        """
        Get predicted presets with probabilities.

        Returns:
            [('punchy', 0.75), ('adaptive', 0.20), ('bright', 0.05)]
        """

    def set_memory_limit(self, limit_mb: int):
        """
        Configure maximum memory usage per track.
        """

    def enable_learning(self, enable: bool = True):
        """
        Enable/disable behavioral learning.

        When disabled, uses only static predictions (privacy mode).
        """
```

---

## Future Enhancements

### 1. Network-Aware Buffering (Streaming Preparation)
When Auralis adds streaming, use multi-tier buffer for:
- L1: Currently playing (always downloaded)
- L2: Next 2-3 songs in queue (preemptive download)
- L3: Entire playlist (background download when on WiFi)

### 2. Collaborative Filtering
Learn from all Auralis users (opt-in):
- "Users who switch adaptive→punchy on rock tracks also often switch to bright"
- Improve cold-start predictions for new users

### 3. GPU Acceleration for L3
Use GPU (if available) for L3 chunk processing:
- Process 5-10 chunks in parallel
- Fill L3 cache in seconds instead of minutes

### 4. Adaptive Chunk Sizes
Vary chunk duration based on prediction confidence:
- High confidence: 30s chunks (current)
- Low confidence: 10s chunks (faster switching, more granular)
- Exploration mode: 5s chunks (maximum flexibility)

---

## Conclusion

This multi-tier buffer architecture transforms Auralis from a **reactive** system (buffer when needed) to a **predictive** system (anticipate needs before they occur). By learning user behavior and analyzing audio content, we can achieve:

1. **Near-zero latency** for 95% of preset switches (L1 hits)
2. **Sub-second latency** for 90% of remaining switches (L2 hits)
3. **Efficient memory usage** through smart eviction and prediction
4. **Personalized experience** that improves over time

The architecture is inspired by decades of CPU cache research, adapted for the unique challenges of audio processing where "branches" are preset switches and "instructions" are audio chunks.

**Next Steps**: Review this design, discuss trade-offs, and create implementation tickets for Phase 1.
