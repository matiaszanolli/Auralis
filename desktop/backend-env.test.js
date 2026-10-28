'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { buildBackendEnv } = require('./backend-env');

// --------------------------------------------------------------------------
// buildBackendEnv (#4898) — production spawn path must not inherit an
// ambient AURALIS_DEV_MODE that could reopen the dev-port CORS/WS allowlist.
// --------------------------------------------------------------------------

test('production path clears an ambient AURALIS_DEV_MODE=1', () => {
  const env = buildBackendEnv({ AURALIS_DEV_MODE: '1', PATH: '/usr/bin' }, false);
  assert.equal(env.AURALIS_DEV_MODE, '0');
});

test('production path clears AURALIS_DEV_MODE even when unset in the parent env', () => {
  const env = buildBackendEnv({ PATH: '/usr/bin' }, false);
  assert.equal(env.AURALIS_DEV_MODE, '0');
});

test('development path keeps AURALIS_DEV_MODE=1 when the shell already exports it', () => {
  const env = buildBackendEnv({ AURALIS_DEV_MODE: '1', PATH: '/usr/bin' }, true);
  assert.equal(env.AURALIS_DEV_MODE, '1');
});

// #5373: the dev spawn passes no --dev flag, and the :3000 renderer's WebSocket Origin is only
// admitted in backend dev mode, so the dev path must turn it on itself.
test('development path enables backend dev mode even when the shell does not export it', () => {
  const env = buildBackendEnv({ PATH: '/usr/bin' }, true);
  assert.equal(env.AURALIS_DEV_MODE, '1');
});

test('development path overrides an ambient AURALIS_DEV_MODE=0', () => {
  const env = buildBackendEnv({ AURALIS_DEV_MODE: '0' }, true);
  assert.equal(env.AURALIS_DEV_MODE, '1');
});

test('does not mutate the base env object', () => {
  const base = { AURALIS_DEV_MODE: '1' };
  buildBackendEnv(base, false);
  assert.equal(base.AURALIS_DEV_MODE, '1');
});

test('preserves other inherited env vars', () => {
  const env = buildBackendEnv({ PATH: '/usr/bin', HOME: '/home/user' }, false);
  assert.equal(env.PATH, '/usr/bin');
  assert.equal(env.HOME, '/home/user');
});
