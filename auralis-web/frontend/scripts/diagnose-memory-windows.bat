@echo off
REM Memory Diagnostic Script for Windows
REM Checks system memory status before running memory tests
REM Usage: diagnose-memory-windows.bat

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo Windows Memory Diagnostic Tool
echo ============================================================
echo.

REM Get system info
echo [System Information]
for /f "tokens=2 delims==" %%A in ('wmic OS get TotalVisibleMemorySize /value') do set TOTAL_MEM=%%A
for /f "tokens=2 delims==" %%A in ('wmic OS get FreePhysicalMemory /value') do set FREE_MEM=%%A

REM Convert from KB to GB
set /a TOTAL_GB=TOTAL_MEM/1048576
set /a FREE_GB=FREE_MEM/1048576
set /a USED_GB=TOTAL_GB-FREE_GB

echo Total Memory: !TOTAL_GB!GB
echo Free Memory:  !FREE_GB!GB
echo Used Memory:  !USED_GB!GB
echo.

REM Check if we have enough RAM for tests
set /a MIN_FREE=512
if !FREE_GB! LSS !MIN_FREE! (
    echo [WARNING] Only !FREE_GB!GB free memory. Recommended: 1GB+
    echo Close unnecessary applications before running tests.
)

REM Recommendations based on available memory
echo.
echo [Recommendations]
if !FREE_GB! GEQ 2048 (
    echo ✓ Plenty of memory - can run full suite with 2GB heap
    echo   npm run test:memory:failsafe
) else if !FREE_GB! GEQ 1024 (
    echo ✓ Good memory - recommend 1GB heap
    echo   npm run test:memory:failsafe -- --max-heap 1024
) else if !FREE_GB! GEQ 512 (
    echo ⚠ Limited memory - use 512MB heap, test by category
    echo   npm run test:memory:failsafe -- --category components --max-heap 512
) else (
    echo ✗ Very low memory - close other apps or add RAM
    echo   Current free: !FREE_GB!GB (Need 512MB minimum)
)

echo.
echo [Current Node Processes]
tasklist /FI "IMAGENAME eq node.exe" 2>nul
if errorlevel 1 (
    echo (None running)
) else (
    echo Kill with: taskkill /IM node.exe /F
)

echo.
echo [Next Steps]
echo 1. Review recommendations above
echo 2. Close unnecessary applications
echo 3. Run: npm run test:memory:failsafe [options]
echo.

REM Open docs if requested
if "%1"=="--help" (
    echo [Available Options]
    echo   --max-heap 1024         Set max heap to 1GB
    echo   --category services     Run only services tests
    echo   --category components   Run only components tests
    echo.
    echo Example combinations:
    echo   npm run test:memory:failsafe
    echo   npm run test:memory:failsafe -- --max-heap 1024
    echo   npm run test:memory:failsafe -- --category components
    echo   npm run test:memory:failsafe -- --category integration --max-heap 1024
)

echo ============================================================
echo.
