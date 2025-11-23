/**
 * Shared UI Components Module
 *
 * Reusable UI components organized by purpose:
 * - RadialPresetSelector - Circular preset selector UI
 * - PresetItem - Individual preset button component
 * - usePresetSelection - State management hook for preset selection
 * - ThemeToggle - Theme switcher component
 * - PRESETS - Preset configuration and utilities
 *
 * Empty subdirectories for future organization:
 * - badges/ - Badge components
 * - bars/ - Bar/progress components
 * - buttons/ - Button variants
 * - cards/ - Card components
 * - dialogs/ - Dialog/modal templates
 * - inputs/ - Input field components
 * - lists/ - List item components
 * - loaders/ - Loading skeleton components
 * - media/ - Media display components
 * - tooltips/ - Tooltip components
 */

// Preset Selector Components
export { default as RadialPresetSelector } from './RadialPresetSelector';
export { PresetItem } from './PresetItem';
export { usePresetSelection } from './usePresetSelection';
export { PRESETS, getPresetByValue, getCirclePosition, type Preset } from './presetConfig';

// Other UI Components
export { default as ThemeToggle } from './ThemeToggle';
