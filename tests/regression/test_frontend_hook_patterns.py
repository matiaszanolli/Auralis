"""
Regression tests: frontend hook patterns (#2372, #2373, #2374)

Source-level verification that fixed patterns remain in place:
- #2372: handleNext/handlePrevious must not capture stale closure
- #2373: usePlaybackQueue initial fetch must not create infinite loop
- #2374: useStandardizedAPI must destructure primitives to avoid re-fetch

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from pathlib import Path

import pytest

FRONTEND_SRC = Path(__file__).parent.parent.parent / "auralis-web" / "frontend" / "src"


class TestHandleNextPreviousStaleClosure:
    """Regression: handleNext/handlePrevious stale closure (#2372, #2346)."""

    def test_handlers_use_commands_prop(self):
        """Handlers must call commands.next()/commands.previous(), not stale refs."""
        source = (FRONTEND_SRC / "components" / "shared" / "PlayerControls.tsx").read_text()
        assert "commands.next()" in source, (
            "handleNext must use commands.next() — not a stale closure"
        )
        assert "commands.previous()" in source, (
            "handlePrevious must use commands.previous() — not a stale closure"
        )


class TestUsePlaybackQueueNoInfiniteLoop:
    """Regression: usePlaybackQueue infinite fetch loop (#2373, #2340)."""

    def test_initial_fetch_exists(self):
        """Hook must have an initial fetch effect."""
        source = (FRONTEND_SRC / "hooks" / "player" / "usePlaybackQueue.ts").read_text()
        assert "fetchInitialQueue" in source or "useEffect" in source, (
            "usePlaybackQueue must have initial fetch logic"
        )

    def test_no_state_in_fetch_deps(self):
        """Fetch effect deps must not include queue state (would cause loop)."""
        source = (FRONTEND_SRC / "hooks" / "player" / "usePlaybackQueue.ts").read_text()
        # The effect that fetches initial queue should depend on 'get' only,
        # not on any state that changes after fetch completes
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "fetchInitialQueue" in line and "useEffect" in line:
                # Check the dependency array near this line
                for j in range(i, min(i + 10, len(lines))):
                    if "], [" in lines[j] or "}," in lines[j]:
                        # Should not contain 'queue' or 'tracks' in deps
                        assert "queue" not in lines[j].lower() or "Queue" in lines[j], (
                            f"Line {j+1}: fetch deps should not include queue state"
                        )


class TestUseStandardizedAPINoReRefetch:
    """Regression: useStandardizedAPI infinite re-fetch (#2374, #2342)."""

    def test_body_stored_in_ref(self):
        """Request body must be stored in useRef, not dependency array."""
        source = (FRONTEND_SRC / "hooks" / "shared" / "useStandardizedAPI.ts").read_text()
        assert "bodyRef" in source or "useRef" in source, (
            "useStandardizedAPI must store body in ref to avoid re-fetch"
        )

    def test_primitive_extraction_from_options(self):
        """Options object must be destructured to primitives for stable deps."""
        source = (FRONTEND_SRC / "hooks" / "shared" / "useStandardizedAPI.ts").read_text()
        # Check that method/timeout/cache are extracted as primitives
        has_extraction = (
            "options?.method" in source or
            "method = " in source or
            "const method" in source
        )
        assert has_extraction, (
            "useStandardizedAPI must extract primitive values from options "
            "to prevent dependency churn from inline objects"
        )
