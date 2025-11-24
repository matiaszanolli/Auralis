/**
 * ContextMenu Component
 *
 * Unified context menu for tracks, albums, artists, and playlists
 * Handles right-click menu display with configurable actions
 *
 * Features:
 * - Position tracking for cursor location
 * - Dynamic action rendering with dividers
 * - Playlist integration (optional, for tracks)
 * - Destructive action styling
 * - Outside-click dismissal
 *
 * Usage:
 * ```tsx
 * <ContextMenu
 *   open={isOpen}
 *   actions={contextActions}
 *   anchorPosition={{ top: e.clientY, left: e.clientX }}
 *   onClose={handleClose}
 *   trackId={trackId}
 *   onAddToPlaylist={addToPlaylist}
 * />
 * ```
 */

import React, { useState, useEffect, useRef } from 'react';
import * as playlistService from '../../../services/playlistService';
import CreatePlaylistDialog from '../../playlist/CreatePlaylistDialog';
import { PlaylistSection } from './PlaylistSection';
import { ContextMenuAction } from './contextMenuActions';
import { StyledMenu } from './ContextMenu.styles';
import { ContextMenuActionsRenderer } from './ContextMenuActionsRenderer';
import { usePlaylistActions } from './usePlaylistActions';

export interface ContextMenuProps {
  open: boolean;
  anchorPosition?: { top: number; left: number };
  onClose: () => void;
  actions: ContextMenuAction[];
  // Playlist integration (optional, for tracks with playlist support)
  trackId?: number | null;
  trackTitle?: string;
  playlists?: playlistService.Playlist[];
  isLoadingPlaylists?: boolean;
  onPlaylistsLoad?: () => void;
  onAddToPlaylist?: (playlistId: number, playlistName: string) => Promise<void>;
  onCreatePlaylist?: (playlist: playlistService.Playlist) => Promise<void>;
}

export const ContextMenu: React.FC<ContextMenuProps> = ({
  open,
  anchorPosition,
  onClose,
  actions,
  trackId,
  trackTitle,
  playlists = [],
  isLoadingPlaylists = false,
  onPlaylistsLoad,
  onAddToPlaylist,
  onCreatePlaylist,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  // Load playlists when menu opens (if trackId provided)
  useEffect(() => {
    if (open && trackId && onPlaylistsLoad) {
      onPlaylistsLoad();
    }
  }, [open, trackId, onPlaylistsLoad]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open, onClose]);

  const {
    handleAddToPlaylist,
    handleCreateNewPlaylist,
    handlePlaylistCreated,
  } = usePlaylistActions({
    onAddToPlaylist,
    onCreatePlaylist,
    onClose,
    onCreateDialogOpen: () => setCreateDialogOpen(true),
  });

  const handleActionClick = (action: ContextMenuAction) => {
    action.onClick();
    onClose();
  };

  const showPlaylistSection = trackId && (playlists.length > 0 || onAddToPlaylist);

  return (
    <>
      <StyledMenu
        ref={menuRef}
        open={open}
        onClose={onClose}
        anchorReference="anchorPosition"
        anchorPosition={anchorPosition}
        transitionDuration={200}
      >
        <ContextMenuActionsRenderer
          actions={actions}
          onActionClick={handleActionClick}
        />

        {/* Playlist Section (only for track context menus with trackId) */}
        {showPlaylistSection && (
          <PlaylistSection
            playlists={playlists}
            isLoadingPlaylists={isLoadingPlaylists}
            onAddToPlaylist={handleAddToPlaylist}
            onCreateNewPlaylist={handleCreateNewPlaylist}
          />
        )}
      </StyledMenu>

      {/* Create Playlist Dialog */}
      {trackId && (
        <CreatePlaylistDialog
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
          onPlaylistCreated={handlePlaylistCreated}
          initialTrackIds={trackId ? [trackId] : undefined}
        />
      )}
    </>
  );
};

export default ContextMenu;
