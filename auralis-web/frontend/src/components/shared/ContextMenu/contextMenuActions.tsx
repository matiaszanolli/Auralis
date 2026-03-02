/**
 * Context Menu Actions
 *
 * Predefined action configurations for different context menu types:
 * - Track context menu
 * - Album context menu
 * - Artist context menu
 * - Playlist context menu
 */

import React from 'react';
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
  Explore, // Phase 5: Find Similar Tracks icon
} from '@mui/icons-material';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon?: React.ReactNode;
  divider?: boolean;
  destructive?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

/**
 * Generate track context menu actions
 */
export const getTrackContextActions = (
  _trackId: number,
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
    onFindSimilar?: () => void; // Phase 5: Find similar tracks callback
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
    id: 'similar',
    label: 'Find Similar Tracks',
    icon: <Explore fontSize="small" />,
    onClick: callbacks.onFindSimilar || (() => {}),
    divider: true, // Phase 5: Separator before Track Info
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

/**
 * Generate album context menu actions
 */
export const getAlbumContextActions = (
  _albumId: number,
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

/**
 * Generate artist context menu actions
 */
export const getArtistContextActions = (
  _artistId: number,
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

/**
 * Generate playlist context menu actions
 */
export const getPlaylistContextActions = (
  _playlistId: string,
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
