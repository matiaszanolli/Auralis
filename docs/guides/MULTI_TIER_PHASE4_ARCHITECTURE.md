# Multi-Tier Buffer Phase 4: Proactive Management & Learning

**Date**: October 25, 2025
**Phase**: 4 of 4 (Final Phase)
**Status**: Design

---

## Executive Summary

Phase 4 completes the multi-tier buffer system by adding:

1. **Adaptive Learning System** - Tracks prediction accuracy and adapts behavior
2. **Proactive Buffer Management** - Intelligent memory pressure handling
3. **Performance Monitoring** - Real-time metrics and health checks
4. **Self-Tuning** - Automatic optimization based on observed behavior

**Goal**: Create a self-optimizing system that learns from its mistakes and adapts to available resources.

---

## 1. Adaptive Learning System

### 1.1 Prediction Accuracy Tracking

**What to Track**:
```python
@dataclass
class PredictionAccuracy:
    """Tracks prediction accuracy over time."""
    timestamp: float
    predicted_preset: str
    actual_preset: str
    was_correct: bool
    confidence: float
    context: str  # "cold_start", "warm_start", "audio_guided"
```

**Metrics**:
- **Overall accuracy**: % of correct predictions
- **Per-preset accuracy**: Which presets are hard to predict?
- **Context-based accuracy**: Cold start vs. warm start vs. audio-guided
- **Confidence calibration**: Do high-confidence predictions succeed more?

**Storage**:
```python
class LearningSystem:
    def __init__(self):
        self.prediction_history: Deque[PredictionAccuracy] = deque(maxlen=1000)
        self.accuracy_by_preset: Dict[str, List[bool]] = defaultdict(list)
        self.accuracy_by_context: Dict[str, List[bool]] = defaultdict(list)
```

### 1.2 Adaptive Weight Tuning

**Current**: 70% user behavior, 30% audio content (hardcoded)

**Adaptive**:
```python
class AdaptiveWeightTuner:
    """Dynamically adjusts user/audio weighting based on accuracy."""

    def __init__(self):
        self.user_weight = 0.7  # Start with 70/30
        self.audio_weight = 0.3
        self.min_user_weight = 0.5  # Never go below 50% user
        self.max_user_weight = 0.9  # Never go above 90% user

    def update_weights(self, recent_predictions: List[PredictionAccuracy]):
        """Adjust weights based on recent accuracy."""

        # Calculate accuracy for user-only vs. audio-enhanced
        user_only_accuracy = self._calculate_user_only_accuracy()
        audio_enhanced_accuracy = self._calculate_audio_enhanced_accuracy()

        # If audio is helping, increase its weight
        if audio_enhanced_accuracy > user_only_accuracy + 0.05:  # 5% improvement
            self.audio_weight = min(0.5, self.audio_weight + 0.05)
            self.user_weight = 1.0 - self.audio_weight

        # If audio is hurting, decrease its weight
        elif audio_enhanced_accuracy < user_only_accuracy - 0.05:
            self.audio_weight = max(0.1, self.audio_weight - 0.05)
            self.user_weight = 1.0 - self.audio_weight
```

**Tuning Strategy**:
- Start with 70/30 split
- Every 100 predictions, evaluate effectiveness
- Adjust weights by ±5% increments
- Clamp user weight between 50-90%
- Save optimal weights per-user (future: per-genre)

### 1.3 Affinity Rule Learning

**Current**: Hardcoded rules (high energy → punchy)

**Learning**:
```python
class AffinityRuleLearner:
    """Learns which audio features predict which presets."""

    def __init__(self):
        # Start with default rules
        self.affinity_rules = DEFAULT_AFFINITY_RULES.copy()

        # Track success rates
        self.rule_success_rates: Dict[Tuple[str, str], List[bool]] = defaultdict(list)
        # (feature_condition, preset) -> [True, False, True, ...]

    def record_outcome(
        self,
        audio_features: AudioFeatures,
        predicted_preset: str,
        actual_preset: str
    ):
        """Record whether audio-based prediction was correct."""

        # Determine which features were active
        active_features = []
        if audio_features.energy > 0.6:
            active_features.append("high_energy")
        if audio_features.energy < 0.4:
            active_features.append("low_energy")
        # ... etc

        # Record success/failure for each feature-preset pair
        was_correct = (predicted_preset == actual_preset)
        for feature in active_features:
            key = (feature, predicted_preset)
            self.rule_success_rates[key].append(was_correct)

    def update_affinity_rules(self):
        """Update rules based on observed success rates."""

        for (feature, preset), outcomes in self.rule_success_rates.items():
            if len(outcomes) < 20:  # Need minimum data
                continue

            success_rate = sum(outcomes) / len(outcomes)

            # If rule is working well (>70% success), increase affinity
            if success_rate > 0.7:
                current_affinity = self.affinity_rules[feature].get(preset, 0.0)
                self.affinity_rules[feature][preset] = min(1.0, current_affinity + 0.05)

            # If rule is failing (<40% success), decrease affinity
            elif success_rate < 0.4:
                current_affinity = self.affinity_rules[feature].get(preset, 0.0)
                self.affinity_rules[feature][preset] = max(0.0, current_affinity - 0.05)
```

---

## 2. Proactive Buffer Management

### 2.1 Memory Pressure Detection

**Problem**: System may not have 99MB available for caching.

**Solution**: Dynamic cache sizing based on available memory.

```python
class MemoryPressureMonitor:
    """Monitors system memory and adjusts cache sizes."""

    def __init__(self):
        self.total_system_memory = self._get_total_memory()
        self.memory_warning_threshold = 0.8  # 80% usage
        self.memory_critical_threshold = 0.9  # 90% usage

    def get_memory_status(self) -> str:
        """Returns: 'normal', 'warning', or 'critical'"""

        used_percent = self._get_memory_usage_percent()

        if used_percent > self.memory_critical_threshold:
            return "critical"
        elif used_percent > self.memory_warning_threshold:
            return "warning"
        else:
            return "normal"

    def get_recommended_cache_sizes(self) -> Tuple[float, float, float]:
        """Returns recommended (L1, L2, L3) sizes in MB."""

        status = self.get_memory_status()

        if status == "critical":
            # Minimal caching: only L1
            return (9.0, 0.0, 0.0)  # 9MB L1 only

        elif status == "warning":
            # Reduced caching: L1 + L2
            return (12.0, 18.0, 0.0)  # 30MB total

        else:  # normal
            # Full caching
            return (18.0, 36.0, 45.0)  # 99MB total
```

**Integration**:
```python
class MultiTierBufferManager:
    def __init__(self):
        self.memory_monitor = MemoryPressureMonitor()
        self._adjust_cache_sizes_if_needed()

    async def _adjust_cache_sizes_if_needed(self):
        """Periodically check memory and adjust cache sizes."""

        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            l1_size, l2_size, l3_size = self.memory_monitor.get_recommended_cache_sizes()

            # Only adjust if sizes changed significantly
            if abs(l1_size - self.l1_cache.max_size_mb) > 3.0:
                logger.info(f"Adjusting cache sizes: L1={l1_size}MB, L2={l2_size}MB, L3={l3_size}MB")

                self.l1_cache.max_size_mb = l1_size
                self.l2_cache.max_size_mb = l2_size
                self.l3_cache.max_size_mb = l3_size

                # Evict excess entries if cache shrunk
                await self.l1_cache._enforce_size_limit()
                await self.l2_cache._enforce_size_limit()
                await self.l3_cache._enforce_size_limit()
```

### 2.2 Priority-Based Eviction Under Pressure

**Strategy**: When memory pressure increases, evict lower-priority entries first.

```python
class CacheTier:
    async def evict_under_pressure(self, target_size_mb: float):
        """Aggressive eviction to hit target size quickly."""

        # Sort entries by priority:
        # 1. Current chunk (never evict)
        # 2. Next chunk (high priority)
        # 3. High-probability predictions
        # 4. Low-probability predictions
        # 5. Everything else

        current_chunk = self._get_current_chunk()

        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (
                e.chunk_idx == current_chunk,  # Current chunk first (never evict)
                e.chunk_idx == current_chunk + 1,  # Next chunk second
                e.probability,  # Then by probability
                e.last_access  # Then by recency
            ),
            reverse=True  # Descending order (keep high-priority)
        )

        # Evict from the end (lowest priority)
        while self.current_size_mb > target_size_mb:
            if not sorted_entries:
                break

            # Skip current and next chunk (protected)
            entry = sorted_entries.pop()
            if entry.chunk_idx in [current_chunk, current_chunk + 1]:
                continue

            await self._evict_entry(entry)
```

### 2.3 Graceful Degradation

**Degradation Levels**:

1. **Level 0 (Normal)**: Full caching (L1 + L2 + L3)
2. **Level 1 (Warning)**: Reduced caching (L1 + L2 only)
3. **Level 2 (Critical)**: Minimal caching (L1 only)
4. **Level 3 (Emergency)**: Disable background buffering

```python
class DegradationManager:
    """Manages graceful degradation under resource constraints."""

    def get_degradation_level(self) -> int:
        """Returns degradation level (0-3)."""

        status = self.memory_monitor.get_memory_status()

        if status == "critical":
            # Check if background worker is impacting performance
            if self._is_worker_causing_latency():
                return 3  # Emergency: disable worker
            else:
                return 2  # Critical: L1 only

        elif status == "warning":
            return 1  # Warning: L1 + L2
        else:
            return 0  # Normal: full caching

    async def apply_degradation(self, level: int):
        """Apply degradation strategy."""

        if level == 0:
            # Normal operation
            self.worker.enable()
            self.l1_cache.max_size_mb = 18.0
            self.l2_cache.max_size_mb = 36.0
            self.l3_cache.max_size_mb = 45.0

        elif level == 1:
            # Reduced caching
            self.worker.enable()
            self.l1_cache.max_size_mb = 12.0
            self.l2_cache.max_size_mb = 18.0
            self.l3_cache.max_size_mb = 0.0
            await self.l3_cache.clear()

        elif level == 2:
            # Minimal caching
            self.worker.enable()  # Keep worker but only for L1
            self.l1_cache.max_size_mb = 9.0
            self.l2_cache.max_size_mb = 0.0
            self.l3_cache.max_size_mb = 0.0
            await self.l2_cache.clear()
            await self.l3_cache.clear()

        elif level == 3:
            # Emergency: disable worker
            await self.worker.pause()
            self.l1_cache.max_size_mb = 6.0
            self.l2_cache.max_size_mb = 0.0
            self.l3_cache.max_size_mb = 0.0
            await self.l2_cache.clear()
            await self.l3_cache.clear()
```

---

## 3. Performance Monitoring

### 3.1 Real-Time Metrics

```python
@dataclass
class PerformanceMetrics:
    """Real-time performance metrics."""

    # Cache metrics
    l1_hit_rate: float
    l2_hit_rate: float
    l3_hit_rate: float
    overall_hit_rate: float

    # Prediction metrics
    prediction_accuracy: float
    user_only_accuracy: float
    audio_enhanced_accuracy: float

    # Memory metrics
    memory_usage_mb: float
    memory_usage_percent: float
    degradation_level: int

    # Performance metrics
    avg_switch_latency_ms: float
    instant_switches_percent: float  # L1 hit rate

    # Worker metrics
    worker_queue_size: int
    worker_processing_rate: float  # chunks per second
    worker_idle_percent: float
```

**Collection**:
```python
class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self):
        self.metrics_history: Deque[PerformanceMetrics] = deque(maxlen=1000)

    def collect_current_metrics(self) -> PerformanceMetrics:
        """Collect current state of all metrics."""

        return PerformanceMetrics(
            l1_hit_rate=self._calculate_hit_rate(self.l1_cache),
            l2_hit_rate=self._calculate_hit_rate(self.l2_cache),
            l3_hit_rate=self._calculate_hit_rate(self.l3_cache),
            overall_hit_rate=self._calculate_overall_hit_rate(),

            prediction_accuracy=self.learning_system.get_overall_accuracy(),
            user_only_accuracy=self.learning_system.get_user_only_accuracy(),
            audio_enhanced_accuracy=self.learning_system.get_audio_enhanced_accuracy(),

            memory_usage_mb=self._get_total_memory_usage(),
            memory_usage_percent=self.memory_monitor.get_memory_usage_percent(),
            degradation_level=self.degradation_manager.get_degradation_level(),

            avg_switch_latency_ms=self._calculate_avg_switch_latency(),
            instant_switches_percent=self.l1_hit_rate,

            worker_queue_size=len(self.worker.processing_queue),
            worker_processing_rate=self.worker.get_processing_rate(),
            worker_idle_percent=self.worker.get_idle_percent()
        )
```

### 3.2 Health Checks

```python
class HealthChecker:
    """Performs health checks on the buffer system."""

    def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check."""

        checks = {
            "cache_health": self._check_cache_health(),
            "prediction_health": self._check_prediction_health(),
            "memory_health": self._check_memory_health(),
            "worker_health": self._check_worker_health()
        }

        overall_status = "healthy"
        if any(check["status"] == "critical" for check in checks.values()):
            overall_status = "critical"
        elif any(check["status"] == "warning" for check in checks.values()):
            overall_status = "warning"

        return {
            "overall_status": overall_status,
            "checks": checks,
            "timestamp": time.time()
        }

    def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache system health."""

        l1_hit_rate = self._calculate_hit_rate(self.l1_cache)

        if l1_hit_rate < 0.7:  # Below 70%
            return {
                "status": "warning",
                "message": f"L1 hit rate low: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate
            }
        elif l1_hit_rate < 0.5:  # Below 50%
            return {
                "status": "critical",
                "message": f"L1 hit rate critical: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate
            }
        else:
            return {
                "status": "healthy",
                "message": f"L1 hit rate: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate
            }

    def _check_prediction_health(self) -> Dict[str, Any]:
        """Check prediction system health."""

        accuracy = self.learning_system.get_overall_accuracy()

        if accuracy < 0.4:  # Below 40%
            return {
                "status": "warning",
                "message": f"Prediction accuracy low: {accuracy:.1%}",
                "accuracy": accuracy
            }
        else:
            return {
                "status": "healthy",
                "message": f"Prediction accuracy: {accuracy:.1%}",
                "accuracy": accuracy
            }
```

---

## 4. Self-Tuning

### 4.1 Automatic Optimization

```python
class SelfTuner:
    """Automatically optimizes system parameters based on observed behavior."""

    def __init__(self):
        self.tuning_interval = 300  # Tune every 5 minutes
        self.weight_tuner = AdaptiveWeightTuner()
        self.affinity_learner = AffinityRuleLearner()

    async def run_tuning_loop(self):
        """Continuously tune system parameters."""

        while True:
            await asyncio.sleep(self.tuning_interval)

            # Collect recent metrics
            recent_predictions = self.learning_system.get_recent_predictions(100)

            # Tune user/audio weights
            self.weight_tuner.update_weights(recent_predictions)

            # Update affinity rules
            self.affinity_learner.update_affinity_rules()

            # Log tuning changes
            logger.info(f"Self-tuning: user_weight={self.weight_tuner.user_weight:.2f}, "
                       f"audio_weight={self.weight_tuner.audio_weight:.2f}")
```

### 4.2 Per-User Optimization (Future)

```python
class UserProfile:
    """Per-user optimization profile."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.optimal_user_weight = 0.7
        self.optimal_audio_weight = 0.3
        self.preset_preferences: Dict[str, float] = {}
        self.genre_preferences: Dict[str, Dict[str, float]] = {}

    def save(self, filepath: str):
        """Save user profile to disk."""
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f)

    @classmethod
    def load(cls, filepath: str) -> 'UserProfile':
        """Load user profile from disk."""
        with open(filepath, 'r') as f:
            data = json.load(f)
            return cls(**data)
```

---

## 5. Implementation Plan

### 5.1 Files to Create

1. **`learning_system.py`** (~400 lines)
   - PredictionAccuracy, LearningSystem, AdaptiveWeightTuner, AffinityRuleLearner

2. **`memory_monitor.py`** (~300 lines)
   - MemoryPressureMonitor, DegradationManager

3. **`metrics_collector.py`** (~350 lines)
   - PerformanceMetrics, MetricsCollector, HealthChecker

4. **`self_tuner.py`** (~250 lines)
   - SelfTuner, UserProfile (future)

### 5.2 Files to Modify

1. **`multi_tier_buffer.py`** (+150 lines)
   - Integrate LearningSystem
   - Add prediction accuracy tracking
   - Add memory monitoring

2. **`multi_tier_worker.py`** (+100 lines)
   - Add pause/resume for degradation
   - Add metrics collection
   - Add processing rate tracking

3. **`routers/cache.py`** (+100 lines)
   - Add metrics endpoints
   - Add health check endpoints
   - Add tuning control endpoints

### 5.3 Tests to Create

1. **`test_learning_system.py`** (20+ tests)
   - Prediction tracking
   - Weight tuning
   - Affinity rule learning

2. **`test_memory_monitor.py`** (15+ tests)
   - Memory pressure detection
   - Cache size adjustment
   - Graceful degradation

3. **`test_metrics.py`** (15+ tests)
   - Metrics collection
   - Health checks
   - Performance monitoring

4. **`test_self_tuning.py`** (10+ tests)
   - Automatic optimization
   - User profiles (future)

**Total Estimated Tests**: 60+ tests

---

## 6. Expected Impact

### 6.1 Performance Improvements

**Before Phase 4**:
- Fixed 70/30 weight split
- Fixed cache sizes (99MB)
- No adaptation to usage patterns

**After Phase 4**:
- Adaptive weight split (50-90% user, optimized per-user)
- Dynamic cache sizes (6-99MB based on memory)
- Self-optimizing affinity rules
- Graceful degradation under pressure

### 6.2 User Experience

**Benefits**:
1. System adapts to individual user behavior patterns
2. Works on memory-constrained devices
3. Self-heals from poor predictions
4. Transparent performance monitoring

**Example**:
- User A: Rarely switches presets → system learns to buffer current preset deeply (90% user weight)
- User B: Frequently experiments → system relies more on audio content (60% user weight)

---

## 7. API Enhancements

### New Endpoints

```python
# Metrics
GET /api/cache/metrics - Get current performance metrics
GET /api/cache/metrics/history - Get metrics history

# Health
GET /api/cache/health - Comprehensive health check
GET /api/cache/health/cache - Cache-specific health
GET /api/cache/health/prediction - Prediction-specific health
GET /api/cache/health/memory - Memory-specific health

# Learning
GET /api/cache/learning/accuracy - Prediction accuracy stats
GET /api/cache/learning/weights - Current weight split
POST /api/cache/learning/reset - Reset learning data

# Tuning
GET /api/cache/tuning/status - Self-tuning status
POST /api/cache/tuning/enable - Enable self-tuning
POST /api/cache/tuning/disable - Disable self-tuning
```

---

## Summary

Phase 4 completes the multi-tier buffer system with:

✅ **Adaptive Learning** - System learns from predictions and adapts weights
✅ **Proactive Management** - Intelligent memory pressure handling and degradation
✅ **Performance Monitoring** - Real-time metrics and health checks
✅ **Self-Tuning** - Automatic optimization based on observed behavior

**Result**: A self-optimizing, resource-aware buffer system that adapts to individual users and system constraints.

**Implementation Scope**: ~1,300 lines of code, 60+ tests, ~2-3 hours
