# -*- coding: utf-8 -*-

"""
Regression guard: the realtime adaptive EQ path stays unwired (#4615)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``RealtimeAdaptiveEQ._process_fixed_chunk`` calls ``PsychoacousticEQ.apply_eq``
with no analysis window and no overlap-add. ``apply_eq_mono`` is documented as
deliberately un-windowed, delegating overlap-add to its caller
(``dsp/eq/filters.py``); the offline ``EQProcessor`` path honours that with a
COLA-correct 50 %-hop WOLA loop (#4217), and this path does not.

That defect is latent rather than live only because the chain has no production
callers. #4615 was resolved by documenting the path as reserved and not
WOLA-safe rather than by building a second WOLA implementation — a second,
subtly-different WOLA is how #3294 (~6 dB COLA ripple) happened in the first
place.

This module makes that resolution machine-checkable: wiring the path into
production without first routing it through a shared WOLA helper fails CI
instead of silently shipping block-boundary clicking.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = (REPO_ROOT / "auralis", REPO_ROOT / "auralis-web")

# The chain: HybridProcessor.process_realtime_chunk
#              -> RealtimeDSPPipeline.process_chunk
#              -> RealtimeAdaptiveEQ.process_realtime
#              -> _process_fixed_chunk / _handle_variable_chunk_size -> apply_eq
#
# Only the outermost name is checked for callers. The inner links are
# implementation detail of a path that is unreachable while the outer one has
# no callers.
ENTRY_POINT = "process_realtime_chunk"

# `PsychoacousticEQ.process_realtime_chunk` is a DIFFERENT method that happens
# to share the name. It is called by eq_processor.py from *inside* the
# COLA-correct WOLA loop, which is correct and must not be flagged. Calls whose
# receiver ends in one of these attribute names are the WOLA-path method.
WOLA_PATH_RECEIVERS = {"psychoacoustic_eq"}


def _production_files():
    for root in PRODUCTION_ROOTS:
        for path in sorted(root.rglob("*.py")):
            yield path


def _receiver_name(node: ast.AST) -> str | None:
    """Trailing attribute/name of a call receiver, e.g. `self.foo.bar` -> 'foo'."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _find_calls(tree: ast.AST, method: str) -> list[tuple[int, str | None]]:
    """(lineno, receiver) for every real call to ``.method(...)``.

    AST-based on purpose: a line-based grep also matches the #4615 docstrings
    that name the method, which is exactly the false positive this guard must
    not produce.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == method:
            found.append((node.lineno, _receiver_name(func.value)))
        elif isinstance(func, ast.Name) and func.id == method:
            found.append((node.lineno, None))
    return found


def test_process_realtime_chunk_has_no_production_callers():
    """The WOLA-unsafe path must stay unreachable from production code.

    If this fails, someone wired up ``HybridProcessor.process_realtime_chunk``.
    Do not silence the test — route the path through ``EQProcessor``'s existing
    COLA-verified WOLA loop (extracted into a shared helper) first, then update
    this guard and the #4615 docstrings.
    """
    offenders = []
    for path in _production_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):  # pragma: no cover
            continue
        for lineno, receiver in _find_calls(tree, ENTRY_POINT):
            if receiver in WOLA_PATH_RECEIVERS:
                continue  # PsychoacousticEQ's method on the correct WOLA path
            offenders.append(f"{rel}:{lineno} (receiver: {receiver})")

    assert not offenders, (
        "HybridProcessor.process_realtime_chunk gained a production caller, but "
        "its EQ path still applies block FFT gain with no window and no "
        "overlap-add (#4615). Route it through EQProcessor's WOLA loop before "
        "wiring it up:\n  " + "\n  ".join(offenders)
    )


def test_wola_path_call_is_still_recognised():
    """Guard the guard.

    ``eq_processor.py`` calls ``self.psychoacoustic_eq.process_realtime_chunk``
    from inside the correct WOLA loop. If that call moves or is renamed, the
    exemption above silently stops matching and the caller test would start
    reporting it as an offender. Assert the exempted call actually exists, so a
    stale exemption fails loudly rather than masking a real regression.
    """
    path = REPO_ROOT / "auralis" / "core" / "processing" / "eq_processor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    receivers = {r for _, r in _find_calls(tree, ENTRY_POINT)}

    assert receivers & WOLA_PATH_RECEIVERS, (
        "eq_processor.py no longer calls psychoacoustic_eq.process_realtime_chunk. "
        "The WOLA_PATH_RECEIVERS exemption in this module is now stale — update "
        "it, or the no-production-callers guard will misreport."
    )


def test_unwired_status_is_documented_on_every_entry_point():
    """The docstrings are the fix — they must not be silently dropped."""
    from auralis.core.hybrid_processor import HybridProcessor
    from auralis.dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ

    for owner, name in (
        (HybridProcessor, "process_realtime_chunk"),
        (RealtimeAdaptiveEQ, "process_realtime"),
        # SIBLING check: both inner entry points, not just the reported one.
        (RealtimeAdaptiveEQ, "_process_fixed_chunk"),
        (RealtimeAdaptiveEQ, "_handle_variable_chunk_size"),
    ):
        doc = inspect.getdoc(getattr(owner, name)) or ""
        assert "WOLA-SAFE" in doc.upper(), (
            f"{owner.__name__}.{name} lost its #4615 not-WOLA-safe warning"
        )
        assert "4615" in doc, (
            f"{owner.__name__}.{name} lost its #4615 issue reference"
        )


def test_no_second_wola_was_introduced_in_the_realtime_path():
    """CONSISTENCY check from #4615, scoped to the resolution actually taken.

    Option (b) was chosen: document the path rather than fix it. So the
    realtime EQ module must NOT have grown its own window/overlap-add
    machinery — if someone adds one here instead of extracting the shared
    helper from ``eq_processor.py``, that is precisely the second,
    subtly-different WOLA that caused #3294.

    Deliberately narrow: Hann windows have many legitimate non-WOLA uses
    elsewhere in the codebase (spectral analysis, resonance notching, FFT
    helpers), so a repo-wide window count would be noise, not signal.
    """
    path = REPO_ROOT / "auralis" / "dsp" / "realtime_adaptive_eq" / "realtime_eq.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    window_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _receiver_name(node.func)
        if name in {"hanning", "hann", "get_window", "blackman", "hamming"}:
            window_calls.append(node.lineno)

    assert not window_calls, (
        "realtime_eq.py grew a window function at line(s) "
        f"{window_calls}. #4615 resolved this path as documented-unwired, not "
        "fixed. If you are now fixing it, extract EQProcessor's COLA-verified "
        "WOLA loop into a shared helper and call that — do not write a second "
        "one here (#3294)."
    )


@pytest.mark.parametrize("method", ["_process_fixed_chunk", "_handle_variable_chunk_size"])
def test_both_sibling_entry_points_still_exist(method):
    """SIBLING check: the fix must cover both, not just the one in the report."""
    from auralis.dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ

    assert hasattr(RealtimeAdaptiveEQ, method), (
        f"{method} disappeared — if the path was removed, delete this guard too"
    )
