/**
 * Shared UI Components Module
 *
 * Centralized, organized reusable UI components
 *
 * Organized by category:
 * - buttons/ - Button variants, toggles, and controls
 * - loaders/ - Loading indicators and skeleton screens
 * - feedback/ - Empty states, toasts, and user feedback
 * - media/ - Media display and image components
 * - badges/ - Badge and chip components
 * - bars/ - Progress bars and control bars (ready for organization)
 * - cards/ - Card templates (ready for organization)
 * - dialogs/ - Dialog and modal templates (ready for organization)
 * - inputs/ - Form input components (ready for organization)
 * - lists/ - List item components (ready for organization)
 * - tooltips/ - Tooltip components (ready for organization)
 */

// Buttons & Toggles
// RadialPresetSelector and its supporting modules (PresetItem,
// RadialCenterHub, RadialDecorations, usePresetSelection, presetConfig)
// removed: zero production consumers (only this barrel and their own test
// file referenced them), and the circular 5-preset selector they built had
// nothing left to arrange in a circle once the preset system was narrowed
// to one (#4861 follow-up).
export { default as ThemeToggle } from './ThemeToggle';
export { EnhancementToggle, ButtonVariant, SwitchVariant } from '@/components/shared/EnhancementToggle';

// Loaders
export {
  LoadingSpinner,
  CenteredLoading,
  AlbumCardSkeleton,
  TrackRowSkeleton,
  LibraryGridSkeleton,
  TrackListSkeleton,
  SidebarItemSkeleton,
  PlayerBarSkeleton,
  Skeleton,
} from './loaders';

// Feedback
export { EmptyState } from './feedback';
// Toast has been moved to @/components/shared/Toast

// Media
export { AlbumArtDisplay } from './media';
export { ProgressiveImage } from './media';

// Badges
export { ParameterChip } from './badges';
