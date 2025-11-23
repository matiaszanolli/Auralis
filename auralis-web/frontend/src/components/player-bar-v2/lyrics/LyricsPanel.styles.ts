import { styled } from '@mui/material/styles';
import { Box, Typography } from '@mui/material';
import { gradients, auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '../../../design-system/tokens';

export const PanelContainer = styled(Box)({
  width: '320px',
  height: '100%',
  background: tokens.colors.bg.secondary,
  borderLeft: `1px solid ${auroraOpacity.veryLight}`,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

export const Header = styled(Box)({
  padding: '16px 20px',
  borderBottom: `1px solid ${auroraOpacity.veryLight}`,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  background: auroraOpacity.minimal,
});

export const LyricsContainer = styled(Box)({
  flex: 1,
  overflowY: 'auto',
  padding: '24px 20px',
  position: 'relative',

  '&::-webkit-scrollbar': {
    width: '8px',
  },
  '&::-webkit-scrollbar-track': {
    background: '#0A0E27',
  },
  '&::-webkit-scrollbar-thumb': {
    background: auroraOpacity.strong,
    borderRadius: '4px',
    '&:hover': {
      background: auroraOpacity.stronger,
    },
  },
});

export const LyricLine = styled(Typography)<{ isactive?: string; ispast?: string }>(
  ({ isactive, ispast }) => ({
    fontSize: '16px',
    lineHeight: '2',
    marginBottom: '12px',
    transition: 'all 0.3s ease',
    color:
      isactive === 'true'
        ? '#ffffff'
        : ispast === 'true'
          ? tokens.colors.text.secondary
          : tokens.colors.text.disabled,
    fontWeight: isactive === 'true' ? 600 : 400,
    transform: isactive === 'true' ? 'scale(1.05)' : 'scale(1)',
    opacity: isactive === 'true' ? 1 : ispast === 'true' ? 0.7 : 0.5,
    ...(isactive === 'true' && {
      background: gradients.aurora,
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
    }),
  })
);

export const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  padding: '40px 20px',
  textAlign: 'center',
});
