/**
 * Context Menu Actions
 *
 * Predefined action configurations for different context menu types:
 * - Track context menu
 * - Artist context menu
 * - Playlist context menu
 */

import { ReactNode } from 'react';
import PlayArrow from '@mui/icons-material/PlayArrow';
import QueueMusic from '@mui/icons-material/QueueMusic';
import Favorite from '@mui/icons-material/Favorite';
import FavoriteBorder from '@mui/icons-material/FavoriteBorder';
import Info from '@mui/icons-material/Info';
import Delete from '@mui/icons-material/Delete';
import Edit from '@mui/icons-material/Edit';
import AlbumIcon from '@mui/icons-material/Album';
import Person from '@mui/icons-material/Person';
import Explore from '@mui/icons-material/Explore';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Draw a separator above this item (the renderer skips it on the first). */
  divider?: boolean;
  destructive?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

/**
 * Keep only the actions that exist. Every generator below builds an entry only
 * when its callback was supplied: an entry whose handler was a `() => {}`
 * fallback rendered as a live menu item that closed the menu and did nothing
 * (#5614).
 */
const present = (
  ...actions: (ContextMenuAction | false | undefined)[]
): ContextMenuAction[] => actions.filter((action): action is ContextMenuAction => Boolean(action));

/**
 * Generate track context menu actions
 *
 * "Add to Playlist" is not an entry here: ContextMenu renders it, with the
 * user's playlists, as its own section below these actions.
 */
export const getTrackContextActions = (
  isLoved: boolean,
  callbacks: {
    onPlay?: () => void;
    onAddToQueue?: () => void;
    onToggleLove?: () => void;
    onEditMetadata?: () => void;
    onShowAlbum?: () => void;
    onShowArtist?: () => void;
    onShowInfo?: () => void;
    onFindSimilar?: () => void; // Phase 5: Find similar tracks callback
    onDelete?: () => void;
  }
): ContextMenuAction[] =>
  present(
    callbacks.onPlay && {
      id: 'play',
      label: 'Play Now',
      icon: <PlayArrow fontSize="small" />,
      onClick: callbacks.onPlay,
    },
    callbacks.onAddToQueue && {
      id: 'queue',
      label: 'Add to Queue',
      icon: <QueueMusic fontSize="small" />,
      onClick: callbacks.onAddToQueue,
    },
    callbacks.onToggleLove && {
      id: 'love',
      label: isLoved ? 'Remove from Favourites' : 'Add to Favourites',
      icon: isLoved ? <Favorite fontSize="small" /> : <FavoriteBorder fontSize="small" />,
      onClick: callbacks.onToggleLove,
      divider: true,
    },
    callbacks.onShowAlbum && {
      id: 'album',
      label: 'Go to Album',
      icon: <AlbumIcon fontSize="small" />,
      onClick: callbacks.onShowAlbum,
    },
    callbacks.onShowArtist && {
      id: 'artist',
      label: 'Go to Artist',
      icon: <Person fontSize="small" />,
      onClick: callbacks.onShowArtist,
    },
    callbacks.onFindSimilar && {
      id: 'similar',
      label: 'Find Similar Tracks',
      icon: <Explore fontSize="small" />,
      onClick: callbacks.onFindSimilar,
      divider: true, // Phase 5: Separator before Track Info
    },
    callbacks.onShowInfo && {
      id: 'info',
      label: 'Track Info',
      icon: <Info fontSize="small" />,
      onClick: callbacks.onShowInfo,
    },
    callbacks.onEditMetadata && {
      id: 'edit-metadata',
      label: 'Edit Metadata',
      icon: <Edit fontSize="small" />,
      onClick: callbacks.onEditMetadata,
      divider: Boolean(callbacks.onDelete),
    },
    callbacks.onDelete && {
      id: 'delete',
      label: 'Remove from Library',
      icon: <Delete fontSize="small" />,
      onClick: callbacks.onDelete,
      destructive: true,
    }
  );

/**
 * Generate artist context menu actions
 */
export const getArtistContextActions = (
  callbacks: {
    onPlayAll?: () => void;
    onAddToQueue?: () => void;
    onShowAlbums?: () => void;
    onShowInfo?: () => void;
  }
): ContextMenuAction[] =>
  present(
    callbacks.onPlayAll && {
      id: 'play-all',
      label: 'Play All Songs',
      icon: <PlayArrow fontSize="small" />,
      onClick: callbacks.onPlayAll,
    },
    callbacks.onAddToQueue && {
      id: 'queue',
      label: 'Add All to Queue',
      icon: <QueueMusic fontSize="small" />,
      onClick: callbacks.onAddToQueue,
      divider: true,
    },
    callbacks.onShowAlbums && {
      id: 'albums',
      label: 'Show Albums',
      icon: <AlbumIcon fontSize="small" />,
      onClick: callbacks.onShowAlbums,
    },
    callbacks.onShowInfo && {
      id: 'info',
      label: 'Artist Info',
      icon: <Info fontSize="small" />,
      onClick: callbacks.onShowInfo,
    }
  );

/**
 * Generate playlist context menu actions
 */
export const getPlaylistContextActions = (
  callbacks: {
    onPlay?: () => void;
    onEdit?: () => void;
    onDelete?: () => void;
  }
): ContextMenuAction[] =>
  present(
    callbacks.onPlay && {
      id: 'play',
      label: 'Play Playlist',
      icon: <PlayArrow fontSize="small" />,
      onClick: callbacks.onPlay,
      divider: true,
    },
    callbacks.onEdit && {
      id: 'edit',
      label: 'Edit Playlist',
      icon: <Edit fontSize="small" />,
      onClick: callbacks.onEdit,
    },
    callbacks.onDelete && {
      id: 'delete',
      label: 'Delete Playlist',
      icon: <Delete fontSize="small" />,
      onClick: callbacks.onDelete,
      destructive: true,
      divider: true,
    }
  );
