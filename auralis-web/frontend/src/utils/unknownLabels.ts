/**
 * Display labels for an absent artist or album.
 *
 * The backend sends `null` / an empty value for an absent artist or album (#5905, #6508); the
 * label belongs to the UI, applied once where API data becomes a domain model.
 */
export const UNKNOWN_ARTIST_LABEL = 'Unknown Artist';
export const UNKNOWN_ALBUM_LABEL = 'Unknown Album';
