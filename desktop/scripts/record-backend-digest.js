#!/usr/bin/env node
/**
 * Record the SHA-256 of the bundled backend binary into backend-digest.json before electron-builder
 * packs it into app.asar (#6527). Every desktop build script runs this first; a build without a
 * backend binary fails here rather than shipping an app that cannot verify what it launches.
 */
const fs = require('node:fs');
const path = require('node:path');
const { DIGEST_FILE, sha256File } = require('../backend-integrity');

const desktopDir = path.join(__dirname, '..');
const backendDir = path.join(desktopDir, 'resources', 'backend');
const candidates = ['auralis-backend.exe', 'auralis-backend'];
const name = candidates.find((candidate) => fs.existsSync(path.join(backendDir, candidate)));

if (!name) {
  console.error(`record-backend-digest: no backend binary in ${backendDir}; build it with PyInstaller first.`);
  process.exit(1);
}

const sha256 = sha256File(path.join(backendDir, name));
fs.writeFileSync(path.join(desktopDir, DIGEST_FILE), `${JSON.stringify({ name, sha256 }, null, 2)}\n`);
console.log(`record-backend-digest: ${name} sha256 ${sha256}`);
