#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis Web Launcher
~~~~~~~~~~~~~~~~~~~

Convenient launcher for the new Auralis Web Interface.
Replaces the old Tkinter GUI with a modern web-based solution.

Usage:
    python launch-auralis-web.py [--port PORT] [--dev]

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import os
import subprocess
import argparse
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")

    # Check Python dependencies
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI and Uvicorn available")
    except ImportError:
        print("❌ FastAPI/Uvicorn not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])

    # Check if Node.js is available for development
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js available: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        print("⚠️  Node.js not found - development mode not available")
        return False

    return True

def start_backend(port=8000):
    """Start the FastAPI backend"""
    backend_dir = Path(__file__).parent / "auralis-web" / "backend"

    if not backend_dir.exists():
        print(f"❌ Backend directory not found: {backend_dir}")
        return None

    print(f"🚀 Starting Auralis Web Backend on port {port}...")

    # Change to backend directory and start
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)

    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir,
        env=env
    )

    return process

def start_frontend_dev():
    """Start the React development server"""
    frontend_dir = Path(__file__).parent / "auralis-web" / "frontend"

    if not frontend_dir.exists():
        print(f"❌ Frontend directory not found: {frontend_dir}")
        return None

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("📦 Installing frontend dependencies...")
        subprocess.check_call(["npm", "install"], cwd=frontend_dir)

    print("🎨 Starting React development server...")

    process = subprocess.Popen(
        ["npm", "start"],
        cwd=frontend_dir
    )

    return process

def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(description="Launch Auralis Web Interface")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--dev", action="store_true", help="Start in development mode with React dev server")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args()

    print("🎵 Auralis Web Interface Launcher")
    print("=" * 40)

    # Check dependencies
    has_node = check_dependencies()

    if args.dev and not has_node:
        print("❌ Development mode requires Node.js")
        sys.exit(1)

    processes = []

    try:
        # Start backend
        backend_process = start_backend(args.port)
        if backend_process:
            processes.append(backend_process)
            print(f"✅ Backend started (PID: {backend_process.pid})")
        else:
            print("❌ Failed to start backend")
            return

        # Wait for backend to start
        print("⏳ Waiting for backend to initialize...")
        time.sleep(3)

        # Start frontend if in dev mode
        if args.dev:
            frontend_process = start_frontend_dev()
            if frontend_process:
                processes.append(frontend_process)
                print(f"✅ Frontend dev server started (PID: {frontend_process.pid})")
                frontend_url = "http://localhost:3000"
            else:
                print("❌ Failed to start frontend")
                frontend_url = f"http://localhost:{args.port}"
        else:
            frontend_url = f"http://localhost:{args.port}"

        # Open browser
        if not args.no_browser:
            print(f"🌐 Opening browser: {frontend_url}")
            webbrowser.open(frontend_url)

        print("\n" + "=" * 40)
        print("🎉 Auralis Web Interface is running!")
        print(f"🌐 Frontend: {frontend_url}")
        print(f"📡 Backend:  http://localhost:{args.port}")
        print(f"📖 API Docs: http://localhost:{args.port}/api/docs")
        print("\nPress Ctrl+C to stop all servers")
        print("=" * 40)

        # Wait for processes
        try:
            for process in processes:
                process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

    finally:
        # Clean up processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        print("✅ All servers stopped")

if __name__ == "__main__":
    main()