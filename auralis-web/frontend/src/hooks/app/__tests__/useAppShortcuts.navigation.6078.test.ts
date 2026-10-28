/**
 * The navigation and global shortcuts in useAppShortcuts (#6078)
 *
 * ComfortableApp.test covers the playback keys; nothing exercised 1/2/3 (view switch + toast), `/`
 * (focus and select the search field), Escape (clear search first, otherwise close Settings), `?`
 * (open help) or Ctrl+, (open Settings). The table is a pure memo over its arguments, so each
 * handler is looked up by key and run against spies.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAppShortcuts } from '../useAppShortcuts';

function setup(overrides: Partial<Parameters<typeof useAppShortcuts>[0]> = {}) {
  const args = {
    session: { isCommandPending: false, handleMuteToggle: vi.fn().mockResolvedValue(true) },
    togglePlayPause: vi.fn(),
    isPlaying: false,
    nextTrack: vi.fn(),
    previousTrack: vi.fn(),
    getVolume: () => 50,
    setVolume: vi.fn(),
    info: vi.fn(),
    searchQuery: '',
    setSearchQuery: vi.fn(),
    settingsOpen: false,
    setSettingsOpen: vi.fn(),
    setCurrentView: vi.fn(),
    openHelpRef: { current: vi.fn() },
    ...overrides,
  };
  const { result } = renderHook(() => useAppShortcuts(args));
  const run = (key: string, ctrl = false) => {
    const shortcut = result.current.find((s) => s.key === key && Boolean(s.ctrl) === ctrl);
    if (!shortcut) throw new Error(`no shortcut for ${ctrl ? 'Ctrl+' : ''}${key}`);
    shortcut.handler();
  };
  return { args, run };
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('view shortcuts', () => {
  it.each([
    ['1', 'songs', 'Songs view'],
    ['2', 'albums', 'Albums view'],
    ['3', 'artists', 'Artists view'],
  ])('%s switches to %s and announces it', (key, view, message) => {
    const { args, run } = setup();

    run(key);

    expect(args.setCurrentView).toHaveBeenCalledWith(view);
    expect(args.info).toHaveBeenCalledWith(message);
  });

  it('has no "4" shortcut (the Playlists view it opened does not exist, #5620)', () => {
    const { run } = setup();

    expect(() => run('4')).toThrow('no shortcut');
  });
});

describe('"/" focuses and selects the search field', () => {
  it('focuses input[data-search-input] and selects its text', () => {
    document.body.innerHTML = '<input data-search-input value="queen" />';
    const input = document.querySelector<HTMLInputElement>('input[data-search-input]')!;
    const select = vi.spyOn(input, 'select');
    const { run } = setup();

    run('/');

    expect(input).toHaveFocus();
    expect(select).toHaveBeenCalledOnce();
  });

  it('does nothing when there is no search field', () => {
    const { run } = setup();

    expect(() => run('/')).not.toThrow();
  });
});

describe('Escape', () => {
  it('clears an active search first and leaves Settings alone', () => {
    const { args, run } = setup({ searchQuery: 'queen', settingsOpen: true });

    run('Escape');

    expect(args.setSearchQuery).toHaveBeenCalledWith('');
    expect(args.info).toHaveBeenCalledWith('Search cleared');
    expect(args.setSettingsOpen).not.toHaveBeenCalled();
  });

  it('closes Settings when there is no search to clear', () => {
    const { args, run } = setup({ searchQuery: '', settingsOpen: true });

    run('Escape');

    expect(args.setSettingsOpen).toHaveBeenCalledWith(false);
    expect(args.setSearchQuery).not.toHaveBeenCalled();
  });

  it('does nothing when neither is open', () => {
    const { args, run } = setup();

    run('Escape');

    expect(args.setSearchQuery).not.toHaveBeenCalled();
    expect(args.setSettingsOpen).not.toHaveBeenCalled();
  });
});

describe('global shortcuts', () => {
  it('? opens the help dialog through the ref', () => {
    const { args, run } = setup();

    run('?');

    expect(args.openHelpRef.current).toHaveBeenCalledOnce();
  });

  it('? is safe before the help opener is attached', () => {
    const { run } = setup({ openHelpRef: { current: null } });

    expect(() => run('?')).not.toThrow();
  });

  it('Ctrl+, opens Settings', () => {
    const { args, run } = setup();

    run(',', true);

    expect(args.setSettingsOpen).toHaveBeenCalledWith(true);
  });
});

describe('volume shortcuts read the volume at keypress time (#6067)', () => {
  it('ArrowUp/ArrowDown step from the volume now, without the table being rebuilt', () => {
    let volume = 50;
    const { args, run } = setup({ getVolume: () => volume });

    run('ArrowUp');
    expect(args.setVolume).toHaveBeenLastCalledWith(60);

    volume = 95; // changed by the slider; no re-render of the shell happened
    run('ArrowUp');
    expect(args.setVolume).toHaveBeenLastCalledWith(100);

    volume = 5;
    run('ArrowDown');
    expect(args.setVolume).toHaveBeenLastCalledWith(0);
  });

  it('does not rebuild the shortcut table when the volume changes', () => {
    let volume = 50;
    const args = setup({ getVolume: () => volume }).args;
    const { result, rerender } = renderHook(() => useAppShortcuts(args));
    const before = result.current;

    volume = 80;
    rerender();

    expect(result.current).toBe(before);
  });
});
