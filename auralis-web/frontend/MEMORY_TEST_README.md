# Memory Test Failsafe Guide

## Overview

The **Memory Test Failsafe** is a diagnostic tool designed to safely test the frontend test suite for memory leaks without crashing your system. It's especially useful for Windows testing where memory constraints are tighter.

## Features

✅ **Safe Memory Monitoring**
- Real-time memory tracking with automatic kill switches
- Configurable kill threshold (default: 1.8GB / 2GB max)
- System memory protection

✅ **Category-Based Testing**
- Isolated test runs by component category
- Identifies which test categories leak memory
- Progressive diagnosis from simple → complex

✅ **Detailed Reporting**
- Peak memory usage per category
- Test duration tracking
- System memory snapshots (before/after)
- Pass/fail statistics

✅ **Platform Support**
- Windows, Linux, macOS compatible
- Node.js memory profiling with GC exposure
- Works with Vitest runner

## Quick Start

### Full Suite (All Categories)
```bash
npm run test:memory:failsafe
```

Tests all categories sequentially with 5-second pauses between them.

### Single Category
```bash
npm run test:memory:failsafe -- --category components
npm run test:memory:failsafe -- --category integration
npm run test:memory:failsafe -- --category services
npm run test:memory:failsafe -- --category hooks
npm run test:memory:failsafe -- --category contexts
```

### Custom Heap Size
```bash
# Test with 1GB max heap
npm run test:memory:failsafe -- --max-heap 1024

# Test with 512MB (tight constraint testing)
npm run test:memory:failsafe -- --max-heap 512
```

### Combined Options
```bash
# Test only integration with 1GB heap
npm run test:memory:failsafe -- --category integration --max-heap 1024
```

## Test Categories

| Category | Description | Typical Memory |
|----------|-------------|-----------------|
| `components` | Component rendering and lifecycle | ~200-400MB |
| `integration` | Cross-component integration tests | ~300-600MB |
| `services` | API and service layer tests | ~150-300MB |
| `hooks` | Custom React hooks tests | ~100-200MB |
| `contexts` | Context provider tests | ~100-200MB |

## Understanding the Output

### Example Run
```
[INFO] Memory Test Failsafe - Starting
[INFO] Node: v18.17.0
[INFO] Platform: win32
[INFO] Total System Memory: 16384.00MB

============================================================
Testing: COMPONENTS
Heap size: 2048MB | Kill threshold: 1740.80MB
System memory: 4521.23MB / 16384.00MB
============================================================

[INFO] Running tests...

------------------------------------------------------------
Category: components
Duration: 45.32s
Max Memory Used: 512.34MB
System Memory Change: 4521.23MB → 4512.45MB
[✓] components tests passed
------------------------------------------------------------

============================================================
MEMORY TEST SUMMARY
============================================================
✓ components        | 45.32s | Peak: 512.34MB
✓ integration       | 67.89s | Peak: 623.45MB
✗ services          | 0.00s  | Peak: unknown
✓ hooks             | 23.45s | Peak: 234.56MB
✓ contexts          | 18.90s | Peak: 189.34MB
------------------------------------------------------------
Total Duration: 155.56s
Peak Memory: 623.45MB / 2048MB
Pass Rate: 4/5 (80%)
============================================================
```

### Color Coding
- **✓ (Green)** = Tests passed, memory within limits
- **✗ (Red)** = Tests failed or memory threshold exceeded
- **[WARN]** = Memory approaching 80% of kill threshold
- **[ERROR]** = Memory exceeded kill threshold, process terminated

## Interpreting Results

### Healthy Pattern
```
✓ components        | 45s   | Peak: 450MB
✓ integration       | 60s   | Peak: 550MB
✓ services          | 30s   | Peak: 300MB
```
→ Memory scales reasonably with test complexity

### Memory Leak Pattern
```
✓ components        | 45s   | Peak: 450MB
✗ integration       | OOM   | KILLED
```
→ Integration tests have memory leak, investigate those tests

### Accumulation Pattern
```
✓ components        | 45s   | Peak: 450MB
✓ integration       | 60s   | Peak: 600MB
✓ services          | 30s   | Peak: 900MB ← Growing!
```
→ Memory not being released between categories, check cleanup in test infrastructure

## Troubleshooting

### Process Killed with No Error
**Cause:** Memory exceeded kill threshold
**Solution:**
1. Run with tighter heap: `--max-heap 1024`
2. Test single categories to isolate culprit
3. Check for missing `afterEach()` cleanup

### "Cannot find module" Errors
**Cause:** Script run from wrong directory
**Solution:** Always run from `auralis-web/frontend/` directory
```bash
cd auralis-web/frontend
npm run test:memory:failsafe
```

### Tests Not Running
**Cause:** Vitest not installed or wrong NODE_ENV
**Solution:**
```bash
npm install
NODE_ENV=test npm run test:memory:failsafe
```

### All Tests Fail Immediately
**Cause:** Test setup issue (MSW, providers, etc.)
**Solution:**
1. Verify `npm run test:run` works normally
2. Check `src/test/setup.ts` is loaded
3. Verify providers in test-utils.tsx are complete

## Advanced Usage

### Windows-Specific (Tight RAM)
```bash
# Test with 512MB (Windows 8GB machine)
npm run test:memory:failsafe -- --max-heap 512

# Test only lightest categories first
npm run test:memory:failsafe -- --category services --max-heap 512
npm run test:memory:failsafe -- --category hooks --max-heap 512
npm run test:memory:failsafe -- --category components --max-heap 512
```

### Memory Leak Hunting
```bash
# 1. Start with single service tests
npm run test:memory:failsafe -- --category services

# 2. If passes, try hooks
npm run test:memory:failsafe -- --category hooks

# 3. If passes, try components (highest memory)
npm run test:memory:failsafe -- --category components

# 4. If fails, dig into component tests:
cd src/components
# Run specific component test manually
NODE_ENV=test npx vitest run SpecificComponent.test.tsx
```

### Generate Memory Report
```bash
# Capture output to file for analysis
npm run test:memory:failsafe > memory-test-$(date +%Y%m%d-%H%M%S).log 2>&1

# View report
cat memory-test-20240120-154230.log | grep -E "(✓|✗|Peak Memory|Pass Rate)"
```

## Configuration

Edit `scripts/memory-test-failsafe.js` to adjust:

```javascript
const config = {
  maxHeap: 2048,           // Default max heap in MB
  killThreshold: 1800,     // Kill at 85% of maxHeap
  updateInterval: 500,     // Memory check frequency (ms)
  timeout: 600000,         // 10 minutes per test category
  testCategories: [        // Test categories to run
    'components',
    'integration',
    'services',
    'hooks',
    'contexts'
  ]
};
```

## When to Use This

✅ **Use Failsafe When:**
- Running tests on Windows with limited RAM
- Diagnosing mysterious OOM errors
- Testing after adding new large components
- Validating test cleanup mechanisms
- CI/CD pipeline setup (memory-constrained servers)

❌ **Use Regular `npm test` When:**
- Interactive development (watch mode)
- Quick local verification
- You have 4GB+ RAM available

## Performance Baselines (2GB Heap)

Expected memory usage per category:
- **Services**: 150-300MB (fast, ~30s)
- **Hooks**: 100-200MB (fast, ~20s)
- **Contexts**: 100-200MB (fast, ~20s)
- **Components**: 300-500MB (medium, ~45s)
- **Integration**: 400-700MB (slow, ~60s)

**Total Suite**: ~20-40 minutes, peaks at ~700MB with safe margins to 2GB

## Reporting Issues

If memory tests fail, include:
1. Platform (Windows/Mac/Linux)
2. Node version (`node --version`)
3. Available RAM (`free -h` or Task Manager)
4. Full test output (`npm run test:memory:failsafe > output.log 2>&1`)
5. Which category failed (or if all categories fail)
6. Memory peak reported by test

Example issue report:
```
Platform: Windows 10
RAM: 8GB available
Node: v18.17.0
Failed Category: integration
Peak Memory: 1920MB / 2048MB
Duration: 72s
Error: Process killed by memory threshold
```

## Maintenance

### Updating Test Categories
When adding new test directories, update `scripts/memory-test-failsafe.js`:

```javascript
testCategories: [
  'components',
  'integration',
  'services',
  'hooks',
  'contexts',
  'NEW_CATEGORY'  // Add here
]
```

### Monitoring Trends
Run monthly to track memory trends:
```bash
# Save baseline
npm run test:memory:failsafe > baseline-$(date +%Y%m).log

# Compare across runs
diff baseline-202401.log baseline-202402.log
```

## FAQ

**Q: What's the difference between this and `npm run test:memory`?**
A: This failsafe runs tests by category with safety checks and detailed reporting. `npm run test:memory` runs all tests at once with higher risk of system crash.

**Q: Can I run this on CI/CD?**
A: Yes! It's designed for constrained environments. Set `--max-heap` to your server's available memory minus 500MB buffer.

**Q: Why does it pause between categories?**
A: Gives system time to release memory and prevents cascading memory pressure. Adjust `waitTime` in the script if needed.

**Q: What if my machine doesn't have 2GB available?**
A: Use `--max-heap 1024` or `--max-heap 512`. Better to start small and work up.

**Q: Can I abort a running test?**
A: Yes, Ctrl+C kills the current category and moves to the next (or exits if you press again).

---

**Created:** January 2025
**Version:** 1.0
**Compatibility:** Node 14+, Vitest 1.0+, Windows/Mac/Linux
