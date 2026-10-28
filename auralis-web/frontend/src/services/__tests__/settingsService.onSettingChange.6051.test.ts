/**
 * OnSettingChange ties a setting's value to its key (#6051)
 *
 * The callback type was `(key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate])`,
 * so key and value were unrelated and `('theme', 42)` compiled. The `@ts-expect-error` lines are
 * the assertion: `pnpm run type-check` fails if one of them starts to compile.
 */

import { describe, it, expect, vi } from 'vitest';
import { isEnhancementPreset } from '@/types/domain';
import type { OnSettingChange } from '../settingsService';

describe('OnSettingChange (#6051)', () => {
  it('accepts a value of the key\'s own type and rejects the others at compile time', () => {
    const onSettingChange: OnSettingChange = vi.fn();

    onSettingChange('theme', 'light');
    onSettingChange('auto_scan', true);
    onSettingChange('scan_interval', 3600);
    onSettingChange('default_preset', 'adaptive');

    // @ts-expect-error a number is not a theme
    onSettingChange('theme', 42);
    // @ts-expect-error a string is not a boolean
    onSettingChange('auto_scan', 'yes');
    // @ts-expect-error an arbitrary string is not a preset
    onSettingChange('default_preset', 'loud');

    expect(onSettingChange).toHaveBeenCalledTimes(7);
  });

  it('isEnhancementPreset is the runtime guard the preset panel now uses', () => {
    expect(isEnhancementPreset('adaptive')).toBe(true);
    expect(isEnhancementPreset('loud')).toBe(false);
    expect(isEnhancementPreset(undefined)).toBe(false);
  });
});
