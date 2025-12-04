import React from 'react';

import { ChevronRight, AutoAwesome } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { useEnhancement } from '../../../contexts/EnhancementContext';
import EnhancementToggle from '../../shared/EnhancementToggle/EnhancementToggle';
import AudioCharacteristics from '../sections/AudioCharacteristics';
import ProcessingParameters from '../sections/ProcessingParameters';
import MasteringRecommendation from '../sections/MasteringRecommendation';
import InfoBox from '../sections/MasteringRecommendation/InfoBox';
import { EmptyState } from '../../shared/ui/feedback';
import LoadingState from '../sections/LoadingState';
import useMasteringRecommendation from '@/hooks/enhancement/useMasteringRecommendation';
import {
  ExpandedPaneContainer,
  PaneHeader,
  PaneContent,
  DisabledStateContainer,
} from '../EnhancementPane.styles';
import { ProcessingParams } from '../hooks/useEnhancementParameters';
import { IconButton } from '@/design-system';
import { Box, Typography, Stack } from '@mui/material';

interface ExpandedProps {
  params: ProcessingParams | null;
  isAnalyzing: boolean;
  onToggleCollapse?: () => void;
  onMasteringToggle?: (enabled: boolean) => void;
}

/**
 * Expanded - Expanded view showing enhancement parameters
 *
 * Displays master toggle, audio characteristics, processing parameters, and info.
 */
export const Expanded: React.FC<ExpandedProps> = ({
  params,
  isAnalyzing,
  onToggleCollapse,
  onMasteringToggle,
}) => {
  const { settings, setEnabled, isProcessing } = useEnhancement();
  // TODO: Get trackId from player state when PlayerStateContext becomes available
  const trackId: number | undefined = undefined;
  const { recommendation, isLoading } = useMasteringRecommendation(trackId);

  const handleMasteringToggle = async (enabled: boolean) => {
    await setEnabled(enabled);
    onMasteringToggle?.(enabled);
  };

  return (
    <ExpandedPaneContainer>
      {/* Header */}
      <PaneHeader>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <AutoAwesome
            sx={{
              color: tokens.colors.accent.primary,
              fontSize: tokens.typography.fontSize.lg,
            }}
          />
          <Typography
            variant="subtitle1"
            sx={{
              fontFamily: tokens.typography.fontFamily.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: tokens.colors.text.primary,
              fontSize: tokens.typography.fontSize.md,
            }}
          >
            Auto-Mastering
          </Typography>
        </Box>
        <IconButton
          onClick={onToggleCollapse}
          size="small"
          sx={{
            color: tokens.colors.text.primary,
            transition: tokens.transitions.fast,
            '&:hover': {
              transform: 'scale(1.1)',
            },
          }}
        >
          <ChevronRight />
        </IconButton>
      </PaneHeader>

      {/* Content */}
      <PaneContent>
        {/* Master Toggle */}
        <EnhancementToggle
          isEnabled={settings.enabled}
          isProcessing={isProcessing}
          onToggle={handleMasteringToggle}
        />

        {/* Parameters Display - when enabled and params available */}
        {settings.enabled && params && (
          <Stack spacing={tokens.spacing.lg}>
            {/* Audio Characteristics */}
            <AudioCharacteristics params={params} />

            {/* Processing Parameters */}
            <ProcessingParameters params={params} />

            {/* Mastering Recommendation (Priority 4) */}
            {(recommendation || isLoading) && (
              <MasteringRecommendation
                recommendation={recommendation}
                isLoading={isLoading}
              />
            )}

            {/* Info Box */}
            <InfoBox />
          </Stack>
        )}

        {/* Loading State - when analyzing */}
        {settings.enabled && !params && isAnalyzing && <LoadingState />}

        {/* Empty State - when enabled but no track playing */}
        {settings.enabled && !params && !isAnalyzing && (
          <EmptyState
            icon="music"
            title="No track playing"
            description="Play a track to see auto-mastering parameters"
          />
        )}

        {/* Disabled State */}
        {!settings.enabled && (
          <DisabledStateContainer>
            <AutoAwesome
              sx={{
                fontSize: tokens.typography.fontSize['4xl'],
                color: tokens.colors.accent.primary,
                marginBottom: tokens.spacing.md,
                opacity: 0.3,
              }}
            />
            <Typography
              variant="body2"
              sx={{
                color: tokens.colors.text.secondary,
                marginBottom: tokens.spacing.md,
                fontSize: tokens.typography.fontSize.sm,
              }}
            >
              Auto-Mastering is currently disabled
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: tokens.colors.text.disabled,
                lineHeight: tokens.typography.lineHeight.relaxed,
                fontSize: tokens.typography.fontSize.xs,
              }}
            >
              Enable the toggle above to start enhancing your music with intelligent processing
            </Typography>
          </DisabledStateContainer>
        )}
      </PaneContent>
    </ExpandedPaneContainer>
  );
};

export default Expanded;
