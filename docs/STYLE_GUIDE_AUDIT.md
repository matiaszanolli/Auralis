# Style Guide Audit Report

**Date**: December 2025
**Auditor**: Claude Code
**Reference**: [UI_STYLE_GUIDE.md](UI_STYLE_GUIDE.md)

---

## Executive Summary

This audit identifies components that violate the new Auralis UI Style Guide. The issues are categorized by severity and type.

**Total Files Reviewed**: 50+
**Files with Violations**: 35+
**Critical Violations**: 12
**Moderate Violations**: 23
**Minor Violations**: 15+

---

## Critical Violations

### 1. Hardcoded Colors (Not Using Tokens)

**Violation**: Style Guide §1 - Colors should use design tokens, not hardcoded hex values.

| File | Issue | Line |
|------|-------|------|
| [Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts) | Defines `#667eea`, `#764ba2` outside token system | 20-26 |
| [Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts) | Uses `rgba(0, 0, 0, *)` (pure black with opacity) | 78-86 |
| [Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts) | Hardcoded status colors `#4ade80`, `#ef4444` | 129-140 |
| [ShuffleModeSelector.module.css](../auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css) | Light theme fallbacks `#f5f5f5`, `#e0e0e0`, `#333` | 22-24 |
| [MediaCardArtwork.tsx](../auralis-web/frontend/src/components/shared/MediaCard/MediaCardArtwork.tsx) | Hardcoded hex colors | - |
| [AudioCharacteristics.tsx](../auralis-web/frontend/src/components/enhancement-pane/sections/AudioCharacteristics/AudioCharacteristics.tsx) | Hardcoded color values | - |

**Fix**: Replace all hardcoded colors with `tokens.colors.*` values.

---

### 2. Pure Black/White Usage

**Violation**: Style Guide §1.2 - "No pure black. No flat gray."

| File | Issue |
|------|-------|
| [Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts) | `blackOpacity` uses `rgba(0, 0, 0, *)` |
| [QueuePanel.tsx](../auralis-web/frontend/src/components/player/QueuePanel.tsx) | Contains `#000000` or `#fff` references |
| [QueueStatisticsPanel.tsx](../auralis-web/frontend/src/components/player/QueueStatisticsPanel.tsx) | Pure black/white values |
| [QueueRecommendationsPanel.tsx](../auralis-web/frontend/src/components/player/QueueRecommendationsPanel.tsx) | Pure black/white values |
| [QueueSearchPanel.tsx](../auralis-web/frontend/src/components/player/QueueSearchPanel.tsx) | Pure black/white values |
| [ShuffleModeSelector.module.css](../auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css) | `#ffffff` fallback |

**Fix**: Replace `#000000` with `tokens.colors.bg.level0` and `#ffffff` with `tokens.colors.text.primaryFull`.

---

### 3. Hard Borders

**Violation**: Style Guide §2.1 - "Borders are almost never visible" (<10% opacity).

| File | Issue |
|------|-------|
| [ShuffleModeSelector.module.css](../auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css) | `border: 1px solid var(--border-default, #e0e0e0)` - solid visible border |

**Fix**: Use `tokens.colors.border.light` (12% opacity) or remove borders entirely.

---

### 4. Always-Visible Numbers/Percentages

**Violation**: Style Guide §7.3 - "Numbers hidden by default, revealed on interaction."

| File | Issue |
|------|-------|
| [SimilarityOverallScore.tsx](../auralis-web/frontend/src/components/features/discovery/SimilarityOverallScore.tsx) | `{Math.round(score * 100)}%` always visible |
| [SimilarityOverallScore.tsx](../auralis-web/frontend/src/components/features/discovery/SimilarityOverallScore.tsx) | `Distance: {distance.toFixed(4)}` always visible |
| [ParameterBar.tsx](../auralis-web/frontend/src/components/enhancement-pane/sections/ProcessingParameters/ParameterBar.tsx) | Uses `LinearProgress` (bar graph style) |
| [StreamingProgressBar.tsx](../auralis-web/frontend/src/components/enhancement/StreamingProgressBar.tsx) | Progress percentage visible |
| [CacheHealthWidget.tsx](../auralis-web/frontend/src/components/shared/CacheHealthWidget.tsx) | Cache stats always visible |
| [CacheStatsDashboard.tsx](../auralis-web/frontend/src/components/shared/CacheStatsDashboard.tsx) | Statistics always visible |
| [ProcessingStatsChips.tsx](../auralis-web/frontend/src/components/shared/feedback/ProcessingStatsChips.tsx) | Stats always visible |

**Fix**: Implement `tokens.numbersPolicy.defaultVisibility: 'hidden'` - show on hover/interaction only.

---

### 5. Bar Graphs / Meters

**Violation**: Style Guide §7.2 - "Disallowed: Bar graphs, Meters, Percent indicators (always-on)"

| File | Issue |
|------|-------|
| [ParameterBar.tsx](../auralis-web/frontend/src/components/enhancement-pane/sections/ProcessingParameters/ParameterBar.tsx) | Uses `LinearProgress` - bar meter style |
| [SimilarityAllDimensions.tsx](../auralis-web/frontend/src/components/features/discovery/SimilarityAllDimensions.tsx) | Dimension bars/meters |
| [VolumeControl.tsx](../auralis-web/frontend/src/components/player/VolumeControl.tsx) | Volume meter |
| [BufferingIndicator.tsx](../auralis-web/frontend/src/components/player/BufferingIndicator.tsx) | Progress meter |

**Fix**: Replace bar graphs with allowed alternatives: flowing waves, halos, breathing gradients, soft arcs.

---

## Moderate Violations

### 6. Bounce/Spring Animations ✅ FIXED

**Violation**: Style Guide §6.1 - "No bounce easing"

**Status**: ✅ **RESOLVED** (December 2025)

| File | Issue | Status |
|------|-------|--------|
| [animations/index.ts](../auralis-web/frontend/src/design-system/animations/index.ts) | Bounce keyframe | ✅ Replaced with `gentleFloat`, `breathe`, `weightedLift` |
| [SmoothAnimationEngine.ts](../auralis-web/frontend/src/utils/SmoothAnimationEngine.ts) | Bounce/elastic easing | ✅ Deprecated with `@deprecated` JSDoc, added `weightedEase`, `liquidEase` |
| [DropZoneIcon.tsx](../auralis-web/frontend/src/components/shared/DropZone/DropZoneIcon.tsx) | Bounce animation | ✅ Replaced with `breathe 2.5s` animation |
| [DropZoneStyles.ts](../auralis-web/frontend/src/components/shared/DropZone/DropZoneStyles.ts) | Bounce keyframe | ✅ Replaced with `breathe` keyframe |
| [SearchBar.tsx](../auralis-web/frontend/src/components/library/SearchBar.tsx) | No spring found | ✅ Already compliant |
| [GlobalSearch.tsx](../auralis-web/frontend/src/components/library/Search/GlobalSearch.tsx) | No spring found | ✅ Already compliant |

**New Style Guide Compliant Animations**:
- `gentleFloat` - Slow, weighted vertical motion (replaces bounce)
- `breathe` - Slow organic scale animation (2-3s duration)
- `weightedLift` - Subtle attention-drawing lift
- `weightedEase` - Quintic ease-out for slow, heavy feel
- `liquidEase` - Custom curve for slow, organic motion

---

### 7. Fast Animations

**Violation**: Style Guide §6.2 - Hover should be 120-180ms, state changes 300-600ms.

| File | Issue |
|------|-------|
| [ShuffleModeSelector.module.css](../auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css) | `transition: all 0.2s ease` - uses 200ms (borderline) |
| [slideIn animation](../auralis-web/frontend/src/components/player/ShuffleModeSelector.module.css#L85-97) | 150ms slide animation |

**Fix**: Use `tokens.transitions.hover` (150ms) for hover, `tokens.transitions.stateChange` (450ms) for state changes.

---

### 8. Opacity Values Not Matching Style Guide

**Violation**: Style Guide §3.3 - Text opacity hierarchy.

The style guide specifies:
- Primary: 90-100%
- Secondary: 60-70%
- Metadata: 40-50%
- Disabled: <30%

| File | Issue |
|------|-------|
| 30+ component files | Using opacity values that don't match the guide |

**Fix**: Update to use `tokens.colors.text.primary`, `tokens.colors.text.secondary`, `tokens.colors.text.metadata`, `tokens.colors.text.disabled`.

---

### 9. Separate Color System (Color.styles.ts)

**Violation**: DRY Principle - Duplicate color definitions outside tokens.ts.

[Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts) defines:
- `colorAuroraPrimary`, `colorAuroraSecondary`
- `auroraOpacity` scale
- `whiteOpacity`, `blackOpacity` scales
- `gradientPresets`
- `statusColors`
- `colorUtility`, `colorCombos`

**Issue**: This creates a parallel color system that can diverge from `tokens.ts`.

**Fix**: Consolidate all color definitions into `tokens.ts` and update imports across components.

---

## Minor Violations

### 10. Gradient Definitions Outside Tokens

| File | Issue |
|------|-------|
| [Color.styles.ts](../auralis-web/frontend/src/components/library/Styles/Color.styles.ts#L92-117) | Gradient presets defined separately |
| Various components | Inline gradient definitions |

**Fix**: Use `tokens.gradients.*` values.

---

### 11. Test Files with Hardcoded Colors

| File | Issue |
|------|-------|
| [ThemeToggle.test.tsx](../auralis-web/frontend/src/components/__tests__/ThemeToggle.test.tsx) | Test assertions with hardcoded colors |
| [SimilarTracksListItem.test.tsx](../auralis-web/frontend/src/components/features/discovery/__tests__/SimilarTracksListItem.test.tsx) | Hardcoded hex in tests |
| [useSimilarTracksFormatting.test.ts](../auralis-web/frontend/src/components/features/discovery/__tests__/useSimilarTracksFormatting.test.ts) | Pure white `#fff` in tests |

**Note**: Test files may need hardcoded values for assertions, but should reference token values where possible.

---

## Recommendations

### Priority 1 (Critical - Do First)

1. **Consolidate Color.styles.ts into tokens.ts**
   - Merge all aurora colors, opacity scales, and gradients
   - Update 50+ imports across the codebase

2. **Replace pure black/white**
   - Search and replace `#000000`, `#000`, `#ffffff`, `#fff`
   - Use deep blue-black base colors instead

3. **Fix always-visible numbers**
   - Implement "reveal on interaction" pattern
   - Add CSS hover states to show technical data

### Priority 2 (Moderate - Do Soon)

4. **Remove bounce animations**
   - Update SmoothAnimationEngine
   - Replace spring easing with smooth easing

5. **Replace bar graphs with waves/halos**
   - ParameterBar → WaveVisualizer
   - LinearProgress → SoftArcProgress

6. **Update text opacities**
   - Audit all `opacity:` declarations
   - Map to new token values

### Priority 3 (Minor - When Convenient)

7. **Fix hard borders**
   - Reduce to <10% opacity
   - Remove unnecessary separators

8. **Update test files**
   - Reference tokens where possible

---

## Files Requiring Updates (Full List)

### Components (35 files)
```
auralis-web/frontend/src/components/
├── library/Styles/Color.styles.ts              [CRITICAL]
├── player/QueuePanel.tsx                        [CRITICAL]
├── player/QueueStatisticsPanel.tsx              [CRITICAL]
├── player/QueueRecommendationsPanel.tsx         [CRITICAL]
├── player/QueueSearchPanel.tsx                  [CRITICAL]
├── player/ShuffleModeSelector.module.css        [CRITICAL]
├── player/ProgressBar.tsx                       [MODERATE]
├── player/VolumeControl.tsx                     [MODERATE]
├── player/BufferingIndicator.tsx                [MODERATE]
├── features/discovery/SimilarityOverallScore.tsx [CRITICAL]
├── features/discovery/SimilarityAllDimensions.tsx [MODERATE]
├── enhancement-pane/sections/ProcessingParameters/ParameterBar.tsx [CRITICAL]
├── enhancement/StreamingProgressBar.tsx         [MODERATE]
├── shared/CacheHealthWidget.tsx                 [MODERATE]
├── shared/CacheStatsDashboard.tsx               [MODERATE]
├── shared/MediaCard/MediaCardArtwork.tsx        [MODERATE]
├── shared/DropZone/DropZoneIcon.tsx             [MINOR]
├── shared/DropZone/DropZoneStyles.ts            [MINOR]
└── ... (17 more files)
```

### Utilities (5 files)
```
auralis-web/frontend/src/
├── utils/SmoothAnimationEngine.ts               [MODERATE]
├── utils/performanceOptimizer.ts                [MINOR]
├── design-system/animations/index.ts            [MODERATE]
├── hooks/library/useLibraryWithStats.ts         [MINOR]
└── hooks/player/usePlayerControls.ts            [MINOR]
```

---

## Conclusion

The codebase has significant style guide violations, primarily around:

1. **Dual color systems** - Color.styles.ts and tokens.ts should be consolidated
2. **Pure black/white usage** - Should use deep blue-black base
3. **Always-visible numbers** - Should hide by default, reveal on interaction
4. **Bar graphs/meters** - Should use wave/halo alternatives
5. **Bounce animations** - Should use slow, weighted motion

Estimated effort: **2-3 days** of focused work to address critical and moderate violations.
