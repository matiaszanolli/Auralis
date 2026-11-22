/**
 * useAppKeyboard (#6703): the global shortcuts bound to the playback session.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { act, renderHook } from '@testing-library/react';
import { createTestStore } from '@/test/test-utils';
import { keyboardShortcuts } from '@/services/keyboardShortcutsService';
import { useAppKeyboard } from '@/hooks/app/useAppKeyboard';

const session = vi.hoisted(() => ({
  isCommandPending: false,
  isPlaybackActive: true,
  isPaused: false,
  handlePlayPause: vi.fn(),
  handleNext: vi.fn(),
  handlePrevious: vi.fn(),
  handleVolumeChange: vi.fn(),
  handleMuteToggle: vi.fn(() => Promise.resolve(true)),
}));

vi.mock('@/contexts/PlaybackSessionContext', () => ({
  usePlaybackControls: () => session,
}));

const press = (key: string) => {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  });
};

function renderKeyboard() {
  const store = createTestStore({ player: { volume: 40 } });
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  const args = {
    info: vi.fn(),
    searchQuery: '',
    setSearchQuery: vi.fn(),
    settingsOpen: false,
    setSettingsOpen: vi.fn(),
    setCurrentView: vi.fn(),
  };
  return { args, hook: renderHook(() => useAppKeyboard(args), { wrapper }) };
}

describe('useAppKeyboard', () => {
  beforeEach(() => {
    keyboardShortcuts.clear();
    vi.clearAllMocks();
  });

  it('steps the volume from the store value at keypress time, scaled to 0-1 (#6067)', () => {
    const { args } = renderKeyboard();
    press('ArrowUp');
    expect(session.handleVolumeChange).toHaveBeenCalledWith(0.5);
    expect(args.info).toHaveBeenCalledWith('Volume: 50%');
  });

  it("'?' opens the help dialog through the ref the table holds (#3077)", () => {
    const { hook } = renderKeyboard();
    expect(hook.result.current.isHelpOpen).toBe(false);
    press('?');
    expect(hook.result.current.isHelpOpen).toBe(true);
  });

  it('routes next-track to the live session (#4541)', () => {
    renderKeyboard();
    press('ArrowRight');
    expect(session.handleNext).toHaveBeenCalledTimes(1);
  });
});
