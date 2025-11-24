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
export { default as RadialPresetSelector } from './RadialPresetSelector';
export { PresetItem } from './PresetItem';
export { usePresetSelection } from './usePresetSelection';
export { PRESETS, getPresetByValue, getCirclePosition, type Preset } from './presetConfig';
export { default as ThemeToggle } from './ThemeToggle';
export { EnhancementToggle, ButtonVariant, SwitchVariant } from './EnhancementToggle';

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
