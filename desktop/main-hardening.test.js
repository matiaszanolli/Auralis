'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// main.js needs the real electron API at module scope, so, like preload.test.js, these checks read
// the sources as text (#6174).
const MAIN_SRC = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
const PACKAGE = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));

test('every IPC handler goes through handleTrusted, never a bare ipcMain.handle', () => {
  const bare = [...MAIN_SRC.matchAll(/ipcMain\.handle\(\s*'([^']+)'/g)].map((m) => m[1]);
  assert.deepEqual(bare, [], `unchecked IPC channels: ${bare.join(', ')}`);
  assert.ok(MAIN_SRC.includes('isTrustedIpcSender(event'), 'handleTrusted must check the sender');
});

test('web permissions are denied by default', () => {
  assert.ok(MAIN_SRC.includes('setPermissionRequestHandler('));
  assert.ok(MAIN_SRC.includes('callback(false);'), 'the request handler must deny');
  assert.equal(/callback\(true\)/.test(MAIN_SRC), false);
  assert.match(MAIN_SRC, /setPermissionCheckHandler\(\(\)\s*=>\s*false\)/);
});

test('the packaged app flips the Electron fuses that expose Node to the environment', () => {
  const fuses = PACKAGE.build.electronFuses;
  assert.equal(fuses.runAsNode, false);
  assert.equal(fuses.enableNodeOptionsEnvironmentVariable, false);
  assert.equal(fuses.enableNodeCliInspectArguments, false);
  assert.equal(fuses.onlyLoadAppFromAsar, true);
});

test('nothing in main.js relies on ELECTRON_RUN_AS_NODE, which the runAsNode fuse disables', () => {
  assert.equal(/RUN_AS_NODE/.test(MAIN_SRC), false);
});

test('the app stops only the backend it spawned, never a listener it found on the port (#6518)', () => {
  // cleanupPort() used to look up whatever listened on 8765 and SIGTERM/SIGKILL it when its command
  // line merely contained "auralis-backend" or ".../backend/main.py", so an unrelated same-user service
  // was killed on every launch. A second launch is now refused by the single-instance lock (#6157).
  const sources = fs.readdirSync(__dirname)
    .filter((name) => name.endsWith('.js') && !name.endsWith('.test.js'))
    .map((name) => [name, fs.readFileSync(path.join(__dirname, name), 'utf8')]);
  for (const [name, src] of sources) {
    assert.equal(/\b(lsof|netstat|fuser)\b|sTCP:LISTEN/.test(src), false, `${name} discovers port listeners`);
  }
  assert.ok(MAIN_SRC.includes('requestSingleInstanceLock('), 'a second launch must be refused, not resolved by killing');
});

function handlerBody(event) {
  const start = MAIN_SRC.indexOf(`app.on('${event}'`);
  assert.notEqual(start, -1, `no app.on('${event}') handler`);
  const end = MAIN_SRC.indexOf('\n});', start);
  return MAIN_SRC.slice(start, end);
}

test('closing the last window and reopening never leaves the quit path skipping backend cleanup (#6521)', () => {
  // cleanup() sets isQuitting for good. When window-all-closed called it on macOS, a dock reopen
  // spawned a new backend with the flag still set, and before-quit, gated on isQuitting, then
  // skipped cleanup: the second backend outlived the app.
  assert.equal(/cleanup\(/.test(handlerBody('window-all-closed')), false,
    'window-all-closed must not stop the backend (macOS keeps the app, and its backend, alive)');
  const beforeQuit = handlerBody('before-quit');
  assert.equal(/isQuitting/.test(beforeQuit), false, 'before-quit must not be gated on the sticky isQuitting flag');
  assert.match(beforeQuit, /auralisApp\.cleanup\(\)\.then/, 'before-quit must wait for the backend to stop');
  assert.match(MAIN_SRC, /if \(!this\.initialized\) \{[\s\S]*?this\.startPythonBackend\(\)/,
    'a reactivation (initialized) must reuse the running backend, not spawn a second one');
});

test('the packaged backend is spawned with a stdin lifeline it exits on (#6720)', () => {
  // A crashed or SIGKILLed main process never runs before-quit, so the backend outlived it and
  // held the port, failing every later launch. The OS closes this pipe when the app exits by any
  // means; the backend (config/parent_lifeline.py) shuts down on end-of-file.
  assert.match(MAIN_SRC, /stdio: \['pipe', 'pipe', 'pipe'\]/, 'the backend needs a stdin pipe');
  assert.match(MAIN_SRC, /AURALIS_STDIN_LIFELINE: '1'/, 'the backend only watches stdin when told to');
  assert.equal(/\.stdin\.(write|end|destroy)\(/.test(MAIN_SRC), false,
    'writing to or closing the lifeline would stop or hang the backend');
});
