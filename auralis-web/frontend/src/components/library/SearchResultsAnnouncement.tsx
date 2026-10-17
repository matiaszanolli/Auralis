/**
 * SearchResultsAnnouncement - library search status region (#5668)
 *
 * The top-bar search filters the track list client-side, but nothing told a
 * screen reader how many tracks match, that none do, or that the list is
 * loading (WCAG 4.1.3). This visually hidden role="status" region announces
 * the result count / "no results" / loading, debounced so typing a whole
 * query does not read out per character.
 *
 * Rendered by the mounted library container (CozyLibraryView) so the same
 * node is present before its content changes. It is a separate concern from
 * AppViewAnnouncement's view-change region — same screenReaderOnly style,
 * different message.
 */

import { useEffect, useRef, useState } from 'react';
import { screenReaderOnly } from '@/components/core/accessibilityStyles';

/** Keystrokes settle this long before the count is read out. */
const ANNOUNCE_DEBOUNCE_MS = 500;

interface SearchResultsAnnouncementProps {
  resultCount: number;
  query: string;
  loading: boolean;
}

export function SearchResultsAnnouncement({ resultCount, query, loading }: SearchResultsAnnouncementProps) {
  const [message, setMessage] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (loading) {
        setMessage('Loading tracks');
        return;
      }
      if (!query.trim()) {
        setMessage('');
        return;
      }
      if (resultCount === 0) {
        setMessage(`No results for ${query.trim()}`);
        return;
      }
      setMessage(resultCount === 1 ? '1 track' : `${resultCount} tracks`);
    }, ANNOUNCE_DEBOUNCE_MS);

    return () => clearTimeout(timerRef.current);
  }, [resultCount, query, loading]);

  return (
    <span role="status" aria-live="polite" aria-atomic="true" style={screenReaderOnly}>
      {message}
    </span>
  );
}

export default SearchResultsAnnouncement;
