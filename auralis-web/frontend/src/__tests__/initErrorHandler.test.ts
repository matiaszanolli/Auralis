/**
 * Tests for init error handler HTML escaping (issue #2162)
 *
 * main.tsx and index.tsx write error details to document.documentElement.innerHTML.
 * Prior to the fix, the error message (msg) was inserted raw, allowing HTML/script
 * injection if the Error.message itself contained tags.
 *
 * Fix: msg is now escaped with the same four-substitution chain already applied to
 * the stack trace:
 *   msg.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
 */

import { describe, it, expect } from 'vitest';

// ---------------------------------------------------------------------------
// Pure helper — mirrors the escapedMsg expression in main.tsx / index.tsx
// ---------------------------------------------------------------------------

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Unit tests: escaping correctness
// ---------------------------------------------------------------------------

describe('initErrorHandler HTML escaping (issue #2162)', () => {
  describe('escapeHtml — character substitution', () => {
    it('escapes < and > to prevent tag injection', () => {
      const payload = '<script>alert("xss")</script>';
      const escaped = escapeHtml(payload);
      expect(escaped).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
      expect(escaped).not.toContain('<');
      expect(escaped).not.toContain('>');
    });

    it('escapes & before < and > so entities are not double-encoded', () => {
      // "&lt;" in the input must become "&amp;lt;", not "&lt;"
      const payload = '&lt;already-escaped&gt;';
      const escaped = escapeHtml(payload);
      expect(escaped).toBe('&amp;lt;already-escaped&amp;gt;');
    });

    it('escapes & to prevent entity injection', () => {
      expect(escapeHtml('A & B')).toBe('A &amp; B');
    });

    it('escapes " to prevent attribute-value break-out', () => {
      expect(escapeHtml('"double"')).toBe('&quot;double&quot;');
    });

    it('escapes all special characters in a mixed payload', () => {
      const payload = '<img src="x" onerror="alert(1)">';
      const escaped = escapeHtml(payload);
      expect(escaped).not.toContain('<');
      expect(escaped).not.toContain('>');
      expect(escaped).not.toContain('"');
      // All four entities present
      expect(escaped).toContain('&lt;');
      expect(escaped).toContain('&gt;');
      expect(escaped).toContain('&quot;');
    });

    it('leaves plain text unchanged', () => {
      const plain = 'Failed to load module: network error';
      expect(escapeHtml(plain)).toBe(plain);
    });

    it('handles empty string', () => {
      expect(escapeHtml('')).toBe('');
    });
  });

  // ---------------------------------------------------------------------------
  // DOM safety: escaped msg must not create executable or injected elements
  // ---------------------------------------------------------------------------

  describe('DOM safety: escaped msg does not create injected elements', () => {
    it('XSS payload in msg does not create a script element after escaping', () => {
      const xssMsg = '<script>window.__xss = true;</script>';
      const escapedMsg = escapeHtml(xssMsg);
      const div = document.createElement('div');
      div.innerHTML = '<p>' + escapedMsg + '</p>';
      // No <script> should have been parsed
      expect(div.querySelector('script')).toBeNull();
      // Text content must equal the raw payload string (displayed, not executed)
      expect(div.querySelector('p')?.textContent).toBe(xssMsg);
    });

    it('img onerror payload does not create an img element after escaping', () => {
      const xssMsg = '<img src=x onerror="window.__xss=true">';
      const escapedMsg = escapeHtml(xssMsg);
      const div = document.createElement('div');
      div.innerHTML = '<p>' + escapedMsg + '</p>';
      expect(div.querySelector('img')).toBeNull();
    });

    it('anchor href payload does not create an anchor element after escaping', () => {
      const xssMsg = '<a href="javascript:alert(1)">click me</a>';
      const escapedMsg = escapeHtml(xssMsg);
      const div = document.createElement('div');
      div.innerHTML = '<p>' + escapedMsg + '</p>';
      expect(div.querySelector('a')).toBeNull();
    });

    it('escaped output renders as visible text, preserving the error message', () => {
      const msg = 'Cannot read property "foo" of undefined';
      const escapedMsg = escapeHtml(msg);
      const div = document.createElement('div');
      div.innerHTML = '<p>' + escapedMsg + '</p>';
      // The text content matches the original (no data loss for safe messages)
      expect(div.querySelector('p')?.textContent).toBe(msg);
    });
  });

  // ---------------------------------------------------------------------------
  // Regression: demonstrates the pre-fix vulnerability (documents the bug)
  // ---------------------------------------------------------------------------

  describe('regression: unescaped msg creates injected DOM elements (pre-fix behaviour)', () => {
    it('raw <b> tag in msg IS parsed by innerHTML — proving the original bug', () => {
      // This test documents why escaping msg is required.
      // Inserting raw msg into innerHTML allows arbitrary tag injection.
      const xssMsg = '<b>bold injection</b>';
      const div = document.createElement('div');
      div.innerHTML = '<p>' + xssMsg + '</p>';   // raw, unescaped (old behaviour)
      // A <b> element is created — the tag was interpreted, not displayed
      expect(div.querySelector('b')).not.toBeNull();
      expect(div.querySelector('b')?.textContent).toBe('bold injection');
    });

    it('escaped <b> tag in msg is NOT parsed — confirming the fix', () => {
      const xssMsg = '<b>bold injection</b>';
      const escapedMsg = escapeHtml(xssMsg);
      const div = document.createElement('div');
      div.innerHTML = '<p>' + escapedMsg + '</p>';   // escaped (new behaviour)
      expect(div.querySelector('b')).toBeNull();
    });
  });
});
