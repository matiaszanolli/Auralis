"""
conftest hook hygiene (issue #4529)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`tests/conftest.py` defined `pytest_configure` and `pytest_collection_modifyitems`
TWICE each. Python binds the last definition, so the earlier copies never ran —
silently. A maintainer editing the dead copy would have seen no effect at all.

That left `pytest_ignore_collect` as the only live hook of the three, and it
used the legacy `(path, config)` / `py.path.local` signature that pytest 9.1
removed — pinning the whole suite below 9.1. It was guarding 8 benchmark files
that had themselves been deleted in 29650ea0.

These tests are static (AST over the conftest sources); they need no fixtures
and cannot be defeated by import order.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent
CONFTESTS = sorted(TESTS_ROOT.rglob("conftest.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _top_level_hook_names(path: Path) -> list[str]:
    return [
        node.name
        for node in _tree(path).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("pytest_")
    ]


def test_conftests_exist():
    """Guard the guard: a bad glob would make every test below vacuous."""
    assert CONFTESTS, "no conftest.py found under tests/"
    assert TESTS_ROOT / "conftest.py" in CONFTESTS


@pytest.mark.parametrize("path", CONFTESTS, ids=lambda p: str(p.relative_to(TESTS_ROOT)))
def test_no_duplicate_pytest_hooks(path: Path):
    """Each pytest_* hook may be defined at most once per conftest module."""
    names = _top_level_hook_names(path)
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    assert not duplicates, (
        f"{path.relative_to(TESTS_ROOT)} defines {duplicates} more than once; "
        "Python binds the last definition and the earlier ones silently never run"
    )


@pytest.mark.parametrize("path", CONFTESTS, ids=lambda p: str(p.relative_to(TESTS_ROOT)))
def test_no_legacy_py_path_api(path: Path):
    """No `py.path.local` attribute access — removed in pytest 9.1.

    `path.basename` and `item.fspath` are the two the suite used. The modern
    equivalents are `collection_path.name` and `item.path`.
    """
    offenders = [
        f"line {node.lineno}: .{node.attr}"
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Attribute) and node.attr in {"fspath", "basename"}
    ]
    assert not offenders, (
        f"{path.relative_to(TESTS_ROOT)} uses the removed py.path API: {offenders}"
    )


@pytest.mark.parametrize("path", CONFTESTS, ids=lambda p: str(p.relative_to(TESTS_ROOT)))
def test_ignore_collect_uses_modern_signature(path: Path):
    """If `pytest_ignore_collect` comes back, it must take `collection_path`."""
    for node in _tree(path).body:
        if isinstance(node, ast.FunctionDef) and node.name == "pytest_ignore_collect":
            params = [a.arg for a in node.args.args]
            assert "path" not in params, (
                f"{path.relative_to(TESTS_ROOT)}: pytest_ignore_collect uses the "
                "legacy `path` parameter removed in pytest 9.1 — use `collection_path`"
            )
            assert "collection_path" in params


def test_skip_benchmark_list_is_gone():
    """The skip list named 8 files that no longer exist (29650ea0).

    If it is ever reintroduced, every filename in it must resolve to a real
    file — a list of ghosts is indistinguishable from a working one.
    """
    root_conftest = TESTS_ROOT / "conftest.py"
    tree = _tree(root_conftest)

    listed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "_SKIP_BENCHMARK_TESTS" in targets:
                listed = {
                    el.value
                    for el in ast.walk(node.value)
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                }

    missing = sorted(
        name for name in listed if not any(TESTS_ROOT.rglob(name))
    )
    assert not missing, (
        f"_SKIP_BENCHMARK_TESTS names files that do not exist: {missing}"
    )


def test_declared_markers_cover_every_used_marker():
    """--strict-markers is on; pytest 9.1 makes an undeclared marker fatal.

    Four markers (transition/precision/long_audio/phase5d) were applied by test
    files but never declared, which pytest 9.0 downgraded to a warning. That was
    the second blocker to lifting the pytest ceiling (#4529).
    """
    ini = (TESTS_ROOT.parent / "pytest.ini").read_text()

    declared: set[str] = set()
    in_markers = False
    for raw in ini.splitlines():
        if raw.startswith("markers ="):
            in_markers = True
            continue
        if in_markers:
            if raw and not raw[0].isspace():
                break
            entry = raw.strip()
            if not entry or entry.startswith("#"):
                continue
            declared.add(entry.split(":", 1)[0].strip())

    # Built-in marks, plus `asyncio`, which pytest-asyncio registers itself.
    # Anything else must be declared in pytest.ini or --strict-markers rejects it.
    declared |= {
        "parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings",
        "asyncio",
    }

    used: set[str] = set()
    for path in TESTS_ROOT.rglob("test_*.py"):
        try:
            tree = _tree(path)
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            # pytest.mark.<name>  /  pytest.mark.<name>(...)
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "mark"
                and isinstance(value.value, ast.Name)
                and value.value.id == "pytest"
            ):
                used.add(node.attr)

    undeclared = sorted(used - declared)
    assert not undeclared, (
        f"markers applied but not declared in pytest.ini: {undeclared} — "
        "collection fails under pytest >= 9.1 with --strict-markers"
    )
