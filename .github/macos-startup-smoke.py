"""Verify the installed app from the Apple Silicon release disk image."""
import ctypes
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

PORT = 8765
BACKEND = "/Contents/Resources/backend/auralis-backend"


def app_processes(bundle):
    output = subprocess.check_output(
        ["/bin/ps", "-axww", "-o", "pid=,ppid=,state=,command="], text=True
    )
    matches = {}
    for line in output.splitlines():
        fields = line.split(None, 3)
        if len(fields) == 4:
            pid, ppid, state, command = fields
            if not state.startswith("Z") and command.startswith(f"{bundle}/Contents/"):
                matches[int(pid)] = (int(ppid), command)
    return matches


def listener_pids():
    command = ["/usr/sbin/lsof", "-nP", "-t", f"-iTCP:{PORT}", "-sTCP:LISTEN"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=10)
    assert result.returncode in (0, 1) and not result.stderr, result
    return set(map(int, result.stdout.split()))


def request(path):
    connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.getheader("X-Auralis-Launch-Id"), response.read()
    finally:
        connection.close()


def sandbox_check(pid):
    sandbox = ctypes.CDLL("/usr/lib/system/libsystem_sandbox.dylib").sandbox_check
    sandbox.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
    sandbox.restype = ctypes.c_int
    return sandbox(pid, None, 0)


def run_smoke(bundle, helper, run_dir, expected_version, mode):
    run_dir.mkdir()
    home = run_dir / "home"
    home.mkdir()
    stdout, stderr = (run_dir / name for name in ("stdout.log", "stderr.log"))
    stdout.touch()
    stderr.touch()

    def logs():
        return "\n".join(path.read_text(errors="replace") for path in (stdout, stderr))

    assert not app_processes(bundle), "An Auralis bundle process is already running"
    assert not listener_pids(), f"Port {PORT} is occupied before launch"
    browser_path = str(bundle / "Contents/MacOS/Auralis")
    command = [
        "/usr/bin/open", "-n", "-W",
        "--stdout", str(stdout), "--stderr", str(stderr),
        "--env", f"HOME={home}",
        str(bundle), "--args", f"--user-data-dir={run_dir / 'electron'}",
    ]
    start = time.monotonic()
    opener = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while time.monotonic() - start < 75 and opener.poll() is None:
            table = app_processes(bundle)
            browsers = [
                pid for pid, (_, cmd) in table.items()
                if cmd == browser_path or cmd.startswith(browser_path + " ")
            ]
            output = logs()
            if "Auralis startup failed" in output:
                raise AssertionError("Electron reported a startup failure")
            if len(browsers) == 1 and "Auralis is ready" in output:
                browser_pid = browsers[0]
                visible = subprocess.run([helper, "visible", str(browser_pid)], timeout=10)
                if visible.returncode == 0:
                    break
            time.sleep(0.25)
        else:
            raise AssertionError(f"Auralis did not open a ready window. Launch Services: {opener.poll()}")

        status, launch_id, body = request("/api/ready")
        assert status == 200 and launch_id and json.loads(body)["ready"] is True
        version_status, _, version = request("/api/version")
        assert version_status == 200 and json.loads(version)["version"] == expected_version
        assert (home / ".auralis/library.db").is_file(), "Fresh profile has no library database"

        table = app_processes(bundle)
        backends = {pid: ppid for pid, (ppid, cmd) in table.items() if cmd.endswith(BACKEND)}
        owners = [pid for pid, ppid in backends.items() if ppid == browser_pid]
        assert len(owners) == 1, f"Expected one backend child of Electron, got {backends}"
        backend_tree = {owners[0]}
        while True:
            branches = {pid for pid, ppid in backends.items() if ppid in backend_tree}
            if branches <= backend_tree:
                break
            backend_tree.update(branches)
        listeners = listener_pids()
        assert set(backends) == backend_tree and listeners and listeners <= backend_tree, (backends, listeners)

        renderers = [pid for pid, (_, cmd) in table.items() if "--type=renderer" in cmd.split()]
        assert renderers, "No Chromium renderer was running"
        assert "--no-sandbox" not in table[browser_pid][1].split()
        renderer_sandboxes = {pid: sandbox_check(pid) for pid in renderers}
        assert all(status == 1 for status in renderer_sandboxes.values()), renderer_sandboxes
        print(
            f"STARTUP_OK mode={mode} version={expected_version} browser={browser_pid} "
            f"backend_owner={owners[0]} listeners={sorted(listeners)} "
            f"launch_id={launch_id} seatbelt={renderer_sandboxes} elapsed={time.monotonic()-start:.2f}s",
            flush=True,
        )

        if mode == "quit":
            subprocess.run([helper, "quit", str(browser_pid)], check=True, timeout=10)
        else:
            os.kill(browser_pid, signal.SIGKILL)
        stopping = time.monotonic()
        while time.monotonic() - stopping < 50:
            if not app_processes(bundle) and not listener_pids():
                break
            time.sleep(0.25)
        else:
            raise AssertionError(f"Shutdown left processes {app_processes(bundle)} or listeners {listener_pids()}")
        opener.wait(timeout=10)
        if mode == "quit":
            assert opener.returncode == 0, opener.returncode
            assert "Application shutdown complete" in logs(), "Backend did not log a completed shutdown"
        print(f"SHUTDOWN_OK mode={mode} no_app_processes=true no_listener=true", flush=True)
    except Exception:
        print(logs()[-16000:], file=sys.stderr, flush=True)
        if opener.poll() is not None:
            launch_stdout, launch_stderr = opener.communicate()
            print(launch_stdout, launch_stderr, file=sys.stderr, flush=True)
        raise
    finally:
        for pid in app_processes(bundle):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if opener.poll() is None:
            opener.terminate()
            opener.wait(timeout=10)


def main():
    dmg = Path(sys.argv[1]).resolve()
    expected_version = sys.argv[2]
    with tempfile.TemporaryDirectory(prefix="auralis-dmg-") as directory:
        scratch = Path(directory).resolve()
        mount = scratch / "mount"
        bundle = scratch / "Applications" / "Auralis.app"
        helper = scratch / "gui-probe"
        subprocess.run(
            ["xcrun", "swiftc", str(Path(__file__).with_suffix(".swift")), "-o", helper],
            check=True, timeout=60,
        )
        subprocess.run(
            ["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, dmg],
            check=True, timeout=60,
        )
        try:
            bundle.parent.mkdir()
            subprocess.run(["ditto", mount / "Auralis.app", bundle], check=True, timeout=60)
        finally:
            subprocess.run(["hdiutil", "detach", mount], check=True, timeout=60)

        for path in (bundle / "Contents/MacOS/Auralis", bundle / BACKEND.lstrip("/")):
            architectures = subprocess.check_output(["lipo", "-archs", path], text=True).split()
            assert "arm64" in architectures, (path, architectures)
            print(f"ARM64_OK {path.name}: {architectures}", flush=True)
        subprocess.run(["codesign", "--display", "--verbose=2", bundle], timeout=15)
        assessment = subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose", bundle], timeout=45)
        print(f"GATEKEEPER_ASSESSMENT status={assessment.returncode}", flush=True)
        for mode in ("quit", "kill"):
            run_smoke(bundle, helper, scratch / mode, expected_version, mode)
        print("AURALIS_MACOS_RESULT=0", flush=True)


if __name__ == "__main__":
    main()
