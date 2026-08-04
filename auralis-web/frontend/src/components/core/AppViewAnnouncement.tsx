import { screenReaderOnly } from './accessibilityStyles';

const VIEW_LABELS: Record<string, string> = {
  songs: 'Songs',
  albums: 'Albums',
  artists: 'Artists',
  favourites: 'Favourites',
  recent: 'Recently played',
  playlists: 'Playlists',
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
