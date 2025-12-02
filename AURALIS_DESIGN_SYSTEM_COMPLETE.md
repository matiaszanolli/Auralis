# Auralis UI/UX Design System & Redesign Specification

**Version**: 1.0 Final
**Date**: December 2025
**Status**: Ready for Implementation
**Target Design Aesthetic**: Premium audio-focused player (Tidal + FabFilter/Ozone + OS elegance)

---

## DESIGN PHILOSOPHY

Auralis is positioned as a **premium local-file audiophile player** with live auto-mastering. The interface must evoke:

- **Professional audio production** (FabFilter, iZotope Ozone)
- **Luxury consumer tech** (Tidal, Apple Music redesign direction)
- **Clean OS aesthetics** (macOS/Windows modern systems)
- **Audiophile precision** (numeric readouts, waveform visualization, real-time parameter display)

**Core Principles:**
- Soft, deep, elevating (no harsh contrasts)
- Premium without gamer-neon aesthetic
- Visual hierarchy through elevation, not borders
- All interactions feel weighted and intentional
- Audio-first: every parameter visible but unobtrusive

---

# PART 1: DESIGN SYSTEM TOKENS

## 1.1 COLOR PALETTE (STRICT)

### Primary Backgrounds (Elevation Levels)

| Level | Name | Hex | Usage | Alpha | Purpose |
|-------|------|-----|-------|-------|---------|
| **0** | Root | `#0A0C10` | Root app container | 100% | Absolute darkest, void-like |
| **1** | Deep Navy | `#0D111A` | Main content area | 100% | Primary background |
| **2** | Carbon Blue | `#131A24` | Panels, sidebars | 100% | Secondary elevated |
| **3** | Dark Layer | `#1B232E` | Cards, raised elements | 100% | Tertiary elevation |
| **4** | Surface | `#1F2936` | Overlays, modals, popovers | 100% | Highest non-floating |

### Brand Colors

| Name | Hex | Alpha | Usage |
|------|-----|-------|-------|
| **Soft Violet** | `#7366F0` | Primary 100% | Accent, buttons, focus rings |
| **Electric Aqua** | `#47D6FF` | Accent 100% | Audio-reactive elements, glows, active states |
| **Lavender Smoke** | `#C1C8EF` | Secondary text | Hint text, labels, disabled |
| **Ultra White** | `#FFFFFF` | Title text | Headers, emphasis |

### Semantic Colors

| State | Hex | Usage |
|-------|-----|-------|
| **Success** | `#10B981` | Process complete, valid input |
| **Warning** | `#F59E0B` | Caution, optimization needed |
| **Error** | `#EF4444` | Critical issues, failures |
| **Info** | `#3B82F6` | Informational messages |
| **Muted** | `#6B7194` | Tertiary text, disabled elements |

### Transparent Tints (for layers without background)

```
Soft Black (for lift): rgba(0, 0, 0, 0.12)
Medium Black (for separation): rgba(0, 0, 0, 0.24)
Heavy Black (for emphasis): rgba(0, 0, 0, 0.40)
```

---

## 1.2 TYPOGRAPHY (STRICT)

### Font Families

```typescript
// Headers & Titles
'Plus Jakarta Sans', 'Arial', sans-serif  // Weight: 600–700

// Body & UI Text
'Inter', 'Segoe UI', sans-serif  // Weight: 400–500

// Technical Readouts (LUFS, dB, %, Hz)
'JetBrains Mono', 'Courier New', monospace  // Weight: 500–600
```

### Type Scale

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|------|------|------|--------|-------------|----------------|
| **Display** | Plus Jakarta Sans | 48px | 700 | 1.2 | -0.02em |
| **H1** | Plus Jakarta Sans | 32px | 700 | 1.3 | -0.01em |
| **H2** | Plus Jakarta Sans | 24px | 700 | 1.4 | 0 |
| **H3** | Plus Jakarta Sans | 20px | 600 | 1.4 | 0 |
| **Title** | Plus Jakarta Sans | 18px | 600 | 1.4 | 0 |
| **Body Large** | Inter | 16px | 400 | 1.5 | 0 |
| **Body** | Inter | 14px | 400 | 1.5 | 0 |
| **Body Small** | Inter | 13px | 400 | 1.5 | 0.01em |
| **Label** | Inter | 12px | 500 | 1.4 | 0.02em |
| **Caption** | Inter | 11px | 400 | 1.3 | 0.01em |
| **Mono (Large)** | JetBrains Mono | 16px | 600 | 1.3 | 0 |
| **Mono (Standard)** | JetBrains Mono | 13px | 500 | 1.3 | 0.01em |
| **Mono (Small)** | JetBrains Mono | 11px | 500 | 1.2 | 0.01em |

---

## 1.3 SPACING & LAYOUT GRID

8px grid system (all values multiples of 8):

```typescript
xs: 4px    // Half-grid, tight spacing
sm: 8px    // Base grid
md: 16px   // Standard spacing
lg: 24px   // Large grouping
xl: 32px   // Extra large
xxl: 48px  // Heading groups
xxxl: 64px // Page sections
```

### Responsive Breakpoints

```
Mobile:   < 480px   (single column, full width)
Tablet:   480–1024px (2 columns, sidebar collapsed)
Desktop:  1024–1920px (sidebar + content, optimal)
Ultra:    > 1920px  (large panels, full feature set)
```

---

## 1.4 RADIUS & CURVES

```typescript
xs:    2px    // Micro-interactions (quick tooltips)
sm:    4px    // Small UI elements (badges, chips)
md:    8px    // Standard controls (buttons, inputs)
lg:    12px   // Cards, panels, default radius
xl:    16px   // Large containers, modals
xxl:   20px   // Hero sections, large panels
full:  9999px // Pills, avatars
```

**Philosophy**: No hard corners. Minimum lg (12px) for any card-like element. Prefer soft, approachable feel.

---

## 1.5 SHADOWS & ELEVATION

### Ambient Shadows (primary)

Soft, directional downward cast. No harsh black — always controlled opacity.

```typescript
// Elevation 1 (subtle cards)
shadow-md: 0 4px 12px rgba(0, 0, 0, 0.16)

// Elevation 2 (floating panels)
shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.20)

// Elevation 3 (modals, overlays)
shadow-xl: 0 12px 32px rgba(0, 0, 0, 0.28)

// Elevation 4 (tooltips, dropdowns)
shadow-2xl: 0 16px 40px rgba(0, 0, 0, 0.32)
```

### Glow Shadows (for audio-reactive elements)

```typescript
// Soft violet glow
glow-soft: 0 0 16px rgba(115, 102, 240, 0.20)

// Violet glow (medium)
glow-md: 0 0 24px rgba(115, 102, 240, 0.32)

// Electric aqua glow (active)
glow-aqua: 0 0 20px rgba(71, 214, 255, 0.24)

// Aqua intense (processing)
glow-aqua-intense: 0 0 32px rgba(71, 214, 255, 0.40)
```

### Glass Effect (Translucent)

For floating elements over content (player bar, overlay panels):

```typescript
background: rgba(19, 26, 36, 0.80)
backdrop-filter: blur(8px)
border: 1px solid rgba(115, 102, 240, 0.12)
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.24)
```

---

## 1.6 TRANSITIONS & ANIMATIONS

### Easing Functions

```typescript
// UI interactions
easeOut: cubic-bezier(0.4, 0, 0.2, 1)     // Quick, sharp (100ms)
easeInOut: cubic-bezier(0.4, 0, 0.6, 1)   // Natural (200ms)
easeIn: cubic-bezier(0.4, 0, 1, 1)        // Slow exit (300ms)

// Playback
easeSmooth: cubic-bezier(0.25, 0.46, 0.45, 0.94) // Audio-like fluidity
```

### Standard Durations

```typescript
fast: 100ms     // Hover states, micro-interactions
base: 200ms     // Color, opacity, scale changes
slow: 300ms     // Layout shifts, slide-in effects
verySlow: 500ms // Modals, major transitions
```

### Key Animations

```
Hover Lift: scale(1.02) + shadow increase (200ms)
Focus Ring: soft violet glow fade-in (150ms)
Audio-Reactive Pulse: aqua glow flicker (varies with audio)
Loading Shimmer: subtle gradient sweep left→right (1200ms loop)
```

---

## 1.7 Z-INDEX SCALE

```typescript
base:           0        // Content
interactive:    10       // Buttons, inputs
dropdown:       1000     // Dropdowns, popovers
sticky:         1020     // Sticky headers
fixed:          1030     // Fixed panels, sidebars
modalBackdrop:  1040     // Modal overlay (dark veil)
modal:          1050     // Modal dialog, large panels
popover:        1060     // Popovers, context menus
tooltip:        1070     // Tooltips (highest interactive)
toast:          1300     // Notifications (above all)
```

---

## 1.8 COMPONENT TOKENS

### Player Bar

```typescript
height: 96px            // Compact yet spacious
zIndex: 1030            // Fixed above content
background: rgba(13, 17, 26, 0.92)
backdropFilter: blur(12px)
borderTop: 1px solid rgba(115, 102, 240, 0.10)
shadow: 0 -8px 24px rgba(0, 0, 0, 0.24)
```

### Sidebar

```typescript
width: 256px            // Desktop
collapsedWidth: 72px    // Collapsed icon-only
background: #131A24
borderRight: 1px solid rgba(115, 102, 240, 0.08)
shadow: 2px 0 16px rgba(0, 0, 0, 0.12)
```

### Right Panel (Enhancement/Queue)

```typescript
width: 360px            // Desktop
minWidth: 300px         // Tablet minimum
background: #131A24
borderLeft: 1px solid rgba(115, 102, 240, 0.08)
shadow: -2px 0 16px rgba(0, 0, 0, 0.12)
```

### Card (Album/Track)

```typescript
borderRadius: lg (12px)
background: #1B232E
shadow: 0 4px 12px rgba(0, 0, 0, 0.16)
hoverShadow: 0 8px 24px rgba(0, 0, 0, 0.24)
hoverScale: 1.02
hoverBlur: none (reserve blur for modals)
transition: all 200ms easeInOut
```

### Album Cover (Large)

```typescript
borderRadius: xl (16px)
aspectRatio: 1/1
shadow: 0 12px 32px rgba(0, 0, 0, 0.28)
hoverShadow: 0 16px 40px rgba(0, 0, 0, 0.32)
```

### Input Field

```typescript
borderRadius: md (8px)
background: rgba(31, 41, 54, 0.60)
border: 1px solid rgba(115, 102, 240, 0.16)
focusBorder: 2px solid #7366F0
padding: 12px 16px (vertical × horizontal)
fontSize: 14px (Inter)
```

### Button (Primary Action)

```typescript
borderRadius: md (8px)
padding: 12px 24px
background: #7366F0
text: #FFFFFF (Ultra White)
shadow: none (fill is enough)
hoverBackground: #6B5FDD (10% darker)
activeScale: 0.98
focusRing: 2px solid rgba(115, 102, 240, 0.40)
transition: all 100ms easeOut
```

### Button (Secondary/Ghost)

```typescript
borderRadius: md (8px)
padding: 12px 24px
background: transparent
border: 1px solid rgba(115, 102, 240, 0.24)
text: #C1C8EF (Lavender Smoke)
hoverBackground: rgba(115, 102, 240, 0.12)
hoverBorder: rgba(115, 102, 240, 0.40)
transition: all 100ms easeOut
```

### Slider (Audio Parameter)

```typescript
height: 4px
thumbSize: 16px
trackBackground: rgba(115, 102, 240, 0.20)
thumbBackground: #7366F0
thumbHoverBackground: #47D6FF
thumbHoverShadow: 0 0 16px rgba(71, 214, 255, 0.32)
focusRing: none (glow is sufficient)
transition: all 200ms easeSmooth
```

---

## 1.9 GRADIENTS

```typescript
// Aurora (brand primary)
aurora: linear-gradient(135°, #7366F0 0%, #5A5CC4 100%)

// Aurora soft (overlays, hover states)
auroraSoft: linear-gradient(135°, rgba(115, 102, 240, 0.80) 0%, rgba(90, 92, 196, 0.80) 100%)

// Aurora vertical (headers, banners)
auroraVertical: linear-gradient(180°, #7366F0 0%, #5A5CC4 100%)

// Aqua (accent, audio-reactive)
aqua: linear-gradient(135°, #47D6FF 0%, #00BCC4 100%)

// Dark subtle (background transitions)
darkSubtle: linear-gradient(180°, #1B232E 0%, #131A24 100%)
```

---

# PART 2: COMPONENT SPECIFICATIONS

## 2.1 PLAYER BAR DOCK (Fixed Footer)

### Overview
A sleek, semi-translucent raised dock at the bottom of the window featuring centered playback controls with left track info and right volume/settings.

### Hierarchy & Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Cover] Track Name  ◄──────────────────────────────────► │
│ [2x48] Artist / Album  |▮▮▮▮▮░░░░░ 2:34 / 5:12       │
└─────────────────────────────────────────────────────────┘
         ↑ 16px padding vertical
         Left 256px    |    Center (controls)    |    Right

  [56×56 Cover]   [◀ ◼ ▶]   [🔊 ─────●──]  [≡ ⊕]
       16px      16px     16px    16px      8px

Total Height: 96px (includes padding)
```

### Color Specifications

```typescript
// Background: Glass effect
background: rgba(13, 17, 26, 0.92)
backdropFilter: blur(12px)

// Border: Soft violet hairline at top
borderTop: 1px solid rgba(115, 102, 240, 0.12)

// Shadow: Upward cast
boxShadow: 0 -8px 32px rgba(0, 0, 0, 0.24)

// Full width, fixed to viewport bottom
position: fixed
bottom: 0
left: 0
right: 0
zIndex: 1030 (above content)
```

### Section: Left (Track Info)

**Dimensions**: 256px (matches sidebar)

```
┌──────────────────────────┐
│ [56×56]  Now Playing    │
│ Cover    Artist Name    │
│          Album / 2:34   │
└──────────────────────────┘

Spacing:
- Cover: 16px × 16px padding
- Title: 18px / 700 weight / Plus Jakarta Sans / Ultra White
- Subtitle: 13px / 400 weight / Inter / Lavender Smoke
- Vertical spacing between title/subtitle: 4px
```

**States:**
- **Default**: Muted cover art, text normal opacity
- **Playing**: Cover has soft glow (`glow-aqua: 0 0 16px rgba(71, 214, 255, 0.20)`)
- **Paused**: Cover dims 20%, text opacity 0.70

**Interactions:**
- Click → Opens mini queue panel (slides up from player bar)
- Hover → Shows expand icon (→), slight lift (shadow increase)

---

### Section: Center (Playback Controls)

**Dimensions**: ~200px (3 buttons × 56px + 16px spacing)

```
            ◀          ◼ / ▶          ▶▶
          56px        56px          56px
          Prev        Play/Pause    Skip

Horizontal centering within viewport with even spacing (24px between buttons)
```

**Button Styling:**

```typescript
// Shape
borderRadius: full (9999px)    // Perfect circle
width: 56px
height: 56px

// Icon sizing
iconSize: 24px (centered within button)

// Colors
backgroundColor: rgba(31, 41, 54, 0.60)
iconColor: #C1C8EF (Lavender Smoke)

// Hover state
hoverBackgroundColor: #1B232E
hoverIconColor: #47D6FF (Electric Aqua)
boxShadow: 0 0 20px rgba(71, 214, 255, 0.16)

// Active state (playing)
activeBackgroundColor: rgba(115, 102, 240, 0.20)
activeIconColor: #7366F0
boxShadow: 0 0 24px rgba(115, 102, 240, 0.24)

// Transition
transition: all 200ms easeInOut
```

**Keyboard Shortcuts:**
- `Space` → Play/Pause
- `◄` / `►` → Previous/Next (if focused)

---

### Section: Right (Volume + Settings)

**Dimensions**: ~200px (volume slider 120px + icon button 56px + spacing)

```
┌────────────────────────────┐
│ 🔊 ──────●─── 80%   [⋯]   │
└────────────────────────────┘

Volume Slider: 120px width
Settings Icon Button: 56px
Spacing between: 16px
Vertical padding: 12px (center align)
```

**Volume Slider:**

```typescript
// Track
height: 4px
backgroundColor: rgba(115, 102, 240, 0.20)
borderRadius: full (9999px)

// Thumb
width: 16px
height: 16px
borderRadius: full
backgroundColor: #7366F0

// Hover
boxShadow: 0 0 16px rgba(71, 214, 255, 0.24)
backgroundColor: #47D6FF

// Interaction
draggable: true
onChange: debounced(50ms) playback volume update
```

**Settings Button:**

```typescript
borderRadius: full (9999px)
width: 56px
height: 56px
backgroundColor: rgba(31, 41, 54, 0.60)
iconColor: #C1C8EF
hoverBackgroundColor: #1B232E
hoverIconColor: #47D6FF
boxShadow: (on hover) 0 0 20px rgba(71, 214, 255, 0.16)
```

---

### Section: Progress Bar

**Below Controls** (spans full width, above main content)

```typescript
// Container
height: 4px
backgroundColor: rgba(115, 102, 240, 0.12)
borderRadius: full (9999px)

// Playback fill (animate on play)
backgroundColor: #7366F0
width: (currentTime / duration × 100%)

// Hover state
height: 6px (expand upward)
backgroundColor: #47D6FF
boxShadow: 0 0 16px rgba(71, 214, 255, 0.24)

// Thumb (on hover)
width: 12px
height: 12px
borderRadius: full
backgroundColor: #FFFFFF
boxShadow: 0 0 12px rgba(71, 214, 255, 0.32)
cursor: pointer

// Transition
transition: all 200ms easeSmooth
```

**Interaction:**
- Click anywhere → Seek to position
- Drag thumb → Smooth scrubbing
- Show tooltip on hover: "2:34 / 5:12"

---

### Progress Display (Inside Progress Bar Area)

On hover over progress bar, show inline time display:

```
╭─────────────────────────────────────────────╮
│ ▮▮▮▮▮▮▮░░░░░░ 2:34 / 5:12 (Remaining: 2:38)│
└─────────────────────────────────────────────┘

Font: JetBrains Mono, 11px, 500 weight
Color: #C1C8EF (muted white)
Position: Center-bottom of progress bar
Opacity: fade in on hover (100ms)
```

---

## 2.2 ALBUM GRID SCREEN

### Overview
Large album covers in a responsive grid with soft hover states, play button overlay, and contextual information.

### Grid Layout

```typescript
// Responsive columns by breakpoint
Mobile (< 480px):    2 columns
Tablet (480–1024):   3 columns
Desktop (1024–1440): 4 columns
Ultra (> 1440):      5–6 columns

// Spacing
columnGap: 20px
rowGap: 24px
horizontalPadding: 24px
verticalPadding: 32px
```

### Card Structure

```
┌──────────────────────┐
│                      │
│     [ALBUM ART]      │   ← 200×200px (high DPI: 2x)
│     [Large Cover]    │
│                      │
├──────────────────────┤
│  Album Name          │   ← Title: 16px / 600 weight
│  Artist Name         │   ← Subtitle: 13px / 400 weight / muted
│  2024 • 12 Tracks    │   ← Meta: 11px / 400 weight / very muted
└──────────────────────┘

Card Width: Responsive (100% / columns) - 12px gap
Total Card Height: 280px (200 cover + 80 text area)
```

---

### Card Styling

```typescript
// Container
borderRadius: lg (12px)
backgroundColor: transparent (cover art is the visual)
padding: 0 (no internal padding for cover)
overflow: hidden

// Cover image
borderRadius: lg (12px)
width: 100%
aspectRatio: 1/1
objectFit: cover
boxShadow: 0 4px 12px rgba(0, 0, 0, 0.16)

// Text section
padding: 16px
backgroundColor: transparent (floating over background)
```

---

### Hover State

**Cover Image:**
```typescript
// On hover: Soft lift + blur background
transform: scale(1.04)
boxShadow: 0 12px 32px rgba(0, 0, 0, 0.28)
filter: brightness(1.08)  // Very subtle brightening (8%)
transition: all 200ms easeInOut

// Overlay: Play button + gradient
position: absolute / inset 0
background: linear-gradient(180°, rgba(0,0,0,0) 0%, rgba(0,0,0,0.40) 100%)
opacity: 0 → 1
transition: opacity 200ms easeOut
```

**Play Button Overlay:**
```
┌──────────────────────┐
│       ▶              │  ← Circular button
│     (56×56px)        │
│                      │
└──────────────────────┘

Position: center of cover (absolute)
Button specs:
  - Shape: Circle (56×56)
  - Background: rgba(115, 102, 240, 0.90)
  - Icon: ▶ (24px, Ultra White)
  - Shadow: 0 0 20px rgba(115, 102, 240, 0.40)
  - Hover: Scale 1.12, shadow intensity +20%
  - Click: Bounce animation (scale 0.95 → 1.0)
```

**Text Area (On Hover):**
```typescript
// Title
color: #FFFFFF (Ultra White)
fontWeight: 600
fontSize: 16px

// Artist + Meta
color: #C1C8EF (Lavender Smoke) — brighter on hover
opacity: 1.0 (from 0.80)
transition: opacity 200ms easeInOut

// Add subtle background lift
backgroundColor: rgba(19, 26, 36, 0.40)
backdropFilter: blur(4px)
borderRadius: md (8px)
padding: 12px 16px
transition: all 200ms easeInOut
```

---

### Context Menu (Right-Click)

```
┌──────────────────────┐
│ ► Play              │
│ + Add to Playlist   │
│ ┌─ Go to Artist     │
│ ✎ Edit Metadata    │
│ ★ Add to Favorites │
│ ✂ Remove          │
└──────────────────────┘

Styling:
- Background: #1F2936 with glass effect
- Border: 1px solid rgba(115, 102, 240, 0.12)
- Shadow: 0 8px 24px rgba(0, 0, 0, 0.24)
- Item height: 40px
- Icon + text spacing: 12px
- Hover item: background rgba(115, 102, 240, 0.12)
- Font: Inter 14px / 400 weight
- Color: #C1C8EF (normal), #FFFFFF (hover)
```

---

### Batch Selection Mode

When entering batch selection (Cmd+A or checkbox toggle):

```
┌─────────────────────────┐
│ ☑ [Album Cover]        │  ← Checkbox appears top-left
│   Album Name           │
│   Artist • Meta        │
└─────────────────────────┘

Checkbox specs:
- Position: 8px from top-left corner
- Size: 24×24
- Border: 2px solid #7366F0
- Background: transparent (unchecked) / #7366F0 (checked)
- Checkmark: white, 1.5px stroke
- Border-radius: 4px
- Transition: all 100ms easeOut

Card styling (selected):
- Border: 2px solid #7366F0
- Shadow: 0 0 16px rgba(115, 102, 240, 0.24)
- Overlay: rgba(115, 102, 240, 0.08) tint
```

---

### Empty State

When library is empty:

```
        🎵 (large icon, 96px, muted violet)

    Your Library is Empty
    (32px, Plus Jakarta Sans, 700 weight, Ultra White)

  Drag audio files here or use File → Add Folder
  (14px, Inter, Lavender Smoke, centered)

  [Browse Folder] [YouTube Search]
  (Secondary buttons, 16px padding)
```

---

## 2.3 ALBUM DETAIL SCREEN

### Overview
Full album view with large cover art on the left, metadata in a sidebar, and tracklist on the right. Uses elevation and tone shifts to separate regions without borders.

### Layout Grid (3-Column)

```
┌─────────────────────────────────────────────────────────────────┐
│ [←]                                                             │
├──────────────────┬──────────────────┬──────────────────────────┤
│                  │   Album Name     │ Track 1  3:45            │
│   Album Cover    │   Artist Name    │ Track 2  4:02            │
│   (320×320)      │   ────────────── │ Track 3  3:28            │
│                  │   2024 • 12 trks │ Track 4  4:15            │
│                  │   123 min        │ Track 5  3:52            │
│   [▶ Play All]   │   ────────────── │ ┈ (scrollable)           │
│   [★ Favorite]   │   Genres, Style  │                          │
│   [⋯ More]       │                  │                          │
└──────────────────┴──────────────────┴──────────────────────────┘

Left Column (width ~20%):   Album art + action buttons
Center Column (width ~15%): Metadata block
Right Column (width ~65%):  Tracklist (scrollable)
```

---

### Section: Album Cover (Left)

```
┌─────────────────────┐
│                     │
│   [Album Art]       │  ← 320×320px cover
│                     │
└─────────────────────┘

Shadow: 0 12px 32px rgba(0, 0, 0, 0.28)
Border-radius: xl (16px)

On hover:
- Scale: 1.02
- Shadow: 0 16px 40px rgba(0, 0, 0, 0.32)
- Glow: 0 0 24px rgba(71, 214, 255, 0.16) (if playing)
```

**Action Buttons (Below Cover):**

```
  [▶ Play All]
   56×56 circular button
   Background: rgba(115, 102, 240, 0.20)
   Icon: ▶ 24px
   Hover: background #7366F0, glow

  [★ Favorite]
   40×40 icon button
   Icon: ☆ / ★ 20px
   Color: Lavender Smoke / aqua (if favorited)
   Hover: scale 1.1

  [⋯ More]
   40×40 icon button
   Opens context menu
```

---

### Section: Metadata (Center)

```
┌──────────────────────┐
│ Album Name           │  ← 20px / 700 / Plus Jakarta Sans
│ Artist Name          │  ← 16px / 400 / Inter / Lavender Smoke
│                      │  ← Divider: 1px dashed rgba(115,102,240,0.12)
│ 2024 • 12 Tracks     │  ← 13px / 400 / Inter / muted
│ 123 minutes          │
│ Released: Jan 15     │
│ Label: XYZ Records   │
│                      │  ← Divider
│ Genres               │  ← 12px / 500 / caps / label
│ Electronic • House   │  ← 13px / 400 / inline chips
│ • Ambient            │
└──────────────────────┘

Container:
- Width: 180px
- Background: transparent (uses ambient color)
- Padding: 24px
- Spacing between groups: 16px
- Divider: 1px solid rgba(115, 102, 240, 0.12)
```

---

### Section: Tracklist (Right)

```
Track #  Title              Artist         Duration  ♡
──────────────────────────────────────────────────────
 1       Track One          Album Artist   3:45      ☆
 2       Track Two          Album Artist   4:02      ☆
 3       Track Three        Album Artist   3:28      ☆
 4       Track Four         Album Artist   4:15      ☆
         ...scrollable...
```

**Header Row:**
```typescript
// Sticky to top of tracklist
position: sticky
top: 0
zIndex: 10
backgroundColor: rgba(13, 17, 26, 0.96)
backdropFilter: blur(6px)
borderBottom: 1px solid rgba(115, 102, 240, 0.08)
padding: 12px 16px
fontSize: 11px
fontWeight: 500
color: #6B7194 (muted)
textTransform: uppercase
letterSpacing: 0.05em
```

**Track Row:**

```
┌────────────────────────────────────────────────────┐
│ [Play Indicator] Track Name   Duration   [Favorite]│
│ 1 px divider at bottom (subtle)                     │
└────────────────────────────────────────────────────┘

Height: 48px
Padding: 8px 16px (vertical × horizontal)
Alignment: Vertically centered

Track Title:
- Font: Inter 14px / 400
- Color: #FFFFFF (normal), #7366F0 (current track)
- Weight: 400 (normal), 600 (current)

Artist:
- Font: Inter 13px / 400
- Color: #C1C8EF (muted white)
- Opacity: 0.70

Duration:
- Font: JetBrains Mono 12px / 500
- Color: #C1C8EF
- Text-align: right

Divider:
- 1px solid rgba(115, 102, 240, 0.06)
- Only visible on hover
```

**Row Hover State:**
```typescript
backgroundColor: rgba(31, 41, 54, 0.40)
borderRadius: md (8px) (on container hover)
boxShadow: 0 2px 8px rgba(0, 0, 0, 0.12)

// Show favorite toggle
favoriteIcon: opacity 0 → 1

// Current playing row (always highlighted)
borderLeft: 4px solid #7366F0
backgroundColor: rgba(115, 102, 240, 0.08)
```

**Drag to Reorder (Optional):**
```
On drag:
- opacity: 0.60
- transform: scale(0.98) rotate(2deg)
- cursor: grabbing
- shadow: 0 8px 24px rgba(0, 0, 0, 0.24)
```

---

### Interactions

**Double-click track** → Play immediately
**Right-click track** → Context menu (play, add to playlist, edit, remove)
**Cmd/Ctrl+Click** → Multi-select
**Drag to reorder** → Visual feedback (opacity, shadow, scale)

---

## 2.4 ARTIST SCREEN

### Overview
Header with artist name, optional image, stats, and two main sections: albums (horizontal strip) and all tracks (list). Uses large visual hierarchy to separate sections.

### Layout (Hero Header + Content Strips)

```
┌─────────────────────────────────────────────────────────┐
│ [←] Artist Name                         [★ ⋯]          │
│ ─────────────────────────────────────────────────────── │
│ 5 Albums • 47 Tracks • 4 Hours 23 Minutes              │
│                                                         │
│ ┌──────────────────────────────────────────────────┐   │
│ │ Albums                              [View All]   │   │
│ ├──────────────────────────────────────────────────┤   │
│ │ [Album 1] [Album 2] [Album 3] [Album 4] [→]    │   │
│ │  Album     Album     Album     Album            │   │
│ │  Name      Name      Name      Name             │   │
│ └──────────────────────────────────────────────────┘   │
│                                                         │
│ ┌──────────────────────────────────────────────────┐   │
│ │ Popular Tracks                                   │   │
│ ├──────────────────────────────────────────────────┤   │
│ │ 1. Track Title      4:23  [♡ ⋯]                │   │
│ │ 2. Track Title      3:45  [♡ ⋯]                │   │
│ │ 3. Track Title      3:28  [♡ ⋯]                │   │
│ │ [Show All Tracks]                               │   │
│ └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

### Header Section

```
┌─────────────────────────────────────────────────────────┐
│ ← Artist Name                            [★ ⋯ ▼]       │
│                                                         │
│ 5 Albums • 47 Tracks • 4 Hours 23 Minutes              │
│                                                         │
│ [▶ Play All]  [★ Add to Library]  [⋯ More]            │
│                                                         │
└─────────────────────────────────────────────────────────┘

Background:
- Gradient: linear-gradient(180°,
    rgba(115, 102, 240, 0.12) 0%,
    rgba(13, 17, 26, 0.0) 100%)
- No background image (keep it clean)
- Padding: 32px 24px

Title:
- Font: Plus Jakarta Sans 48px / 700
- Color: #FFFFFF (Ultra White)
- Margin-bottom: 16px

Stats:
- Font: Inter 14px / 400
- Color: #C1C8EF (Lavender Smoke)
- Spacing: 16px below title

Buttons:
- Layout: Horizontal row, left-aligned
- Spacing: 12px between buttons
- Types: Primary (Play All), Secondary (Add to Library)
```

---

### Albums Section (Horizontal Strip)

```
┌─────────────────────────────────────────────────────────┐
│ Albums                              [View All Albums]   │
├─────────────────────────────────────────────────────────┤
│ [Cover] [Cover] [Cover] [Cover] [Cover] [→]            │
│ Album 1 Album 2 Album 3 Album 4 Album 5                │
└─────────────────────────────────────────────────────────┘

Container:
- Padding: 32px 24px
- Background: transparent
- Margin-bottom: 32px

Section Title:
- Font: Plus Jakarta Sans 24px / 700
- Color: #FFFFFF
- Margin-bottom: 20px
- Layout: flex between (title left, "View All" right)

Album Cards (Horizontal):
- Width: 160px each
- Height: 240px (160 cover + 80 metadata)
- Spacing: 16px between cards
- Scrollable: Yes (use scrollbar if needed)
- Scroll behavior: smooth
- Show 4–5 per row (responsive)

Card styling: See Album Grid (same design)
```

**"View All Albums" Button:**
```typescript
Position: right side of section header
Size: 36×36 or text button
Background: transparent
Icon: → (right chevron) 20px / #C1C8EF
Hover: color #7366F0, scale 1.1
Click: Opens full album grid filtered to this artist
```

---

### Tracks Section (List)

```
┌─────────────────────────────────────────────────────────┐
│ Popular Tracks                                          │
├─────────────────────────────────────────────────────────┤
│ # | Title              Duration | Plays  | [♡ ⋯]      │
│─────────────────────────────────────────────────────────│
│ 1 | Track One          3:45     | 1.2K   | [♡ ⋯]      │
│ 2 | Track Two          4:02     | 950    | [♡ ⋯]      │
│ 3 | Track Three        3:28     | 743    | [♡ ⋯]      │
│ 4 | Track Four         4:15     | 621    | [♡ ⋯]      │
│ 5 | Track Five         3:52     | 549    | [♡ ⋯]      │
│                                                         │
│         [+ Show All (47 tracks)]                        │
└─────────────────────────────────────────────────────────┘

Container:
- Padding: 32px 24px
- Background: transparent
- Max-height: 400px (scrollable)
- Overflow: auto with custom scrollbar

Title:
- Font: Plus Jakarta Sans 20px / 600
- Color: #FFFFFF
- Margin-bottom: 20px

Track Rows:
- Height: 48px
- Padding: 8px 16px
- Font: Inter 14px / 400
- Divider: 1px solid rgba(115, 102, 240, 0.06)

Columns:
- Index: JetBrains Mono 12px / #6B7194
- Title: Inter 14px / #FFFFFF
- Duration: JetBrains Mono 12px / #C1C8EF
- Plays: Inter 12px / #6B7194
- Actions: 40px width (heart + menu icons)
```

**"Show All" Button:**
```
Centered below list
Text: "+ Show All (47 tracks)"
Font: Inter 14px / 500
Color: #7366F0
Hover: color #47D6FF, underline
Click: Expands full tracklist (or navigates to tracklist view)
```

---

## 2.5 AUTO-MASTERING PANEL (Enhancement Pane)

### Overview
Premium plugin-style UI inspired by FabFilter Pro-Q and iZotope Ozone. Real-time parameter visualization with audio-reactive elements. Preset selector, processing metrics, and parameter sliders.

### Panel Layout (Right-Side, Expandable)

```
┌─────────────────────────────────────────────┐
│ ◄ Auralis Enhancement              [x]     │
├─────────────────────────────────────────────┤
│                                             │
│  [Adaptive ▼]  [Gentle] [Warm] [Bright]   │
│                                             │
│  ┌─────────────────────────────────────┐  │
│  │ ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌ [Waveform/Spectrum] │
│  │ Analyzing 48 kHz | 2.0 dB Gain Reduction   │
│  └─────────────────────────────────────┘  │
│                                             │
│  Audio Characteristics:                    │
│  • Loudness:   -14.2 LUFS                 │
│  • Dynamics:   4.3 dB (moderate)           │
│  • Frequency:  Neutral (50Hz–5kHz boost)  │
│  • Stereo:     100% (mono-compat)          │
│                                             │
│  Processing Parameters:                    │
│  ┌─────────────────────────────────────┐  │
│  │ Peak Normalization    -2.0 dB   [─●─] │
│  │ EQ Tilt               +0.5 dB   [─●─] │
│  │ Compression Ratio     2.1:1     [─●─] │
│  │ Limiter Threshold    -2.0 dB    [─●─] │
│  └─────────────────────────────────────┘  │
│                                             │
│  [▼ Collapse]   [Reset]   [Save Preset]   │
│                                             │
└─────────────────────────────────────────────┘
```

---

### Panel Structure & Colors

```typescript
// Container
width: 360px (desktop), 300px (tablet minimum)
backgroundColor: #131A24
borderLeft: 1px solid rgba(115, 102, 240, 0.08)
borderRadius: 0 (edge-to-edge on right side)
boxShadow: -2px 0 16px rgba(0, 0, 0, 0.12)

// Header
padding: 20px 20px
backgroundColor: rgba(19, 26, 36, 0.60)
borderBottom: 1px solid rgba(115, 102, 240, 0.06)
fontSize: 16px
fontWeight: 600
color: #FFFFFF (Ultra White)
```

---

### Header: Title + Close

```
◄ Auralis Enhancement              [x]
^  ^                                ^
Back Btn  Title (Plus Jakarta Sans) Close (icon button)

Back Button:
- Size: 32×32
- Icon: ◄ 16px
- Color: #C1C8EF
- Hover: color #7366F0, background rgba(115, 102, 240, 0.12)

Close Button:
- Size: 32×32
- Icon: × 16px
- Color: #C1C8EF
- Hover: color #EF4444 (error red)
```

---

### Preset Selector (Pill Buttons)

```
┌─────────────────────────────────────────┐
│ [Adaptive ▼]  [Gentle] [Warm] [Bright]  │
│  (Primary)    Secondary buttons          │
└─────────────────────────────────────────┘

Layout:
- Horizontal flex, wrapping allowed
- Gap: 12px
- Padding: 0 20px 20px 20px

Active Preset (Adaptive):
- Background: #7366F0 (Soft Violet)
- Text: #FFFFFF (Ultra White)
- Font: Plus Jakarta Sans 14px / 600
- Icon: ▼ dropdown (12px) on right
- Shadow: 0 4px 12px rgba(115, 102, 240, 0.20)
- Border-radius: md (8px)
- Padding: 10px 16px

Inactive Presets:
- Background: rgba(31, 41, 54, 0.60)
- Text: #C1C8EF (Lavender Smoke)
- Font: Inter 14px / 500
- Border: 1px solid rgba(115, 102, 240, 0.12)
- Hover: background #1B232E, border color increases
- Border-radius: md (8px)
- Padding: 10px 16px

Dropdown Menu (on active preset click):
- Position: below preset button
- Background: #1F2936 + glass effect
- Shadow: 0 8px 24px rgba(0, 0, 0, 0.24)
- Items: "Adaptive", "Gentle", "Warm", "Bright", "Custom"
- Item height: 40px
- Hover item: background rgba(115, 102, 240, 0.12)
```

---

### Spectrum/Waveform Visualizer

```
┌─────────────────────────────────────────┐
│ ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌      │
│ ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▁▂▃▄  │
│                                         │
│ Analyzing 48 kHz | 2.0 dB Gain Reduction│
└─────────────────────────────────────────┘

Container:
- Height: 120px
- Width: 100% - 40px (20px padding left & right)
- Background: linear-gradient(180°, rgba(115, 102, 240, 0.08) 0%, rgba(115, 102, 240, 0.0) 100%)
- Border: 1px solid rgba(115, 102, 240, 0.12)
- Border-radius: md (8px)
- Padding: 16px
- Margin: 0 20px 20px 20px

Spectrum Bars:
- Count: 32 frequency bins (20Hz–20kHz)
- Width: (320px / 32 - gap) = ~8px per bar
- Gap: 1px
- Color (normal): gradient from #7366F0 (bass) → #47D6FF (treble)
- Color (processing): glow effect with aqua
- Height: animates with audio level (0–100px)
- Border-radius: 2px top
- Animation: smooth, 50ms update rate

Peak Meter (Right side, optional):
- Width: 12px
- Height: 100px
- Background: rgba(31, 41, 54, 0.40)
- Track color: gradient #7366F0 → #47D6FF
- Peak indicator: line at current max
- Decay animation: 200ms to bottom

Status Text (Below):
- Font: JetBrains Mono 11px / 500
- Color: #C1C8EF
- Text: "Analyzing 48 kHz | 2.0 dB Gain Reduction"
- Position: center-bottom of container
- Opacity: 0.80
```

---

### Audio Characteristics (Metric Cards)

```
┌──────────────────────────────────────────┐
│ Audio Characteristics:                   │
├──────────────────────────────────────────┤
│ • Loudness:   -14.2 LUFS                │
│ • Dynamics:    4.3 dB (moderate)         │
│ • Frequency:   Neutral (50Hz–5kHz boost)│
│ • Stereo:      100% (mono-compat)        │
└──────────────────────────────────────────┘

Container:
- Padding: 16px 20px
- Background: rgba(31, 41, 54, 0.40)
- Border: 1px solid rgba(115, 102, 240, 0.06)
- Border-radius: md (8px)
- Margin: 0 20px 20px 20px

Label (Section):
- Font: Plus Jakarta Sans 14px / 600
- Color: #FFFFFF
- Margin-bottom: 12px
- Text-transform: none

Metric Item:
- Layout: flex (bullet + label + value)
- Height: 24px
- Font (label): Inter 13px / 400
- Font (value): JetBrains Mono 13px / 500
- Color (label): #C1C8EF
- Color (value): #47D6FF (Electric Aqua)
- Spacing: bullet → label 8px, label → value 8px
- Bullet: • 8px / color same as label

Examples:
• Loudness:       -14.2 LUFS
• Dynamics:       4.3 dB
• Frequency:      Neutral
• Stereo Width:   100%
```

---

### Processing Parameters (Sliders)

```
┌──────────────────────────────────────────┐
│ Processing Parameters:                   │
├──────────────────────────────────────────┤
│ Peak Norm.        -2.0 dB    [─●────────]│
│ EQ Tilt           +0.5 dB    [──●───────]│
│ Compression       2.1:1      [───●──────]│
│ Limiter Threshold -2.0 dB    [────●─────]│
│ Saturation         0.2        [─────●────]│
└──────────────────────────────────────────┘

Container:
- Padding: 16px 20px
- Background: rgba(31, 41, 54, 0.40)
- Border: 1px solid rgba(115, 102, 240, 0.06)
- Border-radius: md (8px)
- Margin: 0 20px 20px 20px

Section Title:
- Font: Plus Jakarta Sans 14px / 600
- Color: #FFFFFF
- Margin-bottom: 16px

Parameter Row:
- Height: 44px (includes spacing)
- Layout: flex (label + slider + value)
- Spacing: between elements 12px
- Align: center (vertical)

Label:
- Font: Inter 13px / 500
- Color: #C1C8EF
- Min-width: 100px (flex-shrink: 0)
- Text-align: left

Slider:
- Height: 4px (track), 16px (thumb)
- Width: 150px (flex: 1)
- Track bg: rgba(115, 102, 240, 0.20)
- Thumb bg: #7366F0
- Thumb hover: #47D6FF, shadow 0 0 16px rgba(71, 214, 255, 0.24)
- Border-radius: full (9999px)
- Cursor: pointer (grab while dragging)
- Transition: all 150ms easeSmooth

Value (Numeric):
- Font: JetBrains Mono 12px / 600
- Color: #47D6FF (Electric Aqua)
- Min-width: 60px (flex-shrink: 0)
- Text-align: right
- Example: "-2.0 dB", "+0.5 dB", "2.1:1"

On Slider Drag:
- Thumb shadow: 0 0 24px rgba(115, 102, 240, 0.32)
- Thumb scale: 1.2
- Value: text color intensifies #FFFFFF
- Row background: rgba(115, 102, 240, 0.08) (subtle highlight)
```

---

### Action Buttons (Footer)

```
┌──────────────────────────────────────────┐
│ [▼ Collapse]  |  [Reset]  |  [Save Preset]│
└──────────────────────────────────────────┘

Layout:
- Flex distributed space-between
- Padding: 20px
- Border-top: 1px solid rgba(115, 102, 240, 0.06)
- Gap: 12px

Collapse Button (Left):
- Type: Secondary button
- Icon: ▼ (16px) + text "Collapse"
- Font: Inter 14px / 500
- Background: rgba(31, 41, 54, 0.40)
- Text color: #C1C8EF
- Hover: background #1B232E, text #7366F0
- Border: 1px solid rgba(115, 102, 240, 0.12)
- Padding: 10px 16px
- Border-radius: md (8px)

Reset Button (Center):
- Type: Secondary button
- Text: "Reset"
- Font: Inter 14px / 500
- Background: rgba(31, 41, 54, 0.40)
- Text color: #C1C8EF
- Hover: background #1B232E, text #F59E0B (warning)
- Border: 1px solid rgba(115, 102, 240, 0.12)
- Padding: 10px 16px
- Border-radius: md (8px)

Save Preset Button (Right):
- Type: Primary button
- Text: "Save Preset"
- Font: Inter 14px / 600
- Background: #7366F0
- Text color: #FFFFFF
- Hover: background #6B5FDD (10% darker)
- Shadow: 0 4px 12px rgba(115, 102, 240, 0.20)
- Padding: 10px 24px
- Border-radius: md (8px)
- Click: Opens "Save Preset" modal
```

**Modal: Save Preset**

```
┌────────────────────────────────┐
│ Save Custom Preset             │
├────────────────────────────────┤
│ Preset Name:                   │
│ [_________________] (input)    │
│                                │
│ [Cancel]  [Save]               │
└────────────────────────────────┘

Background: #1F2936 (surface elevation)
Border: 1px solid rgba(115, 102, 240, 0.12)
Shadow: 0 12px 32px rgba(0, 0, 0, 0.28)
Width: 320px
Border-radius: xl (16px)
```

---

### Collapsed State

When collapsed via the [▼ Collapse] button:

```
┌─────────────────────┐
│ ◄ Enhancement [↑]   │  Height: 60px
│ Adaptive  [▶ Edit]  │
└─────────────────────┘

Layout:
- Title + back button (top)
- Current preset name + edit button (bottom)
- Height: auto, typically 60px

Click anywhere to expand, or [↑] button.
```

---

### Audio-Reactive Animations

**Spectrum bars** pulse and animate with audio input in real-time:

```typescript
// For each frequency bin
frequency_bar_height = smoothedAmplitude * 100px
color = interpolate(#7366F0, #47D6FF, frequency_position / 20kHz)

// On peak: brief glow
if (amplitude > 0.8) {
  boxShadow: 0 0 12px rgba(71, 214, 255, 0.40)
}

// Decay smoothly
decay_rate: 0.95 per frame (60 FPS)
```

**Processing indicator** changes color based on gain reduction:

```
0.0 dB (no change):    #6B7194 (muted)
0–2 dB reduction:      #F59E0B (warning)
2–5 dB reduction:      #F59E0B (caution)
5+ dB reduction:       #EF4444 (alert)
```

---

# PART 3: GLOBAL COMPONENT INTERACTIONS

## 3.1 Hover & Focus States (Universal)

### Hover States

```typescript
// Cards (Album, Track, Item)
opacity: 1.0 (from 0.92 by default)
transform: scale(1.02)
boxShadow: 0 8px 24px rgba(0, 0, 0, 0.24)
backgroundColor: rgba(31, 41, 54, 0.60) (slight tint increase)
transition: all 200ms easeInOut
cursor: pointer

// Buttons
backgroundColor: 10% darker
boxShadow: 0 0 16px rgba(115, 102, 240, 0.20) (for primary)
transform: scale(1.04)
transition: all 100ms easeOut

// Input Fields
borderColor: #7366F0 (from rgba(115, 102, 240, 0.16))
boxShadow: 0 0 12px rgba(115, 102, 240, 0.16)
backgroundColor: rgba(31, 41, 54, 0.80) (slightly lighter)
```

### Focus States (Keyboard Navigation)

```typescript
// Ring (for all interactive elements)
outline: 2px solid #7366F0
outlineOffset: 2px
boxShadow: 0 0 0 4px rgba(115, 102, 240, 0.12)

// Text color boost
color: #FFFFFF (from secondary text colors)

// Transition
transition: all 100ms easeOut
```

---

## 3.2 Loading States

### Skeleton / Shimmer

```
┌──────────────────────┐
│ ░░░░░░░░░░░░░░░░░░ │ ← Loading placeholder
│ ░░░░░░░░░░░░░░░░░░ │
└──────────────────────┘

Color: rgba(31, 41, 54, 0.60) (slightly lighter than bg)
Border-radius: md (8px)
Animation: shimmer left→right (1200ms loop)
  background: linear-gradient(90°,
    rgba(31, 41, 54, 0.60) 0%,
    rgba(71, 214, 255, 0.08) 50%,
    rgba(31, 41, 54, 0.60) 100%)
  background-size: 200% 100%
  animation: shimmer 1.2s ease-in-out infinite
```

### Loading Indicator (Spinner)

```
      ⟳ Loading...

Spinner:
- Size: 24px (can scale)
- Color: #7366F0 (primary accent)
- Animation: rotate 360° over 800ms, linear, infinite
- Glow: 0 0 12px rgba(115, 102, 240, 0.24)

Text:
- Font: Inter 14px / 400
- Color: #C1C8EF
- Position: right of spinner, 8px gap
```

---

## 3.3 Empty States

### Standard Empty State

```
            🎵 (96px, #7366F0 opacity 0.60)

    Your Library is Empty
    (32px, Plus Jakarta Sans, 700, #FFFFFF)

  Drag audio files here or use File → Add Folder
  (14px, Inter, #C1C8EF, centered)

        [Browse Folder] [YouTube Search]
```

---

## 3.4 Toast Notifications

```
┌────────────────────────────────────┐
│ ✓ 47 tracks added to "Workout"    │  ← Toast
└────────────────────────────────────┘

Position: bottom-right, 16px from edges
Background: #10B981 (success) / #EF4444 (error) / #F59E0B (warning)
Text: #FFFFFF (Ultra White)
Font: Inter 14px / 500
Padding: 16px 20px
Border-radius: md (8px)
Shadow: 0 8px 24px rgba(0, 0, 0, 0.28)
Animation: slideUp 300ms easeOut, auto-dismiss after 4 seconds
Z-Index: 1300 (above all)

Icon:
- Size: 20px
- Color: #FFFFFF
- Position: left, 8px margin

Close Button (optional):
- Icon: ×
- Color: #FFFFFF
- Hover: opacity 0.7
```

---

## 3.5 Context Menus

```
┌──────────────────────────┐
│ ► Play                   │
│ + Add to Playlist        │
│ ✎ Edit Metadata         │
│ ★ Add to Library        │
│ ✂ Remove                │
└──────────────────────────┘

Background: #1F2936 + glass effect
Border: 1px solid rgba(115, 102, 240, 0.12)
Shadow: 0 8px 24px rgba(0, 0, 0, 0.24)
Border-radius: md (8px)
Padding: 8px 0

Item:
- Height: 40px
- Padding: 8px 16px
- Font: Inter 14px / 400
- Color: #C1C8EF
- Hover: background rgba(115, 102, 240, 0.12), color #FFFFFF
- Icon: 16px, left-aligned, 8px margin-right

Divider (optional):
- 1px solid rgba(115, 102, 240, 0.06)
- Margin: 4px 0
```

---

## 3.6 Keyboard Shortcuts & Accessibility

### Focus Management

- Tab → Cyclic focus through interactive elements
- Shift+Tab → Reverse focus
- Enter/Space → Activate button
- Escape → Close modal/menu
- Arrow keys → Navigate lists (Up/Down), adjust sliders (Left/Right)

### Screen Reader Announcements

```typescript
// Every interactive element
aria-label: descriptive text
aria-describedby: help text (if complex)

// Live regions
aria-live: polite (for status updates like toast)
aria-busy: true (during loading)

// Semantic HTML
<button>, <input>, <label>, <nav>, <article>, etc.
```

---

# PART 4: IMPLEMENTATION GUIDELINES

## 4.1 Design System Structure (React/Tailwind)

```typescript
// tokens.ts (SINGLE SOURCE OF TRUTH)
export const tokens = {
  colors: { /* all hex values */ },
  spacing: { /* 4px, 8px, 16px... */ },
  typography: { /* font families, sizes */ },
  shadows: { /* elevation shadows + glows */ },
  transitions: { /* easing, duration */ },
  components: { /* player, sidebar, card */ },
}

// primitives/ (reusable components)
Button.tsx       // Primary, secondary, ghost variants
Card.tsx         // Default, elevated, outlined
Input.tsx        // Text, password, number inputs
Slider.tsx       // Audio parameter sliders
Modal.tsx        // Dialogs, modals
Tooltip.tsx      // Hover tooltips

// layouts/ (page-level components)
Sidebar.tsx      // Navigation sidebar
PlayerBar.tsx    // Footer player dock
RightPanel.tsx   // Enhancement/Queue panel

// screens/ (feature pages)
LibraryScreen.tsx        // Album grid + views
PlayerScreen.tsx         // Full-screen player
EnhancementScreen.tsx    // Mastering panel detail view
```

## 4.2 Color Usage Rules (Strict)

- **Never hardcode hex values** in component code
- **Always import `tokens`** from `@/design-system/tokens`
- **Use semantic color names**: `tokens.colors.text.primary`, `tokens.colors.accent.primary`
- **Opacity**: Use `withOpacity()` helper for transparency
- **Gradients**: Reference from `tokens.gradients.aurora`, etc.

Example:
```typescript
// ❌ BAD
<div style={{ color: '#FFFFFF', backgroundColor: '#0D111A' }}>

// ✅ GOOD
import { tokens } from '@/design-system/tokens'
<div style={{ color: tokens.colors.text.primary, backgroundColor: tokens.colors.bg.primary }}>
```

---

## 4.3 Responsive Breakpoints

```typescript
// tailwind.config.js (if using Tailwind)
screens: {
  mobile: '320px',
  sm: '480px',
  md: '768px',
  lg: '1024px',
  xl: '1440px',
  '2xl': '1920px',
}

// Or use CSS media queries
@media (max-width: 1024px) { /* tablet */ }
@media (max-width: 480px) { /* mobile */ }
```

---

## 4.4 Component Composition Pattern

Each screen component should follow this structure:

```typescript
import { tokens } from '@/design-system/tokens'
import { Button, Card, Slider } from '@/design-system/primitives'

const MyScreen: React.FC = () => {
  return (
    <div style={styles.container}>
      {/* Content */}
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colors.bg.primary,
    padding: tokens.spacing.lg,
    // ... other properties
  },
}

export default MyScreen
```

---

## 4.5 Animation Implementation

Use CSS transitions for performance:

```typescript
// Hover state
const styles = {
  card: {
    transition: tokens.transitions.all, // '200ms all ease'
    cursor: 'pointer',
    '&:hover': {
      transform: 'scale(1.02)',
      boxShadow: tokens.shadows.lg,
    },
  },
}

// Keyframe animations (for continuous effects)
const keyframes = `
  @keyframes shimmer {
    0% { background-position: -1000px 0; }
    100% { background-position: 1000px 0; }
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`
```

---

# PART 5: FIGMA TOKENS EXPORT

For seamless Figma integration:

```json
{
  "Color": {
    "Background": {
      "Primary": {"value": "#0D111A"},
      "Secondary": {"value": "#131A24"},
      "Tertiary": {"value": "#1B232E"}
    },
    "Accent": {
      "Primary": {"value": "#7366F0"},
      "Secondary": {"value": "#47D6FF"}
    }
  },
  "Spacing": {
    "xs": {"value": "4px"},
    "sm": {"value": "8px"},
    "md": {"value": "16px"}
  },
  "Typography": {
    "H1": {
      "fontFamily": "Plus Jakarta Sans",
      "fontSize": "32px",
      "fontWeight": "700",
      "lineHeight": "1.3"
    }
  },
  "Shadow": {
    "md": {"value": "0 4px 12px rgba(0, 0, 0, 0.16)"}
  }
}
```

---

# PART 6: DESIGN CHECKLIST (Before Implementation)

- [ ] All color values come from `tokens.colors.*`
- [ ] All spacing uses 8px grid (`tokens.spacing.*`)
- [ ] All typography uses correct font family and size scale
- [ ] All border-radius ≥ lg (12px) for cards
- [ ] All shadows use ambient (no hard black)
- [ ] All buttons have hover/focus states
- [ ] All interactive elements have keyboard support
- [ ] Responsive design tested at 480px, 1024px, 1920px
- [ ] Loading states use shimmer animation
- [ ] Empty states are visually guided
- [ ] Audio-reactive elements use Electric Aqua (#47D6FF) glow
- [ ] Player bar is fixed at bottom, z-index 1030
- [ ] Enhancement panel slides from right, overlay or dock
- [ ] Album covers use xl (16px) radius
- [ ] Modal backdrops darken entire screen with glass effect
- [ ] Notifications use toast (bottom-right)
- [ ] All text is accessible (contrast ratio ≥ 4.5:1)
- [ ] Transitions are smooth (easeOut for 100ms, easeInOut for 200ms)
- [ ] No hardcoded colors in component JSX
- [ ] All spacing consistent with 8px grid

---

**Design System Complete. Ready for implementation across all screens.**

