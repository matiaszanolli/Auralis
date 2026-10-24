/**
 * Fatal-init crash screen
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Builds the static HTML shown when the async boot in `index.tsx` fails
 * before React can render. Colour values come from the design tokens
 * (importing the self-contained colors module is safe pre-render, #6234):
 * this is the one screen that bypasses the light/dark theme, so token
 * values — not inline hex — are what keep it on-brand when the palette
 * changes. Kept in its own module so it is unit-testable without booting
 * the app entry.
 */

import { colors } from '@/design-system/tokens/colors';

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** The whole-screen replacement for `document.documentElement.innerHTML`. */
export function buildFatalInitHtml(message: string, stack: string): string {
  const c = {
    bg: colors.bg.level2,
    text: colors.text.primaryFull,
    heading: colors.semantic.error,
    body: colors.text.secondary,
    detail: colors.text.metadata,
    panel: colors.bg.level3,
    border: colors.border.medium,
    accent: colors.accent.primary,
    stackText: colors.text.muted,
  };

  const escapedMessage = escapeHtml(message);
  const escapedStack = escapeHtml(stack);

  return (
    `<body style="background:${c.bg};color:${c.text};font-family:sans-serif;margin:0;padding:0;display:flex;align-items:center;justify-content:center;height:100vh">` +
    `<div style="text-align:center;max-width:700px;padding:40px">` +
    `<h1 style="color:${c.heading};margin:0 0 20px;font-size:28px">Initialization Error</h1>` +
    `<p style="color:${c.body};margin:0 0 20px;font-size:16px">Failed to initialize application</p>` +
    `<p style="color:${c.detail};margin:0 0 20px;font-size:14px;font-family:monospace">${escapedMessage}</p>` +
    `<details style="text-align:left;margin:30px 0;padding:20px;background:${c.panel};border:1px solid ${c.border};border-radius:6px">` +
    `<summary style="color:${c.accent};cursor:pointer;font-weight:bold;margin-bottom:10px">Stack Trace</summary>` +
    `<pre style="color:${c.stackText};font-size:11px;overflow-x:auto;margin:0;white-space:pre-wrap;word-break:break-word;line-height:1.4">${escapedStack}</pre>` +
    `</details></div></body>`
  );
}
