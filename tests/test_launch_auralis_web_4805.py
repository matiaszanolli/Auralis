"""
launch-auralis-web.py port threading and pnpm usage (issue #4805)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The launcher sets AURALIS_PORT for both the backend and the Vite proxy. It
executes the installed tools directly to avoid package-manager side effects.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_SCRIPT = REPO_ROOT / "launch-auralis-web.py"


def _load_launch_module():
    """Load launch-auralis-web.py as a module.

    Its filename has a hyphen, so it can't be `import`ed normally --
    importlib.util.spec_from_file_location loads it directly from its path.
    """
    spec = importlib.util.spec_from_file_location("launch_auralis_web", LAUNCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launch_module():
    return _load_launch_module()


class TestPortIsThreadedThrough:
    def test_start_backend_passes_the_requested_port_via_env(self, launch_module):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            launch_module.start_backend(port=9000, dev_mode=False)

        assert mock_popen.called
        _, kwargs = mock_popen.call_args
        assert kwargs["env"]["AURALIS_PORT"] == "9000"

    def test_default_port_is_also_passed_via_env(self, launch_module):
        """Even the default must go through AURALIS_PORT -- main.py's own
        default (8765) matching today is coincidental, not load-bearing."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            launch_module.start_backend()

        _, kwargs = mock_popen.call_args
        assert kwargs["env"]["AURALIS_PORT"] == "8765"

    def test_main_py_reads_the_same_env_var_name(self):
        """CONSISTENCY: the launcher and main.py must agree on the variable
        name, or the port silently no-ops again."""
        # main.py binds config.origins.BACKEND_PORT (#5796), the one reader.
        origins_py = (REPO_ROOT / "auralis-web" / "backend" / "config" / "origins.py").read_text()
        assert 'get_int_env("AURALIS_PORT", 8765)' in origins_py


class TestDevModeIsClearedForNonDevLaunches:
    """AURALIS_DEV_MODE used to be only ever ADDED to the child env (#5432),
    so a value inherited from an earlier dev session silently kept dev-mode
    CORS/WS origin widening and /api/docs enabled on a launch the caller
    asked to be non-dev. AURALIS_PORT was always overwritten; dev mode now
    is too."""

    def test_inherited_dev_mode_is_cleared_when_dev_mode_is_false(self, launch_module, monkeypatch):
        monkeypatch.setenv("AURALIS_DEV_MODE", "1")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            launch_module.start_backend(port=8765, dev_mode=False)

        _, kwargs = mock_popen.call_args
        assert kwargs["env"]["AURALIS_DEV_MODE"] == "0"

    def test_inherited_value_is_overridden_when_dev_mode_is_true(self, launch_module, monkeypatch):
        monkeypatch.setenv("AURALIS_DEV_MODE", "0")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)
            launch_module.start_backend(port=8765, dev_mode=True)

        _, kwargs = mock_popen.call_args
        assert kwargs["env"]["AURALIS_DEV_MODE"] == "1"

    def test_matches_the_desktop_launcher_reference(self):
        """CONSISTENCY: desktop/backend-env.js::buildBackendEnv is the
        sanctioned reference implementation — it sets AURALIS_DEV_MODE='0'
        when not in development. Both launchers must keep agreeing."""
        desktop_js = (REPO_ROOT / "desktop" / "backend-env.js").read_text()
        assert "AURALIS_DEV_MODE" in desktop_js and "'0'" in desktop_js


class TestFrontendDevelopment:
    def test_dev_server_uses_installed_vite_and_the_requested_backend_port(self, launch_module):
        with patch("subprocess.Popen") as mock_popen:
            launch_module.start_frontend_dev(9000, 3100)

        args, kwargs = mock_popen.call_args
        assert args[0] == ["node", str(launch_module.VITE), "--host", "127.0.0.1", "--port", "3100", "--strictPort"]
        assert kwargs["env"]["AURALIS_PORT"] == "9000"
        assert kwargs["env"]["VITE_WS_URL"] == "ws://127.0.0.1:9000"

    def test_no_npm_anywhere_in_the_source(self):
        """Regression guard: `npm` must not reappear as a subprocess call."""
        source = LAUNCH_SCRIPT.read_text()
        assert '"npm"' not in source and "'npm'" not in source


class TestMissingDependenciesAreNotAutoInstalled:
    """#6173: check_dependencies() pip-installed fastapi and uvicorn[standard] unpinned, unhashed
    and unprompted into whichever interpreter ran the script."""

    def test_a_missing_backend_dependency_exits_with_instructions_and_installs_nothing(
        self, launch_module, capsys
    ):
        with patch.dict("sys.modules", {"fastapi": None}), patch.object(
            launch_module.subprocess, "check_call"
        ) as check_call, pytest.raises(SystemExit) as exit_info:
            launch_module.check_dependencies()

        assert exit_info.value.code == 1
        check_call.assert_not_called()
        assert "uv pip install -r requirements.txt" in capsys.readouterr().err

    def test_the_launcher_has_no_pip_install_left(self):
        assert '"pip", "install"' not in LAUNCH_SCRIPT.read_text()
