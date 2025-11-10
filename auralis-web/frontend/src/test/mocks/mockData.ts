/**
 * Mock Data for MSW Handlers
 *
 * Comprehensive mock datasets for testing all Auralis features
 */

// Mock Tracks
export const mockTracks = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  title: `Test Track ${i + 1}`,
  artist: `Artist ${(i % 10) + 1}`,
  album: `Album ${(i % 5) + 1}`,
  duration: 180 + (i * 5),
  file_path: `/music/track${i + 1}.flac`,
  favorite: i % 5 === 0,
  play_count: i * 2,
  year: 2020 + (i % 5),
  genre: ['Rock', 'Pop', 'Jazz', 'Electronic', 'Classical'][i % 5],
  created_at: new Date(2024, 0, i + 1).toISOString(),
  last_played: i % 3 === 0 ? new Date(2024, 10, i).toISOString() : null,
}));

// Mock Albums
export const mockAlbums = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  title: `Album ${i + 1}`,
  artist: `Artist ${(i % 10) + 1}`,
  year: 2020 + (i % 5),
  track_count: 10 + (i % 5),
  artwork_path: `/artwork/album${i + 1}.jpg`,
  genre: ['Rock', 'Pop', 'Jazz', 'Electronic', 'Classical'][i % 5],
  total_duration: (10 + (i % 5)) * 180,
}));

// Mock Artists
export const mockArtists = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1,
  name: `Artist ${i + 1}`,
  album_count: 2 + (i % 3),
  track_count: 20 + (i * 5),
  genres: [['Rock', 'Pop'], ['Jazz'], ['Electronic', 'Pop'], ['Classical'], ['Rock']][i % 5],
}));

// Mock Playlists
export const mockPlaylists = [
  {
    id: 1,
    name: 'Favorites',
    track_count: 25,
    created_at: '2024-01-01T00:00:00Z',
    description: 'My favorite tracks',
  },
  {
    id: 2,
    name: 'Recently Added',
    track_count: 15,
    created_at: '2024-01-15T00:00:00Z',
    description: 'Tracks added in the last month',
  },
  {
    id: 3,
    name: 'Workout Mix',
    track_count: 30,
    created_at: '2024-02-01T00:00:00Z',
    description: 'High energy tracks for working out',
  },
];

// Mock Player State
export const mockPlayerState = {
  current_track: mockTracks[0],
  is_playing: false,
  position: 0,
  duration: 180,
  volume: 0.8,
  queue: mockTracks.slice(0, 5),
  queue_position: 0,
  shuffle: false,
  repeat_mode: 'off', // 'off', 'all', 'one'
  enhancement_enabled: false,
  enhancement_preset: 'adaptive',
};

// Mock Enhancement Presets
export const mockEnhancementPresets = [
  {
    id: 'adaptive',
    name: 'Adaptive',
    description: 'Intelligent content-aware mastering',
    default: true,
  },
  {
    id: 'gentle',
    name: 'Gentle',
    description: 'Subtle mastering with minimal processing',
    default: false,
  },
  {
    id: 'warm',
    name: 'Warm',
    description: 'Adds warmth and smoothness',
    default: false,
  },
  {
    id: 'bright',
    name: 'Bright',
    description: 'Enhances clarity and presence',
    default: false,
  },
  {
    id: 'punchy',
    name: 'Punchy',
    description: 'Increases impact and dynamics',
    default: false,
  },
];

// Mock Library Statistics
export const mockLibraryStats = {
  total_tracks: mockTracks.length,
  total_albums: mockAlbums.length,
  total_artists: mockArtists.length,
  total_playlists: mockPlaylists.length,
  total_duration: mockTracks.reduce((acc, t) => acc + t.duration, 0),
  total_play_count: mockTracks.reduce((acc, t) => acc + t.play_count, 0),
  favorites_count: mockTracks.filter(t => t.favorite).length,
  recent_tracks_count: mockTracks.filter(t => t.last_played).length,
};

// Mock Search Results
export const mockSearchResults = {
  tracks: mockTracks.slice(0, 10),
  albums: mockAlbums.slice(0, 5),
  artists: mockArtists.slice(0, 5),
  playlists: mockPlaylists.slice(0, 2),
};

// Helper function to get track by ID
export const getTrackById = (id: number) => {
  return mockTracks.find(t => t.id === id);
};

// Helper function to get album by ID
export const getAlbumById = (id: number) => {
  return mockAlbums.find(a => a.id === id);
};

// Helper function to get artist by ID
export const getArtistById = (id: number) => {
  return mockArtists.find(a => a.id === id);
};

// Helper function to get playlist by ID
export const getPlaylistById = (id: number) => {
  return mockPlaylists.find(p => p.id === id);
};

// Helper function to search tracks
export const searchTracks = (query: string) => {
  return mockTracks.filter(t =>
    t.title.toLowerCase().includes(query.toLowerCase()) ||
    t.artist.toLowerCase().includes(query.toLowerCase()) ||
    t.album.toLowerCase().includes(query.toLowerCase())
  );
};

// Helper function to generate large mock dataset for performance testing
export const generateLargeMockTracks = (count: number) => {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    title: `Track ${i + 1}`,
    artist: `Artist ${(i % 100) + 1}`,
    album: `Album ${(i % 50) + 1}`,
    duration: 180 + (i % 300),
    file_path: `/music/track${i + 1}.flac`,
    favorite: i % 10 === 0,
    play_count: Math.floor(Math.random() * 100),
    year: 2000 + (i % 25),
    genre: ['Rock', 'Pop', 'Jazz', 'Electronic', 'Classical', 'Metal', 'Hip Hop', 'R&B'][i % 8],
    created_at: new Date(2020 + (i % 5), i % 12, (i % 28) + 1).toISOString(),
    last_played: i % 5 === 0 ? new Date(2024, 10, i % 30).toISOString() : null,
    track_number: (i % 15) + 1,
    disc_number: 1,
    format: 'FLAC',
  }));
};
