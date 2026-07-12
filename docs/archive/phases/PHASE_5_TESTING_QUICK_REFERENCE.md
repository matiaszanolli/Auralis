# Phase 5 - Quick Reference Testing Guide

## Pre-Testing Checklist

```bash
# 1. Verify Python syntax
python -m py_compile auralis-web/backend/fingerprint_generator.py
python -m py_compile auralis-web/backend/audio_stream_controller.py
python -m py_compile auralis-web/backend/chunked_processor.py
python -m py_compile auralis-web/backend/routers/system.py

# 2. Check database exists
sqlite3 ~/.auralis/library.db ".tables" | grep -i track

# 3. Verify gRPC server can run
cd vendor/auralis-dsp && ./target/release/fingerprint-server --help 2>/dev/null || echo "Need to build"

# 4. Ensure backend port is free
lsof -ti:8765 | xargs kill -9 2>/dev/null || echo "Port 8765 free"
```

---

## Quick Test Commands

### Test 1: Database Connectivity

```bash
# Check if database accessible
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) as track_count FROM tracks;"

# Clear fingerprints for testing
sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints WHERE 1=1;"

# Verify cleared
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) as fingerprint_count FROM track_fingerprints;"
```

### Test 2: gRPC Server Status

```bash
# Check if server running
pgrep -f "fingerprint-server" && echo "✅ Server running" || echo "❌ Server not running"

# Test server connectivity
curl -s http://localhost:50051/health && echo "✅ Server healthy" || echo "❌ Server unreachable"

# Start server if needed
cd vendor/auralis-dsp
./target/release/fingerprint-server &
```

### Test 3: Backend Python Imports

```bash
# Test imports in isolation
python3 << 'EOF'
import sys
sys.path.insert(0, 'auralis-web/backend')
from fingerprint_generator import FingerprintGenerator
from audio_stream_controller import AudioStreamController
print("✅ All imports successful")
EOF
```

### Test 4: Type Checking

```bash
# Run mypy on modified files
mypy auralis-web/backend/fingerprint_generator.py \
     auralis-web/backend/audio_stream_controller.py \
     auralis-web/backend/chunked_processor.py \
     auralis-web/backend/routers/system.py \
     --ignore-missing-imports || echo "See errors above"
```

---

## Testing Scenarios

### Scenario A: Cold Cache (First Play)

**Setup**:
```bash
# Clear all fingerprints
sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints WHERE 1=1;"

# Start gRPC server
cd vendor/auralis-dsp
./target/release/fingerprint-server &
SERVER_PID=$!

# Start backend
cd auralis-web/backend
python -m uvicorn main:app --reload --port 8765 &
BACKEND_PID=$!
```

**Execute**:
```bash
# Send WebSocket message to play track
python3 << 'EOF'
import asyncio
import json
import websockets

async def test():
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        # Send play_enhanced message
        message = {
            "type": "play_enhanced",
            "data": {
                "track_id": 123,
                "preset": "adaptive",
                "intensity": 1.0
            }
        }
        await ws.send(json.dumps(message))

        # Receive responses
        try:
            while True:
                response = await ws.recv()
                data = json.loads(response)
                print(f"Received: {data.get('type')}")
                if data.get('type') == 'audio_stream_end':
                    break
        except asyncio.TimeoutError:
            print("Stream timeout (expected)")

asyncio.run(test())
EOF
```

**Verify**:
```bash
# Check database for stored fingerprint
sqlite3 ~/.auralis/library.db "SELECT track_id, lufs, crest_db FROM track_fingerprints WHERE track_id=123;"

# Check backend logs for 2D LWRP decisions
tail -50 /tmp/backend.log | grep -E "LWRP|fingerprint"
```

### Scenario B: Warm Cache (Second Play)

**Execute**:
```bash
# Same WebSocket message as above
python3 << 'EOF'
import asyncio
import json
import websockets
import time

async def test():
    start = time.time()
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        message = {
            "type": "play_enhanced",
            "data": {
                "track_id": 123,
                "preset": "adaptive",
                "intensity": 1.0
            }
        }
        await ws.send(json.dumps(message))

        try:
            response = await ws.recv()
            elapsed = time.time() - start
            print(f"First response in {elapsed:.3f}s (expect < 0.1s for warm cache)")
        except asyncio.TimeoutError:
            print("Timeout")

asyncio.run(test())
EOF
```

**Verify**:
```bash
# Should see cache hit in logs
tail -20 /tmp/backend.log | grep "cache hit"

# Should be faster than Scenario A
# Expected: < 100 ms vs 1-2 seconds for Scenario A
```

### Scenario C: gRPC Server Unavailable

**Setup**:
```bash
# Stop gRPC server
pkill -f "fingerprint-server"

# Clear fingerprints
sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints WHERE 1=1;"
```

**Execute**:
```bash
# Send play_enhanced (will timeout waiting for gRPC)
python3 << 'EOF'
import asyncio
import json
import websockets
import time

async def test():
    start = time.time()
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        message = {
            "type": "play_enhanced",
            "data": {
                "track_id": 456,
                "preset": "adaptive",
                "intensity": 1.0
            }
        }
        await ws.send(json.dumps(message))

        try:
            response = await ws.recv()
            elapsed = time.time() - start
            print(f"Response received after {elapsed:.1f}s")
            if elapsed > 60:
                print("✅ Timeout handled correctly (~60s)")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test())
EOF
```

**Verify**:
```bash
# Check logs for timeout handling
tail -50 /tmp/backend.log | grep -i "timeout\|graceful"

# Verify audio still played (no error)
# Expected: Audio streams after 60s timeout
```

### Scenario D: Concurrent Plays

**Execute**:
```bash
# Start 3 concurrent plays
python3 << 'EOF'
import asyncio
import json
import websockets

async def play(track_id):
    try:
        async with websockets.connect("ws://localhost:8765/ws") as ws:
            message = {
                "type": "play_enhanced",
                "data": {
                    "track_id": track_id,
                    "preset": "adaptive",
                    "intensity": 1.0
                }
            }
            await ws.send(json.dumps(message))
            response = await ws.recv()
            print(f"Track {track_id}: {response.get('type')}")
    except Exception as e:
        print(f"Track {track_id} error: {e}")

async def main():
    await asyncio.gather(
        play(123),
        play(456),
        play(789)
    )

asyncio.run(main())
EOF
```

**Verify**:
```bash
# Check database - should have 3 fingerprints
sqlite3 ~/.auralis/library.db "SELECT COUNT(*) as count FROM track_fingerprints;"

# Monitor system resources
# Expected: Memory < 5 MB, CPU reasonable
```

---

## Log Analysis Commands

### Find Fingerprint Generation Logs

```bash
# All fingerprint-related logs
tail -100 /tmp/backend.log | grep -i fingerprint

# Specific 2D LWRP decisions
tail -100 /tmp/backend.log | grep "\[2D LWRP\]"

# Database operations
tail -100 /tmp/backend.log | grep "database\|cache"
```

### Extract Performance Data

```bash
# Get timing information
tail -200 /tmp/backend.log | grep -E "generating|generated|loaded|timeout"

# Calculate average response times
# (requires timestamped logs)
tail -200 /tmp/backend.log | grep "audio_stream_start\|audio_stream_end"
```

### Error Detection

```bash
# Find warnings
tail -100 /tmp/backend.log | grep "WARNING\|Error\|Failed"

# Find graceful fallbacks
tail -100 /tmp/backend.log | grep "graceful\|fallback\|proceeding without"
```

---

## Test Results Template

```markdown
# Phase 5 Test Results

## Scenario A: Cold Cache
- Duration: [XX seconds]
- Fingerprint generated: [Yes/No]
- Audio quality: [Excellent/Good/Poor]
- 2D LWRP logged: [Yes/No]
- Issues: [None/List]

## Scenario B: Warm Cache
- Lookup time: [X ms]
- Audio quality: [Excellent/Good/Poor]
- Performance improvement vs A: [XX%]
- Issues: [None/List]

## Scenario C: gRPC Unavailable
- Timeout respected: [Yes/No]
- Audio still streamed: [Yes/No]
- Graceful degradation: [Yes/No]
- User-facing error: [Yes/No]
- Issues: [None/List]

## Scenario D: Concurrent
- Concurrent streams: [3]
- All successful: [Yes/No]
- Memory overhead: [X MB]
- Race conditions: [None/Found]
- Issues: [None/List]

## Overall Assessment
- Ready for production: [Yes/No]
- Blockers: [None/List]
- Recommendations: [List]
```

---

## Cleanup Commands

```bash
# Stop background services
pkill -f "fingerprint-server"
lsof -ti:8765 | xargs kill -9
lsof -ti:3000 | xargs kill -9

# Clear test data
sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints WHERE 1=1;"

# Check everything stopped
pgrep -f "fingerprint-server" || echo "✅ gRPC server stopped"
lsof -ti:8765 2>/dev/null || echo "✅ Backend port free"
```

---

## Success Criteria

✅ **All Tests Pass When**:
- [x] Fingerprint caching works (< 1 ms retrieval)
- [x] Fingerprint generation works (2-5 seconds)
- [x] 2D LWRP decisions logged correctly
- [x] Audio streams in all scenarios
- [x] Graceful fallback on timeout
- [x] No database errors
- [x] Concurrent operations safe
- [x] Memory usage reasonable
- [x] No user-facing errors

---

## Resources

- **Testing Plan**: [PHASE_5_TESTING_PLAN.md](PHASE_5_TESTING_PLAN.md)
- **Complete Summary**: [PHASE_7_3_COMPLETE_SUMMARY.md](PHASE_7_3_COMPLETE_SUMMARY.md)
- **Integration Plan**: [INTEGRATION_PLAN_FINGERPRINTING_MASTERING_STREAMING.md](INTEGRATION_PLAN_FINGERPRINTING_MASTERING_STREAMING.md)

---

**Ready to test!** 🚀
