import { useMemo } from 'react';
import { tokens } from '@/design-system';

export type ConnectionStatusType = 'connected' | 'connecting' | 'disconnected';

/**
 * useConnectionStatus - Maps connection status to display color
 *
 * Returns the appropriate status color for the current connection state.
 */
export const useConnectionStatus = (status: ConnectionStatusType) => {
  const statusColor = useMemo(() => {
    switch (status) {
      case 'connected':
        return tokens.colors.status.connected;
      case 'connecting':
        return tokens.colors.status.connecting;
      case 'disconnected':
        return tokens.colors.status.disconnected;
      default:
        return tokens.colors.status.disconnected;
    }
  }, [status]);

  return statusColor;
};
