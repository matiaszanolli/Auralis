"""
The app's own scratch directories are not valid scan roots (#6164)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the system temp directory (or ~/.auralis) as a scan root, the library ingested the app's own
chunk and decode WAVs and the watcher kept rescanning them. Only the shared roots are refused:
a subdirectory of the temp dir, where a user may well keep music, stays valid.
"""

import tempfile

import pytest

from security.path_errors import PathValidationError
from security.path_security import validate_user_chosen_directory


def test_the_system_temp_directory_itself_is_refused():
    with pytest.raises(PathValidationError, match="working files"):
        validate_user_chosen_directory(tempfile.gettempdir())


def test_a_subdirectory_of_the_temp_directory_is_still_a_valid_root(tmp_path):
    assert validate_user_chosen_directory(str(tmp_path)) == tmp_path.resolve()


def test_the_app_data_directory_and_anything_in_it_is_refused(tmp_path, monkeypatch):
    data_dir = tmp_path / "appdata"
    (data_dir / "chunks").mkdir(parents=True)
    monkeypatch.setattr("security.path_security.get_data_dir", lambda: data_dir)

    for inside in (data_dir, data_dir / "chunks"):
        with pytest.raises(PathValidationError, match="working files"):
            validate_user_chosen_directory(str(inside))


def test_the_home_directory_stays_valid_and_is_not_mistaken_for_the_data_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    data_dir = home / ".auralis"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr("security.path_security.get_data_dir", lambda: data_dir)

    # A parent of the data directory is a legitimate root; the watcher's event filter already
    # keeps the data directory's own files out of its rescans.
    assert validate_user_chosen_directory(str(home)) == home.resolve()
