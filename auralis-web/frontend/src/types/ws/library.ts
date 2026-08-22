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
    total: number; // Total files (pre-counted by the scanner, #4616)
    // 0-100 once the scanner's counting pass has established a total (#4616);
    // null while that pass is still running. 0 means 0% processed, not unknown.
    percentage: number | null;
    current_file?: string;
    /**
     * #4648: `'fingerprinting'` was removed. The only emitter of
     * `{'stage': 'fingerprinting'}` on this channel was
     * `LibraryScanner._enqueue_fingerprints`, which had zero call sites and is
     * now deleted. `services/fingerprint_worker.py` still emits that stage, but
     * to `FingerprintQueue.set_progress_callback` — a different channel this
     * bridge never subscribes to. Re-adding the member therefore needs bridge
     * wiring plus `processed`/`total_found` in the payload, not just a union
     * edit: without those the bridge computes `current: 0, total: 0` and the UI
     * snaps back to "0 of 0" after a completed scan.
     */
    phase?: 'discovering' | 'processing';
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
    // #4841: which files failed and why, capped backend-side. `files_failed`
    // remains the exact count, so this can be shorter than that number.
    failures?: ScanFailure[];
    directories_scanned?: number;
    duration: number; // Seconds
  };
}


/** One file a scan could not process, and the reason (#4841). */
export interface ScanFailure {
  filepath: string;
  reason: string;
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
