/**
 * SettingsResponse sends theme / language / output_device as `str | None` (the columns are
 * nullable), so UserSettings must not promise `string` for them (#6438). The
 * @ts-expect-error lines are the contract: `pnpm run type-check` fails if they stop erroring.
 */
import { describe, it, expect } from 'vitest';
import type { UserSettings } from '../settingsService';

describe('UserSettings nullable string fields (#6438)', () => {
  it('types theme, language and output_device as string | null', () => {
    const wire: Pick<UserSettings, 'theme' | 'language' | 'output_device'> = {
      theme: null,
      language: null,
      output_device: null,
    };
    // @ts-expect-error -- theme can be null on the wire, so it cannot be used as a string unchecked
    const theme: string = wire.theme;
    // @ts-expect-error -- same for language
    const language: string = wire.language;
    // @ts-expect-error -- same for output_device
    const device: string = wire.output_device;
    expect([theme, language, device]).toEqual([null, null, null]);
  });
});
