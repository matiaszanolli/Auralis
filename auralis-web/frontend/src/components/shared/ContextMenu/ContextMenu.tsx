/**
 * ContextMenu Component
 *
 * Unified context menu for tracks, albums, artists, and playlists
 * Handles right-click menu display with configurable actions
 *
 * Features:
 * - Position tracking for cursor location
 * - Dynamic action rendering
 * - Playlist integration (optional)
 * - Destructive action styling
 * - Outside-click dismissal
 */

import React, { useState, useEffect, useRef } from 'react';
import { Menu, MenuItem, ListItemIcon, ListItemText, Divider, styled } from '@mui/material';
import * as playlistService from '../../../services/playlistService';
import CreatePlaylistDialog from '../../playlist/CreatePlaylistDialog';
import { PlaylistSection } from './PlaylistSection';
import { ContextMenuAction } from './contextMenuActions';
import { useToast } from '../Toast';
import { cardShadows } from '../../library/Shadow.styles';
import { radiusMedium, radiusSmall } from '../../library/BorderRadius.styles';
import { spacingXSmall, spacingXMedium } from '../../library/Spacing.styles';
import { auroraOpacity } from '../../library/Color.styles';
import { tokens } from '@/design-system/tokens';

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

// ============================================================================
// Styled Components
// ============================================================================

const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: tokens.colors.bg.secondary,
    border: `1px solid ${auroraOpacity.standard}`,
    boxShadow: cardShadows.dropdownDark,
    borderRadius: radiusMedium,
    minWidth: '220px',
    padding: spacingXSmall,
    backdropFilter: 'blur(12px)',
  },
});

const StyledMenuItem = styled(MenuItem)<{ destructive?: boolean }>(({ destructive }) => ({
  borderRadius: radiusSmall,
  padding: `${spacingXMedium} ${spacingXMedium}`,
  margin: `${spacingXSmall} 0`,
  fontSize: '14px',
  color: destructive ? tokens.colors.accent.error : tokens.colors.text.primary,
  transition: 'all 0.2s ease',

  '&:hover': {
    background: destructive ? auroraOpacity.ultraLight : auroraOpacity.lighter,
  },

  '&.Mui-disabled': {
    color: tokens.colors.text.disabled,
    opacity: 0.5,
  },

  '& .MuiListItemIcon-root': {
    color: destructive ? tokens.colors.accent.error : tokens.colors.text.secondary,
    minWidth: 36,
  },
}));

// ============================================================================
// Main Component
// ============================================================================

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
  const { success, error } = useToast();

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

  const handleAddToPlaylist = async (playlistId: number, playlistName: string) => {
    if (!onAddToPlaylist) return;
    try {
      await onAddToPlaylist(playlistId, playlistName);
      success(`Added to "${playlistName}"`);
      onClose();
    } catch (err) {
      error(`Failed to add to playlist: ${err}`);
    }
  };

  const handleCreateNewPlaylist = () => {
    onClose();
    setCreateDialogOpen(true);
  };

  const handlePlaylistCreated = async (playlist: playlistService.Playlist) => {
    if (!onCreatePlaylist) return;
    try {
      await onCreatePlaylist(playlist);
      success(`Added to "${playlist.name}"`);
    } catch (err) {
      error(`Failed to add to playlist: ${err}`);
    }
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
        {/* Main Actions */}
        {actions.map((action, index) => (
          <React.Fragment key={action.id}>
            {action.divider && index > 0 && (
              <Divider sx={{ borderColor: auroraOpacity.minimal, my: 1 }} />
            )}
            <StyledMenuItem
              onClick={() => {
                action.onClick();
                onClose();
              }}
              disabled={action.disabled}
              destructive={action.destructive}
            >
              {action.icon && <ListItemIcon>{action.icon}</ListItemIcon>}
              <ListItemText>{action.label}</ListItemText>
            </StyledMenuItem>
          </React.Fragment>
        ))}

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
