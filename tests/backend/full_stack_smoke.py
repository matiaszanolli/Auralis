#!/usr/bin/env python3
"""
Comprehensive test for Auralis full stack
Tests backend, frontend serving, and all components
"""

import subprocess
import sys
import time
from pathlib import Path

import requests


def check_backend_startup():
    """Test that backend starts successfully"""
    print("\n1️⃣  Testing Backend Startup...")
    print("=" * 50)

    # Start backend (path from test file to project root)
    project_root = Path(__file__).parent.parent.parent
    backend_dir = project_root / "auralis-web" / "backend"

    if not backend_dir.exists():
        print(f"❌ Backend directory not found: {backend_dir}")
        return False, None

    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait for startup
    print("⏳ Waiting for backend to start...")
    startup_output = []
    backend_ready = False

    for i in range(30):
        time.sleep(1)

        # Check if backend is responding
        try:
            response = requests.get("http://localhost:8000/api/health", timeout=1)
            if response.status_code == 200:
                backend_ready = True
                print("✅ Backend is responding!")
                break
        except:
            pass

        # Collect output
        try:
            line = proc.stdout.readline()
            if line:
                startup_output.append(line.strip())
                print(f"   {line.strip()}")
        except:
            pass

    if not backend_ready:
        print("❌ Backend failed to start!")
        print("\n--- Startup Output ---")
        for line in startup_output:
            print(line)
        proc.terminate()
        return False, None

    return True, proc

def check_api_endpoints(proc):
    """Test key API endpoints"""
    print("\n2️⃣  Testing API Endpoints...")
    print("=" * 50)

    endpoints = [
        ("/api/health", "Health Check"),
        ("/api/version", "Version Info"),
        ("/api/library/stats", "Library Stats"),
    ]

    all_passed = True
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", timeout=2)
            if response.status_code == 200:
                print(f"✅ {name}: {endpoint}")
                if endpoint == "/api/health":
                    data = response.json()
                    print(f"   Status: {data.get('status')}")
                    print(f"   Auralis Available: {data.get('auralis_available')}")
            else:
                print(f"❌ {name}: {endpoint} - Status {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ {name}: {endpoint} - {str(e)}")
            all_passed = False

    return all_passed

def check_frontend_serving(proc):
    """Test that frontend is being served"""
    print("\n3️⃣  Testing Frontend Serving...")
    print("=" * 50)

    try:
        # Test root page
        response = requests.get("http://localhost:8000/", timeout=2)
        if response.status_code == 200:
            print("✅ Root page loads (/)")

            # Check if it's HTML
            if "<html" in response.text.lower():
                print("✅ Serves HTML content")
            else:
                print("❌ Not serving HTML!")
                return False

            # Check if it references React
            if "react" in response.text.lower() or "root" in response.text.lower():
                print("✅ Looks like React app")

            # Check for static assets
            if "/static/" in response.text:
                print("✅ References static assets")

            return True
        else:
            print(f"❌ Root page failed: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend serving failed: {e}")
        return False

def check_static_assets(proc):
    """Test that static assets are accessible"""
    print("\n4️⃣  Testing Static Assets...")
    print("=" * 50)

    # Get the asset filenames from build
    build_dir = Path(__file__).parent / "auralis-web" / "frontend" / "build" / "static"

    if not build_dir.exists():
        print("❌ Build directory not found!")
        return False

    # Test CSS
    css_files = list((build_dir / "css").glob("*.css"))
    if css_files:
        css_file = css_files[0].name
        try:
            response = requests.get(f"http://localhost:8000/static/css/{css_file}", timeout=2)
            if response.status_code == 200:
                print(f"✅ CSS loads: /static/css/{css_file}")
            else:
                print(f"❌ CSS failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ CSS request failed: {e}")
            return False

    # Test JS
    js_files = list((build_dir / "js").glob("main.*.js"))
    if js_files:
        js_file = js_files[0].name
        try:
            response = requests.get(f"http://localhost:8000/static/js/{js_file}", timeout=2)
            if response.status_code == 200:
                print(f"✅ JavaScript loads: /static/js/{js_file}")
            else:
                print(f"❌ JavaScript failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ JavaScript request failed: {e}")
            return False

    return True

def main():
    """Run full stack tests"""
    print("\n" + "=" * 50)
    print("🧪 Auralis Full Stack Test Suite")
    print("=" * 50)

    # Test backend startup
    success, proc = check_backend_startup()
    if not success:
        print("\n❌ Backend startup failed. Cannot continue tests.")
        sys.exit(1)

    try:
        # Test API endpoints
        api_ok = check_api_endpoints(proc)

        # Test frontend serving
        frontend_ok = check_frontend_serving(proc)

        # Test static assets
        assets_ok = check_static_assets(proc)

        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        print(f"Backend Startup:   {'✅ PASS' if success else '❌ FAIL'}")
        print(f"API Endpoints:     {'✅ PASS' if api_ok else '❌ FAIL'}")
        print(f"Frontend Serving:  {'✅ PASS' if frontend_ok else '❌ FAIL'}")
        print(f"Static Assets:     {'✅ PASS' if assets_ok else '❌ FAIL'}")

        all_passed = success and api_ok and frontend_ok and assets_ok

        if all_passed:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✅ The backend is ready to serve the application.")
            print("✅ You can now run: python launch-auralis-web.py")
            print("✅ Or test Electron: cd desktop && npm run dev")
        else:
            print("\n⚠️  Some tests failed. See details above.")

        return all_passed

    finally:
        print("\n🧹 Cleaning up...")
        proc.terminate()
        proc.wait(timeout=5)
        print("✅ Backend stopped")

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
