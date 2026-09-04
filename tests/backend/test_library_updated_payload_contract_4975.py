"""
`library_updated` payload matches its declared TS contract (#4975)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both emitters used to ship a `reason` field explicitly commented "kept for
backward compat; new consumers use `action`" (#3544). The frontend's
`LibraryUpdatedMessage` never declared it and no consumer read it, and since
Auralis ships frontend and backend as a single Electron bundle there is no
independently-versioned older client that could still be reading it — so the
backward-compat rationale was structurally void. Dropped in #4975.

These tests pin the payload key set against the TypeScript interface so a
re-added undeclared field fails here rather than surfacing as permanent
`sync-contracts` drift.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TS_CONTRACT = _REPO_ROOT / "auralis-web/frontend/src/types/ws/library.ts"
_EMITTERS = {
    "routers/library_scan.py": _REPO_ROOT / "auralis-web/backend/routers/library_scan.py",
    "services/library_auto_scanner.py": _REPO_ROOT / "auralis-web/backend/services/library_auto_scanner.py",
}


def _declared_fields() -> set[str]:
    """Field names declared on LibraryUpdatedMessage['data'] in the TS contract."""
    source = _TS_CONTRACT.read_text()
    block = re.search(
        r"interface LibraryUpdatedMessage.*?data:\s*\{(.*?)\}", source, re.S
    )
    assert block, f"LibraryUpdatedMessage['data'] not found in {_TS_CONTRACT}"
    return set(re.findall(r"^\s*(\w+)\??:", block.group(1), re.M))


def _emitted_fields(path: Path) -> set[str]:
    """Field names in the `library_updated` broadcast payload of one emitter."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "broadcast_typed"
            and len(node.args) >= 3
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "library_updated"
            and isinstance(node.args[2], ast.Dict)
        ):
            continue
        return {
            key.value
            for key in node.args[2].keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    raise AssertionError(f"library_updated typed broadcast not found in {path}")


def test_ts_contract_declares_action_and_not_reason():
    declared = _declared_fields()
    assert "action" in declared
    assert "reason" not in declared, (
        "The TS contract gained a `reason` field — if that is intentional, "
        "these tests and both emitters need updating together."
    )


@pytest.mark.parametrize("label", sorted(_EMITTERS))
def test_emitter_sends_no_undeclared_field(label):
    """Every key an emitter sends must be declared in the TS interface (#4975)."""
    emitted = _emitted_fields(_EMITTERS[label])
    undeclared = emitted - _declared_fields()
    assert not undeclared, (
        f"{label} broadcasts undeclared library_updated field(s) {sorted(undeclared)}. "
        "Add them to LibraryUpdatedMessage in frontend/src/types/ws/library.ts, "
        "or stop sending them."
    )


@pytest.mark.parametrize("label", sorted(_EMITTERS))
def test_emitter_still_sends_action(label):
    """The guard above would also pass if an emitter sent nothing at all."""
    assert "action" in _emitted_fields(_EMITTERS[label])
