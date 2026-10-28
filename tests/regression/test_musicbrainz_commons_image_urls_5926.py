"""MusicBrainz image relations that name a Commons file page resolve to the image (#5926).

The first host-allowlisted 'image' relation was accepted, and MusicBrainz commonly points at
https://commons.wikimedia.org/wiki/File:X.jpg -- an HTML page -- which then became the artist's
artwork_url and rendered as a broken <img>.
"""

from auralis.services.artwork_sources.musicbrainz import _first_trusted_image


def _rel(url, kind="image"):
    return {"type": kind, "url": {"resource": url}}


def test_a_commons_file_page_becomes_a_special_filepath_url():
    result = _first_trusted_image([_rel("https://commons.wikimedia.org/wiki/File:Some_Band.jpg")])

    assert result["artwork_url"] == "https://commons.wikimedia.org/wiki/Special:FilePath/Some_Band.jpg"
    assert result["source"] == "musicbrainz"


def test_another_commons_page_is_skipped_for_the_next_image():
    result = _first_trusted_image([
        _rel("https://commons.wikimedia.org/wiki/Category:Some_Band"),
        _rel("https://upload.wikimedia.org/wikipedia/commons/a/ab/Some_Band.jpg"),
    ])

    assert result["artwork_url"] == "https://upload.wikimedia.org/wikipedia/commons/a/ab/Some_Band.jpg"


def test_a_direct_image_url_is_untouched():
    url = "https://i.discogs.com/abc/photo.jpeg"

    assert _first_trusted_image([_rel(url)])["artwork_url"] == url


def test_untrusted_hosts_and_non_image_relations_still_yield_nothing():
    assert _first_trusted_image([
        _rel("https://evil.example/wiki/File:x.jpg"),
        _rel("https://commons.wikimedia.org/wiki/File:x.jpg", kind="official homepage"),
    ]) is None
