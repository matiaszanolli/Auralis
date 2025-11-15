/**
 * MSW Request Handlers - API mocking for integration tests
 *
 * Comprehensive mocks for all Auralis API endpoints including:
 * - Player control (play, pause, seek, queue, volume)
 * - Library management (tracks, albums, artists, playlists)
 * - Enhancement/processing
 * - Metadata editing
 * - Artwork management
 * - WebSocket real-time updates
 */

import { http, HttpResponse, delay } from 'msw';

// Base URLs - support both absolute and relative paths
const API_BASE = 'http://localhost:8765/api';
const API_RELATIVE = '/api';

// Mock data imports
import { mockTracks, mockAlbums, mockArtists, mockPlaylists, mockPlayerState } from './mockData';

export const handlers = [
  // ============================================================
  // PLAYER ENDPOINTS
  // ============================================================

  // GET /api/player/state - Get current player state
  http.get(`${API_BASE}/player/state`, async () => {
    await delay(50); // Simulate network latency
    return HttpResponse.json(mockPlayerState);
  }),

  // POST /api/player/play - Play track
  http.post(`${API_BASE}/player/play`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: (body as any).track_id
    });
  }),

  // POST /api/player/pause - Pause playback
  http.post(`${API_BASE}/player/pause`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/resume - Resume playback
  http.post(`${API_BASE}/player/resume`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/seek - Seek to position
  http.post(`${API_BASE}/player/seek`, async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      position: (body as any).position
    });
  }),

  // POST /api/player/volume - Set volume
  http.post(`${API_BASE}/player/volume`, async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      volume: (body as any).volume
    });
  }),

  // POST /api/player/next - Next track
  http.post(`${API_BASE}/player/next`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/previous - Previous track
  http.post(`${API_BASE}/player/previous`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/shuffle - Toggle shuffle
  http.post(`${API_BASE}/player/shuffle`, async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      shuffle: (body as any).enabled
    });
  }),

  // POST /api/player/repeat - Set repeat mode
  http.post(`${API_BASE}/player/repeat`, async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      repeat_mode: (body as any).mode
    });
  }),

  // GET /api/player/queue - Get queue
  http.get(`${API_BASE}/player/queue`, async () => {
    await delay(50);
    return HttpResponse.json({
      queue: mockTracks.slice(0, 5)
    });
  }),

  // POST /api/player/queue - Add to queue
  http.post(`${API_BASE}/player/queue`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: (body as any).track_id
    });
  }),

  // DELETE /api/player/queue/:index - Remove from queue
  http.delete(`${API_BASE}/player/queue/:index`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // ============================================================
  // LIBRARY ENDPOINTS
  // ============================================================

  // GET /api/library/tracks - Get tracks with pagination
  http.get(`${API_BASE}/library/tracks`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');
    const search = url.searchParams.get('search') || '';

    await delay(100);

    let filteredTracks = mockTracks;

    // Apply search filter
    if (search) {
      filteredTracks = mockTracks.filter(t =>
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        t.artist.toLowerCase().includes(search.toLowerCase()) ||
        t.album.toLowerCase().includes(search.toLowerCase())
      );
    }

    const paginatedTracks = filteredTracks.slice(offset, offset + limit);
    return HttpResponse.json({
      tracks: paginatedTracks,
      total: filteredTracks.length,
      has_more: offset + limit < filteredTracks.length
    });
  }),

  // GET /api/library/tracks/:id - Get single track
  http.get(`${API_BASE}/library/tracks/:id`, async ({ params }) => {
    await delay(50);
    const track = mockTracks.find(t => t.id === parseInt(params.id as string));
    if (track) {
      return HttpResponse.json(track);
    }
    return HttpResponse.json({ error: 'Track not found' }, { status: 404 });
  }),

  // PUT /api/library/tracks/:id - Update track metadata
  http.put(`${API_BASE}/library/tracks/:id`, async ({ request, params }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: parseInt(params.id as string),
      updated: body
    });
  }),

  // POST /api/library/tracks/:id/favorite - Toggle favorite
  http.post(`${API_BASE}/library/tracks/:id/favorite`, async ({ params }) => {
    await delay(50);
    const track = mockTracks.find(t => t.id === parseInt(params.id as string));
    return HttpResponse.json({
      success: true,
      favorite: !track?.favorite
    });
  }),

  // GET /api/library/albums - Get albums
  http.get(`${API_BASE}/library/albums`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');

    await delay(100);

    const paginatedAlbums = mockAlbums.slice(offset, offset + limit);
    return HttpResponse.json({
      albums: paginatedAlbums,
      total: mockAlbums.length,
      has_more: offset + limit < mockAlbums.length
    });
  }),

  // GET /api/library/albums/:id - Get album details
  http.get(`${API_BASE}/library/albums/:id`, async ({ params }) => {
    await delay(50);
    const album = mockAlbums.find(a => a.id === parseInt(params.id as string));
    if (album) {
      return HttpResponse.json(album);
    }
    return HttpResponse.json({ error: 'Album not found' }, { status: 404 });
  }),

  // GET /api/library/albums/:id/tracks - Get album tracks
  http.get(`${API_BASE}/library/albums/:id/tracks`, async ({ params }) => {
    await delay(100);
    const albumId = parseInt(params.id as string);
    const album = mockAlbums.find(a => a.id === albumId);
    const albumTracks = mockTracks.filter(t => t.album === album?.title);
    return HttpResponse.json({ tracks: albumTracks });
  }),

  // GET /api/library/artists - Get artists
  http.get(`${API_BASE}/library/artists`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');

    await delay(100);

    const paginatedArtists = mockArtists.slice(offset, offset + limit);
    return HttpResponse.json({
      artists: paginatedArtists,
      total: mockArtists.length,
      has_more: offset + limit < mockArtists.length
    });
  }),

  // GET /api/library/artists/:id - Get artist details
  http.get(`${API_BASE}/library/artists/:id`, async ({ params }) => {
    await delay(50);
    const artist = mockArtists.find(a => a.id === parseInt(params.id as string));
    if (artist) {
      return HttpResponse.json(artist);
    }
    return HttpResponse.json({ error: 'Artist not found' }, { status: 404 });
  }),

  // GET /api/library/artists/:id/tracks - Get artist tracks
  http.get(`${API_BASE}/library/artists/:id/tracks`, async ({ params }) => {
    await delay(100);
    const artistId = parseInt(params.id as string);
    const artist = mockArtists.find(a => a.id === artistId);
    const artistTracks = mockTracks.filter(t => t.artist === artist?.name);
    return HttpResponse.json({ tracks: artistTracks });
  }),

  // POST /api/library/scan - Scan library
  http.post(`${API_BASE}/library/scan`, async () => {
    await delay(200);
    return HttpResponse.json({
      success: true,
      scanned: 100,
      added: 10
    });
  }),

  // ============================================================
  // PLAYLIST ENDPOINTS
  // ============================================================

  // GET /api/playlists - Get all playlists
  http.get(`${API_BASE}/playlists`, async () => {
    await delay(100);
    return HttpResponse.json({ playlists: mockPlaylists });
  }),

  // POST /api/playlists - Create playlist
  http.post(`${API_BASE}/playlists`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      playlist: {
        id: mockPlaylists.length + 1,
        name: (body as any).name,
        track_count: 0,
        created_at: new Date().toISOString()
      }
    });
  }),

  // GET /api/playlists/:id - Get playlist details
  http.get(`${API_BASE}/playlists/:id`, async ({ params }) => {
    await delay(50);
    const playlistId = parseInt(params.id as string);
    const playlist = mockPlaylists.find(p => p.id === playlistId);
    if (playlist) {
      return HttpResponse.json({
        ...playlist,
        total_duration: 1800,
        is_smart: false,
        smart_criteria: null,
        auto_master_enabled: false,
        mastering_profile: 'adaptive',
        normalize_levels: false,
        updated_at: new Date().toISOString(),
      });
    }
    return HttpResponse.json({ error: 'Playlist not found', detail: 'Playlist does not exist' }, { status: 404 });
  }),

  // PUT /api/playlists/:id - Update playlist (rename, description)
  http.put(`${API_BASE}/playlists/:id`, async ({ request, params }) => {
    const body = await request.json();
    await delay(100);
    const playlistId = parseInt(params.id as string);
    return HttpResponse.json({
      success: true,
      playlist: {
        id: playlistId,
        name: (body as any).name || 'Updated Playlist',
        description: (body as any).description || '',
        track_count: 10,
        updated_at: new Date().toISOString(),
      }
    });
  }),

  // DELETE /api/playlists/:id - Delete playlist
  http.delete(`${API_BASE}/playlists/:id`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // GET /api/playlists/:id/tracks - Get playlist tracks
  http.get(`${API_BASE}/playlists/:id/tracks`, async ({ params }) => {
    await delay(100);
    const playlistId = parseInt(params.id as string);
    // Return different tracks based on playlist ID for testing
    const tracks = playlistId === 1 ? mockTracks.slice(0, 10) : mockTracks.slice(10, 20);
    return HttpResponse.json({ tracks });
  }),

  // POST /api/playlists/:id/tracks - Add track(s) to playlist
  http.post(`${API_BASE}/playlists/:id/tracks`, async ({ request }) => {
    const body = await request.json();
    await delay(100);

    // Handle both single track_id and multiple track_ids
    const trackId = (body as any).track_id;
    const trackIds = (body as any).track_ids;

    if (trackIds && Array.isArray(trackIds)) {
      return HttpResponse.json({
        success: true,
        added_count: trackIds.length
      });
    } else if (trackId) {
      return HttpResponse.json({
        success: true,
        track_id: trackId
      });
    }

    return HttpResponse.json({ error: 'Invalid request' }, { status: 400 });
  }),

  // DELETE /api/playlists/:playlistId/tracks/:trackId - Remove track from playlist
  http.delete(`${API_BASE}/playlists/:playlistId/tracks/:trackId`, async ({ params }) => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // DELETE /api/playlists/:id/tracks - Clear all tracks from playlist
  http.delete(`${API_BASE}/playlists/:id/tracks`, async () => {
    await delay(100);
    return HttpResponse.json({ success: true });
  }),

  // PUT /api/playlists/:id/reorder - Reorder tracks in playlist
  http.put(`${API_BASE}/playlists/:id/reorder`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      new_order: (body as any).track_ids || []
    });
  }),

  // ============================================================
  // ENHANCEMENT ENDPOINTS
  // ============================================================

  // GET /api/enhancement/state - Get enhancement state
  http.get(`${API_BASE}/enhancement/state`, async () => {
    await delay(50);
    return HttpResponse.json({
      enabled: false,
      preset: 'adaptive',
      presets: ['adaptive', 'gentle', 'warm', 'bright', 'punchy']
    });
  }),

  // POST /api/enhancement/toggle - Toggle enhancement
  http.post(`${API_BASE}/enhancement/toggle`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      enabled: (body as any).enabled
    });
  }),

  // POST /api/enhancement/preset - Set preset
  http.post(`${API_BASE}/enhancement/preset`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      preset: (body as any).preset
    });
  }),

  // POST /api/player/enhancement/toggle - Toggle enhancement (EnhancementContext API)
  http.post(`${API_BASE}/player/enhancement/toggle`, async ({ request }) => {
    const url = new URL(request.url);
    const enabled = url.searchParams.get('enabled') === 'true';
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: enabled,
        preset: 'adaptive',
        intensity: 1.0
      }
    });
  }),

  // POST /api/player/enhancement/preset - Set preset (EnhancementContext API)
  http.post(`${API_BASE}/player/enhancement/preset`, async ({ request }) => {
    const url = new URL(request.url);
    const preset = url.searchParams.get('preset') || 'adaptive';
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: true,
        preset: preset,
        intensity: 1.0
      }
    });
  }),

  // POST /api/player/enhancement/intensity - Set intensity (EnhancementContext API)
  http.post(`${API_BASE}/player/enhancement/intensity`, async ({ request }) => {
    const url = new URL(request.url);
    const intensity = parseFloat(url.searchParams.get('intensity') || '1.0');
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: true,
        preset: 'adaptive',
        intensity: intensity
      }
    });
  }),

  // GET /api/processing/parameters - Get current processing parameters
  http.get(`${API_BASE}/processing/parameters`, async () => {
    await delay(100);
    return HttpResponse.json({
      spectral_balance: 0.6,
      dynamic_range: 0.7,
      energy_level: 0.5,
      target_lufs: -14.0,
      peak_target_db: -1.0,
      bass_boost: 2.5,
      air_boost: 1.8,
      compression_amount: 0.4,
      expansion_amount: 0.2,
      stereo_width: 0.8
    });
  }),

  // ============================================================
  // METADATA ENDPOINTS
  // ============================================================

  // GET /api/metadata/tracks/:id/fields - Get editable fields
  http.get(`${API_BASE}/metadata/tracks/:id/fields`, async ({ params }) => {
    await delay(100);
    const trackId = parseInt(params.id as string);
    const track = mockTracks.find(t => t.id === trackId);

    if (!track) {
      return HttpResponse.json(
        { error: 'Track not found' },
        { status: 404 }
      );
    }

    return HttpResponse.json({
      track_id: trackId,
      filepath: track.file_path || `/music/${track.title}.flac`,
      format: track.format || 'FLAC',
      editable_fields: [
        'title', 'artist', 'album', 'albumartist', 'year', 'genre',
        'track', 'disc', 'comment', 'bpm', 'composer', 'publisher',
        'lyrics', 'copyright'
      ],
      current_metadata: {
        title: track.title,
        artist: track.artist,
        album: track.album,
        year: track.year || 2020,
        genre: track.genre || 'Rock',
        track: 1,
        disc: 1
      }
    });
  }),

  // GET /api/metadata/tracks/:id - Get track metadata
  http.get(`${API_BASE}/metadata/tracks/:id`, async ({ params }) => {
    await delay(100);
    const trackId = parseInt(params.id as string);
    const track = mockTracks.find(t => t.id === trackId);

    if (!track) {
      return HttpResponse.json(
        { error: 'Track not found' },
        { status: 404 }
      );
    }

    return HttpResponse.json({
      track_id: trackId,
      filepath: track.file_path || `/music/${track.title}.flac`,
      format: track.format || 'FLAC',
      metadata: {
        title: track.title,
        artist: track.artist,
        album: track.album,
        year: track.year || 2020,
        genre: track.genre || 'Rock',
        track: 1,
        disc: 1,
        comment: '',
        composer: '',
        publisher: '',
        lyrics: '',
        copyright: ''
      }
    });
  }),

  // PUT /api/metadata/tracks/:id - Update track metadata
  http.put(`${API_BASE}/metadata/tracks/:id`, async ({ params, request }) => {
    await delay(150);
    const trackId = parseInt(params.id as string);
    const body = await request.json();
    const track = mockTracks.find(t => t.id === trackId);

    if (!track) {
      return HttpResponse.json(
        { error: 'Track not found' },
        { status: 404 }
      );
    }

    // Validate metadata
    const metadata = body as any;
    if (metadata.title && metadata.title.length > 200) {
      return HttpResponse.json(
        { detail: 'Title must be 200 characters or less' },
        { status: 400 }
      );
    }
    if (metadata.artist && metadata.artist.length > 100) {
      return HttpResponse.json(
        { detail: 'Artist must be 100 characters or less' },
        { status: 400 }
      );
    }
    if (metadata.album && metadata.album.length > 100) {
      return HttpResponse.json(
        { detail: 'Album must be 100 characters or less' },
        { status: 400 }
      );
    }
    if (metadata.year && (metadata.year < 1900 || metadata.year > 2099)) {
      return HttpResponse.json(
        { detail: 'Year must be between 1900 and 2099' },
        { status: 400 }
      );
    }

    // Update mock track
    Object.assign(track, metadata);

    return HttpResponse.json({
      track_id: trackId,
      success: true,
      updated_fields: Object.keys(metadata),
      metadata: {
        ...metadata,
        title: metadata.title || track.title,
        artist: metadata.artist || track.artist,
        album: metadata.album || track.album
      }
    });
  }),

  // POST /api/metadata/batch - Batch update metadata
  http.post(`${API_BASE}/metadata/batch`, async ({ request }) => {
    await delay(200);
    const body = await request.json();
    const { updates } = body as any;

    const results = updates.map((update: any) => {
      const track = mockTracks.find(t => t.id === update.track_id);
      if (!track) {
        return {
          track_id: update.track_id,
          success: false,
          error: 'Track not found'
        };
      }

      // Update track
      Object.assign(track, update.metadata);

      return {
        track_id: update.track_id,
        success: true,
        updates: update.metadata
      };
    });

    const successful = results.filter((r: any) => r.success).length;
    const failed = results.length - successful;

    return HttpResponse.json({
      success: true,
      total: results.length,
      successful,
      failed,
      results
    });
  }),

  // ============================================================
  // ARTWORK ENDPOINTS
  // ============================================================

  // GET /api/albums/:id/artwork - Get album artwork
  http.get(`${API_BASE}/albums/:id/artwork`, async ({ params }) => {
    await delay(100);
    const albumId = parseInt(params.id as string);

    // Return mock image data (empty ArrayBuffer for testing)
    const mockImageData = new ArrayBuffer(100);
    return HttpResponse.arrayBuffer(mockImageData, {
      headers: {
        'Content-Type': 'image/jpeg',
        'Cache-Control': 'public, max-age=31536000'
      }
    });
  }),

  // POST /api/albums/:id/artwork/extract - Extract artwork from tracks
  http.post(`${API_BASE}/albums/:id/artwork/extract`, async ({ params }) => {
    await delay(150);
    const albumId = parseInt(params.id as string);

    return HttpResponse.json({
      message: 'Artwork extracted successfully',
      artwork_path: `/artwork/album_${albumId}.jpg`,
      album_id: albumId
    });
  }),

  // DELETE /api/albums/:id/artwork - Delete album artwork
  http.delete(`${API_BASE}/albums/:id/artwork`, async ({ params }) => {
    await delay(100);
    const albumId = parseInt(params.id as string);

    return HttpResponse.json({
      message: 'Artwork deleted successfully',
      album_id: albumId
    });
  }),

  // POST /api/albums/:id/artwork/download - Download artwork from online sources
  http.post(`${API_BASE}/albums/:id/artwork/download`, async ({ params }) => {
    await delay(200);
    const albumId = parseInt(params.id as string);

    return HttpResponse.json({
      message: 'Artwork downloaded successfully',
      artwork_path: `/artwork/album_${albumId}_downloaded.jpg`,
      album_id: albumId,
      artist: 'Mock Artist',
      album: 'Mock Album'
    });
  }),

  // Legacy artwork endpoint
  // GET /api/artwork/:id - Get artwork
  http.get(`${API_BASE}/artwork/:id`, async ({ params }) => {
    await delay(100);
    // Return a simple data URL for testing
    return HttpResponse.json({
      artwork_url: `data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100" fill="purple"/></svg>`
    });
  }),

  // ============================================================
  // SYSTEM ENDPOINTS
  // ============================================================

  // GET /api/health - Health check
  http.get(`${API_BASE}/health`, async () => {
    await delay(10);
    return HttpResponse.json({
      status: 'healthy',
      timestamp: new Date().toISOString()
    });
  }),

  // GET /api/version - Get version
  http.get(`${API_BASE}/version`, async () => {
    await delay(10);
    return HttpResponse.json({
      version: '1.0.0-beta.10',
      build: 'test'
    });
  }),

  // ============================================================
  // ERROR HANDLERS (for error testing)
  // ============================================================

  // 400 Bad Request
  http.get(`${API_BASE}/test/bad-request`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Bad Request', detail: 'Invalid parameters' },
      { status: 400 }
    );
  }),

  // 401 Unauthorized
  http.get(`${API_BASE}/test/unauthorized`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Unauthorized', detail: 'Authentication required' },
      { status: 401 }
    );
  }),

  // 403 Forbidden
  http.get(`${API_BASE}/test/forbidden`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Forbidden', detail: 'Access denied' },
      { status: 403 }
    );
  }),

  // 404 Not Found
  http.get(`${API_BASE}/test/not-found`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Not Found', detail: 'Resource does not exist' },
      { status: 404 }
    );
  }),

  // 500 Internal Server Error
  http.get(`${API_BASE}/test/server-error`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Internal Server Error', detail: 'An unexpected error occurred' },
      { status: 500 }
    );
  }),

  // 503 Service Unavailable
  http.get(`${API_BASE}/test/service-unavailable`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Service Unavailable', detail: 'Server is temporarily unavailable' },
      { status: 503 }
    );
  }),

  // Network timeout
  http.get(`${API_BASE}/test/timeout`, async () => {
    await delay(30000); // 30s timeout
    return HttpResponse.json({ data: 'too late' });
  }),

  // ============================================================
  // RELATIVE PATH HANDLERS (for tests using relative URLs)
  // ============================================================

  // Player endpoints - relative paths
  http.get(`${API_RELATIVE}/player/state`, async () => {
    await delay(50);
    return HttpResponse.json(mockPlayerState);
  }),

  http.get(`${API_RELATIVE}/player/status`, async () => {
    await delay(50);
    return HttpResponse.json(mockPlayerState);
  }),

  http.post(`${API_RELATIVE}/player/play`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: (body as any).track_id
    });
  }),

  http.post(`${API_RELATIVE}/player/pause`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  http.post(`${API_RELATIVE}/player/queue/add-track`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: (body as any).track_id
    });
  }),

  // Library endpoints - relative paths
  http.get(`${API_RELATIVE}/library/tracks`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');
    const search = url.searchParams.get('search') || '';

    await delay(100);

    let filteredTracks = mockTracks;

    // Apply search filter
    if (search) {
      filteredTracks = mockTracks.filter(t =>
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        t.artist.toLowerCase().includes(search.toLowerCase()) ||
        t.album.toLowerCase().includes(search.toLowerCase())
      );
    }

    const paginatedTracks = filteredTracks.slice(offset, offset + limit);
    return HttpResponse.json({
      tracks: paginatedTracks,
      total: filteredTracks.length,
      has_more: offset + limit < filteredTracks.length
    });
  }),

  http.get(`${API_RELATIVE}/library/tracks/favorites`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');

    await delay(100);

    const favoriteTracks = mockTracks.filter(t => t.favorite);
    const paginatedTracks = favoriteTracks.slice(offset, offset + limit);
    return HttpResponse.json({
      tracks: paginatedTracks,
      total: favoriteTracks.length,
      has_more: offset + limit < favoriteTracks.length
    });
  }),

  http.get(`${API_RELATIVE}/library/tracks/:id`, async ({ params }) => {
    await delay(50);
    const track = mockTracks.find(t => t.id === parseInt(params.id as string));
    if (track) {
      return HttpResponse.json(track);
    }
    return HttpResponse.json({ error: 'Track not found' }, { status: 404 });
  }),

  http.post(`${API_RELATIVE}/library/tracks/:id/favorite`, async ({ params }) => {
    await delay(50);
    const track = mockTracks.find(t => t.id === parseInt(params.id as string));
    return HttpResponse.json({
      success: true,
      favorite: !track?.favorite
    });
  }),

  http.delete(`${API_RELATIVE}/library/tracks/:id/favorite`, async ({ params }) => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  http.get(`${API_RELATIVE}/albums`, async ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');

    await delay(100);

    const paginatedAlbums = mockAlbums.slice(offset, offset + limit);
    return HttpResponse.json({
      albums: paginatedAlbums,
      total: mockAlbums.length,
      has_more: offset + limit < mockAlbums.length
    });
  }),

  http.post(`${API_RELATIVE}/library/scan`, async () => {
    await delay(200);
    return HttpResponse.json({
      success: true,
      files_added: 10
    });
  }),

  // Playlist endpoints - relative paths
  http.get(`${API_RELATIVE}/playlists`, async () => {
    await delay(100);
    return HttpResponse.json({ playlists: mockPlaylists, total: mockPlaylists.length });
  }),

  http.get(`${API_RELATIVE}/playlists/:id`, async ({ params }) => {
    await delay(50);
    const playlistId = parseInt(params.id as string);
    const playlist = mockPlaylists.find(p => p.id === playlistId);
    if (playlist) {
      return HttpResponse.json({
        ...playlist,
        total_duration: 1800,
        is_smart: false,
        smart_criteria: null,
        auto_master_enabled: false,
        mastering_profile: 'adaptive',
        normalize_levels: false,
        updated_at: new Date().toISOString(),
      });
    }
    return HttpResponse.json({ error: 'Playlist not found' }, { status: 404 });
  }),

  http.post(`${API_RELATIVE}/playlists`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      playlist: {
        id: mockPlaylists.length + 1,
        name: (body as any).name,
        description: (body as any).description || '',
        track_count: 0,
        created_at: new Date().toISOString(),
        is_smart: false,
        smart_criteria: null,
        auto_master_enabled: false,
        mastering_profile: 'adaptive',
        normalize_levels: false,
        total_duration: 0,
        updated_at: new Date().toISOString(),
      }
    });
  }),

  http.put(`${API_RELATIVE}/playlists/:id`, async ({ request, params }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({ success: true });
  }),

  http.delete(`${API_RELATIVE}/playlists/:id`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  http.get(`${API_RELATIVE}/playlists/:id/tracks`, async ({ params }) => {
    await delay(100);
    const playlistId = parseInt(params.id as string);
    const tracks = playlistId === 1 ? mockTracks.slice(0, 10) : mockTracks.slice(10, 20);
    return HttpResponse.json({ tracks });
  }),

  http.post(`${API_RELATIVE}/playlists/:id/tracks`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    const trackId = (body as any).track_id;
    const trackIds = (body as any).track_ids;

    if (trackIds && Array.isArray(trackIds)) {
      return HttpResponse.json({ success: true, added_count: trackIds.length });
    } else if (trackId) {
      return HttpResponse.json({ success: true, track_id: trackId });
    }
    return HttpResponse.json({ error: 'Invalid request' }, { status: 400 });
  }),

  http.delete(`${API_RELATIVE}/playlists/:playlistId/tracks/:trackId`, async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  http.delete(`${API_RELATIVE}/playlists/:id/tracks`, async () => {
    await delay(100);
    return HttpResponse.json({ success: true });
  }),

  http.put(`${API_RELATIVE}/playlists/:id/reorder`, async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      new_order: (body as any).track_ids || []
    });
  }),

  // Connection refused (network error)
  http.get(`${API_BASE}/test/connection-refused`, () => {
    return HttpResponse.error();
  }),

  // DNS failure (network error)
  http.get(`${API_BASE}/test/dns-failure`, () => {
    return HttpResponse.error();
  }),

  // Invalid JSON
  http.get(`${API_BASE}/test/invalid-json`, () => {
    return new HttpResponse('This is not JSON', {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }),

  // Missing required fields
  http.get(`${API_BASE}/test/missing-fields`, async () => {
    await delay(50);
    return HttpResponse.json({
      // Missing required 'tracks' field
      total: 100,
    });
  }),

  // Type mismatch
  http.get(`${API_BASE}/test/type-mismatch`, async () => {
    await delay(50);
    return HttpResponse.json({
      tracks: 'should be array', // Wrong type
      total: 'should be number', // Wrong type
    });
  }),

  // Empty response body
  http.get(`${API_BASE}/test/empty-body`, () => {
    return new HttpResponse(null, { status: 200 });
  }),

  // Null fields
  http.get(`${API_BASE}/test/null-fields`, async () => {
    await delay(50);
    return HttpResponse.json({
      tracks: null,
      total: null,
      has_more: null,
    });
  }),

  // Undefined properties
  http.get(`${API_BASE}/test/undefined-props`, async () => {
    await delay(50);
    return HttpResponse.json({
      some_field: 'value',
      // tracks, total, etc. are undefined
    });
  }),

  // Rate limiting - 429 Too Many Requests
  http.get(`${API_BASE}/test/rate-limit`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Too Many Requests', detail: 'Rate limit exceeded' },
      {
        status: 429,
        headers: {
          'Retry-After': '60',
        }
      }
    );
  }),

  // ============================================================
  // STREAMING / MSE ENDPOINTS
  // ============================================================

  // GET /api/stream/:track_id/metadata - Get stream metadata for MSE initialization
  http.get(`${API_BASE}/stream/:track_id/metadata`, async ({ params }) => {
    const trackId = parseInt(params.track_id as string);
    const track = mockTracks.find(t => t.id === trackId);

    if (!track) {
      return HttpResponse.json(
        { error: 'Track not found', detail: `Track ${trackId} not found` },
        { status: 404 }
      );
    }

    await delay(100);

    // Calculate metadata based on track duration
    const duration = track.duration || 180; // Default 3 minutes
    const chunkDuration = 10; // 10s chunks
    const chunkInterval = 10; // 10s intervals
    const totalChunks = Math.ceil(duration / chunkInterval);

    return HttpResponse.json({
      track_id: trackId,
      duration: duration,
      sample_rate: 44100,
      channels: 2,
      chunk_duration: chunkDuration,
      chunk_interval: chunkInterval,
      total_chunks: totalChunks,
      mime_type: 'audio/webm',
      codecs: 'opus',
      format_version: 'unified-v1.0'
    });
  }),

  // GET /api/stream/:track_id/chunk/:chunk_idx - Get WebM/Opus chunk
  http.get(`${API_BASE}/stream/:track_id/chunk/:chunk_idx`, async ({ params, request }) => {
    const trackId = parseInt(params.track_id as string);
    const chunkIdx = parseInt(params.chunk_idx as string);
    const url = new URL(request.url);
    const preset = url.searchParams.get('preset') || 'adaptive';
    const enhanced = url.searchParams.get('enhanced') !== 'false';

    const track = mockTracks.find(t => t.id === trackId);

    if (!track) {
      return HttpResponse.json(
        { error: 'Track not found' },
        { status: 404 }
      );
    }

    await delay(50); // Simulate network latency

    // Create mock WebM/Opus chunk data (ArrayBuffer)
    const chunkSize = 1024 * 20; // 20KB per chunk (typical for 10s @ 192kbps)
    const mockChunkData = new Uint8Array(chunkSize);
    for (let i = 0; i < chunkSize; i++) {
      mockChunkData[i] = (chunkIdx + i) % 256;
    }

    // Determine cache tier based on chunk index (simulate caching behavior)
    let cacheTier = 'MISS';
    if (chunkIdx === 0) cacheTier = 'L1'; // First chunk always cached
    else if (chunkIdx <= 2) cacheTier = 'L2'; // Next 2 chunks in L2
    else if (chunkIdx <= 5) cacheTier = 'L3'; // Next 3 in L3

    return new HttpResponse(mockChunkData.buffer, {
      status: 200,
      headers: {
        'Content-Type': 'audio/webm; codecs=opus',
        'X-Chunk-Index': chunkIdx.toString(),
        'X-Cache-Tier': cacheTier,
        'X-Latency-Ms': '50',
        'X-Enhanced': enhanced ? 'true' : 'false',
        'X-Preset': preset,
        'Content-Length': chunkSize.toString(),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-cache',
      }
    });
  }),

  // POST /api/stream/:track_id/switch-preset - Switch preset during playback
  http.post(`${API_BASE}/stream/:track_id/switch-preset`, async ({ request, params }) => {
    const trackId = parseInt(params.track_id as string);
    const body = await request.json();
    const newPreset = (body as any).preset || 'adaptive';

    await delay(100);

    return HttpResponse.json({
      success: true,
      track_id: trackId,
      preset: newPreset,
      message: 'Preset switched, buffers cleared'
    });
  }),

  // GET /api/streaming/status/:track_id - Get streaming status/health
  http.get(`${API_BASE}/streaming/status/:track_id`, async ({ params }) => {
    const trackId = parseInt(params.track_id as string);

    await delay(50);

    return HttpResponse.json({
      track_id: trackId,
      status: 'streaming',
      buffered_chunks: 5,
      total_chunks: 20,
      cache_hits: 3,
      cache_misses: 2,
      average_latency_ms: 45,
      preset: 'adaptive',
      enhanced: true
    });
  }),

  // DELETE /api/streaming/cleanup/:track_id - Cleanup streaming resources
  http.delete(`${API_BASE}/streaming/cleanup/:track_id`, async ({ params }) => {
    const trackId = parseInt(params.track_id as string);

    await delay(50);

    return HttpResponse.json({
      success: true,
      track_id: trackId,
      message: 'Streaming resources cleaned up'
    });
  }),

  // ============================================================
  // LEGACY ERROR HANDLERS (for backward compatibility)
  // ============================================================

  http.get(`${API_BASE}/not-found`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Not found' },
      { status: 404 }
    );
  }),

  http.get(`${API_BASE}/server-error`, async () => {
    await delay(50);
    return HttpResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }),

  http.get(`${API_BASE}/timeout`, async () => {
    await delay(30000); // 30s timeout
    return HttpResponse.json({ data: 'too late' });
  }),

  // ============================================================
  // RELATIVE URL HANDLERS (for test environments)
  // These mirror the absolute URL handlers but use relative paths
  // ============================================================

  // POST /api/player/enhancement/toggle - Toggle enhancement (relative URL)
  http.post('/api/player/enhancement/toggle', async ({ request }) => {
    const url = new URL(request.url, 'http://localhost');
    const enabled = url.searchParams.get('enabled') === 'true';
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: enabled,
        preset: 'adaptive',
        intensity: 1.0
      }
    });
  }),

  // POST /api/player/enhancement/preset - Set preset (relative URL)
  http.post('/api/player/enhancement/preset', async ({ request }) => {
    const url = new URL(request.url, 'http://localhost');
    const preset = url.searchParams.get('preset') || 'adaptive';
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: true,
        preset: preset,
        intensity: 1.0
      }
    });
  }),

  // POST /api/player/enhancement/intensity - Set intensity (relative URL)
  http.post('/api/player/enhancement/intensity', async ({ request }) => {
    const url = new URL(request.url, 'http://localhost');
    const intensity = parseFloat(url.searchParams.get('intensity') || '1.0');
    await delay(100);
    return HttpResponse.json({
      success: true,
      settings: {
        enabled: true,
        preset: 'adaptive',
        intensity: intensity
      }
    });
  }),

  // GET /api/processing/parameters - Get processing parameters (relative URL)
  http.get('/api/processing/parameters', async () => {
    await delay(100);
    return HttpResponse.json({
      spectral_balance: 0.5,
      dynamic_range: 0.7,
      energy_level: 0.8
    });
  }),

  // GET /api/player/state - Get player state (relative URL)
  http.get('/api/player/state', async () => {
    await delay(50);
    return HttpResponse.json(mockPlayerState);
  }),

  // POST /api/player/play - Play track (relative URL)
  http.post('/api/player/play', async ({ request }) => {
    const body = await request.json();
    await delay(100);
    return HttpResponse.json({
      success: true,
      track_id: (body as any).track_id
    });
  }),

  // POST /api/player/pause - Pause playback (relative URL)
  http.post('/api/player/pause', async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/seek - Seek to position (relative URL)
  http.post('/api/player/seek', async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      position: (body as any).position
    });
  }),

  // POST /api/player/volume - Set volume (relative URL)
  http.post('/api/player/volume', async ({ request }) => {
    const body = await request.json();
    await delay(50);
    return HttpResponse.json({
      success: true,
      volume: (body as any).volume
    });
  }),

  // POST /api/player/next - Next track (relative URL)
  http.post('/api/player/next', async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // POST /api/player/previous - Previous track (relative URL)
  http.post('/api/player/previous', async () => {
    await delay(50);
    return HttpResponse.json({ success: true });
  }),

  // GET /api/library/tracks - Get tracks list (relative URL)
  http.get('/api/library/tracks', async ({ request }) => {
    const url = new URL(request.url, 'http://localhost');
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const offset = parseInt(url.searchParams.get('offset') || '0');
    await delay(100);
    return HttpResponse.json({
      tracks: mockTracks.slice(offset, offset + limit),
      total: mockTracks.length,
      limit,
      offset
    });
  }),
];
