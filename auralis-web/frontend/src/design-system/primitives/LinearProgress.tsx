/**
 * LinearProgress Primitive Component
 *
 * Linear progress bar for indicating task completion.
 *
 * Usage:
 *   <LinearProgress />
 *   <LinearProgress variant="determinate" value={75} />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import MuiLinearProgress, {
  LinearProgressProps as MuiLinearProgressProps,
} from '@mui/material/LinearProgress';
import { styled } from '@mui/material/styles';
import { tokens } from '../tokens';

export type LinearProgressProps = MuiLinearProgressProps;

const StyledLinearProgress = styled(MuiLinearProgress)({
  backgroundColor: tokens.colors.bg.level3,
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

export const LinearProgress: React.FC<LinearProgressProps> = (props) => {
  return <StyledLinearProgress {...props} />;
};

export default LinearProgress;
