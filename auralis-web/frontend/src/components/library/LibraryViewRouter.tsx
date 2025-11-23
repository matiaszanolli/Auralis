/**
 * LibraryViewRouter - View Routing Component
 *
 * Routes between different library views:
 * - Albums view (grid of albums)
 * - Album detail view (tracks from specific album)
 * - Artists view (list of artists)
 * - Artist detail view (albums/tracks from specific artist)
 *
 * Extracted from CozyLibraryView.tsx to separate routing logic.
 *
 * Returns null if current view should be handled by parent (songs/favorites).
 */

import React from 'react';
import { Container, Box, Typography } from '@mui/material';
import { CozyAlbumGrid } from './CozyAlbumGrid';
import { CozyArtistList } from './CozyArtistList';
import AlbumDetailView from './AlbumDetailView';
import ArtistDetailView from './ArtistDetailView';
import { tokens } from '@/design-system/tokens';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  album_id?: number;
  duration: number;
  albumArt?: string;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

export interface LibraryViewRouterProps {
  view: string;
  selectedAlbumId: number | null;
  selectedArtistId: number | null;
  selectedArtistName: string;
  currentTrackId?: number;
  isPlaying: boolean;

  // Navigation callbacks
  onBackFromAlbum: () => void;
  onBackFromArtist: () => void;
  onAlbumClick: (albumId: number) => void;
  onArtistClick: (artistId: number, artistName: string) => void;

  // Track actions
  onTrackPlay: (track: Track) => void;
}

/**
 * Library View Router Component
 *
 * Handles routing between albums/artists views and their detail pages.
 * Returns null for track list views (songs/favorites) which are handled by parent.
 */
export const LibraryViewRouter: React.FC<LibraryViewRouterProps> = ({
  view,
  selectedAlbumId,
  selectedArtistId,
  selectedArtistName,
  currentTrackId,
  isPlaying,
  onBackFromAlbum,
  onBackFromArtist,
  onAlbumClick,
  onArtistClick,
  onTrackPlay
}) => {
  // Album detail view (from albums or artists view)
  if (selectedAlbumId !== null) {
    return (
      <AlbumDetailView
        albumId={selectedAlbumId}
        onBack={onBackFromAlbum}
        onTrackPlay={onTrackPlay}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
      />
    );
  }

  // Albums view - grid of albums
  if (view === 'albums') {
    return (
      <Container
        maxWidth="xl"
        sx={{
          py: 4,
          height: '100%',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <Box sx={{ mb: 4, flexShrink: 0 }}>
          <Typography
            variant="h3"
            component="h1"
            fontWeight="bold"
            gutterBottom
            sx={{
              background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            📀 Albums
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Browse your music collection by album
          </Typography>
        </Box>
        <Box sx={{ flex: 1, minHeight: 0 }}>
          <CozyAlbumGrid onAlbumClick={onAlbumClick} />
        </Box>
      </Container>
    );
  }

  // Artists view
  if (view === 'artists') {
    // Artist detail view
    if (selectedArtistId !== null) {
      return (
        <ArtistDetailView
          artistId={selectedArtistId}
          artistName={selectedArtistName}
          onBack={onBackFromArtist}
          onTrackPlay={onTrackPlay}
          onAlbumClick={onAlbumClick}
          currentTrackId={currentTrackId}
          isPlaying={isPlaying}
        />
      );
    }

    // Artist list view
    return (
      <Container
        maxWidth="xl"
        sx={{
          py: 4,
          height: '100%',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <Box sx={{ mb: 4, flexShrink: 0 }}>
          <Typography
            variant="h3"
            component="h1"
            fontWeight="bold"
            gutterBottom
            sx={{
              background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            🎤 Artists
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Browse artists in your music library
          </Typography>
        </Box>
        <Box sx={{ flex: 1, minHeight: 0 }}>
          <CozyArtistList onArtistClick={onArtistClick} />
        </Box>
      </Container>
    );
  }

  // Return null for track list views (songs/favorites)
  // These are handled by the parent CozyLibraryView component
  return null;
};

export default LibraryViewRouter;
