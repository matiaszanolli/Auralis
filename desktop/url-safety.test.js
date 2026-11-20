'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { isSafeExternalUrl, escapeControlChars } = require('./url-safety');

test('allows https URLs', () => {
  assert.equal(isSafeExternalUrl('https://example.com'), true);
});

test('allows mailto URLs', () => {
  assert.equal(isSafeExternalUrl('mailto:someone@example.com'), true);
});

test('rejects file URLs', () => {
  assert.equal(isSafeExternalUrl('file:///etc/passwd'), false);
});

test('rejects custom/vendor URI schemes', () => {
  assert.equal(isSafeExternalUrl('search-ms:query=malware'), false);
  assert.equal(isSafeExternalUrl('ms-msdt:/id IT_BrowseForFile'), false);
});

test('rejects plain http (downgrade)', () => {
  assert.equal(isSafeExternalUrl('http://example.com'), false);
});

test('rejects unparseable input', () => {
  assert.equal(isSafeExternalUrl('not a url'), false);
  assert.equal(isSafeExternalUrl(''), false);
});

// --------------------------------------------------------------------------
// isAllowedAppNavigation (#4858) — in-window top-level navigation allowlist.
// --------------------------------------------------------------------------

const { isAllowedAppNavigation } = require('./url-safety');

test('allows the production app origin', () => {
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:8765'), true);
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:8765/library'), true);
});

test('allows the Vite dev origin only in development', () => {
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:3000', { isDevelopment: true }), true);
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:3000', { isDevelopment: false }), false);
  // Default is production-safe.
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:3000'), false);
});

test('rejects arbitrary remote origins', () => {
  assert.equal(isAllowedAppNavigation('https://evil.example.com'), false);
  assert.equal(isAllowedAppNavigation('http://evil.example.com'), false);
  // Even in development.
  assert.equal(isAllowedAppNavigation('https://evil.example.com', { isDevelopment: true }), false);
});

test('rejects other ports and hosts that merely look local', () => {
  assert.equal(isAllowedAppNavigation('http://localhost:9999'), false);
  assert.equal(isAllowedAppNavigation('http://localhost:8765'), false);
  assert.equal(isAllowedAppNavigation('http://[::1]:8765'), false);
  // Host-prefix confusion: the origin must match exactly, not by prefix.
  assert.equal(isAllowedAppNavigation('http://127.0.0.1.evil.com:8765'), false);
  assert.equal(isAllowedAppNavigation('http://localhost.evil.com:8765'), false);
});

test('rejects a scheme downgrade/upgrade on the app host', () => {
  // Origin comparison includes the scheme, so https://localhost:8765 is not
  // the app origin.
  assert.equal(isAllowedAppNavigation('https://localhost:8765'), false);
});

test('rejects credential-embedding and userinfo tricks', () => {
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:8765@evil.com'), false);
  assert.equal(isAllowedAppNavigation('http://user:pass@evil.com/localhost:8765'), false);
});

test('rejects javascript: and data: navigation', () => {
  assert.equal(isAllowedAppNavigation('javascript:alert(1)'), false);
  assert.equal(isAllowedAppNavigation('data:text/html,<script>alert(1)</script>'), false);
});

const { pathToFileURL } = require('node:url');
const nodePath = require('node:path');
const { ERROR_PAGE_PATH } = require('./url-safety');

test('allows the bundled offline error page', () => {
  assert.equal(isAllowedAppNavigation(pathToFileURL(ERROR_PAGE_PATH).href), true);
});

test('rejects every other file: URL (#5356)', () => {
  assert.equal(isAllowedAppNavigation('file:///etc/passwd'), false);
  // Same file name, different directory.
  assert.equal(isAllowedAppNavigation('file:///opt/Auralis/error.html'), false);
  assert.equal(
    isAllowedAppNavigation(pathToFileURL(nodePath.join(nodePath.dirname(ERROR_PAGE_PATH), 'main.js')).href),
    false
  );
  // Traversal that resolves somewhere else.
  assert.equal(
    isAllowedAppNavigation(pathToFileURL(ERROR_PAGE_PATH).href.replace('/error.html', '/../error.html')),
    false
  );
});

test('rejects unparseable input', () => {
  assert.equal(isAllowedAppNavigation('not a url'), false);
  assert.equal(isAllowedAppNavigation(''), false);
  assert.equal(isAllowedAppNavigation(undefined), false);
});

test('escapeControlChars neutralises CR/LF, ESC and NUL so a URL cannot forge log lines (#6187)', () => {
  const hostile = 'https://x.test/\r\n[INFO] forged\u001b[31m\u0000';

  const escaped = escapeControlChars(hostile);

  assert.equal(/[\u0000-\u001f\u007f]/.test(escaped), false);
  assert.match(escaped, /\\x0d\\x0a\[INFO\] forged\\x1b\[31m\\x00/);
});

test('escapeControlChars leaves ordinary text and non-strings alone', () => {
  assert.equal(escapeControlChars('https://example.com/a?b=c'), 'https://example.com/a?b=c');
  assert.equal(escapeControlChars(undefined), 'undefined');
});

// #6174: IPC handlers check who is calling, not just which channel.
const { isTrustedIpcSender } = require('./url-safety');
const frame = (url, parent = null) => ({ senderFrame: { url, parent } });

test('isTrustedIpcSender accepts the top-level app document only', () => {
  assert.equal(isTrustedIpcSender(frame('http://127.0.0.1:8765/library')), true);
  assert.equal(isTrustedIpcSender(frame('http://127.0.0.1:8765/', {})), false, 'a subframe, even on the app origin');
  assert.equal(isTrustedIpcSender(frame('http://localhost:9999/')), false);
  assert.equal(isTrustedIpcSender(frame('https://evil.example/')), false);
  assert.equal(isTrustedIpcSender(frame('http://127.0.0.1:8765@evil.com/')), false);
});

test('isTrustedIpcSender fails closed on a missing or malformed sender', () => {
  assert.equal(isTrustedIpcSender({ senderFrame: null }), false, 'frame already destroyed');
  assert.equal(isTrustedIpcSender({}), false);
  assert.equal(isTrustedIpcSender(undefined), false);
  assert.equal(isTrustedIpcSender(frame('not a url')), false);
  assert.equal(isTrustedIpcSender(frame(`file://${require('node:path').join(__dirname, 'error.html')}`)), false);
});

test('isTrustedIpcSender admits the Vite dev origin only in development', () => {
  assert.equal(isTrustedIpcSender(frame('http://127.0.0.1:3000/'), { isDevelopment: true }), true);
  assert.equal(isTrustedIpcSender(frame('http://127.0.0.1:3000/')), false);
});
