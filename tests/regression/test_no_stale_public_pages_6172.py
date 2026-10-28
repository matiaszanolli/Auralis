"""#6172: the retired MSE debug page must not ship in the production bundle.

Everything under ``auralis-web/frontend/public`` is copied into ``dist/`` and the
Electron resources, so a stray HTML page there is an extra same-origin page with
inline script.
"""

from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[2] / "auralis-web" / "frontend" / "public"


def test_public_dir_ships_no_html_pages():
    assert PUBLIC.is_dir()
    assert sorted(p.name for p in PUBLIC.glob("*.html")) == []
