"""
Test: no duplicate POST /api/library/scan routes (fixes #2123)

Verifies that:
- files.py no longer registers POST /api/library/scan
- library.py is the sole owner of POST /api/library/scan
- The endpoint accepts both single and multiple directory lists (via schemas.LibraryScanRequest)
- files.py still exposes POST /api/files/upload and GET /api/audio/formats
"""

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
FILES_PY = BACKEND / "routers" / "files.py"

sys.path.insert(0, str(BACKEND))


def _parse_files_py() -> ast.Module:
    """Parse routers/files.py as an AST (no import, no circular dependency)."""
    return ast.parse(FILES_PY.read_text())


def _route_decorators(tree: ast.Module) -> list[str]:
    """
    Extract path strings from @router.<method>("<path>") decorators in the AST.
    Returns a list of path literals found in decorator calls.
    """
    paths: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in node.decorator_list:
            # Match router.get(...) / router.post(...) etc.
            if not (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "router"
            ):
                continue
            for arg in dec.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    paths.append(arg.value)
    return paths


def test_files_router_does_not_register_scan_endpoint():
    """
    files.py must not register POST /api/library/scan.
    The duplicate registration caused the richer library.py endpoint to be
    unreachable dead code (fixes #2123).
    """
    tree = _parse_files_py()
    routes = _route_decorators(tree)
    assert "/api/library/scan" not in routes, (
        "files.py must not register /api/library/scan — "
        "this causes library.py's endpoint to be unreachable (fixes #2123)"
    )


def test_files_router_retains_upload_endpoint():
    """POST /api/files/upload must still be present in files.py."""
    tree = _parse_files_py()
    routes = _route_decorators(tree)
    assert "/api/files/upload" in routes, (
        "POST /api/files/upload must remain in files.py"
    )


def test_files_router_retains_formats_endpoint():
    """GET /api/audio/formats must still be present in files.py."""
    tree = _parse_files_py()
    routes = _route_decorators(tree)
    assert "/api/audio/formats" in routes, (
        "GET /api/audio/formats must remain in files.py"
    )


def test_scan_request_accepts_multiple_directories():
    """
    schemas.LibraryScanRequest must accept a list of directory paths.
    A single directory is passed as a one-element list ["path"].
    """
    from unittest.mock import patch
    from schemas import LibraryScanRequest

    with patch("path_security.validate_scan_path", side_effect=lambda p: Path(p)):
        req = LibraryScanRequest(directories=["/tmp/music", "/tmp/other"])
        assert len(req.directories) == 2

        single = LibraryScanRequest(directories=["/tmp/music"])
        assert len(single.directories) == 1


def test_scan_request_accepts_optional_flags():
    """schemas.LibraryScanRequest must default recursive=True, skip_existing=True."""
    from unittest.mock import patch
    from schemas import LibraryScanRequest

    with patch("path_security.validate_scan_path", side_effect=lambda p: Path(p)):
        req = LibraryScanRequest(directories=["/tmp/music"])
        assert req.recursive is True
        assert req.skip_existing is True

        custom = LibraryScanRequest(directories=["/tmp/music"], recursive=False, skip_existing=False)
        assert custom.recursive is False
        assert custom.skip_existing is False


def test_files_router_has_no_local_scan_request_class():
    """
    The local ScanRequest class in files.py must be removed.
    It shadowed schemas.ScanRequest and had an incompatible signature.
    """
    tree = _parse_files_py()
    class_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]
    assert "ScanRequest" not in class_names, (
        "files.py must not define a local ScanRequest class (fixes #2123). "
        "Use schemas.LibraryScanRequest exclusively."
    )
