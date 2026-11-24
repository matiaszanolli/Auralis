# Auralis UI Style Guide

**Scope**: visual language, theming, components, motion
**Platform**: the Electron desktop app (see [subsystems/frontend.md](subsystems/frontend.md))
**Core idea**: audio as a living system, not a dataset

**Token source of truth**: `auralis-web/frontend/src/design-system/tokens/` (merged by
`tokens.ts`, imported as `import { tokens } from '@/design-system'`). Every value named below is
a token key; if this page and the tokens disagree, the tokens win. Theme-aware colour goes
through `themeVars` in `src/theme/semanticTheme.ts` (section 1.2).

> Every visual decision must either clarify the music or get out of its way. If an element does
> neither: remove it, hide it, or demote it.

---

## 1. Color System

### 1.1 Philosophy

Colour in Auralis is stateful and atmospheric, not decorative.

- Colour represents behaviour, not categories.
- Colour is rarely solid; light and glow matter more than hue.
- Saturation increases only when music is active.

If a colour feels loud when nothing is playing, it is wrong.

### 1.2 Base colours and themes

Dark is the canonical theme, and the default. Light is an option in Settings → Interface.

| Role | Dark value | Token |
|------|-----------|-------|
| Canvas | `#0B1020` deep blue-black | `colors.bg.level0` |
| Primary surface | `#101729` | `colors.bg.level1` |
| Secondary surface | `#151D2F` | `colors.bg.level2` |
| Raised surface | `#1A2338` | `colors.bg.level3` |
| Dialogs and overlays | `#1F2940` | `colors.bg.level4` |
| Glass surfaces | translucent `bg.level2` with blur | `glass.starfield`, `glass.subtle`, `glass.strong` |

Rules:

- No pure black and no flat grey; the background should feel like a dark studio room, not a void.
- Overlays sit over a translucent scrim (`themeVars.backdrop`) or use a `glass` preset; they are
  never a hard opaque slab.

**Semantic theme contract.** Components do not choose a palette level. They read `themeVars`
(`canvas`, `surfacePrimary`, `surfaceSecondary`, `surfaceRaised`, `surfaceOverlay`, `textPrimary`,
`textSecondary`, `textMuted`, `textDisabled`, `borderSubtle`, `borderDefault`, `borderStrong`,
`accent`, `accentText`, `success`, `warning`, `error`, `panelFill`, `hoverFill`, `selectedFill`, and
more), which resolve to `--app-*` CSS variables for the active mode. `ThemeProvider` writes the
variables on the document root. Fills built from white alpha (`colors.opacityScale.white`) are
invisible in light mode, so use `panelFill`, `hoverFill` and `selectedFill` for control and
container fills.

**Light theme** is restrained comfort, not spectacle. Its palette is `colors.lightMode`:

- The canvas is a cool off-white (`#F8F9FD`); cards, menus and primary surfaces may be white.
- Text is ink navy (`#1A1F3A`, secondary `#5A6280`).
- Shadows are lighter (`shadows` keys `md` and `xl` where dark uses `lg` and `2xl`).
- Status and accent text use darker variants (`lightMode.accent.*`, `lightMode.text.accent`) so
  they meet WCAG AA contrast on the light canvas.
- Unfilled slider rails, switch tracks and scrollbar thumbs use `themeVars.controlTrack`, which
  keeps 3:1 contrast against the page in both modes.

### 1.3 Accent colours

Accents are semantic, not arbitrary.

| Colour | Meaning | Token |
|--------|---------|-------|
| Violet `#7366F0` | Identity, focus, playback (the brand accent) | `colors.audioSemantic.identity`, `colors.accent.primary` |
| Cyan `#47D6FF` | Spatial width, clarity | `colors.audioSemantic.spatial`, `colors.accent.secondary` |
| Magenta `#EC4899` | Harmonic richness, vibrancy | `colors.audioSemantic.harmonic` |
| Amber `#F59E0B` | Transients, intensity, peaks | `colors.accent.energy` |
| Green `#10B981` | Stability, success | `colors.semantic.success` |

Feedback states use `colors.semantic` (`success`, `warning`, `error`, `info`). `semantic.error` is
for text, icons and borders; anything that carries white text on red uses `semantic.errorFill`
(and `errorFillHover`) for contrast.

Usage rules:

- Never more than two accents in the same component.
- Accents fade in and out with state.
- Glow beats fill: prefer `shadows.glowSoft` / `glowMd` and translucent fills
  (`colors.opacityScale.accent.*`) over solid colour.

### 1.4 Gradients

Gradients are first-class: they represent fingerprints, mood projections, and album identity when
art is missing.

- Brand and surface gradients: `gradients.aurora`, `gradients.darkSubtle`, `gradients.glassShimmer`,
  and the `shimmerSweep` hover gradient.
- Decorative sets for placeholders: `gradients.decorative.*`.
- The energy meter's calm-to-aggressive ramp: `energyGradient(alpha)`.
- Fingerprint-derived gradients: `src/utils/fingerprintToGradient.ts`.

Rules: gradients have depth (radial or diagonal), no harsh transitions, and should feel alive
rather than graphic-design perfect.

---

## 2. Borders, Shapes and Depth

### 2.1 Borders

Borders are almost never visible.

- Allowed: 1 px translucent borders for focus or separation in dense layouts, from
  `colors.border.light` / `medium` / `heavy` or `themeVars.borderSubtle` / `borderDefault`.
- Disallowed: hard separators, table gridlines, high-contrast outlines.

If you can see a border clearly, it is too strong.

### 2.2 Corner radius

Corners are soft but confident. Tokens (`borderRadius`): `sm` 8 px (the minimum for any rounded
interactive element), `md` 12 px, `lg` 16 px, `xl` 20 px, `full` 9999 px.

| Component | `borderRadius` key |
|-----------|--------|
| Buttons | `md` |
| Cards, panels | `md` to `lg` |
| Album art | `md` |
| Pills and circular buttons | `borderRadius.full` |

Never mix sharp and rounded elements in the same context.

### 2.3 Depth and elevation

Depth comes from shadow softness, blur and light falloff, not from strong drop shadows or z-axis
theatrics.

- Shadows are large and soft (`shadows.sm` to `2xl`); elevation increases only on interaction.
- Glass presets (`glass.subtle`, `glass.strong`) add backdrop blur and a light-catching bevel.
- No floating panels unless intentional (overlays). Layering uses `zIndex` (`content`, `elevated`,
  `dropdown`, `sticky`, `fixed`, `toast`).

---

## 3. Typography

### 3.1 Typefaces

| Family | Role | Token |
|--------|------|-------|
| Asap (variable, bundled) | All UI text: controls, metadata, titles | `typography.fontFamily.primary`, `header` |
| JetBrains Mono (variable, bundled) | Technical readouts (dB, Hz, LUFS) | `typography.fontFamily.mono` |

Both fonts ship with the app (`@fontsource-variable/*`), so the UI renders offline with no font
CDN. Emphasis comes from weight and size, not from a second display face.

### 3.2 Scale and hierarchy

Sizes: `fontSize.xs` 11 px, `sm` 13, `base` 14, `md` 16, `lg` 18, `xl` 22, `2xl` 28, `3xl` 36, `4xl`
56, plus `display` 48 and `huge` 80 for artwork glyphs and empty-state icons. Weights: `normal` 400,
`medium` 500, `semibold` 600, `bold` 700.

Hierarchy is built from size, spacing, weight and opacity, never from colour alone.

### 3.3 Text colour

| Type | Dark value | Token (`themeVars`, or `tokens.colors.text` in dark-only code) |
|------|-----------|-------|
| Primary | 95 % white | `textPrimary` / `text.primary` (`text.primaryFull` for peak emphasis) |
| Secondary | 68 % white | `textSecondary` / `text.secondary` |
| Metadata and labels | 60 % white | `textMuted` / `text.metadata` |
| Disabled | 40 % white | `textDisabled` / `text.disabled` |

Metadata is held at 60 % so small text keeps 4.5:1 contrast on `bg.level1`; do not lower it. Text
should sit in space, not scream.

---

## 4. Spacing

Spacing is organic rhythm rather than a strict grid: tight inside groups, generous between
sections.

- Within elements: `spacing.xxs` 2 px, `xs` 4, `sm` 6.
- Between elements: `md` 12, `lg` 20, `xl` 28; between sections `xxl` 40 and `xxxl` 56.
- Named groupings: `cluster` 8 px (items in a natural cluster, and MUI's spacing unit), `group`
  16 px, `section` 32 px.

Use spacing instead of lines to separate things.

---

## 5. Cards and Thumbnails

**Album cards** are identity anchors: album art dominates, metadata is quiet, context badges are
subtle, and cards lift gently on hover (`components.albumCard.hoverScale`). They should feel
collectible, not interchangeable.

**Placeholder covers.** When no art exists, use a fingerprint-derived or per-album gradient (see
1.4); never flat neon blocks, and never the same pattern for every album.

---

## 6. Controls and Interaction

Control primitives live in `src/design-system/primitives/`: `Button` (`primary`, `secondary`,
`ghost`, `danger`), `IconButton`, `Card`, `Slider`, `SegmentedControl`, `Chip`, `CircularProgress`,
`List`, `Alert`, `Tooltip`. Layout and text use `@mui/material` directly.

- **Buttons** are inviting, not assertive: no sharp edges, no aggressive colours, primary buttons
  glow softly, secondary buttons rely on outline and blur. Hover is calm, not instant.
- **Sliders** represent continuous change: rounded tracks, soft thumbs, glow that grows with the
  value, no hard ticks unless required. Sliders should feel analog.
- **Pills and badges** (`Chip`) describe mood, context or state: low contrast, soft glow, never
  stacked densely.

---

## 7. Motion

Motion is slow, weighted, predictable and purposeful. If motion draws attention to itself, it is
wrong.

| Interaction | Duration | Token |
|-------------|----------|-------|
| Hover | 120-180 ms | `transitions.hover` (150 ms), `hover_out` with easing |
| State change | 300-600 ms | `transitions.stateChange` (450 ms), `state_inOut` |
| Slower state change | 600 ms | `transitions.slow`, `slow_inOut` |
| Audio-reactive lag | 80-120 ms | `transitions.audioLag` (100 ms) |

Easing is `transitions.easeOut` or `easeInOut`. No bounce and no fast oscillation.

Audio-reactive visuals use heavy smoothing, no frame-perfect sync, and show trend rather than
sample data: the UI interprets, it does not measure. Motion stops gracefully when playback stops
(the Album Character pane decays over a few seconds), and the ambient starfield background can be
switched off with Settings → Interface → "Show visualizations". Under `prefers-reduced-motion`
global styles suppress animation and the starfield draws a single static frame.

---

## 8. Auto-Mastering and Visualization

Visuals answer "what is the music doing now?", not "what are the numbers?".

- Allowed: flowing waves, halos, breathing gradients, soft arcs, ambient fields.
- Disallowed: bar graphs, meters, always-on percentage indicators.
- Numbers exist but are hidden by default, revealed on interaction, and secondary in hierarchy.
  Engineers can inspect; listeners can listen.

The Album Character pane (see
[frontend/PLAYER_ENHANCEMENT_ARCHITECTURE.md](frontend/PLAYER_ENHANCEMENT_ARCHITECTURE.md)) is
the reference implementation: an "Auto-Mastering" switch above a living picture of the track's
character, with no parameter sliders.

---

## 9. Layout

- **Surfaces over cards.** Use spacing to separate, avoid visual fragmentation, let content breathe.
- **Contextual panels.** The right-hand pane responds to context (the playing track's character,
  or the hovered album's aggregate) and should respond, not dominate. Component sizes such as
  `components.playerBar.height` (96 px), `sidebar.width` (256 px) and `rightPanel.width` (360 px) are
  tokens.
- **Responsive.** Breakpoints are `breakpoints.xs` 0, `sm` 600, `md` 900, `lg` 1200, `xl` 1536;
  use `mediaBelow(key)` in CSS-in-JS so a rule flips at the same pixel as MUI's
  `breakpoints.down(key)`. The layout adapts below 900 px, but desktop is the supported target.

---

## 10. Accessibility and Comfort

- Contrast meets WCAG AA without harshness; contrast-bearing tokens carry their ratio in a comment
  beside the value.
- Motion can be reduced globally.
- No flashing elements and no colour-only state indication (connection state, for example, is also
  announced as text).
- Dialogs, menus and lists are keyboard-operable with visible focus (`themeVars.focusRing`).

Accessibility should feel natural, not bolted on.

---

## 11. Using the tokens

```typescript
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

const sx = {
  color: themeVars.textPrimary,              // theme-aware colour
  background: themeVars.surfaceSecondary,
  padding: tokens.spacing.md,                // spacing, radii, type, motion: tokens
  borderRadius: tokens.borderRadius.md,
  fontSize: tokens.typography.fontSize.base,
  transition: tokens.transitions.hover_out,
  boxShadow: tokens.shadows.glowSoft,
};
```

| Aspect | Do | Don't |
|--------|----|-------|
| Colour | Glows, translucent fills, `themeVars` | Solid loud colours, hex literals in components |
| Borders | Translucent, barely visible | Hard lines, gridlines |
| Text | Opacity-based hierarchy | Colour-based hierarchy |
| Motion | 150 ms hover, 450 ms state change | Bounce, fast oscillation |
| Visuals | Waves, halos, gradients | Bar graphs, meters |
| Numbers | Hidden, revealed on interaction | Always visible |
