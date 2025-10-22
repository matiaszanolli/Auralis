#!/bin/bash

# Comprehensive Chunked Streaming Test Suite
# Tests all aspects of the chunked audio processing implementation

set -e

API_BASE="http://localhost:8765/api"
TEST_OUTPUT="/tmp/auralis_test_output"
CHUNKS_DIR="/tmp/auralis_chunks"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create test output directory
mkdir -p "$TEST_OUTPUT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Auralis Chunked Streaming Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: Verify backend is running
echo -e "${YELLOW}Test 1: Backend Health Check${NC}"
HEALTH=$(curl -s "$API_BASE/health" | grep -o '"status":"healthy"' || echo "")
if [ -n "$HEALTH" ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${RED}✗ Backend is not responding${NC}"
    exit 1
fi
echo ""

# Test 2: Get available tracks
echo -e "${YELLOW}Test 2: Fetch Available Tracks${NC}"
TRACKS=$(curl -s "$API_BASE/library/tracks?limit=5")
TRACK_COUNT=$(echo "$TRACKS" | grep -o '"total":[0-9]*' | grep -o '[0-9]*')
echo -e "${GREEN}✓ Found $TRACK_COUNT tracks in library${NC}"

# Get first track ID
TRACK_ID=$(echo "$TRACKS" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
echo -e "  Using track ID: $TRACK_ID"
echo ""

# Test 3: Clear cache for fresh tests
echo -e "${YELLOW}Test 3: Clear Chunk Cache${NC}"
rm -rf "$CHUNKS_DIR"/* 2>/dev/null || true
echo -e "${GREEN}✓ Cache cleared${NC}"
echo ""

# Test 4: Test all presets
echo -e "${YELLOW}Test 4: Test All Presets (First Playback)${NC}"
PRESETS=("adaptive" "gentle" "warm" "bright" "punchy")

for PRESET in "${PRESETS[@]}"; do
    echo -e "  Testing preset: ${BLUE}$PRESET${NC}"
    START=$(date +%s)

    # Request enhanced stream
    HTTP_CODE=$(curl -s -o "$TEST_OUTPUT/test_${PRESET}.wav" \
        -w "%{http_code}" \
        "$API_BASE/player/stream/$TRACK_ID?enhanced=true&preset=$PRESET&intensity=1.0" \
        --max-time 60)

    END=$(date +%s)
    DURATION=$((END - START))

    if [ "$HTTP_CODE" = "200" ]; then
        FILE_SIZE=$(ls -lh "$TEST_OUTPUT/test_${PRESET}.wav" | awk '{print $5}')
        echo -e "    ${GREEN}✓ Success${NC} - ${DURATION}s - Size: $FILE_SIZE"

        # Verify it's a valid WAV file
        FILE_TYPE=$(file "$TEST_OUTPUT/test_${PRESET}.wav" | grep -o "WAVE audio" || echo "unknown")
        if [ "$FILE_TYPE" = "WAVE audio" ]; then
            echo -e "    ${GREEN}✓ Valid WAV file${NC}"
        else
            echo -e "    ${RED}✗ Invalid audio file${NC}"
        fi
    else
        echo -e "    ${RED}✗ Failed${NC} - HTTP $HTTP_CODE"
    fi
done
echo ""

# Test 5: Test cache performance (second playback)
echo -e "${YELLOW}Test 5: Test Cache Performance (Second Playback)${NC}"
for PRESET in "${PRESETS[@]}"; do
    echo -e "  Testing cached preset: ${BLUE}$PRESET${NC}"
    START=$(date +%s)

    HTTP_CODE=$(curl -s -o "$TEST_OUTPUT/test_${PRESET}_cached.wav" \
        -w "%{http_code}" \
        "$API_BASE/player/stream/$TRACK_ID?enhanced=true&preset=$PRESET&intensity=1.0" \
        --max-time 10)

    END=$(date +%s)
    DURATION=$((END - START))

    if [ "$HTTP_CODE" = "200" ] && [ "$DURATION" -lt 2 ]; then
        echo -e "    ${GREEN}✓ Cached response${NC} - ${DURATION}s (instant!)"
    elif [ "$HTTP_CODE" = "200" ]; then
        echo -e "    ${YELLOW}⚠ Slow cache${NC} - ${DURATION}s (expected <2s)"
    else
        echo -e "    ${RED}✗ Failed${NC} - HTTP $HTTP_CODE"
    fi
done
echo ""

# Test 6: Test intensity variations
echo -e "${YELLOW}Test 6: Test Intensity Variations${NC}"
INTENSITIES=("0.0" "0.5" "1.0")

for INTENSITY in "${INTENSITIES[@]}"; do
    echo -e "  Testing intensity: ${BLUE}$INTENSITY${NC}"
    START=$(date +%s)

    HTTP_CODE=$(curl -s -o "$TEST_OUTPUT/test_intensity_${INTENSITY}.wav" \
        -w "%{http_code}" \
        "$API_BASE/player/stream/$TRACK_ID?enhanced=true&preset=adaptive&intensity=$INTENSITY" \
        --max-time 60)

    END=$(date +%s)
    DURATION=$((END - START))

    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "    ${GREEN}✓ Success${NC} - ${DURATION}s"
    else
        echo -e "    ${RED}✗ Failed${NC} - HTTP $HTTP_CODE"
    fi
done
echo ""

# Test 7: Verify chunk files exist
echo -e "${YELLOW}Test 7: Verify Chunk Files${NC}"
CHUNK_COUNT=$(find "$CHUNKS_DIR" -name "*.wav" 2>/dev/null | wc -l)
echo -e "  Found ${GREEN}$CHUNK_COUNT${NC} chunk files in cache"

if [ "$CHUNK_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}✓ Chunks are being cached${NC}"

    # Show some chunk details
    echo -e "  Sample chunk files:"
    find "$CHUNKS_DIR" -name "*chunk_0.wav" 2>/dev/null | head -3 | while read -r chunk; do
        SIZE=$(ls -lh "$chunk" | awk '{print $5}')
        echo -e "    - $(basename "$chunk") ($SIZE)"
    done
else
    echo -e "  ${RED}✗ No chunks found (caching may not be working)${NC}"
fi
echo ""

# Test 8: Test original (non-enhanced) streaming
echo -e "${YELLOW}Test 8: Test Original Audio Streaming${NC}"
START=$(date +%s)

HTTP_CODE=$(curl -s -o "$TEST_OUTPUT/test_original.flac" \
    -w "%{http_code}" \
    "$API_BASE/player/stream/$TRACK_ID?enhanced=false" \
    --max-time 5)

END=$(date +%s)
DURATION=$((END - START))

if [ "$HTTP_CODE" = "200" ]; then
    FILE_SIZE=$(ls -lh "$TEST_OUTPUT/test_original.flac" | awk '{print $5}')
    echo -e "  ${GREEN}✓ Original stream works${NC} - ${DURATION}s - Size: $FILE_SIZE"
else
    echo -e "  ${RED}✗ Failed${NC} - HTTP $HTTP_CODE"
fi
echo ""

# Test 9: Check response headers
echo -e "${YELLOW}Test 9: Verify Response Headers${NC}"
HEADERS=$(curl -sI "$API_BASE/player/stream/$TRACK_ID?enhanced=true&preset=warm&intensity=1.0")

# Check for specific headers
echo "$HEADERS" | grep -q "X-Enhanced: true" && echo -e "  ${GREEN}✓ X-Enhanced header present${NC}" || echo -e "  ${RED}✗ X-Enhanced header missing${NC}"
echo "$HEADERS" | grep -q "X-Preset: warm" && echo -e "  ${GREEN}✓ X-Preset header present${NC}" || echo -e "  ${RED}✗ X-Preset header missing${NC}"
echo "$HEADERS" | grep -q "X-Chunked: true" && echo -e "  ${GREEN}✓ X-Chunked header present${NC}" || echo -e "  ${RED}✗ X-Chunked header missing${NC}"
echo "$HEADERS" | grep -q "Accept-Ranges: bytes" && echo -e "  ${GREEN}✓ Range support enabled${NC}" || echo -e "  ${RED}✗ Range support missing${NC}"
echo ""

# Test 10: Test range requests (seeking)
echo -e "${YELLOW}Test 10: Test Range Requests (Seeking)${NC}"
HTTP_CODE=$(curl -s -o "$TEST_OUTPUT/test_range.wav" \
    -w "%{http_code}" \
    -H "Range: bytes=0-100000" \
    "$API_BASE/player/stream/$TRACK_ID?enhanced=true&preset=adaptive&intensity=1.0")

if [ "$HTTP_CODE" = "206" ] || [ "$HTTP_CODE" = "200" ]; then
    FILE_SIZE=$(ls -lh "$TEST_OUTPUT/test_range.wav" | awk '{print $5}')
    echo -e "  ${GREEN}✓ Range request works${NC} - HTTP $HTTP_CODE - Size: $FILE_SIZE"
else
    echo -e "  ${RED}✗ Range request failed${NC} - HTTP $HTTP_CODE"
fi
echo ""

# Test 11: Cache size analysis
echo -e "${YELLOW}Test 11: Cache Size Analysis${NC}"
if [ -d "$CHUNKS_DIR" ]; then
    TOTAL_SIZE=$(du -sh "$CHUNKS_DIR" 2>/dev/null | awk '{print $1}')
    FILE_COUNT=$(find "$CHUNKS_DIR" -type f | wc -l)
    echo -e "  Total cache size: ${GREEN}$TOTAL_SIZE${NC}"
    echo -e "  Total files: ${GREEN}$FILE_COUNT${NC}"

    # Calculate average chunk size
    if [ "$FILE_COUNT" -gt 0 ]; then
        TOTAL_BYTES=$(du -sb "$CHUNKS_DIR" 2>/dev/null | awk '{print $1}')
        AVG_BYTES=$((TOTAL_BYTES / FILE_COUNT))
        AVG_MB=$((AVG_BYTES / 1024 / 1024))
        echo -e "  Average chunk size: ${GREEN}${AVG_MB}MB${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ Chunks directory not found${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Test output files saved to: ${GREEN}$TEST_OUTPUT${NC}"
echo -e "Chunk cache location: ${GREEN}$CHUNKS_DIR${NC}"
echo ""
echo -e "${GREEN}✓ All tests completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Listen to the generated WAV files to verify audio quality"
echo "2. Check for any audible artifacts or discontinuities"
echo "3. Compare different presets and intensities"
echo "4. Open browser and test with real UI"
echo ""
