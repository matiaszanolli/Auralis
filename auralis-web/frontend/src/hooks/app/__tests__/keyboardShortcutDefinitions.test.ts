import { describe, it, expect } from 'vitest';
import {
  SHORTCUT_CONFIG_MAP,
  PRESET_SHORTCUTS,
  PRESET_NAMES,
  createShortcutDefinition,
} from '../keyboardShortcutDefinitions';

describe('keyboardShortcutDefinitions', () => {
  describe('SHORTCUT_CONFIG_MAP', () => {
    it('should have at least 20 entries', () => {
      expect(SHORTCUT_CONFIG_MAP.length).toBeGreaterThanOrEqual(20);
    });

    it('should have unique configKeys', () => {
      const keys = SHORTCUT_CONFIG_MAP.map((e) => e.configKey);
      expect(new Set(keys).size).toBe(keys.length);
    });

    it('should have no duplicate key+modifier combos within the same category', () => {
      const seen = new Set<string>();
      for (const entry of SHORTCUT_CONFIG_MAP) {
        for (const shortcut of entry.shortcuts) {
          const id = [
            shortcut.key,
            shortcut.category,
            shortcut.modifiers?.ctrl ? 'ctrl' : '',
            shortcut.modifiers?.shift ? 'shift' : '',
            shortcut.modifiers?.meta ? 'meta' : '',
            shortcut.modifiers?.alt ? 'alt' : '',
          ].join('|');
          expect(seen.has(id), `duplicate shortcut: ${id}`).toBe(false);
          seen.add(id);
        }
      }
    });

    it('every entry should have a valid category', () => {
      const validCategories = new Set(['Playback', 'Navigation', 'Library', 'Queue', 'Global', 'Presets']);
      for (const entry of SHORTCUT_CONFIG_MAP) {
        for (const shortcut of entry.shortcuts) {
          expect(validCategories.has(shortcut.category), `invalid category: ${shortcut.category}`).toBe(true);
        }
      }
    });

    it('every entry should have a non-empty description', () => {
      for (const entry of SHORTCUT_CONFIG_MAP) {
        for (const shortcut of entry.shortcuts) {
          expect(shortcut.description.length).toBeGreaterThan(0);
        }
      }
    });

    it('every handler should return a function when config provides it', () => {
      const mockFn = () => {};
      for (const entry of SHORTCUT_CONFIG_MAP) {
        const config = { [entry.configKey]: mockFn } as any;
        expect(entry.handler(config)).toBe(mockFn);
      }
    });

    it('every handler should return undefined when config does not provide it', () => {
      for (const entry of SHORTCUT_CONFIG_MAP) {
        const config = {} as any;
        expect(entry.handler(config)).toBeUndefined();
      }
    });
  });

  describe('PRESET_SHORTCUTS', () => {
    it('should have 5 preset entries', () => {
      expect(PRESET_SHORTCUTS).toHaveLength(5);
    });

    it('should map keys 1-5', () => {
      expect(PRESET_SHORTCUTS.map((s) => s.key)).toEqual(['1', '2', '3', '4', '5']);
    });

    it('should all be in Presets category', () => {
      for (const shortcut of PRESET_SHORTCUTS) {
        expect(shortcut.category).toBe('Presets');
      }
    });
  });

  describe('PRESET_NAMES', () => {
    it('should have 5 names matching shortcuts', () => {
      expect(PRESET_NAMES).toHaveLength(PRESET_SHORTCUTS.length);
    });

    it('should contain known preset names', () => {
      expect(PRESET_NAMES).toEqual(['adaptive', 'gentle', 'warm', 'bright', 'punchy']);
    });
  });

  describe('createShortcutDefinition', () => {
    it('should create definition with key, category, and description', () => {
      const result = createShortcutDefinition({
        key: 'a',
        category: 'Playback',
        description: 'Test action',
      });
      expect(result).toEqual({
        key: 'a',
        category: 'Playback',
        description: 'Test action',
      });
    });

    it('should include modifier flags when present', () => {
      const result = createShortcutDefinition({
        key: 'k',
        category: 'Navigation',
        description: 'Search',
        modifiers: { ctrl: true, shift: true },
      });
      expect(result).toEqual({
        key: 'k',
        category: 'Navigation',
        description: 'Search',
        ctrl: true,
        shift: true,
      });
    });

    it('should map Presets category to Global', () => {
      const result = createShortcutDefinition({
        key: '1',
        category: 'Presets',
        description: 'Adaptive',
      });
      expect(result.category).toBe('Global');
    });

    it('should not include false modifier flags', () => {
      const result = createShortcutDefinition({
        key: 'x',
        category: 'Global',
        description: 'Test',
        modifiers: { ctrl: false, shift: false },
      });
      expect(result).not.toHaveProperty('ctrl');
      expect(result).not.toHaveProperty('shift');
    });
  });
});
