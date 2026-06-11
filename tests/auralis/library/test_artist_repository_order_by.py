"""Regression tests for ArtistRepository.get_all() count-ordering (#4215).

Previously, order_by='album_count' and order_by='track_count' emitted SQL that
referenced an unjoined subquery alias, causing OperationalError on SQLite.
"""
import pytest

from auralis.library.models import Album, Artist, Track, track_artist


@pytest.fixture
def seeded_artist_repo(session_factory, artist_repository):
    """Seed 3 artists with different album/track counts."""
    session = session_factory()
    try:
        # Artist A: 3 albums, 0 tracks in track_artist
        a = Artist(name="Artist A")
        # Artist B: 1 album, 2 tracks in track_artist
        b = Artist(name="Artist B")
        # Artist C: 0 albums, 0 tracks
        c = Artist(name="Artist C")
        session.add_all([a, b, c])
        session.flush()  # get IDs

        albums_a = [Album(title=f"Album {i}", artist_id=a.id) for i in range(3)]
        album_b = Album(title="B Album", artist_id=b.id)
        session.add_all([*albums_a, album_b])
        session.flush()

        # Tracks for artist B via M2M association table
        t1 = Track(title="B Track 1", filepath="/b1.mp3", duration=180.0)
        t2 = Track(title="B Track 2", filepath="/b2.mp3", duration=200.0)
        session.add_all([t1, t2])
        session.flush()

        session.execute(
            track_artist.insert(),
            [{"track_id": t1.id, "artist_id": b.id}, {"track_id": t2.id, "artist_id": b.id}]
        )
        session.commit()
    finally:
        session.close()

    return artist_repository


class TestArtistRepositoryOrderBy:
    def test_order_by_album_count_no_crash(self, seeded_artist_repo):
        """order_by='album_count' must not raise OperationalError."""
        artists, total = seeded_artist_repo.get_all(order_by='album_count')
        assert total == 3
        assert len(artists) == 3

    def test_order_by_album_count_correct_order(self, seeded_artist_repo):
        """Artist with most albums appears first."""
        artists, _ = seeded_artist_repo.get_all(order_by='album_count')
        assert artists[0].name == "Artist A"   # 3 albums
        assert artists[1].name == "Artist B"   # 1 album
        assert artists[2].name == "Artist C"   # 0 albums

    def test_order_by_track_count_no_crash(self, seeded_artist_repo):
        """order_by='track_count' must not raise OperationalError."""
        artists, total = seeded_artist_repo.get_all(order_by='track_count')
        assert total == 3
        assert len(artists) == 3

    def test_order_by_track_count_correct_order(self, seeded_artist_repo):
        """Artist with most tracks appears first."""
        artists, _ = seeded_artist_repo.get_all(order_by='track_count')
        assert artists[0].name == "Artist B"   # 2 tracks
        # Artist A and C both have 0 tracks — order between them is by DB default

    def test_order_by_name_unaffected(self, seeded_artist_repo):
        """Default name ordering still works correctly."""
        artists, _ = seeded_artist_repo.get_all(order_by='name')
        assert [a.name for a in artists] == ["Artist A", "Artist B", "Artist C"]

    def test_pagination_preserved_with_count_order(self, seeded_artist_repo):
        """limit/offset work correctly on count-ordered queries."""
        page1, total = seeded_artist_repo.get_all(limit=2, offset=0, order_by='album_count')
        page2, _ = seeded_artist_repo.get_all(limit=2, offset=2, order_by='album_count')
        assert total == 3
        assert len(page1) == 2
        assert len(page2) == 1
        all_ids = {a.id for a in page1} | {a.id for a in page2}
        assert len(all_ids) == 3
