# Backend Development Environment Setup

**Version**: 1.0.0
**Last Updated**: 2024-11-28
**Status**: Ready for Use
**Target Audience**: Backend developers (Python)

---

## Quick Start (5 Minutes)

For experienced Python developers, here's the fastest path:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database
python -m auralis.library.init

# 3. Start backend with hot reload
python launch-auralis-web.py --dev

# 4. Open API docs
# Visit: http://localhost:8765/api/docs
```

---

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows (WSL2 recommended)
- **Python**: 3.13+ (check with `python --version`)
- **Git**: Latest version (check with `git --version`)
- **CPU**: Intel/AMD x86-64 (ARM support depends on audio libraries)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 2GB free space for dependencies and database

### Required Software

#### macOS
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.13
brew install python@3.13

# Install audio libraries (required for audio processing)
brew install flac libvorbis libopus
```

#### Ubuntu/Debian
```bash
# Update package manager
sudo apt update

# Install Python 3.13
sudo apt install python3.13 python3.13-dev python3.13-venv

# Install audio libraries
sudo apt install libflac-dev libvorbis-dev libopus-dev portaudio19-dev

# Install build tools
sudo apt install build-essential git
```

#### Windows (WSL2)
```bash
# In WSL2 Ubuntu terminal
sudo apt update
sudo apt install python3.13 python3.13-dev python3.13-venv
sudo apt install libflac-dev libvorbis-dev libopus-dev portaudio19-dev
sudo apt install build-essential git
```

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/matiaszanolli/Auralis.git
cd Auralis

# Verify you're on the main branch
git status
# Should show: On branch master
```

---

## Step 2: Create Python Virtual Environment

**What is a virtual environment?**
A virtual environment isolates Python packages for this project, preventing conflicts with system Python.

### Using Python 3.13 venv

```bash
# Create virtual environment named 'venv'
python3.13 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows (PowerShell):
# venv\Scripts\Activate.ps1

# You should see '(venv)' prefix in terminal
# (venv) user@computer:~/Auralis$
```

**Verify activation:**
```bash
which python
# Should show: /path/to/Auralis/venv/bin/python

python --version
# Should show: Python 3.13.x
```

**Deactivate later with:**
```bash
deactivate
```

---

## Step 3: Install Dependencies

**What does this do?**
Installs all Python packages the project needs (FastAPI, SQLAlchemy, NumPy, etc.).

```bash
# Make sure virtual environment is activated
# (venv) should be visible in terminal prompt

# Install all dependencies
pip install -r requirements.txt

# This will take 2-5 minutes depending on internet speed
```

**Verify installation:**
```bash
# List installed packages (should be 50+)
pip list | head -20

# Test a few key imports
python -c "import fastapi; import sqlalchemy; import numpy; print('All imports OK')"
# Should output: All imports OK
```

---

## Step 4: Initialize Database

**What does this do?**
Creates the SQLite database and populates it with your music library.

```bash
# Initialize database (scans ~/Music directory by default)
python -m auralis.library.init

# Output should show:
# - Number of files found
# - Number of files processed
# - Number of duplicates skipped
# - Database location (usually ~/.auralis/library.db)
```

**Verify database created:**
```bash
# Check database file exists
ls -lh ~/.auralis/library.db

# Inspect with sqlite3 (if installed)
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) as track_count FROM tracks;"
```

**Alternative: Custom music directory**
```bash
# Scan a specific directory instead
python -m auralis.library.init --music-dir /path/to/music

# Example for macOS:
python -m auralis.library.init --music-dir ~/Music
```

---

## Step 5: Configure Environment Variables

**What are environment variables?**
Settings that control how the backend behaves (port, log level, cache size, etc.).

### Create .env File

```bash
# Create .env file in project root
cat > .env << 'EOF'
# Backend Configuration

# Server
SERVER_HOST=127.0.0.1
SERVER_PORT=8765
DEBUG=1

# Database
DATABASE_URL=sqlite:///~/.auralis/library.db
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# Cache
CACHE_MAX_SIZE_MB=256
CACHE_TTL_SECONDS=300
CACHE_CONFIDENCE_THRESHOLD=0.7

# Logging
LOG_LEVEL=INFO

# Audio Processing
SAMPLE_RATE=44100
CHUNK_SIZE=2048

# WebSocket
WEBSOCKET_HEARTBEAT_INTERVAL=30
WEBSOCKET_HEARTBEAT_TIMEOUT=10

# Development
HOT_RELOAD=1
RELOAD_DIRS=auralis,auralis_web/backend
EOF

# Verify .env created
cat .env
```

### Copy .env.example (Alternative)

```bash
# Or copy from provided template
cp .env.example .env

# Edit with your preferences
nano .env  # or vim, or your favorite editor
```

**Reference Environment Variables:**

```ini
# [Server Configuration]
SERVER_HOST=127.0.0.1          # Listen on localhost only
SERVER_PORT=8765               # API port
DEBUG=1                         # Enable debug mode

# [Database]
DATABASE_URL=...               # SQLite path
DATABASE_POOL_SIZE=5           # Connection pool size
DATABASE_MAX_OVERFLOW=10       # Extra connections allowed

# [Phase 7.5 Cache]
CACHE_MAX_SIZE_MB=256          # 256MB in-memory cache
CACHE_TTL_SECONDS=300          # 5 minute TTL
CACHE_CONFIDENCE_THRESHOLD=0.7 # 70% confidence threshold

# [Logging]
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR

# [Audio]
SAMPLE_RATE=44100              # 44.1kHz
CHUNK_SIZE=2048                # Processing chunk size

# [WebSocket]
WEBSOCKET_HEARTBEAT_INTERVAL=30 # Ping every 30s
WEBSOCKET_HEARTBEAT_TIMEOUT=10   # Timeout after 10s

# [Development]
HOT_RELOAD=1                   # Enable auto-reload on changes
RELOAD_DIRS=auralis,auralis_web/backend  # Watch these directories
```

---

## Step 6: Start the Backend Server

### Run with Hot Reload (Development)

**Hot reload** automatically restarts the server when you change code—essential for development.

```bash
# Make sure virtual environment is activated
# (venv) should be visible

# Start with hot reload
python launch-auralis-web.py --dev

# You should see output like:
# INFO:     Uvicorn running on http://127.0.0.1:8765
# INFO:     Application startup complete
```

### Access API Documentation

Once running, open your browser:
```
http://localhost:8765/api/docs
```

You'll see an interactive Swagger UI showing all API endpoints.

**Test the API:**
```bash
# In another terminal (keep the server running)
curl http://localhost:8765/api/health

# Should return:
# {"status":"healthy"}
```

### Stop the Server

```bash
# Press Ctrl+C in the terminal running the server
# You should see:
# INFO:     Shutting down
```

---

## Step 7: Verify Everything Works

Run this verification checklist:

```bash
# 1. Check Python version
python --version
# ✅ Should be 3.13+

# 2. Check key packages installed
pip show fastapi sqlalchemy numpy
# ✅ Should show version info for each

# 3. Check database exists
ls -l ~/.auralis/library.db
# ✅ Should show file with size > 1KB

# 4. Check database has tracks
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) as tracks FROM tracks;"
# ✅ Should show number > 0

# 5. Start server and test
python launch-auralis-web.py --dev &
sleep 2

curl http://localhost:8765/api/health
# ✅ Should return {"status":"healthy"}

curl http://localhost:8765/api/stats
# ✅ Should return library statistics

# Stop server
fg  # Bring server to foreground
# Ctrl+C to stop
```

---

## Troubleshooting

### Problem: "python3.13: command not found"

**Solution**: Install Python 3.13 or create alias

```bash
# Check installed Python versions
ls /usr/bin/python* 2>/dev/null || ls /opt/homebrew/bin/python* 2>/dev/null

# If only Python 3.12 available, use it (may work)
python3.12 -m venv venv

# Or use system Python and note compatibility
python3 --version  # Check version
```

### Problem: "No module named 'auralis'"

**Solution**: Make sure virtual environment is activated

```bash
# Check activation
which python
# Should show: /path/to/venv/bin/python (not /usr/bin/python)

# If not activated, activate it
source venv/bin/activate

# Then try again
python -c "import auralis; print('OK')"
```

### Problem: "Port 8765 already in use"

**Solution**: Stop other processes or use different port

```bash
# Find what's using port 8765
lsof -i :8765  # macOS/Linux
netstat -ano | findstr :8765  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
SERVER_PORT=8766 python launch-auralis-web.py --dev
```

### Problem: "Database is locked"

**Solution**: Remove stale database and rescan

```bash
# Remove database
rm ~/.auralis/library.db

# Reinitialize
python -m auralis.library.init

# Start server
python launch-auralis-web.py --dev
```

### Problem: "AudioReadError" or audio library issues

**Solution**: Install missing audio libraries

**macOS:**
```bash
brew install flac libvorbis libopus
```

**Linux:**
```bash
sudo apt install libflac-dev libvorbis-dev libopus-dev
```

**Windows (WSL2):**
```bash
sudo apt install libflac-dev libvorbis-dev libopus-dev
```

Then reinstall audioread:
```bash
pip install --force-reinstall audioread
```

---

## Development Workflow

### Daily Development

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Start backend server (in one terminal)
python launch-auralis-web.py --dev

# 3. In another terminal, make code changes
# - Edit files in auralis/ or auralis_web/backend/
# - Server auto-reloads on save

# 4. Test changes
curl http://localhost:8765/api/endpoint

# 5. Run tests
pytest tests/ -v

# 6. When done, stop server
# Ctrl+C in server terminal
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_library.py -v

# Run tests matching pattern
pytest -k "search" -v

# Run fast tests only (skip slow tests)
pytest -m "not slow" -v

# Run with coverage
pytest tests/ --cov=auralis --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Running Type Checks

```bash
# Type check backend
mypy auralis/ auralis-web/backend/ --ignore-missing-imports

# Fix common issues
mypy auralis/ --ignore-missing-imports | head -10
```

### Database Inspection

```bash
# Open SQLite shell
sqlite3 ~/.auralis/library.db

# Useful queries
sqlite> SELECT COUNT(*) FROM tracks;
sqlite> SELECT name, COUNT(*) as count FROM artists GROUP BY name;
sqlite> SELECT * FROM tracks LIMIT 5;
sqlite> .quit
```

---

## Testing with Phase 5 Fixtures (Pytest)

**Phase 5 Complete Test Suite Migration - ✅ COMPLETE**

The backend test suite has been migrated to use the **RepositoryFactory pattern** with comprehensive pytest fixtures for dependency injection. This enables:
- ✅ Cleaner test code without direct database initialization
- ✅ Automatic cleanup between tests
- ✅ Parametrized dual-mode testing (both LibraryManager and RepositoryFactory patterns)
- ✅ Better test isolation and fixture reuse

### Available Fixtures (20+ in hierarchy)

**Main Test Fixtures** (`tests/conftest.py`):
```python
# Dependency injection pattern
get_repository_factory_callable  # DI callable that returns RepositoryFactory
repository_factory              # RepositoryFactory instance for tests
library_manager                 # LibraryManager for backward compatibility
track_repository                # Direct access to TrackRepository
album_repository                # Direct access to AlbumRepository
artist_repository               # Direct access to ArtistRepository
playlist_repository             # Direct access to PlaylistRepository
fingerprint_repository          # Direct access to FingerprintRepository
# ... and 3 more repository fixtures
```

**Backend API Test Fixtures** (`tests/backend/conftest.py`):
```python
# Mock fixtures for API endpoint testing
mock_repository_factory         # Mock RepositoryFactory for routers
mock_repository_factory_callable # Mock callable for DI pattern
mock_data_source               # Parametrized dual-mode fixture (runs tests twice)
client                         # FastAPI TestClient
event_loop                     # Async event loop for async tests
```

**Player Component Fixtures** (`tests/auralis/player/conftest.py`):
```python
queue_controller               # QueueController with DI
playback_controller            # PlaybackController for state tests
audio_file_manager             # AudioFileManager for file I/O tests
realtime_processor             # RealtimeProcessor for DSP tests
gapless_playback_engine        # GaplessPlaybackEngine for playback tests
integration_manager            # IntegrationManager with all components
enhanced_player                # EnhancedAudioPlayer main facade
player_config                  # PlayerConfig for configuration tests
```

**Performance Test Fixtures** (`tests/performance/conftest.py`):
```python
performance_data_source        # Dual-mode performance testing
populated_data_source          # Large dataset (1000 tracks) for load tests
timer                          # Timer context manager for benchmarking
```

### Using Phase 5 Fixtures in Tests

**Example 1: Simple Repository Test**
```python
def test_track_creation(track_repository):
    """Test creating a track using repository fixture."""
    track = track_repository.add({
        'filepath': '/tmp/test.wav',
        'title': 'Test Track',
        'artists': ['Test Artist'],
        'sample_rate': 44100
    })
    assert track.id is not None
    assert track.title == 'Test Track'
```

**Example 2: Player Component Test**
```python
def test_enhanced_player_initialization(enhanced_player, player_config):
    """Test player initialization with fixtures."""
    assert enhanced_player is not None
    assert player_config.buffer_size > 0
    # No setup/teardown needed - fixtures handle cleanup
```

**Example 3: Dual-Mode Testing (Both Patterns)**
```python
@pytest.mark.phase5c
def test_get_tracks_both_modes(mock_data_source):
    """Test works with both LibraryManager and RepositoryFactory."""
    mode, source = mock_data_source
    # Test logic runs twice - once per mode
    # mode will be "library_manager" or "repository_factory"
    tracks, total = source.tracks.get_all(limit=10)
    assert isinstance(tracks, list)
    assert isinstance(total, int)
```

**Example 4: Backend Router Test**
```python
def test_get_artists_api(client, mock_data_source):
    """Test API endpoint with mock fixtures."""
    mode, mock_factory = mock_data_source
    # Mock factory is pre-configured with proper mocks
    response = client.get("/api/artists")
    assert response.status_code == 200
    assert "artists" in response.json()
```

### Running Phase 5 Tests

```bash
# Run all Phase 5 tests
pytest tests/ -m phase5 -v

# Run specific Phase 5 sub-phase
pytest tests/ -m phase5c -v   # Backend API tests (Phase 5C)
pytest tests/ -m phase5d -v   # Performance tests (Phase 5D)
pytest tests/ -m phase5e -v   # Player component tests (Phase 5E)

# Run with fixture dependency injection
pytest tests/backend/ -v --tb=short

# Run player component tests
pytest tests/auralis/player/ -v

# Run performance benchmarks
pytest tests/performance/test_latency_benchmarks.py -v
```

### Phase 5 Architecture Patterns

**Dependency Injection Pattern:**
Components receive a callable that returns RepositoryFactory:
```python
# Components accept callable, not direct instance
class QueueController:
    def __init__(self, get_repository_factory: Callable[[], RepositoryFactory]):
        self.get_factory = get_repository_factory

    def load_track(self, track_id: int):
        factory = self.get_factory()
        track = factory.tracks.get_by_id(track_id)
        # Use track...
```

**Fixture Composition:**
Fixtures build on each other, creating a clean hierarchy:
```python
@pytest.fixture
def repository_factory(session_factory):
    """Create RepositoryFactory from session factory."""
    return RepositoryFactory(session_factory)

@pytest.fixture
def get_repository_factory_callable(repository_factory):
    """Create callable that returns RepositoryFactory."""
    def get_factory():
        return repository_factory
    return get_factory

@pytest.fixture
def enhanced_player(get_repository_factory_callable):
    """Create player with DI callable."""
    config = PlayerConfig()
    return EnhancedAudioPlayer(
        config=config,
        get_repository_factory=get_repository_factory_callable
    )
```

**Parametrized Dual-Mode Testing:**
Single test runs with both patterns automatically:
```python
@pytest.fixture(params=["library_manager", "repository_factory"])
def mock_data_source(request, mock_library_manager, mock_repository_factory):
    """Parametrized fixture provides both patterns."""
    if request.param == "library_manager":
        return ("library_manager", mock_library_manager)
    else:
        return ("repository_factory", mock_repository_factory)

@pytest.mark.phase5c
def test_api_both_modes(mock_data_source):
    """Test automatically runs twice - once with each pattern."""
    mode, source = mock_data_source
    # Implementation...
```

### Common Phase 5 Testing Patterns

**Pattern 1: Direct Repository Testing**
```python
def test_repository_operations(track_repository):
    """Test repository methods directly."""
    # Repositories are properly initialized with fixtures
    tracks = track_repository.get_all(limit=10)
    assert len(tracks) >= 0
```

**Pattern 2: Integration Testing**
```python
def test_player_with_database(enhanced_player, library_manager):
    """Test multiple components working together."""
    # Both fixtures available - good for integration tests
    success = enhanced_player.load_file("/path/to/file.wav")
    assert isinstance(success, bool)
```

**Pattern 3: Performance Testing**
```python
def test_query_performance(performance_data_source, timer):
    """Test performance with both patterns."""
    mode, source = performance_data_source
    with timer() as t:
        tracks, total = source.tracks.get_all(limit=100)
    # Both patterns should meet same benchmark
    assert t.elapsed < 0.5  # 500ms max
```

**Pattern 4: Mock-Based Testing**
```python
def test_router_endpoint(client, mock_data_source):
    """Test API route with mocked database."""
    mode, factory = mock_data_source
    # Mock is pre-configured and ready to use
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

### Troubleshooting Phase 5 Tests

**Issue: "TypeError: QueueController() missing required argument 'get_repository_factory'"**

**Solution**: Use the fixture instead of instantiating directly
```python
# ❌ Wrong
def test_queue(self):
    queue = QueueController()  # Missing required parameter

# ✅ Correct
def test_queue(queue_controller):
    queue = queue_controller  # Fixture provides proper initialization
```

**Issue: "AttributeError: 'NoneType' object has no attribute 'tracks'"**

**Solution**: Check fixture is available in conftest.py location
```python
# Fixture must be in same directory or parent conftest.py
# tests/conftest.py - ✅ Available to all tests
# tests/backend/conftest.py - ✅ Available to backend tests only
# tests/auralis/player/conftest.py - ✅ Available to player tests only
```

**Issue: "Test passes locally but fails in CI"**

**Solution**: Fixture cleanup might differ in CI environment
```python
# Use pytest tmp_path fixture for file operations
def test_with_files(tmp_path):
    """Files auto-cleaned after test in CI."""
    test_file = tmp_path / "test.wav"
    # Use test_file...
    # Automatically removed after test
```

See [PHASE_5_FINAL_COMPLETION_SUMMARY.md](../../PHASE_5_FINAL_COMPLETION_SUMMARY.md) for comprehensive architecture documentation.

---

## Advanced Configuration

### Custom Music Directory

```bash
# Create .env setting
echo "MUSIC_DIRECTORY=/path/to/music" >> .env

# Initialize with custom directory
python -m auralis.library.init --music-dir /path/to/music
```

### Disable Hot Reload (Production-like)

```bash
# Without --dev flag
python launch-auralis-web.py

# Or set environment variable
HOT_RELOAD=0 python launch-auralis-web.py --dev
```

### Enable Debug Logging

```bash
# Set log level to DEBUG
LOG_LEVEL=DEBUG python launch-auralis-web.py --dev

# Or temporarily
DEBUG=1 LOG_LEVEL=DEBUG python launch-auralis-web.py --dev
```

### Connect External Database

```bash
# Edit .env
DATABASE_URL=postgresql://user:password@localhost/auralis

# Or MySQL
DATABASE_URL=mysql+pymysql://user:password@localhost/auralis

# Then reinitialize
python -m auralis.library.init
```

---

## IDE Setup

### VS Code

```bash
# Install Python extension
# Open VS Code extensions, search "Python"
# Install extension by Microsoft

# Select interpreter
Cmd+Shift+P (macOS) / Ctrl+Shift+P (Windows/Linux)
Type: "Python: Select Interpreter"
Choose: ./venv/bin/python

# Setup debugging
Create .vscode/launch.json:
```

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend (FastAPI)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "auralis_web.backend.main:app",
        "--reload",
        "--host", "127.0.0.1",
        "--port", "8765"
      ],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

Then press F5 to start debugging.

### PyCharm

1. Open Project → auralis root directory
2. Configure → Project → Python Interpreter
3. Add → Existing Environment → Select venv/bin/python
4. Mark folders:
   - `auralis/` as Sources Root
   - `tests/` as Test Sources Root
5. Run → Edit Configurations → Add Python configuration:
   - Module: uvicorn
   - Parameters: auralis_web.backend.main:app --reload

---

## Performance Notes

### Cache Performance (Phase 7.5)

The backend includes Phase 7.5 streaming fingerprint cache for 10-500x speedup:

```bash
# Cache is automatically initialized on startup
# Check cache stats with:
curl http://localhost:8765/api/cache/stats

# Expected output:
{
  "cache": {
    "hit_rate_percent": 70.5,
    "size_mb": 128.4,
    "items": 2341
  },
  "optimizer": {
    "total_queries": 1000,
    "cache_hits": 705,
    "avg_time_ms": 45.2
  }
}
```

### Memory Management

```bash
# Monitor memory usage (macOS)
top -o MEM -n 1 | grep python

# Or use psutil
pip install psutil
python -c "import psutil; p = psutil.Process(); print(f'Memory: {p.memory_info().rss / 1024 / 1024:.1f}MB')"
```

---

## Clean Up / Reset

### Full Reset (removes all data)

```bash
# Stop the server first
# Ctrl+C in server terminal

# Remove database
rm ~/.auralis/library.db

# Remove cache (if applicable)
rm -rf ~/.auralis/cache

# Clean Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# Reinstall dependencies (optional)
pip install --upgrade -r requirements.txt

# Reinitialize
python -m auralis.library.init
```

### Just Remove Database

```bash
rm ~/.auralis/library.db
python -m auralis.library.init
```

### Update Dependencies

```bash
# Check for updates
pip list --outdated

# Update all packages
pip install --upgrade -r requirements.txt

# Or update specific package
pip install --upgrade fastapi
```

---

## Next Steps

### Ready to develop?

1. ✅ Backend running locally with hot reload
2. ✅ API docs accessible at http://localhost:8765/api/docs
3. ✅ Tests passing (run `pytest tests/` to verify)

### Start Phase B (Backend Foundation)

See [PHASE_A_IMPLEMENTATION_PLAN.md](PHASE_A_IMPLEMENTATION_PLAN.md) for Phase B tasks:
- B.1: Endpoint standardization
- B.2: Phase 7.5 cache integration
- B.3: WebSocket enhancement

---

## Getting Help

**Cannot start server?**
- Check virtual environment is activated: `which python` should show venv path
- Check port is free: `lsof -i :8765` should be empty
- Check logs: `LOG_LEVEL=DEBUG python launch-auralis-web.py --dev`

**Database issues?**
- Reset database: `rm ~/.auralis/library.db && python -m auralis.library.init`
- Check database: `sqlite3 ~/.auralis/library.db ".tables"`

**Import errors?**
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check Python version: `python --version` should be 3.13+

**Performance issues?**
- Check cache stats: `curl http://localhost:8765/api/cache/stats`
- Monitor memory: `top -o MEM | grep python`
- Enable debug: `LOG_LEVEL=DEBUG python launch-auralis-web.py --dev`

---

**Last Updated**: 2024-11-28
**Status**: Ready for Phase A/B development
**Maintained By**: Auralis Team
