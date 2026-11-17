/**
 * Retry a WebSocket connection that gave up when the network comes back (#5917).
 *
 * After the manager exhausts its attempts the singleton is retired and nothing else would ever retry,
 * so the app stayed offline until a reload. The `online` event, or the window becoming visible again, is
 * the cue to build a fresh connection. Armed only while `gaveUp` is true.
 */

import { useEffect } from 'react';

export function useReconnectOnNetwork(gaveUp: boolean, connect: () => Promise<void>): void {
  useEffect(() => {
    if (!gaveUp) return undefined;
    const retry = () => {
      if (document.visibilityState === 'hidden') return;
      void connect();
    };
    window.addEventListener('online', retry);
    document.addEventListener('visibilitychange', retry);
    return () => {
      window.removeEventListener('online', retry);
      document.removeEventListener('visibilitychange', retry);
    };
  }, [gaveUp, connect]);
}
