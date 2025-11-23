import { useMemo } from 'react';
import { statusColors } from '../library/Color.styles';

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
        return statusColors.connected;
      case 'connecting':
        return statusColors.connecting;
      case 'disconnected':
        return statusColors.disconnected;
      default:
        return statusColors.disconnected;
    }
  }, [status]);

  return statusColor;
};
