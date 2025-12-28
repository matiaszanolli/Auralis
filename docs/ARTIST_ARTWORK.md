# Artist Artwork Feature

**Status**: ✅ Implemented (Phase 2)
**Version**: 1.2.0-beta.1+

This feature automatically fetches artist images from free, open-source APIs and displays them in the artist detail view.

---

## Overview

The artwork system uses a **multi-source fallback strategy** to find the best available artist image:

1. **MusicBrainz** (Primary) - Free, no API key required
2. **Discogs** (Fallback) - Requires user token
3. **Last.fm** (Fallback) - Requires API key

---

## Quick Start

### 1. Fetch Artwork for All Artists

Run the CLI command to populate artwork for your existing library:

```bash
# Basic usage (MusicBrainz only, no API keys needed)
python -m auralis.cli.fetch_artwork

# With Discogs token for better coverage
python -m auralis.cli.fetch_artwork --discogs-token YOUR_TOKEN

# With both Discogs and Last.fm
python -m auralis.cli.fetch_artwork \
  --discogs-token YOUR_DISCOGS_TOKEN \
  --lastfm-key YOUR_LASTFM_KEY

# Force refresh even if artwork already exists
python -m auralis.cli.fetch_artwork --force-refresh
```

### 2. Get API Credentials (Optional)

**Discogs Token** (recommended for better coverage):
1. Create an account at https://www.discogs.com
2. Go to Settings → Developers
3. Generate a personal access token
4. Use the token with `--discogs-token`

**Last.fm API Key** (optional):
1. Create an account at https://www.last.fm
2. Go to https://www.last.fm/api/account/create
3. Create an API application
4. Use the API key with `--lastfm-key`

---

## Architecture

### Database Schema

Three new columns added to the `artists` table:

| Column | Type | Description |
|--------|------|-------------|
| `artwork_url` | TEXT | External URL to artist image |
| `artwork_source` | TEXT | Source of the image ('musicbrainz', 'discogs', 'lastfm') |
| `artwork_fetched_at` | TIMESTAMP | When the artwork was last fetched |

### Backend Components

**1. ArtworkService** (`auralis/services/artwork_service.py`)
- Fetches artwork from external APIs
- Implements fallback strategy
- Handles rate limiting and timeouts

**2. CLI Command** (`auralis/cli/fetch_artwork.py`)
- Batch processes all artists
- Provides progress and statistics
- Supports force refresh

**3. API Response Models** (`auralis-web/backend/routers/artists.py`)
- `ArtistResponse` includes `artwork_url` and `artwork_source`
- `ArtistDetailResponse` includes artwork fields

### Frontend Components

**ArtistHeader** (`auralis-web/frontend/src/components/library/Details/ArtistHeader.tsx`)
- Displays real artist image when available
- Falls back to letter-based placeholder if no artwork
- Handles image load errors gracefully

---

## API Reference

### Fetch Artist Artwork

The artwork fetching happens in the background via CLI. The web API automatically returns artwork URLs when available.

**Example API Response**:
```json
{
  "id": 184,
  "name": "Dio",
  "album_count": 15,
  "track_count": 150,
  "artwork_url": "https://musicbrainz.org/...",
  "artwork_source": "musicbrainz"
}
```

---

## Troubleshooting

### No artwork found for artists

**Possible causes**:
1. Artist name doesn't match external databases
2. Artist is not in MusicBrainz/Discogs/Last.fm
3. Network connectivity issues

**Solutions**:
- Verify artist names are correct (typos prevent matching)
- Add Discogs/Last.fm credentials for better coverage
- Check network connectivity and firewall settings

### Images not loading in frontend

**Possible causes**:
1. External image URLs are dead/expired
2. CORS issues with image host
3. Network connectivity

**Solutions**:
- Run `python -m auralis.cli.fetch_artwork --force-refresh` to re-fetch
- Check browser console for CORS errors
- Verify image URLs are still valid

### Rate limiting errors

**MusicBrainz**:
- Limit: 1 request per second
- Solution: CLI automatically respects rate limits

**Discogs**:
- Limit: 60 requests per minute with token
- Solution: Use personal access token (higher limits)

**Last.fm**:
- Limit: Varies by plan
- Solution: Use API key for higher limits

---

## Performance

- **CLI fetch**: ~2-5 seconds per artist (includes API calls + database updates)
- **Frontend load**: Instant (URLs are pre-fetched and cached in database)
- **Storage**: Minimal (only stores URLs, not images)

---

## Future Enhancements

Potential improvements for future versions:

1. **Album Artwork** - Extend to fetch album cover art
2. **Local Cache** - Download and cache images locally for offline use
3. **Automatic Updates** - Periodically refresh artwork in background
4. **Manual Upload** - Allow users to upload custom artist images
5. **Image Quality Selection** - Choose between thumbnail/medium/high-res versions

---

## Credits

This feature uses the following free, open-source APIs:

- **MusicBrainz**: https://musicbrainz.org
- **Discogs**: https://www.discogs.com/developers
- **Last.fm**: https://www.last.fm/api

All APIs are used in compliance with their respective terms of service.
