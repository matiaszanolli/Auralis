/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Each category is merged in the barrel; the
 * glass backgrounds read the surface colour from the colors category instead of re-spelling its
 * channels (#6646).
 */

import { colors } from './colors';
import { withOpacity } from './with-opacity';


  /**
   * Gradient System (Soft Violet + Electric Aqua + subtle dark + glass overlays)
   */
export const gradients = {
    // Brand gradients (solid)
    aurora: 'linear-gradient(135deg, #6F62EC 0%, #5A5CC4 100%)',              // Aurora (Soft Violet → darker); light stop 4.53:1 with white label (#5675)
    darkSubtle: 'linear-gradient(180deg, #1B232E 0%, #131A24 100%)',          // Dark subtle (background transitions)

    // Glass gradients (translucent overlays)
    glassShimmer: 'linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 50%, rgba(255, 255, 255, 0.08) 100%)', // Glass shimmer
    shimmerSweep: 'linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.08) 50%, transparent 100%)', // Card hover shimmer sweep (#4199) — single source for track/album cards

    // Decorative gradients (for album art placeholders, mood visualization)
    // Style Guide §1.4: Gradients must feel alive, not graphic-design perfect
    decorative: {
      electricPurple: 'linear-gradient(135deg, #c44569 0%, #7366F0 100%)',
      gradientPink: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      gradientBlue: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      gradientGreen: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      gradientSunset: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      gradientTeal: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
      gradientPastel: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
      gradientRose: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
    },

} as const;

  /**
   * Glass Surface Presets (Glassmorphism)
   * Ready-to-use glass surface styles for common components
   */
  /**
   * Glass Surface Presets (Design Language §4.1)
   * Continuous surfaces, not boxed cards.
   * Subtle glass borders catch light - depth via borders, spacing, and shadow.
   */
export const glass = {
    // Starfield glass backgrounds (#3950 / DS-5): a SINGLE blue-black base
    // (colors.bg.level2 — the dominant shell tint) at the opacity steps the app shell
    // uses, so glass surfaces (top bar, sidebar, player, container, cards,
    // artist rows) stay consistent and can be retuned from one place. Replaces
    // five hand-picked blue-black tuples that were scattered across components.
    starfield: {
      medium: withOpacity(colors.bg.level2, '0.50'),
      strong: withOpacity(colors.bg.level2, '0.55'),
      sharp: withOpacity(colors.bg.level2, '0.70'),
    },

    // Subtle glass (calm overlays - for idle states)
    // Bevel: top light catch, bottom shadow for 3D glass effect
    subtle: {
      background: withOpacity(colors.bg.level2, '0.25'),
      backdropFilter: 'blur(6px) saturate(1.05)',
      border: 'none',
      // Bevel: outer shadow + top highlight + bottom shadow
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.15)',
    },

    // Medium glass (panels, surfaces)
    medium: {
      // #5641: 0.9 (was 0.6) — this fill carries muted text over arbitrary
      // artwork in light mode and needs >= 4.5:1 against it.
      // (#5646: the dark-mode twin `backgroundDark` is gone with the unused
      // glassEffects helper it existed for.)
      backgroundLight: 'rgba(255, 255, 255, 0.9)',
      backdropFilter: 'blur(8px) saturate(1.08)',
    },

    // Strong glass (modals, prominent surfaces, player bar)
    strong: {
      background: withOpacity(colors.bg.level2, '0.55'),
      // #5641: 0.94 (was 0.85) — keeps secondary text >= 4.5:1 through the
      // dialog scrim in light mode.
      // (#5646: the dark-mode twin `backgroundDark` is gone with the unused
      // glassEffects helper it existed for.)
      backgroundLight: 'rgba(255, 255, 255, 0.94)',
      backdropFilter: 'blur(12px) saturate(1.1)',
      border: 'none',
      // Bevel: outer shadow + top highlight + bottom shadow
      boxShadow: '0 16px 48px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.15), inset 0 -1px 0 rgba(0, 0, 0, 0.20)',
    },

} as const;

/**
 * The energy meter's cool (calm) to warm (aggressive) ramp at a given alpha (#6646). A function, not
 * a string in ``gradients``, because the meter drives the alpha from the live intensity.
 */
export function energyGradient(alpha: number): string {
  return `linear-gradient(to right,
            hsla(210, 80%, 60%, ${alpha}) 0%,
            hsla(45, 90%, 55%, ${alpha}) 50%,
            hsla(15, 95%, 55%, ${alpha}) 100%)`;
}
