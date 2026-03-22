import type { ReactNode } from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';
import type { SxProps } from '@mui/material';
import { tokens } from '@/design-system';
import { FloatingParticles } from './FloatingParticles';

interface PlaceholderShellProps {
  containerStyles: SxProps;
  enhancementSection: ReactNode;
  particlesAnimating: boolean;
  particlesIntensity: number;
  particlesCount: number;
  children: ReactNode;
}

const PlaceholderShell = ({
  containerStyles,
  enhancementSection,
  particlesAnimating,
  particlesIntensity,
  particlesCount,
  children,
}: PlaceholderShellProps) => (
  <Box sx={containerStyles}>
    <FloatingParticles isAnimating={particlesAnimating} intensity={particlesIntensity} count={particlesCount} />
    {enhancementSection}
    {children}
  </Box>
);

interface EmptyStatePaneProps {
  containerStyles: SxProps;
  enhancementSection: ReactNode;
}

export const EmptyStatePane = ({ containerStyles, enhancementSection }: EmptyStatePaneProps) => (
  <PlaceholderShell
    containerStyles={containerStyles}
    enhancementSection={enhancementSection}
    particlesAnimating={false}
    particlesIntensity={0.3}
    particlesCount={8}
  >
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
          fontSize: tokens.typography.fontSize.sm,
          textShadow: `0 2px 8px ${tokens.colors.opacityScale.dark.strong}`,
        }}
      >
        Play a track to see its sonic character
      </Typography>
    </Box>
  </PlaceholderShell>
);

interface PendingStatePaneProps {
  containerStyles: SxProps;
  enhancementSection: ReactNode;
  displayTitle?: string;
}

export const PendingStatePane = ({ containerStyles, enhancementSection, displayTitle }: PendingStatePaneProps) => (
  <PlaceholderShell
    containerStyles={containerStyles}
    enhancementSection={enhancementSection}
    particlesAnimating={true}
    particlesIntensity={0.5}
    particlesCount={10}
  >
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        zIndex: 1,
        gap: tokens.spacing.md,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.secondary,
          textAlign: 'center',
          fontSize: tokens.typography.fontSize.sm,
          textShadow: `0 2px 8px ${tokens.colors.opacityScale.dark.strong}`,
        }}
      >
        {displayTitle || 'Now Playing'}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
          fontSize: tokens.typography.fontSize.xs,
          opacity: 0.8,
        }}
      >
        Generating audio fingerprint...
      </Typography>
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
          fontSize: tokens.typography.fontSize.xs,
          opacity: 0.6,
          mt: tokens.spacing.sm,
        }}
      >
        Character will appear after analysis completes
      </Typography>
    </Box>
  </PlaceholderShell>
);

interface LoadingStatePaneProps {
  containerStyles: SxProps;
  enhancementSection: ReactNode;
  isTrackPlaying: boolean;
}

export const LoadingStatePane = ({ containerStyles, enhancementSection, isTrackPlaying }: LoadingStatePaneProps) => (
  <Box sx={containerStyles}>
    <FloatingParticles isAnimating={true} intensity={0.6} count={10} />
    <Box sx={{ position: 'relative', zIndex: 1 }}>
      {enhancementSection}
      <LinearProgress
        sx={{
          mb: tokens.spacing.lg,
          background: 'rgba(115, 102, 240, 0.15)',
          '& .MuiLinearProgress-bar': {
            background: 'linear-gradient(90deg, rgba(115, 102, 240, 0.8), rgba(0, 200, 220, 0.8))',
          },
        }}
      />
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
          textShadow: '0 0 12px rgba(115, 102, 240, 0.3)',
        }}
      >
        {isTrackPlaying ? 'Analyzing track character...' : 'Analyzing album character...'}
      </Typography>
    </Box>
  </Box>
);

interface NoFingerprintPaneProps {
  containerStyles: SxProps;
  enhancementSection: ReactNode;
  isTrackPlaying: boolean;
}

export const NoFingerprintPane = ({ containerStyles, enhancementSection, isTrackPlaying }: NoFingerprintPaneProps) => (
  <PlaceholderShell
    containerStyles={containerStyles}
    enhancementSection={enhancementSection}
    particlesAnimating={false}
    particlesIntensity={0.3}
    particlesCount={8}
  >
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
          fontSize: tokens.typography.fontSize.sm,
          textShadow: `0 2px 8px ${tokens.colors.opacityScale.dark.strong}`,
        }}
      >
        {isTrackPlaying
          ? 'Fingerprint not available for this track'
          : 'Play a track to see its sonic character'}
      </Typography>
    </Box>
  </PlaceholderShell>
);
