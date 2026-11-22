// Self-test for the weak-test gate (#5682): run with `node --test scripts/check-weak-tests.test.mjs`.
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { scan } from './check-weak-tests.mjs';

function scanSpec(body) {
  const dir = mkdtempSync(join(tmpdir(), 'weak-tests-'));
  writeFileSync(join(dir, 'a.test.ts'), body);
  return scan(dir, dir);
}

test('flags a test with no assertion', () => {
  const found = scanSpec(`it('does nothing', () => { render(); });`);
  assert.deepEqual(found.zero, ['a.test.ts::does nothing']);
  assert.deepEqual(found.weak, []);
});

test('flags a test whose only assertions are presence checks', () => {
  const found = scanSpec(`
    it('presence only', () => {
      expect(x).toBeDefined();
      expect(y).not.toBeNull();
      expect(z).toBeTruthy();
    });`);
  assert.deepEqual(found.weak, ['a.test.ts::presence only']);
  assert.deepEqual(found.zero, []);
});

test('a presence check next to a specific assertion is fine', () => {
  const found = scanSpec(`
    it('mixed', () => {
      expect(x).toBeDefined();
      expect(x.id).toBe(3);
    });`);
  assert.deepEqual(found, { zero: [], weak: [], conditional: [] });
});

test('helpers, expect.* and type-level specs count as assertions', () => {
  const found = scanSpec(`
    it('helper', () => { assertQueued(store); });
    it('async', async () => { await expect.poll(() => v).toBe(1); });
    it('types', () => {
      // @ts-expect-error -- must not compile
      post('/x', 'raw');
    });`);
  assert.deepEqual(found, { zero: [], weak: [], conditional: [] });
});

test('flags an assertion that only runs when an if without an else holds (#6659)', () => {
  const found = scanSpec(`
    it('guarded', () => {
      const el = screen.queryByRole('img');
      if (el) {
        expect(el).toHaveAttribute('src', 'x');
      }
    });`);
  assert.deepEqual(found.conditional, ['a.test.ts::guarded']);
});

test('an if with an else, a guard in a nested callback, or an unconditional expect is fine', () => {
  const found = scanSpec(`
    it('both branches', () => {
      if (a) { expect(a).toBe(1); } else { expect(b).toBe(2); }
    });
    it('inside a callback', async () => {
      await waitFor(() => { expect(x).toBe(1); });
    });
    it('plain', () => {
      expect(screen.getByRole('img')).toHaveAttribute('src', 'x');
    });`);
  assert.deepEqual(found, { zero: [], weak: [], conditional: [] });
});
