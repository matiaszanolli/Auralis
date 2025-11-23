import React from 'react';
import { DropIndicator, DropIndicatorText } from './DroppablePlaylist.styles';

interface PlaylistDropIndicatorProps {
  visible: boolean;
}

/**
 * PlaylistDropIndicator - Shows visual feedback when dragging tracks over playlist
 *
 * Features:
 * - Visible only when dragging tracks over the droppable area
 * - Aurora-styled dashed border
 * - Centered "Drop to add tracks" text
 */
export const PlaylistDropIndicator: React.FC<PlaylistDropIndicatorProps> = ({ visible }) => {
  if (!visible) return null;

  return (
    <DropIndicator>
      <DropIndicatorText>Drop to add tracks</DropIndicatorText>
    </DropIndicator>
  );
};

export default PlaylistDropIndicator;
