# Development Standards & Guidelines

**Version**: 1.0.0
**Date Created**: 2024-11-28
**Status**: Active
**Scope**: All Python backend and TypeScript frontend development

---

## Table of Contents

1. [Overview](#overview)
2. [Python Backend Standards](#python-backend-standards)
3. [TypeScript Frontend Standards](#typescript-frontend-standards)
4. [Git & Version Control](#git--version-control)
5. [Testing Standards](#testing-standards)
6. [Database Standards](#database-standards)
7. [Design System & UI Standards](#design-system--ui-standards)
8. [API Standards](#api-standards)
9. [Performance & Optimization](#performance--optimization)
10. [Security Standards](#security-standards)
11. [Documentation Standards](#documentation-standards)

---

## Overview

This document establishes mandatory standards for all code contributions to the Auralis project. These standards ensure:

- **Consistency**: Code looks and feels like one project
- **Maintainability**: Future developers can understand and modify code
- **Quality**: Reduced bugs, better performance, fewer surprises
- **Collaboration**: Team works efficiently with shared conventions
- **Scalability**: Architecture supports growth without major refactors

### Core Principles

1. **Clarity Over Cleverness**: Code should be obvious, not clever
2. **Modular Design**: Small, single-purpose modules
3. **Defensive Programming**: Validate inputs, handle errors gracefully
4. **Test-Driven**: Tests document behavior and prevent regressions
5. **Performance Conscious**: Optimize hot paths, measure before optimizing
6. **Accessibility First**: WCAG AA compliance, keyboard navigation

---

## Python Backend Standards

### Module Organization

**File Size Limit**: Maximum 300 lines per module (excluding blank lines and docstrings)

**Rationale**: Modules over 300 lines are typically doing multiple things and become harder to understand, test, and maintain.

**Pattern**:
```
auralis/
├── core/
│   ├── __init__.py
│   ├── hybrid_processor.py  (core processing logic)
│   └── streaming.py         (streaming infrastructure)
├── analysis/
│   ├── __init__.py
│   ├── fingerprint.py       (fingerprint generation)
│   └── spectral.py          (spectral analysis)
└── library/
    ├── __init__.py
    ├── manager.py           (library management)
    └── repositories/
        ├── __init__.py
        └── track_repository.py
```

**If a module exceeds 300 lines**:
1. Identify logical units within the module
2. Split into separate files (one unit per file)
3. Use `__init__.py` to expose public interfaces
4. Update all imports

Example:
```python
# OLD: processor.py (350 lines - too big)
class AudioProcessor:
    # 100 lines of audio processing
    pass

class ParameterValidator:
    # 150 lines of validation
    pass

class MetricsCollector:
    # 100 lines of metrics collection
    pass

# NEW: Split into 3 modules
# processor.py (core processing)
# validator.py (parameter validation)
# metrics.py (metrics collection)

# processor/__init__.py
from .core import AudioProcessor
from .validator import ParameterValidator
from .metrics import MetricsCollector

__all__ = ['AudioProcessor', 'ParameterValidator', 'MetricsCollector']
```

### Naming Conventions

**Functions**: `snake_case`
```python
# ✅ Good
def calculate_fingerprint(audio_data: np.ndarray) -> Dict[str, float]:
    pass

def get_track_by_id(track_id: int) -> Optional[Track]:
    pass

# ❌ Bad
def CalculateFingerprint(audioData):
    pass

def getTrackByID(trackID):
    pass
```

**Classes**: `PascalCase`
```python
# ✅ Good
class FingerprintValidator:
    def validate(self) -> bool:
        pass

class SmartCache:
    def get(self, key: str) -> Optional[Any]:
        pass

# ❌ Bad
class fingerprint_validator:
    pass

class smart_cache:
    pass
```

**Constants**: `UPPER_SNAKE_CASE`
```python
# ✅ Good
DEFAULT_SAMPLE_RATE = 44100
MAX_CACHE_SIZE_MB = 256
FINGERPRINT_DIMENSIONS = 25

# ❌ Bad
defaultSampleRate = 44100
max_cache_size = 256
```

**Private/Internal**: Leading underscore
```python
# ✅ Good
class Analyzer:
    def analyze(self) -> List[float]:
        return self._compute_features()

    def _compute_features(self) -> List[float]:
        # Internal method, only called within class
        pass

# ❌ Bad
class Analyzer:
    def analyze(self) -> List[float]:
        return self.compute_features()  # Looks public
```

### Imports

**Order** (separated by blank lines):
1. `__future__` imports
2. Standard library (os, sys, json, etc.)
3. Third-party (numpy, pydantic, etc.)
4. Local/relative imports

```python
# ✅ Good
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel

from auralis.core import AudioProcessor
from auralis.library import LibraryManager
from .validator import FingerprintValidator

# ❌ Bad
import numpy as np
from auralis.core import AudioProcessor
import os
from .validator import FingerprintValidator
from pydantic import BaseModel
import sys
```

**Use specific imports**:
```python
# ✅ Good
from pathlib import Path
from typing import Dict, Optional

path = Path('file.txt')
data: Dict[str, int] = {}

# ⚠️ Less clear (circular/namespace pollution)
from pathlib import *
import typing

# ❌ Bad (star imports)
from auralis.core import *  # What's imported?
```

### Type Hints

**Mandatory** for all public function signatures:

```python
# ✅ Good
def search_tracks(
    query: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Track]:
    """Search library for matching tracks.

    Args:
        query: Search query string
        limit: Maximum results (1-500)
        offset: Result offset for pagination

    Returns:
        List of matching Track objects (sorted by relevance)

    Raises:
        ValueError: If query is empty
        ValueError: If limit > 500
    """
    if not query:
        raise ValueError("query cannot be empty")
    if limit > 500:
        raise ValueError("limit must be <= 500")

    # Implementation
    return []

# ❌ Bad (no types)
def search_tracks(query, limit=50, offset=0):
    # What types are these?
    # What's the return type?
    pass
```

**Generic types**:
```python
# ✅ Good
from typing import Dict, List, Optional, Tuple

def get_stats(self) -> Dict[str, float]:
    return {'avg': 0.5, 'max': 1.0}

def find_similar(self, fingerprint: List[float]) -> Tuple[str, float]:
    return ('track_id', 0.95)

def get_optional(self, key: str) -> Optional[str]:
    return self.data.get(key)

# ❌ Bad (implicit types)
def get_stats(self):
    return {'avg': 0.5}
```

**Use `from __future__ import annotations`** for forward references:

```python
# ✅ Good (use string annotations)
from __future__ import annotations

class Node:
    def __init__(self, value: int, next: Node | None = None):
        self.value = value
        self.next = next

# ❌ Bad (without __future__ import)
class Node:
    def __init__(self, value: int, next: 'Node | None' = None):
        # Need string quotes for forward ref
        pass
```

### Docstrings

**Format**: Google style (3 blank lines after imports, summary first)

```python
def calculate_fingerprint(
    audio_data: np.ndarray,
    sample_rate: int = 44100,
) -> Dict[str, List[float]]:
    """Calculate audio fingerprint with streaming analysis.

    Analyzes audio in chunks to compute a 25-dimensional fingerprint
    suitable for matching and similarity detection.

    Args:
        audio_data: Audio samples as numpy array (float32/float64)
        sample_rate: Sample rate in Hz (default: 44100)

    Returns:
        Dictionary with fingerprint data:
        {
            'frequencies': [...],      # 13 frequency bands
            'energy': [...],           # 13 energy values
            'spectral_flux': [...],    # 13 spectral flux values
            'timestamp': 0.0           # Processing timestamp
        }

    Raises:
        ValueError: If audio_data is empty
        ValueError: If sample_rate < 8000 or > 192000

    Example:
        >>> audio = np.random.randn(44100)  # 1 second
        >>> fp = calculate_fingerprint(audio, sample_rate=44100)
        >>> len(fp['frequencies'])
        13

    Note:
        This function processes audio in 512-sample chunks.
        For real-time processing, consider streaming_fingerprint().
    """
    if audio_data.size == 0:
        raise ValueError("audio_data cannot be empty")
    if sample_rate < 8000 or sample_rate > 192000:
        raise ValueError(f"sample_rate must be 8000-192000, got {sample_rate}")

    # Implementation
    return {}
```

**Sections** (in order):
1. **Summary**: One line (ends with period)
2. **Description**: Longer explanation (2-3 sentences)
3. **Args**: Parameter descriptions with types
4. **Returns**: Return value description and structure
5. **Raises**: Exceptions that can be raised
6. **Example**: Usage example (if public API)
7. **Note**: Additional context (if needed)

### Error Handling

**Create custom exceptions**:
```python
# ✅ Good
class AudioProcessingError(Exception):
    """Raised when audio processing fails."""
    pass

class FingerprintValidationError(Exception):
    """Raised when fingerprint validation fails."""
    pass

class CacheError(Exception):
    """Raised when cache operation fails."""
    pass

# Use them
try:
    fingerprint = calculate_fingerprint(audio)
except AudioProcessingError as e:
    logger.error(f"Failed to process audio: {e}")
    raise

# ❌ Bad (generic exceptions)
try:
    fingerprint = calculate_fingerprint(audio)
except Exception:
    pass  # Silent failure - very bad
```

**Validate inputs early**:
```python
# ✅ Good (fail fast)
def process_audio(
    audio_data: np.ndarray,
    gain: float,
) -> np.ndarray:
    """Process audio with gain adjustment."""
    # Validate early
    if not isinstance(audio_data, np.ndarray):
        raise TypeError(f"Expected np.ndarray, got {type(audio_data)}")

    if audio_data.dtype not in [np.float32, np.float64]:
        raise ValueError(f"Expected float32/64, got {audio_data.dtype}")

    if audio_data.size == 0:
        raise ValueError("audio_data cannot be empty")

    if not isinstance(gain, (int, float)):
        raise TypeError(f"gain must be numeric, got {type(gain)}")

    if gain < 0 or gain > 10:
        raise ValueError(f"gain must be 0-10, got {gain}")

    # Now process with confidence
    output = audio_data.copy() * gain
    return output

# ❌ Bad (validate during processing)
def process_audio(audio_data, gain):
    result = audio_data.copy()
    result *= gain  # Crashes if audio_data not array
    return result
```

**Logging over silent failures**:
```python
# ✅ Good (log failures)
def get_cache_value(key: str) -> Optional[Any]:
    """Get value from cache."""
    try:
        return self.cache.get(key)
    except Exception as e:
        logger.warning(f"Cache retrieval failed for key '{key}': {e}")
        return None  # Graceful degradation

# ❌ Bad (silent failure)
def get_cache_value(key):
    try:
        return self.cache.get(key)
    except:
        return None  # Silent - very hard to debug
```

### Logging

**Always use the logger from auralis.utils.logging**:

```python
from auralis.utils.logging import debug, info, warning, error

# ✅ Good
def initialize_cache(max_size_mb: int) -> SmartCache:
    """Initialize cache system."""
    debug(f"Initializing cache with {max_size_mb}MB capacity")

    cache = SmartCache(max_size_mb=max_size_mb)
    info(f"Cache initialized: {max_size_mb}MB, TTL: 300s")

    return cache

def validate_fingerprint(fp: Dict) -> bool:
    """Validate fingerprint structure."""
    if not fp.get('frequencies'):
        warning(f"Fingerprint missing 'frequencies' data")
        return False

    if len(fp['frequencies']) != 13:
        error(f"Invalid frequencies dimension: {len(fp['frequencies'])}")
        return False

    return True

# ❌ Bad (print or no logging)
def initialize_cache(max_size_mb):
    print(f"Initializing cache...")  # Not structured
    cache = SmartCache(max_size_mb)
    return cache
```

**Log levels**:
- `debug()`: Detailed diagnostic info (development)
- `info()`: Confirmation that something happened
- `warning()`: Something unexpected, but recoverable
- `error()`: Serious error, operation failed
- `critical()`: System is unusable

### Code Comments

**Comment the 'why', not the 'what'**:

```python
# ✅ Good (explains reasoning)
def calculate_fingerprint_streaming(
    audio_data: np.ndarray,
    chunk_size: int = 2048,
) -> Generator[Dict[str, float], None, None]:
    """Generate fingerprints for audio chunks.

    Processes audio in streaming fashion to support real-time
    fingerprinting and reduce memory overhead for large files.
    """
    # Use 50% overlap between chunks to smooth boundaries
    # and capture transitions more accurately
    hop_size = chunk_size // 2

    for i in range(0, len(audio_data) - chunk_size, hop_size):
        chunk = audio_data[i : i + chunk_size]
        # Windowing reduces spectral leakage at chunk boundaries
        window = np.hanning(chunk_size)
        windowed = chunk * window
        yield compute_features(windowed)

# ❌ Bad (explains implementation)
def calculate_fingerprint_streaming(audio_data, chunk_size=2048):
    hop_size = chunk_size // 2  # hop_size = 1024

    for i in range(0, len(audio_data) - chunk_size, hop_size):
        chunk = audio_data[i : i + chunk_size]  # Get chunk
        window = np.hanning(chunk_size)  # Create Hanning window
        windowed = chunk * window  # Apply window
        yield compute_features(windowed)  # Compute features
```

**Avoid redundant comments**:
```python
# ❌ Bad (obvious)
x = 1  # Set x to 1
result = []  # Create empty list
counter += 1  # Increment counter

# ✅ Good (adds value)
# Use 1-based indexing to match user-facing track numbers
x = 1

# Collect results in order before batch processing
# (improves cache locality vs. processing individually)
result = []

# Skip first track (it's the theme song)
counter += 1
```

### Python Anti-Patterns to Avoid

**1. Bare except**:
```python
# ❌ Bad
try:
    process_audio()
except:  # Catches everything, including SystemExit
    pass

# ✅ Good
try:
    process_audio()
except AudioProcessingError as e:
    logger.error(f"Processing failed: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

**2. Mutable default arguments**:
```python
# ❌ Bad (list shared across calls!)
def add_track(track, queue=[]):
    queue.append(track)
    return queue

# First call
queue1 = add_track('song1')  # ['song1']

# Second call (different list intended!)
queue2 = add_track('song2')  # ['song1', 'song2'] - BUG!

# ✅ Good
def add_track(track, queue=None):
    if queue is None:
        queue = []
    queue.append(track)
    return queue
```

**3. Not closing resources**:
```python
# ❌ Bad (file not closed)
def read_config(path: str) -> Dict:
    f = open(path)
    config = json.load(f)
    return config  # File handle leaked!

# ✅ Good (context manager)
def read_config(path: str) -> Dict:
    with open(path) as f:
        config = json.load(f)
    return config  # File automatically closed
```

**4. Type ignores**:
```python
# ❌ Bad (hiding problems)
result = some_function()  # type: ignore

# ✅ Good (fix the actual issue)
# If some_function doesn't have types, add them
# If it returns wrong type, adjust calling code
result = some_function()  # Now with proper types
```

---

## TypeScript Frontend Standards

### Component Organization

**File Size Limit**: Maximum 300 lines per component

**Structure**:
```
src/
├── components/
│   ├── Player/
│   │   ├── PlayerControls.tsx     (< 300 lines)
│   │   ├── PlayerControls.test.tsx
│   │   ├── types.ts               (Player types)
│   │   └── hooks.ts               (Player hooks)
│   ├── Queue/
│   │   ├── QueueDisplay.tsx
│   │   ├── VirtualizedQueue.tsx
│   │   └── Queue.test.tsx
│   └── Common/
│       ├── Button.tsx
│       ├── Modal.tsx
│       └── ErrorBoundary.tsx
├── features/
│   ├── player/
│   │   ├── playerSlice.ts
│   │   ├── playerSelectors.ts
│   │   └── hooks.ts
│   └── queue/
│       ├── queueSlice.ts
│       └── hooks.ts
├── hooks/
│   ├── usePlayer.ts
│   ├── useQueue.ts
│   └── useWebSocket.ts
└── services/
    ├── api.ts
    └── cache.ts
```

### Naming Conventions

**Components**: `PascalCase`
```typescript
// ✅ Good
export function PlayerControls(): JSX.Element {
  return <div>...</div>;
}

export function VirtualizedQueue(): JSX.Element {
  return <div>...</div>;
}

// ❌ Bad
export function playerControls(): JSX.Element {
  return <div>...</div>;
}

export function virtual_queue(): JSX.Element {
  return <div>...</div>;
}
```

**Hooks**: `useXxx`
```typescript
// ✅ Good
export function usePlayer(): PlayerState {
  // ...
}

export function useQueue(): QueueContextType {
  // ...
}

// ❌ Bad
export function playerHook(): PlayerState {
  // ...
}

export function getQueue(): QueueContextType {
  // ...
}
```

**Utilities/Functions**: `camelCase`
```typescript
// ✅ Good
export function formatDuration(ms: number): string {
  return `${Math.floor(ms / 1000)}s`;
}

export function debounce<T extends any[]>(
  fn: (...args: T) => void,
  delay: number,
): (...args: T) => void {
  // ...
}

// ❌ Bad
export function FormatDuration(ms: number): string {
  // ...
}

export function Debounce<T extends any[]>(
  fn: (...args: T) => void,
  delay: number,
): (...args: T) => void {
  // ...
}
```

**Types/Interfaces**: `PascalCase`
```typescript
// ✅ Good
interface PlayerState {
  isPlaying: boolean;
  currentTrack: Track | null;
  position: number;
}

type TrackId = string & { readonly __brand: 'TrackId' };

export enum PlaybackMode {
  NORMAL = 'normal',
  REPEAT_ONE = 'repeat-one',
  SHUFFLE = 'shuffle',
}

// ❌ Bad
interface player_state {
  // ...
}

type trackId = string;
```

**Constants**: `UPPER_SNAKE_CASE`
```typescript
// ✅ Good
const DEFAULT_VOLUME = 0.8;
const MAX_QUEUE_SIZE = 5000;
const API_TIMEOUT_MS = 30000;

// ❌ Bad
const defaultVolume = 0.8;
const MaxQueueSize = 5000;
```

### Type Safety

**Always use strict TypeScript**:

```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitThis": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true
  }
}
```

**Avoid `any` type**:
```typescript
// ❌ Bad
function processData(data: any): any {
  return data.value * 2;  // No type checking
}

// ✅ Good
interface DataPoint {
  value: number;
}

function processData(data: DataPoint): number {
  return data.value * 2;
}
```

**Use union types and literals**:
```typescript
// ✅ Good
type PlaybackStatus = 'playing' | 'paused' | 'stopped';

interface Player {
  status: PlaybackStatus;
  volume: number; // 0-1
  queue: Track[];
}

function setStatus(status: PlaybackStatus): void {
  // Only valid statuses allowed
}

// ❌ Bad
interface Player {
  status: string;  // Could be anything
  volume: number;
}

function setStatus(status: string): void {
  // No validation - bug if invalid status passed
}
```

**Props interfaces**:
```typescript
// ✅ Good
interface PlayerButtonProps {
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}

export function PlayerButton({
  onClick,
  disabled = false,
  className = '',
}: PlayerButtonProps): JSX.Element {
  return (
    <button onClick={onClick} disabled={disabled} className={className}>
      Play
    </button>
  );
}

// ❌ Bad (no interface, implicit any)
export function PlayerButton(props: any): JSX.Element {
  return <button {...props}>Play</button>;
}

// ❌ Bad (scattered props)
export function PlayerButton(
  onClick: () => void,
  disabled?: boolean,
  className?: string,
): JSX.Element {
  // Hard to read with many props
}
```

### React Component Patterns

**Functional components only** (no class components):

```typescript
// ✅ Good
interface TrackListProps {
  tracks: Track[];
  onSelect: (track: Track) => void;
}

export function TrackList({ tracks, onSelect }: TrackListProps): JSX.Element {
  return (
    <div className="track-list">
      {tracks.map((track) => (
        <div key={track.id} onClick={() => onSelect(track)}>
          {track.title}
        </div>
      ))}
    </div>
  );
}

// ❌ Bad (class component)
export class TrackList extends React.Component {
  render() {
    return <div>...</div>;
  }
}
```

**Use hooks for state and effects**:

```typescript
// ✅ Good
export function Player(): JSX.Element {
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);

  useEffect(() => {
    const handlePlayback = () => {
      setPosition((prev) => prev + 1);
    };

    const interval = setInterval(handlePlayback, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <button onClick={() => setIsPlaying(!isPlaying)}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>
      <span>{position}s</span>
    </div>
  );
}

// ❌ Bad (not using hooks)
export class Player extends React.Component {
  state = { isPlaying: false, position: 0 };

  componentDidMount() {
    // ...
  }
}
```

**Keep components under 300 lines**:

If component exceeds 300 lines:
1. Extract sub-components
2. Move logic to custom hooks
3. Break into multiple files

```typescript
// OLD: PlayerPage.tsx (500 lines - too big)
export function PlayerPage(): JSX.Element {
  // 150 lines of player UI
  // 150 lines of queue UI
  // 150 lines of library UI
  // 50 lines of effects and logic
  return <div>...</div>;
}

// NEW: Split into components
// PlayerPage.tsx (< 100 lines - orchestration)
export function PlayerPage(): JSX.Element {
  const player = usePlayer();
  const queue = useQueue();

  return (
    <div>
      <PlayerSection player={player} />
      <QueueSection queue={queue} />
      <LibrarySection />
    </div>
  );
}

// PlayerSection.tsx (< 150 lines)
export function PlayerSection({ player }: PlayerSectionProps): JSX.Element {
  // Player-specific UI
  return <div>...</div>;
}

// QueueSection.tsx (< 150 lines)
export function QueueSection({ queue }: QueueSectionProps): JSX.Element {
  // Queue-specific UI
  return <div>...</div>;
}
```

### Design System Integration

**Always use design tokens** from `src/design-system/tokens.ts`:

```typescript
// ✅ Good
import { tokens } from '@/design-system';

export function Button({ children }: ButtonProps): JSX.Element {
  return (
    <button
      style={{
        color: tokens.colors.text.primary,
        backgroundColor: tokens.colors.button.background,
        padding: tokens.spacing.md,
        borderRadius: tokens.borderRadius.md,
        fontSize: tokens.typography.body.fontSize,
        fontFamily: tokens.typography.body.fontFamily,
      }}
    >
      {children}
    </button>
  );
}

// ❌ Bad (hardcoded values)
export function Button({ children }: ButtonProps): JSX.Element {
  return (
    <button
      style={{
        color: '#ffffff',
        backgroundColor: '#007bff',
        padding: '12px',
        borderRadius: '4px',
        fontSize: '14px',
        fontFamily: 'Inter',
      }}
    >
      {children}
    </button>
  );
}
```

### Testing

**File colocation**:
```
src/components/
├── Button.tsx
├── Button.test.tsx      ← Test file next to component
├── Button.stories.tsx   ← Storybook story
└── types.ts
```

**Test patterns**:

```typescript
import { render, screen } from '@/test/test-utils';
import { PlayerButton } from './PlayerButton';

describe('PlayerButton', () => {
  it('should render play button when not playing', () => {
    render(<PlayerButton onClick={vi.fn()} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    const onClick = vi.fn();
    render(<PlayerButton onClick={onClick} />);
    screen.getByRole('button').click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('should be disabled when disabled prop is true', () => {
    render(<PlayerButton onClick={vi.fn()} disabled={true} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  // Clean up subscriptions in afterEach
  afterEach(() => {
    vi.clearAllMocks();
  });
});
```

---

## Git & Version Control

### Commit Messages

**Format**: `type: description`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `perf`: Performance improvement
- `test`: Test additions/changes
- `docs`: Documentation changes
- `chore`: Maintenance (dependencies, config)

**Examples**:
```
feat: Add virtual scrolling to queue display

fix: Prevent memory leak in WebSocket subscription

refactor: Consolidate state management in Redux slices

perf: Optimize fingerprint calculation with vectorization

test: Add E2E tests for player controls

docs: Update API documentation with cache integration

chore: Update dependencies to latest versions
```

**Good practices**:
- First line: < 72 characters
- Second line: blank
- Body: Explain "why", not "what"
- Reference issues: `Fixes #123` or `Related to #456`

### Branch Naming

**Format**: `type/description`

**Examples**:
```
feature/virtual-scrolling
feature/phase-7-5-caching
fix/websocket-memory-leak
refactor/state-management
chore/update-dependencies
docs/api-documentation
```

### Pull Requests

**Requirements**:
- [ ] Description of changes
- [ ] Tests added/updated
- [ ] Documentation updated (if needed)
- [ ] Performance impact assessed
- [ ] Lighthouse check (if frontend)
- [ ] All CI/CD checks pass

**Review process**:
1. Request review from 2 team members (1 backend, 1 frontend)
2. Address all feedback
3. Squash merge to master

---

## Testing Standards

### Test Organization

**Structure**:
```
tests/
├── unit/
│   ├── test_fingerprint.py
│   ├── test_cache.py
│   └── test_analyzer.py
├── integration/
│   ├── test_library_with_cache.py
│   └── test_api_endpoints.py
├── boundaries/
│   ├── test_edge_cases.py
│   └── test_limits.py
└── conftest.py
```

### Test Coverage

**Minimum**: 85% coverage (measured with coverage.py)

**Coverage targets**:
- Critical paths: 100%
- Helper functions: 70%+
- Error handling: 90%+

**What to test**:
- ✅ Happy path (normal usage)
- ✅ Error cases (invalid input)
- ✅ Edge cases (empty arrays, None values)
- ✅ Boundary conditions (min/max values)
- ✅ Integration (multiple components together)

**What NOT to test**:
- ❌ Implementation details (private methods)
- ❌ Library behavior (third-party code)
- ❌ Auto-generated code

### Python Test Markers

```python
# Mark slow tests
@pytest.mark.slow
def test_process_large_audio_file():
    pass

# Mark integration tests
@pytest.mark.integration
def test_library_with_cache():
    pass

# Mark boundary tests
@pytest.mark.boundary
def test_zero_division_handling():
    pass

# Mark invariant tests
@pytest.mark.invariant
def test_sample_count_preserved():
    pass

# Usage: pytest -m "not slow" (skip slow tests)
```

### TypeScript Testing

**Use vitest** (not Jest):
```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';

describe('PlayerControls', () => {
  let mockOnPlay: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockOnPlay = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should render play button', () => {
    render(<PlayerControls onPlay={mockOnPlay} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('should call onPlay when button clicked', () => {
    render(<PlayerControls onPlay={mockOnPlay} />);
    screen.getByRole('button').click();
    expect(mockOnPlay).toHaveBeenCalledOnce();
  });
});
```

---

## Database Standards

### Repository Pattern

**All database access goes through repositories**:

```python
# ✅ Good (repository pattern)
from auralis.library.repositories import TrackRepository

repo = TrackRepository(db)
tracks = repo.search("query", limit=50)

# ❌ Bad (direct SQL)
from auralis.library import db

tracks = db.execute("SELECT * FROM tracks WHERE title LIKE ?").fetchall()
```

### Query Optimization

**Avoid N+1 queries**:
```python
# ❌ Bad (N+1 query problem)
tracks = repo.get_all()
for track in tracks:
    artists = repo.get_artists_for_track(track.id)  # Query per track!

# ✅ Good (single query with joins)
tracks = repo.get_all_with_artists()
for track in tracks:
    artists = track.artists  # Already loaded
```

### Connection Management

**Use connection pooling**:
```python
from sqlalchemy import create_engine

engine = create_engine(
    'sqlite:///library.db',
    poolclass=StaticPool,
    pool_pre_ping=True,  # Test connections before using
    pool_size=10,
    max_overflow=20,
)
```

---

## Design System & UI Standards

### Color Usage

**Always use tokens**:
```typescript
import { tokens } from '@/design-system';

const colors = {
  text: {
    primary: tokens.colors.text.primary,
    secondary: tokens.colors.text.secondary,
    disabled: tokens.colors.text.disabled,
  },
  background: {
    primary: tokens.colors.background.primary,
    secondary: tokens.colors.background.secondary,
  },
  feedback: {
    success: tokens.colors.feedback.success,
    warning: tokens.colors.feedback.warning,
    error: tokens.colors.feedback.error,
  },
};
```

### Spacing

**Use spacing scale** (based on 4px):
```typescript
const spacing = {
  xs: tokens.spacing.xs,  // 4px
  sm: tokens.spacing.sm,  // 8px
  md: tokens.spacing.md,  // 16px
  lg: tokens.spacing.lg,  // 24px
  xl: tokens.spacing.xl,  // 32px
};
```

### Typography

**Use typography tokens**:
```typescript
const typography = {
  heading1: {
    fontSize: tokens.typography.heading1.fontSize,
    fontWeight: tokens.typography.heading1.fontWeight,
    lineHeight: tokens.typography.heading1.lineHeight,
  },
  body: {
    fontSize: tokens.typography.body.fontSize,
    fontFamily: tokens.typography.body.fontFamily,
  },
};
```

### Accessibility (WCAG AA)

**Color contrast**:
- Text: Minimum 4.5:1 (normal), 3:1 (large)
- UI components: Minimum 3:1

**Keyboard navigation**:
- Tab through all interactive elements
- Enter/Space to activate buttons
- Arrow keys for lists/menus

**Semantic HTML**:
```typescript
// ✅ Good (semantic HTML)
<button onClick={handlePlay}>Play</button>
<header>...</header>
<nav>...</nav>
<main>...</main>
<article>...</article>
<footer>...</footer>

// ❌ Bad (divs everywhere)
<div onClick={handlePlay}>Play</div>
<div className="header">...</div>
```

**ARIA labels**:
```typescript
// ✅ Good (ARIA labels)
<button aria-label="Play audio">▶</button>
<div role="status" aria-live="polite">Now playing: Song Title</div>
<button aria-expanded={isOpen}>Menu</button>

// ❌ Bad (no ARIA)
<button>▶</button>
<div>Song Title</div>
```

---

## API Standards

### Request/Response Format

All API responses follow standardized structure:

```json
{
  "status": "success",
  "data": {
    "items": [],
    "pagination": {
      "offset": 0,
      "limit": 50,
      "total": 150
    }
  },
  "meta": {
    "timestamp": "2024-11-28T10:30:00Z",
    "version": "v1"
  }
}
```

### Error Responses

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_INPUT",
    "message": "User-friendly error message",
    "details": {
      "field": "query",
      "reason": "Must be at least 3 characters"
    }
  },
  "meta": {
    "timestamp": "2024-11-28T10:30:00Z"
  }
}
```

---

## Performance & Optimization

### Frontend Performance Targets

- **FCP** (First Contentful Paint): < 1.5s
- **LCP** (Largest Contentful Paint): < 2.5s
- **CLS** (Cumulative Layout Shift): < 0.1
- **Bundle size**: < 500KB (gzipped)
- **60 FPS**: Smooth scrolling and animations

### Backend Performance Targets

- **Search** (cache hit): < 50ms
- **List operations**: < 100ms
- **Batch operations**: < 50ms per item
- **Cache hit rate**: > 70%
- **API response**: < 200ms (p95)

### Optimization Techniques

**React**:
- Memoization (React.memo for props, useMemo for values)
- Virtual scrolling for large lists
- Code splitting and lazy loading
- Image optimization

**Python**:
- NumPy vectorization (avoid Python loops)
- Connection pooling
- Query caching (Phase 7.5)
- Async/await for I/O

---

## Security Standards

### Input Validation

**Always validate user input**:
```python
def search_library(query: str) -> List[Track]:
    """Search library."""
    # Validate input
    if not isinstance(query, str):
        raise TypeError("query must be string")

    if len(query) < 3:
        raise ValueError("query must be at least 3 characters")

    if len(query) > 200:
        raise ValueError("query must be at most 200 characters")

    # Safe to use after validation
    return repo.search(query)
```

### SQL Injection Prevention

**Use parameterized queries** (always):
```python
# ❌ Bad (SQL injection vulnerability)
tracks = db.execute(f"SELECT * FROM tracks WHERE title = '{query}'")

# ✅ Good (parameterized)
tracks = db.execute(
    "SELECT * FROM tracks WHERE title = ?",
    (query,)
)
```

### XSS Prevention (Frontend)

**Never use dangerouslySetInnerHTML**:
```typescript
// ❌ Bad
<div dangerouslySetInnerHTML={{ __html: userContent }} />

// ✅ Good (React escapes by default)
<div>{userContent}</div>
```

---

## Documentation Standards

### Docstring/Comment Requirements

- Public functions/classes: Mandatory
- Private functions: Required if complex (>20 lines)
- Complex algorithms: Always document the approach
- Workarounds/Hacks: Document why it's needed and alternative approaches

### README Files

Each major module should have a README:

```markdown
# Module Name

**Purpose**: One sentence describing what this module does.

## Overview

Longer explanation of the module's responsibilities.

## Key Components

- ComponentA: What it does
- ComponentB: What it does

## Usage

```python
from module import ComponentA

component = ComponentA()
result = component.process(data)
```

## Performance

- Operation X: O(n) complexity
- Typical throughput: Y items/second

## Known Limitations

- Limitation A
- Limitation B

## Testing

How to run tests for this module.
```

---

## Summary Checklist

Before committing code:

- [ ] Module size < 300 lines (Python) or < 300 lines (React)
- [ ] Type hints on all public functions
- [ ] Docstrings/comments explain "why"
- [ ] No hardcoded colors or spacing (design tokens only)
- [ ] Error handling with logging (not silent failures)
- [ ] Tests added (85%+ coverage)
- [ ] Commit message follows `type: description` format
- [ ] All CI/CD checks pass
- [ ] No `any` types or type ignores
- [ ] No bare excepts
- [ ] No star imports
- [ ] Linting clean (ESLint, mypy)

---

## Questions?

Consult these references:
- Python: [PEP 8](https://pep8.org/), [PEP 484](https://www.python.org/dev/peps/pep-0484/) (Type Hints)
- TypeScript: [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- React: [React Documentation](https://react.dev/)
- Accessibility: [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

---

**Last Updated**: 2024-11-28
**Status**: Active
**Next Review**: After Phase A completion
