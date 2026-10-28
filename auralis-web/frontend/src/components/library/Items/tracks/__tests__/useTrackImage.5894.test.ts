/**
 * A track row retries artwork once its URL changes (#5894).
 *
 * The hook kept a single boolean for the life of the mounted row, so an image that 404'd
 * before the art was extracted never tried the new `?v=N` URL an artwork_updated bumped.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { SyntheticEvent } from 'react';
import { useTrackImage } from '../useTrackImage';

const errorFor = (src: string) =>
  ({ currentTarget: { getAttribute: () => src } }) as unknown as SyntheticEvent<HTMLImageElement>;

describe('useTrackImage', () => {
  it('hides the URL that failed', () => {
    const { result } = renderHook(() => useTrackImage());
    act(() => result.current.handleImageError(errorFor('/api/albums/1/artwork?size=80')));

    expect(result.current.shouldShowImage('/api/albums/1/artwork?size=80')).toBe(false);
  });

  it('tries a different URL (a bumped revision) after an earlier one failed', () => {
    const { result } = renderHook(() => useTrackImage());
    act(() => result.current.handleImageError(errorFor('/api/albums/1/artwork?size=80')));

    expect(result.current.shouldShowImage('/api/albums/1/artwork?size=80&v=3')).toBe(true);
  });

  it('shows nothing without a URL, and a failure reported without its URL hides everything', () => {
    const { result } = renderHook(() => useTrackImage());
    expect(result.current.shouldShowImage(undefined)).toBe(false);

    act(() => result.current.handleImageError());
    expect(result.current.shouldShowImage('/api/albums/1/artwork?size=80&v=3')).toBe(false);
  });
});
