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

module.exports = { isSafeExternalUrl, ALLOWED_EXTERNAL_SCHEMES };
