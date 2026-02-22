/**
 * Auralis Design System
 *
 * Central export for all design system elements.
 * Use this for all design-system imports.
 *
 * @example
 * import { tokens, Button, Card } from '@/design-system';
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

// Design tokens
export { tokens, withOpacity } from './tokens';
export type { DesignTokens, ColorToken, SpacingToken, TypographyToken } from './tokens';

// Animation system
export {
  fadeIn,
  fadeOut,
  slideUp,
  slideDown,
  slideInRight,
  slideOutRight,
  slideInLeft,
  slideOutLeft,
  scaleIn,
  scaleOut,
  pulse,
  rotate,
  shimmer,
  glow,
  glowAqua,
} from './animations';

// Primitive components
export {
  Button,
  IconButton,
  Card,
  Slider,
  Input,
  Badge,
  Tooltip,
  Modal,
  Chip,
  SegmentedControl,
  CircularProgress,
  LinearProgress,
  List,
  Alert,
  Box,
  Stack,
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
  ModalProps,
  ChipProps,
  SegmentedControlProps,
  SegmentedControlOption,
  CircularProgressProps,
  LinearProgressProps,
  ListProps,
  BoxProps,
  TextProps,
} from './primitives';
