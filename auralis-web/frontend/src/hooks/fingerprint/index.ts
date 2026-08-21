/**
 * Fingerprint hooks for audio fingerprinting and similarity
 * - Track/album fingerprint fetching
 * - Similarity search operations
 *
 * `useFingerprintCache` was removed in #4239. It never started the Web Worker
 * its name implied — `startWorker()` called `simulateFingerprinting()`, which
 * faked a progress bar and then wrote one hardcoded 25D vector into the cache
 * for every track. Client-side fingerprinting is also redundant: the backend
 * computes real fingerprints in Rust and serves them from
 * `/api/tracks/{id}/fingerprint`, which `useTrackFingerprint` below already
 * reads. The IndexedDB layer it drove, `services/fingerprint/FingerprintCache`,
 * is kept — it is tested (#4478) and fabricates nothing — but now has no
 * consumer.
 */

export { useTrackFingerprint } from './useTrackFingerprint';
export { useAlbumFingerprint, useAlbumFingerprints } from './useAlbumFingerprint';
export { useSimilarTracks } from './useSimilarTracks';
export type { SimilarTrack, SimilarityOptions } from './useSimilarTracks';
