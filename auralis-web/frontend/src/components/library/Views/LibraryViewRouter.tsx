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
 * Uses ViewContainer for consistent header/layout across views.
 *
 * Returns null if current view should be handled by parent (songs/favorites).
 */

import React from 'react';
import { CozyAlbumGrid } from '../Items/albums/CozyAlbumGrid';
import { CozyArtistList } from '../Items/artists/CozyArtistList';
import AlbumDetailView from '../Details/AlbumDetailView';
import ArtistDetailView from '../Details/ArtistDetailView';
import { ViewContainer } from './ViewContainer';

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

  // Track actions (can be sync or async, accepts track objects with varying field subsets)
  onTrackPlay?: ((track: any) => void | Promise<void>);
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
  onTrackPlay,
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
      <ViewContainer icon="📀" title="Albums" subtitle="Browse your music collection by album">
        <CozyAlbumGrid onAlbumClick={onAlbumClick} />
      </ViewContainer>
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
      <ViewContainer icon="🎤" title="Artists" subtitle="Browse artists in your music library">
        <CozyArtistList onArtistClick={onArtistClick} />
      </ViewContainer>
    );
  }

  // Return null for track list views (songs/favorites)
  // These are handled by the parent CozyLibraryView component
  return null;
};

export default LibraryViewRouter;
