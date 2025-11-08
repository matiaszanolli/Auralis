# Phase 1 Week 3: Boundary Tests - Implementation Plan

**Date**: November 8, 2025
**Target**: 150 boundary tests
**Goal**: Test edge cases that would have caught the overlap bug

---

## Overview

**Boundary testing** validates behavior at the edges of input domains - the exact points where bugs are most likely to occur.

**Key Insight from Overlap Bug:**
```python
# Bug: OVERLAP_DURATION = 3s, CHUNK_DURATION = 10s
# Problem: 3s > 10s/2 causes duplicate audio

# Missing test that would have caught it:
def test_overlap_appropriate_for_chunk_duration():
    assert OVERLAP_DURATION < CHUNK_DURATION / 2
```

**Boundary values include:**
- **Zero and One**: Empty collections, single items
- **Exact boundaries**: Page limits, time boundaries, array indices
- **Maximum values**: Integer limits, string lengths, file sizes
- **Invalid values**: Negative numbers, null/None, empty strings

---

## Test Organization

### Directory Structure
```
tests/boundaries/
├── __init__.py
├── test_chunked_processing_boundaries.py    (30 tests)
├── test_pagination_boundaries.py            (30 tests)
├── test_audio_processing_boundaries.py      (30 tests)
├── test_library_boundaries.py               (30 tests)
└── test_string_input_boundaries.py          (30 tests)
```

---

## Category 1: Chunked Processing (30 tests)

**File**: `tests/boundaries/test_chunked_processing_boundaries.py`

### Critical Invariants (10 tests)
These would have caught the overlap bug:

```python
@pytest.mark.boundary
@pytest.mark.exact
class TestChunkInvariants:
    """Tests that validate chunk processing invariants."""

    def test_overlap_less_than_half_chunk_duration(self):
        """OVERLAP must be < CHUNK_DURATION / 2 to prevent duplicates."""
        from auralis_web.backend.chunked_processor import OVERLAP_DURATION, CHUNK_DURATION
        assert OVERLAP_DURATION < CHUNK_DURATION / 2, \
            f"Overlap {OVERLAP_DURATION}s too large for {CHUNK_DURATION}s chunks"

    def test_chunks_cover_entire_duration_no_gaps(self):
        """Concatenated chunks equal original audio length."""
        processor = ChunkedProcessor(audio, sample_rate=44100)
        chunks = [processor.get_chunk(i) for i in range(processor.total_chunks)]

        total_samples = sum(len(chunk) for chunk in chunks)
        assert total_samples == len(audio), "Gap or overlap detected"

    def test_chunk_start_times_monotonic_increasing(self):
        """Chunk start times must increase monotonically."""
        processor = ChunkedProcessor(audio, sample_rate=44100)

        prev_start = -1
        for i in range(processor.total_chunks):
            start_time = processor.get_chunk_start_time(i)
            assert start_time > prev_start, f"Chunk {i} starts at {start_time}s <= previous {prev_start}s"
            prev_start = start_time
```

### Exact Boundary Cases (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.exact
class TestChunkExactBoundaries:
    """Test chunks at exact time boundaries."""

    def test_chunk_at_exactly_zero_seconds(self):
        """First chunk starts at exactly 0.0s."""
        processor = ChunkedProcessor(audio, sample_rate=44100)
        chunk = processor.get_chunk(0)
        assert chunk is not None
        assert processor.get_chunk_start_time(0) == 0.0

    def test_chunk_at_exact_chunk_duration(self):
        """Chunk at exactly CHUNK_DURATION (10s)."""
        # Create audio exactly 20s long (2 chunks)
        audio_20s = np.zeros(int(44100 * 20))
        processor = ChunkedProcessor(audio_20s, sample_rate=44100)

        # Second chunk should start at exactly 10s
        assert processor.get_chunk_start_time(1) == 10.0

    def test_last_chunk_shorter_than_chunk_duration(self):
        """Last chunk can be shorter than CHUNK_DURATION."""
        # Create audio 15s long (1 full chunk + 5s partial)
        audio_15s = np.zeros(int(44100 * 15))
        processor = ChunkedProcessor(audio_15s, sample_rate=44100)

        last_chunk = processor.get_chunk(processor.total_chunks - 1)
        assert len(last_chunk) < int(44100 * 10)  # Shorter than 10s
```

### Edge Cases (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.edge_case
class TestChunkEdgeCases:
    """Edge cases for chunk processing."""

    def test_single_chunk_audio_shorter_than_chunk_duration(self):
        """Audio < CHUNK_DURATION results in single chunk."""
        audio_5s = np.zeros(int(44100 * 5))  # 5s < 10s
        processor = ChunkedProcessor(audio_5s, sample_rate=44100)

        assert processor.total_chunks == 1
        chunk = processor.get_chunk(0)
        assert len(chunk) == len(audio_5s)

    def test_very_long_audio_many_chunks(self):
        """Audio > 1 hour processes correctly."""
        audio_1h = np.zeros(int(44100 * 3600))  # 1 hour
        processor = ChunkedProcessor(audio_1h, sample_rate=44100)

        # Should be ~360 chunks (3600s / 10s)
        assert processor.total_chunks > 300
        assert processor.total_chunks < 400

    def test_zero_length_audio_raises_error(self):
        """Empty audio raises appropriate error."""
        empty_audio = np.zeros(0)

        with pytest.raises(ValueError, match="Audio cannot be empty"):
            ChunkedProcessor(empty_audio, sample_rate=44100)
```

---

## Category 2: Pagination Boundaries (30 tests)

**File**: `tests/boundaries/test_pagination_boundaries.py`

### Empty and Single Item (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.empty
class TestPaginationEmpty:
    """Test pagination with empty results."""

    def test_empty_result_set_returns_empty_list(self):
        """Paginating empty library returns empty list."""
        result = library_manager.get_tracks(limit=50, offset=0)

        assert result['tracks'] == []
        assert result['total'] == 0
        assert result['has_more'] is False

    def test_offset_beyond_total_returns_empty(self):
        """Offset > total returns empty, not error."""
        # Library has 10 tracks
        result = library_manager.get_tracks(limit=50, offset=100)

        assert result['tracks'] == []
        assert result['has_more'] is False

@pytest.mark.boundary
@pytest.mark.single
class TestPaginationSingleItem:
    """Test pagination with single item."""

    def test_single_track_in_library(self):
        """Single track returns correctly."""
        # Add exactly 1 track
        result = library_manager.get_tracks(limit=50, offset=0)

        assert len(result['tracks']) == 1
        assert result['total'] == 1
        assert result['has_more'] is False
```

### Exact Page Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.exact
class TestPaginationExactBoundaries:
    """Test pagination at exact page boundaries."""

    def test_exactly_one_page_worth_of_items(self):
        """Exactly 50 items with limit=50."""
        # Add exactly 50 tracks
        result = library_manager.get_tracks(limit=50, offset=0)

        assert len(result['tracks']) == 50
        assert result['total'] == 50
        assert result['has_more'] is False

    def test_exactly_two_pages_worth_of_items(self):
        """Exactly 100 items (2 full pages)."""
        # Add exactly 100 tracks
        page1 = library_manager.get_tracks(limit=50, offset=0)
        page2 = library_manager.get_tracks(limit=50, offset=50)

        assert len(page1['tracks']) == 50
        assert len(page2['tracks']) == 50
        assert page1['has_more'] is True
        assert page2['has_more'] is False

    def test_last_page_partial_items(self):
        """Last page with fewer items than limit."""
        # Add exactly 47 tracks
        result = library_manager.get_tracks(limit=50, offset=0)

        assert len(result['tracks']) == 47
        assert result['has_more'] is False
```

### Limit Edge Cases (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.edge_case
class TestPaginationLimitEdgeCases:
    """Edge cases for pagination limits."""

    def test_limit_zero_returns_empty(self):
        """limit=0 returns empty list."""
        result = library_manager.get_tracks(limit=0, offset=0)

        assert result['tracks'] == []
        assert result['total'] > 0  # Total still reported

    def test_limit_one_returns_single_item(self):
        """limit=1 returns exactly one item."""
        result = library_manager.get_tracks(limit=1, offset=0)

        assert len(result['tracks']) == 1

    def test_negative_offset_raises_error(self):
        """Negative offset raises ValueError."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            library_manager.get_tracks(limit=50, offset=-1)
```

---

## Category 3: Audio Processing Boundaries (30 tests)

**File**: `tests/boundaries/test_audio_processing_boundaries.py`

### Duration Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.audio
class TestAudioDurationBoundaries:
    """Test minimum and maximum audio durations."""

    def test_minimum_duration_point_one_seconds(self):
        """0.1s audio processes correctly."""
        audio_0_1s = np.random.randn(int(44100 * 0.1))
        result = processor.process(audio_0_1s)

        assert len(result) == len(audio_0_1s)

    def test_maximum_duration_two_hours(self):
        """2 hour audio processes correctly."""
        audio_2h = np.random.randn(int(44100 * 7200))
        result = processor.process(audio_2h)

        assert len(result) == len(audio_2h)
```

### Amplitude Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.audio
class TestAudioAmplitudeBoundaries:
    """Test silent, quiet, and clipping audio."""

    def test_silent_audio_all_zeros(self):
        """Silent audio (all zeros) processes correctly."""
        silent = np.zeros(44100)
        result = processor.process(silent)

        assert result is not None
        assert len(result) == len(silent)

    def test_maximum_amplitude_clipping(self):
        """Audio at maximum amplitude (1.0) processes correctly."""
        loud = np.ones(44100)  # All samples at 1.0
        result = processor.process(loud)

        # Should not clip (soft limiter)
        assert np.max(np.abs(result)) <= 1.0
```

### Sample Rate Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.audio
class TestSampleRateBoundaries:
    """Test different sample rates."""

    @pytest.mark.parametrize("sample_rate", [
        44100,  # CD quality
        48000,  # Professional
        96000,  # Hi-res
        192000  # Ultra hi-res
    ])
    def test_various_sample_rates(self, sample_rate):
        """Process audio at various sample rates."""
        audio = np.random.randn(sample_rate)  # 1 second
        result = processor.process(audio, sample_rate=sample_rate)

        assert len(result) == len(audio)
```

---

## Category 4: Library Boundaries (30 tests)

**File**: `tests/boundaries/test_library_boundaries.py`

### Collection Size Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.empty
class TestLibraryEmpty:
    """Test empty library operations."""

    def test_scan_empty_folder(self):
        """Scanning empty folder returns 0 tracks."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = library_manager.scan_folder(str(empty_dir))
        assert result['added'] == 0
```

### Performance Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.load
class TestLibraryLargeCollections:
    """Test library with 10,000+ tracks."""

    def test_ten_thousand_tracks_pagination(self):
        """10k tracks paginate correctly."""
        # This would use fixtures from load/stress tests
        result = library_manager.get_tracks(limit=50, offset=0)

        assert result['total'] == 10000
        assert len(result['tracks']) == 50
```

### Invalid Input Boundaries (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.edge_case
class TestLibraryInvalidInputs:
    """Test invalid file paths and corrupt files."""

    def test_nonexistent_path_raises_error(self):
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            library_manager.scan_folder("/nonexistent/path")

    def test_corrupt_audio_file_skipped(self):
        """Corrupt audio files are skipped, not crash."""
        corrupt_file = tmp_path / "corrupt.flac"
        corrupt_file.write_bytes(b"not a real FLAC file")

        result = library_manager.scan_folder(str(tmp_path))
        assert result['errors'] == 1
        assert result['added'] == 0
```

---

## Category 5: String Input Boundaries (30 tests)

**File**: `tests/boundaries/test_string_input_boundaries.py`

### Empty and Long Strings (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.edge_case
class TestStringInputBoundaries:
    """Test string input edge cases."""

    def test_empty_string_search_returns_all(self):
        """Empty search string returns all tracks."""
        result = library_manager.search_tracks("")
        assert len(result) > 0

    def test_very_long_string_one_thousand_chars(self):
        """1000 character string handled correctly."""
        long_string = "a" * 1000
        result = library_manager.search_tracks(long_string)

        # Should not crash, returns empty if no match
        assert isinstance(result, list)
```

### Special Characters (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.edge_case
class TestSpecialCharacters:
    """Test Unicode, emojis, special characters."""

    def test_unicode_artist_name(self):
        """Unicode characters in artist name."""
        track = create_track(artist="周杰倫")  # Jay Chou
        result = library_manager.search_tracks("周杰倫")

        assert len(result) > 0
        assert result[0]['artist'] == "周杰倫"

    def test_emoji_in_track_title(self):
        """Emoji characters in track title."""
        track = create_track(title="My Song 🎵🎸")
        result = library_manager.get_track(track.id)

        assert result['title'] == "My Song 🎵🎸"
```

### Security Edge Cases (10 tests)

```python
@pytest.mark.boundary
@pytest.mark.security
class TestSecurityBoundaries:
    """Test SQL injection and path traversal attempts."""

    def test_sql_injection_attempt_in_search(self):
        """SQL injection attempt returns empty, not error."""
        malicious_input = "'; DROP TABLE tracks; --"
        result = library_manager.search_tracks(malicious_input)

        # Should not crash or execute SQL
        assert isinstance(result, list)

    def test_path_traversal_attempt(self):
        """Path traversal attempt blocked."""
        malicious_path = "../../etc/passwd"

        with pytest.raises(ValueError, match="Invalid path"):
            library_manager.scan_folder(malicious_path)
```

---

## Implementation Order

### Day 1: Chunked Processing (30 tests)
1. Critical invariants (overlap bug prevention)
2. Exact boundary cases
3. Edge cases (zero, single, very long)

### Day 2: Pagination (30 tests)
1. Empty/single item cases
2. Exact page boundaries
3. Limit edge cases

### Day 3: Audio Processing (30 tests)
1. Duration boundaries
2. Amplitude boundaries
3. Sample rate variations

### Day 4: Library Operations (30 tests)
1. Collection size boundaries
2. Performance boundaries
3. Invalid input handling

### Day 5: String Inputs (30 tests)
1. Empty/long strings
2. Special characters
3. Security edge cases

---

## Success Criteria

- [ ] 150 boundary tests created
- [ ] All tests passing
- [ ] Coverage of all 5 categories
- [ ] Pytest markers applied (`@pytest.mark.boundary`, `@pytest.mark.exact`, etc.)
- [ ] Documentation complete

---

## Expected Impact

**Bugs that would have been caught:**
1. ✅ Overlap bug (chunk invariant violation)
2. ✅ Off-by-one errors in pagination
3. ✅ Crashes on empty inputs
4. ✅ Unicode handling failures
5. ✅ Security vulnerabilities

**Improvement in test quality:**
- Boundary tests → 150 additional tests
- Total Phase 1 tests → 300+ tests
- Estimated bug prevention → 60-80% of edge case bugs

---

**Ready to start with Category 1: Chunked Processing?**
