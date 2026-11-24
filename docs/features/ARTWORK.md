# Artwork: Album Covers and Artist Images

Auralis has two independent artwork systems with different storage models. Do not conflate them.

| | Album artwork | Artist artwork |
|---|---------------|----------------|
| What is stored | an image **file** in the artwork cache, path in `albums.artwork_path` | an external **URL** in `artists.artwork_url` (plus `artwork_source`, `artwork_fetched_at`) |
| Sources | embedded tag picture, then a cover file in the album folder, then (on request) MusicBrainz Cover Art Archive and iTunes | MusicBrainz, then Discogs, then Last.fm |
| Filled by | the library scan, or `POST /api/albums/{album_id}/artwork/extract` and `.../download` | the `python -m auralis.cli.fetch_artwork` command only |
| Served as | same-origin `GET /api/albums/{album_id}/artwork` | the third-party URL, loaded directly by the browser |

The library tables behind both are described in [subsystems/library.md](../subsystems/library.md).

---

## Album artwork

### Where it comes from

1. **Library scan.** When `TrackRepository.add` creates a track whose album has no artwork yet, it
   calls `ArtworkExtractor.extract_artwork` (`auralis/library/artwork.py`):
   1. the embedded picture in the file (ID3 `APIC`, FLAC picture, MP4 `covr`, generic tags),
      preferring the *front cover* picture type over the first picture
      (`auralis/library/picture_choice.py`);
   2. otherwise a cover file in the track's folder, matched case-insensitively in this order:
      stems `folder`, `cover`, `front`, `albumart`, `albumartsmall`, extensions `jpg`, `jpeg`,
      `png`, `webp` (`auralis/library/folder_artwork.py`). A candidate is read only if it is a
      regular file (symlinks and FIFOs are refused), within `MAX_LOCAL_ARTWORK_BYTES` (16 MiB) and
      starts with image magic bytes.
2. **On demand, from the files:** `POST /api/albums/{album_id}/artwork/extract` runs the same
   extractor over the album's tracks (`AlbumRepository.extract_and_save_artwork`: the first track
   whose file exists and yields art wins) and deletes the superseded file after the new path is
   committed.
3. **On demand, online:** `POST /api/albums/{album_id}/artwork/download` calls
   `ArtworkDownloader.download_artwork` (`auralis-web/backend/services/artwork_downloader.py`), which tries in
   order:
   1. MusicBrainz release search, then the Cover Art Archive front image
      (`auralis-web/backend/services/artwork_providers/musicbrainz.py`);
   2. iTunes Search, requesting the 600x600 variant
      (`auralis-web/backend/services/artwork_providers/itunes.py`).

   The whole chain is bounded by `_ARTWORK_LOOKUP_BUDGET_S` (45 s) and each request by a 15 s total
   / 5 s connect timeout. Search calls are spaced per host (`HostThrottle`; MusicBrainz at
   `MUSICBRAINZ_MIN_INTERVAL_S`). Last.fm and Discogs are **not** consulted for albums.

   No frontend code calls the extract or download routes today; they are REST-only.

All three paths broadcast an `artwork_updated` message to WebSocket clients when they change
something (`extracted`, `downloaded`, `deleted`).

### Where it is cached

`artwork_dir()` in `auralis/library/data_dir.py`: `~/.auralis/artwork/` by default. It follows the
open database (a library at another path keeps its own `artwork/` beside it) and
`AURALIS_DATA_DIR` moves the default root. The extractor and the downloader write the **same**
directory with the same naming, `album_<album_id>_<first 8 hex of md5(content)>.<ext>`, so they
coexist, and it is the only directory the GET route will serve from. The extension is sniffed from
the image's magic bytes (`detect_image_extension` in `auralis/utils/artwork_security.py`), never
taken from a tag's declared MIME type.

Downscaled thumbnails live in `artwork_dir()/thumbnails/` (see below).

### Limits and validation

- **Size caps:** local (embedded or folder) images over 16 MiB are skipped
  (`MAX_LOCAL_ARTWORK_BYTES`); responses from online providers are read through a bounded reader
  capped at 5 MiB (`MAX_ARTWORK_PAYLOAD_BYTES`).
- **Dimension bound:** `bound_artwork_dimensions` downscales any image whose largest side exceeds
  `MAX_ARTWORK_DIMENSION` (2048 px) before it is stored, and refuses images over
  `MAX_ARTWORK_PIXELS` (8192 x 8192) as decompression bombs; a rejected embedded cover falls
  through to the folder cover.
- **Trusted hosts only (downloads):** every URL taken from a provider response, and every redirect
  hop, must be `https` on a host in `TRUSTED_ARTWORK_DOMAINS` (`auralis/utils/artwork_security.py`)
  *before* it is requested (`_get_trusted_artwork`, at most 5 redirects). Search calls refuse
  redirects outright.
- **Query text is data:** artist and album names from tags are sent to MusicBrainz as one quoted,
  escaped phrase (`musicbrainz_phrase`), never as query syntax.

### Atomic writes

Every artwork file is written with `write_bytes_atomic` (`auralis/utils/atomic_write.py`): the bytes
go to a staged file in a private directory beside the target, are fsynced, then `os.replace`d onto
the final name. A file that is already live and being served is therefore never seen truncated,
even when the same content hash is written again. Thumbnails render into a per-writer
`tempfile.mkstemp` file in the thumbnail directory and are promoted with `Path.replace`; a failed
render removes its own temp file, and orphaned temp files are reaped by the thumbnail sweeper.

### Serving: `GET /api/albums/{album_id}/artwork`

(`auralis-web/backend/routers/artwork.py`.)

- The stored path is resolved and must lie inside `artwork_dir()`; otherwise 403, and a missing
  file is 404. The check runs before any existence probe.
- Content type comes from the file extension, falling back to magic bytes.
- `?size=<px>` (16 to 2048) returns a downscaled copy. The size snaps **up** to one of the
  buckets 64, 128, 256, 512, 1024, so at most five variants exist per image. The cache key
  includes a hash of the source path and its mtime and size, so replacing the image never serves a
  stale thumbnail; extract, delete and download purge the superseded generation's thumbnails.
  Renders for one key are serialised, and the thumbnail directory is pruned to
  `THUMBNAIL_CACHE_MAX_BYTES` (128 MiB) by `auralis-web/backend/core/thumbnail_sweep.py`. A
  failed render falls back to the original; a decompression bomb is a 404.
- `ETag` is built from the served file's mtime and size, with `Cache-Control: public, no-cache`:
  clients always revalidate and get a 304 when unchanged.
- `DELETE` is idempotent: it returns success when the album has no artwork, and 404 only for an
  unknown album.

---

## Artist artwork

### How to fetch it

Artist images are fetched by a command-line tool, not by the backend. The web API only *returns*
the stored URL in `ArtistResponse` / `ArtistDetailResponse`
(`auralis-web/backend/routers/artists_models.py`).

```bash
# MusicBrainz only, no credentials
python -m auralis.cli.fetch_artwork

# Add Discogs and/or Last.fm (preferred: environment variables)
export AURALIS_DISCOGS_TOKEN=...      # Discogs personal access token
export AURALIS_LASTFM_KEY=...         # Last.fm API key
python -m auralis.cli.fetch_artwork

# Refetch artists that already have artwork; use another library file
python -m auralis.cli.fetch_artwork --force-refresh
python -m auralis.cli.fetch_artwork --library-path /path/to/library.db
```

`--discogs-token` and `--lastfm-key` exist but are discouraged: an argument is visible in `ps` and
shell history, and the environment variables take precedence. The tool opens the library through
`LibraryDatabase` (so it migrates if needed), walks `ArtistRepository.get_all_artists()`, skips
artists that already have a URL unless `--force-refresh`, and stores the result with
`ArtistRepository.update_artwork`. It prints totals for found, not found, skipped and errors.

Credentials: a Discogs token comes from Settings, Developers on discogs.com; a Last.fm key from
last.fm/api/account/create.

### Sources (`auralis/services/artwork_service.py`)

`ArtworkService.fetch_artist_artwork(name)` tries, in order, and returns
`{'artwork_url': ..., 'source': ...}` for the first hit:

1. **MusicBrainz**, always on: search the artist, fetch its URL relations, take the first `image`
   relation whose URL is trusted. A Wikimedia Commons *file page* is rewritten to its
   `Special:FilePath` form so the URL serves an image rather than HTML
   (`auralis/services/artwork_sources/musicbrainz.py`).
2. **Discogs**, only with a token: first search result's `cover_image`, else `thumb`. The token is
   sent as an `Authorization` header that is not carried across redirects.
3. **Last.fm**, only with a key: the largest image in `artist.getinfo`.

The source name is stored in `artwork_source` (`musicbrainz`, `discogs`, `lastfm`).

All provider calls go through `fetch_metadata_json` (`auralis/services/artwork_sources/_common.py`):
per-host spacing (MusicBrainz `MUSICBRAINZ_MIN_INTERVAL_S`, Discogs 1 s, Last.fm 0.25 s), no
redirects, bounded JSON (5 MiB), and on HTTP 429/503 the host is paused for `Retry-After` (default
10 s, capped at 120 s) with a WARNING. Every returned URL must pass `validate_artwork_url` (https
on a `TRUSTED_ARTWORK_DOMAINS` host) or it is dropped.

### Schema

Three nullable columns on `artists`: `artwork_url` (text), `artwork_source` (string),
`artwork_fetched_at` (datetime). Stored: a URL, not an image. Nothing is downloaded or cached
locally for artists.

### Display and the CSP allowlist

`ArtistHeader` (`auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx`) renders
`artist.artworkUrl` as an `<img>` and falls back to a letter placeholder when there is no URL or
the image fails to load.

`artwork_url` is the one artwork field passed to clients as an **absolute external URL** (album and
track artwork are rewritten to `/api/.../artwork`). The browser may load these hosts only because
of the `img-src` allowlist `_ARTIST_ARTWORK_IMG_HOSTS` in
`auralis-web/backend/config/middleware/security_headers.py`: Last.fm's CDNs, `i.discogs.com`,
`img.discogs.com`, `upload.wikimedia.org` and `commons.wikimedia.org`. **A new artist-artwork
source needs its CDN host added in three places:** `TRUSTED_ARTWORK_DOMAINS`, that allowlist, and
the provider module. Otherwise the image is rejected or silently blocked and the UI shows the
placeholder. Do not relax `img-src` to `https:`. The frontend's `withArtworkSize()` only adds
`?size=` to `/api/` paths, so it leaves these URLs alone.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| CLI reports "not found" for many artists | name does not match MusicBrainz; or an image relation points at a host outside `TRUSTED_ARTWORK_DOMAINS` (logged at WARNING as an untrusted URL) |
| CLI log shows "pausing requests to it" | the provider answered 429/503; the run continues after the pause |
| artist image missing in the app but the URL is stored | host not in `_ARTIST_ARTWORK_IMG_HOSTS`, or the image was removed upstream; rerun with `--force-refresh` to look again |
| album art 403 | stored `artwork_path` lies outside `artwork_dir()` (for example after moving the library directory) |
| album art 404 after a rescan | the file in `artwork/` was deleted; call the extract route again |
| a thumbnail looks wrong | thumbnails are keyed on the source file's path, mtime and size, so a changed image gets a new key; delete the files in `artwork/thumbnails/` to force a re-render |

---

## Related

[subsystems/library.md](../subsystems/library.md) ·
[subsystems/backend-api.md](../subsystems/backend-api.md)
