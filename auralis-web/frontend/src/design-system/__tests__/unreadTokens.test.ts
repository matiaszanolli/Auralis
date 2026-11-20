/**
 * No unread design token (#6443)
 *
 * #6062 deleted the unread token *groups*; about 65 unread *leaves* remained, so the "single
 * source of truth" still carried a dead surface that read as supported API, could drift from the
 * live values, and invited hard-coded copies elsewhere. Every leaf of `tokens` now has a reader
 * outside `design-system/tokens/`, or an entry in UNREAD_ALLOWLIST saying why it stays.
 *
 * A leaf counts as read when source text outside `design-system/tokens/` either
 *  - spells its path under `tokens` (`tokens.colors.text.tertiary`, `tokens.fontSize['5xl']`), or
 *  - spells its last two segments (`text.tertiary`, `fontSize['5xl']`), which is how aliases
 *    (`const { text } = tokens.colors`) and per-category helpers reach a token.
 * Reading a whole group (`const { text } = tokens.colors`, `Object.values(tokens.spacing)`,
 * `keyof typeof tokens.colors`) deliberately does NOT read every leaf below it: those are
 * aliases, iterations and type positions, and counting them would blind the scan. A real
 * whole-object consumer goes in UNREAD_ALLOWLIST with a reason.
 * Tests count as readers: a value pinned by a test is deliberate, not dead.
 */
import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';

/** Leaf paths (`colors.text.primary`) of a nested plain object. */
export function leafPaths(node: unknown, prefix: string[] = []): string[][] {
  if (node && typeof node === 'object' && !Array.isArray(node)) {
    return Object.entries(node).flatMap(([key, value]) => leafPaths(value, [...prefix, key]));
  }
  return [prefix];
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const stripComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

/** Every `tokens.a.b['c']` chain in `source`, as its segment list (`['a', 'b', 'c']`). */
function tokenChains(source: string): string[][] {
  const chains: string[][] = [];
  for (const match of source.matchAll(/\btokens((?:\??\.[A-Za-z_$][\w$]*|\[\s*['"`][^'"`]+['"`]\s*\])+)/g)) {
    chains.push([...match[1].matchAll(/\??\.([A-Za-z_$][\w$]*)|\[\s*['"`]([^'"`]+)['"`]\s*\]/g)].map((m) => m[1] ?? m[2]));
  }
  return chains;
}

/** The leaves of `tree` that no text in `sources` reads (see the file header for what "reads" means). */
export function findUnreadLeaves(tree: unknown, sources: readonly string[]): string[] {
  const chains = sources.flatMap((s) => tokenChains(s));
  const spells = (chain: string[], leaf: string[]) =>
    leaf.length <= chain.length && leaf.every((segment, i) => segment === chain[i]);

  return leafPaths(tree)
    .filter((leaf) => {
      if (chains.some((chain) => spells(chain, leaf))) return false;
      if (leaf.length < 2) return true;
      const [parent, name] = leaf.slice(-2).map(escape);
      const aliased = new RegExp(`\\b${parent}\\??\\.${name}\\b|\\b${parent}\\??\\[\\s*['"\`]${name}['"\`]\\s*\\]`);
      return !sources.some((s) => aliased.test(s));
    })
    .map((leaf) => leaf.join('.'));
}

/** Source text outside design-system/tokens/, comments stripped, this file excluded. */
function readerSources(): string[] {
  const modules = import.meta.glob('/src/**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;
  return Object.entries(modules)
    .filter(([path]) => !path.includes('/design-system/tokens/') && !path.endsWith('/unreadTokens.test.ts'))
    .map(([, source]) => stripComments(source));
}

/** Leaves kept although nothing reads them, with why. Empty on purpose: delete, don't allowlist. */
const UNREAD_ALLOWLIST: Record<string, string> = {};

describe('findUnreadLeaves', () => {
  const tree = { colors: { text: { used: '#fff', dead: '#000' } }, zIndex: { modal: 1, base: 0 } };

  it('flags a leaf nothing reads, and not one read by path or alias; a whole-group read reads none', () => {
    expect(findUnreadLeaves(tree, ['const a = tokens.colors.text.used;'])).toEqual(['colors.text.dead', 'zIndex.modal', 'zIndex.base']);
    expect(findUnreadLeaves(tree, ['const { text } = tokens.colors; text.dead; text.used'])).toEqual(['zIndex.modal', 'zIndex.base']);
    expect(findUnreadLeaves(tree, ['Object.values(tokens.zIndex); tokens.colors.text'])).toEqual(['colors.text.used', 'colors.text.dead', 'zIndex.modal', 'zIndex.base']);
    expect(findUnreadLeaves(tree, ["tokens.zIndex['modal']"])).toEqual(['colors.text.used', 'colors.text.dead', 'zIndex.base']);
  });
});

describe('design tokens are all read (#6443)', () => {
  const unread = findUnreadLeaves(tokens, readerSources());

  it('every leaf has a reader outside design-system/tokens/, or is allowlisted with a reason', () => {
    const offenders = unread.filter((leaf) => !(leaf in UNREAD_ALLOWLIST));
    expect(offenders, `unread tokens - delete them, or allowlist with a reason:\n${offenders.join('\n')}`).toEqual([]);
  });

  it('the allowlist holds no entry that is read or no longer exists', () => {
    const real = new Set(leafPaths(tokens).map((leaf) => leaf.join('.')));
    const stale = Object.keys(UNREAD_ALLOWLIST).filter((leaf) => !real.has(leaf) || !unread.includes(leaf));
    expect(stale).toEqual([]);
  });
});
