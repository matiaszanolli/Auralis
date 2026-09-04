"""Every WebSocket message type is declared on both sides (#4680).

The frontend has a compile-time exhaustiveness assertion guaranteeing
`ALL_MESSAGE_TYPES` covers the `WebSocketMessageType` union — but nothing
guaranteed the union covers what the backend actually *sends*, so drift was
silent in exactly one direction and accumulated in both:

* `cache_cleared` (#4585) and `job_progress` (#4680) were emitted with no
  frontend declaration, so `dispatchMessage` resolved them to an empty handler
  set and dropped them;
* `queue_updated` stayed declared on four frontend sites for months after
  #3492 deleted its emitter — a subscription key that could never fire.

This is the mechanical check the issue asked for, so the finding does not
recur a fourth time by audit. It reads the backend's emitted string literals
via AST (not grep, so a commented-out or docstring occurrence cannot count) and
compares them against `ALL_MESSAGE_TYPES` parsed out of the TS source.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "auralis-web" / "backend"
_REGISTRY_TS = _REPO / "auralis-web" / "frontend" / "src" / "types" / "ws" / "registry.ts"
_API_DOC = _BACKEND / "WEBSOCKET_API.md"

if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Types that are legitimately on exactly one side. Each entry is a deliberate
# transport-layer decision, not drift — which is the whole reason the list is
# spelled out here rather than the check being loosened.
BACKEND_ONLY = {
    # Protocol control frames. Answered inside the connection layer and never
    # dispatched to subscribers, so they have no place in a subscription union.
    "ping",
    "pong",
    # The JSON header preceding each binary PCM frame. WebSocketContext fuses
    # it with the frame that follows into a synthetic `audio_chunk` before any
    # subscriber sees it (#4167), and asserts it is never dispatched raw.
    "audio_chunk_meta",
}

FRONTEND_ONLY = {
    # The synthetic event produced by that fusion. Nothing puts it on the wire.
    "audio_chunk",
}


def _backend_emitted() -> dict[str, set[str]]:
    """Every typed broadcast or literal message built in the backend."""
    emitted: dict[str, set[str]] = {}
    for path in sorted(_BACKEND.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a broken file fails elsewhere
            continue
        for node in ast.walk(tree):
            literal: str | None = None
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "type"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        literal = value.value
                        break
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "broadcast_typed"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                literal = node.args[1].value

            if literal is not None:
                site = f"{path.relative_to(_REPO)}:{node.lineno}"
                emitted.setdefault(literal, set()).add(site)
    return emitted


def _all_message_types() -> list[str]:
    """`ALL_MESSAGE_TYPES` as declared in registry.ts, in source order."""
    source = _REGISTRY_TS.read_text()
    # Split on "= [" first: the type annotation itself contains "[]", so
    # splitting straight to the first "]" would truncate the block to nothing.
    block = source.split("export const ALL_MESSAGE_TYPES", 1)[1]
    block = block.split("= [", 1)[1].split("]", 1)[0]
    return re.findall(r"'([a-z_]+)'", block)


def _documented_union() -> list[str]:
    """The hand-maintained union reproduced in WEBSOCKET_API.md."""
    source = _API_DOC.read_text()
    block = source.split("The complete `WebSocketMessageType` union", 1)[1]
    block = block.split("```typescript", 1)[1].split("```", 1)[0]
    return re.findall(r"\|\s*'([a-z_]+)'", block)


@pytest.fixture(scope="module")
def emitted() -> dict[str, set[str]]:
    return _backend_emitted()


@pytest.fixture(scope="module")
def registry() -> list[str]:
    return _all_message_types()


class TestBothDirections:
    def test_every_emitted_type_is_declared_by_the_frontend(self, emitted, registry):
        """The direction nothing guarded — how cache_cleared and job_progress hid."""
        undeclared = {
            name: sorted(sites)
            for name, sites in emitted.items()
            if name not in registry and name not in BACKEND_ONLY
        }
        assert not undeclared, (
            "backend emits types the frontend cannot subscribe to:\n"
            + "\n".join(f"  {n}: {s[0]}" for n, s in sorted(undeclared.items()))
            + "\nAdd them to src/types/ws/, or to BACKEND_ONLY with the reason."
        )

    def test_no_declared_type_is_unreachable(self, emitted, registry):
        """The direction that left queue_updated declared for months."""
        dead = [
            name
            for name in registry
            if name not in emitted and name not in FRONTEND_ONLY
        ]
        assert not dead, (
            f"frontend declares types the backend cannot emit: {dead}\n"
            "Delete them, or add to FRONTEND_ONLY with the reason."
        )


class TestTheSpecificDriftedTypes:
    """Named checks, so a regression says which one came back."""

    def test_job_progress_is_declared(self, emitted, registry):
        assert "job_progress" in emitted
        assert "job_progress" in registry

    def test_cache_cleared_stays_declared(self, emitted, registry):
        assert "cache_cleared" in emitted
        assert "cache_cleared" in registry

    def test_queue_updated_is_gone_from_both_sides(self, emitted, registry):
        assert "queue_updated" not in emitted, "an emitter came back — #3492 removed it"
        assert "queue_updated" not in registry
        ws_dir = _REGISTRY_TS.parent
        for module in sorted(ws_dir.glob("*.ts")):
            text = module.read_text()
            # The queue.ts tombstone comment explains the removal; only code
            # occurrences matter.
            code = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("//")
            )
            assert "queue_updated" not in code, f"{module.name} still declares it"


class TestTheHandMaintainedDocs:
    """#4991: the doc's reproduced union drifted from the real one and stayed
    wrong because nothing compared them."""

    def test_documented_union_matches_the_registry(self, registry):
        documented = _documented_union()
        assert sorted(documented) == sorted(registry), (
            f"WEBSOCKET_API.md is stale.\n"
            f"  only in doc:      {sorted(set(documented) - set(registry))}\n"
            f"  only in registry: {sorted(set(registry) - set(documented))}"
        )

    def test_the_member_count_in_the_prose_is_right(self, registry):
        source = _API_DOC.read_text()
        match = re.search(r"`WebSocketMessageType` union \((\d+) members\)", source)
        assert match, "the union header lost its member count"
        assert int(match.group(1)) == len(registry)


def test_the_allowlists_are_not_quietly_absorbing_drift(emitted, registry):
    """An allowlist entry that no longer applies is drift of its own."""
    for name in BACKEND_ONLY:
        assert name in emitted, f"BACKEND_ONLY entry {name!r} is no longer emitted"
        assert name not in registry, f"{name!r} is declared after all — drop the entry"
    for name in FRONTEND_ONLY:
        assert name in registry, f"FRONTEND_ONLY entry {name!r} is no longer declared"
        assert name not in emitted, f"{name!r} is emitted after all — drop the entry"
