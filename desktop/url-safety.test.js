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
