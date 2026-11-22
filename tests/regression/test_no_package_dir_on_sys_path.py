"""
No test puts the auralis/ package directory itself on sys.path
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four tests/boundaries files did ``sys.path.insert(0, <repo>/auralis)``. That
makes every subpackage of auralis importable as a top-level package, so a
later ``import analysis...`` (meant for auralis-web/backend/analysis) loaded
auralis/analysis instead, and broke on its first relative import beyond the
package (``from ..dsp...`` in dynamic_range.py). Whether it failed depended on
whether a boundaries file had been collected earlier in the same process.

The repository root is already importable (pytest rootdir), which is all
``import auralis...`` needs.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]

# sys.path.insert/append whose path expression ends in the bare 'auralis'
# directory (not 'auralis-web', not a deeper path).
_PACKAGE_DIR_ON_PATH = re.compile(
    r"""sys\.path\.(?:insert|append)\(.*[/(,]\s*['"]auralis['"]\s*\)+\s*$"""
)


def offending_lines(source: str) -> list[int]:
    return [
        lineno for lineno, line in enumerate(source.splitlines(), 1)
        if _PACKAGE_DIR_ON_PATH.search(line)
    ]


def test_pattern_matches_the_removed_form_and_not_legitimate_ones():
    assert offending_lines(
        "sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis'))"
    ) == [1]
    assert offending_lines('sys.path.append(os.path.join(root, "auralis"))') == [1]
    assert offending_lines(
        "sys.path.insert(0, str(Path(__file__).parent.parent / 'auralis-web' / 'backend'))"
    ) == []
    assert offending_lines("sys.path.insert(0, str(project_root))") == []


def test_no_test_module_puts_the_auralis_package_dir_on_sys_path():
    offenders = []
    for path in sorted(TESTS_ROOT.rglob('*.py')):
        if path == Path(__file__).resolve():
            continue
        lines = offending_lines(path.read_text(encoding='utf-8'))
        offenders += [f'{path.relative_to(TESTS_ROOT.parent)}:{n}' for n in lines]
    assert offenders == []
