"""uvicorn must not trust X-Forwarded-For (#6168).

Every peer is a loopback peer, and uvicorn's default `forwarded_allow_ips` is 127.0.0.1, so with
proxy_headers on, any local process could rewrite `scope["client"]` with an X-Forwarded-For header.
That value feeds the rate-limit buckets, the WebSocket per-IP bucket and the empty-Origin loopback
checks. There is no reverse proxy in this architecture, so main.py turns the middleware off.
"""

import ast
from pathlib import Path

import uvicorn
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

MAIN = Path(__file__).resolve().parents[2] / "auralis-web" / "backend" / "main.py"


async def _app(scope, receive, send):  # pragma: no cover - never served
    pass


def _run_keywords() -> dict[str, ast.expr]:
    calls = [
        node for node in ast.walk(ast.parse(MAIN.read_text()))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run" and getattr(node.func.value, "id", "") == "uvicorn"
    ]
    assert len(calls) == 1
    return {kw.arg: kw.value for kw in calls[0].keywords}


def test_main_runs_uvicorn_with_proxy_headers_off():
    proxy_headers = _run_keywords()["proxy_headers"]

    assert isinstance(proxy_headers, ast.Constant) and proxy_headers.value is False


def test_proxy_headers_off_leaves_the_app_unwrapped_and_default_wraps_it():
    wrapped = uvicorn.Config(_app, log_config=None)
    wrapped.load()
    plain = uvicorn.Config(_app, proxy_headers=False, log_config=None)
    plain.load()

    assert isinstance(wrapped.loaded_app, ProxyHeadersMiddleware)
    assert not isinstance(plain.loaded_app, ProxyHeadersMiddleware)
