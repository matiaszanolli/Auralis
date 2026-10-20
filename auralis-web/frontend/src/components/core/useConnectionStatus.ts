import { useMemo } from 'react';
import { tokens } from '@/design-system';
import type { ConnectionStatus } from '@/hooks/websocket/websocketConnectionCore';

export type ConnectionStatusType = ConnectionStatus;

/**
 * useConnectionStatus - Maps connection status to display color
 *
 * Returns the appropriate status color for the current connection state.
 * 'error' (permanent failure: reconnect budget exhausted or a policy close
 * code, #5469) shares the disconnected red — the connection is down either
 * way — but stays a distinct state so future UI can offer a reconnect action.
 */
export const useConnectionStatus = (status: ConnectionStatusType) => {
  const statusColor = useMemo(() => {
    switch (status) {
      case 'connected':
        return tokens.colors.status.connected;
      case 'connecting':
        return tokens.colors.status.connecting;
      case 'disconnected':
      case 'error':
        return tokens.colors.status.disconnected;
      default:
        return tokens.colors.status.disconnected;
    }
  }, [status]);

  return statusColor;
};
