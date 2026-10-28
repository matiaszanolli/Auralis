"""Backend startup no longer creates an unused ~/Music/Auralis (#5988).

``_init_library_database`` made ``~/Music/Auralis`` and logged it as the
"Database directory ready", but the database lives in ``~/.auralis`` and nothing
else used the folder; a failure creating it rolled back the whole library init.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import components  # noqa: E402


def test_init_library_database_does_not_create_music_auralis(tmp_path, monkeypatch):
    # Never the real ~/.auralis: DEFAULT_DB_PATH is fixed at import, so point
    # the default at a temp file everywhere it is read.
    db_path = tmp_path / ".auralis" / "library.db"
    for module in ("auralis.library.constants", "auralis.library.database_engine",
                   "auralis.library.data_dir", "auralis.library.database"):
        monkeypatch.setattr(f"{module}.DEFAULT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    globals_dict: dict = {}

    components._init_library_database(globals_dict)
    try:
        assert not (tmp_path / "Music").exists()
        assert db_path.exists()
    finally:
        globals_dict["library_database"].shutdown()
