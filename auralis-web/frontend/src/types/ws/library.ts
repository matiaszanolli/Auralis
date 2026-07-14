/**
 * WebSocket message types — library domain.
 * Split from the former monolithic types/websocket.ts (#4081); consumers import
 * via the '@/types/websocket' barrel which re-exports every ws/* module.
 */


import type { WebSocketMessage } from './base';

/** Message-type literals owned by the library domain. */
export type LibraryMessageType =
  | 'library_updated'
  | 'metadata_updated'
  | 'metadata_batch_updated'
  | 'playlist_created'
  | 'playlist_updated'
  | 'playlist_deleted'
  | 'scan_progress'
  | 'scan_complete'
  | 'library_scan_started'
  | 'library_scan_error'
  | 'library_tracks_removed';


// ============================================================================
// Library Messages
// ============================================================================

export interface LibraryUpdatedMessage extends WebSocketMessage {
  type: 'library_updated';
  data: {
    action: 'scan' | 'import' | 'update';
    track_count?: number;
    album_count?: number;
    artist_count?: number;
  };
}


// ============================================================================
// Metadata Messages
// ============================================================================

export interface MetadataUpdatedMessage extends WebSocketMessage {
  type: 'metadata_updated';
  data: {
    track_id: number;
    updated_fields: string[]; // e.g., ["title", "artist", "album"]
  };
}


export interface MetadataBatchUpdatedMessage extends WebSocketMessage {
  type: 'metadata_batch_updated';
  data: {
    track_ids: number[];
    count: number;
  };
}


// ============================================================================
// Playlist Messages
// ============================================================================

export interface PlaylistCreatedMessage extends WebSocketMessage {
  type: 'playlist_created';
  data: {
    playlist_id: number;
    name: string;
  };
}


export interface PlaylistUpdatedMessage extends WebSocketMessage {
  type: 'playlist_updated';
  data: {
    playlist_id: number;
    action: 'renamed' | 'track_added' | 'track_removed' | 'reordered' | 'cleared';
  };
}


export interface PlaylistDeletedMessage extends WebSocketMessage {
  type: 'playlist_deleted';
  data: {
    playlist_id: number;
  };
}


// ============================================================================
// System Messages
// ============================================================================

export interface ScanProgressMessage extends WebSocketMessage {
  type: 'scan_progress';
  data: {
    current: number; // Files processed
    total: number; // Total files
    percentage: number | null; // 0-100, null during discovery phase
    current_file?: string;
    phase?: 'discovering' | 'processing' | 'fingerprinting';
  };
}


export interface ScanCompleteMessage extends WebSocketMessage {
  type: 'scan_complete';
  data: {
    files_processed: number;
    files_added: number;
    // Emitted by the backend but previously unmodelled (#4412) — surfacing these
    // lets the UI report partial failures instead of a silent "Added 0 tracks".
    files_updated?: number;
    files_skipped?: number;
    files_failed?: number;
    directories_scanned?: number;
    duration: number; // Seconds
  };
}


export interface LibraryScanStartedMessage extends WebSocketMessage {
  type: 'library_scan_started';
  data: {
    directories: string[];
  };
}


export interface LibraryScanErrorMessage extends WebSocketMessage {
  type: 'library_scan_error';
  data: {
    error: string;
  };
}


export interface LibraryTracksRemovedMessage extends WebSocketMessage {
  type: 'library_tracks_removed';
  data: {
    count: number;
  };
}
