/**
 * config/api base-URL resolution (#4468)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `API_BASE_URL` / `WS_BASE_URL` were hardcoded with no env-var escape hatch,
 * while `services/api/standardizedAPIClient.ts` had always read
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

  it('threads the override through getWsUrl', async () => {
    vi.stubEnv('VITE_WS_URL', 'ws://example.test:1234');
    const { getWsUrl } = await loadConfig();
    expect(getWsUrl('/ws')).toBe('ws://example.test:1234/ws');
  });

  it('matches the pattern standardizedAPIClient already used', async () => {
    // CONSISTENCY: that client resolves `VITE_API_URL ?? API_BASE_URL`, so with
    // the override set the two layers must agree on the same origin rather than
    // one talking to 8765 and the other to the override.
    vi.stubEnv('VITE_API_URL', 'http://localhost:7777');
    const { API_BASE_URL } = await loadConfig();
    expect(import.meta.env.VITE_API_URL ?? API_BASE_URL).toBe(API_BASE_URL);
  });
});
