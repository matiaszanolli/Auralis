/**
 * DraggablePlaylistView.tsx
 *
 * Example component demonstrating drag-and-drop functionality for playlist tracks
 * Shows how to integrate DraggableTrackRow with Droppable for reordering
 */

import React, { useState, useEffect } from 'react';
import { Droppable } from '@hello-pangea/dnd';
import { Box, Paper, Typography, styled } from '@mui/material';
import { DraggableTrackRow } from '../library/DraggableTrackRow';
import { Track } from '../library/TrackRow';
import { useToast } from '../shared/Toast';
import * as playlistService from '../../services/playlistService';

const PlaylistContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
  backgroundColor: theme.palette.background.paper,
  borderRadius: theme.spacing(1),
  maxHeight: '600px',
  overflowY: 'auto',
}));

const PlaylistHeader = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(2),
  paddingBottom: theme.spacing(1),
  borderBottom: `1px solid ${theme.palette.divider}`,
}));

const PlaylistTitle = styled(Typography)(({ theme }) => ({
  fontSize: '1.25rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
}));

const DroppableArea = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'isDraggingOver',
})<{ isDraggingOver?: boolean }>(({ theme, isDraggingOver }) => ({
  minHeight: '100px',
  padding: theme.spacing(1),
  backgroundColor: isDraggingOver
    ? 'rgba(102, 126, 234, 0.05)'
    : 'transparent',
  borderRadius: theme.spacing(1),
  transition: 'background-color 0.2s ease',
}));

const EmptyPlaylist = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: theme.spacing(4),
  color: theme.palette.text.secondary,
  fontSize: '0.875rem',
}));

interface DraggablePlaylistViewProps {
  playlistId: number;
  playlistName: string;
  onTrackPlay?: (trackId: number) => void;
}

export const DraggablePlaylistView: React.FC<DraggablePlaylistViewProps> = ({
  playlistId,
  playlistName,
  onTrackPlay,
}) => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentTrackId, setCurrentTrackId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const { success, error } = useToast();

  useEffect(() => {
    loadPlaylistTracks();
  }, [playlistId]);

  const loadPlaylistTracks = async () => {
    try {
      setLoading(true);
      const playlistTracks = await playlistService.getPlaylistTracks(playlistId);
      setTracks(playlistTracks);
    } catch (err) {
      error(`Failed to load playlist tracks: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTrackPlay = (trackId: number) => {
    setCurrentTrackId(trackId);
    setIsPlaying(true);
    if (onTrackPlay) {
      onTrackPlay(trackId);
    }
  };

  const handleTrackReorder = async (fromIndex: number, toIndex: number) => {
    // Optimistically update UI
    const reorderedTracks = Array.from(tracks);
    const [movedTrack] = reorderedTracks.splice(fromIndex, 1);
    reorderedTracks.splice(toIndex, 0, movedTrack);
    setTracks(reorderedTracks);

    try {
      // Call API to persist the new order
      await playlistService.reorderPlaylistTrack(playlistId, fromIndex, toIndex);
      success('Track reordered');
    } catch (err) {
      error(`Failed to reorder track: ${err}`);
      // Revert on error
      loadPlaylistTracks();
    }
  };

  return (
    <PlaylistContainer elevation={2}>
      <PlaylistHeader>
        <PlaylistTitle>{playlistName}</PlaylistTitle>
        <Typography variant="caption" color="text.secondary">
          {tracks.length} {tracks.length === 1 ? 'track' : 'tracks'}
        </Typography>
      </PlaylistHeader>

      <Droppable droppableId={`playlist-content-${playlistId}`} type="TRACK">
        {(provided, snapshot) => (
          <DroppableArea
            ref={provided.innerRef}
            {...provided.droppableProps}
            isDraggingOver={snapshot.isDraggingOver}
          >
            {loading ? (
              <EmptyPlaylist>Loading tracks...</EmptyPlaylist>
            ) : tracks.length === 0 ? (
              <EmptyPlaylist>
                This playlist is empty. Drag tracks here to add them.
              </EmptyPlaylist>
            ) : (
              tracks.map((track, index) => (
                <DraggableTrackRow
                  key={track.id}
                  track={track}
                  index={index}
                  draggableId={`track-${track.id}`}
                  isPlaying={isPlaying && currentTrackId === track.id}
                  isCurrent={currentTrackId === track.id}
                  showDragHandle={true}
                  onPlay={handleTrackPlay}
                  onPause={() => setIsPlaying(false)}
                />
              ))
            )}
            {provided.placeholder}
          </DroppableArea>
        )}
      </Droppable>
    </PlaylistContainer>
  );
};
