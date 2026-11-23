/**
 * The packaged backend binary is checked against the SHA-256 recorded at build time before it is
 * spawned (#6527).
 *
 * The backend ships as an extraResource outside app.asar, so neither the code signature of the
 * asar nor the asar-integrity fuse covers it, and a per-user install (NSIS under %LOCALAPPDATA%,
 * an AppImage in a user directory) is writable by any process running as the user. main.js used to
 * spawn it whenever it existed. scripts/record-backend-digest.js writes its digest into
 * backend-digest.json, which is packed inside app.asar; on Windows and macOS the
 * enableEmbeddedAsarIntegrityValidation fuse makes that file tamper-evident too. Linux has no such
 * fuse, so there this is tamper evidence against a swapped binary, not against a swapped asar.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');

const DIGEST_FILE = 'backend-digest.json';

/** SHA-256 of a file, hex. */
function sha256File(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

/** The build-time record `{ name, sha256 }`, or null when it is absent or malformed. */
function readRecordedDigest(digestPath) {
  try {
    const record = JSON.parse(fs.readFileSync(digestPath, 'utf8'));
    return typeof record.sha256 === 'string' && /^[0-9a-f]{64}$/.test(record.sha256) ? record : null;
  } catch {
    return null;
  }
}

/** Throw unless `binaryPath` matches the digest recorded at `digestPath`. */
function verifyBackendBinary(binaryPath, digestPath) {
  const record = readRecordedDigest(digestPath);
  if (record === null) {
    throw new Error('The installed backend has no integrity record. Reinstall Auralis.');
  }
  if (sha256File(binaryPath) !== record.sha256) {
    throw new Error('The installed backend failed its integrity check. Reinstall Auralis.');
  }
}

module.exports = { DIGEST_FILE, sha256File, readRecordedDigest, verifyBackendBinary };
