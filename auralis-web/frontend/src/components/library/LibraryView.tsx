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
import { tokens, Box, Text, Button } from '@/design-system';
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
    <Box
      display="flex"
      flexDirection="column"
      width="100%"
      height="100%"
      gap="lg"
      padding="lg"
      bg={tokens.colors.bg.primary}
    >
      {/* Flat toolbar row - search + tabs inline, no container styling */}
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        gap="xl"
        paddingY="md"
      >
        {/* Left: Title + Tabs (compact, inline) */}
        <Box display="flex" alignItems="center" gap="xl" flex={1}>
          <Text
            as="h1"
            variant="title"
            color={tokens.colors.text.primary}
            style={{ flexShrink: 0 }}
          >
            Library
          </Text>

          {/* Tabs inline - minimal, ambient */}
          <Box display="flex" gap="xs" alignItems="center">
            {(['tracks', 'albums', 'artists'] as const).map((mode) => (
              <Button
                key={mode}
                variant="ghost"
                size="sm"
                onClick={() => setViewMode(mode)}
                style={{
                  opacity: viewMode === mode ? 1 : 0.75,
                  backgroundColor: viewMode === mode ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                  color: viewMode === mode ? tokens.colors.text.primary : tokens.colors.text.tertiary,
                  transition: 'all 0.15s ease',
                }}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </Button>
            ))}
          </Box>
        </Box>

        {/* Right: Search (minimal, floating directly on surface) */}
        <Box display="flex" alignItems="center" width="320px" flexShrink={0}>
          <SearchBar onSearch={setSearch} />
        </Box>
      </Box>

      {/* Content area */}
      <Box flex={1} overflow="auto" width="100%">
        {viewMode === 'tracks' && (
          <TrackList search={search} onTrackSelect={handleTrackSelect} />
        )}

        {viewMode === 'albums' && (
          <AlbumGrid onAlbumSelect={handleAlbumSelect} />
        )}

        {viewMode === 'artists' && (
          <ArtistList onArtistSelect={handleArtistSelect} />
        )}
      </Box>
    </Box>
  );
};

export default LibraryView;
