/**
 * useRecentlyTouched Hook Tests
 *
 * Tests for localStorage-backed recently accessed album tracking.
 *
 * @module hooks/library/__tests__/useRecentlyTouched.test
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRecentlyTouched } from '../useRecentlyTouched';

const STORAGE_KEY = 'auralis-recently-touched-albums';

describe('useRecentlyTouched', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should return empty array when no stored data', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    expect(result.current.recentAlbums).toEqual([]);
  });

  it('should load previously stored albums on init', () => {
    const stored = [
      { albumId: 1, albumTitle: 'Album A', artist: 'Artist A', touchedAt: 1000 },
      { albumId: 2, albumTitle: 'Album B', artist: 'Artist B', touchedAt: 900 },
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));

    const { result } = renderHook(() => useRecentlyTouched());

    expect(result.current.recentAlbums).toEqual(stored);
  });

  it('should add a new album via touchAlbum', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      result.current.touchAlbum(1, 'Dark Side of the Moon', 'Pink Floyd');
    });

    expect(result.current.recentAlbums).toHaveLength(1);
    expect(result.current.recentAlbums[0]).toMatchObject({
      albumId: 1,
      albumTitle: 'Dark Side of the Moon',
      artist: 'Pink Floyd',
    });
    expect(result.current.recentAlbums[0].touchedAt).toBeGreaterThan(0);
  });

  it('should persist to localStorage on touch', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      result.current.touchAlbum(1, 'Album', 'Artist');
    });

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(stored).toHaveLength(1);
    expect(stored[0].albumId).toBe(1);
  });

  it('should move existing album to top on re-touch', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      result.current.touchAlbum(1, 'Album A', 'Artist A');
    });
    act(() => {
      result.current.touchAlbum(2, 'Album B', 'Artist B');
    });
    act(() => {
      result.current.touchAlbum(1, 'Album A', 'Artist A');
    });

    expect(result.current.recentAlbums).toHaveLength(2);
    expect(result.current.recentAlbums[0].albumId).toBe(1);
    expect(result.current.recentAlbums[1].albumId).toBe(2);
  });

  it('should limit entries to 20 albums', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      for (let i = 1; i <= 25; i++) {
        result.current.touchAlbum(i, `Album ${i}`, `Artist ${i}`);
      }
    });

    expect(result.current.recentAlbums).toHaveLength(20);
    // Most recent should be first
    expect(result.current.recentAlbums[0].albumId).toBe(25);
  });

  it('should clear all recent albums', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      result.current.touchAlbum(1, 'Album', 'Artist');
      result.current.touchAlbum(2, 'Album 2', 'Artist 2');
    });

    act(() => {
      result.current.clearRecent();
    });

    expect(result.current.recentAlbums).toEqual([]);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('should handle corrupted localStorage data gracefully', () => {
    localStorage.setItem(STORAGE_KEY, 'not valid json{{{');

    const { result } = renderHook(() => useRecentlyTouched());

    expect(result.current.recentAlbums).toEqual([]);
  });

  it('should handle non-array stored data gracefully', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ bad: 'data' }));

    const { result } = renderHook(() => useRecentlyTouched());

    expect(result.current.recentAlbums).toEqual([]);
  });

  it('should respond to storage events from other tabs', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    const newData = [
      { albumId: 99, albumTitle: 'From Other Tab', artist: 'Artist', touchedAt: 5000 },
    ];

    act(() => {
      // Simulate storage event from another tab
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newData));
      window.dispatchEvent(new StorageEvent('storage', {
        key: STORAGE_KEY,
        newValue: JSON.stringify(newData),
      }));
    });

    expect(result.current.recentAlbums).toEqual(newData);
  });

  it('should ignore storage events for other keys', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    act(() => {
      result.current.touchAlbum(1, 'Album', 'Artist');
    });

    act(() => {
      window.dispatchEvent(new StorageEvent('storage', {
        key: 'some-other-key',
        newValue: '[]',
      }));
    });

    expect(result.current.recentAlbums).toHaveLength(1);
  });

  it('should deduplicate entries and not grow beyond limit', () => {
    const { result } = renderHook(() => useRecentlyTouched());

    // Touch the same album 30 times
    act(() => {
      for (let i = 0; i < 30; i++) {
        result.current.touchAlbum(1, 'Album A', 'Artist A');
      }
    });

    expect(result.current.recentAlbums).toHaveLength(1);
    expect(result.current.recentAlbums[0].albumId).toBe(1);
  });
});
