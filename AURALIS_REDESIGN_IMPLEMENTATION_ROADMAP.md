# Auralis UI Redesign Implementation Roadmap

**Status**: Design Complete, Ready for Development
**Design System**: [AURALIS_DESIGN_SYSTEM_COMPLETE.md](./AURALIS_DESIGN_SYSTEM_COMPLETE.md)
**Target**: Premium audio-focused player interface
**Estimated Effort**: 3–4 weeks (phased implementation)

---

## PHASE 1: DESIGN TOKENS & PRIMITIVES (Week 1)

### 1.1 Update Design Tokens

**File**: `auralis-web/frontend/src/design-system/tokens.ts`

Current state: Using loose color definitions (#0A0E27, #667eea, etc.)

**Required Changes**:
- [ ] Add elevation-based color system (Level 0–4)
- [ ] Update brand colors: Soft Violet (#7366F0), Electric Aqua (#47D6FF)
- [ ] Add semantic colors: Success (#10B981), Warning (#F59E0B), Error (#EF4444)
- [ ] Define all shadow values with proper ambient opacity
- [ ] Add glass effect mixin (rgba bg + backdrop-filter blur)
- [ ] Add glow shadows for audio-reactive elements
- [ ] Ensure all spacing follows 8px grid (no off-grid values)
- [ ] Add component-specific tokens for player bar, sidebar, cards
- [ ] Document all tokens with comments (usage examples)

**Deliverable**: `tokens.ts` updated with 100% coverage of design system spec

---

### 1.2 Audit & Update Primitive Components

**Files to Review**:
- `primitives/Button.tsx` → Add primary/secondary/ghost variants
- `primitives/Card.tsx` → Update shadow, radius, hover states
- `primitives/Input.tsx` → Ensure token compliance
- `primitives/Slider.tsx` → Add audio parameter styling (JetBrains Mono, glow)
- `primitives/Modal.tsx` → Glass effect background
- `primitives/Badge.tsx` → Semantic colors for states
- `primitives/IconButton.tsx` → Circular variants (56×56 for player)

**Audit Checklist**:
- [ ] No hardcoded colors (all from tokens)
- [ ] All hover/focus states defined
- [ ] Border-radius ≥ lg (12px) for containers
- [ ] Shadows use ambient opacity (no harsh black)
- [ ] Transitions smooth (easeOut 100ms, easeInOut 200ms)
- [ ] Keyboard accessible (focus ring, ARIA labels)
- [ ] TypeScript fully typed

**Deliverable**: All primitives updated, tests passing

---

### 1.3 Create New Primitives (If Missing)

**New Components**:
- [ ] `GlassPanel.tsx` → Translucent overlay with backdrop blur
- [ ] `AudioSlider.tsx` → Specialized slider for dB/Hz values (JetBrains Mono display)
- [ ] `PresetButton.tsx` → Pill-shaped preset selector buttons
- [ ] `SpectrumVisualizer.tsx` → Frequency bin visualization (audio-reactive)

---

## PHASE 2: PLAYER BAR DOCK (Week 1–2)

### 2.1 Refactor PlayerBar Component

**File**: `components/player/PlayerBar.tsx`

**Current Issues**:
- Likely using simple flex layout
- May not have glass effect
- Progress bar may be basic

**Required Redesign**:

```typescript
// NEW STRUCTURE
<PlayerBar>
  <LeftSection>          {/* 256px: Cover + Track Info */}
    <AlbumCover />
    <TrackInfo>
      <TrackTitle />
      <ArtistName />
    </TrackInfo>
  </LeftSection>

  <ProgressBar />        {/* Full width, above controls */}

  <CenterSection>        {/* Centered: Play controls */}
    <IconButton icon="prev" />
    <IconButton icon="play" size="large" />
    <IconButton icon="next" />
  </CenterSection>

  <RightSection>         {/* Volume + Settings */}
    <VolumeControl />
    <IconButton icon="settings" />
  </RightSection>
</PlayerBar>
```

**Style Changes**:
- [ ] Background: Glass effect (rgba(13,17,26,0.92) + blur 12px)
- [ ] Border-top: Soft violet hairline
- [ ] Height: 96px (increased from current)
- [ ] Position: Fixed bottom, z-index 1030
- [ ] Shadow: Upward cast (0 -8px 32px)
- [ ] Control buttons: 56×56 circular, centered
- [ ] Progress bar: Full width, expand on hover to 6px

**Deliverable**: PlayerBar matching design spec, all tests passing

---

### 2.2 Refactor PlaybackControls

**File**: `components/player/PlaybackControls.tsx`

- [ ] Circular button shape (56×56, border-radius full)
- [ ] Background: rgba(31,41,54,0.60)
- [ ] Icon: 24px centered
- [ ] Hover: darker background, Electric Aqua glow
- [ ] Active (playing): violet glow, 0 0 24px rgba(115,102,240,0.24)
- [ ] Transition: all 200ms easeInOut

---

### 2.3 Refactor ProgressBar

**File**: `components/player/ProgressBar.tsx`

- [ ] Full-width seekable bar
- [ ] Track height: 4px (expand to 6px on hover)
- [ ] Thumb: 16px circle, white
- [ ] On hover: show time tooltip centered
- [ ] Drag: smooth scrubbing
- [ ] Fill color: gradient Violet → Aqua

---

### 2.4 Refactor VolumeControl

**File**: `components/player/VolumeControl.tsx`

- [ ] Layout: Icon (🔊) + slider (120px) + percentage text
- [ ] Slider thumb: hover glow (Electric Aqua)
- [ ] Typography: JetBrains Mono for percentage
- [ ] Icon button: same 56×56 style as playback controls

---

## PHASE 3: ALBUM GRID & LIBRARY VIEW (Week 2)

### 3.1 Update Album Grid

**File**: `components/library/CozyAlbumGrid.tsx` (or create if doesn't exist)

**Layout**:
- [ ] Responsive columns: 2 (mobile) → 3 (tablet) → 4 (desktop) → 5+ (ultra)
- [ ] Card spacing: 20px horizontal, 24px vertical
- [ ] Album cover: 200×200px, border-radius lg (12px)
- [ ] Hover: scale 1.04, shadow increase, brightness +8%
- [ ] Play button overlay: 56×56 circle, centered, on hover

**Card Structure**:
```
[Album Cover 200×200]
────────────────────
Album Name      (16px / 600 / Plus Jakarta Sans / white)
Artist Name     (13px / 400 / Inter / muted)
2024 • 12 Tracks (11px / 400 / very muted)
```

**Hover State**:
- Cover lifts with shadow and slight brightening
- Play button (▶) fades in at center, 56×56, circular, violet background
- On click play button: bounce animation (scale 0.95 → 1.0)
- Text becomes brighter

**Deliverable**: Updated grid component with all hover states

---

### 3.2 Batch Selection UI

**File**: `components/library/Controls/BatchActionsToolbar.tsx`

- [ ] Checkbox appears in top-left of album card (24×24)
- [ ] Checkbox border: 2px solid #7366F0
- [ ] Selected card: 2px border, glow shadow, slight tint overlay
- [ ] Batch toolbar: sticky top, shows "X selected, [Select All] [Clear]"

---

## PHASE 4: ALBUM DETAIL SCREEN (Week 2–3)

### 4.1 Redesign AlbumDetailView

**File**: `components/library/Details/AlbumDetailView.tsx`

**Layout** (3-column grid):

```
[Left 20%]      [Center 15%]    [Right 65%]
─────────────────────────────────────────
Album Cover     Metadata        Tracklist
320×320         Block           Scrollable
                                Header (sticky)
+ Buttons       Stats, Genres   Rows (48px each)
```

**Left Column**:
- [ ] Album cover: 320×320, shadow, border-radius xl (16px)
- [ ] Play All button: 56×56 circular, violet, centered
- [ ] Favorite button: 40×40 icon
- [ ] More menu button: 40×40 icon

**Center Column**:
- [ ] Album name: 20px / 700 / Plus Jakarta Sans / white
- [ ] Artist name: 16px / 400 / muted
- [ ] Divider: dashed rgba(115,102,240,0.12)
- [ ] Stats: "2024 • 12 Tracks • 123 minutes"
- [ ] Genres: chip badges, inline

**Right Column**:
- [ ] Header row: sticky, slightly raised background
- [ ] Track rows: 48px height, 8px padding
- [ ] Columns: # | Title | Duration | Actions
- [ ] Track title: current track highlighted (violet) with left border (4px)
- [ ] On hover: row background lightens, favorite icon appears
- [ ] Dividers: subtle (1px dashed)

**Deliverable**: AlbumDetailView matching spec

---

## PHASE 5: ARTIST SCREEN (Week 3)

### 5.1 Redesign ArtistDetailView

**File**: `components/library/Details/ArtistDetailView.tsx`

**Header Section**:
- [ ] Title: 48px / 700 / Plus Jakarta Sans / white
- [ ] Stats: "5 Albums • 47 Tracks • 4 Hours 23 Minutes"
- [ ] Background: gradient aurora soft (0.12 opacity)
- [ ] Buttons: Play All, Add to Library (secondary)

**Albums Strip**:
- [ ] Horizontal scroll, 160px card width each
- [ ] Cards: same design as grid (but in a strip)
- [ ] "View All Albums" button on right

**Popular Tracks**:
- [ ] List view, first 5 tracks
- [ ] Table: # | Title | Duration | Plays | Actions
- [ ] Rows: 48px height
- [ ] "Show All (47 tracks)" button centered below

**Deliverable**: ArtistDetailView with all sections

---

## PHASE 6: AUTO-MASTERING PANEL (Week 3–4)

### 6.1 Redesign EnhancementPaneV2

**File**: `components/enhancement-pane-v2/EnhancementPaneV2.tsx`

**Key Changes**:
- [ ] Right-side dock panel (360px width)
- [ ] Glass effect background (rgba + blur)
- [ ] Preset selector: pill buttons (active = violet, inactive = ghost)
- [ ] Spectrum visualizer: 32 bars, color gradient violet→aqua
- [ ] Audio characteristics: metric cards with JetBrains Mono values
- [ ] Processing parameters: sliders with numeric readout
- [ ] Footer buttons: Collapse, Reset, Save Preset

**Spectrum Visualizer**:
- [ ] 120px height
- [ ] 32 frequency bins (20Hz–20kHz)
- [ ] Bar width: ~8px, gap: 1px
- [ ] Color gradient: #7366F0 (bass) → #47D6FF (treble)
- [ ] Height animates with audio input
- [ ] Peak meter on right side (optional)
- [ ] Update rate: 50ms smooth

**Audio Characteristics Cards**:
```
• Loudness:      -14.2 LUFS           (JetBrains Mono)
• Dynamics:      4.3 dB               (JetBrains Mono)
• Frequency:     Neutral (50Hz–5kHz)  (JetBrains Mono)
• Stereo Width:  100%                 (JetBrains Mono)
```

**Parameter Sliders**:
```
[Peak Normalization]    [-2.0 dB]    [────●───────]
[EQ Tilt]              [+0.5 dB]     [─────●──────]
[Compression]          [2.1:1]       [──────●─────]
[Limiter Threshold]    [-2.0 dB]     [───●────────]
```

Each row: label + slider (150px) + value (JetBrains Mono)
Hover: row background highlights, thumb glows

**Deliverable**: EnhancementPaneV2 matching premium plugin aesthetic

---

## PHASE 7: GLOBAL REFINEMENTS (Week 4)

### 7.1 Update All Components for Token Compliance

- [ ] Grep codebase for hardcoded colors (`#` or `rgb`)
- [ ] Replace all with token references
- [ ] Update button variants (primary, secondary, ghost)
- [ ] Ensure all border-radius ≥ lg (12px)
- [ ] Update all shadows (no harsh black)

### 7.2 Responsive Breakpoints

- [ ] Test at 480px, 768px, 1024px, 1440px, 1920px
- [ ] Sidebar: collapse to icon-only at < 1024px
- [ ] Right panel: drawer/modal on < 1024px
- [ ] Album grid: reflow columns appropriately
- [ ] Player bar: adjust spacing for mobile

### 7.3 Accessibility Audit

- [ ] Focus ring visible on all interactive elements
- [ ] Color contrast ≥ 4.5:1 (AA standard)
- [ ] ARIA labels on all buttons, icons
- [ ] Keyboard navigation complete (Tab, Escape, Arrow keys)
- [ ] Screen reader announcements for dynamic content

### 7.4 Animation Performance

- [ ] Use CSS transitions (not JS animations)
- [ ] GPU acceleration: `transform`, `opacity` only
- [ ] Avoid animating `width`, `height`, `background`
- [ ] Test on low-end devices (60 FPS minimum)

### 7.5 Documentation

- [ ] Update design system README
- [ ] Document all component variants
- [ ] Create Figma exports (if applicable)
- [ ] Document color/spacing usage rules

---

## PRIORITY IMPLEMENTATION ORDER

**Critical** (Do First):
1. Update design tokens (foundation)
2. Redesign player bar (most visible)
3. Update album grid (core library experience)

**High** (Do Second):
4. Album detail screen
5. Artist screen
6. Enhancement panel

**Medium** (Follow-up):
7. Global refinements
8. Responsive testing
9. Accessibility audit
10. Performance optimization

---

## SUCCESS CRITERIA

- [ ] All colors from `tokens.colors.*`
- [ ] All spacing multiples of 8px
- [ ] Player bar is premium, sleek, audio-focused
- [ ] Album grid: large covers, soft hover, play button overlay
- [ ] Detail screens: elevation-based hierarchy, no harsh borders
- [ ] Enhancement panel: FabFilter/Ozone aesthetic, real-time visualization
- [ ] Responsive: works at all breakpoints
- [ ] Accessible: keyboard navigation, screen readers, focus rings
- [ ] Performant: smooth 60 FPS animations, no jank
- [ ] Tests: all existing tests pass + new tests added

---

## FILE CHECKLIST

**Core Tokens**:
- [ ] `src/design-system/tokens.ts` (updated)
- [ ] `src/design-system/primitives/*.tsx` (all updated)

**Player Bar**:
- [ ] `src/components/player/PlayerBar.tsx` (refactored)
- [ ] `src/components/player/PlaybackControls.tsx` (refactored)
- [ ] `src/components/player/ProgressBar.tsx` (refactored)
- [ ] `src/components/player/VolumeControl.tsx` (refactored)

**Library**:
- [ ] `src/components/library/CozyAlbumGrid.tsx` (updated)
- [ ] `src/components/library/Details/AlbumDetailView.tsx` (redesigned)
- [ ] `src/components/library/Details/ArtistDetailView.tsx` (redesigned)

**Enhancement**:
- [ ] `src/components/enhancement-pane-v2/EnhancementPaneV2.tsx` (redesigned)
- [ ] `src/components/enhancement-pane-v2/SpectrumVisualizer.tsx` (new or updated)

**Global**:
- [ ] All components audited for token compliance
- [ ] All components tested at breakpoints
- [ ] All components accessible

---

## TESTING STRATEGY

### Visual Regression Testing
```bash
# After each phase, manually test in browser
npm run dev
# Check at: 480px, 768px, 1024px, 1440px, 1920px
```

### Automated Tests
```bash
# Update existing tests for new styles
npm run test:memory

# Type check
npx tsc --noEmit
```

### Accessibility
```bash
# Use browser DevTools (Lighthouse)
# Check: contrast, focus ring, keyboard nav, ARIA
```

---

## HANDOFF TO DEVELOPER

When ready to code, provide:
1. ✅ This implementation roadmap
2. ✅ Complete design system spec (`AURALIS_DESIGN_SYSTEM_COMPLETE.md`)
3. ✅ Component wireframes/ASCII layouts
4. ✅ Figma export (if applicable)
5. ✅ All colors, spacing, typography values

Developer should:
1. Update tokens.ts first (foundation)
2. Follow PHASE sequence
3. Run tests after each phase
4. Reference design system doc frequently
5. Never hardcode colors or spacing

---

**Design System**: Complete ✅
**Implementation Roadmap**: Complete ✅
**Ready for Development**: Yes ✅

