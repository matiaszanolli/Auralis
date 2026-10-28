/**
 * SegmentedControl restores a keyboard focus ring (#6030).
 *
 * SegmentButton resets `outline: none` in its own emotion class, which beats the
 * global :focus-visible rule (equal specificity, later insertion), so keyboard
 * focus was invisible. The component now declares its own :focus-visible rule.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { SegmentedControl } from '../SegmentedControl';

function injectedCss(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((el) => el.textContent ?? '')
    .join('\n');
}

describe('SegmentedControl keyboard focus', () => {
  it('declares a solid accent :focus-visible outline on its segment buttons', () => {
    render(
      <SegmentedControl
        value="a"
        onChange={() => {}}
        options={[{ value: 'a', label: 'Albums' }, { value: 'b', label: 'Artists' }]}
      />
    );
    const button = screen.getByText('Albums').closest('button');
    expect(button).not.toBeNull();

    const className = button!.className.split(/\s+/).find((c) => c.startsWith('css-'));
    expect(className).toBeTruthy();
    const css = injectedCss();
    const rule = new RegExp(`\\.${className}:focus-visible\\{([^}]*)\\}`).exec(css);

    expect(rule, 'no :focus-visible rule was emitted for the segment button').not.toBeNull();
    expect(rule![1]).toMatch(/outline:2px solid var\(--app-accent\)/);
  });
});
