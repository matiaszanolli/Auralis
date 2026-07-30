/**
 * SettingsDialog / KeyboardShortcutsHelp render-crash isolation (#4880)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * ComfortableApp already wraps the library and Player subtrees in their own
 * ErrorBoundary (#3583, #3115) so a render crash in one doesn't take the
 * others down. SettingsDialog and KeyboardShortcutsHelp were mounted as
 * plain Suspense siblings with no boundary of their own — Suspense does not
 * catch render errors, so a crash there propagated to the root boundary and
 * unmounted the whole app, including active playback.
 *
 * These tests mock each dialog to throw when opened and assert the rest of
 * the app (here: the always-visible sidebar "Songs" navigation) survives.
 */

import { describe, it, expect, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { PlaybackSessionProvider } from '@/contexts/PlaybackSessionContext';
import ComfortableApp from '../ComfortableApp';

vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: vi.fn(),
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    setVolume: vi.fn(),
    isStreaming: false,
    streamingState: 'idle',
    processedChunks: 0,
    totalChunks: 0,
    currentTime: 0,
    isPaused: false,
    isSeeking: false,
    error: null,
  }),
}));

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({ preset: 'adaptive', intensity: 1.0 }),
}));

vi.mock('@/components/settings/SettingsDialog', () => ({
  default: ({ open }: { open: boolean }) => {
    if (open) throw new Error('settings crash');
    return null;
  },
}));

vi.mock('@/components/shared/KeyboardShortcutsHelp', () => ({
  default: ({ open }: { open: boolean }) => {
    if (open) throw new Error('shortcuts help crash');
    return null;
  },
}));

function renderApp() {
  return render(
    <PlaybackSessionProvider>
      <ComfortableApp />
    </PlaybackSessionProvider>
  );
}

function pressKey(key: string, opts: KeyboardEventInit = {}) {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...opts }));
  });
}

describe('ComfortableApp dialog error boundaries (#4880)', () => {
  it('a SettingsDialog render crash does not unmount the rest of the app', async () => {
    renderApp();

    // Ctrl+, opens Settings (ComfortableApp's own shortcut binding).
    pressKey(',', { ctrlKey: true });

    expect(await screen.findByText(/Settings failed to render/i)).toBeInTheDocument();
    // The rest of the app (sidebar navigation, player) is still mounted.
    expect(screen.getByRole('region', { name: /music player/i })).toBeInTheDocument();
  });

  it('a KeyboardShortcutsHelp render crash does not unmount the rest of the app', async () => {
    renderApp();

    // '?' opens the keyboard-shortcuts help dialog.
    pressKey('?');

    expect(await screen.findByText(/Keyboard shortcuts help failed to render/i)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /music player/i })).toBeInTheDocument();
  });
});
