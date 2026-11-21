"""The router deps plumbing lives once in routers/dependencies.py (#6624).

Every ``*_deps.py`` holder used to define its own placeholder getter
(``_unavailable`` or an inline ``lambda: None``), its own optional-getter
resolver and, in five routers, the same ``_get_connection_manager`` body. They
now share ``unavailable``, ``resolve_optional`` and ``provide_connection_manager``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from routers.dependencies import (
    RouterDeps,
    provide_connection_manager,
    resolve_optional,
    unavailable,
)

_ROUTERS = Path(__file__).resolve().parents[2] / "auralis-web" / "backend" / "routers"


class _Holder:
    def __init__(self, connection_manager: object = None) -> None:
        self.connection_manager = connection_manager


def test_the_placeholder_getter_resolves_to_none():
    assert unavailable() is None


def test_resolve_optional_calls_a_getter_and_tolerates_a_missing_one():
    assert resolve_optional(None) is None
    assert resolve_optional(lambda: "factory") == "factory"


def test_the_connection_manager_comes_from_the_router_serving_the_request():
    """Two routers' providers must not see each other's manager (#5262, #5762)."""
    first = RouterDeps("first_6624", _Holder())
    second = RouterDeps("second_6624", _Holder())
    get_first = provide_connection_manager(first)
    get_second = provide_connection_manager(second)

    first.bind(_Holder("bound-first"))
    second.bind(_Holder("bound-second"))
    assert get_first() == "bound-first"
    assert get_second() == "bound-second"

    with first.use(_Holder("request-first")):
        assert get_first() == "request-first"
        assert get_second() == "bound-second"


@pytest.mark.parametrize(
    "pattern",
    [r"def _unavailable\(", r"lambda: None", r"def _get_connection_manager\("],
)
def test_no_router_module_retypes_the_shared_plumbing(pattern):
    offenders = [
        path.name
        for path in sorted(_ROUTERS.glob("*.py"))
        if path.name != "dependencies.py" and re.search(pattern, path.read_text())
    ]
    assert offenders == [], f"{pattern!r} retyped in {offenders}; use routers/dependencies.py"
