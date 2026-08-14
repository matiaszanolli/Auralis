/**
 * The vendor chunk rule keeps its module-initialisation-order guarantee (#4697)
 *
 * `manualChunks` exists for one reason: React, ReactDOM, MUI and Emotion must
 * initialise before application code, or a packaged Electron/AppImage build
 * dies with `'Paper is not defined'`. That failure only reproduces in a
 * packaged build — never in `vite dev` or `vite preview` — so a change here is
 * shipped before anyone notices.
 *
 * #4697 asked for Redux / React Query / react-virtual / dnd to be split out of
 * the eager `App` chunk as well, and that was measured and declined (see the
 * comment in vite.manualChunks.ts). These tests pin the parts that must not drift:
 * the three families that must land in `vendor`, and application code that
 * must not.
 */

import { describe, expect, it } from 'vitest';

import { vendorChunk } from '../../vite.manualChunks';

describe('vendor chunk rule (#4697)', () => {
  it.each([
    ['react', '/app/node_modules/react/index.js'],
    ['react-dom', '/app/node_modules/react-dom/client.js'],
    ['@mui/material', '/app/node_modules/@mui/material/Paper/Paper.mjs'],
    ['@emotion/react', '/app/node_modules/@emotion/react/dist/index.mjs'],
  ])('routes %s into the vendor chunk', (_label, id) => {
    expect(vendorChunk(id)).toBe('vendor');
  });

  it('leaves application code out of the vendor chunk', () => {
    expect(vendorChunk('/app/src/ComfortableApp.tsx')).toBeUndefined();
    expect(vendorChunk('/app/src/components/core/AppContainer.tsx')).toBeUndefined();
  });

  it('does not split the declined #4697 libraries into their own chunks', () => {
    // Not a style preference: an extra *eager* chunk removes no startup work on
    // localhost and reintroduces the module-init-order risk. If this ever needs
    // to change, it must be verified in a packaged AppImage build, not `preview`.
    for (const id of [
      '/app/node_modules/@reduxjs/toolkit/dist/redux-toolkit.modern.mjs',
      '/app/node_modules/@tanstack/query-core/build/modern/query.js',
      '/app/node_modules/@hello-pangea/dnd/dist/dnd.esm.js',
    ]) {
      expect(vendorChunk(id)).toBeUndefined();
    }
  });

  it('is the same function the build actually uses', async () => {
    // Guards against the config drifting back to an inline copy, which would
    // leave these assertions passing against a rule nothing runs.
    const config = await import('../../vite.config.mts?raw');

    expect(config.default).toContain("from './vite.manualChunks'");
    expect(config.default).toContain('manualChunks: vendorChunk');
  });
});
