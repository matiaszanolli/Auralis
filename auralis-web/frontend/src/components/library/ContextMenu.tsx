import React from 'react';
import {
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider
} from '@mui/material';
import {
  PlayArrow,
  PlaylistAdd,
  QueueMusic,
  Favorite,
  FavoriteBorder,
  Info,
  Album as AlbumIcon,
  Person as PersonIcon,
  Share,
  Delete
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  divider?: boolean;
  disabled?: boolean;
  destructive?: boolean;
}

interface ContextMenuProps {
  anchorEl: HTMLElement | null;
  open: boolean;
  onClose: () => void;
  onAction: (actionId: string) => void;
  entityType: 'track' | 'album' | 'artist' | 'playlist';
  isFavorite?: boolean;
}

const StyledMenu = styled(Menu)(({ theme }) => ({
  '& .MuiPaper-root': {
    background: 'rgba(26, 31, 58, 0.98)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: theme.spacing(1.5),
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    minWidth: 220
  }
}));

const StyledMenuItem = styled(MenuItem)(({ theme }) => ({
  padding: theme.spacing(1.5, 2),
  borderRadius: theme.spacing(0.5),
  margin: theme.spacing(0.5, 1),
  '&:hover': {
    backgroundColor: 'rgba(102, 126, 234, 0.1)',
    '& .MuiListItemIcon-root': {
      color: '#667eea'
    },
    '& .MuiListItemText-primary': {
      color: '#667eea'
    }
  },
  '&.destructive': {
    '& .MuiListItemIcon-root': {
      color: theme.palette.error.main
    },
    '& .MuiListItemText-primary': {
      color: theme.palette.error.main
    },
    '&:hover': {
      backgroundColor: 'rgba(239, 68, 68, 0.1)',
      '& .MuiListItemIcon-root': {
        color: theme.palette.error.light
      },
      '& .MuiListItemText-primary': {
        color: theme.palette.error.light
      }
    }
  }
}));

const MenuItemIcon = styled(ListItemIcon)(({ theme }) => ({
  minWidth: 36,
  color: theme.palette.text.secondary
}));

export const ContextMenu: React.FC<ContextMenuProps> = ({
  anchorEl,
  open,
  onClose,
  onAction,
  entityType,
  isFavorite = false
}) => {
  const handleAction = (actionId: string) => {
    onAction(actionId);
    onClose();
  };

  const getActions = (): ContextMenuAction[] => {
    const baseActions: ContextMenuAction[] = [
      {
        id: 'play',
        label: 'Play Now',
        icon: <PlayArrow />
      },
      {
        id: 'add_to_queue',
        label: 'Add to Queue',
        icon: <QueueMusic />
      },
      {
        id: 'add_to_playlist',
        label: 'Add to Playlist',
        icon: <PlaylistAdd />,
        divider: true
      }
    ];

    if (entityType === 'track' || entityType === 'album') {
      baseActions.push({
        id: isFavorite ? 'remove_favorite' : 'add_favorite',
        label: isFavorite ? 'Remove from Favorites' : 'Add to Favorites',
        icon: isFavorite ? <Favorite /> : <FavoriteBorder />,
        divider: true
      });
    }

    if (entityType === 'track') {
      baseActions.push(
        {
          id: 'go_to_album',
          label: 'Go to Album',
          icon: <AlbumIcon />
        },
        {
          id: 'go_to_artist',
          label: 'Go to Artist',
          icon: <PersonIcon />,
          divider: true
        }
      );
    }

    if (entityType === 'album') {
      baseActions.push({
        id: 'go_to_artist',
        label: 'Go to Artist',
        icon: <PersonIcon />,
        divider: true
      });
    }

    baseActions.push(
      {
        id: 'show_info',
        label: 'Show Info',
        icon: <Info />
      },
      {
        id: 'share',
        label: 'Share',
        icon: <Share />,
        divider: true
      }
    );

    if (entityType === 'playlist') {
      baseActions.push({
        id: 'delete',
        label: 'Delete Playlist',
        icon: <Delete />,
        destructive: true
      });
    }

    return baseActions;
  };

  const actions = getActions();

  return (
    <StyledMenu
      anchorEl={anchorEl}
      open={open}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'right'
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'right'
      }}
    >
      {actions.map((action, index) => (
        <React.Fragment key={action.id}>
          <StyledMenuItem
            onClick={() => handleAction(action.id)}
            disabled={action.disabled}
            className={action.destructive ? 'destructive' : ''}
          >
            <MenuItemIcon>{action.icon}</MenuItemIcon>
            <ListItemText primary={action.label} />
          </StyledMenuItem>
          {action.divider && index < actions.length - 1 && (
            <Divider sx={{ my: 0.5, borderColor: 'rgba(255,255,255,0.05)' }} />
          )}
        </React.Fragment>
      ))}
    </StyledMenu>
  );
};

export default ContextMenu;
