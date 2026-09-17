/**
 * useServerRestartNotice - tell the user when a backend restart lost their session
 *
 * The backend keeps the playback session (queue, current track, position)
 * only in memory, so after a restart the reconnect snapshot is empty and looks
 * exactly like a fresh launch (#5487). Every `player_state` snapshot carries
 * the backend's per-process `server_instance_id`; when it changes and the
 * previous process had something loaded, show a warning instead of letting the
 * queue vanish silently.
 *
 * "Had something loaded" is judged from the snapshots this hook itself saw,
 * so it does not depend on whether usePlayerStateSync has already applied the
 * empty post-restart snapshot to Redux.
 *
 * Mount once at the app level inside both WebSocketProvider and ToastProvider.
 */

import { useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import type { RawPlayerStateData } from '@/types/ws/player';

export const SESSION_RESET_MESSAGE =
  'The audio engine restarted, so your queue and playback position were reset.';

const SESSION_RESET_TOAST_MS = 8000;

export function useServerRestartNotice(): void {
  const { warning } = useToast();
  const lastInstanceIdRef = useRef<string | null>(null);
  const hadSessionRef = useRef(false);

  useWebSocketMessages(['player_state'], (message) => {
    const state = (message as { data?: Partial<RawPlayerStateData> }).data;
    const instanceId = state?.server_instance_id;
    if (!state || typeof instanceId !== 'string' || !instanceId) return;

    const restarted =
      lastInstanceIdRef.current !== null && lastInstanceIdRef.current !== instanceId;
    if (restarted && hadSessionRef.current) {
      warning(SESSION_RESET_MESSAGE, SESSION_RESET_TOAST_MS);
    }

    lastInstanceIdRef.current = instanceId;
    hadSessionRef.current =
      Boolean(state.current_track) || (Array.isArray(state.queue) && state.queue.length > 0);
  });
}
