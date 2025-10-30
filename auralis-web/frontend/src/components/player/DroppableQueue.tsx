/**
 * DroppableQueue.tsx
 *
 * Droppable queue area that accepts track drops and supports reordering
 * Used in player for drag-and-drop queue management
 */

import React from 'react';
import { Droppable } from '@hello-pangea/dnd';
import { styled } from '@mui/material/styles';
import { Box, Typography, Paper } from '@mui/material';
import QueueMusicIcon from '@mui/icons-material/QueueMusic';

const QueueContainer = styled(Paper, {
  shouldForwardProp: (prop) => prop !== 'isDraggingOver',
})<{ isDraggingOver?: boolean }>(({ theme, isDraggingOver }) => ({
  padding: theme.spacing(2),
  backgroundColor: isDraggingOver
    ? 'rgba(102, 126, 234, 0.1)'
    : theme.palette.background.paper,
  border: isDraggingOver
    ? '2px dashed rgba(102, 126, 234, 0.5)'
    : `1px solid ${theme.palette.divider}`,
  borderRadius: theme.spacing(1),
  transition: 'all 0.2s ease',
  minHeight: '200px',
  maxHeight: '400px',
  overflowY: 'auto',
}));

const QueueHeader = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  marginBottom: theme.spacing(2),
  paddingBottom: theme.spacing(1),
  borderBottom: `1px solid ${theme.palette.divider}`,
}));

const QueueIcon = styled(QueueMusicIcon)(({ theme }) => ({
  marginRight: theme.spacing(1),
  color: theme.palette.text.secondary,
}));

const QueueTitle = styled(Typography)(({ theme }) => ({
  fontSize: '1rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
}));

const EmptyState = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: theme.spacing(4),
  color: theme.palette.text.secondary,
}));

const EmptyStateIcon = styled(QueueMusicIcon)(({ theme }) => ({
  fontSize: '3rem',
  marginBottom: theme.spacing(2),
  opacity: 0.3,
}));

const EmptyStateText = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  textAlign: 'center',
}));

const DropIndicator = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: theme.spacing(3),
  backgroundColor: 'rgba(102, 126, 234, 0.05)',
  borderRadius: theme.spacing(1),
  marginBottom: theme.spacing(1),
}));

const DropIndicatorText = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.main,
  fontWeight: 600,
  fontSize: '0.875rem',
}));

interface DroppableQueueProps {
  queueLength: number;
  children?: React.ReactNode;
  showHeader?: boolean;
}

export const DroppableQueue: React.FC<DroppableQueueProps> = ({
  queueLength,
  children,
  showHeader = true,
}) => {
  return (
    <Droppable droppableId="queue" type="TRACK">
      {(provided, snapshot) => (
        <QueueContainer
          ref={provided.innerRef}
          {...provided.droppableProps}
          isDraggingOver={snapshot.isDraggingOver}
          elevation={2}
        >
          {showHeader && (
            <QueueHeader>
              <QueueIcon />
              <QueueTitle>
                Queue {queueLength > 0 && `(${queueLength})`}
              </QueueTitle>
            </QueueHeader>
          )}

          {snapshot.isDraggingOver && (
            <DropIndicator>
              <DropIndicatorText>Drop to add to queue</DropIndicatorText>
            </DropIndicator>
          )}

          {queueLength === 0 && !snapshot.isDraggingOver ? (
            <EmptyState>
              <EmptyStateIcon />
              <EmptyStateText>
                Drag tracks here to add them to the queue
              </EmptyStateText>
            </EmptyState>
          ) : (
            <Box>{children}</Box>
          )}

          {provided.placeholder}
        </QueueContainer>
      )}
    </Droppable>
  );
};
