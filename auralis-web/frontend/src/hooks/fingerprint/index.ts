/**
 * Fingerprint hooks for audio fingerprinting and similarity
 * - Audio fingerprint caching
 * - Track/album fingerprint fetching
 * - Similarity search operations
 */

export { useFingerprintCache } from './useFingerprintCache';
export { useTrackFingerprint, usePlayingTrackFingerprint } from './useTrackFingerprint';
export { useAlbumFingerprint, useAlbumFingerprints } from './useAlbumFingerprint';
export { useSimilarTracks } from './useSimilarTracks';
export type { SimilarTrack, SimilarityOptions } from './useSimilarTracks';
