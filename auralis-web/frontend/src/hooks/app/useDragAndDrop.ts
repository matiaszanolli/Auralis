/**
 * useDragAndDrop.ts
 *
 * Custom hook for drag-and-drop functionality using @hello-pangea/dnd
 * Provides reusable logic for drag-and-drop interactions across the application
 */

import { DragStart, DragUpdate, DropResult } from '@hello-pangea/dnd';
import { useState, useCallback } from 'react';

export interface DragDropState {
  isDragging: boolean;
  draggedItemId: string | null;
  draggedItemType: 'track' | 'playlist' | null;
}

export interface UseDragAndDropOptions {
  onDragStart?: (result: DragStart) => void;
  onDragUpdate?: (result: DragUpdate) => void;
  onDragEnd?: (result: DropResult) => void;
}

/**
 * Hook for managing drag-and-drop state and callbacks
 */
export const useDragAndDrop = (options: UseDragAndDropOptions = {}) => {
  const [dragState, setDragState] = useState<DragDropState>({
    isDragging: false,
    draggedItemId: null,
    draggedItemType: null,
  });

  const handleDragStart = useCallback((result: DragStart) => {
    const itemType = result.source.droppableId.includes('track') ? 'track' : 'playlist';

    setDragState({
      isDragging: true,
      draggedItemId: result.draggableId,
      draggedItemType: itemType,
    });

    options.onDragStart?.(result);
  }, [options]);

  const handleDragUpdate = useCallback((result: DragUpdate) => {
    options.onDragUpdate?.(result);
  }, [options]);

  const handleDragEnd = useCallback((result: DropResult) => {
    setDragState({
      isDragging: false,
      draggedItemId: null,
      draggedItemType: null,
    });

    options.onDragEnd?.(result);
  }, [options]);

  return {
    dragState,
    handleDragStart,
    handleDragUpdate,
    handleDragEnd,
  };
};

/**
 * Helper function to reorder items in an array
 */
export const reorder = <T,>(
  list: T[],
  startIndex: number,
  endIndex: number
): T[] => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);
  return result;
};

/**
 * Helper function to move item between lists
 */
export const move = <T,>(
  source: T[],
  destination: T[],
  droppableSource: { index: number; droppableId: string },
  droppableDestination: { index: number; droppableId: string }
): { [key: string]: T[] } => {
  const sourceClone = Array.from(source);
  const destClone = Array.from(destination);
  const [removed] = sourceClone.splice(droppableSource.index, 1);

  destClone.splice(droppableDestination.index, 0, removed);

  const result: { [key: string]: T[] } = {};
  result[droppableSource.droppableId] = sourceClone;
  result[droppableDestination.droppableId] = destClone;

  return result;
};

/**
 * Get drag handle props with consistent styling
 */
export const getDragHandleProps = (isDragging: boolean) => ({
  style: {
    cursor: isDragging ? 'grabbing' : 'grab',
    opacity: isDragging ? 0.5 : 1,
    transition: 'opacity 0.2s ease',
  },
});

/**
 * Get droppable area props with highlight styling
 */
export const getDroppableProps = (isDraggingOver: boolean, isDraggingItem: boolean) => ({
  style: {
    background: isDraggingOver
      ? 'rgba(102, 126, 234, 0.1)'
      : isDraggingItem
        ? 'rgba(102, 126, 234, 0.05)'
        : 'transparent',
    transition: 'background 0.2s ease',
    borderRadius: '8px',
  },
});
