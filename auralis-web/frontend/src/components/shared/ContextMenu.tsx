import React, { useState, useEffect, useRef } from 'react';
import { Menu, MenuItem, ListItemIcon, ListItemText, Divider, styled } from '@mui/material';
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
} from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';
import { cardShadows } from '../library/Shadow.styles';
import { radiusMedium, radiusSmall } from '../library/BorderRadius.styles';

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
}

const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: colors.background.secondary,
    border: `1px solid rgba(102, 126, 234, 0.2)`,
    boxShadow: cardShadows.dropdownDark,
    borderRadius: radiusMedium,
    minWidth: '220px',
    padding: '4px',
    backdropFilter: 'blur(12px)',
  },
});

const StyledMenuItem = styled(MenuItem)<{ destructive?: boolean }>(({ destructive }) => ({
  borderRadius: radiusSmall,
  padding: '10px 12px',
  margin: '2px 0',
  fontSize: '14px',
  color: destructive ? '#ff4757' : colors.text.primary,
  transition: 'all 0.2s ease',

  '&:hover': {
    background: destructive
      ? 'rgba(255, 71, 87, 0.1)'
      : 'rgba(102, 126, 234, 0.15)',
  },

  '&.Mui-disabled': {
    color: colors.text.disabled,
    opacity: 0.5,
  },

  '& .MuiListItemIcon-root': {
    color: destructive ? '#ff4757' : colors.text.secondary,
    minWidth: 36,
  },
}));

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
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

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

  return (
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
            <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)', my: 1 }} />
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
    </StyledMenu>
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
