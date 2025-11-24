#!/bin/bash

# Memory Diagnostic Script for Linux/macOS
# Checks system memory status before running memory tests
# Usage: ./diagnose-memory-linux.sh

echo ""
echo "============================================================"
echo "Memory Diagnostic Tool (Linux/macOS)"
echo "============================================================"
echo ""

# Get system info
echo "[System Information]"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    TOTAL_MEM=$(sysctl -n hw.memsize | awk '{printf "%.0f", $1/1024/1024/1024}')
    FREE_MEM=$(vm_stat | grep "Pages free" | awk '{printf "%.0f", ($3 * 4096) / 1024 / 1024 / 1024}')
    USED_MEM=$(vm_stat | grep "Pages active\|Pages inactive\|Pages wired" | awk '{sum += $3} END {printf "%.0f", (sum * 4096) / 1024 / 1024 / 1024}')
    OS_TYPE="macOS"
else
    # Linux
    TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}' | sed 's/G//')
    FREE_MEM=$(free -h | awk '/^Mem:/ {print $7}' | sed 's/G//')
    AVAILABLE_MEM=$(free -h | awk '/^Mem:/ {print $7}' | sed 's/G//')
    OS_TYPE="Linux"
fi

echo "Platform:      $OS_TYPE"
echo "Total Memory:  ${TOTAL_MEM}GB"
echo "Free Memory:   ${FREE_MEM}GB"
echo ""

# Parse as integers for comparison
TOTAL_INT=$(printf "%.0f" $TOTAL_MEM)
FREE_INT=$(printf "%.0f" $FREE_MEM)

# Check if we have enough RAM for tests
echo "[Memory Check]"
if [ $FREE_INT -lt 1 ]; then
    echo "⚠  WARNING: Only ${FREE_INT}GB free memory"
    echo "   Recommended: 1GB+ available"
    echo "   Action: Close unnecessary applications"
elif [ $FREE_INT -lt 2 ]; then
    echo "✓ Adequate memory for constrained testing"
else
    echo "✓ Good memory available for full testing"
fi

# Recommendations based on available memory
echo ""
echo "[Recommendations]"

if [ $FREE_INT -ge 2 ]; then
    cat << 'EOF'
✓ Plenty of memory - can run full suite with 2GB heap
  npm run test:memory:failsafe
EOF
elif [ $FREE_INT -ge 1 ]; then
    cat << 'EOF'
✓ Good memory - recommend 1GB heap
  npm run test:memory:failsafe -- --max-heap 1024
EOF
elif [ $FREE_INT -ge 0 ]; then
    cat << 'EOF'
⚠ Limited memory - use 512MB heap, test by category
  npm run test:memory:failsafe -- --category components --max-heap 512
  npm run test:memory:failsafe -- --category services --max-heap 512
EOF
else
    cat << 'EOF'
✗ Very low memory - close other apps or add RAM
  Current free: less than 512MB (minimum required)
EOF
fi

echo ""
echo "[Current Node Processes]"
if pgrep -l "node" > /dev/null 2>&1; then
    pgrep -l "node"
    echo ""
    echo "Kill with: pkill -f node"
else
    echo "(None running)"
fi

echo ""
echo "[Disk Space Check]"
df -h . | tail -1 | awk '{printf "Current directory: %s free\n", $4}'
if [ $? -ne 0 ]; then
    df -h . | tail -1
fi

echo ""
echo "[Next Steps]"
echo "1. Review recommendations above"
echo "2. Close unnecessary applications if needed"
echo "3. Run: npm run test:memory:failsafe [options]"
echo ""

# Show help if requested
if [ "$1" == "--help" ]; then
    cat << 'EOF'
[Available Options]
  --max-heap 1024         Set max heap to 1GB
  --max-heap 512          Set max heap to 512MB
  --category services     Run only services tests
  --category components   Run only components tests
  --category integration  Run only integration tests
  --category hooks        Run only hooks tests
  --category contexts     Run only contexts tests

[Example Commands]
  # Full suite with default heap
  npm run test:memory:failsafe

  # Full suite with 1GB heap
  npm run test:memory:failsafe -- --max-heap 1024

  # Single category
  npm run test:memory:failsafe -- --category components

  # Single category with custom heap
  npm run test:memory:failsafe -- --category components --max-heap 1024

  # Tight constraint testing (512MB)
  npm run test:memory:failsafe -- --max-heap 512

[Memory Leak Investigation]
  # 1. Start with fastest category
  npm run test:memory:failsafe -- --category services

  # 2. Progressively test larger categories
  npm run test:memory:failsafe -- --category hooks
  npm run test:memory:failsafe -- --category contexts
  npm run test:memory:failsafe -- --category components

  # 3. If one category fails, investigate those tests
  # Look for missing cleanup in afterEach() or useEffect() cleanup

[Monitoring Memory]
  # Watch memory in real-time while tests run
  watch -n 1 free -h

  # Or use top/htop for continuous monitoring
  top    # Press 'q' to quit
  htop   # Press 'q' to quit (if installed)

EOF
fi

echo "============================================================"
echo ""
