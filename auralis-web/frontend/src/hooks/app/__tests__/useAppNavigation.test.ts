/**
 * useAppNavigation (#6703): view, mode and the re-pick reset token (#6014).
 */

import { describe, it, expect } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAppNavigation } from '@/hooks/app/useAppNavigation';

describe('useAppNavigation', () => {
  it('starts on the songs grid', () => {
    const { result } = renderHook(() => useAppNavigation());
    expect(result.current.currentView).toBe('songs');
    expect(result.current.viewMode).toBe('grid');
  });

  it('bumps the reset token on every sidebar pick, including the current view (#6014)', () => {
    const { result } = renderHook(() => useAppNavigation());

    act(() => result.current.handleSidebarNavigation('album-7'));
    expect(result.current.currentView).toBe('album-7');
    expect(result.current.navigationResetToken).toBe(1);

    act(() => result.current.handleSidebarNavigation('album-7'));
    expect(result.current.navigationResetToken).toBe(2);
  });

  it('a direct setCurrentView (a shortcut) does not bump the token', () => {
    const { result } = renderHook(() => useAppNavigation());
    act(() => result.current.setCurrentView('favourites'));
    expect(result.current.currentView).toBe('favourites');
    expect(result.current.navigationResetToken).toBe(0);
  });
});
