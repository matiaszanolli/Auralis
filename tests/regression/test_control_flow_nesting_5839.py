"""No production function nests control flow deeper than four levels (#5839).

The 2026-10 census found 32 functions at depth 5-7 (three of them the audio
streaming pumps). They were flattened with guard clauses and small helpers; this
keeps the count at zero. Depth counts ``if``/``for``/``while``/``try``/``with``/
``match`` blocks, an ``elif`` continuing its chain rather than adding a level.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ROOTS = (REPO / "auralis", REPO / "auralis-web" / "backend")
MAX_DEPTH = 4

_BLOCKS = (
    ast.If, ast.For, ast.While, ast.Try, ast.With,
    ast.AsyncFor, ast.AsyncWith, ast.Match,
)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _depth(node: ast.AST, level: int = 0) -> int:
    deepest = level
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPES):
            continue  # a nested def is measured on its own
        if isinstance(child, _BLOCKS):
            is_elif = (
                isinstance(node, ast.If)
                and isinstance(child, ast.If)
                and node.orelse == [child]
            )
            deepest = max(deepest, _depth(child, level if is_elif else level + 1))
        else:
            deepest = max(deepest, _depth(child, level))
    return deepest


@pytest.mark.regression
def test_no_function_nests_control_flow_deeper_than_four_levels():
    offenders = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    depth = _depth(node)
                    if depth > MAX_DEPTH:
                        offenders.append(f"{path.relative_to(REPO)}:{node.lineno} {node.name} (depth {depth})")
    assert offenders == [], "flatten with guard clauses / helpers:\n" + "\n".join(sorted(offenders))
