# Shared UI components

Small, reusable pieces with no domain logic. Import from the subdirectory or the
file you need; there is deliberately no top-level barrel (nothing imported it, and
it advertised directories that never existed — #5805).

```
shared/ui/
├── ThemeToggle.tsx (+ ThemeToggleIcon, ThemeToggleLabelComponent, useThemeToggleSize,
│                    ThemeToggle.styles)     - theme switcher
├── ConfirmationDialog.tsx                   - confirm / cancel modal
├── feedback/                                - EmptyState and its variants (index.ts)
├── loaders/                                 - LoadingSpinner, Skeleton and the per-screen skeletons (index.ts)
└── media/                                   - AlbumArtDisplay, ProgressiveImage (index.ts)
```

```tsx
import ThemeToggle from '@/components/shared/ui/ThemeToggle';
import { EmptyState } from '@/components/shared/ui/feedback';
import { Skeleton } from '@/components/shared/ui/loaders';
import { ProgressiveImage } from '@/components/shared/ui/media';
```

Conventions: colors and spacing come from `tokens` (`@/design-system`), components stay
under 300 lines, and tests sit next to the code in a `__tests__/` folder.
