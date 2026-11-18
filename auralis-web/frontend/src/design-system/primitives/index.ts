/**
 * Auralis Design System - Primitive Components
 *
 * The primitive components, grouped into three family sub-barrels: layout, surface,
 * control. Each one has a production consumer; a primitive nothing imports does not
 * belong here (#6442).
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

export { List } from './layout';
export type { ListProps } from './layout';

export { Alert, Card, Chip, CircularProgress, Tooltip } from './surface';
export type {
  CardProps,
  ChipProps,
  CircularProgressProps,
  TooltipProps,
} from './surface';

export { Button, IconButton, SegmentedControl, Slider } from './control';
export type { ButtonProps, IconButtonProps, SegmentedControlProps, SegmentedControlOption, SliderProps } from './control';
