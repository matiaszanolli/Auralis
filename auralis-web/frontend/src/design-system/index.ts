/**
 * Auralis Design System
 *
 * Central export for all design system elements.
 * Use this for all design-system imports.
 *
 * @example
 * import { tokens, Button, Card } from '@/design-system';
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

// Design tokens
export { tokens, withOpacity, hexToRgb, mediaBelow } from './tokens';
export type { DesignTokens, ColorToken, SpacingToken, TypographyToken, RgbChannels } from './tokens';

// Primitive components
export {
  Button,
  IconButton,
  Card,
  Slider,
  Tooltip,
  Chip,
  SegmentedControl,
  CircularProgress,
  List,
  Alert,
} from './primitives';

export type {
  ButtonProps,
  IconButtonProps,
  CardProps,
  SliderProps,
  TooltipProps,
  ChipProps,
  SegmentedControlProps,
  SegmentedControlOption,
  CircularProgressProps,
  ListProps,
} from './primitives';
