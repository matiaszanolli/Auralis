# Auralis Design System – Quick Reference Card

**Print this. Keep it nearby while designing.**

---

## COLOR PALETTE (Copy-Paste Ready)

### Backgrounds
```
Level 0:  #0A0C10  (root void)
Level 1:  #0D111A  (main background) ← USE THIS MOST
Level 2:  #131A24  (panels, sidebar)
Level 3:  #1B232E  (cards, raised)
Level 4:  #1F2936  (modals, overlays)
```

### Brand Colors
```
Soft Violet:   #7366F0  (primary accent)
Electric Aqua: #47D6FF  (audio-reactive, glows)
Lavender:      #C1C8EF  (secondary text)
Ultra White:   #FFFFFF  (titles)
```

### Semantic
```
Success:  #10B981  Error:  #EF4444
Warning:  #F59E0B  Info:   #3B82F6
```

---

## SPACING (8px Grid)

```
4px  → xs (half-grid, never use for main spacing)
8px  → sm (base unit)
16px → md (MOST COMMON — use this!)
24px → lg (big gaps, section breaks)
32px → xl (extra large breaks)
48px → xxl (heading grouping)
64px → xxxl (page sections)
```

**Rule**: All spacing = multiple of 8px

---

## TYPOGRAPHY

### Fonts
```
Headers:   Plus Jakarta Sans, 600–700 weight
Body:      Inter, 400–500 weight
Technical: JetBrains Mono, 500–600 weight (dB, Hz, LUFS)
```

### Common Sizes
```
Titles (H1):      32px / 700 / Plus Jakarta Sans
Headers (H2/H3):  24px / 700 or 20px / 600
Body Text:        14px / 400 / Inter
Small Label:      12px / 500 / Inter
Caption:          11px / 400 / Inter
Technical:        13px / 600 / JetBrains Mono
```

---

## BORDER RADIUS

```
No radius:   0
Micro:       2px
Small:       4px
Standard:    8px (buttons, inputs)
Cards:       12px (default minimum!)
Large:       16px (album covers)
Extra:       20px (hero sections)
Circle:      9999px (buttons, avatars)
```

**Rule**: Never use < 12px for cards!

---

## SHADOWS (No Harsh Black!)

### Elevation Shadows
```
Card (subtle):   0 4px 12px rgba(0,0,0,0.16)
Panel (raised):  0 8px 24px rgba(0,0,0,0.20)
Modal (float):   0 12px 32px rgba(0,0,0,0.28)
Top-level:       0 16px 40px rgba(0,0,0,0.32)
```

### Glow Shadows (Audio-Reactive)
```
Soft Violet:     0 0 16px rgba(115,102,240,0.20)
Violet Med:      0 0 24px rgba(115,102,240,0.32)
Aqua:            0 0 20px rgba(71,214,255,0.24)
Aqua Intense:    0 0 32px rgba(71,214,255,0.40)
```

---

## TRANSITIONS

```
Fast:  100ms (hover states)
Base:  200ms (color, scale, opacity) ← MOST COMMON
Slow:  300ms (layout shifts)
Extra: 500ms (modals, major changes)

Easing:
  easeOut:   cubic-bezier(0.4, 0, 0.2, 1)   [quick]
  easeInOut: cubic-bezier(0.4, 0, 0.6, 1)   [natural]
  easeSmooth: cubic-bezier(0.25, 0.46, 0.45, 0.94) [audio]
```

---

## COMPONENT QUICK SPECS

### Primary Button
```
Size:       12px × 24px padding
Font:       14px / 600 / Inter
Radius:     8px
Background: #7366F0 (Soft Violet)
Text:       #FFFFFF (Ultra White)
Shadow:     0 4px 12px rgba(115,102,240,0.20)
Hover:      darker + glow
```

### Secondary Button
```
Size:       12px × 24px padding
Font:       14px / 500 / Inter
Radius:     8px
Background: transparent
Border:     1px solid rgba(115,102,240,0.24)
Text:       #C1C8EF
Hover:      bg tint + border brightens
```

### Icon Button (56×56, Circular)
```
Size:       56×56 (fixed)
Radius:     9999px (circle)
Background: rgba(31,41,54,0.60)
Icon Size:  24px
Icon Color: #C1C8EF
Hover:      darker background + #47D6FF glow
```

### Card
```
Radius:      12px (minimum!)
Background:  #1B232E
Shadow:      0 4px 12px rgba(0,0,0,0.16)
Padding:     16px
Hover:       scale 1.02 + shadow lift
Transition:  all 200ms easeInOut
```

### Input
```
Radius:    8px
Background: rgba(31,41,54,0.60)
Border:    1px solid rgba(115,102,240,0.16)
Padding:   12px × 16px (vert × horiz)
Focus:     border #7366F0 + glow shadow
```

### Slider (Audio Parameter)
```
Track Height:  4px (6px on hover)
Track Color:   rgba(115,102,240,0.20)
Thumb Size:    16px circle
Thumb Color:   #7366F0
Hover:         #47D6FF + 0 0 16px glow
```

---

## HOVER STATES (Universal)

```
Scale:       1.02–1.04
Shadow:      increase by 1 level (card → raised)
Opacity:     1.0 (from 0.92)
Color:       brighten 10% or shift accent
Background:  if ghost button, add tint rgba(115,102,240,0.12)
Transition:  all 200ms easeOut
Cursor:      pointer
```

---

## FOCUS STATES (Keyboard)

```
Ring:         2px solid #7366F0
Ring-Offset:  2px
Shadow:       0 0 0 4px rgba(115,102,240,0.12)
Color:        brighten (if text color)
Transition:   all 100ms easeOut
```

---

## GLASS EFFECT (Translucent Overlays)

```
background:     rgba(19, 26, 36, 0.80)
backdrop-filter: blur(8px–12px)
border:         1px solid rgba(115,102,240,0.12)
shadow:         0 8px 24px rgba(0,0,0,0.24)
```

Used for:
- Player bar background
- Floating panels
- Modal overlays
- Context menus

---

## Z-INDEX SCALE

```
0:    base (content)
10:   interactive (buttons, inputs)
1000: dropdown menus
1020: sticky headers
1030: fixed panels (player bar, sidebar)
1040: modal backdrop
1050: modal dialog
1060: popovers, context menu
1070: tooltips
1300: notifications/toasts (highest)
```

---

## BREAKPOINTS (Responsive)

```
Mobile:   < 480px   (single column)
Tablet:   480–1024px (2 columns, sidebar icon-only)
Desktop:  1024–1440px (full layout, sidebars visible)
Ultra:    > 1440px  (maximum content)
```

**Album Grid Columns**:
- Mobile: 2 columns
- Tablet: 3 columns
- Desktop: 4 columns
- Ultra: 5–6 columns

---

## DO'S & DON'TS

### DO ✅
- Use colors from the palette (copy-paste hex)
- Space in 8px increments
- Border-radius ≥ 12px on containers
- Use soft shadows (ambient opacity)
- Transition all changes (100–300ms)
- Use Plus Jakarta Sans for headers
- Use Inter for body text
- Use JetBrains Mono for numbers
- Test hover and focus states
- Keyboard accessibility

### DON'T ❌
- Hardcode colors (always reference palette)
- Use border colors instead of shadows for elevation
- Mix fonts (stick to the 3)
- Add harsh black shadows
- Use instant transitions (feels snappy)
- Make interactive elements < 44px (mobile)
- Forget focus ring for keyboard nav
- Use only color to convey meaning (add icon/text)
- Animate position/width (animate transform/opacity)
- Forget to test at all breakpoints

---

## QUICK COLOR COMBOS

### Primary Action
```
Background: #7366F0 (Soft Violet)
Text:       #FFFFFF (Ultra White)
Hover:      Darker violet + glow shadow
```

### Secondary Action
```
Background: transparent
Border:     1px solid rgba(115,102,240,0.24)
Text:       #C1C8EF (Lavender)
Hover:      rgba(115,102,240,0.12) tint
```

### Card Background
```
Background: #1B232E (Dark Layer)
Text:       #FFFFFF + #C1C8EF
Shadow:     0 4px 12px rgba(0,0,0,0.16)
Hover:      Shadow to 0 8px 24px
```

### Disabled State
```
Opacity:    50%
Color:      #6B7194 (Muted)
Cursor:     not-allowed
```

---

## FIGMA TOKENS QUICK ACCESS

Open Figma > Plugins > Tokens Studio and import:
- `FIGMA_TOKENS_EXPORT.json` (in root)

All tokens ready to use in Figma!

---

## AUDIO-REACTIVE ELEMENTS

When something responds to audio (spectrum, meters, glows):

```
Color:      Electric Aqua (#47D6FF)
Glow:       0 0 20px rgba(71,214,255,0.24)
Update:     50ms (smooth animation)
Decay:      0.95 per frame (smooth fade)
Intensity:  scale with audio level
```

---

## PLAYER BAR QUICK SPEC

```
Height:      96px (fixed)
Position:    bottom, fixed
Background:  glass effect (rgba + blur 12px)
Border-top:  1px solid rgba(115,102,240,0.12)
Shadow:      0 -8px 32px rgba(0,0,0,0.24) (upward cast)
Z-Index:     1030

Layout:
[Cover] [Info] [Progress] [Controls] [Volume]
 256px  flex   full-width  center     120px
```

---

## SPECTRUM VISUALIZER QUICK SPEC

```
Height:        120px
Bars:          32 (frequency bins)
Bar Width:     ~8px each
Bar Color:     gradient #7366F0 → #47D6FF
Bar Animation: height animates with audio
Update Rate:   50ms (smooth)
Peak Meter:    optional on right (12px wide)
```

---

## ALBUM COVER HOVER

```
Cover Scale:      1.04
Shadow:           increase 1 level
Brightness:       +8% (subtle!)
Play Button:      fade in (56×56 circle, violet)
Text:             opacity increases
Border:           optional soft glow
Transition:       all 200ms easeInOut
```

---

## EMPTY STATE TEMPLATE

```
┌─────────────────────────────┐
│                             │
│       🎵 (icon 96px)       │
│    Your Library is Empty    │
│    (32px / 700 / white)     │
│                             │
│  Drag files or use + button │
│  (14px / 400 / muted)       │
│                             │
│   [Browse Folder] [Search]  │
│                             │
└─────────────────────────────┘
```

---

## COMMON PADDING COMBOS

```
Button:        12px (vert) × 24px (horiz)
Card:          16px (all sides)
Panel/Section: 20px (top/bottom), 24px (left/right)
Page Margin:   24px (all sides)
Compact:       8px (all sides)
Spacious:      32px (all sides)
```

---

## TEXT COLOR HIERARCHY

```
Titles/Primary:  #FFFFFF (Ultra White)
Body/Secondary:  #C1C8EF (Lavender)
Tertiary/Hint:   #8B92B0 or #6B7194 (muted)
Disabled:        #4A5073 (very muted)

Interactive:
- Normal:        #C1C8EF
- Hover:         #FFFFFF
- Active:        #7366F0
```

---

## ANIMATION CHECKLIST

Before shipping, ensure:
- [ ] All transitions smooth (100–300ms)
- [ ] Hover states defined on all interactive elements
- [ ] Focus rings visible and clear
- [ ] Loading states use shimmer (not spinner)
- [ ] Dismissals/exits animate out
- [ ] Audio-reactive elements use smooth easing
- [ ] No jarring instant changes (except modals)
- [ ] 60 FPS on low-end devices (use `transform` + `opacity` only)

---

**Bookmark this page. Reference before every design session.**

*Last Updated: December 2025*
*Design System Version: 1.0*

