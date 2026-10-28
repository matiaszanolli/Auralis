"""uvicorn's own log records go through the sanitizing root handler (#6184).

uvicorn.run() applies LOGGING_CONFIG after install_log_sanitizer(), adding
``uvicorn`` / ``uvicorn.access`` handlers with stock formatters and
propagate=False, so an unhandled exception logged by "Exception in ASGI
application" carried a raw multi-line traceback (log forging) in addition to the
sanitized copy. main.py passes ``log_config=None`` so those loggers propagate.
"""

import ast
import io
import logging
from pathlib import Path

import uvicorn.config

from auralis.utils.logging import SanitizingFormatter

MAIN = Path(__file__).resolve().parents[2] / "auralis-web" / "backend" / "main.py"


def test_main_runs_uvicorn_without_its_own_log_config():
    run_calls = [
        node for node in ast.walk(ast.parse(MAIN.read_text()))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run" and getattr(node.func.value, "id", "") == "uvicorn"
    ]
    assert len(run_calls) == 1
    log_config = {kw.arg: kw.value for kw in run_calls[0].keywords}["log_config"]
    assert isinstance(log_config, ast.Constant) and log_config.value is None


def test_uvicorn_error_records_reach_the_sanitizing_root_handler():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SanitizingFormatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    saved = {
        name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
    }
    try:
        uvicorn.config.Config(app=lambda *a: None, log_config=None, log_level="info").configure_logging()
        try:
            raise ValueError("bad\n2026-01-01 ERROR FORGED LINE")
        except ValueError:
            logging.getLogger("uvicorn.error").exception("Exception in ASGI application")
    finally:
        root.removeHandler(handler)
        for name, (handlers, propagate) in saved.items():
            logging.getLogger(name).handlers[:] = handlers
            logging.getLogger(name).propagate = propagate

    out = stream.getvalue()
    assert "Exception in ASGI application" in out
    assert not any(line.startswith("2026-01-01") for line in out.splitlines())
    assert "bad\\x0a2026-01-01 ERROR FORGED LINE" in out
