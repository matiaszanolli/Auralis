# Phase 5E Migration Strategy

## Overview

Phase 5E addresses the remaining 5 test files (2600+ lines) that depend on LibraryManager or have unsupported unittest-style fixtures. These files represent the final step in completing the test suite migration to support RepositoryFactory pattern.

**Status**: In Progress
**Target Completion**: ~15-20 hours of focused refactoring
**Complexity**: Medium-High (requires fixing skipped tests and converting unittest to pytest)

---

## Phase 5E Scope

### Files to Migrate

1. **tests/auralis/player/test_enhanced_player.py** (573 lines)
   - Status: ⏸️ SKIPPED - Requires conftest.py fixture integration
   - Current Issue: Uses unittest-style setUp/tearDown instead of pytest fixtures
   - Files Affected: EnhancedAudioPlayer, QueueController, QueueManager
   - Estimated Effort: 4-5 hours
   - Priority: **HIGH** - Core player component

2. **tests/auralis/player/test_enhanced_player_detailed.py** (669 lines)
   - Status: ⏸️ SKIPPED - Similar to test_enhanced_player.py
   - Current Issue: Unittest-style fixtures incompatible with pytest
   - Files Affected: Enhanced audio processing, playback state management
   - Estimated Effort: 4-5 hours
   - Priority: **HIGH** - Detailed player validation

3. **tests/auralis/core/test_core.py** (616 lines)
   - Status: ⚠️ FUNCTIONAL - Uses proper pytest fixtures but depends on LibraryManager
   - Current Issue: LibraryManager database migration errors
   - Files Affected: LibraryManager, Scanner, Models
   - Estimated Effort: 2-3 hours
   - Priority: **MEDIUM** - Can be fixed by migrating LibraryManager calls to RepositoryFactory

4. **tests/auralis/analysis/fingerprint/test_similarity_system.py** (298 lines)
   - Status: ⏸️ SKIPPED - Database migration errors in LibraryManager
   - Current Issue: LibraryManager initialization fails during test setup
   - Files Affected: FingerprintSimilarity, KNNGraphBuilder
   - Estimated Effort: 2-3 hours
   - Priority: **MEDIUM** - Complex integration test

5. **tests/test_fingerprint_extraction.py** (461 lines)
   - Status: ⚠️ FUNCTIONAL - Uses proper pytest fixtures
   - Current Issue: LibraryManager dependency
   - Files Affected: Fingerprint extraction and analysis
   - Estimated Effort: 2-3 hours
   - Priority: **LOW** - Standalone feature test

---

## Migration Approach

### Strategy 1: Quick Wins (Easiest Path)

For tests that already use pytest fixtures correctly (test_core.py, test_fingerprint_extraction.py):

1. Replace LibraryManager dependencies with RepositoryFactory
2. Convert database setup to use `repository_factory` fixture
3. Update method calls from `manager.repos.method()` to `factory.repos.method()`
4. Keep existing test logic mostly unchanged

**Time**: 2-3 hours each
**Risk**: Low (minimal refactoring needed)

### Strategy 2: Major Refactoring (unittest → pytest)

For tests using unittest-style fixtures (test_enhanced_player*.py):

1. Convert setUp() → pytest fixture with appropriate scope
2. Convert tearDown() → fixture cleanup with yield
3. Migrate LibraryManager to RepositoryFactory
4. Update all assertions and test logic
5. Add proper mocking where needed

**Time**: 4-5 hours each
**Risk**: Medium (significant code changes needed)

### Strategy 3: Hybrid Approach (Recommended)

Execute in this order:

#### Phase 5E.1: Quick Wins (Days 1-2)
1. Fix test_core.py (2-3 hours)
2. Fix test_fingerprint_extraction.py (2-3 hours)
3. Both use pytest fixtures, just need LibraryManager → RepositoryFactory migration

#### Phase 5E.2: Complex Refactoring (Days 3-4)
1. Fix test_enhanced_player.py (4-5 hours)
2. Fix test_enhanced_player_detailed.py (4-5 hours)
3. Major unittest → pytest conversion

#### Phase 5E.3: Integration (Day 5)
1. Fix test_similarity_system.py (2-3 hours)
2. Verify all database access uses RepositoryFactory
3. Run full test suite validation

---

## Recommended Order

### High Priority (Do First)

**1. test_core.py** (Easiest)
- Already uses pytest fixtures correctly
- Just needs LibraryManager → RepositoryFactory swap
- 2-3 hours of work
- **Quick win to build momentum**

```python
# Before
@pytest.fixture
def manager(self, temp_db):
    return LibraryManager(temp_db)

def test_example(self, manager):
    tracks = manager.tracks.get_all()

# After
@pytest.fixture
def manager(self, repository_factory):
    return repository_factory  # or just use factory directly

def test_example(self, manager):
    tracks = manager.tracks.get_all()
```

**2. test_fingerprint_extraction.py** (Easy)
- Also uses proper pytest fixtures
- Standalone feature tests
- 2-3 hours of work
- Will showcase pattern applicability

**3. test_similarity_system.py** (Medium)
- Already structured as pytest class
- Requires fixing database initialization
- 2-3 hours of work
- May require mock fixtures

### Medium Priority (After Quick Wins)

**4. test_enhanced_player.py** (Hard)
- Currently skipped - requires unittest → pytest conversion
- Major refactoring needed
- 4-5 hours of work
- High value (core player functionality)

**5. test_enhanced_player_detailed.py** (Hard)
- Similar complexity to test_enhanced_player.py
- 4-5 hours of work
- Can reuse patterns from player conversion

---

## Implementation Patterns

### Pattern 1: Simple LibraryManager Replacement

For tests using LibraryManager for basic operations:

```python
# Before (LibraryManager)
def test_track_operations(self, library_manager):
    track = library_manager.tracks.add({...})
    tracks, total = library_manager.tracks.get_all()
    result = library_manager.tracks.search("query")

# After (RepositoryFactory)
def test_track_operations(self, repository_factory):
    # Use factory.tracks directly
    track = repository_factory.tracks.add({...})
    tracks, total = repository_factory.tracks.get_all()
    result = repository_factory.tracks.search("query")
```

### Pattern 2: Unittest setUp/tearDown → pytest Fixtures

```python
# Before (unittest style)
class TestExample:
    def setUp(self):
        self.db_path = tempfile.mktemp()
        self.manager = LibraryManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.db_path))

    def test_example(self):
        result = self.manager.tracks.get_all()

# After (pytest style)
class TestExample:
    @pytest.fixture
    def manager(self, repository_factory):
        return repository_factory

    def test_example(self, manager):
        result = manager.tracks.get_all()
```

### Pattern 3: Parametrized Fixtures (Optional)

If dual-mode testing is needed:

```python
# Add parametrized fixture to conftest.py
@pytest.fixture(params=["library_manager", "repository_factory"])
def data_source(request, library_manager, repository_factory):
    """Provide both patterns for comparison tests"""
    if request.param == "library_manager":
        return library_manager
    else:
        return repository_factory

# Use in tests
def test_interface_compatibility(self, data_source):
    """Test works with both LibraryManager and RepositoryFactory"""
    tracks = data_source.tracks.get_all()
    # Test logic...
```

---

## Key Challenges & Solutions

### Challenge 1: Unittest-Style Classes

**Problem**: test_enhanced_player.py uses unittest.TestCase patterns with setUp/tearDown

**Solution**:
1. Convert class to plain pytest class (no TestCase inheritance)
2. Move setUp logic to @pytest.fixture
3. Move tearDown logic to fixture cleanup (yield)
4. Update test methods to accept fixtures as parameters

```python
# Before
class TestExample(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LibraryManager()

    def test_example(self):
        self.manager.tracks.get_all()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

# After
class TestExample:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def manager(self, repository_factory):
        return repository_factory

    def test_example(self, manager, temp_dir):
        manager.tracks.get_all()
```

### Challenge 2: Database Migration Errors

**Problem**: LibraryManager initialization fails with schema_info table errors

**Solution**:
1. Don't initialize LibraryManager - use RepositoryFactory instead
2. RepositoryFactory uses in-memory SQLite with proper schema
3. Tests get fresh database with no migration issues

```python
# Before (fails)
manager = LibraryManager()  # Fails with schema_info error

# After (works)
factory = repository_factory  # Already initialized properly
```

### Challenge 3: File Path Mocking

**Problem**: Tests create fake file paths that don't exist

**Solution**:
1. Use @pytest.fixture(autouse=True) with pathlib.Path.exists mock
2. Or use temporary directories for actual files
3. Keep existing mock pattern from test_core.py as reference

```python
@pytest.fixture(autouse=True)
def mock_file_exists(self):
    """Mock Path.exists() to allow fake paths in tests."""
    with patch('pathlib.Path.exists', return_value=True):
        yield
```

### Challenge 4: Audio File Creation

**Problem**: Tests create temporary audio files using soundfile

**Solution**:
1. Keep existing temporary directory approach
2. Use conftest.py fixtures: `performance_audio_file`, `large_audio_file`
3. Or create custom fixture in test-specific conftest if needed

```python
@pytest.fixture
def test_audio_file(tmp_path):
    """Create a test audio file"""
    audio = np.random.randn(44100, 2) * 0.1
    filepath = tmp_path / 'test.wav'
    sf.write(filepath, audio, 44100)
    return str(filepath)
```

---

## Testing Strategy

### Per-File Testing

1. **test_core.py**: Run individually after conversion
   ```bash
   python -m pytest tests/auralis/core/test_core.py -v
   ```

2. **test_fingerprint_extraction.py**: Run with fingerprint tests
   ```bash
   python -m pytest tests/test_fingerprint_extraction.py -v
   ```

3. **test_enhanced_player.py**: Run with player tests
   ```bash
   python -m pytest tests/auralis/player/test_enhanced_player.py -v
   ```

### Full Suite Validation

After completing all Phase 5E migrations:

```bash
# Run all Phase 5 migrated tests
python -m pytest tests/ -m "phase5c or phase5d" -v

# Run all player tests
python -m pytest tests/auralis/player/ -v

# Run all core tests
python -m pytest tests/auralis/core/ -v

# Full test suite
python -m pytest tests/ -m "not slow" -v
```

---

## Success Criteria

### Per-File Success

- **test_core.py**: All tests pass, no skipped tests, properly uses RepositoryFactory
- **test_fingerprint_extraction.py**: All tests pass, database initialization works
- **test_similarity_system.py**: @pytest.mark.skip removed, all tests pass
- **test_enhanced_player.py**: @pytest.mark.skip removed, 16 tests passing
- **test_enhanced_player_detailed.py**: All tests passing with proper fixtures

### Overall Success

- ✅ 5/5 Phase 5E files migrated
- ✅ All skipped tests now passing
- ✅ 100% use of RepositoryFactory pattern (no LibraryManager in test code)
- ✅ All tests use pytest fixtures (no unittest-style code)
- ✅ Full test suite passes: `python -m pytest tests/ -m "not slow" -v`

---

## Timeline & Effort

### Estimated Schedule

| Phase | File | Hours | Days | Status |
|---|---|---|---|---|
| 5E.1 | test_core.py | 2-3 | 1 | Ready to start |
| 5E.1 | test_fingerprint_extraction.py | 2-3 | 1 | Ready to start |
| 5E.2 | test_enhanced_player.py | 4-5 | 1-2 | Requires conversion |
| 5E.2 | test_enhanced_player_detailed.py | 4-5 | 1-2 | Requires conversion |
| 5E.3 | test_similarity_system.py | 2-3 | 1 | Requires conversion |
| **Total** | **5 files** | **15-20** | **5-7 days** | **In Progress** |

### Effort Breakdown

- **Planning & Setup**: 1-2 hours
- **Quick Wins (2 files)**: 4-6 hours
- **Major Refactoring (2 files)**: 8-10 hours
- **Integration Tests (1 file)**: 2-3 hours
- **Validation & Testing**: 1-2 hours
- **Documentation**: 1-2 hours

---

## Next Steps

### Immediate (Next Session)

1. ✅ Phase 5D complete and committed
2. ⏳ Start Phase 5E.1 with test_core.py (quick win)
3. ⏳ Complete test_fingerprint_extraction.py
4. Document progress

### Short-term (Following Sessions)

1. Phase 5E.2: Convert test_enhanced_player.py (unittest → pytest)
2. Phase 5E.2: Convert test_enhanced_player_detailed.py
3. Phase 5E.3: Fix test_similarity_system.py
4. Full validation and test suite run

### Long-term (After Phase 5E)

1. Phase 6: LibraryManager Deprecation Decision
   - Option A: Complete removal
   - Option B: Minimal facade wrapper

2. Performance optimization based on Phase 5D findings
3. Documentation of migration patterns for future developers

---

## Reference Material

### Existing Fixtures (tests/conftest.py)

- `session_factory` - SQLAlchemy session factory for tests
- `library_manager` - LibraryManager instance (temp database)
- `repository_factory` - RepositoryFactory instance
- `temp_test_db` - Temporary database file path
- `temp_audio_dir` - Temporary audio directory
- `performance_audio_file` - 5-second test audio file
- `large_audio_file` - 3-minute test audio file
- `timer` - Timer utility for benchmarks
- `benchmark_results` - Shared dict for benchmark data

### Useful Pytest Features

- `@pytest.fixture(autouse=True)` - Auto-applied fixtures
- `@pytest.fixture(scope="class")` - Class-level fixtures
- `yield` - Fixture cleanup
- `tmp_path` - Temporary directory
- `patch()` - Mock replacements
- `@pytest.mark.skip()` - Skip tests with reason

---

## Checklist for Phase 5E Completion

- [ ] test_core.py migrated and passing
- [ ] test_fingerprint_extraction.py migrated and passing
- [ ] test_enhanced_player.py converted from unittest and passing
- [ ] test_enhanced_player_detailed.py converted from unittest and passing
- [ ] test_similarity_system.py migrated and passing (skip marker removed)
- [ ] All Phase 5E tests use RepositoryFactory exclusively
- [ ] No LibraryManager dependencies in test code
- [ ] Full test suite passes
- [ ] Phase 5E completion summary documented
- [ ] Overall migration (Phases 5A-5E) documented

---

## Conclusion

Phase 5E represents the final step in completing the test suite migration from
LibraryManager to RepositoryFactory pattern. The strategy prioritizes quick wins
first (easy migrations) before tackling complex refactoring, ensuring steady
progress and maintaining team confidence.

With proper execution, Phase 5E will:
- ✅ Complete 100% of test suite migration
- ✅ Enable LibraryManager deprecation
- ✅ Establish foundation for future pattern migrations
- ✅ Improve test maintainability and clarity
