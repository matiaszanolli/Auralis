/**
 * config/api base-URL resolution (#4468)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `API_BASE_URL` / `WS_BASE_URL` were hardcoded with no env-var escape hatch,
 * while the retired standardized client (now `services/api/cacheShapeGuards.ts`) always read
 * `import.meta.env.VITE_API_URL ?? API_BASE_URL`. With port 8765 hardcoded
 * there was no way to move the backend if that port was already taken.
 *
 * Both constants are evaluated at module load, so each case stubs the env and
 * re-imports the module rather than mutating an already-resolved binding.
 */

import { describe, it, expect, afterEach, vi } from 'vitest';

async function loadConfig() {
  vi.resetModules();
  return import('../api');
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('config/api – env overrides (#4468)', () => {
  it('uses VITE_API_URL when set', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:9999');
    const { API_BASE_URL } = await loadConfig();
    expect(API_BASE_URL).toBe('http://localhost:9999');
  });

  it('uses VITE_WS_URL when set', async () => {
    vi.stubEnv('VITE_WS_URL', 'ws://localhost:9999');
    const { WS_BASE_URL } = await loadConfig();
    expect(WS_BASE_URL).toBe('ws://localhost:9999');
  });

  it('falls back to the default WS URL when VITE_WS_URL is unset', async () => {
    const { WS_BASE_URL } = await loadConfig();
    expect(WS_BASE_URL).toBe('ws://localhost:8765');
  });

  it('threads the override through getApiUrl', async () => {
    vi.stubEnv('VITE_API_URL', 'http://example.test:1234');
    const { getApiUrl } = await loadConfig();
    expect(getApiUrl('/api/tracks')).toBe('http://example.test:1234/api/tracks');
    // Paths are normalised whether or not they carry a leading slash.
    expect(getApiUrl('api/tracks')).toBe('http://example.test:1234/api/tracks');
  });

  it('matches the pattern the retired standardized client already used', async () => {
    // CONSISTENCY: that client resolves `VITE_API_URL ?? API_BASE_URL`, so with
    // the override set the two layers must agree on the same origin rather than
    // one talking to 8765 and the other to the override.
    vi.stubEnv('VITE_API_URL', 'http://localhost:7777');
    const { API_BASE_URL } = await loadConfig();
    expect(import.meta.env.VITE_API_URL ?? API_BASE_URL).toBe(API_BASE_URL);
  });
});

describe('config/api – production derives from the page origin (#5886)', () => {
  // A production page is served by the backend on whatever port --port bound;
  // a hard-coded :8765 (or a "localhost && port >= 3000" dev guess) sent REST
  // and WS to the wrong port.
  it('builds ws:// and wss:// from the page host', async () => {
    const { sameOriginWsBase } = await loadConfig();
    expect(sameOriginWsBase({ protocol: 'http:', host: 'localhost:9000' })).toBe('ws://localhost:9000');
    expect(sameOriginWsBase({ protocol: 'https:', host: 'example.test' })).toBe('wss://example.test');
  });

  it('uses the page origin for WS and same-origin REST when not on the Vite dev server', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('location', { ...window.location, protocol: 'http:', host: 'localhost:9000' });
    try {
      const { WS_BASE_URL, API_BASE_URL, getApiUrl } = await loadConfig();
      expect(WS_BASE_URL).toBe('ws://localhost:9000');
      expect(API_BASE_URL).toBe('');
      expect(getApiUrl('/api/tracks')).toBe('/api/tracks');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('keeps the dev WebSocket on the backend port', async () => {
    vi.stubEnv('DEV', true);
    const { WS_BASE_URL } = await loadConfig();
    expect(WS_BASE_URL).toBe('ws://localhost:8765');
  });
});
