'use strict';

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
const APP_ORIGIN = 'http://localhost:8765';
const DEV_ORIGIN = 'http://localhost:3000';

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
 * `file:` is permitted because the offline error page is loaded via
 * `loadFile(error.html)`. That is main-process-initiated and so does not emit
 * `will-navigate` today, but allowing it keeps the predicate honest about the
 * set of documents this window legitimately displays.
 */
function isAllowedAppNavigation(url, { isDevelopment = false } = {}) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  if (parsed.protocol === 'file:') return true;
  if (parsed.origin === APP_ORIGIN) return true;
  return isDevelopment && parsed.origin === DEV_ORIGIN;
}

module.exports = {
  isSafeExternalUrl,
  ALLOWED_EXTERNAL_SCHEMES,
  isAllowedAppNavigation,
  APP_ORIGIN,
  DEV_ORIGIN,
};
