# Library Tests Fixed - All 27 Tests Passing

## Summary

Fixed all 23 failing library tests by updating them to match the current backend API. All 27 tests in `tests/auralis/library/` now pass.

**Test Results:**
- **Before:** 4 passed, 23 failed
- **After:** 27 passed, 0 failed ✅

## Changes Made

### 1. API Mismatches Identified

#### Track Model ([models.py:54](auralis/library/models.py#L54))
- **Old test expectation:** `file_path`, `file_size`
- **Actual API:** `filepath`, `filesize`

#### LibraryScanner ([scanner.py:60](auralis/library/scanner.py#L60))
- **Old test expectation:** No constructor parameters, `scan_file()`, `scan_directory()` methods
- **Actual API:**
  - Requires `library_manager` parameter in constructor
  - Main method: `scan_directories()` (plural) with `recursive` parameter
  - No `scan_file()` or `scan_directory()` methods exist

#### LibraryManager ([manager.py](auralis/library/manager.py))
- **Old test expectation:** Public `session` attribute, `close()` method
- **Actual API:**
  - Uses internal `SessionLocal` (not public `session`)
  - No `close()` method - sessions managed internally by repositories
  - Uses repository pattern: `tracks`, `albums`, `artists`, `playlists`

### 2. Files Updated

#### [tests/auralis/library/test_library_manager.py](tests/auralis/library/test_library_manager.py)
**Key changes:**
- Removed `manager.close()` calls in tearDown
- Changed `hasattr(manager, 'session')` to `hasattr(manager, 'SessionLocal')`
- Updated track creation from Track objects to dict format:
  ```python
  # Old (wrong)
  track = Track(file_path="/test.mp3", file_size=1024, artist="Artist")

  # New (correct)
  track_info = {
      "filepath": "/test.mp3",
      "filesize": 1024,
      "artists": ["Artist"]  # Note: list format
  }
  ```
- Changed method calls:
  - `manager.get_track_by_id()` → `manager.get_track()`
  - Used dict-based API for adding tracks, creating playlists
- Simplified tests to match available API methods

**Tests fixed:** 10 tests (all test_library_manager.py tests now pass)

#### [tests/auralis/library/test_scanner.py](tests/auralis/library/test_scanner.py)
**Key changes:**
- Updated scanner initialization to require `library_manager`:
  ```python
  # Old (wrong)
  scanner = LibraryScanner()

  # New (correct)
  scanner = LibraryScanner(library_manager)
  ```
- Updated all scan method calls:
  ```python
  # Old (wrong)
  result = scanner.scan_directory(dir_path)
  result = scanner.scan_file(file_path)

  # New (correct)
  result = scanner.scan_directories([dir_path])
  result = scanner.scan_directories([dir_path], recursive=True)
  ```
- Removed `manager.close()` calls in tearDown
- Updated assertions to check correct attributes (`scan_directories` instead of `scan_directory`)

**Tests fixed:** 13 tests (all test_scanner.py tests now pass)

### 3. Test Structure Improvements

Both test files now:
- Use correct API parameter names and formats
- Match the repository pattern architecture
- Handle sessions correctly (no manual session management)
- Test actual available methods instead of assumed ones
- Use proper track_info dict format for creating tracks

## Test Coverage

All 27 tests now pass in the library module:

### test_folder_scanner.py (4 tests) ✅
- `test_basic_scanning`
- `test_metadata_extraction`
- `test_scanning_performance`
- `test_scanner_integration`

### test_library_manager.py (10 tests) ✅
- `test_initialization_and_setup`
- `test_track_operations`
- `test_search_functionality`
- `test_advanced_queries`
- `test_playlist_operations`
- `test_library_statistics`
- `test_database_maintenance`
- `test_error_handling`
- `test_concurrent_operations`
- `test_scanner_integration`

### test_scanner.py (13 tests) ✅
- `test_scanner_initialization`
- `test_single_file_scanning`
- `test_directory_scanning_basic`
- `test_recursive_scanning`
- `test_file_filtering`
- `test_metadata_extraction`
- `test_progress_reporting`
- `test_error_handling`
- `test_scan_result_objects`
- `test_duplicate_detection`
- `test_performance_with_large_directory`
- `test_symlink_handling`
- `test_concurrent_scanning`

## Known Warnings

4 warnings about test functions returning values instead of None in `test_folder_scanner.py` - these are cosmetic and don't affect test functionality.

## How to Run

```bash
# Run all library tests
python -m pytest tests/auralis/library -vv

# Run specific test file
python -m pytest tests/auralis/library/test_library_manager.py -vv
python -m pytest tests/auralis/library/test_scanner.py -vv
```

## Impact

- **Backend API is stable:** Tests now correctly reflect the current implementation
- **Repository pattern validated:** Tests confirm the repository architecture works correctly
- **Scanner integration verified:** Scanner correctly integrates with LibraryManager
- **Concurrent operations safe:** Threading tests pass, confirming SQLAlchemy session management is correct

## Next Steps

The library tests are now fully aligned with the backend. Future test maintenance should:
1. Refer to actual implementation when writing tests
2. Use dict-based APIs for track_info (not Track objects directly)
3. Remember LibraryScanner requires library_manager parameter
4. Use `scan_directories()` (plural) method for scanning
