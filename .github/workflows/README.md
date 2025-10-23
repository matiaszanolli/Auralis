# GitHub Actions Workflows

This directory contains automated CI/CD workflows for Auralis.

## Active Workflows

### 🔄 ci.yml - Main CI Pipeline
**Triggers**: Every push and PR to master/develop
**Purpose**: Main continuous integration workflow
**Jobs**:
- **lint-python**: Python code formatting and linting (black, isort, flake8)
- **test-python**: Run backend tests on Python 3.9, 3.10, 3.11
- **test-frontend**: Build and test React frontend
- **health-check**: Start backend and verify endpoints

**Status Badge**:
```markdown
![CI](https://github.com/matiaszanolli/Auralis/workflows/CI/badge.svg)
```

### 🧪 backend-tests.yml - Backend Testing
**Triggers**: Changes to backend code (`auralis/`, `auralis-web/backend/`, `tests/`)
**Purpose**: Comprehensive backend testing with coverage
**Jobs**:
- Run backend API tests (154 tests)
- Run core adaptive processing tests
- Upload coverage to Codecov

**Python versions**: 3.9, 3.10, 3.11

### 🎨 frontend-build.yml - Frontend Build
**Triggers**: Changes to frontend code (`auralis-web/frontend/`)
**Purpose**: Build and test React frontend
**Jobs**:
- Install dependencies with npm ci
- Run linter (if configured)
- Run tests (if configured)
- Build production bundle
- Upload build artifacts

**Node versions**: 18.x, 20.x

### 📦 desktop-build.yml - Desktop App Packaging
**Triggers**:
- Pushes to master
- Version tags (`v*`)
- Changes to desktop app code

**Purpose**: Build cross-platform Electron desktop apps
**Jobs**:
- **build-linux**: Package as AppImage and .deb
- **build-windows**: Package as .exe installer
- **build-macos**: Package as .dmg
- **release**: Publish artifacts on version tags

**Platforms**: Linux x64, Windows x64, macOS x64

## Workflow Dependencies

```
ci.yml (on every PR/push)
├── lint-python
├── test-python
├── test-frontend
└── health-check (needs: test-python)

backend-tests.yml (on backend changes)
└── test (matrix: Python 3.9, 3.10, 3.11)

frontend-build.yml (on frontend changes)
└── build (matrix: Node 18.x, 20.x)

desktop-build.yml (on master push or tag)
├── build-linux
├── build-windows
├── build-macos
└── release (needs: all builds, only on tags)
```

## Required Secrets

### Optional Secrets
- `CODECOV_TOKEN`: For uploading test coverage to Codecov (optional)
- `PYPI_USERNAME`: For publishing Python packages (not currently used)
- `PYPI_PASSWORD`: For publishing Python packages (not currently used)

### Auto-provided Secrets
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions (for releases)

## Local Testing

### Run backend tests locally
```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov

# Run tests
python -m pytest tests/backend/ -v --cov=auralis-web/backend
```

### Build frontend locally
```bash
# Install dependencies
cd auralis-web/frontend
npm ci

# Build
npm run build
```

### Package desktop app locally
```bash
# Install all dependencies
cd desktop
npm ci

# Build for current platform
npm run package
```

## Workflow Status

| Workflow | Status | Coverage |
|----------|--------|----------|
| CI | ![CI](https://github.com/matiaszanolli/Auralis/workflows/CI/badge.svg) | - |
| Backend Tests | ![Backend Tests](https://github.com/matiaszanolli/Auralis/workflows/Backend%20Tests/badge.svg) | [![codecov](https://codecov.io/gh/matiaszanolli/Auralis/branch/master/graph/badge.svg)](https://codecov.io/gh/matiaszanolli/Auralis) |
| Frontend Build | ![Frontend Build](https://github.com/matiaszanolli/Auralis/workflows/Frontend%20Build/badge.svg) | - |
| Desktop Build | ![Desktop Build](https://github.com/matiaszanolli/Auralis/workflows/Desktop%20Build/badge.svg) | - |

## Troubleshooting

### Common Issues

**1. Test failures on CI but pass locally**
- Ensure you're using the same Python/Node version as CI
- Check for environment-specific issues (paths, system dependencies)
- Look at the full CI logs for system dependency errors

**2. Desktop build failures**
- Verify PyInstaller can bundle the backend: `pyinstaller auralis-web/backend/main.py`
- Check Electron builder configuration in `desktop/package.json`
- Ensure frontend is built before packaging

**3. Slow CI runs**
- Use caching for pip and npm dependencies (already configured)
- Consider splitting large test suites
- Run expensive tests only on master/tags

### Debug Workflows Locally

Use [act](https://github.com/nektos/act) to run GitHub Actions locally:

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI workflow
act -j test-python

# Run specific workflow
act -W .github/workflows/ci.yml
```

## Making Changes

When modifying workflows:

1. **Test locally first** using act or manual testing
2. **Update this README** if adding/removing workflows
3. **Use path filters** to avoid unnecessary runs
4. **Add status badges** to main README.md
5. **Document required secrets** in this file

## Archived Workflows

Old workflows have been renamed with `.old` extension:
- `build.yml.old`: Old monolithic build workflow (replaced by ci.yml, desktop-build.yml)
- `pythonpublish.yml.old`: Old PyPI publish workflow (not currently used)

These are kept for reference and will be removed in a future version.
