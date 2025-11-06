# UI Design Guidelines - Auralis

**Version**: 1.0
**Status**: 🎯 **ACTIVE** (Mandatory for all UI development)
**Last Updated**: November 6, 2025

---

## Purpose

This document establishes **strict rules and guidelines** for UI development in Auralis to prevent:
- Component bloat and duplication
- Inconsistent design patterns
- Technical debt accumulation
- "Bootstrap clone" feel

**These are not suggestions - they are requirements.**

---

## Core Principles

### 1. Less is More
- **Default to NO** when adding new components
- Ask: "Can I use/extend an existing component?" before creating new ones
- Every new component must justify its existence

### 2. Consistency Over Novelty
- Use established patterns, not experimental ideas
- Don't create "Enhanced", "Magic", "Professional" variants
- One component per purpose, refined over time

### 3. Design System First
- All UI must use design system tokens (colors, spacing, typography)
- No hardcoded values in components
- No inline styles for design decisions

### 4. Performance Budget
- Every component must be performant
- No unnecessary re-renders
- Virtual scrolling for long lists
- Code splitting for heavy components

---

## Component Creation Rules

### Rule 1: The "One Component" Rule
**Only one component per logical purpose.**

❌ **WRONG**:
```
AudioPlayer.tsx
EnhancedAudioPlayer.tsx
MagicalMusicPlayer.tsx
ProfessionalAudioPlayer.tsx
```

✅ **RIGHT**:
```
PlayerBar.tsx  (the definitive player component)
```

### Rule 2: No "Enhanced" Versions
**Never create "Enhanced", "Magic", "Professional", "Advanced" variants.**

If you need to improve a component:
1. Refactor the existing component
2. Add props for different variants
3. Delete the old version

❌ **WRONG**: Create `EnhancedButton.tsx`
✅ **RIGHT**: Add `variant` prop to `Button.tsx`

### Rule 3: Component Naming
**Clear, simple names. No adjectives.**

❌ **WRONG**:
- `MagicalMusicPlayer.tsx`
- `EnhancedCorrelationDisplay.tsx`
- `Phase5VisualizationSuite.tsx`

✅ **RIGHT**:
- `PlayerBar.tsx`
- `CorrelationMeter.tsx`
- `Visualizer.tsx`

### Rule 4: Maximum Component Size
**Components should be < 300 lines.**

If a component exceeds 300 lines:
1. Extract subcomponents
2. Extract custom hooks
3. Split into logical modules

### Rule 5: Experimental Code
**No experimental code in main codebase.**

Use feature branches or separate directory:
```
src/experimental/
  RadialPresetSelector.tsx  (experiment, not merged)
```

Delete after experiment concludes (success or failure).

---

## Design System Usage

### Mandatory: Use Design Tokens

All components **must** use design tokens from `src/design-system/tokens.ts`.

❌ **WRONG**:
```typescript
sx={{
  color: '#ffffff',
  padding: '16px',
  borderRadius: '8px',
  background: '#1a1f3a',
}}
```

✅ **RIGHT**:
```typescript
sx={{
  color: tokens.colors.text.primary,
  padding: tokens.spacing.md,
  borderRadius: tokens.borderRadius.md,
  background: tokens.colors.bg.secondary,
}}
```

### Color Usage

**Only use colors from the design system.**

```typescript
// src/design-system/tokens.ts
colors: {
  bg: { primary, secondary, tertiary, elevated },
  accent: { primary, secondary, success, warning, error },
  text: { primary, secondary, tertiary, disabled },
}
```

**Never**: Hardcode hex colors in components
**Never**: Create one-off color variations
**Always**: Add new colors to tokens.ts if needed

### Spacing

**Only use spacing scale from design system.**

```typescript
spacing: {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  xxl: '48px',
}
```

**Never**: Use arbitrary pixel values (`padding: '13px'`)
**Always**: Use spacing tokens (`padding: tokens.spacing.md`)

### Typography

**Only use typography scale from design system.**

```typescript
typography: {
  sizes: { xs, sm, base, lg, xl, '2xl', '3xl' },
  weights: { normal, medium, semibold, bold },
}
```

**Never**: Create custom font sizes
**Always**: Use typography tokens

---

## Component Architecture

### Primitive Components (8 total)

**Core UI building blocks. Cannot be duplicated.**

1. **Button** - All button variants (primary, secondary, ghost, danger)
2. **IconButton** - Icon-only buttons
3. **Card** - Content cards, containers
4. **Slider** - All slider variants (seek, volume, parameters)
5. **Input** - Text inputs, search bars
6. **Badge** - Status indicators, counts
7. **Tooltip** - Hover information
8. **Modal** - Dialogs, confirmations

**Rule**: Only these 8 primitives. No more.

### Feature Components (~30 total)

**App-specific components built from primitives.**

Examples:
- `PlayerBar.tsx` - Bottom player bar
- `TrackItem.tsx` - Single track in list
- `AlbumCard.tsx` - Album grid item
- `PresetCard.tsx` - Preset selector card
- `ParameterSlider.tsx` - Audio parameter control

**Rule**: Must use design system primitives, not raw MUI components.

### View Components (~7 total)

**Top-level page/view components.**

1. `LibraryView.tsx` - Library browsing
2. `AlbumView.tsx` - Album detail page
3. `ArtistView.tsx` - Artist detail page
4. `PlaylistView.tsx` - Playlist view
5. `QueueView.tsx` - Queue management
6. `SettingsView.tsx` - App settings
7. `SearchView.tsx` - Search results

**Rule**: Views compose feature components, not primitives directly.

### Component Hierarchy

```
View Components
  └─> Feature Components
        └─> Primitive Components
              └─> Design System Tokens
```

**Never skip levels.** Views should not use primitives directly.

---

## Animation Guidelines

### Performance First

**All animations must be 60fps.**

Use CSS transforms (cheap):
```typescript
transform: 'translateX(0)',  // ✅ GPU-accelerated
scale: 1.05,                 // ✅ GPU-accelerated
```

Avoid layout thrashing (expensive):
```typescript
width: '100px',  // ❌ Triggers layout
height: '50px',  // ❌ Triggers layout
```

### Subtle, Not Distracting

**Animations should enhance, not distract.**

✅ **Good**:
- Button hover: scale 1.0 → 1.02 (subtle)
- Card hover: shadow sm → md (gentle)
- Toast enter: slide + fade (smooth)

❌ **Bad**:
- Spinning, bouncing, pulsing everywhere
- Long animation durations (>400ms)
- Animations that block interaction

### Duration Guidelines

```typescript
transitions: {
  fast: '150ms',   // Hover states, tooltips
  normal: '250ms', // Buttons, cards, modals
  slow: '400ms',   // Page transitions, large movements
}
```

**Never exceed 400ms** unless for special cases (page transitions).

---

## Accessibility Requirements

### Keyboard Navigation

**All interactive elements must be keyboard accessible.**

- Tab order must be logical
- Focus indicators must be visible
- Escape key closes modals/dropdowns
- Arrow keys navigate lists

### Focus Management

```typescript
sx={{
  '&:focus-visible': {
    outline: `2px solid ${tokens.colors.accent.primary}`,
    outlineOffset: '2px',
  }
}}
```

### Screen Readers

**All interactive elements must have proper labels.**

```typescript
<IconButton aria-label="Play track">
  <PlayIcon />
</IconButton>
```

### Color Contrast

**All text must meet WCAG AA standards (4.5:1 contrast ratio).**

Use design system colors - they're already compliant.

---

## Performance Requirements

### Bundle Size Budget

- **Total bundle**: < 1MB (gzipped)
- **Initial load**: < 500KB
- **Code splitting**: Required for heavy components

### Rendering Performance

- **First paint**: < 500ms
- **Time to interactive**: < 1s
- **60fps scrolling**: Required for all lists

### Virtual Scrolling

**Required for lists > 100 items.**

```typescript
import { VirtualList } from 'src/design-system/primitives';

<VirtualList
  items={tracks}
  itemHeight={48}
  renderItem={(track) => <TrackItem track={track} />}
/>
```

### Image Optimization

**All images must be optimized.**

- Album art: WebP format, max 500x500
- Icons: SVG format
- Lazy loading for images below fold

---

## Code Quality Standards

### TypeScript

**Strict mode enabled. No `any` types.**

```typescript
// ❌ WRONG
const props: any = { ... };

// ✅ RIGHT
interface ButtonProps {
  variant: 'primary' | 'secondary';
  onClick: () => void;
  disabled?: boolean;
}
```

### Component Props

**Use proper TypeScript interfaces.**

```typescript
interface ComponentProps {
  // Required props first
  title: string;
  onAction: () => void;

  // Optional props with defaults
  variant?: 'default' | 'compact';
  disabled?: boolean;
  className?: string;
}
```

### Hooks

**Extract complex logic into custom hooks.**

```typescript
// ❌ WRONG: 100 lines of logic in component
function PlayerBar() {
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(1);
  // ... 95 more lines
}

// ✅ RIGHT: Logic in custom hook
function PlayerBar() {
  const player = usePlayer();
  return <div>...</div>;
}
```

### Error Handling

**All async operations must handle errors.**

```typescript
try {
  await api.loadTrack(trackId);
} catch (error) {
  showToast(`Failed to load track: ${error.message}`, 'error');
  logError(error);
}
```

---

## Testing Requirements

### Unit Tests

**All primitives must have unit tests.**

```typescript
describe('Button', () => {
  it('renders with correct variant', () => { ... });
  it('calls onClick when clicked', () => { ... });
  it('is disabled when disabled prop is true', () => { ... });
});
```

### Integration Tests

**All feature components must have integration tests.**

```typescript
describe('PlayerBar', () => {
  it('plays track when play button clicked', () => { ... });
  it('updates seek bar as track plays', () => { ... });
  it('shows track info correctly', () => { ... });
});
```

### E2E Tests

**Critical user flows must have E2E tests.**

```typescript
test('user can play track from library', async () => {
  await page.goto('/library');
  await page.click('[data-testid="track-123"]');
  await page.click('[data-testid="play-button"]');
  await expect(page.locator('[data-testid="player-bar"]')).toBeVisible();
});
```

---

## File Organization

### Directory Structure

```
src/
  design-system/
    tokens.ts              # Design tokens (colors, spacing, etc.)
    theme.ts               # MUI theme configuration
    primitives/            # 8 primitive components
      Button.tsx
      IconButton.tsx
      Card.tsx
      Slider.tsx
      Input.tsx
      Badge.tsx
      Tooltip.tsx
      Modal.tsx
    animations/            # Animation utilities
      useSpring.ts
      transitions.ts

  components/              # Feature components (~30)
    player/
      PlayerBar.tsx
      VolumeControl.tsx
      SeekBar.tsx
    library/
      TrackItem.tsx
      AlbumCard.tsx
      ArtistCard.tsx
    mastering/
      PresetCard.tsx
      ParameterSlider.tsx
      ProcessingToast.tsx

  views/                   # View components (~7)
    LibraryView.tsx
    AlbumView.tsx
    SettingsView.tsx

  hooks/                   # Custom hooks
    usePlayer.ts
    useLibrary.ts
    useWebSocket.ts

  services/                # API services
    api.ts
    websocket.ts

  contexts/                # React contexts
    PlayerContext.tsx
    LibraryContext.tsx
```

### Naming Conventions

- **Components**: PascalCase (`PlayerBar.tsx`)
- **Hooks**: camelCase with `use` prefix (`usePlayer.ts`)
- **Services**: camelCase (`api.ts`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_VOLUME`)

---

## Review Checklist

Before merging any UI PR, verify:

### Design System Compliance
- [ ] Uses design tokens (no hardcoded values)
- [ ] Follows spacing scale
- [ ] Uses color palette
- [ ] Uses typography scale

### Component Standards
- [ ] No duplicate components
- [ ] Clear, simple naming (no adjectives)
- [ ] < 300 lines per component
- [ ] Proper TypeScript types

### Performance
- [ ] No unnecessary re-renders
- [ ] Virtual scrolling for long lists
- [ ] Images optimized
- [ ] Code split if > 50KB

### Accessibility
- [ ] Keyboard navigable
- [ ] Focus indicators visible
- [ ] Proper ARIA labels
- [ ] Color contrast compliant

### Testing
- [ ] Unit tests for primitives
- [ ] Integration tests for features
- [ ] E2E tests for critical flows

### Code Quality
- [ ] No `any` types
- [ ] Error handling present
- [ ] No console.log statements
- [ ] Proper documentation

---

## Enforcement

### Pull Request Requirements

**PRs that violate these guidelines will be rejected.**

The reviewer must verify:
1. Design system compliance
2. No component duplication
3. Performance requirements met
4. Accessibility standards met
5. Tests included

### Breaking the Rules

**Only break these rules with explicit approval from lead developer.**

Document reasons in PR description:
```markdown
## Design Guideline Deviation

**Rule Broken**: Creating second player component
**Reason**: Experimental A/B test for new interaction model
**Approval**: @lead-developer
**Cleanup Plan**: Delete after test concludes (2 weeks)
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: "Enhanced" Versions
```typescript
// DON'T create enhanced versions
EnhancedButton.tsx
ProfessionalMeterBridge.tsx
MagicalMusicPlayer.tsx
```

**Fix**: Refactor the original component.

### ❌ Mistake 2: Hardcoded Values
```typescript
// DON'T hardcode design decisions
sx={{
  color: '#667eea',
  padding: '16px',
  borderRadius: '12px'
}}
```

**Fix**: Use design tokens.

### ❌ Mistake 3: Inline Styles for Design
```typescript
// DON'T use inline styles for design decisions
<div style={{ color: 'white', padding: '10px' }}>
```

**Fix**: Use sx prop with tokens.

### ❌ Mistake 4: Skipping Hierarchy
```typescript
// DON'T use primitives directly in views
function LibraryView() {
  return <Button>...</Button>;  // ❌ Skip level
}
```

**Fix**: Use feature components.

### ❌ Mistake 5: Large Components
```typescript
// DON'T create monolithic components
function PlayerBar() {
  // 500 lines of code ❌
}
```

**Fix**: Extract subcomponents and hooks.

---

## Migration Path

### Existing Code
1. **Audit**: Identify components that violate guidelines
2. **Plan**: Create refactoring plan (see UI_OVERHAUL_PLAN.md)
3. **Execute**: Refactor incrementally
4. **Delete**: Remove old/duplicate components

### New Code
- **All new code must follow these guidelines from day one**
- No exceptions
- No "we'll fix it later"

---

## Success Metrics

### Component Count
- **Target**: < 50 total components
- **Current**: 92 (Beta 9.0)
- **Reduction**: 45% required

### Code Lines
- **Target**: < 25k lines
- **Current**: 46k (Beta 9.0)
- **Reduction**: 46% required

### Performance
- **First paint**: < 500ms ✅
- **Time to interactive**: < 1s ✅
- **60fps scrolling**: All views ✅

### Quality
- **Zero console errors**: ✅
- **Zero UI crashes**: ✅
- **Test coverage**: > 80% ✅

---

## Resources

### Design Systems to Study
- **Radix UI** - Accessible primitives
- **Headless UI** - Unstyled components
- **Chakra UI** - Design token system
- **Material-UI v5** - Emotion + sx prop patterns

### Animation Libraries
- **Framer Motion** - React animations
- **React Spring** - Spring physics

### Performance Tools
- **React DevTools Profiler** - Component performance
- **Lighthouse** - Bundle size, metrics
- **Bundle Analyzer** - Code splitting analysis

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Nov 6, 2025 | Initial guidelines (post-Beta 9.0 audit) |

---

**Remember**: These guidelines exist to prevent the problems that led to Beta 9.0's 92-component, 46k-line codebase. Follow them religiously.

---

**Questions?** See [UI_OVERHAUL_PLAN.md](../roadmaps/UI_OVERHAUL_PLAN.md) for implementation details.

**Violations?** Open a discussion before breaking the rules.
