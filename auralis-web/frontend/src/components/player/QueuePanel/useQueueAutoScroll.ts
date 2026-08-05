/**
 * useQueueAutoScroll
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Auto-scrolls the queue list while a row is being dragged near an edge of
 * the scroll container. Extracted from QueuePanel.tsx (#4916) to bring it
 * under the project's 300-line component guideline.
 */

import { DragEvent, RefObject, useCallback, useEffect, useRef } from 'react';
import { DRAG_EDGE_ZONE, DRAG_SCROLL_SPEED } from './styles';

export interface UseQueueAutoScrollOptions {
  /** The scrollable queue list container. */
  scrollElementRef: RefObject<HTMLDivElement | null>;
  /** Whether a row is currently being dragged (auto-scroll only applies then). */
  isDragActive: boolean;
}

export interface UseQueueAutoScrollReturn {
  handleContainerDragOver: (e: DragEvent<HTMLDivElement>) => void;
  stopAutoScroll: () => void;
}

export function useQueueAutoScroll({
  scrollElementRef,
  isDragActive,
}: UseQueueAutoScrollOptions): UseQueueAutoScrollReturn {
  const scrollDirectionRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  const autoScrollLoop = useCallback(() => {
    const el = scrollElementRef.current;
    if (!el || scrollDirectionRef.current === 0) {
      rafIdRef.current = null;
      return;
    }
    el.scrollTop += scrollDirectionRef.current * DRAG_SCROLL_SPEED;
    rafIdRef.current = requestAnimationFrame(autoScrollLoop);
  }, [scrollElementRef]);

  const handleContainerDragOver = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!isDragActive) return;
      e.preventDefault();
      const rect = e.currentTarget.getBoundingClientRect();
      const y = e.clientY - rect.top;

      if (y < DRAG_EDGE_ZONE) {
        scrollDirectionRef.current = -1;
      } else if (y > rect.height - DRAG_EDGE_ZONE) {
        scrollDirectionRef.current = 1;
      } else {
        scrollDirectionRef.current = 0;
      }

      if (scrollDirectionRef.current !== 0 && rafIdRef.current === null) {
        rafIdRef.current = requestAnimationFrame(autoScrollLoop);
      }
    },
    [isDragActive, autoScrollLoop],
  );

  const stopAutoScroll = useCallback(() => {
    scrollDirectionRef.current = 0;
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, []);

  return { handleContainerDragOver, stopAutoScroll };
}
