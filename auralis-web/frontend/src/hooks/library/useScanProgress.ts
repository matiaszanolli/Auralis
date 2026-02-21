/**
 * useScanProgress Hook
 *
 * Subscribes to scan_progress and scan_complete WebSocket messages
 * so components can display live scanning status (fixes #2500).
 */

import { useState } from 'react';
import { useWebSocketSubscription } from '../websocket/useWebSocketSubscription';
import type { ScanProgressMessage, ScanCompleteMessage } from '../../types/websocket';

export interface ScanProgress {
  isScanning: boolean;
  current: number;
  total: number;
  percentage: number;
  currentFile: string | null;
}

const INITIAL_STATE: ScanProgress = {
  isScanning: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentFile: null,
};

/**
 * Subscribe to library scan progress messages from the WebSocket.
 * Returns live scan status that updates as the backend processes files.
 */
export function useScanProgress(): ScanProgress {
  const [state, setState] = useState<ScanProgress>(INITIAL_STATE);

  useWebSocketSubscription(
    ['scan_progress', 'scan_complete'],
    (message) => {
      if (message.type === 'scan_progress') {
        const msg = message as ScanProgressMessage;
        setState({
          isScanning: true,
          current: msg.data.current,
          total: msg.data.total,
          percentage: msg.data.percentage,
          currentFile: msg.data.current_file ?? null,
        });
      } else if (message.type === 'scan_complete') {
        setState(INITIAL_STATE);
      }
    }
  );

  return state;
}
