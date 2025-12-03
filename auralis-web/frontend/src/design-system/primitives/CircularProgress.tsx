/**
 * CircularProgress Primitive Component
 *
 * Circular loading indicator for async operations.
 *
 * Usage:
 *   <CircularProgress />
 *   <CircularProgress size={40} />
 *   <CircularProgress variant="determinate" value={75} />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import MuiCircularProgress, {
  CircularProgressProps as MuiCircularProgressProps,
} from '@mui/material/CircularProgress';
import { styled } from '@mui/material/styles';
import { tokens } from '../tokens';

export type CircularProgressProps = MuiCircularProgressProps;

const StyledCircularProgress = styled(MuiCircularProgress)({
  color: tokens.colors.accent.primary,

  '& circle': {
    strokeLinecap: 'round',
  },
});

export const CircularProgress: React.FC<CircularProgressProps> = (props) => {
  return <StyledCircularProgress {...props} />;
};

export default CircularProgress;
