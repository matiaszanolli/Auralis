/**
 * LibraryView Component
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Main library browser view.
 * Combines SearchBar, TrackList, AlbumGrid, and ArtistList.
 *
 * Usage:
 * ```typescript
 * <LibraryView />
 * ```
 *
 * @module components/library/LibraryView
 */

import React, { useState, useCallback } from 'react';
import { tokens } from '@/design-system';
import SearchBar from './SearchBar';
import TrackList from './TrackList';
import AlbumGrid from './AlbumGrid';
import ArtistList from './ArtistList';
import { usePlayer } from '@/hooks/shared/useReduxState';
import { useToast } from '@/components/shared/Toast';
import type { Track, Album, Artist } from '@/types/domain';

type ViewMode = 'tracks' | 'albums' | 'artists';

/**
 * LibraryView component
 *
 * Main library interface with tabs for tracks, albums, artists.
 * Includes search and selection handling.
 */
export const LibraryView: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('tracks');
  const [search, setSearch] = useState('');
  const [selectedAlbum, setSelectedAlbum] = useState<Album | null>(null);
  const [selectedArtist, setSelectedArtist] = useState<Artist | null>(null);

  const player = usePlayer();
  const { success, error: showError } = useToast();

  /**
   * Handle track selection - start playback of selected track
   */
  const handleTrackSelect = useCallback(
    (track: Track) => {
      try {
        // Set the track as current and play it
        player.setTrack(track);
        player.play();
        success(`Playing ${track.title}`);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to play track';
        showError(errorMessage);
      }
    },
    [player, success, showError]
  );

  /**
   * Handle album selection - show album details/tracks
   * Currently stores selected album state; can be extended with modal
   */
  const handleAlbumSelect = useCallback((album: Album) => {
    setSelectedAlbum(album);
    success(`Viewing album: ${album.title}`);
  }, [success]);

  /**
   * Handle artist selection - show artist details/albums
   * Currently stores selected artist state; can be extended with modal
   */
  const handleArtistSelect = useCallback((artist: Artist) => {
    setSelectedArtist(artist);
    success(`Viewing artist: ${artist.name}`);
  }, [success]);

  return (
    <div style={styles.container}>
      {/* Header with search */}
      <div style={styles.header}>
        <h1 style={styles.title}>Library</h1>
        <SearchBar onSearch={setSearch} />
      </div>

      {/* View tabs */}
      <div style={styles.tabs}>
        {(['tracks', 'albums', 'artists'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            style={{
              ...styles.tab,
              ...(viewMode === mode && styles.tabActive),
            }}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div style={styles.content}>
        {viewMode === 'tracks' && (
          <TrackList search={search} onTrackSelect={handleTrackSelect} />
        )}

        {viewMode === 'albums' && (
          <AlbumGrid onAlbumSelect={handleAlbumSelect} />
        )}

        {viewMode === 'artists' && (
          <ArtistList onArtistSelect={handleArtistSelect} />
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.primary,
  },

  header: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  tabs: {
    display: 'flex',
    gap: tokens.spacing.sm,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  tab: {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: 'transparent',
    border: 'none',
    borderBottom: `2px solid transparent`,
    cursor: 'pointer',
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s ease',
  },

  tabActive: {
    color: tokens.colors.accent.primary,
    borderBottomColor: tokens.colors.accent.primary,
  },

  content: {
    flex: 1,
    overflow: 'auto',
    width: '100%',
  },
};

export default LibraryView;
