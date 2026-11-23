'use strict';

const path = require('node:path');
const { fileURLToPath } = require('node:url');

// Schemes safe to hand to the OS shell via shell.openExternal. Unchecked
// openExternal is a known Electron local-code-execution vector: custom/
// vendor URI-scheme handlers (search-ms:, ms-msdt:) can execute code or
// leak credentials, and file:// opens arbitrary local paths (#4844).
const ALLOWED_EXTERNAL_SCHEMES = new Set(['https:', 'mailto:']);

/**
 * True if `url` parses and its scheme is in ALLOWED_EXTERNAL_SCHEMES.
 */
function isSafeExternalUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return ALLOWED_EXTERNAL_SCHEMES.has(parsed.protocol);
}

// Origins the app window itself is ever allowed to sit on. Production serves
// the built React app from the backend; :3000 is the Vite dev server and is
// accepted only in development.
// The port the packaged backend serves on. backend-env.js pins AURALIS_PORT to it, so an exported
// AURALIS_PORT cannot move the backend away from the origin Electron loads and trusts (#6170).
const APP_PORT = 8765;
const APP_ORIGIN = `http://127.0.0.1:${APP_PORT}`;
const DEV_ORIGIN = 'http://127.0.0.1:3000';

// Passed to the renderer via webPreferences.additionalArguments only when
// unpackaged, so the sandboxed preload (which cannot require this module or
// see app.isPackaged) knows whether DEV_ORIGIN may receive electronAPI.
const DEV_ORIGIN_FLAG = '--auralis-allow-dev-origin';

// The one local document the window legitimately shows: the offline error
// page main.js opens with loadFile() from this same directory.
const ERROR_PAGE_PATH = path.join(__dirname, 'error.html');

function isErrorPageUrl(parsed) {
  // A host means a UNC share (file://server/...), never the bundled page.
  if (parsed.host !== '') return false;
  try {
    return path.resolve(fileURLToPath(parsed)) === ERROR_PAGE_PATH;
  } catch {
    return false;
  }
}

/**
 * True when an IPC invoke comes from the top-level document on the app origin (#6174).
 *
 * preload.js already withholds electronAPI from other origins, but a handler that never looks at
 * who is calling trusts that alone: an unexpected subframe, or a document that slipped past the
 * navigation guard, would reach the native file pickers and window controls. `senderFrame` is
 * null once its frame is gone, which fails closed. The offline error page (file:) is refused.
 */
function isTrustedIpcSender(event, { isDevelopment = false } = {}) {
  const frame = event && event.senderFrame;
  if (!frame || typeof frame.url !== 'string' || frame.parent) return false;
  try {
    const { origin } = new URL(frame.url);
    return origin === APP_ORIGIN || (isDevelopment && origin === DEV_ORIGIN);
  } catch {
    return false;
  }
}

/**
 * True if `url` is an origin the main window may navigate to in-place.
 *
 * Electron allows top-level navigation to anywhere when no `will-navigate`
 * listener is attached, and `preload.js` is bound to the BrowserWindow rather
 * than to a URL — so it re-runs on every navigation regardless of destination.
 * Without this check, any navigation away from localhost (a bare `<a href>`, a
 * meta-refresh, a `window.location =` from injected content, an open redirect
 * followed top-level) would hand `window.electronAPI` — native file/folder
 * pickers returning absolute paths, window controls — to a remote origin
 * (#4858).
 *
 * The only `file:` URL permitted is the bundled offline error page, loaded
 * via `loadFile(error.html)`. That is main-process-initiated and so does not
 * emit `will-navigate` today, but allowing it keeps the predicate honest about
 * the set of documents this window legitimately displays. Any other local
 * file is refused (#5356).
 */
function isAllowedAppNavigation(url, { isDevelopment = false } = {}) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  if (parsed.protocol === 'file:') return isErrorPageUrl(parsed);
  if (parsed.origin === APP_ORIGIN) return true;
  return isDevelopment && parsed.origin === DEV_ORIGIN;
}

// C0, DEL, C1, zero-width/directional marks, U+2028/2029 line separators and the bidi
// embedding/override/isolate controls: the set auralis/utils/logging.py _LOG_UNSAFE_CHARS escapes (#6535).
const LOG_UNSAFE = /[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069]/g;

/**
 * A value that is safe to interpolate into a log line: control characters (CR/LF, ESC, NUL, ...) are
 * escaped so a renderer- or backend-controlled URL or output cannot forge extra log entries (#6187),
 * nor break or visually reorder a line in an editor (#6535).
 */
function escapeControlChars(value) {
  return String(value).replace(LOG_UNSAFE, (c) => {
    const code = c.charCodeAt(0);
    return code <= 0xff ? `\\x${code.toString(16).padStart(2, '0')}` : `\\u${code.toString(16).padStart(4, '0')}`;
  });
}

module.exports = {
  escapeControlChars,
  isSafeExternalUrl,
  ALLOWED_EXTERNAL_SCHEMES,
  isAllowedAppNavigation,
  isTrustedIpcSender,
  APP_PORT,
  APP_ORIGIN,
  DEV_ORIGIN,
  DEV_ORIGIN_FLAG,
  ERROR_PAGE_PATH,
};
