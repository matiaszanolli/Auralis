// #6152: the lock must not resolve an Electron below the GHSA-jr5w-w6x2-84p9 fix
// (affects >=43.0.0-alpha.1 <43.8.1; we require >=43.8.3 for the Chromium/V8
// security backports in between). Raise MIN_43 when a newer advisory lands.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const MIN_43 = [43, 8, 3];

function parse(v) {
  const m = /^(\d+)\.(\d+)\.(\d+)/.exec(v);
  assert.ok(m, `unparseable electron version: ${v}`);
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function atLeast(v, min) {
  for (let i = 0; i < 3; i++) {
    if (v[i] !== min[i]) return v[i] > min[i];
  }
  return true;
}

test('desktop/pnpm-lock.yaml resolves an Electron past the advisory fix', () => {
  const lock = fs.readFileSync(path.join(__dirname, 'pnpm-lock.yaml'), 'utf8');
  const versions = [...lock.matchAll(/^ {2}electron@(\d[^:\s]*):/gm)].map((m) => m[1]);
  assert.ok(versions.length > 0, 'no electron entry found in pnpm-lock.yaml');
  for (const version of new Set(versions)) {
    const parsed = parse(version);
    // A newer major is fine; within 43.x it must be >= MIN_43.
    assert.ok(
      parsed[0] > MIN_43[0] || (parsed[0] === MIN_43[0] && atLeast(parsed, MIN_43)),
      `electron@${version} is below ${MIN_43.join('.')} (GHSA-jr5w-w6x2-84p9)`,
    );
  }
});

test('package.json range cannot resolve below the minimum either', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
  const range = pkg.devDependencies.electron;
  const floor = parse(range.replace(/^[\^~>=\s]+/, ''));
  assert.ok(
    floor[0] > MIN_43[0] || (floor[0] === MIN_43[0] && atLeast(floor, MIN_43)),
    `package.json allows electron ${range}, below ${MIN_43.join('.')}`,
  );
});
