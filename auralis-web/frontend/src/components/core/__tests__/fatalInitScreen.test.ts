/**
 * Fatal-init crash screen (#6234)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The one screen that bypasses the light/dark theme must still track the
 * design tokens: pin that every colour in the built markup is a token value
 * and that no raw hex literal (least of all the retired #667eea brand
 * colour) leaks back in. Also pins the HTML escaping of message/stack.
 */

import { describe, expect, it } from 'vitest';

import { colors } from '@/design-system/tokens/colors';
import { buildFatalInitHtml } from '../fatalInitScreen';

describe('buildFatalInitHtml (#6234)', () => {
  const html = buildFatalInitHtml('boom <script>', 'at x (<y>)');

  it('uses token colour values, not inline hex literals', () => {
    expect(html).toContain(`background:${colors.bg.level2}`);
    expect(html).toContain(`color:${colors.semantic.error}`);
    expect(html).toContain(`background:${colors.bg.level3}`);
    expect(html).toContain(`color:${colors.accent.primary}`);
    expect(html).toContain(colors.text.secondary);
    expect(html).toContain(colors.text.metadata);
    expect(html).toContain(colors.text.muted);
  });

  it('carries the retired #667eea brand colour nowhere', () => {
    // Token values are hex themselves once interpolated; the contract is
    // that every colour in the markup ARRIVED via the tokens object.
    expect(html).not.toContain('#667eea');
    expect(html).not.toContain('#764ba2');
  });

  it('escapes message and stack before embedding', () => {
    expect(html).not.toContain('<script>');
    expect(html).toContain('boom &lt;script&gt;');
    expect(html).toContain('&lt;y&gt;');
  });
});
