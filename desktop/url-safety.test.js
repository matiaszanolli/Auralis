'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { isSafeExternalUrl } = require('./url-safety');

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
  assert.equal(isAllowedAppNavigation('http://localhost:8765'), true);
  assert.equal(isAllowedAppNavigation('http://localhost:8765/library'), true);
});

test('allows the Vite dev origin only in development', () => {
  assert.equal(isAllowedAppNavigation('http://localhost:3000', { isDevelopment: true }), true);
  assert.equal(isAllowedAppNavigation('http://localhost:3000', { isDevelopment: false }), false);
  // Default is production-safe.
  assert.equal(isAllowedAppNavigation('http://localhost:3000'), false);
});

test('rejects arbitrary remote origins', () => {
  assert.equal(isAllowedAppNavigation('https://evil.example.com'), false);
  assert.equal(isAllowedAppNavigation('http://evil.example.com'), false);
  // Even in development.
  assert.equal(isAllowedAppNavigation('https://evil.example.com', { isDevelopment: true }), false);
});

test('rejects other ports and hosts that merely look local', () => {
  assert.equal(isAllowedAppNavigation('http://localhost:9999'), false);
  assert.equal(isAllowedAppNavigation('http://127.0.0.1:8765'), false);
  // Host-prefix confusion: the origin must match exactly, not by prefix.
  assert.equal(isAllowedAppNavigation('http://localhost:8765.evil.com'), false);
  assert.equal(isAllowedAppNavigation('http://localhost.evil.com:8765'), false);
});

test('rejects a scheme downgrade/upgrade on the app host', () => {
  // Origin comparison includes the scheme, so https://localhost:8765 is not
  // the app origin.
  assert.equal(isAllowedAppNavigation('https://localhost:8765'), false);
});

test('rejects credential-embedding and userinfo tricks', () => {
  assert.equal(isAllowedAppNavigation('http://localhost:8765@evil.com'), false);
  assert.equal(isAllowedAppNavigation('http://user:pass@evil.com/localhost:8765'), false);
});

test('rejects javascript: and data: navigation', () => {
  assert.equal(isAllowedAppNavigation('javascript:alert(1)'), false);
  assert.equal(isAllowedAppNavigation('data:text/html,<script>alert(1)</script>'), false);
});

test('allows file: so the bundled offline error page still renders', () => {
  assert.equal(isAllowedAppNavigation('file:///opt/Auralis/error.html'), true);
});

test('rejects unparseable input', () => {
  assert.equal(isAllowedAppNavigation('not a url'), false);
  assert.equal(isAllowedAppNavigation(''), false);
  assert.equal(isAllowedAppNavigation(undefined), false);
});
