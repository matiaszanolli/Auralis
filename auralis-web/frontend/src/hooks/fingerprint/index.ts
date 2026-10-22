/**
 * Fingerprint hooks for audio fingerprinting and similarity
 * - Track/album fingerprint fetching
 * - Similarity search operations
 *
 * Fingerprints are computed by the backend (in Rust) and served from
 * `/api/tracks/{id}/fingerprint`, which `useTrackFingerprint` reads; there is
 * no client-side fingerprinting or cache.
 */

export { useTrackFingerprint } from './useTrackFingerprint';
export { useAlbumFingerprint, useAlbumFingerprints } from './useAlbumFingerprint';
export { useSimilarTracks } from './useSimilarTracks';
export type { SimilarTrack, SimilarityOptions } from './useSimilarTracks';
export { classifySimilarityError } from './similarityErrorState';
export type { SimilarityErrorKind, SimilarityErrorState } from './similarityErrorState';
