/**
 * useQueueRovingFocus
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Roving tabindex for the queue list (WAI-ARIA APG pattern, as the library
 * listbox got in #5011): exactly one row is a tab stop, and ArrowUp / ArrowDown /
 * Home / End move focus between rows (#6027). Alt+Arrow stays the reorder
 * gesture (QueueTrackItem), so plain arrows here never conflict with it.
 *
 * The queue is virtualized, so the remembered row may not be mounted: the tab
 * stop is clamped into the mounted window (as for the library list, #6069) and
 * a row outside it is scrolled in before it is focused.
 */

import { KeyboardEvent, FocusEvent, RefObject, useCallback, useState } from 'react';
import type { Virtualizer } from '@tanstack/react-virtual';

export interface UseQueueRovingFocusOptions {
  queueLength: number;
  scrollElementRef: RefObject<HTMLDivElement | null>;
  virtualizer: Virtualizer<HTMLDivElement, Element>;
}

export interface UseQueueRovingFocusReturn {
  /** The one row that currently has tabIndex 0. */
  tabStopIndex: number;
  onListKeyDown: (e: KeyboardEvent<HTMLElement>) => void;
  onListFocus: (e: FocusEvent<HTMLElement>) => void;
}

/** The queue row (an element with data-queue-index) that `target` IS, not one inside it. */
function rowIndexOf(target: EventTarget): number | null {
  if (!(target instanceof HTMLElement)) return null;
  const raw = target.dataset.queueIndex;
  return raw === undefined ? null : Number(raw);
}

export function useQueueRovingFocus({
  queueLength,
  scrollElementRef,
  virtualizer,
}: UseQueueRovingFocusOptions): UseQueueRovingFocusReturn {
  const [activeIndex, setActiveIndex] = useState(0);

  const virtualItems = virtualizer.getVirtualItems();
  const first = virtualItems[0];
  const last = virtualItems[virtualItems.length - 1];
  const clamped = Math.max(0, Math.min(activeIndex, queueLength - 1));
  const tabStopIndex = first && last ? Math.min(Math.max(clamped, first.index), last.index) : clamped;

  const focusRow = useCallback((index: number) => {
    const find = () =>
      scrollElementRef.current?.querySelector<HTMLElement>(`[data-queue-index="${index}"]`) ?? null;
    const row = find();
    if (row) {
      row.focus();
      return;
    }
    // Outside the virtual window: scroll it in, then focus once it has mounted.
    virtualizer.scrollToIndex(index);
    requestAnimationFrame(() => find()?.focus());
  }, [scrollElementRef, virtualizer]);

  const onListKeyDown = useCallback((e: KeyboardEvent<HTMLElement>) => {
    // Alt+Arrow reorders, and keys aimed at a control inside a row are its own.
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const current = rowIndexOf(e.target);
    if (current === null || queueLength === 0) return;

    let next: number;
    switch (e.key) {
      case 'ArrowDown': next = Math.min(current + 1, queueLength - 1); break;
      case 'ArrowUp': next = Math.max(current - 1, 0); break;
      case 'Home': next = 0; break;
      case 'End': next = queueLength - 1; break;
      default: return;
    }
    e.preventDefault();
    setActiveIndex(next);
    focusRow(next);
  }, [queueLength, focusRow]);

  // Focus arriving by Tab, click or script makes that row the tab stop.
  const onListFocus = useCallback((e: FocusEvent<HTMLElement>) => {
    const index = rowIndexOf(e.target);
    if (index !== null) setActiveIndex((current) => (current === index ? current : index));
  }, []);

  return { tabStopIndex, onListKeyDown, onListFocus };
}
