import React from 'react';
import { Box, styled, keyframes } from '@mui/material';

interface PageTransitionProps {
  children: React.ReactNode;
  delay?: number;
}

const fadeInUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const StyledPageContainer = styled(Box)<{ delay?: number }>(({ delay = 0 }) => ({
  animation: `${fadeInUp} 0.5s cubic-bezier(0.4, 0, 0.2, 1) ${delay}s both`,
  width: '100%',
  height: '100%',
}));

export const PageTransition: React.FC<PageTransitionProps> = ({ children, delay = 0 }) => {
  return <StyledPageContainer delay={delay}>{children}</StyledPageContainer>;
};

export default PageTransition;
