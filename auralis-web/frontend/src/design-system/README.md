# Auralis Design System

**Status**: ✅ Foundation Complete (Nov 6, 2025)

The Auralis Design System provides a consistent, professional foundation for all UI components. It enforces strict design principles and prevents the component bloat that led to the Beta 9.0 UI issues.

---

## 📦 What's Included

### Design Tokens (`tokens.ts`)
Single source of truth for all design values:
- **Colors**: Background, accent, text, borders
- **Spacing**: 8px grid system (xs to xxxl)
- **Typography**: Font families, sizes, weights, line heights
- **Border Radius**: Consistent corner rounding
- **Shadows**: Elevation and glow effects
- **Transitions**: Animation timings
- **Z-Index**: Layering scale
- **Gradients**: Aurora-themed gradients
- **Component-specific tokens**: Player bar, sidebar, etc.

### Primitive Components (`primitives/`)
8 core building blocks for all UI:

1. **Button** - Primary, secondary, ghost, danger variants
2. **IconButton** - Icon-only actions with tooltip support
3. **Card** - Containers for content sections
4. **Slider** - Volume, progress, parameter controls
5. **Input** - Text inputs and search fields
6. **Badge** - Counts, labels, status indicators
7. **Tooltip** - Contextual help on hover
8. **Modal** - Dialogs and confirmations

---

## 🚀 Quick Start

### Basic Usage

```typescript
// Import design system elements
import { tokens, Button, Card, IconButton } from '@/design-system';

// Use tokens for styling
const MyComponent = () => (
  <Card padding="lg">
    <Box sx={{
      color: tokens.colors.text.primary,
      padding: tokens.spacing.md,
      borderRadius: tokens.borderRadius.lg,
    }}>
      <Button variant="primary">Click me</Button>
      <IconButton variant="ghost" tooltip="Settings">
        <SettingsIcon />
      </IconButton>
    </Box>
  </Card>
);
```

### Component Examples

```typescript
// Button variants
<Button variant="primary">Primary Action</Button>
<Button variant="secondary" size="sm">Secondary</Button>
<Button variant="ghost">Ghost Button</Button>
<Button variant="danger" loading>Deleting...</Button>

// IconButton with tooltip
<IconButton tooltip="Play" variant="primary" size="lg">
  <PlayArrowIcon />
</IconButton>

// Card with hover
<Card variant="elevated" hoverable padding="lg">
  <h3>Album Title</h3>
  <p>Artist Name</p>
</Card>

// Slider with gradient
<Slider
  value={75}
  onChange={handleChange}
  variant="gradient"
  size="md"
  showValue
/>

// Input with icons
<Input
  variant="search"
  placeholder="Search music..."
  startIcon={<SearchIcon />}
/>

// Modal dialog
<Modal
  open={open}
  onClose={handleClose}
  title="Confirm Delete"
  size="md"
  actions={
    <>
      <Button variant="ghost" onClick={handleClose}>Cancel</Button>
      <Button variant="danger" onClick={handleDelete}>Delete</Button>
    </>
  }
>
  <p>Are you sure you want to delete this playlist?</p>
</Modal>
```

---

## 🎨 Design Principles

### 1. **Less is More**
- Default to NO when adding new components
- Ask: "Can I use/extend an existing component?"
- Every new component must justify its existence

### 2. **Consistency Over Novelty**
- Use established patterns, not experimental ideas
- Don't create "Enhanced", "Magic", "Professional" variants
- One component per purpose, refined over time

### 3. **Design System First**
- All UI must use design system tokens
- No hardcoded values in components
- No inline styles for design decisions

---

## 📏 The Rules

### Rule 1: The "One Component" Rule
**Only one component per logical purpose.**

❌ WRONG:
```
AudioPlayer.tsx
EnhancedAudioPlayer.tsx
MagicalMusicPlayer.tsx
```

✅ RIGHT:
```
PlayerBar.tsx  (the definitive player component)
```

### Rule 2: No "Enhanced" Versions
Never create "Enhanced", "Magic", "Professional", "Advanced" variants.

**Instead**:
- Refactor the existing component
- Add props for new features
- Keep backward compatibility

### Rule 3: Use Design Tokens Only

❌ WRONG:
```typescript
sx={{
  color: '#ffffff',
  padding: '16px',
  borderRadius: '8px',
}}
```

✅ RIGHT:
```typescript
sx={{
  color: tokens.colors.text.primary,
  padding: tokens.spacing.md,
  borderRadius: tokens.borderRadius.md,
}}
```

### Rule 4: Maximum Component Size
Components should be < 300 lines. If exceeded:
1. Extract subcomponents
2. Move logic to hooks
3. Split into logical modules

### Rule 5: Use Primitives First
Before creating a new component, check if primitives can be composed:

```typescript
// Instead of creating a new "FancyActionButton" component:
<Button variant="primary" startIcon={<StarIcon />} size="lg">
  Fancy Action
</Button>
```

---

## 🎨 Aurora Color Palette

```typescript
// Primary Background
tokens.colors.bg.primary    // #0A0E27 - Deep navy
tokens.colors.bg.secondary  // #1a1f3a - Lighter navy
tokens.colors.bg.tertiary   // #252a47 - Card backgrounds
tokens.colors.bg.elevated   // #2d3350 - Hover/active

// Aurora Accents
tokens.colors.accent.primary   // #667eea - Primary purple
tokens.colors.accent.secondary // #764ba2 - Secondary purple
tokens.colors.accent.success   // #00d4aa - Turquoise
tokens.colors.accent.error     // #ef4444 - Red

// Text
tokens.colors.text.primary   // #ffffff - White
tokens.colors.text.secondary // #8b92b0 - Muted purple-gray
tokens.colors.text.tertiary  // #6b7194 - More muted

// Gradients
tokens.gradients.aurora      // Purple gradient
tokens.gradients.pink        // Pink gradient
tokens.gradients.turquoise   // Turquoise gradient
```

---

## 📐 Spacing Scale

Based on 8px grid system:

```typescript
tokens.spacing.xs    // 4px
tokens.spacing.sm    // 8px
tokens.spacing.md    // 16px
tokens.spacing.lg    // 24px
tokens.spacing.xl    // 32px
tokens.spacing.xxl   // 48px
tokens.spacing.xxxl  // 64px
```

---

## 🔤 Typography Scale

```typescript
// Font Sizes
tokens.typography.fontSize.xs   // 11px
tokens.typography.fontSize.sm   // 12px
tokens.typography.fontSize.base // 14px
tokens.typography.fontSize.md   // 16px
tokens.typography.fontSize.lg   // 18px
tokens.typography.fontSize.xl   // 20px
tokens.typography.fontSize['2xl'] // 24px
tokens.typography.fontSize['3xl'] // 32px

// Font Weights
tokens.typography.fontWeight.normal   // 400
tokens.typography.fontWeight.medium   // 500
tokens.typography.fontWeight.semibold // 600
tokens.typography.fontWeight.bold     // 700
```

---

## 📦 File Structure

```
src/design-system/
├── tokens.ts                 # Design tokens (colors, spacing, etc.)
├── primitives/
│   ├── Button.tsx
│   ├── IconButton.tsx
│   ├── Card.tsx
│   ├── Slider.tsx
│   ├── Input.tsx
│   ├── Badge.tsx
│   ├── Tooltip.tsx
│   ├── Modal.tsx
│   └── index.ts
├── index.ts                  # Main export
└── README.md                 # This file
```

---

## ✅ Before Creating a New Component

**Ask yourself**:

1. ❓ Can I use an existing primitive component?
2. ❓ Can I compose multiple primitives?
3. ❓ Can I add a prop to an existing component?
4. ❓ Is this truly a new pattern, or a variant?
5. ❓ Have I checked the [UI_DESIGN_GUIDELINES.md](../../../docs/guides/UI_DESIGN_GUIDELINES.md)?

**If you answered NO to all of these**, then you may create a new component. But it must:
- Use design tokens exclusively
- Be < 300 lines
- Have clear, simple naming (no adjectives)
- Be documented with usage examples

---

## 🚫 Common Mistakes to Avoid

### ❌ Hardcoded Values
```typescript
// DON'T
<Box sx={{ color: '#ffffff', padding: '16px' }}>
```

### ❌ Duplicate Components
```typescript
// DON'T create:
EnhancedPlayerBar.tsx  // If PlayerBar.tsx exists
```

### ❌ Inline Styles for Design
```typescript
// DON'T
<div style={{ backgroundColor: '#1a1f3a', borderRadius: '8px' }}>
```

### ❌ One-off Components
```typescript
// DON'T create a component for a single use case
// Instead, compose primitives directly
```

---

## 🎯 Performance Targets

All components must meet these targets:

- **Render time**: < 16ms (60fps)
- **Bundle size**: Contribute < 10KB per component (gzipped)
- **Re-renders**: Memoize expensive computations
- **Animations**: Use CSS transitions, not JS

---

## 📚 Additional Resources

- **[UI Design Guidelines](../../../docs/guides/UI_DESIGN_GUIDELINES.md)** - **MANDATORY** reading
- **[UI Overhaul Plan](../../../docs/roadmaps/UI_OVERHAUL_PLAN.md)** - Beta 10.0 roadmap
- **[Master Roadmap](../../../docs/roadmaps/MASTER_ROADMAP.md)** - Complete project roadmap

---

## 🔄 Migration Guide

### Migrating from Old Components

**Step 1**: Import design system
```typescript
import { tokens, Button, Card } from '@/design-system';
```

**Step 2**: Replace hardcoded values
```typescript
// Before
<Button sx={{ background: '#667eea', padding: '16px' }}>

// After
<Button sx={{ background: tokens.gradients.aurora, padding: tokens.spacing.md }}>
```

**Step 3**: Use primitive components
```typescript
// Before
<MuiButton variant="contained" color="primary">

// After
<Button variant="primary">
```

**Step 4**: Remove old component imports
```typescript
// Remove
import { OldButton } from '@/components/OldButton';

// Keep only
import { Button } from '@/design-system';
```

---

## 📝 Component Checklist

When creating a new component:

- [ ] Read [UI_DESIGN_GUIDELINES.md](../../../docs/guides/UI_DESIGN_GUIDELINES.md)
- [ ] Checked if existing primitives can be composed
- [ ] Uses design tokens exclusively (no hardcoded values)
- [ ] Component is < 300 lines
- [ ] Clear, simple name (no adjectives like "Enhanced", "Magic")
- [ ] TypeScript props interface with JSDoc comments
- [ ] Usage examples in component comments
- [ ] Memoized if expensive rendering
- [ ] Meets performance targets (< 16ms render, < 10KB bundle)

---

**Version**: 1.0.0
**Created**: November 6, 2025
**Part of**: Beta 10.0 UI Overhaul

**See**: [UI_DESIGN_GUIDELINES.md](../../../docs/guides/UI_DESIGN_GUIDELINES.md) for complete rules
