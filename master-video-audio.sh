#!/bin/bash
set -e

# Script: master-video-audio.sh
# Description: Extract audio from video, master it with auto_master.py, and replace the original audio
# Usage: ./master-video-audio.sh input.mp4 [-o output.mp4] [-i 0.8]

# Check dependencies
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ Error: ffmpeg is not installed"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Error: python3 is not installed"; exit 1; }

# Default values
INTENSITY="1.0"
OUTPUT_FILE=""
INPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -i|--intensity)
            INTENSITY="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 input_video.mp4 [-o output.mp4] [-i 0.8]"
            echo ""
            echo "Options:"
            echo "  -o, --output      Output video file (default: input_mastered.mp4)"
            echo "  -i, --intensity   Mastering intensity 0.0-1.0 (default: 1.0)"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 video.mp4"
            echo "  $0 video.mp4 -o mastered_video.mp4 -i 0.8"
            exit 0
            ;;
        *)
            if [ -z "$INPUT_FILE" ]; then
                INPUT_FILE="$1"
            else
                echo "❌ Error: Unknown argument '$1'"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate input file
if [ -z "$INPUT_FILE" ]; then
    echo "❌ Error: No input file specified"
    echo "Usage: $0 input_video.mp4 [-o output.mp4] [-i 0.8]"
    exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ Error: Input file '$INPUT_FILE' does not exist"
    exit 1
fi

# Set output file if not specified
if [ -z "$OUTPUT_FILE" ]; then
    BASENAME="${INPUT_FILE%.*}"
    EXTENSION="${INPUT_FILE##*.}"
    OUTPUT_FILE="${BASENAME}_mastered.${EXTENSION}"
fi

# Create temporary files in scratchpad
TEMP_DIR="/tmp/claude/-mnt-data-src-matchering/169c7d9b-32ff-4d20-9d4e-70afc3efd25b/scratchpad"
mkdir -p "$TEMP_DIR"
TEMP_AUDIO="${TEMP_DIR}/temp_audio_$$.wav"
TEMP_MASTERED="${TEMP_DIR}/temp_mastered_$$.wav"

# Cleanup function
cleanup() {
    rm -f "$TEMP_AUDIO" "$TEMP_MASTERED"
}
trap cleanup EXIT

echo "🎬 Processing video: $INPUT_FILE"
echo "📊 Mastering intensity: $INTENSITY"
echo ""

# Step 1: Extract audio from video
echo "🎵 Step 1/3: Extracting audio from video..."
ffmpeg -i "$INPUT_FILE" -vn -acodec pcm_s16le -ar 44100 -ac 2 "$TEMP_AUDIO" -y -loglevel warning -stats
echo "  ✓ Audio extracted"
echo ""

# Step 2: Master the audio with auto_master.py
echo "🎚️  Step 2/3: Mastering audio..."
python3 auto_master.py "$TEMP_AUDIO" -o "$TEMP_MASTERED" -i "$INTENSITY"
echo "  ✓ Audio mastered"
echo ""

# Step 3: Replace audio in video
echo "🎬 Step 3/3: Replacing audio in video..."
# Copy video stream, replace audio stream, copy all other streams
ffmpeg -i "$INPUT_FILE" -i "$TEMP_MASTERED" \
    -map 0:v:0 -map 1:a:0 -map 0:s? -map 0:d? -map 0:t? \
    -c:v copy -c:a aac -b:a 320k -c:s copy \
    -shortest \
    "$OUTPUT_FILE" -y -loglevel warning -stats
echo "  ✓ Video created"
echo ""

echo "✨ Success! Output saved to: $OUTPUT_FILE"
echo ""
echo "📊 File sizes:"
echo "  Input:  $(du -h "$INPUT_FILE" | cut -f1)"
echo "  Output: $(du -h "$OUTPUT_FILE" | cut -f1)"
