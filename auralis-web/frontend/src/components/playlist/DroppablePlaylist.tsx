/**
 * DroppablePlaylist - Droppable playlist item that accepts track drops
 *
 * Used in PlaylistList for drag-and-drop functionality.
 * Provides visual feedback when dragging tracks over the playlist.
 *
 * Features:
 * - Drag-and-drop support for adding tracks to playlists
 * - Visual feedback on drag over state
 * - Selection highlight support
 * - Context menu support for playlist actions
 *
 * @example
 * <DroppablePlaylist
 *   playlistId={playlist.id}
 *   playlistName={playlist.name}
 *   trackCount={playlist.track_count}
 *   selected={isSelected}
 *   onClick={() => selectPlaylist(playlist)}
 *   onContextMenu={handleContextMenu}
 * />
 */

import React from 'react';
import { Droppable } from '@hello-pangea/dnd';
import {
  StyledListItemButton,
  DroppableContainer,
  PlaceholderContainer,
} from './DroppablePlaylist.styles';
import { PlaylistItemContent } from './PlaylistItemContent';
import { PlaylistDropIndicator } from './PlaylistDropIndicator';

interface DroppablePlaylistProps {
  playlistId: number;
  playlistName: string;
  trackCount: number;
  selected?: boolean;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
}

export const DroppablePlaylist: React.FC<DroppablePlaylistProps> = ({
  playlistId,
  playlistName,
  trackCount,
  selected = false,
  onClick,
  onContextMenu,
}) => {
  const droppableId = `playlist-${playlistId}`;

  return (
    <Droppable droppableId={droppableId} type="TRACK">
      {(provided, snapshot) => (
        <DroppableContainer
          ref={provided.innerRef}
          {...provided.droppableProps}
        >
          <StyledListItemButton
            selected={selected}
            isDraggingOver={snapshot.isDraggingOver}
            onClick={onClick}
            onContextMenu={onContextMenu}
          >
            <PlaylistItemContent
              playlistName={playlistName}
              trackCount={trackCount}
            />
          </StyledListItemButton>

          <PlaylistDropIndicator visible={snapshot.isDraggingOver} />

          {/* Hidden placeholder for dnd */}
          <PlaceholderContainer>{provided.placeholder}</PlaceholderContainer>
        </DroppableContainer>
      )}
    </Droppable>
  );
};
