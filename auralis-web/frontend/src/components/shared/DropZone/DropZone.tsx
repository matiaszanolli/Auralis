/**
 * DropZone Component
 * ~~~~~~~~~~~~~~~~~~
 *
 * Drag-and-drop zone for folder import.
 * Supports both drag-and-drop and click-to-browse functionality.
 *
 * Icon and text content extracted to separate components.
 */

import React, { useCallback, useRef } from 'react';
import { DropZonePaper } from './DropZoneStyles';
import { useDropZone } from './useDropZone';
import { DropZoneIcon } from './DropZoneIcon';
import { DropZoneText } from './DropZoneText';

export interface DropZoneProps {
  onFolderDrop: (folderPath: string) => void;
  onFolderSelect?: (folderPath: string) => void;
  disabled?: boolean;
  scanning?: boolean;
}

/**
 * DropZone - Drag-and-drop area for music folder import
 *
 * Features:
 * - Drag-and-drop support for folders and files
 * - Click-to-browse fallback for browsers without drag-drop
 * - Visual feedback during dragging
 * - Scanning state indication
 * - Smooth animations and transitions
 *
 * @example
 * ```tsx
 * <DropZone
 *   onFolderDrop={handleFolderDrop}
 *   onFolderSelect={handleFolderSelect}
 *   scanning={isScanning}
 * />
 * ```
 */
export const DropZone: React.FC<DropZoneProps> = ({
  onFolderDrop,
  onFolderSelect,
  disabled = false,
  scanning = false,
}) => {
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop } =
    useDropZone(disabled, scanning);

  const handleDropWrapper = useCallback(
    (e: React.DragEvent) => {
      handleDrop(e, onFolderDrop);
    },
    [handleDrop, onFolderDrop]
  );

  const handleClick = useCallback(() => {
    if (disabled || scanning) return;

    // Trigger folder selection dialog
    if (onFolderSelect) {
      // In web browser, show input prompt
      const folderPath = prompt('Enter folder path to scan:');
      if (folderPath) {
        onFolderSelect(folderPath);
      }
    }
  }, [disabled, scanning, onFolderSelect]);

  return (
    <DropZonePaper
      ref={dropZoneRef}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDropWrapper}
      onClick={handleClick}
      $isDragging={isDragging}
      $disabled={disabled}
      $scanning={scanning}
    >
      <DropZoneIcon isDragging={isDragging} scanning={scanning} />
      <DropZoneText isDragging={isDragging} scanning={scanning} />
    </DropZonePaper>
  );
};

export default DropZone;
