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

import { useState, useCallback } from 'react';
import { CozyAlbumGrid, type AlbumSortOption } from '@/components/library/Items/albums/CozyAlbumGrid';
import { RecentlyTouchedSection } from '@/components/library/Items/albums/RecentlyTouchedSection';
import { CozyArtistList } from '@/components/library/Items/artists/CozyArtistList';
import AlbumDetailView from '@/components/library/Details/AlbumDetailView';
import ArtistDetailView from '@/components/library/Details/ArtistDetailView';
import { ViewContainer } from './ViewContainer';
import { AlbumCharacterPane } from '@/components/library/AlbumCharacterPane';
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

  // Track actions (can be sync or async, accepts a full LibraryTrack or
  // a richer Track domain object — the contract is: at minimum `{ id }`
  // plus the title/artist/album/duration fields needed for playback UI).
  // #3633: typed as LibraryTrack (which covers all current call sites)
  // rather than `any`, so backend field renames produce TS errors here.
  onTrackPlay?: (
    track: import('@/types/domain').LibraryTrack
  ) => void | Promise<void>;
}

/**
 * Library View Router Component
 *
 * Handles routing between albums/artists views and their detail pages.
 * Returns null for track list views (songs/favorites) which are handled by parent.
 */
export const LibraryViewRouter = ({
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
}: LibraryViewRouterProps) => {
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

  // Albums view - grid of albums with character pane on hover.
  // Rendered as a dedicated sub-component (AlbumsView) so its hooks run
  // unconditionally — calling them inside this `if` branch was a Rules-of-Hooks
  // violation that corrupted fiber state slots on view transitions (#3924).
  if (view === 'albums') {
    return <AlbumsView onAlbumClick={onAlbumClick} />;
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

/**
 * Albums view — owns all album-grid local state (hover, sort, fingerprint,
 * recently-touched). Extracted from LibraryViewRouter so its hooks are called
 * unconditionally rather than inside an `if (view === 'albums')` branch (#3924).
 */
interface AlbumsViewProps {
  onAlbumClick: (albumId: number) => void;
}

const AlbumsView = ({ onAlbumClick }: AlbumsViewProps) => {
  const [hoveredAlbumId, setHoveredAlbumId] = useState<number | null>(null);
  const [hoveredAlbumTitle, setHoveredAlbumTitle] = useState<string | undefined>(undefined);
  const [hoveredAlbumArtist, setHoveredAlbumArtist] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState<AlbumSortOption>('az');

  // Recently touched albums tracking
  const { recentAlbums, touchAlbum } = useRecentlyTouched();

  // Fetch fingerprint for hovered album
  const { fingerprint, isLoading } = useAlbumFingerprint(
    hoveredAlbumId ?? 0,
    { enabled: hoveredAlbumId !== null }
  );

  const handleAlbumHover = useCallback((albumId: number, albumTitle?: string, albumArtist?: string) => {
    setHoveredAlbumId(albumId);
    setHoveredAlbumTitle(albumTitle);
    setHoveredAlbumArtist(albumArtist);
  }, []);

  const handleAlbumHoverEnd = useCallback(() => {
    setHoveredAlbumId(null);
    setHoveredAlbumTitle(undefined);
    setHoveredAlbumArtist(undefined);
  }, []);

  // Click handler that tracks album access using hover state info
  const handleAlbumClick = useCallback((albumId: number) => {
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
          aria-label="Sort albums by"
        />
      }
      rightPane={
        <AlbumCharacterPane
          fingerprint={fingerprint ?? null}
          albumTitle={hoveredAlbumTitle}
          isLoading={isLoading && hoveredAlbumId !== null}
        />
      }
    >
      <>
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
      </>
    </ViewContainer>
  );
};

export default LibraryViewRouter;
