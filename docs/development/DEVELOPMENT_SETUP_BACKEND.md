# Backend Development

Per-side depth for working on the Python engine (`auralis/`) and the FastAPI backend
(`auralis-web/backend/`): running the backend alone, configuration, debugging, tooling and common
failures. Installing and launching the project is in [FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md);
ground rules, CI gates and the PR flow are in [CONTRIBUTING.md](../CONTRIBUTING.md). The backend's
design is in [subsystems/backend-api.md](../subsystems/backend-api.md).

Every command assumes the repository's `.venv` is active.

---

## Running the backend alone

`launch-auralis-web.py` starts the backend, waits for `/api/ready`, and supervises Vite or
Electron. To run only the backend:

```bash
cd auralis-web/backend
python main.py --dev
```

`--dev` turns on dev mode: DEBUG logging, Swagger UI at `http://127.0.0.1:8765/api/docs` (also
`/api/redoc` and `/api/openapi.json`), and the wider CORS and WebSocket origin allowlists that the
Vite page needs. Without it none of those routes exist. The server binds `127.0.0.1` only.

`python main.py` does not reload on code changes. For a server that restarts on save, run uvicorn
from the same directory and set dev mode through the environment, because uvicorn's argv has no
`--dev`:

```bash
cd auralis-web/backend
AURALIS_DEV_MODE=1 python -m uvicorn main:app --reload --host 127.0.0.1 --port 8765
```

Probe a running backend:

```bash
curl http://127.0.0.1:8765/api/health   # liveness, library and fingerprint-engine status
curl http://127.0.0.1:8765/api/ready    # 200 once the database and engine are initialized
```

---

## Configuration

No `.env` file is read, and there is no database, host or hot-reload setting beyond the variables
below. The backend uses SQLite at `~/.auralis/library.db` and listens on `127.0.0.1` by design
(see [CLAUDE.md](../../CLAUDE.md)).

| Variable | Effect |
|----------|--------|
| `AURALIS_PORT` | Backend port (default 8765). `launch-auralis-web.py --port` sets it, and the Vite proxy follows it |
| `AURALIS_DEV_MODE` | `1`, `true` or `yes` is equivalent to `--dev` |
| `AURALIS_LOG_LEVEL` | `critical`, `error`, `warning`, `info`, `debug` or `trace`. Overrides the default (DEBUG in dev mode, INFO otherwise); unknown values are ignored |
| `AURALIS_DATA_DIR` | Moves the artwork, fingerprint and upload directories off `~/.auralis`. The database path stays fixed |

The tunable budgets (stream caps, worker counts, scan and shutdown timeouts, rate limits) are
documented in [auralis-web/backend/CONFIG.md](../../auralis-web/backend/CONFIG.md). An invalid
value falls back to its default with a logged warning.

---

## Debugging

- **Logs.** INFO output is kept free of absolute paths so it can be pasted into a bug report; paths
  appear at DEBUG. To read DEBUG on a non-dev backend, set `AURALIS_LOG_LEVEL=debug` rather than
  `AURALIS_DEV_MODE`, which also widens the origin allowlists.
- **HTTP.** In dev mode use `/api/docs` to call any router by hand. Handlers are `async def` and
  report errors as `HTTPException`.
- **WebSocket.** The protocol is in [WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md).
  Chunk geometry comes only from `core/chunk_boundaries.py`.
- **Library database.** Inspect it read-only; the backend holds it open in WAL mode.
  ```bash
  sqlite3 -readonly ~/.auralis/library.db '.tables'
  sqlite3 -readonly ~/.auralis/library.db 'SELECT COUNT(*) FROM tracks;'
  ```
  Application code reaches the database only through
  [`auralis/library/repositories/`](../../auralis/library/repositories/); do not write SQL elsewhere.
- **Fingerprint engine.** `/api/health` reports whether `auralis_dsp` imported. If it did not,
  rebuild it as described in [FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md#4-build-the-rust-dsp-module).
- **VS Code.** `.vscode/settings.json` points the interpreter at `.venv`. A debug configuration
  that mirrors the reload command:
  ```json
  {
    "name": "Backend (FastAPI)",
    "type": "debugpy",
    "request": "launch",
    "module": "uvicorn",
    "cwd": "${workspaceFolder}/auralis-web/backend",
    "args": ["main:app", "--host", "127.0.0.1", "--port", "8765"],
    "env": { "AURALIS_DEV_MODE": "1" },
    "justMyCode": true
  }
  ```
  `auralis-web` contains a hyphen, so it is never imported as a package: set `cwd` to
  `auralis-web/backend` and use `main:app`.
- **PyCharm.** Use the `.venv` interpreter, mark `auralis/` as Sources Root and `tests/` as Test
  Sources Root, and create a Python run configuration for module `uvicorn` with working directory
  `auralis-web/backend`, parameters `main:app`, and environment `AURALIS_DEV_MODE=1`.

---

## Tooling

| Task | Command |
|------|---------|
| Type check | `mypy auralis/ auralis-web/backend/ --ignore-missing-imports` |
| Unused imports and locals (a CI gate) | `pipx run ruff==0.12.12 check --no-cache --select F401,F811,F841 auralis auralis-web/backend scripts tools` |
| Format and lint | `pre-commit run --files <changed files>` (black, isort, pylint, mypy, ruff) |
| Scoped tests | `python -m pytest -q -m "not slow" tests/<subdir>` |
| Coverage for one area | `python -m pytest -q -m "not slow" --cov=auralis --cov-report=html tests/<subdir>` |

`pyproject.toml` runs mypy strict on `auralis.*`, `services.*` and `cache.*`, and with the global
flags on the rest of the backend. `pytest.ini` puts `auralis-web/backend` on `pythonpath`, sets
`asyncio_mode = auto`, and uses `--strict-markers`, so a new marker must be declared there. Test
selection, the nightly `slow` set and the two files that hang when run whole are covered in
[CONTRIBUTING.md](../CONTRIBUTING.md#4-testing).

Fixtures live in `tests/conftest.py` and the per-directory `conftest.py` files:

- `temp_test_db` yields a throwaway database path and `library_database` opens a `LibraryDatabase`
  on it. `LibraryDatabase(':memory:')` does not work because the connection pool rejects it, so
  use a file under `tmp_path`.
- `session_factory`, `repository_factory` and the `*_repository` fixtures use a plain SQLAlchemy
  engine with foreign keys off. A test that depends on foreign-key enforcement uses
  `library_database`.
- `tests/backend/conftest.py` provides `client` (a `TestClient` on an isolated library),
  `library_track`, `mock_track`, `mock_library_database`, `mock_repository_factory` and
  `reset_rate_limits`.
- Any test that boots `main.app` takes `_isolated_library_db`, and the fingerprint-store fixture
  is applied automatically (`tests/app_isolation.py`), so `~/.auralis` is never touched.
- Components that need a repository take a callable or a fixture instead of constructing one.
  See [REPOSITORY_PATTERN.md](REPOSITORY_PATTERN.md) and
  [TESTING_GUIDELINES.md](TESTING_GUIDELINES.md).

---

## Common failures

| Symptom | Cause and fix |
|---------|---------------|
| Collection errors or `NameError` at import on an older Python | The codebase relies on Python 3.14 deferred annotations. Recreate the venv with `uv venv --python-preference only-managed` |
| `No module named 'auralis'` | The venv is not active, or a script runs outside the repository. `main.py` adds the repository root to `sys.path`; for other scripts set `PYTHONPATH` to the repository root |
| `Cannot use port 8765` or an address-in-use error | Another backend is running. Stop it (`lsof -ti:8765`) or set `AURALIS_PORT` / pass `--port` |
| `database is locked` | A second process has the library open. Stop other Auralis and Python processes. Reset only for a damaged file ([FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md#where-data-lives)) |
| `FingerprintUnavailable`, or a fingerprint-engine error in `/api/health` | `auralis_dsp` is not built into this venv |
| `LibsndfileError` | libsndfile cannot open the file. MP3, M4A/AAC, OGG, Opus and WMA are decoded by FFmpeg (`auralis/io/formats.py`), so check `ffmpeg` is on `PATH`. For a broken libsndfile install: `uv pip install --force-reinstall soundfile` |
| `/api/docs` returns 404 | The backend is not in dev mode |
| A pytest run never finishes | It included `tests/backend/test_system_api.py` or `tests/concurrency/test_thread_safety.py`. Scope the run or use `--ignore` |
| Rust-backed tests fail only under `ulimit -v` | Rayon's thread pool cannot reserve address space. Run those tests without the cap |
| Edits to `auralis/` are not picked up | `python main.py` does not reload. Restart it, or use the uvicorn `--reload` command above |
