# First-Time Setup

This guide takes a fresh checkout to a running development session. It is the
canonical setup procedure; other docs link here instead of repeating it.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| [uv](https://docs.astral.sh/uv/) | current | Provisions the Python interpreter and the virtual environment |
| Python | 3.14 (GIL build) | `.python-version` pins it; uv downloads it when missing. `3.14t` is not supported |
| Node.js | 24 or newer | `engines` in every `package.json` |
| pnpm | 10.20.0 | The only supported JS package manager. `corepack enable` installs the version each `package.json` pins in `packageManager` |
| Rust | stable via [rustup](https://rustup.rs/) | `vendor/auralis-dsp/rust-toolchain.toml` pins the exact release; rustup installs it on first use |
| Git | any | |
| libsndfile and FFmpeg | system packages | See below |

Audio is decoded by libsndfile (through `soundfile`) for WAV, FLAC, AIFF and AU,
and by FFmpeg for MP3, M4A/AAC, OGG, WMA and Opus (`auralis/io/formats.py`).
Compressed files do not load without `ffmpeg` on `PATH`.

```bash
# Debian/Ubuntu
sudo apt-get install -y libsndfile1 ffmpeg
# Fedora
sudo dnf install -y libsndfile ffmpeg
# macOS (Homebrew)
brew install libsndfile ffmpeg
# Windows: install FFmpeg from https://ffmpeg.org/download.html and add it to PATH
```

## Setup

Run every command from the repository root.

### 1. Clone

```bash
git clone https://github.com/matiaszanolli/Auralis.git
cd Auralis
```

### 2. Create the Python environment

```bash
uv venv --python-preference only-managed
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

`--python-preference only-managed` makes uv use its own CPython 3.14. Without it,
uv can pick an older interpreter or a pyenv shim that happens to be on `PATH`.
`which python` should print a path inside `.venv`.

### 3. Install the Python dependencies

```bash
uv pip install -r requirements.txt     # runtime
uv pip install -e '.[dev]'             # pytest, mypy, black, isort, pre-commit
uv pip install maturin                 # builds the Rust module in step 4
```

`requirements.txt` carries runtime pins only. The `dev` extra in `pyproject.toml`
provides the test and type-check tools.

### 4. Build the Rust DSP module

The 25D fingerprint runs in Rust (`vendor/auralis-dsp`, imported as `auralis_dsp`).
There is no Python fallback: without the module every fingerprint and every adaptive
master fails with `FingerprintUnavailable`, `/api/health` reports
`fingerprint_engine_available: false`, and `/api/ready` stays at 503, so the launcher
aborts with `Backend initialization failed`.

```bash
cd vendor/auralis-dsp && maturin develop --uv --release && cd ../..
python -c "import auralis_dsp; print('auralis_dsp OK')"
```

`--uv` is required because a uv-created venv has no `pip`; maturin installs the
wheel through `uv` instead. `--release` matches what CI and the installers build.

### 5. Install the JavaScript dependencies

```bash
pnpm --dir auralis-web/frontend install --frozen-lockfile
pnpm --dir desktop install --frozen-lockfile
```

The frontend directory holds the React renderer and Vite; `desktop` holds Electron.
The root `package.json` has no install step of its own.

## Run your first development session

With the environment from step 2 active:

```bash
pnpm run dev
```

`pnpm run dev` runs `dev.js`, which starts `python launch-auralis-web.py --electron`.
The launcher supervises one backend (port 8765) and one Vite server (port 3000),
then opens the Electron window once `/api/ready` answers. Ctrl+C stops everything
it started. `AURALIS_PYTHON` selects a different interpreter for `dev.js`.

For a browser preview of the renderer instead of Electron:

```bash
python launch-auralis-web.py --dev                    # backend + Vite
pnpm --dir auralis-web/frontend run build             # once, for the next line
python launch-auralis-web.py                          # backend serving the built frontend
```

The browser page is a developer preview. Electron is the supported client.

| Flag | Effect |
|------|--------|
| `--dev` | Serve the frontend with Vite and run the backend in dev mode |
| `--electron` | Open the Electron app (implies dev mode; needs Vite on port 3000) |
| `--port N` | Backend port (default 8765) |
| `--frontend-port N` | Vite port (default 3000) |
| `--no-browser` | Do not open a browser tab |

`GET /api/health` reports liveness. `GET /api/ready` returns 200 once the database,
player state and fingerprint engine are initialized. Dev mode also serves Swagger UI at
`http://127.0.0.1:8765/api/docs`; production mode serves no API docs.

Environment variables the backend reads are listed in
[auralis-web/backend/CONFIG.md](auralis-web/backend/CONFIG.md).

## Verify the setup

```bash
python -c "import fastapi, numpy, soundfile, auralis_dsp; print('python OK')"
ffmpeg -version | head -1
node --version && pnpm --version
python -m pytest -q -m "not slow" tests/auralis/dsp
```

The last command is one domain of the backend suite. See
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md#4-testing) for scoping tests and for the
suites that never run whole.

## Where data lives

Everything user-specific is under `~/.auralis/`:

| Path | Contents |
|------|----------|
| `library.db` | SQLite library: tracks, playlists, settings |
| `library.backup_*.db` | Backups written before a schema migration |
| `artwork/`, `fingerprints/`, `cache/` | Regenerable caches |
| `uploads/` | Files accepted through the upload endpoint |

The database is created and migrated on first start; no manual step exists.
`AURALIS_DATA_DIR` moves the cache and upload directories. The default database
path is fixed at `~/.auralis/library.db`.

To reset, stop the backend first, then:

```bash
rm -f ~/.auralis/library.db ~/.auralis/library.db-wal ~/.auralis/library.db-shm   # empty library; rescan your folders
rm -rf ~/.auralis                                                                   # everything, caches and backups included
```

## Common first-run failures

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError` for numpy, fastapi or others | The venv is not active: `source .venv/bin/activate`, then redo step 3 |
| `Backend initialization failed; see backend logs`, `FingerprintUnavailable`, or an import error naming `auralis_dsp` | Step 4 was skipped or ran outside the active venv |
| `Failed to find pip (if working with a uv venv try maturin develop --uv)` | Add `--uv` to the `maturin develop` command |
| `Cannot use port 8765` | Another process holds the port. Stop it (`lsof -ti:8765`) or pass `--port` |
| `Built frontend missing` | Run the frontend build from the section above, or launch with `--dev` |
| `Install Node.js and run pnpm --dir auralis-web/frontend install first` | Step 5 was skipped for the frontend |
| `Run pnpm --dir desktop install first` | Step 5 was skipped for `desktop` |
| `pnpm: command not found` | Install Node 24+, then `corepack enable` |
| `database is locked` | Another Auralis or Python process has the library open. Stop it; reset only if the file is damaged |
| Compressed audio will not play or scan | `ffmpeg` is missing from `PATH` |

## Next steps

- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md): ground rules, testing, CI gates, PR flow
- [CLAUDE.md](CLAUDE.md): architecture, invariants and project principles
- [docs/subsystems/dsp-engine.md](docs/subsystems/dsp-engine.md): the audio pipeline
- [docs/development/DEVELOPMENT_SETUP_BACKEND.md](docs/development/DEVELOPMENT_SETUP_BACKEND.md) and [docs/development/DEVELOPMENT_SETUP_FRONTEND.md](docs/development/DEVELOPMENT_SETUP_FRONTEND.md): debugging and tooling per side
- [docs/development/BUILD_QUICK_REFERENCE.md](docs/development/BUILD_QUICK_REFERENCE.md): packaging installers
