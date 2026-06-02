/**
 * WebSocket message types — enhancement domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessage } from './base';

/** Message-type literals owned by the enhancement domain. */
export type EnhancementMessageType =
  | 'enhancement_settings_changed'
  | 'mastering_recommendation'
  | 'artwork_updated'
  | 'fingerprint_progress';


// ============================================================================
// Enhancement Messages
// ============================================================================

export interface EnhancementSettingsChangedMessage extends WebSocketMessage {
  type: 'enhancement_settings_changed';
  data: {
    enabled: boolean;
    preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
    intensity: number; // 0.0 - 1.0
  };
}


export interface MasteringRecommendationData {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number; // 0.0 - 1.0
  predicted_loudness_change: number; // dB
  predicted_crest_change: number; // dB
  predicted_centroid_change: number; // Hz
  /** Optional on the wire — the backend dataclass only emits this when
   *  `self.weighted_profiles` is truthy (#3550 / BE-NEW-92). */
  weighted_profiles?: Array<{
    profile_id: string;
    profile_name: string;
    weight: number; // 0.0 - 1.0, sum of all = 1.0
  }>;
  reasoning: string;
  is_hybrid: boolean;
  /** Alternative profile rankings emitted by adaptive_mastering_engine
   *  but not currently consumed by the frontend (#3550 / BE-NEW-92). */
  alternative_profiles?: Array<{
    profile_id: string;
    profile_name: string;
    confidence_score: number;
  }>;
  /** ISO timestamp the recommendation was computed. */
  created?: string;
}


export interface MasteringRecommendationMessage extends WebSocketMessage {
  type: 'mastering_recommendation';
  data: MasteringRecommendationData;
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
    stream_type?: 'enhanced' | 'normal';
  };
}
