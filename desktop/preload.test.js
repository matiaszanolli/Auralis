'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// preload.js requires `window` and the real electron API at module scope, so
// it can't be require()d outside a BrowserWindow. These checks read both
// files as text instead of executing them (#4851).
const PRELOAD_SRC = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');
const MAIN_SRC = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

function invokedChannels(src) {
  const re = /ipcRenderer\.invoke\(\s*'([^']+)'/g;
  const channels = new Set();
  let m;
  while ((m = re.exec(src))) channels.add(m[1]);
  return channels;
}

function handledChannels(src) {
  const re = /ipcMain\.handle\(\s*'([^']+)'/g;
  const channels = new Set();
  let m;
  while ((m = re.exec(src))) channels.add(m[1]);
  return channels;
}

// #4851: preload.js exposed sendToBackend/openExternal invoking
// 'backend-message'/'open-external', neither of which main.js ever handled --
// a no-op today, but a landmine for whoever wires one up later without
// noticing the missing validation main.js's real openExternalSafely()
// provides. Removed rather than implemented (zero renderer consumers of
// either method). This pins the invariant so a future preload addition can't
// silently reopen the same gap.
test('every channel preload.js invokes has a matching ipcMain.handle in main.js', () => {
  const invoked = invokedChannels(PRELOAD_SRC);
  const handled = handledChannels(MAIN_SRC);

  assert.ok(invoked.size > 0, 'sanity check: preload.js should invoke at least one channel');

  const missing = [...invoked].filter((channel) => !handled.has(channel));
  assert.deepEqual(
    missing,
    [],
    `preload.js exposes a channel with no ipcMain.handle: ${missing.join(', ')}`
  );
});

test('the two dead channels do not reappear', () => {
  assert.equal(PRELOAD_SRC.includes('sendToBackend'), false);
  assert.equal(PRELOAD_SRC.includes('backend-message'), false);
  assert.equal(PRELOAD_SRC.includes('openExternal'), false);
  assert.equal(PRELOAD_SRC.includes("'open-external'"), false);
});

// --------------------------------------------------------------------------
// Origin backstop (#4858, #5356). preload.js runs top-level script against a
// stubbed `electron`, `window` and sandboxed `process`, so it can execute in a
// vm context here even though it cannot be require()d.
// --------------------------------------------------------------------------

const vm = require('node:vm');
const { pathToFileURL } = require('node:url');
const { APP_ORIGIN, DEV_ORIGIN, DEV_ORIGIN_FLAG, ERROR_PAGE_PATH } = require('./url-safety');

function exposesApi(pageUrl, argv = []) {
  const exposed = {};
  vm.runInNewContext(PRELOAD_SRC, {
    require: (name) => {
      assert.equal(name, 'electron', 'a sandboxed preload can only require electron');
      return {
        contextBridge: { exposeInMainWorld: (key, api) => { exposed[key] = api; } },
        ipcRenderer: {},
      };
    },
    window: { location: new URL(pageUrl) },
    process: { argv, platform: 'linux', env: {}, versions: { node: 'test', electron: 'test' } },
    console: { log() {}, warn() {} },
  });
  return 'electronAPI' in exposed;
}

test('exposes electronAPI on the app origin', () => {
  // Uses url-safety.js's constant, so the preload's copy cannot drift from it.
  assert.equal(exposesApi(`${APP_ORIGIN}/library`), true);
});

test('withholds electronAPI from another localhost port', () => {
  assert.equal(exposesApi('http://localhost:9999/'), false);
  assert.equal(exposesApi('https://localhost:8765/'), false);
});

test('exposes electronAPI on the dev origin only when main.js passes the flag', () => {
  assert.equal(exposesApi(`${DEV_ORIGIN}/`), false);
  assert.equal(exposesApi(`${DEV_ORIGIN}/`, [DEV_ORIGIN_FLAG]), true);
  // The flag never widens anything beyond the dev origin.
  assert.equal(exposesApi('http://localhost:9999/', [DEV_ORIGIN_FLAG]), false);
});

test('withholds electronAPI from the offline error page and remote origins', () => {
  assert.equal(exposesApi(pathToFileURL(ERROR_PAGE_PATH).href), false);
  assert.equal(exposesApi('https://evil.example.com/'), false);
});

test('main.js passes the dev-origin flag to the renderer', () => {
  assert.match(MAIN_SRC, /additionalArguments:\s*this\.isDevelopment \? \[DEV_ORIGIN_FLAG\] : \[\]/);
});
