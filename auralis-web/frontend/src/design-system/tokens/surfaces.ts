/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


  /**
   * Gradient System (Soft Violet + Electric Aqua + subtle dark + glass overlays)
   */
export const gradients = {
    // Brand gradients (solid)
    aurora: 'linear-gradient(135deg, #7366F0 0%, #5A5CC4 100%)',              // Aurora (Soft Violet → darker)
    auroraSoft: 'linear-gradient(135deg, rgba(115, 102, 240, 0.80) 0%, rgba(90, 92, 196, 0.80) 100%)', // Aurora soft (overlays)
    auroraVertical: 'linear-gradient(180deg, #7366F0 0%, #5A5CC4 100%)',      // Aurora vertical (headers)
    aqua: 'linear-gradient(135deg, #47D6FF 0%, #00BCC4 100%)',                // Aqua (audio-reactive)
    darkSubtle: 'linear-gradient(180deg, #1B232E 0%, #131A24 100%)',          // Dark subtle (background transitions)

    // Glass gradients (translucent overlays)
    glassViolet: 'linear-gradient(135deg, rgba(115, 102, 240, 0.08) 0%, rgba(90, 92, 196, 0.12) 100%)',   // Glass violet tint
    glassAqua: 'linear-gradient(135deg, rgba(71, 214, 255, 0.06) 0%, rgba(0, 188, 196, 0.10) 100%)',     // Glass aqua tint
    glassShimmer: 'linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 50%, rgba(255, 255, 255, 0.08) 100%)', // Glass shimmer
    shimmerSweep: 'linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.08) 50%, transparent 100%)', // Card hover shimmer sweep (#4199) — single source for track/album cards

    // Mesh gradients (multi-color glass)
    glassMesh: 'radial-gradient(at 0% 0%, rgba(115, 102, 240, 0.15) 0%, transparent 50%), radial-gradient(at 100% 100%, rgba(71, 214, 255, 0.12) 0%, transparent 50%)',

    // Border gradients (for glass edges)
    borderGlow: 'linear-gradient(135deg, rgba(115, 102, 240, 0.4) 0%, rgba(71, 214, 255, 0.3) 100%)',
    borderSubtle: 'linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.12) 100%)',

    // Decorative gradients (for album art placeholders, mood visualization)
    // Style Guide §1.4: Gradients must feel alive, not graphic-design perfect
    decorative: {
      neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
      deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
      electricPurple: 'linear-gradient(135deg, #c44569 0%, #7366F0 100%)',
      cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
      gradientPink: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      gradientBlue: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      gradientGreen: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      gradientSunset: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      gradientTeal: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
      gradientPastel: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
      gradientRose: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
    },

    // Overlay gradients (for fades, scrim effects)
    overlay: {
      bottomFade: 'linear-gradient(to top, rgba(11, 16, 32, 0.8), transparent)',
      topFade: 'linear-gradient(to bottom, rgba(11, 16, 32, 0.8), transparent)',
      radialDark: 'radial-gradient(circle, transparent 0%, rgba(11, 16, 32, 0.6) 100%)',
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
    // (21,29,47 — the dominant shell tint) at the opacity steps the app shell
    // uses, so glass surfaces (top bar, sidebar, player, container, cards,
    // artist rows) stay consistent and can be retuned from one place. Replaces
    // five hand-picked blue-black tuples (21,29,47 / 16,23,41 / 11,16,32 /
    // 27,35,46) that were scattered across components.
    starfield: {
      faint: 'rgba(21, 29, 47, 0.25)',
      subtle: 'rgba(21, 29, 47, 0.40)',
      soft: 'rgba(21, 29, 47, 0.45)',
      medium: 'rgba(21, 29, 47, 0.50)',
      strong: 'rgba(21, 29, 47, 0.55)',
      solid: 'rgba(21, 29, 47, 0.65)',
      sharp: 'rgba(21, 29, 47, 0.70)',
    },

    // Subtle glass (calm overlays - for idle states)
    // Bevel: top light catch, bottom shadow for 3D glass effect
    subtle: {
      background: 'rgba(21, 29, 47, 0.25)',
      backdropFilter: 'blur(6px) saturate(1.05)',
      border: 'none',
      // Bevel: outer shadow + top highlight + bottom shadow
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.15)',
    },

    // Medium glass (panels, surfaces)
    medium: {
      background: 'rgba(21, 29, 47, 0.40)',
      // Per-mode backgrounds for the glassEffects.minimal utility (#3948),
      // which runs slightly more opaque than the base medium background.
      backgroundDark: 'rgba(21, 29, 47, 0.45)',
      backgroundLight: 'rgba(255, 255, 255, 0.6)',
      backdropFilter: 'blur(8px) saturate(1.08)',
      border: 'none',
      // Bevel: outer shadow + top highlight + bottom shadow
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.12), inset 0 -1px 0 rgba(0, 0, 0, 0.18)',
    },

    // Strong glass (modals, prominent surfaces, player bar)
    strong: {
      background: 'rgba(21, 29, 47, 0.55)',
      // Per-mode backgrounds for the glassEffects.strong utility (#3948),
      // which runs more opaque than the base strong background for solid presence.
      backgroundDark: 'rgba(21, 29, 47, 0.65)',
      backgroundLight: 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'blur(12px) saturate(1.1)',
      border: 'none',
      // Bevel: outer shadow + top highlight + bottom shadow
      boxShadow: '0 16px 48px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.15), inset 0 -1px 0 rgba(0, 0, 0, 0.20)',
    },

    // Violet-tinted glass (accent surfaces - playback/active states)
    violet: {
      background: 'linear-gradient(135deg, rgba(115, 102, 240, 0.12) 0%, rgba(21, 29, 47, 0.50) 100%)',
      backdropFilter: 'blur(10px) saturate(1.15)',
      border: 'none',
      // Violet bevel
      boxShadow: '0 8px 32px rgba(115, 102, 240, 0.20), inset 0 1px 0 rgba(115, 102, 240, 0.25), inset 0 -1px 0 rgba(0, 0, 0, 0.20)',
    },

    // Aqua-tinted glass (audio-reactive surfaces - processing/energy)
    aqua: {
      background: 'linear-gradient(135deg, rgba(71, 214, 255, 0.10) 0%, rgba(21, 29, 47, 0.50) 100%)',
      backdropFilter: 'blur(10px) saturate(1.15)',
      border: 'none',
      // Aqua bevel
      boxShadow: '0 8px 32px rgba(71, 214, 255, 0.18), inset 0 1px 0 rgba(71, 214, 255, 0.20), inset 0 -1px 0 rgba(0, 0, 0, 0.20)',
    },
} as const;
