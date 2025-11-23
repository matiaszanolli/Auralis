# Shared UI Components Module

**Status**: Phase 3 (In Progress)
**Purpose**: Centralized reusable UI components organized by function

## Current Structure

```
shared/ui/
├── RadialPresetSelector.tsx    - Circular preset selection UI
├── ThemeToggle.tsx             - Theme switcher component
├── index.ts                    - Barrel export
├── badges/                     - (empty, ready for badges)
├── bars/                       - (empty, ready for progress/control bars)
├── buttons/                    - (empty, ready for button variants)
├── cards/                      - (empty, ready for card components)
├── dialogs/                    - (empty, ready for dialog templates)
├── inputs/                     - (empty, ready for input components)
├── lists/                      - (empty, ready for list items)
├── loaders/                    - (empty, ready for skeleton loaders)
├── media/                      - (empty, ready for media displays)
└── tooltips/                   - (empty, ready for tooltips)
```

## Components

### RadialPresetSelector
**File**: `RadialPresetSelector.tsx` (302 lines)
**Status**: Phase 3 Candidate (pending refactoring)
**Purpose**: Circular UI for selecting audio processing presets

**Features**:
- 5-item circular layout (Adaptive, Bright, Punchy, Warm, Gentle)
- Animated preset selection
- Hover tooltips with descriptions
- Gradient color indicators
- Icon support for each preset

**Props**:
- `currentPreset: string` - Selected preset value
- `onPresetChange: (preset: string) => void` - Selection handler
- `disabled?: boolean` - Disable interaction
- `size?: number` - Circle diameter (default 240)

### ThemeToggle
**File**: `ThemeToggle.tsx` (126 lines)
**Status**: Complete
**Purpose**: Light/dark theme switcher

**Features**:
- Toggle between light and dark modes
- Persistent theme preference
- Icon button with transition

## Phase 3 Refactoring Plan

### Immediate (Ready for Implementation)
1. **RadialPresetSelector** (302 lines) → Extract:
   - `PresetItem.tsx` - Individual preset button component
   - `usePresetSelection.ts` - State management hook
   - `presetConfig.ts` - Preset definitions (array of presets)
   - Target reduction: 302L → 120L main component (-60%)

### Upcoming (After RadialPresetSelector)
2. **EnhancementToggle** (300 lines) → Extract variant subcomponents
3. **DropZone** (296 lines) → Extract drop zone type variants
4. **Sidebar** (283 lines) → Extract nav sections

### UI Directory Population (Phase 3)
Consolidate existing components from scattered locations:
- Move button variants to `buttons/`
- Move input wrappers to `inputs/`
- Move dialog templates to `dialogs/`
- Move loading skeletons to `loaders/`
- Move card templates to `cards/`
- Move list items to `lists/`

## Usage Examples

### RadialPresetSelector
```typescript
import { RadialPresetSelector } from '@/components/shared/ui'

export const EnhancementPanel = () => {
  const [preset, setPreset] = useState('adaptive')

  return (
    <RadialPresetSelector
      currentPreset={preset}
      onPresetChange={setPreset}
      size={240}
    />
  )
}
```

### ThemeToggle
```typescript
import { ThemeToggle } from '@/components/shared/ui'

export const AppHeader = () => {
  return (
    <Box sx={{ display: 'flex', gap: 2 }}>
      <ThemeToggle />
    </Box>
  )
}
```

## Import Patterns

**All components from module**:
```typescript
import { RadialPresetSelector, ThemeToggle } from '@/components/shared/ui'
```

**Specific imports**:
```typescript
import RadialPresetSelector from '@/components/shared/ui/RadialPresetSelector'
import ThemeToggle from '@/components/shared/ui/ThemeToggle'
```

## Design Tokens Integration

All UI components use design tokens for consistency:
- Colors from `@/design-system/tokens`
- Aurora colors from `@/components/library/Styles/Color.styles`
- Spacing from `@/design-system/tokens`
- Typography from design system

## Testing

Each component has corresponding test files in `__tests__/`:
- `RadialPresetSelector.test.tsx`
- `ThemeToggle.test.tsx`

## Next Steps

1. Refactor RadialPresetSelector (Phase 3)
2. Refactor EnhancementToggle, DropZone, Sidebar
3. Populate subdirectories with consolidated components
4. Add comprehensive tests for all UI components
5. Create storybook/component library documentation

---

**Last Updated**: November 23, 2025
**Phase**: 3 (In Progress)
**Status**: Foundation laid, refactoring in progress
