/**
 * Tests for useKeyboardShortcuts Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the global keyboard shortcuts functionality via the hook's array
 * API. #4692's registration-gating regression (re-register-on-every-render
 * vs. stale-handler-closure) has its own dedicated coverage in
 * useKeyboardShortcuts.registration.test.ts — this file covers the
 * behavior the underlying KeyboardShortcutsService provides through the
 * hook: input-field skipping and Mac/non-Mac modifier matching aren't
 * covered by keyboardShortcutsService.test.ts's direct unit tests, so they
 * stay here rather than being dropped.
 *
 * #5231: previously built its shortcut sets via a `KeyboardShortcutsConfig`
 * object (`useKeyboardShortcuts({ onPlayPause, onNext, ... })`) — the "V1"
 * input form deleted along with the rest of that dead code path. Rewritten
 * against the array form the hook now exclusively accepts; the preset
 * selection and KEYBOARD_SHORTCUTS-export coverage that stood here is gone
 * too, since both were reachable only through the deleted V1 branch (not,
 * as previously assumed, a live path — see #5231's investigation).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts, formatShortcut } from '../useKeyboardShortcuts';
import type { KeyboardShortcut } from '../useKeyboardShortcuts';

// Helper to create keyboard events
const createKeyboardEvent = (
  key: string,
  options: {
    code?: string;
    metaKey?: boolean;
    ctrlKey?: boolean;
    shiftKey?: boolean;
    altKey?: boolean;
    target?: Partial<HTMLElement>;
  } = {}
): KeyboardEvent => {
  const event = new KeyboardEvent('keydown', {
    key,
    code: options.code || key,
    metaKey: options.metaKey || false,
    ctrlKey: options.ctrlKey || false,
    shiftKey: options.shiftKey || false,
    altKey: options.altKey || false,
    bubbles: true,
    cancelable: true,
  });

  if (options.target) {
    Object.defineProperty(event, 'target', {
      value: options.target,
      writable: false,
    });
  }

  return event;
};

interface Handlers {
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;
  onToggleLyrics?: () => void;
  onToggleEnhancement?: () => void;
  onFocusSearch?: () => void;
  onOpenSettings?: () => void;
}

/**
 * Build the array form the real app registers (mirrors ComfortableApp.tsx's
 * shortcut set) from a sparse handler map, so tests read like the old
 * config-object form while exercising the actual production input shape.
 */
const buildShortcuts = (handlers: Handlers): KeyboardShortcut[] => {
  const isMac = navigator.platform === 'MacIntel';
  const shortcuts: KeyboardShortcut[] = [];
  if (handlers.onPlayPause) {
    shortcuts.push({ key: ' ', description: 'Play/Pause', category: 'Playback', handler: handlers.onPlayPause });
  }
  if (handlers.onNext) {
    shortcuts.push({ key: 'ArrowRight', description: 'Next track', category: 'Playback', handler: handlers.onNext });
  }
  if (handlers.onPrevious) {
    shortcuts.push({ key: 'ArrowLeft', description: 'Previous track', category: 'Playback', handler: handlers.onPrevious });
  }
  if (handlers.onVolumeUp) {
    shortcuts.push({ key: 'ArrowUp', description: 'Volume up', category: 'Playback', handler: handlers.onVolumeUp });
  }
  if (handlers.onVolumeDown) {
    shortcuts.push({ key: 'ArrowDown', description: 'Volume down', category: 'Playback', handler: handlers.onVolumeDown });
  }
  if (handlers.onMute) {
    shortcuts.push({ key: '0', description: 'Mute/Unmute', category: 'Playback', handler: handlers.onMute });
    shortcuts.push({ key: 'm', ctrl: true, description: 'Mute/Unmute', category: 'Playback', handler: handlers.onMute });
  }
  if (handlers.onToggleEnhancement) {
    shortcuts.push({ key: 'm', description: 'Toggle enhancement', category: 'Global', handler: handlers.onToggleEnhancement });
  }
  if (handlers.onToggleLyrics) {
    shortcuts.push({ key: 'l', description: 'Toggle lyrics', category: 'Global', handler: handlers.onToggleLyrics });
  }
  if (handlers.onFocusSearch) {
    shortcuts.push({ key: '/', description: 'Focus search', category: 'Navigation', handler: handlers.onFocusSearch });
    shortcuts.push({
      key: 'k',
      ...(isMac ? { meta: true } : { ctrl: true }),
      description: 'Quick search',
      category: 'Navigation',
      handler: handlers.onFocusSearch,
    });
  }
  if (handlers.onOpenSettings) {
    shortcuts.push({
      key: ',',
      ...(isMac ? { meta: true } : { ctrl: true }),
      description: 'Open settings',
      category: 'Global',
      handler: handlers.onOpenSettings,
    });
  }
  return shortcuts;
};

describe('useKeyboardShortcuts', () => {
  let handlers: Required<{ [K in keyof Handlers]: ReturnType<typeof vi.fn> }>;

  beforeEach(() => {
    vi.clearAllMocks();

    handlers = {
      onPlayPause: vi.fn(),
      onNext: vi.fn(),
      onPrevious: vi.fn(),
      onVolumeUp: vi.fn(),
      onVolumeDown: vi.fn(),
      onMute: vi.fn(),
      onToggleLyrics: vi.fn(),
      onToggleEnhancement: vi.fn(),
      onFocusSearch: vi.fn(),
      onOpenSettings: vi.fn(),
    };

    // Mock navigator.platform
    Object.defineProperty(navigator, 'platform', {
      value: 'Linux',
      writable: true,
      configurable: true,
    });
  });

  describe('Playback controls', () => {
    it('should handle Space key for play/pause', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent(' ', { code: 'Space' });
      document.dispatchEvent(event);

      expect(handlers.onPlayPause).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowRight for next track', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('ArrowRight');
      document.dispatchEvent(event);

      expect(handlers.onNext).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowLeft for previous track', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('ArrowLeft');
      document.dispatchEvent(event);

      expect(handlers.onPrevious).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should not trigger play/pause with modifier keys', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const eventWithCtrl = createKeyboardEvent(' ', { code: 'Space', ctrlKey: true });
      document.dispatchEvent(eventWithCtrl);

      const eventWithShift = createKeyboardEvent(' ', { code: 'Space', shiftKey: true });
      document.dispatchEvent(eventWithShift);

      expect(handlers.onPlayPause).not.toHaveBeenCalled();
    });
  });

  describe('Volume controls', () => {
    it('should handle ArrowUp for volume up', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('ArrowUp');
      document.dispatchEvent(event);

      expect(handlers.onVolumeUp).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowDown for volume down', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('ArrowDown');
      document.dispatchEvent(event);

      expect(handlers.onVolumeDown).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle 0 key for mute', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('0');
      document.dispatchEvent(event);

      expect(handlers.onMute).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd/Ctrl+M for mute', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('m', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onMute).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });
  });

  describe('Enhancement and display toggles', () => {
    it('should handle M key for toggle enhancement', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('m');
      document.dispatchEvent(event);

      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle uppercase M for toggle enhancement', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('M');
      document.dispatchEvent(event);

      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
    });

    it('should handle L key for toggle lyrics', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('l');
      document.dispatchEvent(event);

      expect(handlers.onToggleLyrics).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle uppercase L for toggle lyrics', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('L');
      document.dispatchEvent(event);

      expect(handlers.onToggleLyrics).toHaveBeenCalledTimes(1);
    });
  });

  describe('Navigation', () => {
    it('should handle / key for focus search', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('/');
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Ctrl+K for quick search on non-Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Win32', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('k', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd+K for quick search on Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent('k', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Ctrl+, for settings on non-Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Linux', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent(',', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onOpenSettings).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd+, for settings on Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const event = createKeyboardEvent(',', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onOpenSettings).toHaveBeenCalledTimes(1);
    });
  });

  describe('Input field handling', () => {
    it('should not trigger shortcuts in input fields', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const inputElement = document.createElement('input');
      document.body.appendChild(inputElement);
      inputElement.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'm',
        bubbles: true,
        cancelable: true,
      });

      inputElement.dispatchEvent(event);

      expect(handlers.onToggleEnhancement).not.toHaveBeenCalled();

      document.body.removeChild(inputElement);
    });

    it('should not trigger shortcuts in textarea', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const textareaElement = document.createElement('textarea');
      document.body.appendChild(textareaElement);
      textareaElement.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'l',
        bubbles: true,
        cancelable: true,
      });

      textareaElement.dispatchEvent(event);

      expect(handlers.onToggleLyrics).not.toHaveBeenCalled();

      document.body.removeChild(textareaElement);
    });

    it('should not trigger shortcuts in contentEditable elements', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const divElement = document.createElement('div');
      divElement.contentEditable = 'true';
      document.body.appendChild(divElement);
      divElement.focus();

      const event = new KeyboardEvent('keydown', {
        key: ' ',
        code: 'Space',
        bubbles: true,
        cancelable: true,
      });

      divElement.dispatchEvent(event);

      expect(handlers.onPlayPause).not.toHaveBeenCalled();

      document.body.removeChild(divElement);
    });

    it('should allow / to focus search even from input fields', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const inputElement = document.createElement('input');
      document.body.appendChild(inputElement);
      inputElement.focus();

      const event = new KeyboardEvent('keydown', {
        key: '/',
        bubbles: true,
        cancelable: true,
      });

      inputElement.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);

      document.body.removeChild(inputElement);
    });

    it('should allow / to focus global-search', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      const searchInput = document.createElement('input');
      searchInput.id = 'global-search';
      document.body.appendChild(searchInput);
      searchInput.focus();

      const event = new KeyboardEvent('keydown', {
        key: '/',
        bubbles: true,
        cancelable: true,
      });

      searchInput.dispatchEvent(event);

      // Should still call onFocusSearch even from the search input itself
      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);

      document.body.removeChild(searchInput);
    });
  });

  describe('Optional handlers', () => {
    it('should not crash when no shortcuts are registered', () => {
      renderHook(() => useKeyboardShortcuts([]));

      expect(() => {
        document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
        document.dispatchEvent(createKeyboardEvent('m'));
      }).not.toThrow();
    });

    it('should only call handlers for registered shortcuts', () => {
      const onPlayPause = vi.fn();
      const onPrevious = vi.fn();

      renderHook(() =>
        useKeyboardShortcuts([
          { key: ' ', description: 'Play/Pause', category: 'Playback', handler: onPlayPause },
          // onNext deliberately absent
          { key: 'ArrowLeft', description: 'Previous track', category: 'Playback', handler: onPrevious },
        ])
      );

      document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
      document.dispatchEvent(createKeyboardEvent('ArrowRight'));
      document.dispatchEvent(createKeyboardEvent('ArrowLeft'));

      expect(onPlayPause).toHaveBeenCalled();
      expect(onPrevious).toHaveBeenCalled();
    });
  });

  describe('Cleanup', () => {
    it('should remove event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });

    it('should not trigger handlers after unmount', () => {
      const { unmount } = renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      unmount();

      document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));

      expect(handlers.onPlayPause).not.toHaveBeenCalled();
    });
  });

  describe('Platform detection', () => {
    it('should detect Mac platform', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      // Cmd+K should work on Mac
      const event = createKeyboardEvent('k', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalled();
    });

    it('should detect non-Mac platforms', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Win32', writable: true });

      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      // Ctrl+K should work on Windows
      const event = createKeyboardEvent('k', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalled();
    });
  });

  describe('Edge cases', () => {
    it('should handle rapid key presses', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      // Rapidly press Space multiple times
      for (let i = 0; i < 10; i++) {
        document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
      }

      expect(handlers.onPlayPause).toHaveBeenCalledTimes(10);
    });

    it('should handle simultaneous different keys', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      document.dispatchEvent(createKeyboardEvent('ArrowRight'));
      document.dispatchEvent(createKeyboardEvent('m'));

      expect(handlers.onNext).toHaveBeenCalledTimes(1);
      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
    });

    it('should handle case-insensitive letters', () => {
      renderHook(() => useKeyboardShortcuts(buildShortcuts(handlers)));

      document.dispatchEvent(createKeyboardEvent('k', { ctrlKey: true }));
      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);

      document.dispatchEvent(createKeyboardEvent('K', { ctrlKey: true }));
      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(2);
    });
  });
});

// #4645: getShortcutString (a string-in/string-out "legacy alias for
// formatShortcut") had zero production consumers and was deleted. Its
// docstring's "alias" claim didn't hold — formatShortcut takes a
// ShortcutDefinition object, not a pre-formatted string, and joins modifiers
// with '' on Mac vs '+' elsewhere, unlike getShortcutString's plain
// find-and-replace. This block re-points the Mac/non-Mac modifier-symbol
// coverage getShortcutString exercised onto formatShortcut's real API,
// asserting formatShortcut's actual output rather than the old function's.
describe('formatShortcut (Mac/non-Mac modifier symbols)', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'platform', {
      value: 'Linux',
      writable: true,
      configurable: true,
    });
  });

  it('renders Ctrl/Cmd as ⌘ on Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'MacIntel' });

    const result = formatShortcut({ key: 'k', ctrl: true, description: 'Test', category: 'Global' });

    expect(result).toBe('⌘K');
  });

  it('renders Ctrl as Ctrl on non-Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'Win32' });

    const result = formatShortcut({ key: 'k', ctrl: true, description: 'Test', category: 'Global' });

    expect(result).toBe('Ctrl+K');
  });

  it('renders meta as Ctrl on non-Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'Linux' });

    const result = formatShortcut({ key: ',', meta: true, description: 'Test', category: 'Global' });

    expect(result).toBe('Ctrl+,');
  });

  it('handles shortcuts without modifiers', () => {
    const result = formatShortcut({ key: ' ', description: 'Test', category: 'Global' });

    expect(result).toBe('Space');
  });
});
