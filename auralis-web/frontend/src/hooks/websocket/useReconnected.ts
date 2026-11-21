/**
 * useReconnected — run a resync when the WebSocket comes back after a drop (#6581).
 *
 * Frames emitted while the socket was down (a `--dev` backend reload, the reconnect backoff, the
 * give-up state) are never replayed, so a consumer that only refreshes on frames keeps pre-outage
 * data. This fires `onReconnect` on a connected transition that FOLLOWS a connection this mount
 * has already seen - never on the first connect, whose data the consumer fetched itself.
 *
 * `onReconnect` is read through a ref, so an inline callback does not re-run the effect.
 *
 * @module hooks/websocket/useReconnected
 */

import { useEffect, useRef } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

export function useReconnected(onReconnect: () => void): void {
  const { isConnected } = useWebSocketContext();
  const callbackRef = useRef(onReconnect);
  const wasConnectedRef = useRef(isConnected);
  const hasConnectedRef = useRef(isConnected);

  useEffect(() => {
    callbackRef.current = onReconnect;
  }, [onReconnect]);

  useEffect(() => {
    if (isConnected && !wasConnectedRef.current && hasConnectedRef.current) callbackRef.current();
    if (isConnected) hasConnectedRef.current = true;
    wasConnectedRef.current = isConnected;
  }, [isConnected]);
}

export default useReconnected;
