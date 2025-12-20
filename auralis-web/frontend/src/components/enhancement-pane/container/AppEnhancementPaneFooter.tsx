/**
 * AppEnhancementPaneFooter Component
 *
 * Footer with V2 toggle button
 */

import React from 'react';

import { FooterArea } from './AppEnhancementPaneStyles';
import { auroraOpacity } from '../../library/Styles/Color.styles';
import { Button, Tooltip } from '@/design-system';

interface AppEnhancementPaneFooterProps {
  useV2: boolean;
  onToggleV2?: () => void;
}

export const AppEnhancementPaneFooter: React.FC<AppEnhancementPaneFooterProps> = ({
  useV2,
  onToggleV2,
}) => {
  return (
    <FooterArea>
      <Tooltip title={useV2 ? 'Switch to V1' : 'Switch to V2'}>
        <Button
          onClick={onToggleV2}
          size="sm"
          fullWidth
          variant="secondary"
          sx={{
            background: useV2
              ? auroraOpacity.standard
              : auroraOpacity.minimal,
            color: useV2 ? 'rgb(102, 126, 234)' : 'rgba(255, 255, 255, 0.5)',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            padding: '8px',
            border: `1px solid ${
              useV2
                ? auroraOpacity.strong
                : auroraOpacity.veryLight
            }`,
            borderRadius: '4px',
            '&:hover': {
              background: useV2
                ? auroraOpacity.strong
                : auroraOpacity.veryLight,
            },
          }}
        >
          {useV2 ? 'V2 Active' : 'V1'}
        </Button>
      </Tooltip>
    </FooterArea>
  );
};
