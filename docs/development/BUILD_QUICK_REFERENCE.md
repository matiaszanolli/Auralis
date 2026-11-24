# Build Quick Reference

How the desktop installers are built. Day-to-day development does not need any of this: use
[FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md) to run from source. The release process (version
bump, tag, checklist) is in [releases/RELEASE_GUIDE.md](../releases/RELEASE_GUIDE.md).

CI is the only release publisher. `.github/workflows/build-release.yml` builds every installer and
creates the GitHub release; the steps below are what it runs, in order, so a local build matches it.

## Targets

| Platform | Runner | Artifacts in `dist/` |
|----------|--------|----------------------|
| Linux x64 | `ubuntu-24.04` | `Auralis-<version>.AppImage`, `auralis-desktop_<version>_amd64.deb`, `*.flatpak` |
| Windows x64 | `windows-2025` | `Auralis Setup <version>.exe` (NSIS) |
| macOS arm64 | `macos-15` | `Auralis-<version>-arm64.dmg` |

There is no Intel macOS or Linux arm64 build. The backend binary must match the host architecture,
so each target is built on its own platform.

## Pipeline

Run from the repository root with the Python environment active. Python 3.14, Node 24, pnpm and the
Rust toolchain from [FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md#prerequisites) are required.

```bash
# 1. Build tools and the runtime set, both hash-locked
uv pip install --require-hashes -r requirements-build.txt   # pip, setuptools, wheel, maturin, PyInstaller
uv pip install --require-hashes -r requirements-lock.txt    # everything the backend imports

# 2. Rust DSP wheel: a full-API cp314 build, not abi3
(cd vendor/auralis-dsp && maturin build --release --locked)
uv pip install --no-deps vendor/auralis-dsp/target/wheels/*.whl

# 3. Frontend bundle -> auralis-web/frontend/dist/
pnpm --dir auralis-web/frontend install --frozen-lockfile
pnpm --dir auralis-web/frontend run build

# 4. Stage the renderer and the engine for Electron
mkdir -p desktop/resources/frontend desktop/resources/auralis
rsync -a --delete auralis-web/frontend/dist/ desktop/resources/frontend/
rsync -a --delete auralis/ desktop/resources/auralis/ --exclude='__pycache__' --exclude='*.pyc'

# 5. Freeze the backend -> auralis-web/backend/dist/auralis-backend (auralis-backend.exe on Windows)
(cd auralis-web/backend && pyinstaller --clean --noconfirm auralis-backend.spec)
mkdir -p desktop/resources/backend
cp auralis-web/backend/dist/auralis-backend desktop/resources/backend/

# 6. Package with electron-builder -> dist/
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop run build:linux          # or build:win, build:mac:arm64
```

`desktop/resources/` is git-ignored build output. CI uses `maturin build` plus `pip install`; a uv
venv has no `pip`, so the commands above use `uv pip`.

## Scripts

Root `package.json`:

| Script | Runs |
|--------|------|
| `pnpm run dev` | `dev.js`: the source launcher with Electron (not a build) |
| `pnpm run install:all` | `pnpm install` in `desktop/` and in `auralis-web/frontend/` |
| `pnpm run clean` | Removes `dist/`, both `node_modules/` trees and `auralis-web/frontend/dist/` |
| `pnpm run test`, `test:coverage` | Whole-tree pytest; do not use it as an inner loop (see [CONTRIBUTING.md](../CONTRIBUTING.md#4-testing)) |
| `pnpm run build`, `package`, `package:win\|mac\|linux` | `build.js` and `package.js`; see the note below |

`desktop/package.json`; each build script first runs `desktop/scripts/record-backend-digest.js`, which fails
unless `desktop/resources/backend/` holds the frozen backend:

| Script | electron-builder target |
|--------|------------------------|
| `build` / `dist` | Current platform, default targets |
| `build:linux` | AppImage and deb, x64 |
| `build:linux:flatpak` | Flatpak, x64 (needs `flatpak` and `flatpak-builder`, plus the freedesktop 25.08 runtime) |
| `build:win` | NSIS installer, x64 |
| `build:mac`, `build:mac:arm64` | DMG, arm64 |
| `pack` | Unpacked app directory, no installer |

`build.js` and `package.js` are local conveniences that CI does not run, and they do not follow the
pipeline above: `build.js` expects PyInstaller to emit a directory while the spec emits a single
file, and `package.js` derives its root one level above the checkout. Use the steps above.

## Key files

| File | Role |
|------|------|
| `auralis-web/backend/auralis-backend.spec` | PyInstaller spec: one-file `auralis-backend`, bundles `auralis/`, the backend packages, `auralis_dsp`, `numba` and `llvmlite`; excludes CUDA and unused scientific packages |
| `desktop/package.json` | electron-builder configuration (`build` key): app id, targets, `extraResources` for backend, frontend and `auralis/` |
| `desktop/main.js` | Electron main process: starts the packaged backend from `resources/backend`, waits up to 45 s for it, owns shutdown |
| `desktop/backend-integrity.js` | Verifies the backend binary against the SHA-256 recorded at build time (*backend-digest.json*, packed into the app) |
| `requirements-build.in`, `requirements-build.txt` | Build tools and their hash lock |
| `requirements-lock.txt` | Hash lock of the runtime set; regenerated from `requirements.txt` |
| `vendor/auralis-dsp/rust-toolchain.toml` | Rust release the CI jobs install |

## Release workflow

`build-release.yml` triggers on:

- **Push to `master` or a pull request** touching version files or the workflow: the `prepare` job
  only runs `scripts/validate_release_metadata.py`, so a version that disagrees across
  `auralis/version.py`, `pyproject.toml` and the three `package.json` files fails early.
- **`workflow_dispatch`** with a `version` input: builds all three platforms and uploads artifacts
  (kept 30 days) without a release.
- **A `v*` tag**: builds all three platforms, then `create-release` writes `SHA256SUMS.txt`, signs it
  with a GPG key when the `RELEASE_GPG_PRIVATE_KEY` secret exists, and opens a **draft** GitHub
  release (a pre-release when the version has a suffix such as `-rc.1`).

`auralis/version.py` is the version source of truth; `python sync_version.py <version>` writes it to
every `package.json` and `pyproject.toml`. The installers are not code-signed, so Windows and macOS
show an unidentified-publisher or Gatekeeper warning; see the Release Verification section of
[README.md](../../README.md) for checksum and signature checks.

## Build failures

| Symptom | Fix |
|---------|-----|
| `record-backend-digest: no backend binary in .../desktop/resources/backend` | Run steps 5 and the copy before `pnpm --dir desktop run build:*` |
| `pyinstaller: command not found` | Install `requirements-build.txt` into the active venv (step 1) |
| Frozen backend fails with `No module named ...` | Add the module to `hiddenimports` in `auralis-backend.spec` and rebuild |
| Frozen backend reports no fingerprint engine | The `auralis_dsp` wheel was not installed into the venv before PyInstaller ran (step 2) |
| `maturin` produces a wheel that is not `cp314-cp314` | The venv is not Python 3.14, or a build flag requested `abi3`; CI asserts the full-API build |
| White window or `Backend startup timeout` in the packaged app | The backend did not answer `/api/ready` within 45 s. Run `resources/backend/auralis-backend` from a terminal and read its log |
| `--require-hashes` rejects a package | The lock files drifted from `requirements.txt` or `requirements-build.in`. Regenerate with the `uv pip compile` commands in each file's header |
