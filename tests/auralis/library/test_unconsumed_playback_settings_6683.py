"""
Unconsumed playback settings are gone from the schema (#6683)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``crossfade_enabled``, ``crossfade_duration``, ``gapless_enabled`` and
``replay_gain_enabled`` were editable in Settings but read by no player,
streaming or engine code. Migration v033 -> v034 drops the columns; a
database that still has them (with a saved row) migrates forward and keeps
its other settings.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import UserSettings

DROPPED = {'crossfade_enabled', 'crossfade_duration', 'gapless_enabled', 'replay_gain_enabled'}


def _settings_columns(engine) -> set[str]:
    with engine.connect() as conn:
        return {row[1] for row in conn.execute(text("PRAGMA table_info(user_settings)"))}


def test_model_and_payload_no_longer_carry_the_settings():
    assert not DROPPED & set(UserSettings.__table__.columns.keys())
    assert not DROPPED & set(UserSettings(volume=0.5).to_dict())


def test_fresh_database_has_no_dropped_columns(tmp_path):
    with MigrationManager(str(tmp_path / "fresh.db")) as manager:
        assert manager.initialize_fresh_database()
        assert not DROPPED & _settings_columns(manager.engine)


def test_v033_database_drops_the_columns_and_keeps_its_settings(tmp_path):
    db_path = str(tmp_path / "v33.db")
    with MigrationManager(db_path) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            for ddl in ("crossfade_enabled BOOLEAN", "crossfade_duration FLOAT",
                        "gapless_enabled BOOLEAN", "replay_gain_enabled BOOLEAN"):
                conn.execute(text(f"ALTER TABLE user_settings ADD COLUMN {ddl}"))
            conn.execute(text("UPDATE schema_version SET version = 33"))
        with Session(manager.engine) as session:
            session.add(UserSettings(id=1, volume=0.42))
            session.commit()
        with manager.engine.begin() as conn:
            conn.execute(text(
                "UPDATE user_settings SET crossfade_enabled = 1, crossfade_duration = 3.0, "
                "gapless_enabled = 1, replay_gain_enabled = 0 WHERE id = 1"))
        assert DROPPED <= _settings_columns(manager.engine)

    with MigrationManager(db_path) as manager:
        assert manager.get_current_version() == 33
        assert manager.migrate_to_latest()
        assert not DROPPED & _settings_columns(manager.engine)
        with manager.engine.connect() as conn:
            assert conn.execute(text("SELECT volume FROM user_settings WHERE id = 1")).scalar() == 0.42
