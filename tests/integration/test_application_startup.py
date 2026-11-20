"""Exercise the real launcher, backend, and Vite with an isolated profile."""

import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
VITE = ROOT / "auralis-web/frontend/node_modules/vite/bin/vite.js"
pytestmark = pytest.mark.skipif(
    os.name == "nt" or not VITE.is_file() or shutil.which("node") is None,
    reason="startup smoke uses POSIX process groups and requires installed frontend dependencies",
)


@pytest.fixture
def launch(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "launcher.log"
    with socket.socket() as backend, socket.socket() as frontend:
        backend.bind(("127.0.0.1", 0))
        frontend.bind(("127.0.0.1", 0))
        backend_port = backend.getsockname()[1]
        frontend_port = frontend.getsockname()[1]

    launcher = None

    def output():
        return log.read_text(errors="replace")

    def start(*, port=backend_port):
        nonlocal launcher
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / "cache"),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_DATA_HOME": str(home / "data"),
            "MPLCONFIGDIR": str(home / "matplotlib"),
        }
        with log.open("w") as stream:
            launcher = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "launch-auralis-web.py"),
                    "--dev",
                    "--no-browser",
                    "--port",
                    str(port),
                    "--frontend-port",
                    str(frontend_port),
                ],
                cwd=tmp_path,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return launcher

    yield home, backend_port, frontend_port, start, output
    if launcher is not None and launcher.poll() is None:
        launcher.terminate()
        try:
            launcher.wait(timeout=50)
        except subprocess.TimeoutExpired:
            for pid in re.findall(r"started \(PID (\d+)\)", output()):
                try:
                    os.killpg(int(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            launcher.kill()
            launcher.wait(timeout=5)


def wait_for_ready(process, output):
    deadline = time.monotonic() + 30
    while "Auralis is ready at" not in output():
        assert process.poll() is None and time.monotonic() < deadline, output()
        time.sleep(0.1)


def assert_reaped(output):
    pids = re.findall(r"(?:Backend|Vite) started \(PID (\d+)\)", output())
    assert pids
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.killpg(int(pid), 0)


@pytest.mark.parametrize("stop", ["launcher", "backend"])
def test_source_launch_uses_one_backend_and_reaps_children(launch, stop):
    home, backend_port, frontend_port, start, output = launch
    process = start()
    wait_for_ready(process, output)

    assert (home / ".auralis" / "library.db").is_file()
    assert len(re.findall(r"^Backend started \(PID", output(), re.M)) == 1
    with (
        urlopen(f"http://127.0.0.1:{backend_port}/api/ready", timeout=2) as backend,
        urlopen(f"http://127.0.0.1:{frontend_port}/api/ready", timeout=2) as proxy,
        urlopen(f"http://127.0.0.1:{frontend_port}/", timeout=2) as page,
    ):
        assert backend.headers["X-Auralis-Launch-Id"]
        assert (
            proxy.headers["X-Auralis-Launch-Id"]
            == backend.headers["X-Auralis-Launch-Id"]
        )
        assert page.headers.get_content_type() == "text/html"
        assert b"/@vite/client" in page.read()

    if stop == "backend":
        backend_pid = int(re.search(r"Backend started \(PID (\d+)\)", output())[1])
        os.kill(backend_pid, signal.SIGTERM)
        assert process.wait(timeout=50) == 1, output()
    else:
        process.terminate()
        assert process.wait(timeout=50) == 0, output()

    assert_reaped(output)


def test_backend_initialization_failure_cannot_report_ready(launch):
    home, _, _, start, output = launch
    (home / ".auralis").write_text("blocks the database directory")
    assert start().wait(timeout=30) == 1, output()

    assert "Auralis launch failed:" in output()
    assert "Auralis is ready at" not in output()
    assert "Vite started" not in output()
    assert_reaped(output)


def test_port_collision_leaves_unrelated_listener_running(launch):
    _, _, _, start, output = launch
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert start(port=port).wait(timeout=10) == 1, output()
        assert f"Cannot use port {port}:" in output()
        assert "Backend started" not in output()
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            conn, _ = listener.accept()
            conn.close()
