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
export { tokens, withOpacity, hexToRgb } from './tokens';
export type { DesignTokens, ColorToken, SpacingToken, TypographyToken, RgbChannels } from './tokens';

// Primitive components
export {
  Button,
  IconButton,
  Card,
  Slider,
  Input,
  Badge,
  Tooltip,
  Chip,
  SegmentedControl,
  CircularProgress,
  List,
  Alert,
  Box,
  Container,
  Text,
} from './primitives';

export type {
  ButtonProps,
  IconButtonProps,
  CardProps,
  SliderProps,
  InputProps,
  BadgeProps,
  TooltipProps,
  ChipProps,
  SegmentedControlProps,
  SegmentedControlOption,
  CircularProgressProps,
  ListProps,
  BoxProps,
  TextProps,
} from './primitives';
