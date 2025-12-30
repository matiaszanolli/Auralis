/**
 * LibraryViewRouter - View Routing Component
 *
 * Routes between different library views:
 * - Albums view (grid of albums) with Album Character Pane
 * - Album detail view (tracks from specific album)
 * - Artists view (list of artists)
 * - Artist detail view (albums/tracks from specific artist)
 *
 * Extracted from CozyLibraryView.tsx to separate routing logic.
 * Uses ViewContainer for consistent header/layout across views.
 *
 * Returns null if current view should be handled by parent (songs/favorites).
 */

import React, { useState, useCallback } from 'react';
import { Box } from '@mui/material';
import { CozyAlbumGrid, type AlbumSortOption } from '../Items/albums/CozyAlbumGrid';
import { RecentlyTouchedSection } from '../Items/albums/RecentlyTouchedSection';
import { CozyArtistList } from '../Items/artists/CozyArtistList';
import AlbumDetailView from '../Details/AlbumDetailView';
import ArtistDetailView from '../Details/ArtistDetailView';
import { ViewContainer } from './ViewContainer';
import { AlbumCharacterPane } from '../AlbumCharacterPane';
import { SegmentedControl } from '@/design-system';
import { useAlbumFingerprint } from '@/hooks/fingerprint/useAlbumFingerprint';
import { useRecentlyTouched } from '@/hooks/library';

/** Sort options for album grid */
const ALBUM_SORT_OPTIONS = [
  { value: 'az', label: 'A-Z' },
  { value: 'year', label: 'Year' },
  { value: 'era', label: 'Era' },
];

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

  // Enhancement (auto-mastering) state - passed to AlbumCharacterPane
  isEnhancementEnabled?: boolean;
  onEnhancementToggle?: (enabled: boolean) => void;
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
  isEnhancementEnabled = true,
  onEnhancementToggle,
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

  // Albums view - grid of albums with character pane on hover
  if (view === 'albums') {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [hoveredAlbumId, setHoveredAlbumId] = useState<number | null>(null);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [hoveredAlbumTitle, setHoveredAlbumTitle] = useState<string | undefined>(undefined);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [hoveredAlbumArtist, setHoveredAlbumArtist] = useState<string | undefined>(undefined);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [sortBy, setSortBy] = useState<AlbumSortOption>('az');

    // Recently touched albums tracking
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { recentAlbums, touchAlbum } = useRecentlyTouched();

    // Fetch fingerprint for hovered album
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { fingerprint, isLoading } = useAlbumFingerprint(
      hoveredAlbumId ?? 0,
      { enabled: hoveredAlbumId !== null }
    );

    // Hover handlers
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const handleAlbumHover = useCallback((albumId: number, albumTitle?: string, albumArtist?: string) => {
      setHoveredAlbumId(albumId);
      setHoveredAlbumTitle(albumTitle);
      setHoveredAlbumArtist(albumArtist);
    }, []);

    // eslint-disable-next-line react-hooks/rules-of-hooks
    const handleAlbumHoverEnd = useCallback(() => {
      setHoveredAlbumId(null);
      setHoveredAlbumTitle(undefined);
      setHoveredAlbumArtist(undefined);
    }, []);

    // Click handler that tracks album access
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const handleAlbumClick = useCallback((albumId: number) => {
      // Track album access using hover state info
      if (hoveredAlbumTitle) {
        touchAlbum(albumId, hoveredAlbumTitle, hoveredAlbumArtist ?? 'Unknown Artist');
      }
      onAlbumClick(albumId);
    }, [onAlbumClick, touchAlbum, hoveredAlbumTitle, hoveredAlbumArtist]);

    return (
      <ViewContainer
        icon="📀"
        title="Albums"
        subtitle="Browse your music collection by album"
        headerActions={
          <SegmentedControl
            value={sortBy}
            onChange={(value) => setSortBy(value as AlbumSortOption)}
            options={ALBUM_SORT_OPTIONS}
            size="sm"
          />
        }
        rightPane={
          <AlbumCharacterPane
            fingerprint={fingerprint ?? null}
            albumTitle={hoveredAlbumTitle}
            isLoading={isLoading && hoveredAlbumId !== null}
            isEnhancementEnabled={isEnhancementEnabled}
            onEnhancementToggle={onEnhancementToggle}
          />
        }
      >
        <Box sx={{ height: '100%', overflow: 'auto' }}>
          {/* Recently Touched Section */}
          <RecentlyTouchedSection
            recentAlbums={recentAlbums}
            onAlbumClick={handleAlbumClick}
            onAlbumHover={handleAlbumHover}
            onAlbumHoverEnd={handleAlbumHoverEnd}
          />

          {/* Main Album Grid */}
          <CozyAlbumGrid
            sortBy={sortBy}
            onAlbumClick={handleAlbumClick}
            onAlbumHover={handleAlbumHover}
            onAlbumHoverEnd={handleAlbumHoverEnd}
          />
        </Box>
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
