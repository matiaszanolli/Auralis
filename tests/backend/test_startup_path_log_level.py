"""
Regression: startup path logs at DEBUG, not INFO (#4376)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The startup sequence logged the absolute music-library directory and database
path at INFO ("Database directory ready", "Database location"). Absolute
home/database paths are sensitive and persist to the on-disk electron-log, so
they were demoted to DEBUG — consistent with the #3844 demotion of the sibling
path-validation logs.

These path lines live inside the heavy lifespan() context manager, so this
guard asserts the source uses logger.debug (not logger.info) for them rather
than driving a full application startup.
"""

import ast
from pathlib import Path

STARTUP = (
    Path(__file__).parent.parent.parent
    / "auralis-web" / "backend" / "config" / "startup.py"
)

# The two path-logging call sites, keyed by a distinctive substring.
PATH_LOG_MARKERS = ("Database directory ready", "Database location")


def _logger_calls() -> list[tuple[str, str]]:
    """Return (level, literal_text) for every logger.<level>(f"...") call whose
    f-string static parts contain one of the path markers."""
    tree = ast.parse(STARTUP.read_text())
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logger"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        # Collect the static text from a plain str or an f-string.
        text = ""
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            text = arg.value
        elif isinstance(arg, ast.JoinedStr):
            text = "".join(
                v.value for v in arg.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        if any(marker in text for marker in PATH_LOG_MARKERS):
            found.append((node.func.attr, text))
    return found


def test_both_path_markers_present():
    """Guard the markers still exist (renamed messages would silently pass)."""
    calls = _logger_calls()
    texts = " ".join(t for _, t in calls)
    for marker in PATH_LOG_MARKERS:
        assert marker in texts, f"expected a startup log containing {marker!r}"


def test_path_logs_are_debug_not_info():
    for level, text in _logger_calls():
        assert level == "debug", (
            f"startup path log {text!r} logs at {level}(); absolute paths must "
            "log at DEBUG so they do not persist to the electron-log (#4376)"
        )
