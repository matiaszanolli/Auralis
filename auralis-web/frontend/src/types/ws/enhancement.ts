/**
 * WebSocket message types — enhancement domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessage } from './base';
import type { EnhancementPreset, StreamType } from '@/types/domain';

/** Message-type literals owned by the enhancement domain. */
export type EnhancementMessageType =
  | 'enhancement_settings_changed'
  | 'artwork_updated'
  | 'fingerprint_progress';


// ============================================================================
// Enhancement Messages
// ============================================================================

export interface EnhancementSettingsChangedMessage extends WebSocketMessage {
  type: 'enhancement_settings_changed';
  data: {
    enabled: boolean;
    // Derived from the canonical EnhancementPreset, not redeclared (#5610).
    preset: EnhancementPreset;
    intensity: number; // 0.0 - 1.0
  };
}


// ============================================================================
// Artwork Messages
// ============================================================================

export interface ArtworkUpdatedMessage extends WebSocketMessage {
  type: 'artwork_updated';
  data: {
    action: 'extracted' | 'downloaded' | 'deleted';
    album_id: number;
    artwork_url?: string; // absent for 'deleted'
  };
}


// ============================================================================
// Fingerprint Messages (fixes #2282)
// ============================================================================

/** Sent by system.py seek handler — see also SeekStartedMessage below.
 *  This forward-declaration block exists so seek_started can include
 *  `track_id` (fixes #3547 / BE-NEW-89). */
// ---

/** Sent by audio_stream_controller.py while computing track fingerprint (fixes #2502) */
export interface FingerprintProgressMessage extends WebSocketMessage {
  type: 'fingerprint_progress';
  data: {
    track_id: number;
    status: 'analyzing' | 'complete' | 'failed' | 'error' | 'cached' | 'queued';
    message: string;
    stream_type?: StreamType;
  };
}
