/**
 * useSimilarTracksModal close keeps the mount gate (#5397)
 *
 * CozyLibraryView mounts SimilarTracksModal while `similarTrackId` is set.
 * The close handler used to clear it together with `open`, which unmounted
 * the modal before MUI's exit transition could run.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSimilarTracksModal } from '../useSimilarTracksModal';
import type { LibraryTrack } from '@/types/domain';

const tracks = [
  { id: 7, title: 'Roads' },
  { id: 8, title: 'Glory Box' },
] as LibraryTrack[];

describe('useSimilarTracksModal (#5397)', () => {
  it('is not mountable before the first open', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));
    expect(result.current.similarTrackId).toBeNull();
    expect(result.current.similarTracksModalOpen).toBe(false);
  });

  it('closing flips only `open`, keeping the track for the exit transition', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));

    act(() => result.current.handleFindSimilar(7));
    expect(result.current.similarTracksModalOpen).toBe(true);

    act(() => result.current.handleCloseSimilarTracksModal());
    expect(result.current.similarTracksModalOpen).toBe(false);
    expect(result.current.similarTrackId).toBe(7);
    expect(result.current.similarTrackTitle).toBe('Roads');
  });

  it('the next open replaces the retained track', () => {
    const { result } = renderHook(() => useSimilarTracksModal({ tracks, onPlayTrack: vi.fn() }));

    act(() => result.current.handleFindSimilar(7));
    act(() => result.current.handleCloseSimilarTracksModal());
    act(() => result.current.handleFindSimilar(8));

    expect(result.current.similarTracksModalOpen).toBe(true);
    expect(result.current.similarTrackId).toBe(8);
    expect(result.current.similarTrackTitle).toBe('Glory Box');
  });
});
