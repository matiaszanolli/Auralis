/**
 * CozyArtistList Component
 *
 * Orchestrates artist list display with infinite scroll pagination,
 * alphabetic grouping, and context menu support.
 * Uses extracted components and custom hook for logic separation.
 */

import React from 'react';
import {
  Box,
  Typography,
  Person
} from '@mui/material';
import { ContextMenu, getArtistContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';
import { EmptyState } from '../shared/EmptyState';
import { SectionHeader } from '../Styles/ArtistList.styles';
import { ArtistListLoading } from './ArtistListLoading';
import { ArtistSection } from './ArtistSection';
import { useArtistListPagination } from './useArtistListPagination';

interface CozyArtistListProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
}

/**
 * CozyArtistList - Main orchestration component for artist list view
 *
 * Displays:
 * - Loading skeleton during initial fetch
 * - Alphabetically grouped artist sections
 * - Infinite scroll pagination (2000px threshold)
 * - Context menu with artist actions
 * - Loading indicator and end-of-list message
 *
 * Uses:
 * - useArtistListPagination hook for pagination, grouping, context menu logic
 * - ArtistSection component for letter-grouped sections
 * - ArtistListLoading component for loading skeleton
 */
export const CozyArtistList: React.FC<CozyArtistListProps> = ({ onArtistClick }) => {
  const { success, info } = useToast();

  const {
    artists,
    loading,
    error,
    hasMore,
    totalArtists,
    isLoadingMore,
    containerRef,
    loadMoreTriggerRef,
    contextMenuState,
    contextMenuArtist,
    handleCloseContextMenu,
    handleArtistClick,
    handleContextMenuOpen,
    groupedArtists,
    sortedLetters
  } = useArtistListPagination({ onArtistClick });

  // Context menu actions
  const contextActions = contextMenuArtist
    ? getArtistContextActions(contextMenuArtist.id, {
        onPlayAll: () => {
          success(`Playing all songs by ${contextMenuArtist.name}`);
          // TODO: Implement play all artist tracks
        },
        onAddToQueue: () => {
          success(`Added ${contextMenuArtist.name} to queue`);
          // TODO: Implement add artist to queue
        },
        onShowAlbums: () => {
          info(`Showing albums by ${contextMenuArtist.name}`);
          if (onArtistClick) {
            onArtistClick(contextMenuArtist.id, contextMenuArtist.name);
          }
        },
        onShowInfo: () => {
          info(`Artist: ${contextMenuArtist.name}\n${contextMenuArtist.album_count} albums • ${contextMenuArtist.track_count} tracks`);
          // TODO: Show artist info modal
        },
      })
    : [];

  if (loading) {
    return <ArtistListLoading />;
  }

  if (error) {
    return (
      <EmptyState
        title="Error Loading Artists"
        description={error}
      />
    );
  }

  if (artists.length === 0) {
    return (
      <EmptyState
        title="No Artists Yet"
        description="Your artist library will appear here once you scan your music folder"
        customIcon={<Person sx={{ fontSize: 64, opacity: 0.3 }} />}
      />
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        padding: '24px',
        width: '100%'
      }}
    >
      <SectionHeader>
        <Typography variant="body2" color="text.secondary">
          {artists.length} {artists.length !== totalArtists ? `of ${totalArtists}` : ''} artists in your library
        </Typography>
      </SectionHeader>

      {/* Alphabetically grouped artist sections */}
      {sortedLetters.map((letter) => (
        <ArtistSection
          key={letter}
          letter={letter}
          artists={groupedArtists[letter]}
          onArtistClick={handleArtistClick}
          onContextMenu={handleContextMenuOpen}
        />
      ))}

      {/* Load more trigger - invisible sentinel element */}
      {hasMore && (
        <Box
          ref={loadMoreTriggerRef}
          sx={{
            height: '1px',
            width: '100%',
          }}
        />
      )}

      {/* Loading indicator */}
      {isLoadingMore && (
        <Box
          sx={{
            height: '100px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: 2
          }}
        >
          <Box
            sx={{
              width: 20,
              height: 20,
              border: '2px solid',
              borderColor: 'primary.main',
              borderRightColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' }
              }
            }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
            Loading more artists... ({artists.length}/{totalArtists})
          </Typography>
        </Box>
      )}

      {/* End of list indicator */}
      {!hasMore && artists.length > 0 && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Showing all {totalArtists} artists
          </Typography>
        </Box>
      )}

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      />
    </Box>
  );
};

export default CozyArtistList;
