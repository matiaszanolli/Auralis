import React, { useState, useEffect, useRef } from 'react';
import { Menu, MenuItem, ListItemIcon, ListItemText, Divider, styled, Box } from '@mui/material';
import {
  PlayArrow,
  QueueMusic,
  PlaylistAdd,
  Favorite,
  FavoriteBorder,
  Info,
  Delete,
  Edit,
  Album as AlbumIcon,
  Person,
  Add,
} from '@mui/icons-material';
import { useToast } from './Toast';
import * as playlistService from '../../services/playlistService';
import CreatePlaylistDialog from '../playlist/CreatePlaylistDialog';
import { cardShadows } from '../library/Shadow.styles';
import { radiusMedium, radiusSmall } from '../library/BorderRadius.styles';
import { spacingXSmall, spacingXMedium } from '../library/Spacing.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon?: React.ReactNode;
  divider?: boolean;
  destructive?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

interface ContextMenuProps {
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
    background: destructive
      ? auroraOpacity.ultraLight
      : auroraOpacity.lighter,
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

const PlaylistMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: tokens.colors.text.secondary,
  padding: '8px 16px 8px 48px',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: auroraOpacity.veryLight,
    color: tokens.colors.text.primary,
    transform: 'translateX(2px)',
  },
});

const CreateNewMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: tokens.colors.accent.purple,
  padding: '8px 16px 8px 48px',
  fontWeight: 600,
  transition: 'all 0.2s ease',
  '&:hover': {
    background: auroraOpacity.lighter,
    transform: 'translateX(2px)',
  },
});

const SectionLabel = styled(Box)({
  fontSize: '11px',
  fontWeight: 600,
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  padding: '8px 16px 4px 16px',
});

// Hook for managing context menu state
export const useContextMenu = () => {
  const [contextMenuState, setContextMenuState] = useState<{
    isOpen: boolean;
    mousePosition: { top: number; left: number } | undefined;
  }>({
    isOpen: false,
    mousePosition: undefined,
  });

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
    setContextMenuState({
      isOpen: true,
      mousePosition: {
        top: event.clientY,
        left: event.clientX,
      },
    });
  };

  const handleCloseContextMenu = () => {
    setContextMenuState({
      isOpen: false,
      mousePosition: undefined,
    });
  };

  return {
    contextMenuState,
    handleContextMenu,
    handleCloseContextMenu,
  };
};

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

        {/* Playlist section (only for track context menus with trackId) */}
        {showPlaylistSection && (
          <>
            <Divider sx={{ borderColor: auroraOpacity.minimal, my: 1 }} />
            <StyledMenuItem disabled>
              <ListItemIcon>
                <PlaylistAdd />
              </ListItemIcon>
              <ListItemText>Add to Playlist</ListItemText>
            </StyledMenuItem>

            {playlists.length > 0 && (
              <>
                <SectionLabel>Your Playlists</SectionLabel>
                {playlists.map((playlist) => (
                  <PlaylistMenuItem
                    key={playlist.id}
                    onClick={() => handleAddToPlaylist(playlist.id, playlist.name)}
                  >
                    {playlist.name} ({playlist.track_count})
                  </PlaylistMenuItem>
                ))}
              </>
            )}

            {onCreatePlaylist && (
              <CreateNewMenuItem onClick={handleCreateNewPlaylist}>
                <Add sx={{ fontSize: '16px', mr: 1 }} />
                Create New Playlist
              </CreateNewMenuItem>
            )}
          </>
        )}
      </StyledMenu>

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

// Predefined context menu configurations

export const getTrackContextActions = (
  trackId: number,
  isLoved: boolean,
  callbacks: {
    onPlay?: () => void;
    onAddToQueue?: () => void;
    onAddToPlaylist?: () => void;
    onToggleLove?: () => void;
    onEditMetadata?: () => void;
    onShowAlbum?: () => void;
    onShowArtist?: () => void;
    onShowInfo?: () => void;
    onDelete?: () => void;
  }
): ContextMenuAction[] => [
  {
    id: 'play',
    label: 'Play Now',
    icon: <PlayArrow fontSize="small" />,
    onClick: callbacks.onPlay || (() => {}),
  },
  {
    id: 'queue',
    label: 'Add to Queue',
    icon: <QueueMusic fontSize="small" />,
    onClick: callbacks.onAddToQueue || (() => {}),
  },
  {
    id: 'playlist',
    label: 'Add to Playlist',
    icon: <PlaylistAdd fontSize="small" />,
    onClick: callbacks.onAddToPlaylist || (() => {}),
    divider: true,
  },
  {
    id: 'love',
    label: isLoved ? 'Remove from Favourites' : 'Add to Favourites',
    icon: isLoved ? <Favorite fontSize="small" /> : <FavoriteBorder fontSize="small" />,
    onClick: callbacks.onToggleLove || (() => {}),
    divider: true,
  },
  {
    id: 'album',
    label: 'Go to Album',
    icon: <AlbumIcon fontSize="small" />,
    onClick: callbacks.onShowAlbum || (() => {}),
  },
  {
    id: 'artist',
    label: 'Go to Artist',
    icon: <Person fontSize="small" />,
    onClick: callbacks.onShowArtist || (() => {}),
  },
  {
    id: 'info',
    label: 'Track Info',
    icon: <Info fontSize="small" />,
    onClick: callbacks.onShowInfo || (() => {}),
  },
  ...(callbacks.onEditMetadata
    ? [
        {
          id: 'edit-metadata',
          label: 'Edit Metadata',
          icon: <Edit fontSize="small" />,
          onClick: callbacks.onEditMetadata,
          divider: callbacks.onDelete ? true : false,
        },
      ]
    : []),
  ...(callbacks.onDelete
    ? [
        {
          id: 'delete',
          label: 'Remove from Library',
          icon: <Delete fontSize="small" />,
          onClick: callbacks.onDelete,
          destructive: true,
        },
      ]
    : []),
];

export const getAlbumContextActions = (
  albumId: number,
  callbacks: {
    onPlay?: () => void;
    onAddToQueue?: () => void;
    onShowArtist?: () => void;
    onEdit?: () => void;
  }
): ContextMenuAction[] => [
  {
    id: 'play',
    label: 'Play Album',
    icon: <PlayArrow fontSize="small" />,
    onClick: callbacks.onPlay || (() => {}),
  },
  {
    id: 'queue',
    label: 'Add to Queue',
    icon: <QueueMusic fontSize="small" />,
    onClick: callbacks.onAddToQueue || (() => {}),
    divider: true,
  },
  {
    id: 'artist',
    label: 'Go to Artist',
    icon: <Person fontSize="small" />,
    onClick: callbacks.onShowArtist || (() => {}),
  },
  {
    id: 'edit',
    label: 'Edit Album',
    icon: <Edit fontSize="small" />,
    onClick: callbacks.onEdit || (() => {}),
  },
];

export const getArtistContextActions = (
  artistId: number,
  callbacks: {
    onPlayAll?: () => void;
    onAddToQueue?: () => void;
    onShowAlbums?: () => void;
    onShowInfo?: () => void;
  }
): ContextMenuAction[] => [
  {
    id: 'play-all',
    label: 'Play All Songs',
    icon: <PlayArrow fontSize="small" />,
    onClick: callbacks.onPlayAll || (() => {}),
  },
  {
    id: 'queue',
    label: 'Add All to Queue',
    icon: <QueueMusic fontSize="small" />,
    onClick: callbacks.onAddToQueue || (() => {}),
    divider: true,
  },
  {
    id: 'albums',
    label: 'Show Albums',
    icon: <AlbumIcon fontSize="small" />,
    onClick: callbacks.onShowAlbums || (() => {}),
  },
  {
    id: 'info',
    label: 'Artist Info',
    icon: <Info fontSize="small" />,
    onClick: callbacks.onShowInfo || (() => {}),
  },
];

export const getPlaylistContextActions = (
  playlistId: string,
  callbacks: {
    onPlay?: () => void;
    onEdit?: () => void;
    onDelete?: () => void;
  }
): ContextMenuAction[] => [
  {
    id: 'play',
    label: 'Play Playlist',
    icon: <PlayArrow fontSize="small" />,
    onClick: callbacks.onPlay || (() => {}),
    divider: true,
  },
  {
    id: 'edit',
    label: 'Edit Playlist',
    icon: <Edit fontSize="small" />,
    onClick: callbacks.onEdit || (() => {}),
  },
  {
    id: 'delete',
    label: 'Delete Playlist',
    icon: <Delete fontSize="small" />,
    onClick: callbacks.onDelete || (() => {}),
    destructive: true,
    divider: true,
  },
];

export default ContextMenu;
