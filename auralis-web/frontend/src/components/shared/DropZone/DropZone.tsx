/**
 * DropZone Component
 * ~~~~~~~~~~~~~~~~~~
 *
 * Drag-and-drop zone for folder import.
 * Supports both drag-and-drop and click-to-browse functionality.
 *
 * Icon and text content extracted to separate components.
 */

import React, { useCallback, useRef, type KeyboardEvent } from 'react';
import { DropZonePaper } from './DropZoneStyles';
import { useDropZone } from './useDropZone';
import { DropZoneIcon } from './DropZoneIcon';
import { DropZoneText } from './DropZoneText';
import { getElectronAPI } from '@/utils/electron';

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
export const DropZone = ({
  onFolderDrop,
  onFolderSelect,
  disabled = false,
  scanning = false,
}: DropZoneProps) => {
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop } =
    useDropZone(disabled, scanning);

  const handleDropWrapper = useCallback(
    (e: React.DragEvent) => {
      handleDrop(e, onFolderDrop);
    },
    [handleDrop, onFolderDrop]
  );

  const handleClick = useCallback(async () => {
    if (disabled || scanning) return;
    if (!onFolderSelect) return;

    // Use Electron folder picker if available
    const electronAPI = getElectronAPI();
    if (electronAPI?.selectFolder) {
      try {
        const result = await electronAPI.selectFolder();
        if (result?.[0]) {
          onFolderSelect(result[0]);
        }
      } catch (err) {
        console.error('Folder picker failed:', err);
      }
    }
    // prompt() is not supported in Electron — omit the web fallback
    // since this app runs exclusively as a desktop Electron app.
  }, [disabled, scanning, onFolderSelect]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleClick();
      }
    },
    [handleClick]
  );

  return (
    <DropZonePaper
      ref={dropZoneRef}
      tabIndex={disabled ? -1 : 0}
      role="button"
      aria-label={scanning ? 'Scanning music folder' : 'Drop a music folder here or press to browse'}
      aria-disabled={disabled || undefined}
      aria-busy={scanning || undefined}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDropWrapper}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
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
