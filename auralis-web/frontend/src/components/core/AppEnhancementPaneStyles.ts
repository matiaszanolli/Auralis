/**
 * AppEnhancementPane Styled Components
 */

import { Box, styled } from '@mui/material';
import { auroraOpacity } from '../library/Styles/Color.styles';

export const PaneContainer = styled(Box)<{ isCollapsed: boolean }>(
  ({ isCollapsed }) => ({
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--midnight-blue)',
    borderLeft: `1px solid ${auroraOpacity.veryLight}`,
    transition: 'width 0.3s ease',
    width: isCollapsed ? 60 : 320,
    minWidth: isCollapsed ? 60 : 320,
    height: '100%',
    overflow: 'hidden',
  })
);

export const PaneHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 8px',
  borderBottom: `1px solid ${auroraOpacity.veryLight}`,
  gap: 16,
});

export const PaneTitle = styled(Box)({
  fontSize: '12px',
  fontWeight: 600,
  color: 'rgba(255, 255, 255, 0.5)',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  flex: 1,
});

export const ContentArea = styled(Box)({
  flex: 1,
  overflow: 'auto',
  padding: '16px 12px',
  '&::-webkit-scrollbar': {
    width: '6px',
  },
  '&::-webkit-scrollbar-track': {
    background: 'transparent',
  },
  '&::-webkit-scrollbar-thumb': {
    background: auroraOpacity.strong,
    borderRadius: '3px',
    '&:hover': {
      background: auroraOpacity.stronger,
    },
  },
});

export const FooterArea = styled(Box)({
  padding: '12px 8px',
  borderTop: `1px solid ${auroraOpacity.veryLight}`,
  display: 'flex',
  gap: 8,
});
