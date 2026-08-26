/**
 * Auralis Design System - Primitive Components
 *
 * 18 core primitive components that form the foundation of all UI,
 * grouped into four family sub-barrels: layout, typography, surface,
 * control. These are the canonical components for all basic UI patterns.
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

export { Box, Container, ErrorBoundary, List } from './layout';
export type { BoxProps, ListProps } from './layout';

export { Text } from './typography';
export type { TextProps } from './typography';

export { Alert, Badge, Card, Chip, CircularProgress, ProgressBar, Tooltip } from './surface';
export type {
  BadgeProps,
  CardProps,
  ChipProps,
  CircularProgressProps,
  TooltipProps,
} from './surface';

export { Button, Checkbox, IconButton, Input, SegmentedControl, Slider } from './control';
export type { ButtonProps, IconButtonProps, InputProps, SegmentedControlProps, SegmentedControlOption, SliderProps } from './control';
