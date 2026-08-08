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

test('development path leaves an ambient AURALIS_DEV_MODE untouched', () => {
  const env = buildBackendEnv({ AURALIS_DEV_MODE: '1', PATH: '/usr/bin' }, true);
  assert.equal(env.AURALIS_DEV_MODE, '1');
});

test('development path does not fabricate AURALIS_DEV_MODE when unset', () => {
  const env = buildBackendEnv({ PATH: '/usr/bin' }, true);
  assert.equal('AURALIS_DEV_MODE' in env, false);
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
