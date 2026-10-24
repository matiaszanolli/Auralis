import { screenReaderOnly } from './accessibilityStyles';

// No 'recent'/'playlists' labels (#5620): those views have no data path,
// so a stale persisted value announces its generic fallback rather than a
// library view that does not exist.
const VIEW_LABELS: Record<string, string> = {
  songs: 'Songs',
  albums: 'Albums',
  artists: 'Artists',
  favourites: 'Favourites',
};

function getViewLabel(view: string): string {
  if (view.startsWith('playlist-')) return 'Playlist';
  const knownLabel = VIEW_LABELS[view];
  if (knownLabel) return knownLabel;

  const normalized = view.replace(/[-_]+/g, ' ').trim();
  return normalized
    ? normalized.charAt(0).toUpperCase() + normalized.slice(1)
    : 'Library';
}

export function AppViewAnnouncement({ view }: { view: string }) {
  return (
    <span
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={screenReaderOnly}
    >
      {`${getViewLabel(view)} view`}
    </span>
  );
}
