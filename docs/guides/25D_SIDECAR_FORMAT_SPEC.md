# .25d Sidecar File Format Specification

**Version**: 1.0
**Status**: Design Proposal
**Date**: October 29, 2025

## Overview

The `.25d` sidecar file format provides portable, non-destructive metadata storage for audio files. It stores both audio fingerprints (for similarity analysis) and processing cache (for faster mastering).

### Benefits

1. **Non-destructive** - Original audio files remain untouched
2. **Portable** - Metadata travels with audio files
3. **Fast** - Skip expensive analysis when .25d file is up-to-date
4. **Dual-purpose** - Fingerprints + processing cache in one file
5. **User-friendly** - Human-readable JSON format
6. **Version-safe** - Format version tracking for future updates

### Use Cases

- **Library Scanning**: Check for .25d files before analyzing audio (50-100x speedup)
- **Backup/Migration**: Copy audio + .25d files together, preserve all metadata
- **Collaboration**: Share audio with fingerprint/processing data
- **Re-analysis**: Delete .25d file to force fresh analysis
- **Debugging**: Inspect audio characteristics in human-readable format

---

## File Format

### Naming Convention

```
<audio_filename>.25d
```

**Examples**:
```
01 - See No Evil.mp3          → 01 - See No Evil.mp3.25d
Bohemian Rhapsody.flac        → Bohemian Rhapsody.flac.25d
track01.wav                   → track01.wav.25d
```

### File Structure (JSON)

```json
{
  "format_version": "1.0",
  "auralis_version": "1.0.0-beta.5",
  "generated_at": "2025-10-29T00:00:00Z",
  "audio_file": {
    "path": "01 - See No Evil.mp3",
    "size_bytes": 8456789,
    "modified_at": "2024-03-15T10:30:00Z",
    "checksum_sha256": "abc123...",
    "duration_seconds": 238.5,
    "sample_rate": 44100,
    "channels": 2,
    "format": "mp3"
  },
  "fingerprint": {
    "version": "1.0",
    "dimensions": 25,
    "frequency": {
      "sub_bass_pct": 0.588,
      "bass_pct": 39.111,
      "low_mid_pct": 14.684,
      "mid_pct": 26.745,
      "upper_mid_pct": 13.995,
      "presence_pct": 2.787,
      "air_pct": 2.090
    },
    "dynamics": {
      "lufs": -14.019,
      "crest_db": 14.494,
      "bass_mid_ratio": -0.250
    },
    "temporal": {
      "tempo_bpm": 143.555,
      "rhythm_stability": 0.960,
      "transient_density": 0.430,
      "silence_ratio": 0.027
    },
    "spectral": {
      "spectral_centroid": 0.306,
      "spectral_rolloff": 0.435,
      "spectral_flatness": 0.0002
    },
    "harmonic": {
      "harmonic_ratio": 0.639,
      "pitch_stability": 0.076,
      "chroma_energy": 1.0
    },
    "variation": {
      "dynamic_range_variation": 0.0,
      "loudness_variation_std": 10.0,
      "peak_consistency": 0.773
    },
    "stereo": {
      "stereo_width": 0.204,
      "phase_correlation": 0.591
    }
  },
  "processing_cache": {
    "content_analysis": {
      "rms_db": -18.5,
      "peak_db": -0.3,
      "true_peak_db": -0.1,
      "dynamic_range_dr": 12.3,
      "spectral_centroid_hz": 1350.5,
      "spectral_rolloff_hz": 8500.0,
      "genre_detected": "Rock",
      "genre_confidence": 0.85
    },
    "eq_analysis": {
      "critical_bands": [
        {"freq_hz": 20, "gain_db": -2.5},
        {"freq_hz": 60, "gain_db": 1.2},
        {"freq_hz": 250, "gain_db": 0.5}
      ]
    },
    "recommended_preset": "Punchy",
    "last_processed_at": "2025-10-29T00:00:00Z"
  },
  "metadata": {
    "title": "See No Evil",
    "artist": "Television",
    "album": "Marquee Moon",
    "year": 1977,
    "track_number": 1,
    "genre": "Punk Rock"
  }
}
```

---

## File Validation

### Validity Checks

A `.25d` file is considered **valid** if:

1. **File exists** - `.25d` file is present alongside audio file
2. **Format version supported** - `format_version` is compatible (currently "1.0")
3. **Checksum matches** - Audio file hasn't been modified since .25d generation
4. **Timestamp check** - Audio file `modified_at` matches .25d `audio_file.modified_at`
5. **Required fields present** - All fingerprint dimensions are present and valid (not NaN/Inf)

### Invalidation Conditions

A `.25d` file becomes **invalid** when:

1. **Audio file modified** - Checksum or timestamp mismatch
2. **Audio file moved/renamed** - Path doesn't match
3. **Format version incompatible** - Newer Auralis version requires different format
4. **Corrupted data** - JSON parsing fails or required fields missing

**Action on invalid .25d file**: Delete and regenerate

---

## Implementation Design

### Core Components

#### 1. SidecarManager (`auralis/library/sidecar_manager.py`)

```python
class SidecarManager:
    """Manages .25d sidecar files for audio metadata"""

    def exists(audio_path: Path) -> bool:
        """Check if .25d file exists for audio file"""

    def is_valid(audio_path: Path) -> bool:
        """Validate .25d file (checksum, timestamp, format)"""

    def read(audio_path: Path) -> Dict:
        """Read .25d file and return metadata dict"""

    def write(audio_path: Path, data: Dict) -> bool:
        """Write metadata to .25d file"""

    def delete(audio_path: Path) -> bool:
        """Delete .25d file"""

    def get_fingerprint(audio_path: Path) -> Optional[Dict]:
        """Extract fingerprint from .25d file"""

    def get_processing_cache(audio_path: Path) -> Optional[Dict]:
        """Extract processing cache from .25d file"""
```

#### 2. Modified FingerprintExtractor

```python
class FingerprintExtractor:
    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        """
        Extract fingerprint with .25d sidecar support

        Workflow:
        1. Check if .25d file exists and is valid
        2. If valid: Load fingerprint from .25d (instant)
        3. If invalid/missing: Analyze audio (slow)
        4. Store in database + write .25d file
        """

        # Check for valid .25d file
        if self.sidecar_manager.is_valid(filepath):
            fingerprint = self.sidecar_manager.get_fingerprint(filepath)
            if fingerprint:
                # Fast path: Use cached data
                self.fingerprint_repo.upsert(track_id, fingerprint)
                return True

        # Slow path: Analyze audio
        audio, sr = load_audio(filepath)
        fingerprint = self.analyzer.analyze(audio, sr)

        # Store in DB
        self.fingerprint_repo.upsert(track_id, fingerprint)

        # Write .25d sidecar file
        self.sidecar_manager.write(filepath, {
            "fingerprint": fingerprint,
            "audio_file": self._get_audio_metadata(filepath)
        })

        return True
```

#### 3. Processing Pipeline Integration

```python
class HybridProcessor:
    def process(self, audio, sr, **kwargs):
        """
        Process audio with .25d cache support

        Workflow:
        1. Check for .25d file with processing_cache
        2. If valid: Skip content analysis (50-100x speedup)
        3. If invalid/missing: Run content analysis + cache results
        """

        filepath = kwargs.get('filepath')

        # Try to load processing cache from .25d
        if filepath and self.sidecar_manager.is_valid(filepath):
            cache = self.sidecar_manager.get_processing_cache(filepath)
            if cache and cache.get('content_analysis'):
                # Use cached analysis
                content_profile = cache['content_analysis']

        # Slow path: Analyze audio
        if not content_profile:
            content_profile = self.content_analyzer.analyze(audio, sr)

            # Write to .25d file
            if filepath:
                self.sidecar_manager.update_processing_cache(
                    filepath,
                    content_profile
                )

        # Continue with processing...
```

---

## Performance Impact

### Before (No .25d files)

```
Library scan (10,000 tracks):
- Fingerprint extraction: 8.5 days (75s/track)
- First-time processing: 3-5s/track (content analysis)
```

### After (With .25d files)

```
Library scan (10,000 tracks, assuming 80% have .25d):
- Fingerprint extraction: 1.7 days (8,000 cached + 2,000 new)
- Subsequent scans: ~5 minutes (all cached)
- First-time processing: 0.05s/track (cache hit)
- Speedup: 60-100x for content analysis
```

### Storage Requirements

```
Average .25d file size: ~2-4 KB
10,000 tracks: 20-40 MB total
50,000 tracks: 100-200 MB total
```

**Conclusion**: Negligible storage cost, massive performance gain

---

## Migration Strategy

### Phase 1: Core Implementation (Beta.6)
- ✅ Implement `SidecarManager` class
- ✅ Update `FingerprintExtractor` to use .25d files
- ✅ Add .25d file validation logic
- ✅ Write comprehensive tests

### Phase 2: Processing Integration (Beta.7)
- ✅ Integrate .25d cache into `HybridProcessor`
- ✅ Cache content analysis results
- ✅ Cache EQ analysis results
- ✅ Add processing cache invalidation logic

### Phase 3: Library Management (Beta.7)
- ✅ Add .25d management to `LibraryScanner`
- ✅ Add API endpoints for .25d operations
- ✅ Add UI for .25d status/management
- ✅ Add "Regenerate all .25d files" bulk operation

### Phase 4: User Features (Beta.8)
- ✅ Add .25d export/import functionality
- ✅ Add .25d viewer/editor UI
- ✅ Add batch .25d generation
- ✅ Add .25d integrity check tool

---

## User-Facing Features

### Settings Panel

```
[ ] Generate .25d files during library scan
[ ] Use .25d files for faster processing
[ ] Auto-update .25d files when audio changes
[ ] Show .25d status in library view
```

### Library View

```
Track Listing:
┌──────────────────────────────────────────────────┐
│ See No Evil - Television              [.25d: ✓] │
│ Venus - Television                     [.25d: ✓] │
│ Bohemian Rhapsody - Queen              [.25d: ✗] │
└──────────────────────────────────────────────────┘
```

### Bulk Operations

```
Actions:
- Generate .25d files for all tracks
- Regenerate invalid .25d files
- Delete all .25d files
- Export .25d files (for backup)
- Import .25d files (from backup)
```

---

## File Format Evolution

### Version 1.0 → 2.0 (Future)

**Potential additions**:
- Waveform data for UI visualization
- Beat grid for DJ features
- Mood/emotion tags
- Key detection (musical key)
- BPM confidence scores
- Additional fingerprint dimensions (expand from 25D to 30D+)

**Backward compatibility**: Version 2.0 reader must support 1.0 files

---

## Security Considerations

1. **File Permissions**: .25d files inherit permissions from audio file
2. **No Sensitive Data**: No user credentials or private data in .25d files
3. **Validation**: Always validate JSON parsing to prevent injection attacks
4. **Path Traversal**: Sanitize paths when reading/writing .25d files

---

## Testing Strategy

### Unit Tests

```python
def test_sidecar_read_write():
    """Test basic .25d file I/O"""

def test_sidecar_validation():
    """Test .25d file validity checks"""

def test_checksum_mismatch():
    """Test .25d invalidation when audio file changes"""

def test_fingerprint_extraction_with_cache():
    """Test fingerprint extraction uses .25d cache"""

def test_processing_cache_integration():
    """Test HybridProcessor uses .25d cache"""
```

### Integration Tests

```python
def test_library_scan_with_25d_files():
    """Test library scanning with .25d files present"""

def test_25d_migration():
    """Test migrating existing library to .25d format"""

def test_25d_file_regeneration():
    """Test bulk .25d file regeneration"""
```

---

## Documentation

### User Guide

**Title**: "Understanding .25d Sidecar Files"

**Sections**:
1. What are .25d files?
2. Why use .25d files?
3. How to enable .25d file generation
4. Managing .25d files
5. Troubleshooting .25d files

### Developer Guide

**Title**: "Working with .25d Sidecar Files"

**Sections**:
1. .25d file format specification
2. Reading/writing .25d files programmatically
3. Extending the .25d format
4. Best practices for .25d file management

---

## Open Questions

1. **Compression**: Should .25d files be gzipped to save space? (~50% size reduction)
2. **Binary format**: Consider MessagePack or Protocol Buffers for smaller files?
3. **Multiple versions**: Support multiple .25d versions in one file (for A/B testing)?
4. **Cloud sync**: Support cloud storage for .25d files (Google Drive, Dropbox)?

**Decision**: Start with JSON for v1.0 (human-readable, debuggable), consider binary format for v2.0

---

## Implementation Priority

**High Priority** (Beta.6):
- ✅ `SidecarManager` implementation
- ✅ Fingerprint extraction integration
- ✅ Basic validation logic

**Medium Priority** (Beta.7):
- ✅ Processing pipeline integration
- ✅ Library scanner integration
- ✅ API endpoints

**Low Priority** (Beta.8):
- ⏳ UI features
- ⏳ Bulk operations
- ⏳ Import/export

---

## Conclusion

The `.25d` sidecar file format provides a **non-destructive, portable, fast** solution for audio metadata storage. Key benefits:

1. **10-100x speedup** for library scanning and processing
2. **Portable metadata** that travels with audio files
3. **User-friendly** JSON format for debugging and inspection
4. **Dual-purpose** design (fingerprints + processing cache)
5. **Future-proof** with version tracking

**Recommendation**: Implement in Beta.6 as a core feature, enable by default for all new library scans.
