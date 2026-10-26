/**
 * Display labels for an absent album artist.
 *
 * The backend sends `null` for an absent artist (#5905); the label belongs to
 * the UI, applied once where API data becomes a domain model.
 */
export const UNKNOWN_ARTIST_LABEL = 'Unknown Artist';
