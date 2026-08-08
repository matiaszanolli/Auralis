/**
 * LinearProgress Primitive Component
 *
 * Linear progress bar for indicating task completion.
 *
 * Usage:
 *   <LinearProgress />
 *   <LinearProgress variant="determinate" value={75} />
 *
 * @see docs/UI_DESIGN_GUIDELINES.md
 */

import MuiLinearProgress, {
  LinearProgressProps as MuiLinearProgressProps,
} from '@mui/material/LinearProgress';
import { styled } from '@mui/material/styles';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export type LinearProgressProps = MuiLinearProgressProps;

const StyledLinearProgress = styled(MuiLinearProgress)({
  backgroundColor: themeVars.surfaceRaised,
  height: 6,
  borderRadius: tokens.borderRadius.sm,

  '& .MuiLinearProgress-bar': {
    backgroundColor: tokens.colors.accent.primary,
    borderRadius: tokens.borderRadius.sm,
  },

  '& .MuiLinearProgress-bar2Indeterminate': {
    backgroundColor: tokens.colors.accent.secondary,
  },
});

export const LinearProgress = (props: LinearProgressProps) => {
  return <StyledLinearProgress {...props} />;
};

export default LinearProgress;
