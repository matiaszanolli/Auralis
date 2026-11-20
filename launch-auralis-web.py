#!/usr/bin/env python3
"""Supervise the Auralis web and Electron development entry points."""

from __future__ import annotations

import argparse
import http.client
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
from pathlib import Path
from types import FrameType

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "auralis-web" / "backend"
FRONTEND = ROOT / "auralis-web" / "frontend"
DESKTOP = ROOT / "desktop"
VITE = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
ELECTRON = DESKTOP / "node_modules" / "electron" / "cli.js"
FRONTEND_PORT = 3000
STARTUP_TIMEOUT = 45
SHUTDOWN_TIMEOUT = 40


def check_dependencies() -> bool:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "FastAPI and Uvicorn are missing. Activate the project environment "
            "and run: uv pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    return shutil.which("node") is not None


def spawn(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    if sys.platform == "win32":
        return subprocess.Popen(
            command, cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def start_backend(
    port: int = 8765,
    dev_mode: bool = False,
    launch_id: str | None = None,
    frontend_port: int = FRONTEND_PORT,
) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "AURALIS_PORT": str(port),
        "AURALIS_DEV_MODE": "1" if dev_mode else "0",
        "AURALIS_FRONTEND_PORT": str(frontend_port),
        "ELECTRON_MODE": "0",
        "PYTHONUNBUFFERED": "1",
    }
    if launch_id is not None:
        env["AURALIS_LAUNCH_ID"] = launch_id
    return spawn([sys.executable, "main.py"], BACKEND, env)


def start_frontend_dev(port: int, frontend_port: int) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "AURALIS_PORT": str(port),
        "VITE_API_URL": "",
        "VITE_WS_URL": f"ws://127.0.0.1:{port}",
    }
    return spawn(
        [
            "node",
            str(VITE),
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
            "--strictPort",
        ],
        FRONTEND,
        env,
    )


def start_electron(port: int, launch_id: str) -> subprocess.Popen[bytes]:
    env = {**os.environ, "AURALIS_PORT": str(port), "AURALIS_LAUNCH_ID": launch_id}
    return spawn(["node", str(ELECTRON), "."], DESKTOP, env)


def require_free_port(port: int) -> None:
    with socket.socket() as listener:
        if sys.platform == "win32":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"Cannot use port {port}: {error.strerror}") from error


def check_children(
    children: dict[str, subprocess.Popen[bytes]], *, allow_electron_close: bool = False
) -> bool:
    for name, child in children.items():
        code = child.poll()
        if code is None:
            continue
        if allow_electron_close and name == "Electron" and code == 0:
            return False
        raise RuntimeError(f"{name} exited with status {code}")
    return True


def probe_ready(port: int, launch_id: str) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", "/api/ready")
        response = connection.getresponse()
        if response.getheader("X-Auralis-Launch-Id") == launch_id:
            if response.status == 503:
                raise RuntimeError("Backend initialization failed; see backend logs")
            return response.status == 200
    except OSError, http.client.HTTPException:
        pass
    finally:
        connection.close()
    return False


def wait_ready(
    children: dict[str, subprocess.Popen[bytes]], port: int, launch_id: str, label: str
) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        check_children(children)
        if probe_ready(port, launch_id):
            check_children(children)
            return
        time.sleep(0.1)
    raise RuntimeError(f"{label} did not become ready on port {port}")


def signal_group(child: subprocess.Popen[bytes], signum: signal.Signals) -> None:
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass


def stop_child(child: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        if child.poll() is None:
            # Windows has no killpg. Terminate the owned process tree while its
            # root PID still identifies it, then reap the spawned process.
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            child.wait(timeout=10)
        return

    signal_group(child, signal.SIGTERM)
    try:
        child.wait(timeout=SHUTDOWN_TIMEOUT)
    finally:
        # Helpers can outlive their leader even after a graceful leader exit.
        signal_group(child, signal.SIGKILL)
        child.wait(timeout=5)


def interrupt(_signum: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def run(args: argparse.Namespace) -> None:
    development = args.dev or args.electron
    if not development and not (FRONTEND / "dist" / "index.html").is_file():
        raise RuntimeError(
            "Built frontend missing. Run pnpm --dir auralis-web/frontend run build "
            "or use --dev."
        )
    if development:
        if not check_dependencies() or not VITE.is_file():
            raise RuntimeError(
                "Install Node.js and run pnpm --dir auralis-web/frontend install first"
            )
        if args.electron and not ELECTRON.is_file():
            raise RuntimeError("Run pnpm --dir desktop install first")
        if args.port == args.frontend_port:
            raise RuntimeError("Backend and frontend must use different ports")
        require_free_port(args.frontend_port)
    else:
        check_dependencies()
    require_free_port(args.port)

    children: dict[str, subprocess.Popen[bytes]] = {}
    launch_id = uuid.uuid4().hex
    try:
        children["Backend"] = start_backend(
            args.port, development, launch_id, args.frontend_port
        )
        print(f"Backend started (PID {children['Backend'].pid})", flush=True)
        wait_ready(children, args.port, launch_id, "Backend")
        url = f"http://127.0.0.1:{args.port}"
        if development:
            children["Vite"] = start_frontend_dev(args.port, args.frontend_port)
            print(f"Vite started (PID {children['Vite'].pid})", flush=True)
            wait_ready(children, args.frontend_port, launch_id, "Vite")
            url = f"http://127.0.0.1:{args.frontend_port}"
        if args.electron:
            children["Electron"] = start_electron(args.port, launch_id)
            print(f"Electron started (PID {children['Electron'].pid})", flush=True)
        else:
            print(f"Auralis is ready at {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
        while check_children(children, allow_electron_close=True):
            time.sleep(0.2)
    finally:
        # Let cleanup finish if the terminal sends another interrupt.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        cleanup_failed = False
        for name, child in reversed(children.items()):
            try:
                stop_child(child)
            except (OSError, subprocess.TimeoutExpired) as error:
                print(f"Failed to stop {name}: {error}", file=sys.stderr)
                cleanup_failed = True
        if cleanup_failed:
            raise RuntimeError("One or more child processes did not stop")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Auralis")
    parser.add_argument(
        "--port", type=int, default=8765, help="Backend port (default: 8765)"
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=FRONTEND_PORT,
        help="Vite port in web development mode",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Serve the frontend with Vite"
    )
    parser.add_argument(
        "--electron", action="store_true", help="Open the Electron development app"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 1 <= args.frontend_port <= 65535:
        parser.error("--frontend-port must be between 1 and 65535")
    if args.electron and args.frontend_port != FRONTEND_PORT:
        parser.error(f"Electron development requires Vite port {FRONTEND_PORT}")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        run(args)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Auralis launch failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
