/**
 * useGridVirtualizer — shared row-based grid virtualization for album grids
 *
 * Wraps `@tanstack/react-virtual`'s `useVirtualizer` for grids where every row
 * holds N equally-wide columns. Callers compute `columnsPerRow` from container
 * width and feed it back in; the hook returns a virtualizer keyed on row count
 * so DOM nodes scale with the viewport, not the dataset.
 *
 * Pairs with #3606 — bounds `AlbumCard` DOM count to roughly
 * `(visibleRows + overscan) × columnsPerRow` regardless of total loaded albums.
 *
 * @module components/library/Items/utilities/useGridVirtualizer
 */

import { RefObject, useEffect, useLayoutEffect, useState } from 'react';
import { useVirtualizer, Virtualizer } from '@tanstack/react-virtual';

interface UseGridVirtualizerArgs {
  /** Total number of items to display. */
  itemCount: number;
  /** Columns rendered per row. Re-measured by the caller on resize. */
  columnsPerRow: number;
  /** Row height in pixels (card height + row gap). */
  rowHeight: number;
  /** Scroll container — must be a stable getter returning a live element. */
  getScrollElement: () => HTMLElement | null;
  /** Pixel offset of the grid's container from the top of `scrollElement`. */
  scrollMargin?: number;
  /** Extra rows rendered above/below the viewport. Defaults to 2. */
  overscan?: number;
}

/** Row-based virtualizer for grids with uniform-height rows. */
export function useGridVirtualizer({
  itemCount,
  columnsPerRow,
  rowHeight,
  getScrollElement,
  scrollMargin = 0,
  overscan = 2,
}: UseGridVirtualizerArgs): Virtualizer<HTMLElement, Element> {
  const safeColumns = Math.max(1, columnsPerRow);
  const rowCount = Math.ceil(itemCount / safeColumns);

  return useVirtualizer({
    count: rowCount,
    getScrollElement,
    estimateSize: () => rowHeight,
    overscan,
    scrollMargin,
  });
}

/**
 * Track an element's clientWidth via ResizeObserver, falling back to the
 * initial measurement when ResizeObserver is unavailable (test environment
 * mocks it as a no-op — see `src/test/setup.ts`).
 */
export function useContainerWidth(ref: RefObject<HTMLElement>): number {
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
  }, [ref]);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const next = entry.contentRect.width;
        setWidth((prev) => (Math.abs(prev - next) > 0.5 ? next : prev));
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return width;
}

/**
 * Compute the number of columns that fit in `containerWidth` for a grid built
 * from `minmax(minColumnWidth, 1fr)` style cells separated by `gap`. Matches
 * the CSS Grid `auto-fill` algorithm closely enough for virtualization sizing.
 */
export function computeColumnsPerRow(
  containerWidth: number,
  minColumnWidth: number,
  gap: number
): number {
  if (containerWidth <= 0 || minColumnWidth <= 0) return 1;
  const cols = Math.floor((containerWidth + gap) / (minColumnWidth + gap));
  return Math.max(1, cols);
}
