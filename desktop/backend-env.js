'use strict';

// The backend is spawned with `env: { ...process.env, ... }` — the entire
// parent environment is inherited unfiltered. `is_dev_mode()`
// (auralis-web/backend/config/app.py) treats an ambient AURALIS_DEV_MODE=1
// left exported in the launching shell (a leftover dev session, a global
// dotfile export) exactly the same as an explicit `--dev` flag: it silently
// re-widens the CORS/WebSocket origin allowlist and re-enables Swagger/
// ReDoc/OpenAPI in what is otherwise a packaged production launch (#4898,
// completing the defense #4350/#4802 established).
//
// A packaged build never passes `--dev` in pythonArgs, so the only guard
// available to the *production* spawn path is to explicitly clear whatever
// AURALIS_DEV_MODE the parent shell happened to have set. The development
// spawn path is left untouched — it legitimately wants the ambient value
// (or the developer explicitly exports it), and clearing it there would
// break the intended dev workflow.

/**
 * Return the env object to pass to the spawned backend process.
 *
 * @param {NodeJS.ProcessEnv} baseEnv - the parent environment (`process.env`)
 * @param {boolean} isDevelopment - true for the development spawn path
 * @returns {NodeJS.ProcessEnv} a new env object; never mutates `baseEnv`
 */
function buildBackendEnv(baseEnv, isDevelopment) {
  const env = { ...baseEnv };
  if (!isDevelopment) {
    // Production: never let an ambient AURALIS_DEV_MODE reach the backend.
    env.AURALIS_DEV_MODE = '0';
  }
  return env;
}

module.exports = { buildBackendEnv };
