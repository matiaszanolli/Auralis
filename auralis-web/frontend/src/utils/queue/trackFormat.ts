/**
 * Track format resolution — single source of truth.
 *
 * #4586: `queue_recommender` and `queue_statistics` each carried their own
 * identical `extractFormat(filepath)`, both deriving the audio format by
 * parsing the file extension off `track.filepath`. No transport populates
 * `filepath`: `Track.to_dict()` omits it and `player_state.TrackInfo` marks it
 * `Field(exclude=True)` so server paths are never sent to the client (#3205).
 * Both helpers therefore returned `'unknown'` for every queue-sourced track,
 * silently flattening format similarity and the format distribution.
 *
 * The backend ships the format explicitly instead, so prefer that and keep the
 * filepath parse only as a fallback for track objects that do carry a path.
 */

export interface TrackFormatSource {
  format?: string | null;
  filepath?: string;
}

export const UNKNOWN_FORMAT = 'unknown';

/**
 * Resolve a track's audio format as a lowercase string (e.g. `'flac'`).
 *
 * Returns `'unknown'` when neither an explicit format nor a parseable
 * filepath extension is available.
 */
export function extractTrackFormat(track: TrackFormatSource | undefined): string {
  if (!track) return UNKNOWN_FORMAT;

  const explicit = track.format;
  if (typeof explicit === 'string' && explicit.trim() !== '') {
    return explicit.trim().toLowerCase();
  }

  const filepath = track.filepath;
  if (typeof filepath === 'string' && filepath !== '') {
    const match = filepath.match(/\.([a-z0-9]+)$/i);
    if (match) return match[1].toLowerCase();
  }

  return UNKNOWN_FORMAT;
}
