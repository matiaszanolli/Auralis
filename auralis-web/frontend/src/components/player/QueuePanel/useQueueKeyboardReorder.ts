/**
 * useQueueKeyboardReorder
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Keyboard-driven queue reordering (#4536) plus the focus restoration and
 * live-region announcement that go with it. Extracted from QueuePanel.tsx
 * (#4916) to bring it under the project's 300-line component guideline.
 */

import { RefObject, useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { Virtualizer } from '@tanstack/react-virtual';
import type { Track, QueueTrack } from '@/types/domain';

export interface UseQueueKeyboardReorderOptions {
  queue: (Track | QueueTrack)[];
  reorderTrack: (fromIndex: number, toIndex: number) => Promise<void>;
  scrollElementRef: RefObject<HTMLDivElement | null>;
  virtualizer: Virtualizer<HTMLDivElement, Element>;
}

export interface UseQueueKeyboardReorderReturn {
  handleKeyboardReorder: (fromIndex: number, toIndex: number) => Promise<void>;
  /** Message for the live region announcing the result of a keyboard move. */
  announcement: string;
}

export function useQueueKeyboardReorder({
  queue,
  reorderTrack,
  scrollElementRef,
  virtualizer,
}: UseQueueKeyboardReorderOptions): UseQueueKeyboardReorderReturn {
  // Index whose row should receive focus after the next render, and the
  // message mirrored into the live region. State rather than a ref so
  // setting it is itself enough to run the restoring effect below --
  // keying only on `queue` would silently skip restoration whenever the
  // queue array keeps its identity across the reorder.
  const [pendingFocusIndex, setPendingFocusIndex] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState('');

  // Read inside handleKeyboardReorder so the callback stays stable — depending
  // on `queue` would give every row a new handler on each queue change and
  // defeat QueueTrackItem's memo (#4177).
  const queueRef = useRef(queue);
  queueRef.current = queue;

  /**
   * Bounds are checked here rather than in the row, which does not know the
   * queue length. `reorderTrack` is optimistic: it dispatches to Redux before
   * the PUT resolves, so the list re-renders — and, because the row key embeds
   * the index (#4428), the moved row unmounts and remounts — while this is
   * still awaiting. Focus therefore cannot be restored after the await; it is
   * handed to the layout effect below, which runs on every queue change.
   */
  const handleKeyboardReorder = useCallback(
    async (fromIndex: number, toIndex: number) => {
      const track = queueRef.current[fromIndex];
      if (!track) return;
      if (toIndex < 0 || toIndex >= queueRef.current.length) {
        // At an end of the queue: announce rather than failing silently, since
        // there is no visual cue that the key press did nothing.
        setAnnouncement(
          `${track.title} is already ${toIndex < 0 ? 'first' : 'last'} in the queue`,
        );
        return;
      }

      setPendingFocusIndex(toIndex);
      try {
        await reorderTrack(fromIndex, toIndex);
        setAnnouncement(
          `${track.title} moved to position ${toIndex + 1} of ${queueRef.current.length}`,
        );
      } catch (err) {
        // runOptimistic rolls the queue back, so the row is at its original
        // index again — follow it there instead of leaving focus on whichever
        // track now occupies the target slot.
        console.error('Failed to reorder track:', err);
        setPendingFocusIndex(fromIndex);
        setAnnouncement(`Could not move ${track.title}`);
      }
    },
    [reorderTrack],
  );

  // Restore focus to the moved row once it has re-rendered at its new index.
  // Done in an effect rather than inline after the await because the row
  // unmounts and remounts (its key embeds the index, #4428) during the
  // optimistic update, which would drop focus set beforehand.
  useLayoutEffect(() => {
    if (pendingFocusIndex === null) return;

    const focusRow = () => {
      const row = scrollElementRef.current?.querySelector<HTMLElement>(
        `[data-queue-index="${pendingFocusIndex}"]`,
      );
      row?.focus();
      return Boolean(row);
    };

    if (!focusRow()) {
      // Outside the virtual window (reachable only if the row scrolled out
      // between keypress and commit) — scroll it in, then retry once.
      virtualizer.scrollToIndex(pendingFocusIndex);
      requestAnimationFrame(focusRow);
    }
    setPendingFocusIndex(null);
  }, [pendingFocusIndex, queue, scrollElementRef, virtualizer]);

  return { handleKeyboardReorder, announcement };
}
