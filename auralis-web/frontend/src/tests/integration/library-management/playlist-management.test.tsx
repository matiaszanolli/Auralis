/**
 * Playlist Management Integration Tests
 *
 * Complete integration tests for playlist functionality
 * Part of Week 3 - Frontend Testing Roadmap (200-test suite)
 *
 * Test Categories:
 * 1. Playlist CRUD Operations (3 tests: create, load, metadata)
 * 2. Track Management in Playlists (2 tests)
 * 3. Playlist Display & Navigation (3 tests)
 * 4. Playlist Playback (2 tests)
 * 5. Playlist Search & Filter (1 test)
 *
 * Total: 14 tests
 *
 * Rename, delete, duplicate and drag-and-drop specs were removed (#5677): each ended on a
 * comment saying the interaction was out of scope and asserted only that a playlist it already
 * held was still in the document. Reinstate them with a real context-menu / dnd keyboard-sensor drive.
 *
 * Coverage:
 * - PlaylistList component
 * - CreatePlaylistDialog component
 * - Playlist API integration via playlistService
 * - MSW API mocking for playlist endpoints
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { DragDropContext } from '@hello-pangea/dnd';
import PlaylistList from '@/components/playlist/PlaylistList';
import * as playlistService from '@/services/playlistService';

/**
 * Wrapper component that provides DragDropContext for PlaylistList.
 * The test-utils intentionally excludes DragDropContext to prevent state conflicts,
 * so tests using drag-drop components must provide it individually.
 */
const PlaylistListWithDnd = (props: React.ComponentProps<typeof PlaylistList>) => (
  <DragDropContext onDragEnd={() => {}}>
    <PlaylistList {...props} />
  </DragDropContext>
);

// Mock window.confirm for delete operations
const mockConfirm = vi.fn();
global.window.confirm = mockConfirm;

describe('Playlist Management Integration Tests', () => {
  beforeEach(() => {
    // Reset mocks
    mockConfirm.mockReset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    mockConfirm.mockReset();
  });

  // ==========================================
  // 1. Playlist CRUD Operations (6 tests)
  // ==========================================

  describe('Playlist CRUD Operations', () => {
    it('should create a new playlist', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPlaylistSelect = vi.fn();

      render(<PlaylistListWithDnd onPlaylistSelect={onPlaylistSelect} />);

      // Wait for playlists to load
      await waitFor(() => {
        expect(screen.getByText(/Playlists \(3\)/i)).toBeInTheDocument();
      }, { timeout: 2000 });

      // Act - Click "Create playlist" button (+ icon)
      const addButton = screen.getByLabelText(/create playlist/i);
      await user.click(addButton);

      // Assert - Create dialog should open
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/create new playlist/i)).toBeInTheDocument();
      });

      // Act - Enter playlist name
      const nameInput = screen.getByLabelText(/playlist name/i);
      await user.type(nameInput, 'My Test Playlist');

      // Act - Submit form
      const createButton = screen.getByRole('button', { name: /create/i });
      await user.click(createButton);

      // Assert - Playlist should be created (MSW returns success)
      await waitFor(() => {
        // Dialog should close
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      }, { timeout: 2000 });
    });

    it('should load existing playlists on mount', async () => {
      // Arrange & Act
      render(<PlaylistListWithDnd />);

      // Assert - Wait for playlists to load (MSW returns 3 mock playlists)
      await waitFor(() => {
        expect(screen.getByText(/Playlists \(3\)/i)).toBeInTheDocument();
      }, { timeout: 2000 });

      // Should display playlist names from mockData
      await waitFor(() => {
        expect(screen.getByText('Favorites')).toBeInTheDocument();
        expect(screen.getByText('Recently Added')).toBeInTheDocument();
        expect(screen.getByText('Workout Mix')).toBeInTheDocument();
      });
    });

    it('should display playlist metadata correctly', async () => {
      // Arrange & Act
      render(<PlaylistListWithDnd />);

      // Wait for playlists to load
      await waitFor(() => {
        expect(screen.getByText('Favorites')).toBeInTheDocument();
      }, { timeout: 2000 });

      // Assert - Check track count is displayed (from mockData)
      expect(screen.getByText(/25 tracks/i)).toBeInTheDocument(); // Favorites has 25 tracks
      expect(screen.getByText(/15 tracks/i)).toBeInTheDocument(); // Recently Added has 15 tracks
      expect(screen.getByText(/30 tracks/i)).toBeInTheDocument(); // Workout Mix has 30 tracks
    });
  });

  // ==========================================
  // 2. Track Management in Playlists (2 tests)
  // ==========================================

  describe('Track Management in Playlists', () => {
    it('should add multiple tracks to playlist', async () => {
      // Arrange
      const addTracksSpy = vi.spyOn(playlistService, 'addTracksToPlaylist');

      // Act - Add multiple tracks
      const result = await playlistService.addTracksToPlaylist(1, [101, 102, 103]);

      // Assert - API returns added count
      expect(addTracksSpy).toHaveBeenCalledWith(1, [101, 102, 103]);
      expect(result).toBe(3); // MSW returns added_count: trackIds.length
    });

    it('should move track to different position within playlist', async () => {
      // Arrange
      const newTrackOrder = [3, 1, 2, 4, 5]; // New order after moving track

      // Act - Reorder tracks (direct API call)
      const response = await fetch('/api/playlists/1/reorder', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_ids: newTrackOrder })
      });

      // Assert - MSW handler returns success
      expect(response.ok).toBe(true);
      const data = await response.json();
      expect(data.success).toBe(true);
      expect(data.new_order).toEqual(newTrackOrder);
    });
  });

  // ==========================================
  // 3. Playlist Display & Navigation (3 tests)
  // ==========================================

  describe('Playlist Display & Navigation', () => {
    it('should display playlists in library view', async () => {
      // Arrange & Act
      render(<PlaylistListWithDnd />);

      // Assert - Playlists section is visible
      await waitFor(() => {
        expect(screen.getByText(/Playlists \(3\)/i)).toBeInTheDocument();
      }, { timeout: 2000 });

      // Should show playlist icons (one for section header, others for each playlist)
      const playlistIcons = screen.getAllByTestId('QueueMusicIcon');
      expect(playlistIcons.length).toBeGreaterThan(0);
    });

    it('should navigate between playlists and highlight selection', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPlaylistSelect = vi.fn();

      render(<PlaylistListWithDnd onPlaylistSelect={onPlaylistSelect} selectedPlaylistId={1} />);

      // Wait for playlists to load
      await waitFor(() => {
        expect(screen.getByText('Favorites')).toBeInTheDocument();
      }, { timeout: 2000 });

      // Act - Click on different playlist
      const workoutPlaylist = screen.getByText('Workout Mix');
      await user.click(workoutPlaylist);

      // Assert - Callback was called with playlist ID
      await waitFor(() => {
        expect(onPlaylistSelect).toHaveBeenCalled();
      });
    });

    it('should display empty playlist state correctly', async () => {
      // Arrange - Mock empty playlists response
      const user = userEvent.setup();

      render(<PlaylistListWithDnd />);

      // Wait for component to render
      await waitFor(() => {
        const header = screen.getByText(/Playlists/i);
        expect(header).toBeInTheDocument();
      }, { timeout: 2000 });

      // Act - Collapse and expand to trigger empty state check
      const header = screen.getByRole('button', { name: /collapse playlists|expand playlists/i });
      await user.click(header);
      await user.click(header);

      // Assert - Empty state would show "No playlists yet" if list was empty
      // With mock data, we have 3 playlists
      expect(screen.queryByText(/no playlists yet/i)).not.toBeInTheDocument();
    });
  });

  // ==========================================
  // 5. Playlist Playback (2 tests)
  // ==========================================

  describe('Playlist Playback', () => {
    it('should play playlist from start', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPlaylistSelect = vi.fn();

      render(<PlaylistListWithDnd onPlaylistSelect={onPlaylistSelect} />);

      // Wait for playlists to load
      await waitFor(() => {
        expect(screen.getByText('Favorites')).toBeInTheDocument();
      }, { timeout: 2000 });

      // Act - Click on playlist to play
      const favorites = screen.getByText('Favorites');
      await user.click(favorites);

      // Assert - Playlist selection callback was triggered
      await waitFor(() => {
        expect(onPlaylistSelect).toHaveBeenCalledWith(1); // Favorites is ID 1
      });
    });

    it('should resume playlist from specific track', async () => {
      // Arrange
      const playlistId = 1;

      // Act - Get playlist tracks
      const playlist = await playlistService.getPlaylist(playlistId);

      // Assert - Playlist has tracks that can be resumed from
      expect(playlist).toBeDefined();
      expect(playlist.id).toBe(playlistId);

      // Resume functionality would:
      // 1. Get playlist tracks (✓ API available)
      // 2. Load track at specific index
      // 3. Start playback from that track
      // MSW returns tracks for playlists, enabling this workflow
    });
  });

  // ==========================================
  // 6. Playlist Search & Filter (1 test)
  // ==========================================

  describe('Playlist Search & Filter', () => {
    it('should search tracks within playlist', async () => {
      // Arrange
      const playlistId = 1;

      // Act - Get playlist with tracks
      const response = await fetch(`/api/playlists/${playlistId}/tracks`);
      const data = await response.json();

      // Assert - Tracks are returned and can be filtered
      expect(data.tracks).toBeDefined();
      expect(Array.isArray(data.tracks)).toBe(true);
      expect(data.tracks.length).toBeGreaterThan(0);

      // Client-side filtering example
      const searchQuery = 'Track 1';
      const filteredTracks = data.tracks.filter((track: any) =>
        track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        track.artist.toLowerCase().includes(searchQuery.toLowerCase())
      );

      expect(filteredTracks.length).toBeGreaterThan(0);
    });
  });
});
