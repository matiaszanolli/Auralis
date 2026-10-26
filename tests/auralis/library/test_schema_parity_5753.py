"""A fresh (create_all) database and an upgraded one differ only where accepted (#5753).

Behaviour used to depend on how the database was born: raw-SQL inserts left
`created_at`/`updated_at` NULL on fresh installs (no server default), ids of
deleted tail rows were reissued on fresh databases (no AUTOINCREMENT), and so
on. The timestamp differences are fixed (the mixin declares a server default and
the raw upserts write the columns). Everything else below is a *known*
difference, each with its reason: this test fails on a new one (drift nobody
decided on) and on an accepted one that has since gone (a stale entry that
would re-permit the regression).
"""

import sqlite3

import pytest

from tests.auralis.library.schema_parity_helpers import build_both, schema_differences

_AUTOINCREMENT = (
    "Upgraded tables were created with AUTOINCREMENT; create_all does not emit it for "
    "Integer primary keys. On a fresh database the id of a deleted highest row is reissued, "
    "so a cache keyed on /api/albums/{id}/artwork can show another item (report #5753)."
)
_COUNTER_COLUMN = (
    "Counter/flag columns added by a migration are nullable with a DEFAULT; the model declares "
    "them NOT NULL with a Python-side default. Equivalent through the ORM, different for raw SQL."
)
_EXTRA_UPGRADED_INDEX = (
    "Index created by a migration but not declared on the model, so create_all never builds it."
)

ACCEPTED_DIFFERENCES: dict[str, str] = {
    "table albums: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table artists: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table genres: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table playlists: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table schema_version: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table tracks: AUTOINCREMENT differs (upgraded=True)": _AUTOINCREMENT,
    "table queue_template: only on upgraded databases": (
        "Legacy table from an old release that no model declares; create_all never builds it."
    ),
    "column tracks.fingerprint_hash: only on upgraded databases": (
        "Unused legacy column kept on upgraded databases; no model declares it."
    ),
    "column schema_version.applied_at: default differs": (
        "SchemaVersion is not a TimestampMixin table; the migration SQL gives applied_at a "
        "DEFAULT CURRENT_TIMESTAMP and the model sets it in Python only."
    ),
    "column track_playlist.position: default differs": (
        "Migration v015->v016 gave position DEFAULT 0; the Table() declares no server default."
    ),
    "column artists.total_plays: default differs": _COUNTER_COLUMN,
    "column artists.total_plays: notnull differs": _COUNTER_COLUMN,
    "column playlists.auto_master_enabled: default differs": _COUNTER_COLUMN,
    "column playlists.auto_master_enabled: notnull differs": _COUNTER_COLUMN,
    "column playlists.is_smart: default differs": _COUNTER_COLUMN,
    "column playlists.is_smart: notnull differs": _COUNTER_COLUMN,
    "column playlists.normalize_levels: default differs": _COUNTER_COLUMN,
    "column playlists.normalize_levels: notnull differs": _COUNTER_COLUMN,
    "column tracks.favorite: default differs": _COUNTER_COLUMN,
    "column tracks.favorite: notnull differs": _COUNTER_COLUMN,
    "column tracks.play_count: notnull differs": _COUNTER_COLUMN,
    "column tracks.skip_count: default differs": _COUNTER_COLUMN,
    "column tracks.skip_count: notnull differs": _COUNTER_COLUMN,
    "index artists.idx_artists_name: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index artists.idx_artists_normalized_name: only on upgraded databases": (
        "Same column as ix_artists_normalized_name under the migration's older name."
    ),
    "index artists.ix_artists_normalized_name: only on fresh databases": (
        "Same column as idx_artists_normalized_name under the model's naming."
    ),
    "index genres.idx_genres_name: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index similarity_graph.idx_similarity_graph_track_id: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index tracks.idx_tracks_created_at: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index tracks.idx_tracks_favorite: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index tracks.idx_tracks_play_count: only on upgraded databases": _EXTRA_UPGRADED_INDEX,
    "index tracks.ix_tracks_filepath_key: definition differs (upgraded unique=False)": (
        "REAL DRIFT: the model's filepath_key index is UNIQUE, the migrated one is not, so an "
        "upgraded database can hold two rows with the same key. Fixing it needs a migration; see #6103 "
        "for the related fresh-vs-migrated schema work. Remove this entry when it is unique."
    ),
}


@pytest.fixture(scope="module")
def differences(tmp_path_factory):
    upgraded, fresh = build_both(tmp_path_factory.mktemp("schema_parity"))
    return schema_differences(upgraded, fresh), fresh




def test_only_accepted_differences_remain(differences):
    found, _ = differences

    new = sorted(found - ACCEPTED_DIFFERENCES.keys())
    stale = sorted(ACCEPTED_DIFFERENCES.keys() - found)

    assert not new, "schema drift nobody decided on (fix it, or accept it with a reason):\n  " + "\n  ".join(new)
    assert not stale, "accepted difference no longer exists (remove the entry):\n  " + "\n  ".join(stale)


def test_timestamp_columns_no_longer_differ(differences):
    found, _ = differences

    assert not [k for k in found if k.endswith(("created_at: default differs", "updated_at: default differs"))
                and "schema_version" not in k]


def test_a_raw_insert_that_omits_the_timestamps_still_gets_them(differences):
    _, fresh = differences
    conn = sqlite3.connect(fresh)
    conn.execute("INSERT INTO albums (title) VALUES ('raw')")
    created, updated = conn.execute("SELECT created_at, updated_at FROM albums").fetchone()
    conn.close()

    assert created is not None and updated is not None
