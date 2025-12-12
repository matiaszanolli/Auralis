# Mypy Coverage Improvement - Implementation Plan

**Goal**: Reduce 1761 mypy errors to 0 (or <5 critical errors)

**Strategy**: Fix cascading errors first (root modules → dependencies)

---

## Phase 1: Critical Root Modules (Cascading Error Reduction)

### Priority 0: `auralis/utils/logging.py` ⚠️ CRITICAL
- **Current Status**: 875 cascading errors (imported everywhere)
- **File Size**: 84 lines, 9 functions
- **Effort**: ~30 minutes
- **Impact**: Likely reduces 300+ errors in all importing modules
- **Common Fixes**:
  - Add `-> None` return type to logging functions
  - Fix `ModuleError.__init__` parameter types
  - Fix `**kwargs` type annotation

### Priority 1: `auralis/core/config/settings.py`
- **Current Status**: Multiple __post_init__ missing return types
- **File Size**: 97 lines
- **Effort**: ~20 minutes
- **Impact**: Reduces errors in config-dependent modules
- **Common Fixes**:
  - Add `-> None` to all `__post_init__` dataclass methods
  - Fix Optional field assignments (None to typed fields)
  - Add type parameters to generic returns: `dict` → `Dict[str, Any]`

### Priority 1b: `auralis/core/config/preset_profiles.py`
- **Current Status**: Missing generic type parameters
- **Fixes**: `get_available_presets() -> list:` → `-> List[str]:`

### Priority 2: `auralis/player/realtime/gain_smoother.py`
- **Current Status**: Missing return types on methods
- **File Size**: Small
- **Effort**: ~15 minutes
- **Impact**: Reduces errors in player module chain

### Priority 3: `auralis/dsp/dynamics/settings.py`
- **Current Status**: Incompatible None assignments, missing return types
- **Fixes**:
  - Change `compressor: CompressorSettings = None` → `Optional[CompressorSettings] = None`
  - Add return type annotations

---

## Phase 2: High-Priority Backend Modules

### Priority 4: `auralis-web/backend/chunked_processor.py`
- **Current Status**: 66 errors
- **File Size**: 1067 lines
- **Effort**: ~2-3 hours
- **Fixes**:
  - Generic type parameters: `Optional[dict]` → `Optional[Dict[str, Any]]`
  - Missing return type annotations on all methods
  - Fix function parameter type annotations

### Priority 5: `auralis/library/manager.py`
- **Current Status**: 44 errors
- **Effort**: ~1.5 hours
- **Fixes**:
  - Method return type annotations
  - Parameter type annotations on complex methods

### Priority 6: `auralis-web/backend/routers/player.py`
- **Current Status**: 43 errors
- **Effort**: ~1.5 hours
- **Fixes**: FastAPI endpoint type annotations

### Priority 7: `auralis/player/enhanced_audio_player.py`
- **Current Status**: 40 errors
- **Effort**: ~1.5 hours

### Priority 8: `auralis/core/hybrid_processor.py`
- **Current Status**: 32 errors
- **Effort**: ~1.5 hours

---

## Phase 3: Medium-Priority Modules

- `auralis/library/models/core.py` (30 errors)
- `auralis-web/backend/processing_engine.py` (30 errors)
- `auralis/optimization/parallel_processor.py` (29 errors)
- `auralis/core/processing/base_processing_mode.py` (29 errors)
- `auralis/library/metadata_editor/writers.py` (28 errors)
- `auralis/library/fingerprint_queue.py` (28 errors)
- `auralis-web/backend/state_manager.py` (27 errors)

---

## Expected Cascading Impact

**Before Phase 1**: 1761 errors
**After Priority 0 (logging.py)**: Estimate ~900-1000 errors (300+ reduction)
**After Priority 1-3 (config + player + dynamics)**: Estimate ~700-800 errors
**After Phase 2 (top 5 backend modules)**: Estimate ~400-500 errors
**After Phase 3**: Estimate <100 errors

---

## Implementation Steps

### Step 1: Setup (5 minutes)
```bash
# Verify mypy output format
mypy auralis/utils/logging.py --show-error-codes --pretty

# Create branch for tracking
git checkout -b feat/mypy-coverage-phase1
```

### Step 2: Execute Phase 1 (1-2 hours)
- Fix each Priority 0 module one at a time
- After each fix, run mypy to verify error reduction
- Commit after each module passes

### Step 3: Execute Phase 2 (6-8 hours)
- Batch fixes by error pattern
- Group chunked_processor, manager, routers together
- Test each module

### Step 4: Execute Phase 3 (4-6 hours)
- Fix remaining medium-priority modules
- Run full test suite: `python -m pytest tests/ -v`

### Step 5: Verification
```bash
# Full check
mypy auralis/ auralis-web/backend/ --ignore-missing-imports

# Ensure tests still pass
make test
```

---

## Common Type Annotation Patterns

### Missing Return Types
```python
# ❌ Wrong
def set_target(self, target: float):
    self.target = target

# ✅ Correct
def set_target(self, target: float) -> None:
    self.target = target
```

### Generic Type Parameters
```python
# ❌ Wrong
def get_presets() -> list:
def get_targets() -> dict:

# ✅ Correct
from typing import List, Dict, Any
def get_presets() -> List[str]:
def get_targets() -> Dict[str, Any]:
```

### Optional Type Assignments
```python
# ❌ Wrong
compressor: CompressorSettings = None

# ✅ Correct
from typing import Optional
compressor: Optional[CompressorSettings] = None
```

### **kwargs Type Annotation
```python
# ❌ Wrong
def is_compliant(self, standard: str, **kwargs) -> bool:

# ✅ Correct
from typing import Any
def is_compliant(self, standard: str, **kwargs: Any) -> bool:
```

---

## Success Criteria

- [ ] All Priority 0-1 modules pass mypy check
- [ ] All Priority 2-3 modules pass mypy check
- [ ] Total errors reduced to <50
- [ ] All tests pass: `make test`
- [ ] No regression in code functionality
- [ ] Type annotations follow project conventions

---

## Risk Assessment

**Low Risk**: These are type annotation additions only, no logic changes
- Fixes are mechanical (adding type hints, not changing behavior)
- Full test coverage exists (850+ tests)
- Changes can be reviewed incrementally by module

**Mitigation**: After each phase, run `make test` to catch any regressions
