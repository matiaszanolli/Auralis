/// <reference types="node" />
/**
 * Guard: the UI fonts ship with the app, never from a font CDN (#6060)
 *
 * Auralis is a local desktop app that must render in its design-language faces
 * offline. index.html used to <link> Asap from fonts.googleapis.com (absent
 * offline, so every label fell back to the platform sans-serif), JetBrains Mono
 * was never loaded at all, and an unused Material Icons stylesheet was fetched on
 * every launch. Asap and JetBrains Mono are now bundled via @fontsource-variable
 * and the typography tokens name the family names those packages register.
 */

import { describe, it, expect } from 'vitest';
import { typography } from '@/design-system/tokens/typography';

const read = async (relative: string): Promise<string> => {
  const fs = await import('fs');
  const path = await import('path');
  return fs.readFileSync(path.join(process.cwd(), relative), 'utf-8');
};

describe('bundled fonts (#6060)', () => {
  it('index.html requests nothing from a font CDN', async () => {
    const html = await read('index.html');

    expect(html).not.toMatch(/fonts\.googleapis\.com|fonts\.gstatic\.com/);
    expect(html).not.toMatch(/Material\+Icons|Material Icons/);
  });

  it('the entry point imports both bundled font packages', async () => {
    const entry = await read('src/index.tsx');

    expect(entry).toContain("import '@fontsource-variable/asap'");
    expect(entry).toContain("import '@fontsource-variable/jetbrains-mono'");
  });

  it('both font packages are declared dependencies', async () => {
    const pkg = JSON.parse(await read('package.json')) as { dependencies: Record<string, string> };

    expect(pkg.dependencies).toHaveProperty(['@fontsource-variable/asap']);
    expect(pkg.dependencies).toHaveProperty(['@fontsource-variable/jetbrains-mono']);
  });

  it('typography tokens name the families the packages register, ahead of any fallback', () => {
    expect(typography.fontFamily.primary.startsWith('"Asap Variable"')).toBe(true);
    expect(typography.fontFamily.header.startsWith('"Asap Variable"')).toBe(true);
    expect(typography.fontFamily.mono.startsWith("'JetBrains Mono Variable'")).toBe(true);
  });
});
