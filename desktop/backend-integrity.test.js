'use strict';

// The packaged backend is verified against its build-time digest before it is spawned (#6527).

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { DIGEST_FILE, readRecordedDigest, sha256File, verifyBackendBinary } = require('./backend-integrity');

const MAIN_SRC = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
const PACKAGE = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));

function fixture(binaryBytes, record) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auralis-integrity-'));
  const binary = path.join(dir, 'auralis-backend');
  fs.writeFileSync(binary, binaryBytes);
  const digest = path.join(dir, DIGEST_FILE);
  if (record !== undefined) fs.writeFileSync(digest, typeof record === 'string' ? record : JSON.stringify(record));
  return { binary, digest };
}

const sha = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');

test('a backend matching its recorded digest is accepted', () => {
  const { binary, digest } = fixture('backend v1', { name: 'auralis-backend', sha256: sha('backend v1') });

  assert.equal(sha256File(binary), sha('backend v1'));
  assert.doesNotThrow(() => verifyBackendBinary(binary, digest));
});

test('a replaced backend is refused', () => {
  const { binary, digest } = fixture('tampered', { name: 'auralis-backend', sha256: sha('backend v1') });

  assert.throws(() => verifyBackendBinary(binary, digest), /failed its integrity check/);
});

test('a missing or malformed integrity record is refused, never skipped', () => {
  const missing = fixture('backend v1');
  const malformed = fixture('backend v1', '{"sha256": "not-a-digest"}');

  assert.throws(() => verifyBackendBinary(missing.binary, missing.digest), /no integrity record/);
  assert.equal(readRecordedDigest(malformed.digest), null);
  assert.throws(() => verifyBackendBinary(malformed.binary, malformed.digest), /no integrity record/);
});

test('the build records the digest first and packs it with the asar-integrity fuse on', () => {
  assert.equal(PACKAGE.build.electronFuses.enableEmbeddedAsarIntegrityValidation, true);
  for (const file of ['backend-integrity.js', DIGEST_FILE]) assert.ok(PACKAGE.build.files.includes(file), file);
  for (const script of ['build', 'build:win', 'build:mac:arm64', 'build:linux', 'build:linux:flatpak', 'pack', 'dist']) {
    assert.match(PACKAGE.scripts[script], /^node scripts\/record-backend-digest\.js && electron-builder /, script);
  }
});

test('main.js verifies the binary before spawning it and has no python3 script fallback', () => {
  const verify = MAIN_SRC.indexOf('verifyBackendBinary(backendExe');
  const spawnCall = MAIN_SRC.indexOf('this.pythonProcess = spawn(');
  assert.ok(verify > 0 && verify < spawnCall, 'verification must precede the spawn');
  assert.equal(MAIN_SRC.includes("'python3'"), false);
  assert.equal(MAIN_SRC.includes('main.py'), false);
});
