"""The `/` fallback must not disclose the install path (#4351).

When the built frontend is missing and the backend is not in dev mode, `GET /`
served a page that interpolated the absolute `frontend_path`. It was
HTML-escaped, so never an XSS vector, but any client that can reach `/` -- a
stray browser tab, a DNS-rebound page -- could read the install layout: the
PyInstaller `_MEIPASS` temp dir, or `/home/<user>/...`, which additionally
discloses the OS username.

Which `/` handler gets registered is decided at import time by `is_dev_mode()`
and `frontend_path.exists()`, so on a checkout that has a built frontend the
not-found branch is unreachable through the app. The page body is therefore a
module-level constant, and these tests assert on it directly rather than
pretending to exercise a branch they cannot enter.
"""

import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import main  # noqa: E402


# Shapes that would indicate a leaked filesystem path.
PATH_PATTERNS = [
    r"/home/",
    r"/Users/",
    r"/root/",
    r"/tmp/",
    r"/var/folders/",       # macOS temp, where _MEIPASS lands
    r"_MEI",                # PyInstaller extraction dir
    r"[A-Za-z]:\\",         # Windows drive letter
    r"/mnt/",
]


class TestFrontendMissingPage:
    def test_page_contains_no_filesystem_path(self):
        for pattern in PATH_PATTERNS:
            assert not re.search(pattern, main.FRONTEND_MISSING_HTML), (
                f"`/` fallback body matches {pattern!r} — it is disclosing a path (#4351)"
            )

    def test_page_does_not_interpolate_the_frontend_path(self):
        """The specific regression: the real resolved path must not appear."""
        assert str(main.frontend_path) not in main.FRONTEND_MISSING_HTML

    def test_page_is_a_plain_string_not_an_f_string_template(self):
        """An unformatted placeholder would mean the interpolation came back."""
        assert "{" not in main.FRONTEND_MISSING_HTML
        assert "}" not in main.FRONTEND_MISSING_HTML

    def test_page_still_tells_the_user_what_went_wrong(self):
        """Removing the path must not reduce this to a blank error."""
        body = main.FRONTEND_MISSING_HTML.lower()
        assert "not found" in body
        assert "reinstall" in body

    def test_page_still_links_the_api_docs(self):
        assert "/api/docs" in main.FRONTEND_MISSING_HTML


class TestPathStillAvailableServerSide:
    """Acceptance criterion: the absolute path is still logged for diagnostics."""

    def test_main_logs_the_frontend_path_at_debug(self):
        source = (Path(_BACKEND) / "main.py").read_text()
        # Comment lines are stripped so prose about the path does not satisfy
        # the assertion -- a mistake worth guarding against, since the comment
        # right above these calls talks about exactly this.
        code = "\n".join(
            line for line in source.split("\n") if not line.lstrip().startswith("#")
        )
        assert 'logger.debug(f"Looking for frontend at: {frontend_path}")' in code
        assert 'logger.debug(f"Frontend not found at: {frontend_path}")' in code

    def test_the_path_is_not_logged_at_info_or_warning(self):
        """#4366 keeps absolute paths out of INFO so logs stay safe to paste
        into a public bug report; this fix must not undo that."""
        source = (Path(_BACKEND) / "main.py").read_text()
        code = "\n".join(
            line for line in source.split("\n") if not line.lstrip().startswith("#")
        )
        for level in ("info", "warning", "error"):
            for match in re.finditer(rf"logger\.{level}\((.*)\)", code):
                assert "frontend_path" not in match.group(1), (
                    f"logger.{level} emits frontend_path: {match.group(0)}"
                )


# One representative leak per pattern, so the meta-test below proves each
# pattern is non-vacuous rather than proving it against a sample that happens
# to contain some other pattern.
LEAK_SAMPLES = {
    r"/home/": "not found at: /home/someone/app/frontend",
    r"/Users/": "not found at: /Users/someone/app/frontend",
    r"/root/": "not found at: /root/app/frontend",
    r"/tmp/": "not found at: /tmp/_MEI123/frontend",
    r"/var/folders/": "not found at: /var/folders/xy/T/app/frontend",
    r"_MEI": "not found at: /somewhere/_MEIabc123/frontend",
    r"[A-Za-z]:\\": r"not found at: C:\Users\someone\app",
    r"/mnt/": "not found at: /mnt/data/src/app/frontend",
}


def test_every_pattern_has_a_sample():
    """Guards the mapping itself: a pattern added without a sample would slip
    past the discriminating check below entirely."""
    assert sorted(LEAK_SAMPLES) == sorted(PATH_PATTERNS)


@pytest.mark.parametrize("pattern", PATH_PATTERNS)
def test_patterns_are_discriminating(pattern):
    """Each detector must actually fire on a leak of its own shape — otherwise
    the assertions above pass for the wrong reason."""
    assert re.search(pattern, LEAK_SAMPLES[pattern])
