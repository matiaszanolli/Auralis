"""No router keeps a no-op `except HTTPException: raise`, and the stragglers use @with_error_handling (#6506).

#6210/#4605 moved the routers onto @with_error_handling but left copies: get_processing_parameters
re-implemented the pattern (bypassing handle_query_error's status mapping), cleanup_old_jobs had no
decorator at all, and several handlers kept an `except HTTPException: raise` that changed nothing.
Such an arm only matters when a later handler of the same try would otherwise catch the
HTTPException (Exception, BaseException or a bare except); every other one is dead code.
"""

import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[2] / "auralis-web" / "backend" / "routers"
_CATCHES_HTTP_EXCEPTION = {"Exception", "BaseException"}


def _is_bare_reraise_of_http_exception(handler: ast.ExceptHandler) -> bool:
    named = isinstance(handler.type, ast.Name) and handler.type.id == "HTTPException"
    body_is_raise = len(handler.body) == 1 and isinstance(handler.body[0], ast.Raise) and handler.body[0].exc is None
    return named and body_is_raise


def _catches_http_exception(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in _CATCHES_HTTP_EXCEPTION for t in types)


def test_no_router_has_a_no_op_http_exception_reraise():
    offenders = []
    for path in sorted(ROUTERS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Try):
                continue
            for index, handler in enumerate(node.handlers):
                later = node.handlers[index + 1:]
                if _is_bare_reraise_of_http_exception(handler) and not any(map(_catches_http_exception, later)):
                    offenders.append(f"{path.name}:{handler.lineno}")
    assert offenders == [], f"no-op `except HTTPException: raise` arms: {offenders}"


def test_the_stragglers_are_decorated():
    for module, function in (("processing_parameters.py", "get_processing_parameters"),
                             ("processing_jobs.py", "cleanup_old_jobs")):
        tree = ast.parse((ROUTERS / module).read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == function)
        names = [d.func.id for d in fn.decorator_list if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)]
        assert "with_error_handling" in names, f"{module}:{function} is not decorated"
