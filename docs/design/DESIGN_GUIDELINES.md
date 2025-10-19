# Auralis Design Guidelines

**Version:** 1.1
**Last Updated:** October 14, 2025
**Status:** Official Brand Standards

---

## 🎨 Brand Kit Overview

Auralis embodies the **visual beauty of the aurora borealis** - flowing, energetic, and mesmerizing. Our design language reflects this through fluid gradients, dark backgrounds, and glowing accents.

**Core Philosophy:** *Flowing, Creative, Precise, Energetic, Accessible*

---

## 🖥️ UI Design Philosophy

### 1. Core Philosophy

**"Comfortable First"**
- Familiar, uncluttered layout inspired by Rhythmbox (library + player controls at bottom)
- Prioritize ease of use and instant familiarity over feature discoverability
- Follow established music player conventions (Spotify, Apple Music patterns)

**"Invisible Mastering"**
- Mastering runs automatically in the background
- Small, subtle control area for presets (dropdown or simple slider)
- Never interrupts the listening experience
- Defaults to ON, requires zero configuration

**"Focus on Playback"**
- Album art, track info, and playlist/library management take center stage
- Player controls are always visible and accessible
- Quick access to essential functions (play, skip, volume)

### 2. Layout Structure

#### Left Sidebar
- **Library** (Artists, Albums, Songs)
- **Playlists** (simple drag-and-drop, like Spotify's left column)
- **Favourites** / Recently Played
- **Width:** 200-250px
- **Collapsible:** Optional for more screen space

#### Main View
- **Album grid** or **tracklist** depending on selection
- **Smooth transitions** (not flashy, just modern)
- **Search bar** at the top (search across artists/albums/songs)
- **Responsive grid:** Adapts to screen width (2-6 columns)

#### Bottom Player Bar
- **Fixed position** at bottom of screen
- **Controls:** Play/Pause, Previous, Next
- **Seekbar** with aurora gradient highlight when playing
- **Volume slider** (right side)
- **Mini visualizer bar** (subtle aurora glow, optional)
- **Now Playing** area shows album art + waveform progress
- **Height:** 80-100px

#### Right Preset Pane (Optional)
- **"Remastering" label** with dropdown for presets:
  - Studio (default)
  - Vinyl
  - Live
  - Custom
- **Toggle:** ON/OFF (defaults ON)
- **Tucked away,** not intrusive
- **Width:** 200-250px when visible
- **Collapsible:** Can be hidden completely

### 3. Styling Guidelines

#### Color Scheme
- **Background:** Deep navy (#0F172A / Midnight Blue)
- **Active Elements:** Aurora gradient (#06B6D4 → #7C3AED → #F472B6)
- **Text:** Off-white (#E2E8F0 / Silver)
- **Secondary text:** Silver with 0.7 opacity
- **Borders:** Silver with 0.1 opacity

#### Typography
- **Lists/Body:** Inter Regular
- **Headers/Titles:** Montserrat SemiBold
- **Sizes:**
  - H1: 24px (Montserrat SemiBold)
  - H2: 20px (Montserrat SemiBold)
  - Body: 14px (Inter Regular)
  - Caption: 12px (Inter Regular)

#### Iconography
- **Style:** Line icons (outline style, not filled)
- **Corners:** Rounded (Spotify-like softness)
- **Color:** Silver (#E2E8F0), Aurora gradient for active states
- **Size:** 20-24px for standard icons, 32-40px for primary actions

#### Spacing
- **Base unit:** 8px (4px grid system)
- **Component padding:** 16px (2 units)
- **Section spacing:** 24px (3 units)
- **Page margins:** 32px (4 units)

### 4. Key Comfort Features

#### Drag-and-Drop
- **Playlists:** Drag tracks to playlists (like Spotify)
- **Reordering:** Drag to reorder tracks within playlists
- **Visual feedback:** Ghost image while dragging, drop zone highlights

#### Search
- **Position:** Top of main view, always visible
- **Scope:** Search across artists/albums/songs simultaneously
- **Live results:** Updates as you type
- **Keyboard shortcut:** Cmd/Ctrl + F

#### Now Playing
- **Album art:** Large, prominent display
- **Waveform progress:** Aurora gradient seekbar with waveform visualization
- **Track info:** Title, artist, album clearly visible
- **Quick actions:** Love/favorite, add to playlist

#### Settings
- **Access:** Hidden under gear icon (⚙️)
- **Philosophy:** "No configuration needed" is main promise
- **Advanced only:** Only expose settings for power users
- **Location:** Top-right corner or bottom-right of player bar

### 5. Component Patterns

#### Cards
- **Background:** Charcoal (#1E293B)
- **Border:** 1px solid rgba(226, 232, 240, 0.1)
- **Radius:** 12px (--radius-lg)
- **Padding:** 16px
- **Hover:** Subtle lift (transform: translateY(-2px))

#### Buttons
- **Primary:** Aurora gradient background
- **Secondary:** Transparent with Silver border
- **Ghost:** No background, Silver text
- **Hover:** Scale(1.05) + glow effect
- **Active:** Aurora glow (--glow-medium)

#### Lists
- **Row height:** 48px minimum
- **Hover:** Charcoal background
- **Selected:** Aurora gradient left border (4px)
- **Dividers:** Silver 0.1 opacity

#### Progress Bars
- **Track:** Silver 0.2 opacity
- **Fill:** Aurora horizontal gradient
- **Thumb:** Aurora Violet with glow on hover
- **Height:** 4px (standard), 8px (player seekbar)

---

## 1. Logo Usage

### Primary Logo
**Components:** Aurora waveform symbol + wordmark "Auralis"
- **Symbol:** Gradient aurora waveform
- **Wordmark:** White text (Montserrat SemiBold)
- **Usage:** Marketing, splash screens, about pages

### Icon / App Badge
**Format:** Circular aurora waveform symbol (no text)
- **Usage:** App icons, favicons, small contexts
- **Sizes:** 16×16, 32×32, 64×64, 128×128, 256×256, 512×512, 1024×1024

### Monochrome Variant
**Dark Mode:** Solid white on dark background
**Light Mode:** Solid black on light background
**Usage:** Print, single-color contexts

### Spacing Rule
**Minimum Clear Space:** Half the logo's height as padding on all sides

```
┌──────────────────────┐
│     (0.5h padding)   │
│  ┌──────────────┐    │
│  │   AURALIS    │ h  │
│  └──────────────┘    │
│     (0.5h padding)   │
└──────────────────────┘
```

### Don'ts
- ❌ Don't rotate or skew the logo
- ❌ Don't change the gradient colors
- ❌ Don't add drop shadows or effects
- ❌ Don't place on busy backgrounds without proper spacing
- ❌ Don't use outdated versions

---

## 2. Color Palette

### Core Colors

#### Midnight Blue (Primary Background)
- **Hex:** `#0F172A`
- **RGB:** `rgb(15, 23, 42)`
- **Usage:** Main backgrounds, cards, panels
- **Accessibility:** WCAG AAA with white text

#### Aurora Gradient (Brand Identity)
**Cyan → Violet → Pink**

**Cyan:**
- **Hex:** `#06B6D4`
- **RGB:** `rgb(6, 182, 212)`
- **Usage:** Gradient start, interactive elements

**Violet:**
- **Hex:** `#7C3AED`
- **RGB:** `rgb(124, 58, 237)`
- **Usage:** Gradient middle, primary actions

**Pink:**
- **Hex:** `#F472B6`
- **RGB:** `rgb(244, 114, 182)`
- **Usage:** Gradient end, highlights

**CSS Gradient:**
```css
background: linear-gradient(135deg, #06B6D4 0%, #7C3AED 50%, #F472B6 100%);
```

**Gradient Variations:**
```css
/* Horizontal */
background: linear-gradient(90deg, #06B6D4, #7C3AED, #F472B6);

/* Vertical */
background: linear-gradient(180deg, #06B6D4, #7C3AED, #F472B6);

/* Diagonal (45deg) */
background: linear-gradient(45deg, #06B6D4, #7C3AED, #F472B6);

/* Radial */
background: radial-gradient(circle, #06B6D4 0%, #7C3AED 50%, #F472B6 100%);
```

### Supporting Neutrals

#### Silver (Light Text / Borders)
- **Hex:** `#E2E8F0`
- **RGB:** `rgb(226, 232, 240)`
- **Usage:** Secondary text, dividers, borders
- **Opacity Variants:** 90%, 70%, 50%, 30%

#### Charcoal (Secondary Background)
- **Hex:** `#1E293B`
- **RGB:** `rgb(30, 41, 59)`
- **Usage:** Elevated cards, hover states, secondary panels

### Semantic Colors

#### Success (Green Aurora)
- **Hex:** `#10B981`
- **RGB:** `rgb(16, 185, 129)`
- **Usage:** Success states, connected status, completed actions

#### Warning (Amber Aurora)
- **Hex:** `#F59E0B`
- **RGB:** `rgb(245, 158, 11)`
- **Usage:** Warnings, connecting status, pending states

#### Error (Red Aurora)
- **Hex:** `#EF4444`
- **RGB:** `rgb(239, 68, 68)`
- **Usage:** Errors, disconnected status, failed actions

### Color Usage Guidelines

**Text on Midnight Blue:**
- Primary text: White (#FFFFFF) or Silver (#E2E8F0)
- Secondary text: Silver at 70% opacity
- Disabled text: Silver at 50% opacity

**Interactive Elements:**
- Default: Charcoal background, Silver text
- Hover: Aurora gradient, White text
- Active: Aurora gradient (brighter), White text
- Disabled: Charcoal at 50%, Silver at 30%

**Backgrounds Hierarchy:**
1. **Page background:** Midnight Blue
2. **Cards/panels:** Charcoal
3. **Elevated elements:** Charcoal + subtle aurora glow
4. **Active elements:** Aurora gradient

---

## 3. Typography

### Primary Typefaces

#### Montserrat SemiBold
**Usage:** Wordmark, titles, headings, buttons
- **Weight:** 600 (SemiBold)
- **Characteristics:** Geometric, clean, friendly, modern
- **License:** Open Font License
- **Google Fonts:** `https://fonts.googleapis.com/css2?family=Montserrat:wght@600&display=swap`

**Sizes:**
- H1 (Hero): 48px / 3rem
- H2 (Section): 36px / 2.25rem
- H3 (Card Title): 24px / 1.5rem
- H4 (Label): 18px / 1.125rem
- Button: 16px / 1rem

#### Inter Regular
**Usage:** Body text, UI text, metadata, menus, captions
- **Weight:** 400 (Regular), 500 (Medium for emphasis)
- **Characteristics:** Highly legible, optimized for screens
- **License:** Open Font License
- **Google Fonts:** `https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap`

**Sizes:**
- Body Large: 16px / 1rem
- Body Regular: 14px / 0.875rem
- Body Small: 12px / 0.75rem
- Caption: 11px / 0.6875rem

#### Inter Mono / JetBrains Mono (Optional)
**Usage:** Technical values, EQ readouts, dB levels, Hz frequencies
- **Weight:** 400 (Regular)
- **Characteristics:** Monospaced, tabular alignment
- **Usage:** When precision alignment matters

**Sizes:**
- Technical values: 14px / 0.875rem
- Metadata: 12px / 0.75rem

### Typography Scale

```css
/* Headings - Montserrat SemiBold */
h1 { font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 3rem; }
h2 { font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 2.25rem; }
h3 { font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 1.5rem; }
h4 { font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 1.125rem; }

/* Body - Inter Regular */
body { font-family: 'Inter', sans-serif; font-weight: 400; font-size: 1rem; }
.text-large { font-size: 1rem; }
.text-regular { font-size: 0.875rem; }
.text-small { font-size: 0.75rem; }
.caption { font-size: 0.6875rem; font-weight: 400; opacity: 0.7; }

/* Technical - Inter Mono */
.mono { font-family: 'Inter', monospace; font-size: 0.875rem; }
```

### Line Heights
- **Headings:** 1.2 (tight, impactful)
- **Body text:** 1.5 (readable)
- **Captions:** 1.4 (compact)

### Letter Spacing
- **Headings:** -0.02em (slightly tighter)
- **Body:** 0 (default)
- **All caps:** 0.05em (slightly looser)
- **Mono:** 0 (default for alignment)

---

## 4. Graphic Motifs

### Aurora Waves
**Description:** Flowing gradient ribbons as separators or backgrounds

**Usage:**
- Section dividers
- Background elements
- Hero sections
- Loading states

**Implementation:**
```css
.aurora-wave {
  background: linear-gradient(90deg, #06B6D4, #7C3AED, #F472B6);
  height: 2px;
  opacity: 0.5;
  border-radius: 1px;
}

.aurora-wave-animated {
  background: linear-gradient(90deg, #06B6D4, #7C3AED, #F472B6);
  background-size: 200% 100%;
  animation: aurora-flow 3s ease infinite;
}

@keyframes aurora-flow {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
```

### Circular Energy
**Description:** Arcs around buttons to emphasize sound/light connection

**Usage:**
- Play/pause button halos
- Active state indicators
- Loading spinners
- Volume knobs

**Implementation:**
```css
.circular-energy {
  position: relative;
  border-radius: 50%;
}

.circular-energy::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  padding: 2px;
  background: linear-gradient(135deg, #06B6D4, #7C3AED, #F472B6);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
}
```

### Spectrum Glow
**Description:** Aurora gradient applied to waveform visualizers

**Usage:**
- Audio waveforms
- Spectrum analyzers
- Progress bars
- Equalizer bars

**Implementation:**
```css
.spectrum-glow {
  background: linear-gradient(180deg, #06B6D4, #7C3AED, #F472B6);
  box-shadow: 0 0 20px rgba(124, 58, 237, 0.5);
  filter: blur(0.5px); /* Subtle glow */
}

.spectrum-bar {
  background: linear-gradient(to top, #06B6D4, #7C3AED, #F472B6);
  box-shadow: 0 0 10px currentColor;
}
```

---

## 5. UI Guidelines

### Dark Mode First
**Philosophy:** All interfaces default to dark backgrounds with aurora accents

**Background Hierarchy:**
1. **Page:** Midnight Blue (#0F172A)
2. **Cards:** Charcoal (#1E293B)
3. **Elevated:** Charcoal + subtle glow
4. **Modals:** Charcoal with backdrop blur

**Why Dark First:**
- Reduces eye strain during long listening sessions
- Emphasizes aurora gradient accents
- Modern, premium aesthetic
- Better for OLED displays

### Highlight States

**Active EQ Bands:**
```css
.eq-band.active {
  background: linear-gradient(135deg, #06B6D4, #7C3AED);
  box-shadow: 0 0 20px rgba(124, 58, 237, 0.6);
}
```

**Spectrum Analyzers:**
```css
.spectrum-analyzer {
  background: linear-gradient(to top, #06B6D4 0%, #7C3AED 50%, #F472B6 100%);
}
```

**Progress Bars:**
```css
.progress-bar {
  background: linear-gradient(90deg, #06B6D4, #7C3AED);
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
}
```

**Glow Intensity:**
- Idle: No glow
- Hover: Subtle glow (10px blur, 30% opacity)
- Active: Medium glow (20px blur, 60% opacity)
- Focus: Strong glow (30px blur, 80% opacity)

### Minimal Chrome
**Philosophy:** Flat, precise controls with glowing accents - no skeuomorphism

**Avoid:**
- ❌ Fake 3D effects
- ❌ Embossed textures
- ❌ Realistic shadows (use glow instead)
- ❌ Gradients on backgrounds (only on accents)

**Embrace:**
- ✅ Flat colors
- ✅ Clear typography
- ✅ Aurora gradient accents
- ✅ Subtle glows for depth
- ✅ Crisp borders

**Button Style:**
```css
.button {
  background: #1E293B; /* Charcoal */
  border: 1px solid rgba(226, 232, 240, 0.1);
  border-radius: 8px;
  padding: 12px 24px;
  color: #E2E8F0;
  font-family: 'Montserrat', sans-serif;
  font-weight: 600;
  transition: all 0.2s ease;
}

.button:hover {
  background: linear-gradient(135deg, #06B6D4, #7C3AED);
  border-color: transparent;
  color: #FFFFFF;
  box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
}

.button:active {
  transform: scale(0.98);
}
```

### Spacing System
**Based on 4px grid**

```
4px   = 0.25rem = xs
8px   = 0.5rem  = sm
12px  = 0.75rem = md
16px  = 1rem    = base
24px  = 1.5rem  = lg
32px  = 2rem    = xl
48px  = 3rem    = 2xl
64px  = 4rem    = 3xl
```

**Usage:**
- Component padding: 16px (base)
- Card padding: 24px (lg)
- Section spacing: 48px (2xl)
- Element gaps: 8px (sm) or 12px (md)

### Border Radius
```
2px   = Subtle (dividers)
4px   = Small (badges, chips)
8px   = Medium (buttons, inputs)
12px  = Large (cards)
50%   = Circle (avatars, icons)
```

### Shadows & Glows

**Elevation (subtle):**
```css
.elevation-1 { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); }
.elevation-2 { box-shadow: 0 4px 6px rgba(0, 0, 0, 0.4); }
.elevation-3 { box-shadow: 0 10px 15px rgba(0, 0, 0, 0.5); }
```

**Aurora Glow:**
```css
.glow-subtle { box-shadow: 0 0 10px rgba(124, 58, 237, 0.3); }
.glow-medium { box-shadow: 0 0 20px rgba(124, 58, 237, 0.5); }
.glow-strong { box-shadow: 0 0 30px rgba(124, 58, 237, 0.7); }
```

---

## 6. Voice & Tone

### Brand Keywords
- **Flowing:** Smooth transitions, fluid animations
- **Creative:** Inspires musical expression
- **Precise:** Accurate, professional tools
- **Energetic:** Vibrant, alive, dynamic
- **Accessible:** Easy to use, welcoming

### Messaging Style

**Confident but Not Corporate:**
- ✅ "Rediscover the magic in your music"
- ❌ "Enterprise-grade audio processing solutions"

**Musician-Friendly:**
- ✅ "Magic enhancement toggle"
- ❌ "Adaptive psychoacoustic mastering engine"

**Modern and Approachable:**
- ✅ "Your music player with magical audio enhancement"
- ❌ "Professional audio workstation for mastering engineers"

### Writing Guidelines

**Headlines:**
- Short and punchy
- Use Montserrat SemiBold
- Focus on benefits, not features

**Body Copy:**
- Clear and concise
- Use Inter Regular
- Friendly, conversational tone
- Technical when necessary, simple when possible

**Buttons:**
- Action-oriented verbs
- 1-2 words max
- Examples: "Scan Folder", "Play", "Magic On"

**Error Messages:**
- Helpful, not accusatory
- Suggest solutions
- Example: "✅ Scan complete! Added 42 tracks" not "Operation successful"

---

## 7. Component Patterns

### Cards
```css
.card {
  background: #1E293B;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid rgba(226, 232, 240, 0.1);
}

.card:hover {
  border-color: rgba(124, 58, 237, 0.3);
  box-shadow: 0 0 20px rgba(124, 58, 237, 0.2);
}
```

### Inputs
```css
.input {
  background: #0F172A;
  border: 1px solid rgba(226, 232, 240, 0.2);
  border-radius: 8px;
  padding: 12px 16px;
  color: #E2E8F0;
  font-family: 'Inter', sans-serif;
}

.input:focus {
  border-color: #7C3AED;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2);
  outline: none;
}
```

### Toggles / Switches
```css
.toggle.active {
  background: linear-gradient(90deg, #06B6D4, #7C3AED);
  box-shadow: 0 0 10px rgba(124, 58, 237, 0.5);
}
```

---

## 8. Animation Guidelines

### Timing
- **Fast:** 150ms (micro-interactions)
- **Normal:** 200ms (hover states)
- **Slow:** 300ms (page transitions)
- **Animated:** 2-3s (aurora flows)

### Easing
- **Ease-out:** Transitions in
- **Ease-in:** Transitions out
- **Ease-in-out:** Smooth both ways

### Aurora Flow Animation
```css
@keyframes aurora-flow {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.aurora-animated {
  background-size: 200% 200%;
  animation: aurora-flow 3s ease-in-out infinite;
}
```

---

## 9. Accessibility

### Contrast Ratios (WCAG AA minimum)
- **Large text (18px+):** 3:1
- **Normal text:** 4.5:1
- **UI components:** 3:1

**Our Palette:**
- White on Midnight Blue: 15.3:1 ✅ (WCAG AAA)
- Silver on Midnight Blue: 11.2:1 ✅ (WCAG AAA)
- Aurora gradient on Midnight Blue: 4.8:1+ ✅ (WCAG AA)

### Focus Indicators
Always provide visible focus for keyboard navigation:
```css
*:focus-visible {
  outline: 2px solid #7C3AED;
  outline-offset: 2px;
}
```

### Motion
Respect `prefers-reduced-motion`:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 10. Implementation Checklist

### Setting Up Brand Kit

- [ ] Install fonts (Montserrat, Inter)
- [ ] Create color variables
- [ ] Set up aurora gradient classes
- [ ] Configure spacing system
- [ ] Implement component patterns
- [ ] Add animation utilities
- [ ] Test accessibility compliance
- [ ] Document custom components

### Quality Checks

- [ ] All text uses Montserrat or Inter
- [ ] Aurora gradient used consistently
- [ ] Midnight Blue as primary background
- [ ] Contrast ratios meet WCAG AA
- [ ] Focus indicators visible
- [ ] Animations respect reduced motion
- [ ] Logo spacing maintained
- [ ] Voice & tone consistent

---

## 11. Resources

### Font Downloads
- **Montserrat:** https://fonts.google.com/specimen/Montserrat
- **Inter:** https://fonts.google.com/specimen/Inter
- **JetBrains Mono:** https://www.jetbrains.com/lp/mono/

### Color Tools
- **Contrast Checker:** https://webaim.org/resources/contrastchecker/
- **Gradient Generator:** https://cssgradient.io/

### Design Files
- Logo assets: `/assets/logo/`
- Icon library: `/assets/icons/`
- Brand kit download: [Download link]

---

## 12. Version History

### v1.0 - October 14, 2025
- Initial brand guidelines
- Established aurora color palette
- Defined typography system
- Created UI component patterns
- Documented voice & tone

---

**Questions or feedback?** Contact the design team.

**🎨 Keep Auralis beautiful, flowing, and energetic.**
