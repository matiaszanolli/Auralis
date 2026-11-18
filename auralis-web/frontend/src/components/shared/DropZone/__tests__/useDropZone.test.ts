/**
 * useDropZone Hook Tests
 *
 * The nested dragenter/dragleave counter lives in a ref, so no state updater
 * performs a second state update (#6429).
 */

import { StrictMode } from 'react';
import type { DragEvent } from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useDropZone } from '../useDropZone';

/** A drag event carrying `itemCount` dragged items. */
function dragEvent(itemCount = 1): DragEvent {
  return {
    preventDefault: () => {},
    stopPropagation: () => {},
    dataTransfer: { items: Array.from({ length: itemCount }), dropEffect: 'none' },
  } as unknown as DragEvent;
}

describe('useDropZone', () => {
  it('stays dragging until every nested enter has a matching leave', () => {
    const { result } = renderHook(() => useDropZone(), { wrapper: StrictMode });

    act(() => { result.current.handleDragEnter(dragEvent()); });
    act(() => { result.current.handleDragEnter(dragEvent()); }); // child element
    expect(result.current.isDragging).toBe(true);

    act(() => { result.current.handleDragLeave(dragEvent()); }); // left the child
    expect(result.current.isDragging).toBe(true);

    act(() => { result.current.handleDragLeave(dragEvent()); }); // left the zone
    expect(result.current.isDragging).toBe(false);
  });

  it('an unpaired leave does not pin the zone into the dragging state', () => {
    const { result } = renderHook(() => useDropZone());

    act(() => { result.current.handleDragLeave(dragEvent()); }); // no matching enter
    act(() => { result.current.handleDragEnter(dragEvent()); });
    expect(result.current.isDragging).toBe(true);

    act(() => { result.current.handleDragLeave(dragEvent()); });
    expect(result.current.isDragging).toBe(false);
  });

  it('a drop resets the counter and the dragging flag', () => {
    const { result } = renderHook(() => useDropZone());
    act(() => { result.current.handleDragEnter(dragEvent()); });
    act(() => { result.current.handleDragEnter(dragEvent()); });

    act(() => { result.current.handleDrop(dragEvent(0), () => {}); });
    expect(result.current.isDragging).toBe(false);

    // A fresh drag after the drop starts from zero, not from the stale nesting depth.
    act(() => { result.current.handleDragEnter(dragEvent()); });
    act(() => { result.current.handleDragLeave(dragEvent()); });
    expect(result.current.isDragging).toBe(false);
  });

  it('ignores drags while disabled or scanning', () => {
    const { result } = renderHook(() => useDropZone(true, false));

    act(() => { result.current.handleDragEnter(dragEvent()); });

    expect(result.current.isDragging).toBe(false);
  });
});
