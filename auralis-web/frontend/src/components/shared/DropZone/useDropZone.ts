import { useState, useCallback, useRef } from 'react';

interface UseDropZoneReturn {
  isDragging: boolean;
  handleDragEnter: (e: React.DragEvent) => void;
  handleDragLeave: (e: React.DragEvent) => void;
  handleDragOver: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent, callback: (path: string) => void) => void;
}

/**
 * Hook for managing drag-and-drop state and handlers
 *
 * Handles:
 * - Drag enter/leave/over events with proper counter logic
 * - Drop event processing for files and folders
 * - Path extraction from dropped items
 * - Disabled and scanning state handling
 */
export const useDropZone = (
  disabled: boolean = false,
  scanning: boolean = false
): UseDropZoneReturn => {
  const [isDragging, setIsDragging] = useState(false);
  // Nested dragenter/dragleave pairs, never rendered, so a ref: its updates (and the
  // setIsDragging that follows the last leave) stay out of state updater functions (#6429).
  const dragCounterRef = useRef(0);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    dragCounterRef.current += 1;

    // Check if we're dragging files
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, [disabled, scanning]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    // Clamped: an unpaired leave must not leave the counter below 0, which never
    // reaches 0 again and would pin isDragging on.
    dragCounterRef.current = Math.max(0, dragCounterRef.current - 1);
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, [disabled, scanning]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled || scanning) return;

    // Set dropEffect to indicate this is a copy operation
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy';
    }
  }, [disabled, scanning]);

  const handleDrop = useCallback((e: React.DragEvent, callback: (path: string) => void) => {
    e.preventDefault();
    e.stopPropagation();

    setIsDragging(false);
    dragCounterRef.current = 0;

    if (disabled || scanning) return;

    // Get dropped files/folders
    const items = Array.from(e.dataTransfer.items);

    // Process the first item (should be a folder)
    if (items.length > 0) {
      const item = items[0];

      // Check if it's a file or directory
      if (item.kind === 'file') {
        const entry = item.webkitGetAsEntry();

        if (entry && entry.isDirectory) {
          // Get the full path. #4664: no cast needed — webkitGetAsEntry()
          // already returns FileSystemEntry, which declares `fullPath` in
          // lib.dom. The `as any` was hiding a type that was there all along.
          const folderPath = entry.fullPath || entry.name;
          callback(folderPath);
        } else if (entry && entry.isFile) {
          // If it's a file, get its parent directory
          const file = item.getAsFile();
          if (file) {
            // Extract folder path from file path
            const pathParts = file.webkitRelativePath || file.name;
            const folderPath = pathParts.substring(0, pathParts.lastIndexOf('/')) || './';
            callback(folderPath);
          }
        }
      }
    }
  }, [disabled, scanning]);

  return {
    isDragging,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
  };
};

export default useDropZone;
