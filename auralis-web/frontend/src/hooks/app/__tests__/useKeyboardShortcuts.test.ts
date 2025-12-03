/**
 * Tests for useKeyboardShortcuts Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the global keyboard shortcuts functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts, getShortcutString, KEYBOARD_SHORTCUTS } from '../useKeyboardShortcuts';

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

describe('useKeyboardShortcuts', () => {
  let handlers: Record<string, ReturnType<typeof vi.fn>>;

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
      onPresetChange: vi.fn(),
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
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent(' ', { code: 'Space' });
      document.dispatchEvent(event);

      expect(handlers.onPlayPause).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowRight for next track', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('ArrowRight');
      document.dispatchEvent(event);

      expect(handlers.onNext).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowLeft for previous track', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('ArrowLeft');
      document.dispatchEvent(event);

      expect(handlers.onPrevious).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should not trigger play/pause with modifier keys', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const eventWithCtrl = createKeyboardEvent(' ', { code: 'Space', ctrlKey: true });
      document.dispatchEvent(eventWithCtrl);

      const eventWithShift = createKeyboardEvent(' ', { code: 'Space', shiftKey: true });
      document.dispatchEvent(eventWithShift);

      expect(handlers.onPlayPause).not.toHaveBeenCalled();
    });
  });

  describe('Volume controls', () => {
    it('should handle ArrowUp for volume up', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('ArrowUp');
      document.dispatchEvent(event);

      expect(handlers.onVolumeUp).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle ArrowDown for volume down', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('ArrowDown');
      document.dispatchEvent(event);

      expect(handlers.onVolumeDown).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle 0 key for mute', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('0');
      document.dispatchEvent(event);

      expect(handlers.onMute).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd/Ctrl+M for mute', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('m', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onMute).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });
  });

  describe('Enhancement and display toggles', () => {
    it('should handle M key for toggle enhancement', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('m');
      document.dispatchEvent(event);

      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle uppercase M for toggle enhancement', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('M');
      document.dispatchEvent(event);

      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
    });

    it('should handle L key for toggle lyrics', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('l');
      document.dispatchEvent(event);

      expect(handlers.onToggleLyrics).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle uppercase L for toggle lyrics', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('L');
      document.dispatchEvent(event);

      expect(handlers.onToggleLyrics).toHaveBeenCalledTimes(1);
    });
  });

  describe('Navigation', () => {
    it('should handle / key for focus search', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('/');
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Ctrl+K for quick search on non-Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Win32', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('k', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd+K for quick search on Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('k', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Ctrl+, for settings on non-Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Linux', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent(',', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onOpenSettings).toHaveBeenCalledTimes(1);
      expect(event.defaultPrevented).toBe(true);
    });

    it('should handle Cmd+, for settings on Mac', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent(',', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onOpenSettings).toHaveBeenCalledTimes(1);
    });
  });

  describe('Preset selection', () => {
    const presets = [
      { key: '1', name: 'adaptive' },
      { key: '2', name: 'gentle' },
      { key: '3', name: 'warm' },
      { key: '4', name: 'bright' },
      { key: '5', name: 'punchy' },
    ];

    presets.forEach(({ key, name }) => {
      it(`should handle ${key} key for ${name} preset`, () => {
        renderHook(() => useKeyboardShortcuts(handlers));

        const event = createKeyboardEvent(key);
        document.dispatchEvent(event);

        expect(handlers.onPresetChange).toHaveBeenCalledWith(name);
        expect(event.defaultPrevented).toBe(true);
      });
    });

    it('should not handle keys 6-9', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      ['6', '7', '8', '9'].forEach(key => {
        const event = createKeyboardEvent(key);
        document.dispatchEvent(event);
      });

      expect(handlers.onPresetChange).not.toHaveBeenCalled();
    });

    it('should not trigger preset with modifier keys', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const event = createKeyboardEvent('1', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onPresetChange).not.toHaveBeenCalled();
    });
  });

  describe('Input field handling', () => {
    it('should not trigger shortcuts in input fields', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

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
      renderHook(() => useKeyboardShortcuts(handlers));

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
      renderHook(() => useKeyboardShortcuts(handlers));

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
      renderHook(() => useKeyboardShortcuts(handlers));

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
      renderHook(() => useKeyboardShortcuts(handlers));

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
    it('should not crash when handlers are undefined', () => {
      renderHook(() => useKeyboardShortcuts({}));

      expect(() => {
        document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
        document.dispatchEvent(createKeyboardEvent('m'));
        document.dispatchEvent(createKeyboardEvent('1'));
      }).not.toThrow();
    });

    it('should only call defined handlers', () => {
      const partialHandlers = {
        onPlayPause: vi.fn(),
        // onNext not defined
        onPrevious: vi.fn(),
      };

      renderHook(() => useKeyboardShortcuts(partialHandlers));

      document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
      document.dispatchEvent(createKeyboardEvent('ArrowRight'));
      document.dispatchEvent(createKeyboardEvent('ArrowLeft'));

      expect(partialHandlers.onPlayPause).toHaveBeenCalled();
      expect(partialHandlers.onPrevious).toHaveBeenCalled();
    });
  });

  describe('Cleanup', () => {
    it('should remove event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useKeyboardShortcuts(handlers));

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });

    it('should not trigger handlers after unmount', () => {
      const { unmount } = renderHook(() => useKeyboardShortcuts(handlers));

      unmount();

      document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));

      expect(handlers.onPlayPause).not.toHaveBeenCalled();
    });
  });

  describe('Platform detection', () => {
    it('should detect Mac platform', () => {
      Object.defineProperty(navigator, 'platform', { value: 'MacIntel', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      // Cmd+K should work on Mac
      const event = createKeyboardEvent('k', { metaKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalled();
    });

    it('should detect non-Mac platforms', () => {
      Object.defineProperty(navigator, 'platform', { value: 'Win32', writable: true });

      renderHook(() => useKeyboardShortcuts(handlers));

      // Ctrl+K should work on Windows
      const event = createKeyboardEvent('k', { ctrlKey: true });
      document.dispatchEvent(event);

      expect(handlers.onFocusSearch).toHaveBeenCalled();
    });
  });

  describe('Edge cases', () => {
    it('should handle rapid key presses', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      // Rapidly press Space multiple times
      for (let i = 0; i < 10; i++) {
        document.dispatchEvent(createKeyboardEvent(' ', { code: 'Space' }));
      }

      expect(handlers.onPlayPause).toHaveBeenCalledTimes(10);
    });

    it('should handle simultaneous different keys', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      document.dispatchEvent(createKeyboardEvent('ArrowRight'));
      document.dispatchEvent(createKeyboardEvent('m'));
      document.dispatchEvent(createKeyboardEvent('1'));

      expect(handlers.onNext).toHaveBeenCalledTimes(1);
      expect(handlers.onToggleEnhancement).toHaveBeenCalledTimes(1);
      expect(handlers.onPresetChange).toHaveBeenCalledWith('adaptive');
    });

    it('should handle case-insensitive letters', () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      document.dispatchEvent(createKeyboardEvent('k', { ctrlKey: true }));
      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);

      document.dispatchEvent(createKeyboardEvent('K', { ctrlKey: true }));
      expect(handlers.onFocusSearch).toHaveBeenCalledTimes(2);
    });
  });
});

describe('getShortcutString', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'platform', {
      value: 'Linux',
      writable: true,
      configurable: true,
    });
  });

  it('should replace Cmd with ⌘ on Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'MacIntel' });

    const result = getShortcutString('Cmd+K');

    expect(result).toBe('⌘+K');
  });

  it('should replace Ctrl with Ctrl on non-Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'Win32' });

    const result = getShortcutString('Ctrl+K');

    expect(result).toBe('Ctrl+K');
  });

  it('should replace Cmd with Ctrl on non-Mac', () => {
    Object.defineProperty(navigator, 'platform', { value: 'Linux' });

    const result = getShortcutString('Cmd+,');

    expect(result).toBe('Ctrl+,');
  });

  it('should handle strings without modifiers', () => {
    const result = getShortcutString('Space');

    expect(result).toBe('Space');
  });
});

describe('KEYBOARD_SHORTCUTS', () => {
  it('should export list of all shortcuts', () => {
    expect(KEYBOARD_SHORTCUTS).toBeDefined();
    expect(Array.isArray(KEYBOARD_SHORTCUTS)).toBe(true);
    expect(KEYBOARD_SHORTCUTS.length).toBeGreaterThan(0);
  });

  it('should have valid structure for each shortcut', () => {
    KEYBOARD_SHORTCUTS.forEach(shortcut => {
      expect(shortcut).toHaveProperty('key');
      expect(shortcut).toHaveProperty('action');
      expect(shortcut).toHaveProperty('category');
      expect(typeof shortcut.key).toBe('string');
      expect(typeof shortcut.action).toBe('string');
      expect(typeof shortcut.category).toBe('string');
    });
  });

  it('should include all preset shortcuts', () => {
    const presetShortcuts = KEYBOARD_SHORTCUTS.filter(s => s.category === 'Presets');

    expect(presetShortcuts).toHaveLength(5);
    expect(presetShortcuts.map(s => s.key)).toEqual(['1', '2', '3', '4', '5']);
  });

  it('should include playback controls', () => {
    const playbackShortcuts = KEYBOARD_SHORTCUTS.filter(s => s.category === 'Playback');

    expect(playbackShortcuts.length).toBeGreaterThan(0);
    expect(playbackShortcuts.some(s => s.action === 'Play/Pause')).toBe(true);
    expect(playbackShortcuts.some(s => s.action === 'Next track')).toBe(true);
  });

  it('should include navigation shortcuts', () => {
    const navigationShortcuts = KEYBOARD_SHORTCUTS.filter(s => s.category === 'Navigation');

    expect(navigationShortcuts.length).toBeGreaterThan(0);
    expect(navigationShortcuts.some(s => s.action === 'Focus search')).toBe(true);
  });
});
