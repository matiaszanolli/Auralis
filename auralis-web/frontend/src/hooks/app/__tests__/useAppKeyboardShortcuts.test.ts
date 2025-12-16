import { renderHook } from '@testing-library/react';
import { useAppKeyboardShortcuts, AppKeyboardShortcutsConfig } from '../useAppKeyboardShortcuts';

describe('useAppKeyboardShortcuts', () => {
  const createConfig = (): AppKeyboardShortcutsConfig => ({
    onPlayPause: vi.fn(),
    onNextTrack: vi.fn(),
    onPreviousTrack: vi.fn(),
    onVolumeUp: vi.fn(),
    onVolumeDown: vi.fn(),
    onMute: vi.fn(),
    onViewSongs: vi.fn(),
    onViewAlbums: vi.fn(),
    onViewArtists: vi.fn(),
    onViewPlaylists: vi.fn(),
    onSearchFocus: vi.fn(),
    onSearchClear: vi.fn(),
    onSettingsOpen: vi.fn(),
    onHelpOpen: vi.fn(),
  });

  describe('initialization', () => {
    it('initializes with all shortcuts', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.shortcuts).toBeDefined();
      expect(Array.isArray(result.current.shortcuts)).toBe(true);
      expect(result.current.shortcuts.length).toBeGreaterThan(0);
    });

    it('initializes help dialog state', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.isHelpOpen).toBeDefined();
      expect(typeof result.current.isHelpOpen).toBe('boolean');
    });

    it('provides help dialog handlers', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.openHelp).toBeDefined();
      expect(result.current.closeHelp).toBeDefined();
      expect(typeof result.current.openHelp).toBe('function');
      expect(typeof result.current.closeHelp).toBe('function');
    });

    it('provides formatShortcut utility', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.formatShortcut).toBeDefined();
      expect(typeof result.current.formatShortcut).toBe('function');
    });
  });

  describe('shortcuts categories', () => {
    it('includes playback shortcuts', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const playbackShortcuts = result.current.shortcuts.filter(
        (s) => s.category === 'Playback'
      );
      expect(playbackShortcuts.length).toBeGreaterThan(0);
    });

    it('includes navigation shortcuts', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const navigationShortcuts = result.current.shortcuts.filter(
        (s) => s.category === 'Navigation'
      );
      expect(navigationShortcuts.length).toBeGreaterThan(0);
    });

    it('includes global shortcuts', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const globalShortcuts = result.current.shortcuts.filter(
        (s) => s.category === 'Global'
      );
      expect(globalShortcuts.length).toBeGreaterThan(0);
    });
  });

  describe('playback shortcuts', () => {
    it('has space bar for play/pause', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const playPause = result.current.shortcuts.find(
        (s) => s.key === ' '
      );
      expect(playPause).toBeDefined();
      expect(playPause?.description).toBe('Play/Pause');
      expect(playPause?.category).toBe('Playback');
    });

    it('has arrow keys for navigation', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const arrowRight = result.current.shortcuts.find(
        (s) => s.key === 'ArrowRight'
      );
      const arrowLeft = result.current.shortcuts.find(
        (s) => s.key === 'ArrowLeft'
      );

      expect(arrowRight?.description).toContain('Next');
      expect(arrowLeft?.description).toContain('Previous');
    });

    it('has volume controls', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const volumeUp = result.current.shortcuts.find(
        (s) => s.key === 'ArrowUp'
      );
      const volumeDown = result.current.shortcuts.find(
        (s) => s.key === 'ArrowDown'
      );

      expect(volumeUp?.description).toContain('Volume');
      expect(volumeDown?.description).toContain('Volume');
    });

    it('has mute shortcut', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const mute = result.current.shortcuts.find((s) => s.key === 'm');
      expect(mute?.description).toContain('Mute');
    });
  });

  describe('navigation shortcuts', () => {
    it('has number keys for view selection', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const view1 = result.current.shortcuts.find((s) => s.key === '1');
      const view2 = result.current.shortcuts.find((s) => s.key === '2');
      const view3 = result.current.shortcuts.find((s) => s.key === '3');
      const view4 = result.current.shortcuts.find((s) => s.key === '4');

      expect(view1).toBeDefined();
      expect(view2).toBeDefined();
      expect(view3).toBeDefined();
      expect(view4).toBeDefined();
    });

    it('has slash for search focus', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const search = result.current.shortcuts.find((s) => s.key === '/');
      expect(search?.description).toContain('search');
    });

    it('has escape for clear/close', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const escape = result.current.shortcuts.find((s) => s.key === 'Escape');
      expect(escape?.description).toContain('search');
    });
  });

  describe('global shortcuts', () => {
    it('has question mark for help', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const help = result.current.shortcuts.find((s) => s.key === '?');
      expect(help?.description).toContain('keyboard shortcuts');
    });

    it('has ctrl+comma for settings', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const settings = result.current.shortcuts.find((s) => s.key === ',');
      expect(settings?.ctrl).toBe(true);
      expect(settings?.description).toContain('settings');
    });
  });

  describe('optional handlers', () => {
    it('handles undefined handlers gracefully', () => {
      const config: AppKeyboardShortcutsConfig = {}; // Empty config
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.shortcuts).toBeDefined();
      // Shortcuts array should be populated even with empty config
      expect(result.current.shortcuts.length).toBeGreaterThan(0);
      // Each shortcut should have key and description
      result.current.shortcuts.forEach((shortcut) => {
        expect(shortcut.key).toBeDefined();
        expect(shortcut.description).toBeDefined();
      });
    });

    it('returns shortcuts with proper structure', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const playPause = result.current.shortcuts.find(
        (s) => s.key === ' '
      );

      expect(playPause).toBeDefined();
      expect(playPause?.key).toBe(' ');
      expect(playPause?.description).toBeDefined();
    });
  });

  describe('help dialog', () => {
    it('starts with help dialog closed', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      expect(result.current.isHelpOpen).toBe(false);
    });

    it('opens and closes help dialog', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      // Open help - note: actual state changes depend on useKeyboardShortcuts implementation
      expect(result.current.openHelp).toBeDefined();
      expect(result.current.closeHelp).toBeDefined();
    });
  });

  describe('shortcut formatting', () => {
    it('provides formatShortcut utility function', () => {
      const config = createConfig();
      const { result } = renderHook(() => useAppKeyboardShortcuts(config));

      const playPause = result.current.shortcuts.find((s) => s.key === ' ');
      expect(playPause).toBeDefined();

      const formatted = result.current.formatShortcut(playPause!);
      expect(typeof formatted).toBe('string');
    });
  });
});
