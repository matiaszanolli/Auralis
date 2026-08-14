"""
No queue.enqueue() runs synchronously on the event loop (#4702).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Three of five backend enqueue call sites offloaded with ``asyncio.to_thread``;
two called ``enqueue`` directly from an ``async def``. ``FingerprintQueue.enqueue``
is a bounded in-memory push under a lock, so the stall was sub-millisecond and
nothing broke — but the invariant is only useful if it holds uniformly, and the
``library_scan`` site is a comprehension over every newly-added track, so its
cost scales with the size of the import.

A static check rather than a behavioural one: the defect is "this call shape
exists somewhere", which a runtime test on one endpoint cannot cover. It is also
what keeps a future sixth call site honest.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
from pathlib import Path

import pytest

_ROUTERS = Path(__file__).parent.parent.parent / "auralis-web" / "backend" / "routers"


def _async_function_ranges(tree: ast.AST) -> list[tuple[int, int, str]]:
    """(start, end, name) for every `async def` in the module."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            out.append((node.lineno, node.end_lineno or node.lineno, node.name))
    return out


def _sync_function_ranges(tree: ast.AST) -> list[tuple[int, int, str]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            out.append((node.lineno, node.end_lineno or node.lineno, node.name))
    return out


def _innermost(ranges, line):
    """The most deeply nested function containing `line`, or None."""
    covering = [r for r in ranges if r[0] <= line <= r[1]]
    return max(covering, key=lambda r: r[0]) if covering else None


def _enqueue_references(path: Path):
    """Yield the line of every `.enqueue` reference in the module.

    Any attribute access, not just a call: after the fix the offloaded sites
    pass `queue.enqueue` to `to_thread` as a value, so matching only `ast.Call`
    would report those modules as having no enqueue at all — and the coverage
    guard below would then pass vacuously for exactly the files it exists to
    watch. Uses the AST so a reference in a comment or string is not counted.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "enqueue":
            yield node.lineno


def _router_modules():
    return sorted(p for p in _ROUTERS.glob("*.py") if p.name != "__init__.py")


class TestNoSyncEnqueueOnTheLoop:
    @pytest.mark.parametrize(
        "path", _router_modules(), ids=lambda p: p.name
    )
    def test_enqueue_is_never_called_directly_from_an_async_def(self, path):
        source = path.read_text()
        tree = ast.parse(source)
        async_ranges = _async_function_ranges(tree)
        sync_ranges = _sync_function_ranges(tree)

        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "enqueue"):
                continue

            # A call inside a nested sync def is fine: the enclosing async code
            # is expected to hand that whole function to to_thread. Compare
            # nesting depth so the innermost enclosing scope decides.
            inner_async = _innermost(async_ranges, node.lineno)
            inner_sync = _innermost(sync_ranges, node.lineno)
            if inner_async is None:
                continue
            if inner_sync is not None and inner_sync[0] > inner_async[0]:
                continue  # innermost scope is a sync def -> offloaded wholesale

            # Directly awaited via to_thread?
            line_src = source.splitlines()[node.lineno - 1]
            if "to_thread" in line_src:
                continue
            offenders.append((node.lineno, inner_async[2], line_src.strip()))

        assert not offenders, (
            f"{path.name}: enqueue() called synchronously on the event loop:\n"
            + "\n".join(f"  line {ln} in async def {fn}: {src}" for ln, fn, src in offenders)
            + "\n\nWrap it: `await asyncio.to_thread(queue.enqueue, track_id)`, or "
            "move the loop into a sync helper handed to to_thread wholesale."
        )


class TestTheKnownCallSitesAreCovered:
    """Guards the check itself: if these files stop containing enqueue calls,
    the parametrized test above would pass vacuously."""

    def test_the_expected_modules_still_contain_enqueue_calls(self):
        with_calls = {
            p.name for p in _router_modules() if any(_enqueue_references(p))
        }
        assert "fingerprint_status.py" in with_calls
        assert "library_scan.py" in with_calls
        assert "fingerprint_queue.py" in with_calls

    def test_offloaded_sites_use_await(self):
        """RETURN VALUE: a missing `await` yields a truthy coroutine and
        inverts every `if queued:` / `sum(...)` the callers depend on."""
        for path in _router_modules():
            source = path.read_text()
            for i, line in enumerate(source.splitlines(), 1):
                if "to_thread" in line and "enqueue" in line:
                    assert "await" in line, (
                        f"{path.name}:{i} wraps enqueue in to_thread without "
                        f"awaiting it — the result is a coroutine, always truthy: {line.strip()}"
                    )
