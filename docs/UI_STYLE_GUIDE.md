# Auralis UI Style Guide

**Scope**: Visual language, theming, components, motion
**Applies to**: Desktop (primary), adaptable to tablet/mobile
**Core idea**: Audio as a living system, not a dataset

> **Final Guiding Principle**: Every visual decision must either clarify the music or get out of its way. If an element does neither: Remove it, Hide it, or Demote it.

---

## 1. Color System

### 1.1 Philosophy

Color in Auralis is **stateful and atmospheric**, not decorative.

**Rules**:
- Color represents behavior, not categories
- Color is rarely solid
- Light and glow matter more than hue
- Saturation increases only when music is active

> **If a color feels "loud" when nothing is playing, it's wrong.**

### 1.2 Base Colors

#### Dark Theme (Canonical)

| Role | Description |
|------|-------------|
| Base background | Deep blue-black, slightly cool (`#0B1020`) |
| Surface | +4–8% luminance over base (`#101729`) |
| Raised surface | +10–14% luminance, blurred backdrop (`#1A2338`) |
| Overlay | Translucent, never opaque |

**Critical**:
- No pure black
- No flat gray
- The background should feel like a dark studio room, not a void

#### Light Theme (Secondary)

Light mode is intentionally restrained.

**Rules**:
- Never pure white
- Use warm off-white / parchment tones
- Reduce glow intensity by ~50%
- Reduce saturation across the board

Light mode exists for comfort, not spectacle.

### 1.3 Accent Colors

Accent colors are **semantic**, not arbitrary.

| Color Family | Meaning | Token |
|--------------|---------|-------|
| Indigo / Violet | Identity, focus, playback | `audioSemantic.identity` |
| Cyan / Teal | Spatial width, clarity | `audioSemantic.spatial` |
| Green | Energy stability, balance | `audioSemantic.stability` |
| Amber / Warm | Transients, intensity, peaks | `audioSemantic.transient` |
| Magenta / Pink | Harmonic richness, vibrancy | `audioSemantic.harmonic` |

**Usage rules**:
- Never use more than 2 accents in the same component
- Accents fade in and out with state
- **Glow > fill**

### 1.4 Gradients

Gradients are **first-class citizens** in Auralis.

They represent:
- Fingerprints
- Mood projections
- Album identity (when art is missing)

**Rules**:
- Gradients always have depth (radial or diagonal)
- No harsh transitions
- Slight noise or grain is encouraged
- Gradients must feel alive, not graphic-design perfect

---

## 2. Borders, Shapes & Depth

### 2.1 Borders (Minimal by Design)

Borders are **almost never visible**.

**Allowed**:
- 1px translucent borders at <10% opacity
- Only for focus or separation in dense layouts

**Disallowed**:
- Hard separators
- Table gridlines
- High-contrast outlines

> **If you can see a border clearly, it's too strong.**

### 2.2 Corner Radius

Auralis corners are soft but confident.

| Component | Radius |
|-----------|--------|
| Buttons | Medium (`12px`) |
| Cards | Medium–large (`12-16px`) |
| Album art | Medium (`12px`) |
| Pills | Fully rounded (`9999px`) |

**Never mix sharp and rounded elements in the same context.**

### 2.3 Depth & Elevation

Depth is communicated via:
- Shadow softness
- Blur
- Light falloff

**Not via**:
- Strong drop shadows
- Z-axis theatrics

**Rules**:
- Shadows are large and soft
- Elevation increases only on interaction
- No floating panels unless intentional (overlays)

---

## 3. Typography

### 3.1 Typeface Roles

| Typeface | Role |
|----------|------|
| Inter | UI, controls, metadata |
| Manrope | Identity, titles, emphasis |

Manrope is used **sparingly**. If everything is expressive, nothing is.

### 3.2 Hierarchy

Hierarchy is created by:
- Size
- Spacing
- Weight
- Opacity

**Never by color alone.**

### 3.3 Text Color Usage

| Type | Opacity | Token |
|------|---------|-------|
| Primary text | 90–100% | `text.primary` |
| Secondary text | 60–70% | `text.secondary` |
| Metadata | 40–50% | `text.metadata` |
| Disabled | <30% | `text.disabled` |

> **Text should sit in space, not scream.**

---

## 4. Cards & Thumbnails

### 4.1 Album Cards

Album cards are **identity anchors**.

**Rules**:
- Album art is dominant
- Metadata is quiet
- Context badges are subtle
- Cards lift gently on hover

> **Album cards should feel collectible, not interchangeable.**

### 4.2 Placeholder Covers

When no art exists:
- Use fingerprint-derived gradient
- Add subtle texture/noise
- Never use flat neon blocks
- Never repeat patterns identically

**Each album must feel unique even without art.**

---

## 5. Controls & Interaction

### 5.1 Buttons

Buttons are **inviting, not assertive**.

**Rules**:
- No sharp edges
- No aggressive colors
- Primary buttons glow softly
- Secondary buttons rely on outline + blur

Hover states are calm, not instant.

### 5.2 Sliders

Sliders represent **continuous change**.

**Rules**:
- Rounded tracks
- Soft thumbs
- Glow increases as value increases
- No hard ticks unless required

> **Sliders should feel analog.**

### 5.3 Pills & Badges

Pills are used for:
- Mood descriptors
- Context tags
- States

**Rules**:
- Low contrast
- Soft glow
- Never stacked too densely

They should feel **descriptive, not categorical**.

---

## 6. Motion & Animation

### 6.1 Motion Philosophy

Motion in Auralis is:
- **Slow**
- **Weighted**
- **Predictable**
- **Purposeful**

> **If motion draws attention to itself, it's wrong.**

### 6.2 Timing Guidelines

| Interaction | Duration | Token |
|-------------|----------|-------|
| Hover | 120–180ms | `transitions.hover` |
| State change | 300–600ms | `transitions.stateChange` |
| Audio-reactive | Lag audio by ~80–120ms | `audioReactive.lagMs` |

**Forbidden**:
- No fast oscillations
- No bounce easing

### 6.3 Audio-Reactive Visuals

**Rules**:
- Heavy smoothing
- No frame-perfect sync
- Motion represents trend, not sample data

> **The UI should feel like it's interpreting, not measuring.**

---

## 7. Auto-Mastering & Visualization

### 7.1 Visualization Purpose

Visuals answer: **"What is the music doing now?"**

Not: "What are the numbers?"

### 7.2 Allowed Visual Forms

- Flowing waves
- Halos
- Breathing gradients
- Soft arcs
- Ambient fields

**Disallowed**:
- Bar graphs
- Meters
- Percent indicators (always-on)

### 7.3 Numbers Policy

Numbers exist, but:
- Hidden by default
- Revealed on interaction
- Secondary in hierarchy

> **Engineers can inspect. Listeners can listen.**

---

## 8. Layout Guidelines

### 8.1 Surfaces Over Cards

Auralis is built from **surfaces**, not boxes.

- Use spacing to separate
- Avoid visual fragmentation
- Let content breathe

### 8.2 Contextual Panels

Panels adapt to context:
- Track view → Track Character
- Album view → Album Character
- Browse view → Mood / Discovery hints

**Panels should respond, not dominate.**

---

## 9. Accessibility & Comfort

**Rules**:
- Contrast meets standards without harshness
- Motion can be reduced globally
- No flashing elements
- No color-only state indication

> **Accessibility should feel natural, not bolted on.**

---

## 10. Implementation Reference

### Token Usage

```typescript
import { tokens } from '@/design-system'

// Colors
tokens.colors.bg.level0           // Base background
tokens.colors.text.primary        // Primary text (95% opacity)
tokens.colors.text.metadata       // Metadata (45% opacity)
tokens.colors.audioSemantic.spatial // Cyan for spatial/width

// Motion
tokens.transitions.hover          // 150ms
tokens.transitions.stateChange    // 450ms
tokens.audioReactive.lagMs        // 100ms audio lag

// Visualization policy
tokens.numbersPolicy.defaultVisibility // 'hidden'
tokens.visualization.allowed      // ['flowingWaves', 'halos', ...]
```

### Quick Reference Card

| Aspect | Do | Don't |
|--------|----|----|
| Colors | Use glows, translucent fills | Use solid, loud colors |
| Borders | <10% opacity, barely visible | Hard lines, gridlines |
| Text | Opacity-based hierarchy | Color-based hierarchy |
| Motion | 150ms hover, 450ms state | Bounce, fast oscillation |
| Visuals | Waves, halos, gradients | Bar graphs, meters |
| Numbers | Hidden, reveal on interaction | Always visible |

---

## Changelog

- **v1.0.0** (Dec 2025): Initial style guide implementation
  - Added audio-semantic accent colors
  - Added opacity-based text hierarchy
  - Added audio-reactive motion tokens
  - Added numbers policy and visualization guidelines
