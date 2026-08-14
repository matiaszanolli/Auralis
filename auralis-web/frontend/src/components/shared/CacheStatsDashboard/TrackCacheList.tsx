/**
 * Per-Track Cache List (virtualized)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The per-track cache rows used to be a plain `Object.entries(tracks).map(...)`
 * inside a fixed-height scroll container in CacheStatsDashboard — one DOM node
 * per cached track, with no windowing, unlike TrackList/QueuePanel (#4471).
 * The cache track count is bounded by disk size rather than by anything the UI
 * controls, so it can comfortably exceed a few hundred entries in a long
 * session.
 *
 * Extracted here rather than inlined so CacheStatsDashboard stays under the
 * 300-line component budget, and reusing the same `useVirtualizer` shape as
 * QueuePanel: absolutely-positioned rows inside a spacer sized to
 * `getTotalSize()`, translated by `virtualRow.start`.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/** Shape of one entry in the cache stats `tracks` map. */
export interface TrackCacheInfo {
  track_id: number;
  completion_percent: number;
  fully_cached: boolean;
}

interface TrackCacheListProps {
  tracks: Record<string, TrackCacheInfo>;
}

/**
 * Row height in px. Rows are a fixed single line, so a constant estimate is
 * exact and no dynamic measurement is needed. Includes the inter-row gap that
 * the pre-virtualization flex column produced, since absolutely-positioned
 * rows cannot use `gap`.
 */
export const TRACK_CACHE_ROW_HEIGHT = 44;

/** Height of the scroll viewport, unchanged from the original container. */
const LIST_MAX_HEIGHT = 300;

export function TrackCacheList({ tracks }: TrackCacheListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const entries = Object.entries(tracks);

  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => TRACK_CACHE_ROW_HEIGHT,
    overscan: 5,
  });

  return (
    <div
      ref={scrollRef}
      data-testid="track-cache-scroll"
      style={{
        maxHeight: `${LIST_MAX_HEIGHT}px`,
        overflowY: 'auto',
      }}
    >
      <div
        role="list"
        aria-label="Per-track cache status"
        style={{
          height: virtualizer.getTotalSize(),
          position: 'relative',
          width: '100%',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const [trackId, trackInfo] = entries[virtualRow.index];
          return (
            <div
              key={trackId}
              role="listitem"
              data-testid="track-cache-row"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${TRACK_CACHE_ROW_HEIGHT}px`,
                transform: `translateY(${virtualRow.start}px)`,
                // Inner box keeps the original look; the outer row owns the
                // slot height so the gap survives absolute positioning.
                paddingBottom: tokens.spacing.sm,
                boxSizing: 'border-box',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: tokens.spacing.sm,
                  background: themeVars.surfaceRaised,
                  borderRadius: '4px',
                  height: '100%',
                  boxSizing: 'border-box',
                }}
              >
                <span
                  style={{
                    fontSize: tokens.typography.fontSize.sm,
                    color: themeVars.textSecondary,
                  }}
                >
                  Track {trackInfo.track_id}
                </span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: tokens.spacing.md,
                  }}
                >
                  <div
                    style={{
                      width: '100px',
                      height: '4px',
                      background: tokens.colors.border.light,
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${trackInfo.completion_percent}%`,
                        background: trackInfo.fully_cached
                          ? tokens.colors.semantic.success
                          : tokens.colors.semantic.warning,
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontSize: tokens.typography.fontSize.xs,
                      color: themeVars.textMuted,
                      minWidth: '40px',
                      textAlign: 'right',
                    }}
                  >
                    {Math.round(trackInfo.completion_percent)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
