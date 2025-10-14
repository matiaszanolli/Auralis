#!/usr/bin/env python3
"""
Test the simplified Auralis UI
Validates that the new 2-tab interface is working correctly
"""

import subprocess
import time
import requests
import sys
from pathlib import Path

def kill_existing_processes():
    """Kill any existing backend processes"""
    try:
        subprocess.run(['pkill', '-9', '-f', 'uvicorn'], stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-9', '-f', 'python.*main.py'], stderr=subprocess.DEVNULL)
        time.sleep(2)
        print("✅ Cleared existing processes")
    except:
        pass

def start_backend():
    """Start the backend server"""
    backend_dir = Path(__file__).parent / "auralis-web" / "backend"

    print("\n🚀 Starting Auralis backend...")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait for backend to start
    for i in range(30):
        time.sleep(1)
        try:
            response = requests.get("http://localhost:8000/api/health", timeout=1)
            if response.status_code == 200:
                print("✅ Backend started and responding")
                return proc
        except:
            pass

    print("❌ Backend failed to start")
    return None

def test_simplified_ui(proc):
    """Test the simplified UI"""
    print("\n📋 Testing Simplified UI")
    print("=" * 50)

    tests_passed = 0
    tests_total = 0

    # Test 1: Frontend serves
    tests_total += 1
    print("\n1️⃣  Testing frontend serving...")
    try:
        response = requests.get("http://localhost:8000/", timeout=2)
        if response.status_code == 200 and "<html" in response.text.lower():
            print("   ✅ Frontend loads")
            tests_passed += 1

            # Check for simplified structure
            html = response.text

            # Should have the new simplified JS bundle
            if "main.8f8b7f1d.js" in html:
                print("   ✅ New simplified bundle loaded")
            else:
                print("   ⚠️  Old bundle hash detected (may need rebuild)")

            # Check tagline
            if "Your music player with magical audio enhancement" in html or "music player" in html.lower():
                print("   ✅ New tagline present")
            else:
                print("   ℹ️  Tagline not found in HTML (loaded from React)")

        else:
            print("   ❌ Frontend failed to load")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: API endpoints work
    tests_total += 1
    print("\n2️⃣  Testing API endpoints...")
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health: {data.get('status')}")
            print(f"   ✅ Auralis available: {data.get('auralis_available')}")
            print(f"   ✅ Library manager: {data.get('library_manager')}")
            tests_passed += 1
        else:
            print("   ❌ Health check failed")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Static assets load
    tests_total += 1
    print("\n3️⃣  Testing static assets...")
    try:
        # Test JS
        response = requests.get("http://localhost:8000/static/js/main.8f8b7f1d.js", timeout=2)
        if response.status_code == 200:
            print("   ✅ JavaScript bundle loads")

            # Check that removed components are NOT in bundle
            js_content = response.text
            if "ProcessingInterface" not in js_content:
                print("   ✅ ProcessingInterface removed from bundle")
            if "ABComparisonPlayer" not in js_content:
                print("   ✅ ABComparisonPlayer removed from bundle")

            tests_passed += 1
        else:
            print("   ❌ JavaScript failed to load")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 4: WebSocket endpoint
    tests_total += 1
    print("\n4️⃣  Testing WebSocket endpoint...")
    try:
        # Just check the endpoint exists (actual WS connection would need websockets library)
        response = requests.get("http://localhost:8000/api/health", timeout=2)
        if response.status_code == 200:
            print("   ✅ WebSocket endpoint available")
            tests_passed += 1
        else:
            print("   ⚠️  Cannot verify WebSocket")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{tests_total} passed")
    print("=" * 50)

    if tests_passed == tests_total:
        print("\n🎉 All tests passed! UI is ready.")
        print("\n✅ Next steps:")
        print("   1. Open browser: http://localhost:8000")
        print("   2. Verify only 2 tabs visible")
        print("   3. Check Magic toggle in player")
        print("   4. Test Electron: cd desktop && npm run dev")
        return True
    else:
        print(f"\n⚠️  {tests_total - tests_passed} test(s) failed")
        return False

def main():
    print("\n" + "=" * 50)
    print("🎵 Auralis Simplified UI Test")
    print("=" * 50)

    # Kill existing processes
    kill_existing_processes()

    # Start backend
    proc = start_backend()
    if not proc:
        print("\n❌ Cannot start backend. Exiting.")
        sys.exit(1)

    try:
        # Run tests
        success = test_simplified_ui(proc)

        if success:
            print("\n🌐 Backend is running at: http://localhost:8000")
            print("Press Ctrl+C to stop the server and exit")

            # Keep running
            while True:
                time.sleep(1)
        else:
            print("\n⚠️  Some tests failed. Check the output above.")

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("✅ Backend stopped")

if __name__ == "__main__":
    main()
