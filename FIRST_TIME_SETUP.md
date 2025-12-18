# First-Time Setup Guide for Auralis Development

This guide walks you through everything you need to get Auralis running on your machine for the first time.

**⏱️ Estimated Time**: 20-30 minutes

---

## 📋 Prerequisites Checklist

Before you begin, ensure your system has:

- [ ] **Python 3.13+** - Check with `python3 --version`
- [ ] **Node.js 20+ LTS** - Check with `node --version`
- [ ] **Git** - Check with `git --version`
- [ ] **pip** - Check with `pip --version` (comes with Python)
- [ ] **npm** - Check with `npm --version` (comes with Node)
- [ ] **Audio libraries** (platform-dependent, see section below)
- [ ] **~5GB free disk space** for dependencies, database, and build artifacts

### 🔧 System-Specific Audio Dependencies

Auralis requires audio processing libraries. Install based on your OS:

#### **Linux (Ubuntu/Debian)**
```bash
sudo apt-get update
sudo apt-get install -y libsndfile1 libsndfile1-dev ffmpeg libavformat-dev libavcodec-dev
# Optional: for better audio backend support
sudo apt-get install -y libflac-dev libogg-dev libvorbis-dev libopus-dev
```

#### **Linux (Fedora/RHEL)**
```bash
sudo dnf install -y libsndfile libsndfile-devel ffmpeg
```

#### **macOS**
```bash
# Using Homebrew
brew install libsndfile ffmpeg
```

#### **Windows**
Download from:
- FFmpeg: https://ffmpeg.org/download.html (add to PATH)
- libsndfile: Usually handled automatically by Python packages

---

## 🚀 Step-by-Step Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/matiaszanolli/Auralis.git
cd Auralis
```

### 2️⃣ Set Up Python Environment (Recommended: Virtual Environment)

**Option A: Using venv (built-in)**
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

**Option B: Using conda (if you prefer)**
```bash
conda create -n auralis python=3.13
conda activate auralis
```

**Verify activation:**
```bash
which python  # Should show path inside .venv or conda env
python --version  # Should be 3.13+
```

### 3️⃣ Install Python Dependencies
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Expected output**: 40-60 packages installed, no errors

### 4️⃣ Initialize the Database
```bash
python -m auralis.library.init
```

This creates:
- `~/.auralis/library.db` - SQLite database for your music library
- `~/.auralis/` - Configuration directory

### 5️⃣ Set Up Node.js & Frontend Dependencies

```bash
# Check Node version
node --version  # Should be 20+ LTS

# Install frontend dependencies
cd auralis-web/frontend
npm install
cd ../..
```

**Expected output**: ~1000+ packages installed

### 6️⃣ Verify Environment Configuration

The project uses environment variables from `.env`:
```bash
cat .env
```

**For local development, these defaults should work:**
- Backend runs on `http://localhost:8765`
- Frontend dev server runs on `http://localhost:3000`
- Database uses SQLite at `~/.auralis/library.db`

**To override for your setup:**
```bash
cp .env .env.local  # Create local override (not tracked by git)
# Edit .env.local as needed
```

---

## ✅ Verify Your Setup

### Quick Verification Script
```bash
echo "=== Python ==="
python --version
python -c "import numpy, scipy, fastapi, pytest; print('✅ Core Python packages OK')"

echo "=== Node ==="
node --version
npm --version

echo "=== Database ==="
ls -lh ~/.auralis/library.db

echo "=== Audio Libraries ==="
python -c "import soundfile; print('✅ Audio I/O OK')"

echo "=== Frontend ==="
cd auralis-web/frontend && npm list react react-dom 2>/dev/null | head -5
```

---

## 🎯 Run Your First Development Session

### Option A: Full Web Interface (Recommended)
```bash
# From project root
python launch-auralis-web.py --dev
```

Then visit:
- **Backend**: http://localhost:8765/api/docs (Swagger docs)
- **Frontend**: http://localhost:3000 (Vite dev server)
- **Health check**: `curl http://localhost:8765/api/health`

### Option B: Backend Only
```bash
cd auralis-web/backend
python -m uvicorn main:app --reload
# Visit http://localhost:8765/api/docs
```

### Option C: Frontend Only
```bash
cd auralis-web/frontend
npm run dev
# Visit http://localhost:3000
```

---

## 🧪 Run Tests to Verify Everything Works

### Backend Tests (Fast, skips slow tests)
```bash
python -m pytest tests/ -m "not slow" -v --tb=short
# Expected: 700+ tests passing in ~1-2 minutes
```

### Frontend Tests (Watch mode)
```bash
cd auralis-web/frontend
npm test
# Press 'q' to quit, 'a' to run all tests
```

---

## 📚 Next Steps

1. **Read the main architecture guide**: [CLAUDE.md](CLAUDE.md) - Overall architecture and patterns
2. **Understand the audio pipeline**: [ADAPTIVE_MASTERING_SYSTEM.md](ADAPTIVE_MASTERING_SYSTEM.md)
3. **Learn the testing approach**: [docs/development/TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)
4. **Explore the codebase**: Start with `auralis/core/hybrid_processor.py` (main audio pipeline)

---

## 🛠️ IDE Setup (Optional but Recommended)

### VS Code
1. **Install extensions**:
   - Python (Microsoft)
   - Pylance (Microsoft)
   - Black Formatter (Microsoft)
   - TypeScript Vue Plugin (Vue)
   - ESLint (Microsoft)
   - Prettier (Code Formatter)

2. **Settings** (`.vscode/settings.json` - already partially configured):
   ```json
   {
     "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
     "python.linting.enabled": true,
     "python.formatting.provider": "black",
     "editor.formatOnSave": true
   }
   ```

3. **Debug Python**:
   - Press `Ctrl+Shift+D` (or Cmd+Shift+D on macOS)
   - Click "Run and Debug"
   - Select "Python" from dropdown

---

## ⚠️ Common First-Time Issues & Fixes

| Issue | Solution |
|-------|----------|
| `python: command not found` | Install Python 3.13+ or use `python3` instead |
| `ModuleNotFoundError: numpy` | Did you activate venv? `source .venv/bin/activate` |
| `libsndfile not found` | Install audio libraries (see section above) |
| `Port 8765 already in use` | Kill existing process: `lsof -ti:8765 \| xargs kill -9` |
| `SQLite database locked` | Delete database: `rm ~/.auralis/library.db` (will rescan) |
| `npm: command not found` | Install Node 20+ LTS from https://nodejs.org/ |
| `Module not found (TypeScript)` | Run `cd auralis-web/frontend && npm install` |
| `Audio file won't play` | Install ffmpeg: `brew install ffmpeg` (macOS) or apt-get (Linux) |

---

## 🔍 Verify Audio Backend

The system uses `audioread` which supports multiple backends. Check which backends are available:

```bash
python -c "
import audioread
print('Available audioread backends:')
for backend in audioread.get_backends():
    print(f'  ✅ {backend.__name__}')
"
```

**Expected output** (at least one):
- `FFmpeg` (most flexible)
- `libsndfile`
- `core audio` (macOS)
- `WinMM` (Windows)

---

## 📞 Need Help?

- **Setup issues**: Check "Common First-Time Issues" section above
- **Audio problems**: See `AUDIO_DEPENDENCY_TROUBLESHOOTING.md` (reference in CLAUDE.md)
- **Architecture questions**: Read [CLAUDE.md](CLAUDE.md)
- **Bug reports**: Create a GitHub issue with setup details

---

## 🎉 You're Ready!

Once setup completes successfully, you should:
- ✅ Have a running backend at http://localhost:8765
- ✅ Have a running frontend at http://localhost:3000
- ✅ Be able to see API documentation at http://localhost:8765/api/docs
- ✅ Have tests passing (`pytest tests/ -m "not slow" -v`)

**Happy developing!** 🎵
