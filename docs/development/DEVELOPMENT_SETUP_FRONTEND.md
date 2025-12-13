# Frontend Development Environment Setup

**Version**: 1.0.0
**Last Updated**: 2024-11-28
**Status**: Ready for Use
**Target Audience**: Frontend developers (React/TypeScript)

---

## Quick Start (5 Minutes)

For experienced Node.js developers, here's the fastest path:

```bash
# 1. Install dependencies
cd auralis-web/frontend
npm install

# 2. Start development server
npm run dev

# 3. Open in browser
# Visit: http://localhost:3000
```

---

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows (WSL2 recommended)
- **Node.js**: 20+ LTS (check with `node --version`)
- **npm**: 10+ (check with `npm --version`)
- **Git**: Latest version (check with `git --version`)
- **RAM**: 2GB minimum, 4GB recommended for comfortable development
- **Disk**: 2GB free space for node_modules

### Required Software

#### macOS
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Node.js 20 LTS
brew install node@20

# Link node to PATH
brew link node@20 --force

# Verify installation
node --version  # v20.x.x
npm --version   # 10.x.x
```

#### Ubuntu/Debian
```bash
# Update package manager
sudo apt update

# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version  # v20.x.x
npm --version   # 10.x.x
```

#### Windows (WSL2)
```bash
# In WSL2 Ubuntu terminal
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version
npm --version
```

---

## Step 1: Navigate to Frontend Directory

```bash
# From project root
cd auralis-web/frontend

# Verify correct directory
pwd
# Should end with: .../auralis-web/frontend

# Check files present
ls -la
# Should see: package.json, vite.config.ts, src/, etc.
```

---

## Step 2: Install Dependencies

**What does this do?**
Installs all npm packages the project needs (React, TypeScript, Vite, etc.).

```bash
# Install dependencies (creates node_modules/ folder)
npm install

# This will take 2-5 minutes depending on internet speed
# You'll see output like:
# added 1,234 packages in 2m 45s
```

**Verify installation:**
```bash
# Check that node_modules exists
ls -la node_modules | head -10

# List installed packages
npm list --depth=0
# Should show: react, vite, typescript, @mui/material, etc.

# Verify key packages
npm list react vite typescript
# Should show versions for each
```

**Troubleshooting npm install:**
```bash
# If npm install fails, try:
# 1. Clear cache
npm cache clean --force

# 2. Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json

# 3. Reinstall
npm install

# 4. Check Node.js version (must be 20+)
node --version
```

---

## Step 3: Create Environment Configuration

**What are environment variables?**
Settings that tell the frontend where the backend is, logging level, feature flags, etc.

### Create .env.local File

```bash
# Create .env.local in auralis-web/frontend/
cat > .env.local << 'EOF'
# Frontend Configuration

# API Configuration
VITE_API_URL=http://localhost:8765/api
VITE_WS_URL=ws://localhost:8765/ws

# Logging
VITE_LOG_LEVEL=info

# Feature Flags
VITE_ENABLE_OFFLINE_MODE=true
VITE_ENABLE_CACHE_STATS=true

# Performance
VITE_ENABLE_PROFILING=false
VITE_CHUNK_SIZE_WARNING=500

# Development
VITE_SHOW_PERFORMANCE_METRICS=true
EOF

# Verify .env.local created
cat .env.local
```

### Copy .env.local.example (Alternative)

```bash
# If .env.local.example exists
cp .env.local.example .env.local

# Edit with your preferences
nano .env.local  # or vim, or your favorite editor
```

**Reference Environment Variables:**

```ini
# [Backend Connection]
VITE_API_URL=http://localhost:8765/api     # REST API endpoint
VITE_WS_URL=ws://localhost:8765/ws        # WebSocket endpoint

# [Logging]
VITE_LOG_LEVEL=info                        # debug, info, warn, error

# [Feature Flags]
VITE_ENABLE_OFFLINE_MODE=true              # Enable offline capabilities
VITE_ENABLE_CACHE_STATS=true               # Show cache statistics
VITE_ENABLE_KEYBOARD_SHORTCUTS=true        # Enable keyboard shortcuts

# [Performance]
VITE_ENABLE_PROFILING=false                # Enable React profiling
VITE_CHUNK_SIZE_WARNING=500                # Warn if chunk > 500KB
VITE_LAZY_LOAD_COMPONENTS=true             # Code splitting enabled

# [Development]
VITE_SHOW_PERFORMANCE_METRICS=true         # Show FCP/LCP/CLS metrics
VITE_MOCK_API=false                        # Use MSW mock handlers
```

---

## Step 4: Start Development Server

**What does this do?**
Starts Vite development server with hot module replacement (HMR). Changes to code automatically update in browser.

### Run Development Server

```bash
# Start development server
npm run dev

# You should see output like:
# ➜  Local:   http://localhost:3000/
# ➜  press h to show help

# Your default browser should open automatically
# If not, visit: http://localhost:3000
```

### Hot Module Replacement (HMR)

Once the server is running:

1. Edit a file in `src/` (e.g., `src/App.tsx`)
2. Save the file
3. Browser updates **instantly** without page refresh
4. Component state is **preserved**

This is the core development experience—make changes, see results immediately.

### Stop Development Server

```bash
# Press Ctrl+C in the terminal running `npm run dev`
# You should see:
# SIGINT received, shutting down gracefully...
```

---

## Step 5: Verify Frontend Works

Run this verification checklist:

```bash
# 1. Check Node.js version
node --version
# ✅ Should be v20+

# 2. Check npm version
npm --version
# ✅ Should be 10+

# 3. Check dependencies installed
npm list react vite typescript
# ✅ Should show versions

# 4. Check environment file exists
ls -la .env.local
# ✅ Should exist and be readable

# 5. Build the frontend (verify no errors)
npm run build
# ✅ Should complete with 0 errors
# Output will show: "built in 3.45s"

# 6. Start dev server and test
npm run dev &
sleep 3

# Test API connection
curl http://localhost:3000
# ✅ Should get HTML (app loaded)

# Stop dev server
fg  # Bring to foreground
# Ctrl+C to stop
```

---

## Development Workflow

### Daily Development

```bash
# 1. Navigate to frontend directory
cd auralis-web/frontend

# 2. Start development server (in one terminal)
npm run dev

# 3. In another terminal, make code changes
# - Edit files in src/
# - Server auto-updates in browser
# - Component state preserved

# 4. When done, stop server
# Ctrl+C in server terminal
```

### Running Tests

```bash
# Run all tests
npm run test

# Watch mode (re-run on file changes)
npm run test -- --watch

# With coverage report
npm run test -- --coverage

# Run specific test file
npm run test src/components/Player.test.tsx

# Run tests matching pattern
npm run test -- -t "Player"

# IMPORTANT: Run with memory management for CI
npm run test:memory
# This sets 2GB heap to prevent OOM

# Run tests from backend (Phase 5 fixtures)
# Frontend tests can use backend fixtures for integration testing
pytest tests/ -v  # Backend includes Phase 5 fixture patterns
```

### Phase 5: Frontend & Backend Test Integration

**Phase 5 Complete - Test Suite Migration**

The entire test infrastructure now uses a comprehensive **pytest fixture hierarchy** with **RepositoryFactory pattern** for dependency injection. This benefits both backend and frontend testing:

**Fixture Organization:**
- **Main fixtures** (`tests/conftest.py`) - Available to all tests
- **Backend fixtures** (`tests/backend/conftest.py`) - API endpoint testing
- **Player fixtures** (`tests/auralis/player/conftest.py`) - Player component testing
- **Performance fixtures** (`tests/performance/conftest.py`) - Load and performance testing

**Key Patterns:**
- ✅ **Dependency Injection** - Components receive callables for factory access
- ✅ **Parametrized Testing** - Single test runs with both LibraryManager and RepositoryFactory
- ✅ **Fixture Composition** - Fixtures build on each other in clean hierarchy
- ✅ **Automatic Cleanup** - No manual setUp/tearDown needed

See [DEVELOPMENT_SETUP_BACKEND.md](DEVELOPMENT_SETUP_BACKEND.md#testing-with-phase-5-fixtures-pytest) for complete fixture documentation and examples.

### Building for Production

```bash
# Build optimized bundle
npm run build

# Output in: auralis-web/frontend/build/

# Preview production build locally
npm run preview

# Visit: http://localhost:4173
```

### Type Checking

```bash
# Check TypeScript types
npm run type-check

# Or use tsc directly
npx tsc --noEmit

# Fix common issues
npm run type-check 2>&1 | head -20
```

### Linting & Formatting

```bash
# Run ESLint
npm run lint

# Fix linting issues automatically
npm run lint -- --fix

# Format code with Prettier
npm run format

# Check formatting without fixing
npm run format -- --check
```

---

## Project Structure

Understanding the frontend organization:

```
src/
├── components/           # Reusable React components
│   ├── Player/          # Player-related components
│   │   ├── PlayerControls.tsx
│   │   ├── PlayerControls.test.tsx
│   │   └── types.ts
│   ├── Queue/           # Queue-related components
│   ├── Library/         # Library browser components
│   └── Common/          # Shared components (Button, Modal, etc.)
│
├── features/            # Feature slices (Redux)
│   ├── player/
│   │   ├── playerSlice.ts      # Redux state
│   │   ├── playerSelectors.ts  # Memoized selectors
│   │   └── hooks.ts            # usePlayer hook
│   ├── queue/
│   └── library/
│
├── hooks/               # Custom React hooks
│   ├── usePlayer.ts
│   ├── useQueue.ts
│   ├── useWebSocket.ts
│   └── useKeyboardShortcuts.ts
│
├── services/            # API and external services
│   ├── api.ts          # REST API calls
│   ├── websocket.ts    # WebSocket client
│   └── cache.ts        # TanStack Query setup
│
├── store/              # Redux store configuration
│   ├── store.ts
│   └── middleware.ts
│
├── design-system/      # Design tokens (single source of truth)
│   └── tokens.ts       # Colors, spacing, typography
│
├── test/               # Test utilities and mocks
│   ├── mocks/
│   │   └── handlers.ts # MSW mock handlers
│   ├── test-utils.ts   # Custom render function
│   └── setup.ts        # Test setup
│
├── pages/              # Page-level components
│   ├── Player.tsx
│   ├── Library.tsx
│   └── Settings.tsx
│
├── App.tsx             # Root component
├── main.tsx            # Entry point
└── index.css           # Global styles
```

---

## Component Development

### Creating a New Component

```tsx
// src/components/MyComponent.tsx
import { ReactNode } from 'react';
import { tokens } from '@/design-system';

interface MyComponentProps {
  title: string;
  children: ReactNode;
  onAction?: () => void;
}

export function MyComponent({
  title,
  children,
  onAction
}: MyComponentProps): JSX.Element {
  return (
    <div style={{ padding: tokens.spacing.md }}>
      <h2 style={{ color: tokens.colors.text.primary }}>
        {title}
      </h2>
      {children}
      {onAction && (
        <button onClick={onAction}>Action</button>
      )}
    </div>
  );
}
```

### Adding Tests

```tsx
// src/components/MyComponent.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('should render title', () => {
    render(<MyComponent title="Test Title">Content</MyComponent>);
    expect(screen.getByRole('heading', { name: /test title/i })).toBeInTheDocument();
  });

  it('should call onAction when button clicked', () => {
    const onAction = vi.fn();
    render(
      <MyComponent title="Test" onAction={onAction}>
        Content
      </MyComponent>
    );
    screen.getByRole('button', { name: /action/i }).click();
    expect(onAction).toHaveBeenCalledOnce();
  });
});
```

### Using Redux State

```tsx
// src/components/PlayerDisplay.tsx
import { useAppDispatch, useAppSelector } from '@/store';
import { playerSelectors, playerSlice } from '@/features/player';

export function PlayerDisplay(): JSX.Element {
  const dispatch = useAppDispatch();
  const { isPlaying, currentTrack } = useAppSelector(playerSelectors.selectPlayerState);

  return (
    <div>
      <h2>{currentTrack?.title ?? 'No track'}</h2>
      <button onClick={() => dispatch(playerSlice.actions.togglePlayback())}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>
    </div>
  );
}
```

---

## Troubleshooting

### Problem: "npm: command not found"

**Solution**: Install Node.js or check PATH

```bash
# Check if Node.js is installed
which node
# If not found, install Node.js 20+

# Check npm
which npm

# If installed but not found, add to PATH
# See Node.js installation guide above
```

### Problem: "Port 3000 already in use"

**Solution**: Stop other processes or use different port

```bash
# Find what's using port 3000
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or start on different port
npm run dev -- --port 3001
```

### Problem: "Cannot find module '@/...'"

**Solution**: Check vite.config.ts alias configuration

```bash
# vite.config.ts should have:
# resolve: {
#   alias: {
#     '@': path.resolve(__dirname, './src')
#   }
# }

# If not present, add it and restart dev server
npm run dev
```

### Problem: "WebSocket connection failed"

**Solution**: Check backend is running on correct port

```bash
# Backend should be running on 8765
curl http://localhost:8765/api/health
# Should return: {"status":"healthy"}

# If not running, start backend in another terminal:
# cd auralis
# source venv/bin/activate
# python launch-auralis-web.py --dev

# Check .env.local settings
grep VITE_WS_URL .env.local
# Should show: ws://localhost:8765/ws
```

### Problem: "Tests failing with OOM (Out of Memory)"

**Solution**: Use memory-managed test runner

```bash
# Use built-in memory management
npm run test:memory

# This sets NODE_OPTIONS="--max-old-space-size=2048"
# Prevents OOM on CI systems with limited memory
```

### Problem: "Dependency version conflicts"

**Solution**: Update package-lock.json

```bash
# Delete lock file and reinstall
rm package-lock.json
npm install

# Or update specific package
npm install --save react@latest

# Check for outdated packages
npm outdated
```

---

## IDE Setup

### VS Code

**Recommended Extensions:**
1. ES7+ React/Redux/React-Native snippets
2. ESLint
3. Prettier - Code formatter
4. TypeScript Vue Plugin (Volar)
5. Thunder Client (or similar REST client)

**Setup:**

```json
// .vscode/settings.json
{
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

### WebStorm / JetBrains IDEs

1. Open Project → auralis-web/frontend
2. Mark src/ as Sources Root (right-click → Mark Directory as)
3. Configure → Project → Node.js and npm
4. Set Node interpreter to 20 LTS
5. Run → Edit Configurations → Add npm:
   - Command: run
   - Scripts: dev

Then click Run to start dev server.

---

## Performance Monitoring

### Check Frontend Performance

```bash
# Lighthouse report (requires backend running)
npm run build
npm run preview

# Visit http://localhost:4173 in Chrome
# Open DevTools → Lighthouse
# Run audit on "Mobile" (stricter targets)

# Target metrics from ADR-001:
# ✅ FCP (First Contentful Paint): < 1.5s
# ✅ LCP (Largest Contentful Paint): < 2.5s
# ✅ CLS (Cumulative Layout Shift): < 0.1
# ✅ Bundle size: < 500KB (gzipped)
```

### Memory Leak Detection

```bash
# Run tests with memory tracking
npm run test -- --reporter=verbose

# Monitor test process
top -o MEM -p $(pgrep -f "vitest")

# Check for memory growth in multiple runs
npm run test -- --runs 3
```

### Bundle Analysis

```bash
# Install bundle analyzer
npm install --save-dev rollup-plugin-visualizer

# Add to vite.config.ts:
# import { visualizer } from 'rollup-plugin-visualizer';
# plugins: [visualizer()]

# Build and analyze
npm run build
# Opens visualization in browser
```

---

## Advanced Configuration

### Using Mock API (MSW)

```bash
# Mock Service Worker is pre-configured for testing
# Edit src/test/mocks/handlers.ts to add mock endpoints

# Example mock:
export const handlers = [
  http.get('http://localhost:8765/api/tracks', () => {
    return HttpResponse.json([
      { id: '1', title: 'Track 1', artist: 'Artist 1' },
    ]);
  }),
];

# Run tests with mocked API:
npm run test
```

### Connecting to Production Backend

```bash
# Edit .env.local
VITE_API_URL=https://api.example.com/api
VITE_WS_URL=wss://api.example.com/ws

# Rebuild
npm run build

# Test with preview
npm run preview
```

### Enabling Offline Mode

```bash
# Edit .env.local
VITE_ENABLE_OFFLINE_MODE=true

# Service Worker will cache API responses
# App continues working without internet
```

---

## Clean Up / Reset

### Full Reset (removes all dependencies)

```bash
# Stop dev server first
# Ctrl+C

# Remove node_modules
rm -rf node_modules

# Remove lock file (forces fresh install)
rm package-lock.json

# Clear npm cache
npm cache clean --force

# Reinstall
npm install

# Restart dev server
npm run dev
```

### Reset Build Artifacts

```bash
# Remove build directory
rm -rf build/

# Remove test results
rm -rf test-results/

# Rebuild
npm run build
```

---

## Integration with Backend

### Make Both Run Together

**Terminal 1 - Backend:**
```bash
cd auralis
source venv/bin/activate
python launch-auralis-web.py --dev
```

**Terminal 2 - Frontend:**
```bash
cd auralis-web/frontend
npm run dev
```

**Terminal 3 - Tests:**
```bash
cd auralis-web/frontend
npm run test:memory -- --watch
```

### Testing Full Stack

```bash
# 1. Start backend (Terminal 1)
# 2. Start frontend (Terminal 2)
# 3. Open http://localhost:3000
# 4. Login and test features
# 5. Open DevTools (F12) to check:
#    - Network tab (API calls)
#    - Console (errors/warnings)
#    - Performance tab (metrics)
```

---

## Next Steps

### Ready to develop?

1. ✅ Frontend running locally with hot reload
2. ✅ Dev server accessible at http://localhost:3000
3. ✅ Tests passing (run `npm test` to verify)
4. ✅ Backend accessible at http://localhost:8765

### Start Phase B (Backend Foundation)

See [PHASE_A_IMPLEMENTATION_PLAN.md](../PHASE_A_IMPLEMENTATION_PLAN.md) for Phase B tasks:
- B.1: Backend endpoint standardization
- B.2: Phase 7.5 cache integration
- B.3: WebSocket enhancement

Then Phase C (Frontend Foundation):
- C.1: Project setup & architecture
- C.2: Core components
- C.3: State management & hooks
- C.4: Integration & polish

---

## Getting Help

**Cannot start dev server?**
- Check Node version: `node --version` (must be 20+)
- Check port is free: `lsof -i :3000` should be empty
- Check dependencies: `npm list` should show 1000+ packages
- Check env file: `cat .env.local | head -5`

**Backend not connecting?**
- Check backend running: `curl http://localhost:8765/api/health`
- Check API URL: `grep VITE_API_URL .env.local`
- Check console errors: Press F12 in browser, check Console tab
- Check network: DevTools → Network tab, click API calls

**Tests failing?**
- Run with verbose output: `npm run test -- --reporter=verbose`
- Run single test: `npm run test -- PlayerControls.test.tsx`
- Check for timeout: Default is 30s, some tests might need more
- Use memory management: `npm run test:memory`

**Performance issues?**
- Check bundle size: `npm run build` shows sizes
- Check for console errors: `npm run dev` shows errors as they happen
- Run Lighthouse: Build and preview, check performance metrics
- Profile with DevTools: Open DevTools → Performance tab

---

**Last Updated**: 2024-11-28
**Status**: Ready for Phase A/B development
**Maintained By**: Auralis Team
