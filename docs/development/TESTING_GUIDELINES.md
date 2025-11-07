# Auralis Testing Guidelines

**Version:** 1.0.0
**Last Updated:** November 6, 2024
**Status:** 🎯 **MANDATORY** - All contributors must follow these guidelines

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Philosophy](#testing-philosophy)
3. [Test Design Principles](#test-design-principles)
4. [Quality Metrics](#quality-metrics)
5. [Test Categories](#test-categories)
6. [Implementation Guidelines](#implementation-guidelines)
7. [Test Organization](#test-organization)
8. [Continuous Integration](#continuous-integration)
9. [Common Pitfalls](#common-pitfalls)
10. [Appendix: Case Study](#appendix-case-study)

---

## Overview

### Current State (Nov 2024)

**Test Count:** 486 tests (241 backend, 245 frontend)
**Coverage:** 74% (backend), ~95% (frontend pass rate)
**Problem:** Low test count for complexity, insufficient quality validation

### Target State (Beta 10.0 - Q1 2025)

**Test Count:** 2,500+ tests (5x increase)
**Coverage:** >85% with quality validation
**Focus:** Invariant testing, integration testing, property-based testing

### Why These Guidelines?

The overlap bug (3s overlap with 10s chunks) had **100% code coverage** but **zero validation**. This demonstrates that:

- ✅ **Code coverage ≠ test quality**
- ✅ **Line execution ≠ bug detection**
- ✅ **Passing tests ≠ correct behavior**

We need tests that **catch bugs**, not just execute lines.

---

## Testing Philosophy

### 1. Test Quality Over Coverage

**WRONG:**
```python
def test_chunked_processor_exists():
    """Test that ChunkedAudioProcessor exists"""
    processor = ChunkedAudioProcessor(...)
    assert processor is not None  # ❌ Meaningless
```

**RIGHT:**
```python
def test_overlap_is_appropriate_for_chunk_duration():
    """Verify overlap doesn't cause duplicate audio"""
    assert OVERLAP_DURATION < CHUNK_DURATION / 2, \
        f"Overlap {OVERLAP_DURATION}s too large for {CHUNK_DURATION}s chunks"
```

### 2. Test Invariants, Not Implementation

**WRONG:**
```python
def test_process_chunk_calls_extract():
    """Test that process_chunk calls _extract_segment"""
    with mock.patch('processor._extract_segment') as mock_extract:
        processor.process_chunk(0)
        assert mock_extract.called  # ❌ Tests implementation detail
```

**RIGHT:**
```python
def test_chunks_cover_entire_duration_no_gaps():
    """Property: All chunks concatenated = original duration"""
    total_extracted = sum(len(chunk) for chunk in chunks)
    assert total_extracted == len(original_audio), \
        f"Gap detected: {len(original_audio) - total_extracted} samples missing"
```

### 3. Test Behavior, Not Code

**Focus on:**
- ✅ What the system **does**
- ✅ Properties that **must hold**
- ✅ Invariants that **cannot break**
- ✅ User-visible **outcomes**

**Avoid:**
- ❌ Testing internal method calls
- ❌ Testing code structure
- ❌ Testing mocked behavior
- ❌ Testing private methods directly

---

## Test Design Principles

### Principle 1: Invariant Testing

**Invariants** are properties that must **always** hold, regardless of input.

#### Example: Audio Processing Invariants

```python
def test_processing_preserves_sample_count():
    """Invariant: Processing never changes sample count"""
    audio = generate_test_audio(duration=10.0)
    processed = processor.process(audio)
    assert len(processed) == len(audio), \
        "Processing must preserve sample count"

def test_processing_preserves_sample_rate():
    """Invariant: Processing never changes sample rate"""
    audio, sr = load_audio("test.flac")
    processed = processor.process(audio)
    # Sample rate is metadata, verify it's preserved
    assert processor.sample_rate == sr

def test_lufs_target_is_within_tolerance():
    """Invariant: LUFS target is achieved within ±1.0 dB"""
    audio = generate_loud_audio()
    processed = processor.process(audio, target_lufs=-14.0)
    actual_lufs = calculate_lufs(processed)
    assert abs(actual_lufs - (-14.0)) < 1.0, \
        f"LUFS {actual_lufs:.1f} outside tolerance of -14.0 ±1.0 dB"
```

#### Example: Chunked Processing Invariants

```python
def test_chunk_boundaries_are_continuous():
    """Invariant: Chunks have no gaps or overlaps"""
    chunk_ranges = [
        (chunk.start_sample, chunk.end_sample)
        for chunk in processor.chunks
    ]

    for i in range(len(chunk_ranges) - 1):
        current_end = chunk_ranges[i][1]
        next_start = chunk_ranges[i+1][0]

        assert next_start == current_end, \
            f"Gap/overlap between chunks {i} and {i+1}: " \
            f"chunk {i} ends at {current_end}, chunk {i+1} starts at {next_start}"

def test_all_chunks_sum_to_original_duration():
    """Invariant: Total chunk duration = original audio duration"""
    original_duration = len(audio) / sample_rate
    chunk_durations = [len(chunk) / sample_rate for chunk in chunks]
    total_chunk_duration = sum(chunk_durations)

    assert abs(total_chunk_duration - original_duration) < 0.001, \
        f"Duration mismatch: {total_chunk_duration:.3f}s chunks != " \
        f"{original_duration:.3f}s original"
```

#### Example: Library Invariants

```python
def test_pagination_returns_all_items_exactly_once():
    """Invariant: Pagination returns all items with no duplicates"""
    all_ids = set()
    offset = 0
    limit = 50

    while True:
        tracks = library.get_tracks(limit=limit, offset=offset)
        if not tracks:
            break

        # Check for duplicates
        track_ids = {t.id for t in tracks}
        duplicates = all_ids & track_ids
        assert not duplicates, f"Duplicate IDs found: {duplicates}"

        all_ids.update(track_ids)
        offset += limit

    # Verify total count matches
    assert len(all_ids) == library.get_track_count()
```

### Principle 2: Property-Based Testing

Generate **many random inputs** to verify properties hold universally.

```python
from hypothesis import given, strategies as st

@given(
    duration=st.floats(min_value=1.0, max_value=3600.0),
    sample_rate=st.sampled_from([44100, 48000, 96000])
)
def test_chunk_duration_handles_all_durations(duration, sample_rate):
    """Property: Chunking works for any valid duration"""
    audio = generate_sine_wave(duration, sample_rate)
    chunks = processor.create_chunks(audio, sample_rate)

    # Verify no gaps
    total_samples = sum(len(c) for c in chunks)
    assert total_samples == len(audio)

@given(
    query=st.text(min_size=1, max_size=100),
    limit=st.integers(min_value=1, max_value=1000)
)
def test_search_never_returns_more_than_limit(query, limit):
    """Property: Search respects limit parameter"""
    results = library.search(query, limit=limit)
    assert len(results) <= limit
```

### Principle 3: Boundary Testing

Test **edge cases** and **boundary conditions** explicitly.

```python
def test_chunk_extraction_at_exact_boundaries():
    """Boundary: Chunk extraction at 0s, 10s, 20s boundaries"""
    audio = generate_test_audio(duration=30.0, sample_rate=44100)
    processor = ChunkedAudioProcessor(audio, sample_rate=44100)

    # Test exact boundaries
    boundaries = [0.0, 10.0, 20.0, 30.0]
    for boundary in boundaries:
        sample_idx = int(boundary * 44100)
        # Verify no off-by-one errors
        assert processor._get_chunk_at_sample(sample_idx) is not None

def test_pagination_with_zero_results():
    """Boundary: Pagination with empty result set"""
    library.clear()  # Empty library
    tracks = library.get_tracks(limit=50, offset=0)

    assert tracks == []
    assert library.get_track_count() == 0
    assert not library.has_more(limit=50, offset=0)

def test_pagination_with_one_result():
    """Boundary: Pagination with single result"""
    library.clear()
    library.add_track("single.flac")

    tracks = library.get_tracks(limit=50, offset=0)
    assert len(tracks) == 1
    assert not library.has_more(limit=50, offset=1)

def test_pagination_at_exact_page_boundary():
    """Boundary: Last page has exactly limit items"""
    library.clear()
    for i in range(100):  # Exactly 2 pages of 50
        library.add_track(f"track{i}.flac")

    page1 = library.get_tracks(limit=50, offset=0)
    page2 = library.get_tracks(limit=50, offset=50)
    page3 = library.get_tracks(limit=50, offset=100)

    assert len(page1) == 50
    assert len(page2) == 50
    assert len(page3) == 0
```

### Principle 4: Integration Testing

Test **entire workflows** end-to-end.

```python
def test_e2e_add_track_to_library_and_play():
    """Integration: Add track → scan → retrieve → play"""
    # Add track
    track_path = create_test_flac("test.flac")
    library.add_track(track_path)

    # Scan library
    library.scan()

    # Retrieve track
    tracks = library.get_tracks(limit=1, offset=0)
    assert len(tracks) == 1
    track = tracks[0]

    # Play track
    player.load_track(track.id)
    player.play()

    # Verify playback state
    assert player.is_playing
    assert player.current_track_id == track.id

def test_e2e_chunked_processing_with_preset_switching():
    """Integration: Load audio → process chunks → switch preset → verify continuity"""
    # Load audio
    audio, sr = load_audio("test_track.flac")

    # Process first 3 chunks with "adaptive" preset
    processor = ChunkedAudioProcessor(audio, sr, preset="adaptive")
    chunks = [processor.process_chunk(i) for i in range(3)]

    # Switch to "warm" preset
    processor.set_preset("warm")
    chunks.extend([processor.process_chunk(i) for i in range(3, 6)])

    # Verify no gaps at preset switch boundary
    gap_samples = processor.check_gap_at_chunk(2, 3)
    assert gap_samples == 0, f"Gap of {gap_samples} samples at preset switch"
```

### Principle 5: Failure Testing

Test **error conditions** and **failure modes**.

```python
def test_invalid_audio_format_raises_clear_error():
    """Failure: Invalid audio format shows helpful error"""
    with pytest.raises(AudioFormatError) as exc_info:
        load_audio("invalid.txt")

    assert "Unsupported format" in str(exc_info.value)
    assert ".txt" in str(exc_info.value)

def test_database_connection_loss_is_recoverable():
    """Failure: Database disconnect doesn't crash system"""
    # Simulate connection loss
    library.db.close()

    # Operations should fail gracefully
    with pytest.raises(DatabaseError):
        library.get_tracks()

    # Reconnection should work
    library.reconnect()
    tracks = library.get_tracks()  # Should succeed

def test_corrupt_audio_file_is_skipped_during_scan():
    """Failure: Corrupt files don't stop library scan"""
    create_corrupt_flac("corrupt.flac")
    create_valid_flac("valid.flac")

    library.scan_folder("test_folder/")

    # Valid file should be imported, corrupt file logged
    assert library.get_track_count() == 1
    assert "corrupt.flac" in library.get_scan_errors()
```

---

## Quality Metrics

### 1. Coverage is Necessary but Insufficient

**Minimum Coverage Requirements:**
- Backend: **85%** line coverage
- Frontend: **80%** line coverage
- Critical paths: **100%** coverage (audio processing, database writes)

**But coverage alone is meaningless!** Also track:

### 2. Defect Detection Rate

**Metric:** Percentage of intentional bugs caught by tests.

**How to measure:**
```bash
# Mutation testing with pytest-mutpy
pip install mutpy
mutpy --target auralis --unit-test tests/ --runner pytest
```

**Target:** >80% mutation score (80% of mutants killed by tests)

### 3. Test Specificity

**Metric:** Do tests fail when code breaks?

**How to verify:**
```python
# Example: Break the code intentionally
OVERLAP_DURATION = 5.0  # Was 0.1s, now too large

# Run tests
pytest tests/backend/test_chunked_processor.py

# Expected: test_overlap_is_appropriate_for_chunk_duration FAILS
```

**If tests still pass, they're not specific enough!**

### 4. Edge Case Coverage

**Metric:** Percentage of boundary conditions tested.

**Required edge cases per feature:**
- Minimum/maximum values
- Zero/empty inputs
- Exact boundaries (e.g., page limits)
- One-off errors (off-by-one)
- Negative values (where invalid)

**Target:** 100% of identified edge cases

### 5. Integration Test Ratio

**Metric:** Integration tests vs. unit tests.

**Recommended ratio:**
- 60% unit tests (fast, isolated)
- 30% integration tests (realistic workflows)
- 10% end-to-end tests (full system)

---

## Test Categories

### Category 1: Unit Tests

**Purpose:** Test individual functions/methods in isolation.

**Characteristics:**
- Fast (<10ms per test)
- No external dependencies (mock/stub)
- Test single responsibility

**Examples:**
```python
def test_calculate_rms_returns_correct_value():
    """Unit: RMS calculation for known signal"""
    # Known signal: amplitude 0.5 sine wave → RMS = 0.5 / √2 ≈ 0.3536
    signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
    rms = calculate_rms(signal)
    assert abs(rms - 0.3536) < 0.01

def test_format_duration_handles_hours_and_minutes():
    """Unit: Duration formatting"""
    assert format_duration(125) == "2m 5s"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(59) == "59s"
```

### Category 2: Integration Tests

**Purpose:** Test interactions between components.

**Characteristics:**
- Moderate speed (100ms-1s per test)
- Uses real dependencies (database, files)
- Tests workflows

**Examples:**
```python
def test_library_scan_extracts_metadata():
    """Integration: Scanner → metadata extractor → database"""
    track_path = create_test_flac(
        path="test.flac",
        title="Test Track",
        artist="Test Artist",
        album="Test Album"
    )

    library.scan_folder(os.path.dirname(track_path))

    tracks = library.get_tracks()
    assert len(tracks) == 1
    assert tracks[0].title == "Test Track"
    assert tracks[0].artist == "Test Artist"

def test_artwork_extraction_updates_album():
    """Integration: Artwork extractor → database → album lookup"""
    album_id = library.add_album("Test Album", "Test Artist")
    track_path = create_test_flac_with_artwork("test.flac", album_id)

    library.scan_folder(os.path.dirname(track_path))

    album = library.get_album(album_id)
    assert album.has_artwork
    assert os.path.exists(album.artwork_path)
```

### Category 3: End-to-End Tests

**Purpose:** Test complete user workflows.

**Characteristics:**
- Slow (1s-10s per test)
- Full system (UI → API → backend → database)
- Simulates real usage

**Examples:**
```python
def test_e2e_user_adds_album_and_plays_track():
    """E2E: Add album → browse library → play track"""
    # Add album folder
    album_folder = create_test_album_folder(
        name="Test Album",
        tracks=["01 Track One.flac", "02 Track Two.flac"]
    )

    # API: Scan folder
    response = client.post("/api/library/scan", json={
        "folder": album_folder
    })
    assert response.status_code == 200

    # API: Browse albums
    response = client.get("/api/albums")
    albums = response.json()["albums"]
    assert len(albums) == 1

    # API: Get album tracks
    album_id = albums[0]["id"]
    response = client.get(f"/api/albums/{album_id}/tracks")
    tracks = response.json()["tracks"]
    assert len(tracks) == 2

    # API: Play track
    track_id = tracks[0]["id"]
    response = client.post("/api/player/play", json={
        "track_id": track_id
    })
    assert response.status_code == 200

    # Verify playback state
    response = client.get("/api/player/state")
    state = response.json()
    assert state["is_playing"]
    assert state["current_track_id"] == track_id
```

### Category 4: Property-Based Tests

**Purpose:** Verify properties hold for generated inputs.

**Characteristics:**
- Uses hypothesis/QuickCheck
- Generates hundreds of test cases
- Finds edge cases automatically

**Examples:**
```python
from hypothesis import given, strategies as st

@given(
    audio=st.lists(
        st.floats(min_value=-1.0, max_value=1.0),
        min_size=1000,
        max_size=100000
    )
)
def test_rms_is_always_non_negative(audio):
    """Property: RMS is always >= 0"""
    rms = calculate_rms(np.array(audio))
    assert rms >= 0.0

@given(
    sample_rate=st.sampled_from([44100, 48000, 96000]),
    duration=st.floats(min_value=0.1, max_value=600.0)
)
def test_chunking_preserves_duration(sample_rate, duration):
    """Property: Chunked duration = original duration"""
    audio = generate_sine_wave(duration, sample_rate)
    chunks = processor.create_chunks(audio, sample_rate)

    total_samples = sum(len(c) for c in chunks)
    expected_samples = int(duration * sample_rate)

    # Allow 1 sample tolerance for rounding
    assert abs(total_samples - expected_samples) <= 1
```

### Category 5: Performance Tests

**Purpose:** Verify system meets performance requirements.

**Characteristics:**
- Benchmarks execution time
- Tracks memory usage
- Validates scalability

**Examples:**
```python
def test_library_scan_handles_10k_tracks_in_under_30_seconds():
    """Performance: Scan 10,000 tracks < 30s"""
    folder = create_large_test_library(num_tracks=10000)

    start_time = time.time()
    library.scan_folder(folder)
    elapsed = time.time() - start_time

    assert elapsed < 30.0, f"Scan took {elapsed:.1f}s, expected <30s"

def test_pagination_query_time_is_constant():
    """Performance: Pagination O(1) query time"""
    library.add_many_tracks(10000)

    # First page
    start = time.time()
    library.get_tracks(limit=50, offset=0)
    first_page_time = time.time() - start

    # Last page
    start = time.time()
    library.get_tracks(limit=50, offset=9950)
    last_page_time = time.time() - start

    # Query time should be similar (within 2x)
    assert last_page_time < first_page_time * 2, \
        f"Last page query ({last_page_time:.3f}s) slower than first page ({first_page_time:.3f}s)"

def test_real_time_processing_achieves_target_speed():
    """Performance: Real-time processing >= 10x real-time"""
    audio, sr = load_audio("test_track.flac")  # 180s track

    start_time = time.time()
    processed = processor.process(audio, sr)
    elapsed = time.time() - start_time

    audio_duration = len(audio) / sr
    real_time_factor = audio_duration / elapsed

    assert real_time_factor >= 10.0, \
        f"Processing only {real_time_factor:.1f}x real-time, expected >=10x"
```

---

## Implementation Guidelines

### Backend Testing (Python)

#### Setup

```python
# tests/conftest.py
import pytest
from auralis.library.manager import LibraryManager
from pathlib import Path

@pytest.fixture
def test_db(tmp_path):
    """Provide clean test database"""
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def library_manager(test_db):
    """Provide library manager with test database"""
    manager = LibraryManager(db_path=test_db)
    yield manager
    manager.close()

@pytest.fixture
def test_audio():
    """Provide test audio samples"""
    def _generate(duration=1.0, sample_rate=44100):
        samples = int(duration * sample_rate)
        return np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples))
    return _generate
```

#### Test Structure

```python
# tests/backend/test_library.py
import pytest

class TestLibraryScanning:
    """Test library scanning functionality"""

    def test_scan_empty_folder_returns_zero_tracks(self, library_manager, tmp_path):
        """Scanning empty folder should return 0 tracks"""
        library_manager.scan_folder(str(tmp_path))
        assert library_manager.get_track_count() == 0

    def test_scan_folder_with_flac_files(self, library_manager, tmp_path):
        """Scanning folder with FLAC files imports them"""
        # Create test files
        create_test_flac(tmp_path / "track1.flac")
        create_test_flac(tmp_path / "track2.flac")

        library_manager.scan_folder(str(tmp_path))

        assert library_manager.get_track_count() == 2

    def test_scan_ignores_non_audio_files(self, library_manager, tmp_path):
        """Scanning folder ignores non-audio files"""
        (tmp_path / "readme.txt").write_text("Not audio")
        (tmp_path / "image.jpg").write_bytes(b"fake image")
        create_test_flac(tmp_path / "track.flac")

        library_manager.scan_folder(str(tmp_path))

        assert library_manager.get_track_count() == 1
```

#### Parametrized Tests

```python
@pytest.mark.parametrize("sample_rate", [44100, 48000, 96000, 192000])
def test_processing_supports_all_sample_rates(sample_rate, test_audio):
    """Processing works with all standard sample rates"""
    audio = test_audio(duration=1.0, sample_rate=sample_rate)
    processed = processor.process(audio, sample_rate)

    assert len(processed) == len(audio)

@pytest.mark.parametrize("format,extension", [
    ("flac", ".flac"),
    ("wav", ".wav"),
    ("mp3", ".mp3"),
    ("ogg", ".ogg"),
])
def test_loading_supports_all_formats(format, extension, tmp_path):
    """Audio loading supports all common formats"""
    file_path = tmp_path / f"test{extension}"
    create_test_audio_file(file_path, format=format)

    audio, sr = load_audio(str(file_path))

    assert len(audio) > 0
    assert sr in [44100, 48000]
```

### Frontend Testing (TypeScript/Vitest)

#### Setup

```typescript
// tests/setup.ts
import { vi } from 'vitest';
import '@testing-library/jest-dom';

// Mock fetch globally
global.fetch = vi.fn();

// Mock Web Audio API
global.AudioContext = vi.fn().mockImplementation(() => ({
  createMediaElementSource: vi.fn(),
  createGain: vi.fn(),
}));
```

#### Component Tests

```typescript
// tests/components/LibraryView.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LibraryView } from '@/components/LibraryView';
import * as libraryService from '@/services/libraryService';

describe('LibraryView', () => {
  it('loads and displays tracks on mount', async () => {
    // Mock API response
    vi.spyOn(libraryService, 'getTracks').mockResolvedValue({
      tracks: [
        { id: 1, title: 'Track 1', artist: 'Artist 1' },
        { id: 2, title: 'Track 2', artist: 'Artist 2' },
      ],
      total: 2,
      has_more: false,
    });

    render(<LibraryView />);

    // Wait for tracks to load
    await waitFor(() => {
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });
  });

  it('shows loading state while fetching', () => {
    vi.spyOn(libraryService, 'getTracks').mockReturnValue(
      new Promise(() => {}) // Never resolves
    );

    render(<LibraryView />);

    expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
  });

  it('loads more tracks when scrolling to bottom', async () => {
    const getTracks = vi.spyOn(libraryService, 'getTracks');

    // First page
    getTracks.mockResolvedValueOnce({
      tracks: [{ id: 1, title: 'Track 1', artist: 'Artist 1' }],
      total: 100,
      has_more: true,
    });

    // Second page
    getTracks.mockResolvedValueOnce({
      tracks: [{ id: 2, title: 'Track 2', artist: 'Artist 2' }],
      total: 100,
      has_more: true,
    });

    const { container } = render(<LibraryView />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Track 1')).toBeInTheDocument();
    });

    // Simulate scroll to bottom
    const scrollContainer = container.querySelector('[data-testid="scroll-container"]');
    fireEvent.scroll(scrollContainer!, { target: { scrollTop: 1000 } });

    // Wait for second page
    await waitFor(() => {
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });

    expect(getTracks).toHaveBeenCalledTimes(2);
  });
});
```

#### Integration Tests (Frontend + API)

```typescript
// tests/integration/playback.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { rest } from 'msw';
import { App } from '@/App';

const server = setupServer(
  rest.get('/api/library/tracks', (req, res, ctx) => {
    return res(ctx.json({
      tracks: [{ id: 1, title: 'Test Track', artist: 'Test Artist' }],
      total: 1,
      has_more: false,
    }));
  }),
  rest.post('/api/player/play', (req, res, ctx) => {
    return res(ctx.json({ success: true }));
  }),
  rest.get('/api/player/state', (req, res, ctx) => {
    return res(ctx.json({
      is_playing: true,
      current_track_id: 1,
    }));
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Playback Integration', () => {
  it('allows user to browse library and play track', async () => {
    const user = userEvent.setup();
    render(<App />);

    // Navigate to library
    await user.click(screen.getByText('Library'));

    // Wait for tracks to load
    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    // Click play button
    await user.click(screen.getByLabelText('Play Test Track'));

    // Verify player shows playing state
    await waitFor(() => {
      expect(screen.getByText('Now Playing: Test Track')).toBeInTheDocument();
      expect(screen.getByLabelText('Pause')).toBeInTheDocument();
    });
  });
});
```

---

## Test Organization

### Directory Structure

```
tests/
├── backend/                    # Backend Python tests
│   ├── conftest.py            # Shared fixtures
│   ├── test_library.py        # Library management
│   ├── test_player.py         # Audio player
│   ├── test_chunked_processor.py  # Chunked processing
│   └── integration/
│       ├── test_library_scan.py   # Library scan workflow
│       └── test_playback.py       # Playback workflow
│
├── frontend/                   # Frontend TypeScript tests
│   ├── setup.ts               # Test setup
│   ├── components/            # Component tests
│   │   ├── LibraryView.test.tsx
│   │   ├── PlayerBar.test.tsx
│   │   └── AlbumCard.test.tsx
│   └── integration/           # Integration tests
│       └── playback.test.tsx
│
├── auralis/                   # Audio processing tests
│   ├── core/
│   │   └── test_hybrid_processor.py
│   ├── dsp/
│   │   ├── test_eq.py
│   │   ├── test_dynamics.py
│   │   └── test_stages.py
│   ├── analysis/
│   │   └── test_fingerprint.py
│   └── player/
│       └── test_realtime.py
│
├── validation/                # Validation & E2E tests
│   ├── test_preset_integration.py
│   ├── test_e2e_processing.py
│   └── test_performance.py
│
└── helpers/                   # Test utilities
    ├── audio_generators.py    # Audio generation
    ├── fixtures.py            # Common fixtures
    └── assertions.py          # Custom assertions
```

### Naming Conventions

**Test Files:**
- `test_<module_name>.py` - Unit tests for module
- `test_<feature>_integration.py` - Integration tests
- `test_e2e_<workflow>.py` - End-to-end tests

**Test Functions:**
- `test_<function>_<scenario>()` - Descriptive scenario
- `test_<function>_raises_<error>_when_<condition>()` - Error cases
- `test_<invariant>_always_holds()` - Invariant tests

**Examples:**
```python
# ✅ GOOD
def test_overlap_is_smaller_than_chunk_duration()
def test_pagination_returns_all_items_exactly_once()
def test_lufs_target_is_within_tolerance()
def test_scan_raises_permission_error_when_folder_unreadable()

# ❌ BAD
def test_chunks()  # Too vague
def test_overlap()  # What about overlap?
def test_1()  # Meaningless
def test_edge_case()  # Which edge case?
```

### Test Markers

Use pytest markers to organize tests:

```python
# pytest.ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (moderate speed)
    e2e: End-to-end tests (slow)
    audio: Audio processing tests
    library: Library management tests
    player: Player tests
    performance: Performance benchmarks
    slow: Slow tests (>1s)
```

**Usage:**
```python
@pytest.mark.unit
def test_calculate_rms():
    """Unit test for RMS calculation"""
    pass

@pytest.mark.integration
@pytest.mark.library
def test_library_scan_workflow():
    """Integration test for library scanning"""
    pass

@pytest.mark.slow
@pytest.mark.performance
def test_scan_10k_tracks():
    """Performance test with large library"""
    pass
```

**Run specific categories:**
```bash
pytest -m unit              # Only unit tests
pytest -m "integration and library"  # Library integration tests
pytest -m "not slow"        # Skip slow tests
pytest -m audio             # Only audio processing tests
```

---

## Continuous Integration

### Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: Run fast tests
        entry: pytest -m "not slow" --maxfail=1
        language: system
        pass_filenames: false
        stages: [commit]
```

### CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-xdist

      - name: Run unit tests
        run: pytest -m unit --cov=auralis --cov-report=xml -n auto

      - name: Run integration tests
        run: pytest -m integration --cov=auralis --cov-append --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: cd auralis-web/frontend && npm ci

      - name: Run tests
        run: cd auralis-web/frontend && npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-e2e:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - uses: actions/checkout@v3

      - name: Start backend
        run: python launch-auralis-web.py &

      - name: Run E2E tests
        run: pytest -m e2e --maxfail=3
```

### Quality Gates

**Merge Requirements:**
- ✅ All tests pass
- ✅ Coverage ≥85% (backend), ≥80% (frontend)
- ✅ No new critical issues (mutation testing)
- ✅ Performance benchmarks within 10% of baseline

---

## Common Pitfalls

### Pitfall 1: Testing Implementation Details

**❌ WRONG:**
```python
def test_process_chunk_calls_extract():
    """BAD: Tests internal method call"""
    with mock.patch.object(processor, '_extract_segment') as mock_extract:
        processor.process_chunk(0)
        assert mock_extract.called
```

**✅ RIGHT:**
```python
def test_process_chunk_returns_correct_duration():
    """GOOD: Tests observable behavior"""
    chunk = processor.process_chunk(0)
    expected_duration = CHUNK_DURATION * processor.sample_rate
    assert len(chunk) == expected_duration
```

### Pitfall 2: Over-Mocking

**❌ WRONG:**
```python
def test_library_scan():
    """BAD: Everything is mocked, nothing is tested"""
    with mock.patch('scanner.extract_metadata') as mock_meta, \
         mock.patch('scanner.save_to_db') as mock_save, \
         mock.patch('scanner.update_index') as mock_index:

        scanner.scan_folder("test/")

        # All we're testing is that mocked functions were called
        assert mock_meta.called
        assert mock_save.called
        assert mock_index.called
```

**✅ RIGHT:**
```python
def test_library_scan(test_db):
    """GOOD: Use real dependencies, test real behavior"""
    # Create real test file
    track_path = create_test_flac("test.flac")

    # Use real scanner with real database
    scanner = Scanner(db_path=test_db)
    scanner.scan_folder(os.path.dirname(track_path))

    # Verify real outcome
    tracks = scanner.get_tracks()
    assert len(tracks) == 1
    assert tracks[0].title == "Test Track"
```

### Pitfall 3: Flaky Tests

**❌ WRONG:**
```python
def test_async_processing():
    """BAD: Race condition, timing-dependent"""
    processor.start_async()
    time.sleep(0.5)  # Hope it finishes in 500ms
    assert processor.is_done()
```

**✅ RIGHT:**
```python
def test_async_processing():
    """GOOD: Wait for actual completion"""
    processor.start_async()

    # Wait up to 5 seconds for completion
    for _ in range(50):
        if processor.is_done():
            break
        time.sleep(0.1)

    assert processor.is_done(), "Processing did not complete in 5 seconds"
```

### Pitfall 4: Brittle Assertions

**❌ WRONG:**
```python
def test_format_track_info():
    """BAD: Brittle exact string match"""
    info = format_track_info(track)
    assert info == "Artist - Title (3:45)"  # Breaks with any format change
```

**✅ RIGHT:**
```python
def test_format_track_info():
    """GOOD: Test essential properties"""
    info = format_track_info(track)
    assert track.artist in info
    assert track.title in info
    assert "3:45" in info  # Duration should be present
```

### Pitfall 5: Ignoring Test Failures

**❌ WRONG:**
```python
@pytest.mark.xfail(reason="Known issue, will fix later")
def test_overlap_calculation():
    """BAD: Marked as expected failure, never gets fixed"""
    assert calculate_overlap() < CHUNK_DURATION
```

**✅ RIGHT:**
```python
def test_overlap_calculation():
    """GOOD: Fix the bug, then enable test"""
    # TODO: Remove xfail once issue #123 is fixed
    assert calculate_overlap() < CHUNK_DURATION
```

**Better yet:**
```python
def test_overlap_calculation():
    """BEST: Fix the bug immediately"""
    assert calculate_overlap() < CHUNK_DURATION  # Passes now!
```

---

## Appendix: Case Study

### The Overlap Bug (Nov 2024)

**Bug Description:**
Chunked audio processing had 3-second overlap with 10-second chunks, causing brief silence gaps at boundaries.

**Why 100% Coverage Didn't Catch It:**

```python
# This test had 100% coverage but caught nothing:
def test_process_chunk_returns_audio():
    """Coverage: ✅ | Bug Detection: ❌"""
    chunk = processor.process_chunk(0)
    assert chunk is not None  # Meaningless assertion
    assert len(chunk) > 0      # Doesn't verify correctness
```

**Missing Test That Would Have Caught It:**

```python
def test_overlap_is_appropriate_for_chunk_duration():
    """The test we should have written"""
    assert OVERLAP_DURATION < CHUNK_DURATION / 2, \
        f"Overlap {OVERLAP_DURATION}s too large for {CHUNK_DURATION}s chunks - " \
        f"will cause duplicate audio! Max safe overlap: {CHUNK_DURATION/2}s"

# This test would have FAILED immediately when OVERLAP_DURATION = 3s
# and CHUNK_DURATION = 10s, because 3s > 5s (CHUNK_DURATION/2)
```

**Missing Integration Test:**

```python
def test_chunks_concatenate_without_gaps():
    """Verify chunk boundaries are continuous"""
    audio = generate_test_audio(duration=30.0, sample_rate=44100)
    processor = ChunkedAudioProcessor(audio, sample_rate=44100)

    # Process all chunks
    chunks = [processor.process_chunk(i) for i in range(processor.total_chunks)]

    # Concatenate chunks
    concatenated = np.concatenate(chunks)

    # CRITICAL: Total duration must match original
    expected_samples = len(audio)
    actual_samples = len(concatenated)

    assert actual_samples == expected_samples, \
        f"Gap/overlap detected: expected {expected_samples} samples, " \
        f"got {actual_samples} samples (diff: {actual_samples - expected_samples})"
```

**Lesson Learned:**

1. **Code coverage measures line execution, not correctness**
2. **Test invariants (properties that must always hold), not implementation**
3. **Integration tests catch configuration bugs that unit tests miss**
4. **Boundary validation is essential for chunked/paginated systems**

---

## Summary

### Golden Rules

1. **Quality > Coverage** - 85% coverage with quality tests beats 100% coverage with meaningless tests
2. **Test Behavior, Not Code** - Focus on what the system does, not how it does it
3. **Test Invariants** - Verify properties that must always hold
4. **Integration Tests Matter** - Unit tests alone won't catch configuration bugs
5. **Property-Based Testing** - Let tools generate edge cases for you
6. **Fail Fast** - Don't mark tests as xfail, fix the bugs
7. **Measure Quality** - Track mutation score, not just coverage

### Implementation Roadmap

**Phase 1 (Beta 9.1 - Dec 2024):**
- Add 500 invariant tests for critical paths
- Implement mutation testing for backend
- Add property-based tests for audio processing

**Phase 2 (Beta 10.0 - Q1 2025):**
- Reach 1,500 total tests
- 85% backend coverage with 80% mutation score
- Integration test suite for all major workflows

**Phase 3 (Beta 11.0 - Q2 2025):**
- Reach 2,500+ total tests
- Comprehensive E2E test suite
- Performance regression testing

### Resources

**Tools:**
- pytest (Python testing framework)
- pytest-cov (coverage reporting)
- mutpy (mutation testing)
- hypothesis (property-based testing)
- vitest (TypeScript/JavaScript testing)
- MSW (API mocking for integration tests)

**Further Reading:**
- [Property-Based Testing](https://hypothesis.works/)
- [Mutation Testing](https://mutpy.readthedocs.io/)
- [Test-Driven Development](https://www.amazon.com/Test-Driven-Development-Kent-Beck/dp/0321146530)

---

**Document Owner:** Engineering Team
**Last Reviewed:** November 6, 2024
**Next Review:** December 2024
