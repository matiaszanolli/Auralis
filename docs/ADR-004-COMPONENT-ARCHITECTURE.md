# ADR-004: Component Size and Architecture Limits

**Status**: Accepted
**Date**: 2024-11-28
**Author**: Architecture Team
**Decision**: Enforce 300-line limit per component/module with clear separation of concerns
**Applies To**: All Python modules and React components in the modernized codebase

---

## Context

Both the current backend and frontend codebase have monolithic components that:
- Are difficult to understand (too many responsibilities)
- Are hard to test (mixing concerns)
- Create merge conflicts (large files, multiple changes)
- Are slow to render (React components with too much logic)
- Accumulate technical debt (band-aids and workarounds)

Examples from current codebase:
- Frontend components: 500-1000+ lines
- Backend modules: 400+ lines
- Business logic mixed with UI/API handling
- Monolithic classes with 20+ methods

---

## Decision

### Line Limits

#### Python Backend: 300 Lines Maximum
```
300 lines = ~12 average functions/classes
            = 1 clear responsibility per module
            = 15-20 minutes to understand
            = Easy to test
            = Favorable for refactoring
```

#### React Components: 300 Lines Maximum
```
300 lines = ~15 JSX blocks
           = 1-2 features per component
           = Handles 1 responsibility
           = < 16ms render time
           = Testable with 2-3 test cases
```

### Definition of "Lines"

**Count**:
- ✅ Code lines (logic, JSX, imports)
- ✅ Blank lines (within module)
- ✅ Type definitions (Python, TypeScript)

**Exclude**:
- ❌ Comments (standalone comment lines)
- ❌ Docstrings (module-level)
- ❌ Blank lines between sections (top-level)

```python
# NOT counted
"""Module docstring.

Multi-line docstring explaining the module.
"""

# Counted
import os  # 1 line

class MyClass:  # 1 line
    """Class docstring."""  # Not counted

    def method(self):  # 1 line
        x = 1  # 1 line
        return x  # 1 line
# Total: 5 lines (docstrings not counted)
```

### Separation of Concerns

#### Python Backend Layers

```
Layer 1: API Endpoints (FastAPI routes)
├─ Request validation
├─ Response formatting
└─ Error handling
    ↓
Layer 2: Service/Business Logic
├─ Core algorithms
├─ State management
└─ Domain logic
    ↓
Layer 3: Data Access (Repositories)
├─ Query construction
├─ Database operations
└─ Result transformation
    ↓
Layer 4: Infrastructure
├─ Caching
├─ Logging
└─ Configuration
```

**Module per layer**:
```python
# ✅ Good (separation of concerns)
auralis/
├── core/
│   ├── processor.py      (Layer 2: Business logic)
│   └── analysis.py       (Layer 2: Analysis logic)
├── library/
│   ├── manager.py        (Layer 2: Library management)
│   └── repositories/
│       ├── track_repository.py  (Layer 3: Data access)
│       └── artist_repository.py (Layer 3: Data access)
└── optimization/
    ├── caching/
    │   ├── smart_cache.py (Layer 4: Infrastructure)
    │   └── fingerprint_cache.py

auralis_web/backend/
├── routers/
│   ├── player.py         (Layer 1: API)
│   ├── queue.py          (Layer 1: API)
│   └── library.py        (Layer 1: API)
├── schemas/
│   └── models.py         (Layer 1: Request/Response)
└── services/
    ├── player_service.py (Layer 2: Business logic)
    └── queue_service.py

# ❌ Bad (mixing layers)
monolithic/
└── everything.py  (500 lines: API + logic + DB + caching)
```

#### React Component Layers

```
Layer 1: Pages/Screens
├─ Route handling
├─ Feature orchestration
└─ Layout
    ↓
Layer 2: Container Components
├─ Redux connection
├─ Data fetching
└─ Props preparation
    ↓
Layer 3: Presentational Components
├─ Rendering only
├─ No side effects
└─ Prop-driven
    ↓
Layer 4: Base Components (Design System)
├─ Button, Input, Modal, etc.
└─ Design token usage
```

**Component per layer**:
```typescript
// ✅ Good (separation of concerns)
src/
├── pages/
│   ├── Player.tsx        (Layer 1: Page orchestration)
│   └── Library.tsx
├── features/
│   ├── player/
│   │   ├── PlayerContainer.tsx  (Layer 2: Redux connection)
│   │   └── PlayerControls.tsx   (Layer 3: Presentation)
│   ├── queue/
│   │   ├── QueueContainer.tsx   (Layer 2)
│   │   └── QueueDisplay.tsx     (Layer 3)
│   └── library/
│       ├── LibraryContainer.tsx (Layer 2)
│       └── LibraryBrowser.tsx   (Layer 3)
└── components/
    └── Common/
        ├── Button.tsx           (Layer 4: Base)
        ├── Modal.tsx
        └── Input.tsx

// ❌ Bad (mixing layers)
monolithic/
├── PlayerPage.tsx  (500 lines: page + container + presentation + styles)
└── LibraryPage.tsx (600 lines)
```

### Component Responsibilities

#### Python Module: Single Responsibility

```python
# ✅ Good (single responsibility)
class FingerprintValidator:
    """Validate fingerprint accuracy."""

    def validate_fingerprint_pair(
        self,
        streaming: Dict[str, float],
        batch: Dict[str, float],
    ) -> ValidationResult:
        """Validate fingerprint against batch version."""
        similarity = self._cosine_similarity(streaming, batch)
        accuracy = self._calculate_accuracy(streaming, batch)
        confidence = self._assess_confidence(similarity, accuracy)
        return ValidationResult(similarity, accuracy, confidence)

    def _cosine_similarity(self, a: Dict, b: Dict) -> float:
        """Calculate cosine similarity."""
        # Implementation

# ❌ Bad (multiple responsibilities)
class FingerprintProcessor:
    """Do everything with fingerprints."""

    def validate_fingerprint(self, ...):
        # Fingerprint validation
        pass

    def cache_fingerprint(self, ...):
        # Caching logic
        pass

    def analyze_fingerprint(self, ...):
        # Analysis logic
        pass

    def serialize_fingerprint(self, ...):
        # Serialization logic
        pass

    def sync_fingerprint(self, ...):
        # Network sync logic
        pass
    # 5 different responsibilities!
```

#### React Component: Single Visual Responsibility

```typescript
// ✅ Good (single responsibility)
interface PlayerControlsProps {
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
}

export function PlayerControls({
  isPlaying,
  onPlay,
  onPause,
}: PlayerControlsProps): JSX.Element {
  return (
    <div className="player-controls">
      {isPlaying ? (
        <button onClick={onPause}>⏸ Pause</button>
      ) : (
        <button onClick={onPlay}>▶ Play</button>
      )}
    </div>
  );
}

// ❌ Bad (multiple visual responsibilities)
export function PlayerPage(): JSX.Element {
  // Player controls rendering
  // Queue display
  // Library browser
  // Settings panel
  // Search bar
  // Keyboard shortcuts
  // WebSocket subscription
  // Redux dispatch
  // Local state management
  // ...
  // 500+ lines!
}
```

### When to Split a Module/Component

**Split immediately when**:
- Exceeding 300 lines
- Multiple responsibilities (use "and" test: "validates AND caches")
- Hard to test (more than 3 test files)
- Multiple classes/functions (> 5 functions)

**Split approach**:
1. Identify logical units (validation, caching, serialization, etc.)
2. Create separate modules/components for each unit
3. Use dependency injection to wire together
4. Use `__init__.py` or barrel exports for public interface

```python
# BEFORE: validator.py (350 lines)
class FingerprintValidator:
    def validate(self, ...):
        # 100 lines
        pass

    def cache_result(self, ...):
        # 100 lines
        pass

    def serialize(self, ...):
        # 100 lines
        pass

# AFTER: Split into modules
# validator/
# ├── __init__.py
# ├── validator.py (100 lines - core validation)
# ├── caching.py (100 lines - result caching)
# └── serialization.py (100 lines - serialization)

# validator/__init__.py
from .validator import FingerprintValidator
from .caching import ValidationCache
from .serialization import ValidationSerializer

__all__ = [
    'FingerprintValidator',
    'ValidationCache',
    'ValidationSerializer',
]

# Usage remains the same
from auralis.library.validation import FingerprintValidator
validator = FingerprintValidator()
```

---

## Metrics & Enforcement

### Line Count Measurement

```bash
# Python modules
find auralis/ -name "*.py" -exec wc -l {} + | sort -rn | head -20

# React components
find src/components -name "*.tsx" -exec wc -l {} + | sort -rn | head -20
```

### Automated Checks

```yaml
# .github/workflows/lint.yml
- name: Check module sizes
  run: |
    python scripts/check_module_sizes.py auralis/ --max-lines 300
    python scripts/check_component_sizes.py src/components --max-lines 300
```

### Pre-commit Hook

```bash
# .githooks/pre-commit
#!/bin/bash
MAX_LINES=300

# Check Python modules
for file in $(git diff --cached --name-only --diff-filter=A auralis/**/*.py); do
    lines=$(wc -l < "$file")
    if [ $lines -gt $MAX_LINES ]; then
        echo "ERROR: $file exceeds $MAX_LINES lines ($lines)"
        exit 1
    fi
done

# Check React components
for file in $(git diff --cached --name-only --diff-filter=A src/components/**/*.tsx); do
    lines=$(wc -l < "$file")
    if [ $lines -gt $MAX_LINES ]; then
        echo "ERROR: $file exceeds $MAX_LINES lines ($lines)"
        exit 1
    fi
done
```

---

## Code Organization Patterns

### Python: Repository Pattern

```python
# auralis/library/repositories/
# ├── __init__.py
# ├── base_repository.py   (100 lines)
# ├── track_repository.py  (150 lines)
# ├── artist_repository.py (120 lines)
# └── playlist_repository.py (130 lines)

# base_repository.py
class BaseRepository:
    """Base repository with common CRUD operations."""

    def __init__(self, db):
        self.db = db

    def create(self, entity: T) -> T:
        pass

    def read(self, id: Any) -> Optional[T]:
        pass

    def update(self, id: Any, entity: T) -> T:
        pass

    def delete(self, id: Any) -> bool:
        pass

# track_repository.py
class TrackRepository(BaseRepository):
    """Track-specific queries."""

    def search(self, query: str) -> List[Track]:
        pass

    def get_by_artist(self, artist_id: str) -> List[Track]:
        pass

    def get_popular(self, limit: int) -> List[Track]:
        pass
```

### React: Container + Presentational

```typescript
// features/player/PlayerContainer.tsx (100 lines)
import { usePlayer } from '@/hooks/usePlayer';
import { PlayerControls } from './PlayerControls';

export function PlayerContainer(): JSX.Element {
  const { isPlaying, onPlay, onPause } = usePlayer();

  return <PlayerControls isPlaying={isPlaying} onPlay={onPlay} onPause={onPause} />;
}

// features/player/PlayerControls.tsx (80 lines)
interface PlayerControlsProps {
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
}

export function PlayerControls({
  isPlaying,
  onPlay,
  onPause,
}: PlayerControlsProps): JSX.Element {
  return (
    <button onClick={isPlaying ? onPause : onPlay}>
      {isPlaying ? '⏸ Pause' : '▶ Play'}
    </button>
  );
}
```

---

## Consequences

### Positive
- ✅ Modules are easier to understand (15-20 min read)
- ✅ Tests are faster to write (2-3 tests per module)
- ✅ Merge conflicts reduced (smaller files)
- ✅ Refactoring is safer (less coupling)
- ✅ Performance is better (smaller bundles, faster renders)
- ✅ Maintenance is easier (clear responsibility)
- ✅ Onboarding is faster (less complexity)

### Trade-offs
- ⚠️ More files (harder to navigate initially)
- ⚠️ More imports (duplication of concerns across layers)
- ⚠️ Dependency injection complexity (wiring modules together)

### Mitigations
- Organize in logical directories
- Use barrel exports (`__init__.py`, index.ts) for grouping
- Provide clear architecture documentation
- Use IDE features (Go to definition, Outline)

---

## Examples: Before & After

### Example 1: Python - Fingerprint Validator

**BEFORE** (350 lines - too big):
```python
# fingerprint.py (350 lines)
class FingerprintValidator:
    def __init__(self):
        self.cache = {}
        self.metrics = []

    def validate_fingerprint(self, a, b):
        # 50 lines of validation logic
        pass

    def cache_result(self, key, value):
        # 50 lines of caching
        self.cache[key] = value
        self.cleanup_cache()
        pass

    def cleanup_cache(self):
        # 50 lines of cleanup
        pass

    def serialize(self, data):
        # 50 lines of serialization
        pass

    def deserialize(self, data):
        # 50 lines of deserialization
        pass

    def log_metrics(self):
        # 50 lines of metrics logging
        pass
```

**AFTER** (split into modules):
```python
# fingerprint/
# ├── __init__.py
# ├── validator.py     (100 lines)
# ├── cache.py         (100 lines)
# └── metrics.py       (80 lines)

# fingerprint/__init__.py
from .validator import FingerprintValidator
from .cache import FingerprintCache
from .metrics import MetricsCollector

# fingerprint/validator.py
class FingerprintValidator:
    def __init__(self, cache: FingerprintCache):
        self.cache = cache

    def validate_fingerprint(self, a: Dict, b: Dict) -> ValidationResult:
        # Core validation logic only
        pass

# fingerprint/cache.py
class FingerprintCache:
    def get(self, key: str):
        pass

    def set(self, key: str, value: Any):
        pass

    def cleanup(self):
        pass

# fingerprint/metrics.py
class MetricsCollector:
    def collect_validation_metrics(self, result):
        pass

    def report(self):
        pass
```

### Example 2: React - Player Page

**BEFORE** (600 lines - too big):
```typescript
// pages/Player.tsx (600 lines)
export function Player(): JSX.Element {
  // Player state (100 lines)
  const [isPlaying, setIsPlaying] = useState(false);
  // ... more state

  // Player effects (100 lines)
  useEffect(() => {
    // ... playback logic
  }, []);
  // ... more effects

  // Player controls rendering (50 lines)
  const renderControls = () => {
    // ...
  };

  // Queue rendering (100 lines)
  const renderQueue = () => {
    // ...
  };

  // Library rendering (100 lines)
  const renderLibrary = () => {
    // ...
  };

  // Settings rendering (50 lines)
  const renderSettings = () => {
    // ...
  };

  return (
    <div>
      {renderControls()}
      {renderQueue()}
      {renderLibrary()}
      {renderSettings()}
    </div>
  );
}
```

**AFTER** (split into components):
```typescript
// pages/Player.tsx (80 lines)
export function Player(): JSX.Element {
  return (
    <div className="player-page">
      <PlayerSection />
      <QueueSection />
      <LibrarySection />
      <SettingsSection />
    </div>
  );
}

// features/player/PlayerSection.tsx (120 lines)
export function PlayerSection(): JSX.Element {
  const { isPlaying, onPlay, onPause } = usePlayer();

  return (
    <section className="player">
      <PlayerControls isPlaying={isPlaying} onPlay={onPlay} onPause={onPause} />
      {/* ... */}
    </section>
  );
}

// features/queue/QueueSection.tsx (150 lines)
export function QueueSection(): JSX.Element {
  const { tracks, currentIndex } = useQueue();

  return (
    <section className="queue">
      <VirtualizedQueue tracks={tracks} currentIndex={currentIndex} />
    </section>
  );
}

// features/library/LibrarySection.tsx (140 lines)
export function LibrarySection(): JSX.Element {
  const { query, setQuery, results } = useLibrarySearch();

  return (
    <section className="library">
      <SearchBar query={query} onQueryChange={setQuery} />
      <TrackGrid tracks={results} />
    </section>
  );
}
```

---

## Review Checklist

Before committing code:

- [ ] Module/component ≤ 300 lines (excluding comments)
- [ ] Single, clear responsibility
- [ ] Easy to test (3-5 test cases max)
- [ ] Clear imports from other modules
- [ ] Public interface documented
- [ ] No data access in presentation
- [ ] No business logic in API layer
- [ ] Appropriately named file
- [ ] Located in correct directory

---

## Related Decisions
- ADR-001: React 18 + TypeScript + Redux Toolkit Stack
- ADR-002: Phase 7.5 Cache Integration Architecture
- ADR-003: WebSocket Message Protocol Design

---

## References
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single_responsibility_principle)
- [Clean Code by Robert Martin](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [React Component Best Practices](https://react.dev/learn)
- [Python Design Patterns](https://refactoring.guru/design-patterns/python)

---

**Next Review**: After Phase C.1 project setup (Week 6)
**Last Updated**: 2024-11-28
