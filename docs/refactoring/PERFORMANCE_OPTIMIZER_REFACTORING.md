# Performance Optimizer Refactoring Plan

**Date**: November 5, 2025
**Target**: `auralis/optimization/performance_optimizer.py` (570 lines)
**Objective**: Split into feature-wise modules for better maintainability

---

## Current Structure Analysis

### File: `performance_optimizer.py` (570 lines)

**Classes Found**:
1. `PerformanceConfig` (23 lines) - Configuration dataclass
2. `MemoryPool` (63 lines) - Memory buffer pooling
3. `SmartCache` (114 lines) - Intelligent caching with TTL
4. `SIMDAccelerator` (81 lines) - SIMD vectorization utilities
5. `ParallelProcessor` (51 lines) - Parallel processing orchestration
6. `PerformanceProfiler` (52 lines) - Performance metrics tracking
7. `PerformanceOptimizer` (155 lines) - Main orchestrator class

**Total**: 539 lines of class code + 31 lines imports/utils = 570 lines

---

## Refactoring Strategy

### New Structure

```
auralis/optimization/
├── __init__.py                      # Public API exports
├── performance_optimizer.py         # Main orchestrator (KEEP, simplified)
├── config.py                        # Configuration
├── memory/
│   ├── __init__.py
│   └── memory_pool.py              # MemoryPool class
├── caching/
│   ├── __init__.py
│   └── smart_cache.py              # SmartCache class
├── acceleration/
│   ├── __init__.py
│   ├── simd_accelerator.py         # SIMD utilities
│   └── parallel_processor.py       # Parallel processing
└── profiling/
    ├── __init__.py
    └── performance_profiler.py     # Metrics tracking
```

---

## File Breakdown

### 1. `config.py` (~30 lines)

```python
"""Performance optimization configuration"""

from dataclasses import dataclass
import multiprocessing as mp

@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    enable_caching: bool = True
    enable_parallel: bool = True
    enable_simd: bool = True
    enable_prefetch: bool = True

    # Cache settings
    cache_size_mb: int = 128
    cache_ttl_seconds: int = 300

    # Threading settings
    max_threads: int = min(4, mp.cpu_count())
    thread_pool_size: int = 2

    # SIMD settings
    vectorization_threshold: int = 1024

    # Memory settings
    memory_pool_size_mb: int = 64
    garbage_collect_interval: int = 100
```

### 2. `memory/memory_pool.py` (~80 lines)

```python
"""High-performance memory pool for audio buffers"""

import numpy as np
from typing import Tuple
from collections import deque
import threading

class MemoryPool:
    """High-performance memory pool for audio buffers"""

    def __init__(self, pool_size_mb: int = 64):
        # ... (existing implementation)

    def get_buffer(self, shape: Tuple[int, ...], dtype=np.float32) -> np.ndarray:
        # ... (existing implementation)

    def return_buffer(self, buffer: np.ndarray):
        # ... (existing implementation)

    def clear(self):
        # ... (existing implementation)
```

### 3. `caching/smart_cache.py` (~130 lines)

```python
"""Intelligent caching with TTL and size limits"""

import time
import hashlib
import pickle
from typing import Any, Callable, Optional
from collections import OrderedDict
from functools import wraps
import threading

class SmartCache:
    """Intelligent cache with TTL and LRU eviction"""

    def __init__(self, size_mb: int = 128, ttl_seconds: int = 300):
        # ... (existing implementation)

    def get(self, key: str) -> Optional[Any]:
        # ... (existing implementation)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        # ... (existing implementation)

    def cached(self, ttl: Optional[int] = None):
        """Decorator for caching function results"""
        # ... (existing implementation)
```

### 4. `acceleration/simd_accelerator.py` (~100 lines)

```python
"""SIMD vectorization utilities"""

import numpy as np
from typing import Callable

class SIMDAccelerator:
    """SIMD vectorization for audio processing"""

    def __init__(self, threshold: int = 1024):
        # ... (existing implementation)

    def vectorize(self, func: Callable, *args, **kwargs):
        """Apply SIMD vectorization to function"""
        # ... (existing implementation)

    def is_vectorizable(self, data_size: int) -> bool:
        # ... (existing implementation)
```

### 5. `acceleration/parallel_processor.py` (~70 lines)

```python
"""Parallel processing orchestration"""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Any
import multiprocessing as mp

class ParallelProcessor:
    """Parallel processing for independent operations"""

    def __init__(self, max_threads: int = None, pool_size: int = 2):
        # ... (existing implementation)

    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """Parallel map operation"""
        # ... (existing implementation)

    def shutdown(self):
        # ... (existing implementation)
```

### 6. `profiling/performance_profiler.py` (~70 lines)

```python
"""Performance metrics tracking"""

import time
from typing import Dict, List
from collections import defaultdict, deque
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    operation: str
    duration_ms: float
    timestamp: float

class PerformanceProfiler:
    """Track and analyze performance metrics"""

    def __init__(self, history_size: int = 1000):
        # ... (existing implementation)

    def start_timer(self, operation: str):
        # ... (existing implementation)

    def end_timer(self, operation: str) -> float:
        # ... (existing implementation)

    def get_stats(self) -> Dict:
        # ... (existing implementation)
```

### 7. `performance_optimizer.py` (SIMPLIFIED, ~180 lines)

```python
"""Main performance optimization orchestrator"""

from .config import PerformanceConfig
from .memory import MemoryPool
from .caching import SmartCache
from .acceleration import SIMDAccelerator, ParallelProcessor
from .profiling import PerformanceProfiler

class PerformanceOptimizer:
    """Main performance optimization orchestrator"""

    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()

        # Initialize subsystems
        self.memory_pool = MemoryPool(self.config.memory_pool_size_mb) if self.config.enable_caching else None
        self.cache = SmartCache(self.config.cache_size_mb, self.config.cache_ttl_seconds) if self.config.enable_caching else None
        self.simd = SIMDAccelerator(self.config.vectorization_threshold) if self.config.enable_simd else None
        self.parallel = ParallelProcessor(self.config.max_threads, self.config.thread_pool_size) if self.config.enable_parallel else None
        self.profiler = PerformanceProfiler()

    # ... (existing orchestration methods)
```

### 8. `__init__.py` (Public API)

```python
"""
Performance Optimization Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance optimization for real-time audio processing
"""

from .performance_optimizer import PerformanceOptimizer
from .config import PerformanceConfig
from .memory import MemoryPool
from .caching import SmartCache
from .acceleration import SIMDAccelerator, ParallelProcessor
from .profiling import PerformanceProfiler, PerformanceMetrics

__all__ = [
    'PerformanceOptimizer',
    'PerformanceConfig',
    'MemoryPool',
    'SmartCache',
    'SIMDAccelerator',
    'ParallelProcessor',
    'PerformanceProfiler',
    'PerformanceMetrics',
]
```

---

## File Size Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Config | N/A (inline) | ~30 lines | N/A |
| MemoryPool | 63 lines | ~80 lines | 0% (with imports) |
| SmartCache | 114 lines | ~130 lines | 0% (with imports) |
| SIMDAccelerator | 81 lines | ~100 lines | 0% (with imports) |
| ParallelProcessor | 51 lines | ~70 lines | 0% (with imports) |
| PerformanceProfiler | 52 lines | ~70 lines | 0% (with imports) |
| PerformanceOptimizer | 155 lines | ~180 lines | 0% (orchestration only) |
| **Total** | **570 lines** | **~660 lines** | +16% (with module overhead) |

**Note**: Refactoring adds ~90 lines for module structure (imports, `__init__.py` files), but **dramatically improves**:
- Code organization
- Testability
- Maintainability
- Reusability

---

## Benefits

### 1. Better Organization
- Each component in its own module
- Clear separation of concerns
- Easy to find and modify specific features

### 2. Improved Testability
- Test each component independently
- Mock dependencies easily
- Isolate failures

### 3. Enhanced Reusability
- Import only what you need
- Use individual components standalone
- Clear public API

### 4. Easier Maintenance
- Changes localized to specific modules
- No 570-line monolith to navigate
- Clear responsibilities

---

## Migration Steps

### Phase 1: Create Module Structure (30 min)

1. Create directories:
   ```bash
   mkdir -p auralis/optimization/memory
   mkdir -p auralis/optimization/caching
   mkdir -p auralis/optimization/acceleration
   mkdir -p auralis/optimization/profiling
   ```

2. Create `__init__.py` files for all directories

### Phase 2: Extract Components (1 hour)

1. Extract `PerformanceConfig` → `config.py`
2. Extract `MemoryPool` → `memory/memory_pool.py`
3. Extract `SmartCache` → `caching/smart_cache.py`
4. Extract `SIMDAccelerator` → `acceleration/simd_accelerator.py`
5. Extract `ParallelProcessor` → `acceleration/parallel_processor.py`
6. Extract `PerformanceProfiler` → `profiling/performance_profiler.py`

### Phase 3: Update Main File (30 min)

1. Simplify `performance_optimizer.py` to orchestrator only
2. Update imports to use new module structure
3. Keep all public methods unchanged

### Phase 4: Create Backward Compatibility (15 min)

Keep old imports working:
```python
# Old code still works:
from auralis.optimization.performance_optimizer import MemoryPool

# New code uses:
from auralis.optimization.memory import MemoryPool
# OR
from auralis.optimization import MemoryPool
```

### Phase 5: Testing (30 min)

1. Run existing tests
2. Verify all imports work
3. Check no functionality broken

---

## Backward Compatibility

### Old API (Still Supported)

```python
# All these still work
from auralis.optimization.performance_optimizer import (
    PerformanceConfig,
    MemoryPool,
    SmartCache,
    SIMDAccelerator,
    ParallelProcessor,
    PerformanceProfiler,
    PerformanceOptimizer
)
```

### New API (Recommended)

```python
# Cleaner imports
from auralis.optimization import (
    PerformanceConfig,
    MemoryPool,
    SmartCache,
    PerformanceOptimizer
)

# Or specific imports
from auralis.optimization.memory import MemoryPool
from auralis.optimization.caching import SmartCache
```

---

## Success Criteria

- [ ] All classes extracted to separate modules
- [ ] All existing tests pass
- [ ] No breaking changes to public API
- [ ] Backward compatibility maintained
- [ ] Documentation updated
- [ ] Each module < 150 lines
- [ ] Clear public API in `__init__.py`

---

## Estimated Time

- Phase 1 (Structure): 30 minutes
- Phase 2 (Extract): 1 hour
- Phase 3 (Update main): 30 minutes
- Phase 4 (Compatibility): 15 minutes
- Phase 5 (Testing): 30 minutes

**Total**: ~2.5 hours

---

## Similar Refactorings Completed

This follows the same pattern as:
1. ✅ `dsp/unified.py` → `dsp/utils/` (87% reduction)
2. ✅ `dsp/psychoacoustic_eq.py` → `dsp/eq/` (80% reduction)
3. ✅ `analysis/quality_metrics.py` → `analysis/quality/` (72% reduction)
4. ✅ Multi-tier cache → Streamlined cache (52% reduction)

**Total refactorings**: 13 modules, 50+ new focused files, average 60% size reduction

---

**Next Action**: Create module structure and begin extraction
