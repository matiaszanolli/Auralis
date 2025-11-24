# Memory Test Failsafe - Quick Start Guide

## 🚀 For Tomorrow's Windows Testing

### Step 1: Prepare Your System
```bash
# Windows only - Check available memory
scripts/diagnose-memory-windows.bat

# macOS/Linux
./scripts/diagnose-memory-linux.sh
```

### Step 2: Choose Your Test Level

**Option A: Full Suite (if you have 2GB+ free memory)**
```bash
npm run test:memory:failsafe
```

**Option B: Conservative (1GB heap - safe for most systems)**
```bash
npm run test:memory:failsafe -- --max-heap 1024
```

**Option C: Tight Constraints (512MB - Windows with low RAM)**
```bash
npm run test:memory:failsafe -- --max-heap 512
```

**Option D: Category-by-Category (safest for diagnosis)**
```bash
# Run each category separately to find the culprit
npm run test:memory:failsafe -- --category services --max-heap 1024
npm run test:memory:failsafe -- --category hooks --max-heap 1024
npm run test:memory:failsafe -- --category contexts --max-heap 1024
npm run test:memory:failsafe -- --category components --max-heap 1024
npm run test:memory:failsafe -- --category integration --max-heap 1024
```

---

## 📊 Understanding the Output

The test will show:
```
✓ components        | 45.32s | Peak: 512.34MB
✓ integration       | 67.89s | Peak: 623.45MB
```

**Meaning:**
- ✓ = Tests passed
- ✗ = Tests failed or killed by memory limit
- Duration = How long tests took
- Peak = Maximum memory used

---

## ⚠️ If Process Gets Killed

The failsafe has **automatic protection** - if memory hits the threshold, it will:
1. Kill the test process gracefully
2. Show which category caused the problem
3. Continue to next category or exit cleanly

You won't lose your system!

---

## 🎯 What to Look For

### Healthy Results
```
✓ services          | 30s   | Peak: 250MB
✓ hooks             | 20s   | Peak: 180MB
✓ contexts          | 20s   | Peak: 190MB
✓ components        | 45s   | Peak: 500MB
✓ integration       | 60s   | Peak: 650MB

Pass Rate: 5/5 (100%)
Peak Memory: 650MB / 2048MB ← Plenty of headroom
```
→ **Conclusion:** No memory leaks detected

### Problem Pattern
```
✓ services          | 30s   | Peak: 250MB
✓ hooks             | 20s   | Peak: 180MB
✓ contexts          | 20s   | Peak: 190MB
✓ components        | 45s   | Peak: 500MB
✗ integration       | OOM   | KILLED ← Exceeds limit

Pass Rate: 4/5 (80%)
Peak Memory: 1800MB / 2048MB ← Hit kill threshold
```
→ **Conclusion:** Integration tests have memory leak
→ **Next:** Run individual integration tests to isolate

---

## 💡 Tips for Tomorrow

### Before Starting
1. Close Chrome, VS Code, Discord, etc. (save your work first!)
2. Close Slack, email, any web apps
3. Ideally: Restart Windows before major test run
4. Run the diagnostic first: `scripts/diagnose-memory-windows.bat`

### During Testing
1. Let it run uninterrupted (don't multitask)
2. Monitor with Task Manager if interested
3. The script shows progress in real-time
4. If a category fails, note which one and continue

### After Testing
1. Save the output to a file:
   ```bash
   npm run test:memory:failsafe > memory-test-$(date /t).txt 2>&1
   ```
2. Compare with previous runs to spot trends
3. If failures occur, share the output for analysis

---

## 🔧 Platform-Specific Commands

### Windows
```bash
# Check memory before running
scripts\diagnose-memory-windows.bat

# Run tests
npm run test:memory:failsafe -- --max-heap 1024
```

### macOS/Linux
```bash
# Check memory before running
./scripts/diagnose-memory-linux.sh

# Run tests
npm run test:memory:failsafe -- --max-heap 1024
```

---

## 🚨 Emergency Exit

If something goes wrong:
- **Press Ctrl+C** to stop immediately
- The script will clean up gracefully
- No system damage will occur

---

## 📝 What We're Looking For

The memory test will help answer:
1. ✅ **Do all tests pass?** (Yes = no code issues)
2. 📊 **What's peak memory usage?** (Healthy = <800MB)
3. 🔍 **Which category leaks memory?** (If any fail, know which)
4. 📈 **Does memory accumulate between tests?** (Should reset)
5. 🎯 **What's the safest heap size?** (For CI/CD)

---

## ✅ Success Checklist

- [ ] Diagnostic script shows 1GB+ free memory
- [ ] Chose appropriate test level (A, B, C, or D)
- [ ] Closed other applications
- [ ] Running from `auralis-web/frontend/` directory
- [ ] Captured output to file for reference
- [ ] All tests passed with reasonable memory usage
- [ ] No kills/failures reported

---

## 📞 If Issues Occur

Save this information for debugging:
1. Full console output (redirect to file)
2. Which category failed
3. Windows Task Manager memory screenshot
4. System specs (RAM, CPU, Node version)

Example:
```bash
# Capture everything
npm run test:memory:failsafe -- --max-heap 1024 2>&1 | tee memory-test-results.txt

# Then share memory-test-results.txt for analysis
```

---

**Status:** Ready for tomorrow's testing! ✨

For detailed documentation, see `MEMORY_TEST_README.md`
