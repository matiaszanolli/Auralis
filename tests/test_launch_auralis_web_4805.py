"""
launch-auralis-web.py port threading and pnpm usage (issue #4805)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

start_backend() accepted a `port` argument but never used it -- the backend
always started on main.py's hardcoded 8765, so `--port 9000` silently
no-op'd. Separately, start_frontend_dev() shelled out to `npm install`/
`npm start` in a pnpm-only repo (package.json declares
"packageManager": "pnpm@10.20.0"; #4357).

Fix: the port is threaded through via AURALIS_PORT, the same environment-
variable mechanism AURALIS_DEV_MODE already used two lines below (sys.argv
doesn't propagate reliably through subprocess.Popen); main.py reads it via
core.env_config.get_int_env(), the same helper every other env-configurable
constant in the backend uses. start_frontend_dev() now calls `pnpm install`/
`pnpm run dev`.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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
        main_py = (REPO_ROOT / "auralis-web" / "backend" / "main.py").read_text()
        assert 'get_int_env("AURALIS_PORT", 8765)' in main_py


class TestFrontendUsesPnpmNotNpm:
    def test_missing_node_modules_triggers_pnpm_install(self, launch_module):
        def _exists(path_self):
            # frontend_dir itself must exist (else start_frontend_dev bails
            # early); only node_modules is "missing".
            return path_self.name != "node_modules"

        with (
            patch("subprocess.check_call") as mock_check_call,
            patch("subprocess.Popen") as mock_popen,
            patch.object(Path, "exists", _exists, autospec=False),
        ):
            mock_popen.return_value = MagicMock(pid=54321)
            launch_module.start_frontend_dev()

        mock_check_call.assert_called_once()
        args, kwargs = mock_check_call.call_args
        assert args[0] == ["pnpm", "install"]
        assert kwargs["cwd"] == Path(launch_module.__file__).parent / "auralis-web" / "frontend"

    def test_dev_server_started_with_pnpm_run_dev(self, launch_module):
        with (
            patch("subprocess.check_call"),
            patch("subprocess.Popen") as mock_popen,
            patch.object(Path, "exists", return_value=True),  # node_modules "present"
        ):
            mock_popen.return_value = MagicMock(pid=54321)
            launch_module.start_frontend_dev()

        args, _ = mock_popen.call_args
        assert args[0] == ["pnpm", "run", "dev"]

    def test_no_npm_anywhere_in_the_source(self):
        """Regression guard: `npm` must not reappear as a subprocess call."""
        source = LAUNCH_SCRIPT.read_text()
        assert '"npm"' not in source and "'npm'" not in source
