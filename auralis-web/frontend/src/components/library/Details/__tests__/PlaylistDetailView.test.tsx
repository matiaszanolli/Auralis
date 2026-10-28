/**
 * PlaylistDetailView Component Tests (#6007)
 *
 * The view exists so that clicking a playlist in the sidebar shows only
 * that playlist's tracks under the playlist's own name — previously the
 * `playlist-N` view id fell through to the Songs config and paginated the
 * entire library.
 *
 * Covered:
 * - Fetches GET /api/playlists/{id} (not the library tracks endpoint)
 * - Renders the playlist name and its tracks
 * - Empty playlist state
 * - 404 -> "Playlist not found" with recovery framing (#4643 parity)
 */

import { vi } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import PlaylistDetailView from '../PlaylistDetailView';

const mockPlayTrack = vi.fn();
vi.mock('@/hooks/player', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/player')>()),
  usePlayTrack: () => ({ playTrack: mockPlayTrack }),
}));

const mockFetch = vi.fn();
beforeAll(() => {
  global.fetch = mockFetch as any;
});
beforeEach(() => {
  vi.clearAllMocks();
});

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);

const mockPlaylist = {
  id: 7,
  name: 'Road Trip',
  description: null,
  is_smart: false,
  smart_criteria: null,
  auto_master_enabled: false,
  normalize_levels: false,
  track_count: 2,
  total_duration: 400,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  tracks: [
    { id: 1, title: 'Drive', artist: 'Cars', duration: 200 },
    { id: 2, title: 'Highway Star', artist: 'Deep Purple', duration: 200 },
  ],
};

describe('PlaylistDetailView', () => {
  it('fetches the playlist endpoint, not the library tracks endpoint', async () => {
    mockFetch.mockImplementation(() =>
      jsonResponse(mockPlaylist));

    render(<PlaylistDetailView playlistId={7} />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Road Trip' })).toBeInTheDocument();
    });

    const urls = mockFetch.mock.calls.map((call: any[]) => String(call[0]));
    expect(urls.some((u) => u.includes('/api/playlists/7'))).toBe(true);
    expect(urls.some((u) => u.includes('/api/library/tracks'))).toBe(false);
  });

  it('renders the playlist tracks under the playlist name', async () => {
    mockFetch.mockImplementation(() => jsonResponse(mockPlaylist));

    render(<PlaylistDetailView playlistId={7} />);

    expect(await screen.findByText('Drive')).toBeInTheDocument();
    expect(screen.getByText('Highway Star')).toBeInTheDocument();
    expect(screen.getByText(/2 tracks/)).toBeInTheDocument();
  });

  it('shows an empty state for a playlist with no tracks', async () => {
    mockFetch.mockImplementation(() =>
      jsonResponse({ ...mockPlaylist, tracks: [], track_count: 0 }));

    render(<PlaylistDetailView playlistId={7} />);

    expect(await screen.findByText('This playlist is empty')).toBeInTheDocument();
  });

  it('renders "Playlist not found" for a 404 (stale sidebar link)', async () => {
    mockFetch.mockImplementation(() =>
      jsonResponse({ detail: 'Playlist not found' }, 404));

    render(<PlaylistDetailView playlistId={404} onBack={() => {}} />);

    expect(await screen.findByText('Playlist not found')).toBeInTheDocument();
    expect(screen.getByText('Back to Songs')).toBeInTheDocument();
  });

  it('navigates back via onBack', async () => {
    mockFetch.mockImplementation(() => jsonResponse(mockPlaylist));
    const onBack = vi.fn();

    render(<PlaylistDetailView playlistId={7} onBack={onBack} />);

    const backButton = await screen.findByRole('button', { name: 'Go back to songs' });
    backButton.click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
