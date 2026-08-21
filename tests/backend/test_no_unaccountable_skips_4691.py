"""No backend test module is skipped without saying who owns it (#4691).

Eleven modules once carried a bare `pytestmark = pytest.mark.skip(...)` whose
reasons were stale API-drift excuses — "Tests use old TrackRepository API",
"APIs incompatible with current implementation". A skip reports as a skip, not
a failure, so CI and the release checklist stayed green over zero executing
assertions, and nothing ever announced when a reason stopped being true. Two of
them had in fact been wrong for months: `test_playlist_integration.py` passed
11/11 the moment #5171 landed, and `test_library_boundaries.py` needed only the
fixture rebuild `test_string_input_boundaries.py` had already received.

This is the ratchet that keeps that from recurring. A module-level skip is
allowed — some things genuinely cannot run yet — but it must name an issue, so
"why is this dark?" is always answerable and the backlog is honest about its
own size.
"""

import ast
import re
from pathlib import Path

import pytest

_BACKEND_TESTS = Path(__file__).parent
_ISSUE_REF = re.compile(r"#\d{3,}")


def _module_level_marks(path: Path) -> list[ast.Call]:
    """Every `pytest.mark.<something>(...)` assigned to a module-level `pytestmark`."""
    tree = ast.parse(path.read_text())
    calls: list[ast.Call] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            continue
        values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
        calls.extend(v for v in values if isinstance(v, ast.Call))
    return calls


def _mark_name(call: ast.Call) -> str:
    """`pytest.mark.skip(...)` -> "skip"."""
    return call.func.attr if isinstance(call.func, ast.Attribute) else ""


def _reason(call: ast.Call) -> str:
    for kw in call.keywords:
        if kw.arg == "reason":
            return ast.literal_eval(kw.value) if isinstance(kw.value, ast.Constant) else _join(kw.value)
    return ""


def _join(node: ast.AST) -> str:
    """Reasons are often implicitly-concatenated string literals."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp):
        return _join(node.left) + _join(node.right)
    if isinstance(node, ast.JoinedStr):
        return "".join(_join(v) for v in node.values)
    return ""


def _backend_test_modules() -> list[Path]:
    return sorted(p for p in _BACKEND_TESTS.glob("test_*.py"))


def test_there_are_backend_test_modules_to_check():
    """A glob that silently matches nothing would make every check below vacuous."""
    assert len(_backend_test_modules()) > 50


@pytest.mark.parametrize(
    "module", _backend_test_modules(), ids=lambda p: p.name
)
def test_module_level_skip_names_a_tracking_issue(module):
    for call in _module_level_marks(module):
        if _mark_name(call) != "skip":
            continue
        reason = _reason(call)
        assert _ISSUE_REF.search(reason), (
            f"{module.name} is skipped at module level with no issue reference.\n"
            f"  reason: {reason!r}\n"
            "A bare skip is how eleven modules went dark for months (#4691). "
            "Port the module, delete it, or file an issue and name it here."
        )


@pytest.mark.parametrize(
    "module", _backend_test_modules(), ids=lambda p: p.name
)
def test_module_level_xfail_is_strict(module):
    """A non-strict module-level xfail hides a module that started passing.

    Same failure mode as the bare skip, one marker over: the suite goes quiet
    either way, and nothing tells you when the reason stopped being true.
    """
    for call in _module_level_marks(module):
        if _mark_name(call) != "xfail":
            continue
        strict = next(
            (ast.literal_eval(kw.value) for kw in call.keywords
             if kw.arg == "strict" and isinstance(kw.value, ast.Constant)),
            None,
        )
        assert strict is True, (
            f"{module.name} has a module-level xfail that is not strict=True. "
            "Without strict, a module that starts passing stays silent."
        )


def test_conditional_skipif_is_not_caught_by_this_gate():
    """`skipif` is legitimate and deliberately out of scope (#4691).

    `test_migration_manager_fd_leak.py` guards on a platform condition; the
    finding was always about *unconditional* skips.
    """
    fd_leak = _BACKEND_TESTS / "test_migration_manager_fd_leak.py"
    if not fd_leak.exists():  # pragma: no cover - module may be renamed later
        pytest.skip("#4691: the skipif exemplar has moved; nothing to assert")

    names = {_mark_name(c) for c in _module_level_marks(fd_leak)}
    assert "skipif" in names
    assert "skip" not in names
