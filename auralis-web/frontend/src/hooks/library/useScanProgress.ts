/**
 * useScanProgress Hook
 *
 * Subscribes to scan lifecycle WebSocket messages so components can display
 * live scanning status and last scan results.
 */

import { useState } from 'react';
import { useWebSocketSubscription } from '../websocket/useWebSocketSubscription';
import type {
  ScanProgressMessage,
  ScanCompleteMessage,
  LibraryTracksRemovedMessage,
} from '../../types/websocket';

export interface ScanProgress {
  isScanning: boolean;
  current: number;
  total: number;
  percentage: number;
  currentFile: string | null;
}

export interface ScanResult {
  filesAdded: number;
  filesRemoved: number;
  duration: number;
}

export interface ScanStatus extends ScanProgress {
  lastResult: ScanResult | null;
}

const INITIAL_STATE: ScanStatus = {
  isScanning: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentFile: null,
  lastResult: null,
};

/**
 * Subscribe to library scan lifecycle messages from the WebSocket.
 * Returns live scan status and the result of the most recent completed scan.
 */
export function useScanProgress(): ScanStatus {
  const [state, setState] = useState<ScanStatus>(INITIAL_STATE);

  useWebSocketSubscription(
    ['library_scan_started', 'scan_progress', 'scan_complete', 'library_tracks_removed'],
    (message) => {
      if (message.type === 'library_scan_started') {
        setState((prev) => ({
          ...INITIAL_STATE,
          lastResult: prev.lastResult,
          isScanning: true,
        }));
      } else if (message.type === 'scan_progress') {
        const msg = message as ScanProgressMessage;
        setState((prev) => ({
          ...prev,
          isScanning: true,
          current: msg.data.current,
          total: msg.data.total,
          percentage: msg.data.percentage,
          currentFile: msg.data.current_file ?? null,
        }));
      } else if (message.type === 'scan_complete') {
        const msg = message as ScanCompleteMessage;
        setState((prev) => ({
          ...INITIAL_STATE,
          lastResult: {
            filesAdded: msg.data.files_added ?? 0,
            filesRemoved: prev.lastResult?.filesRemoved ?? 0,
            duration: msg.data.duration,
          },
        }));
      } else if (message.type === 'library_tracks_removed') {
        const msg = message as LibraryTracksRemovedMessage;
        setState((prev) => ({
          ...prev,
          lastResult: prev.lastResult
            ? { ...prev.lastResult, filesRemoved: msg.data.count }
            : { filesAdded: 0, filesRemoved: msg.data.count, duration: 0 },
        }));
      }
    }
  );

  return state;
}
