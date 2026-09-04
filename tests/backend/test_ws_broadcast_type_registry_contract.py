"""Contract: every backend WS broadcast type is modelled on the frontend (#4585).

`WebSocketContext.dispatchMessage` resolves handlers from a `Map<type, Set>`.
A broadcast whose type literal was never registered in the frontend registry
resolves to an empty handler set and is dropped with no warning — invisible to
the type system, to the `_AssertExhaustive` check in `registry.ts` (which can
only guard types already imported there), and to any runtime log.

That is exactly how `cache_cleared` survived the #3545 fix: the envelope half
was corrected and the registration half was not, so a broadcast that looks
correct at both ends went nowhere for months.

This test closes the *class* rather than the instance: it enumerates the
`"type": "..."` literals the backend actually broadcasts and asserts each one
appears in `ALL_MESSAGE_TYPES`.
"""

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "auralis-web" / "backend"
_REGISTRY = _REPO_ROOT / "auralis-web" / "frontend" / "src" / "types" / "ws" / "registry.ts"

# Types deliberately absent from the public union.
_INTENTIONALLY_UNREGISTERED = {
    # Internal chunk-metadata frame consumed directly by WebSocketContext and
    # kept out of AnyWebSocketMessage / ALL_MESSAGE_TYPES (#4167).
    "audio_chunk_meta",
}

# Only these directories originate broadcasts.
_BROADCAST_DIRS = ("routers", "services", "core")

def _frontend_registered_types() -> set[str]:
    """Parse the ALL_MESSAGE_TYPES array out of registry.ts."""
    source = _REGISTRY.read_text()
    match = re.search(
        r"ALL_MESSAGE_TYPES\s*:\s*readonly WebSocketMessageType\[\]\s*=\s*\[(.*?)\]",
        source,
        re.DOTALL,
    )
    assert match, "could not locate ALL_MESSAGE_TYPES in registry.ts"
    return set(re.findall(r"['\"]([a-z_][a-z0-9_]*)['\"]", match.group(1)))


def _backend_broadcast_types() -> dict[str, list[str]]:
    """Map each typed broadcast discriminator to the files that emit it."""
    found: dict[str, list[str]] = {}
    for subdir in _BROADCAST_DIRS:
        base = _BACKEND / subdir
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "broadcast_typed"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                ):
                    continue
                found.setdefault(node.args[1].value, []).append(
                    str(path.relative_to(_REPO_ROOT))
                )
    return found


@pytest.mark.skipif(not _REGISTRY.exists(), reason="frontend registry not present")
class TestBroadcastTypeRegistryContract:

    def test_every_backend_broadcast_type_is_registered_on_the_frontend(self):
        registered = _frontend_registered_types()
        emitted = _backend_broadcast_types()

        orphaned = {
            literal: sorted(set(files))
            for literal, files in emitted.items()
            if literal not in registered and literal not in _INTENTIONALLY_UNREGISTERED
        }

        assert not orphaned, (
            "backend broadcasts these types with no frontend counterpart — they "
            "will be dropped silently by WebSocketContext.dispatchMessage:\n"
            + "\n".join(f"  {t}: {files}" for t, files in sorted(orphaned.items()))
            + "\nRegister each in types/ws/<domain>.ts, WebSocketMessageType, "
            "AnyWebSocketMessage and ALL_MESSAGE_TYPES (#4585)."
        )

    def test_cache_cleared_specifically_is_registered(self):
        """The #4585 instance — guards against a silent revert."""
        assert "cache_cleared" in _frontend_registered_types()

    def test_detector_actually_sees_the_backend_broadcasts(self):
        """Guard the guard: a broken scan would make this test vacuously pass."""
        emitted = _backend_broadcast_types()
        assert "cache_cleared" in emitted, "scan failed to find the cache_cleared broadcast"
        assert len(emitted) > 15, f"scan found suspiciously few broadcasts: {sorted(emitted)}"
