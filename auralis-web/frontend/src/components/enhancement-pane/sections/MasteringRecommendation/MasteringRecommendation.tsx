/**
 * MasteringRecommendation Component
 *
 * Displays weighted mastering profile recommendations (Priority 4).
 * Shows primary profile with confidence, and blend composition if hybrid mastering detected.
 * 100% design token compliant.
 */

import React from 'react';
import { tokens } from '@/design-system';

interface ProfileWeight {
  profile_id: string;
  profile_name: string;
  weight: number;
}

interface MasteringRecommendationData {
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number;
  predicted_loudness_change: number;
  predicted_crest_change: number;
  predicted_centroid_change: number;
  weighted_profiles?: ProfileWeight[];
  reasoning?: string;
  is_hybrid?: boolean;
}

interface MasteringRecommendationProps {
  recommendation: MasteringRecommendationData | null;
  isLoading?: boolean;
}

const MasteringRecommendation: React.FC<MasteringRecommendationProps> = React.memo(({
  recommendation,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div style={{
        padding: tokens.spacing.md,
        background: tokens.colors.bg.secondary,
        borderRadius: tokens.borderRadius.md,
        textAlign: 'center',
        color: tokens.colors.text.secondary
      }}>
        <span>📊 Analyzing mastering profile...</span>
      </div>
    );
  }

  if (!recommendation) {
    return null;
  }

  const isHybrid = recommendation.is_hybrid && recommendation.weighted_profiles && recommendation.weighted_profiles.length > 0;

  return (
    <div style={{
      padding: tokens.spacing.md,
      background: tokens.colors.bg.secondary,
      borderRadius: tokens.borderRadius.md,
      border: `1px solid ${tokens.colors.border.medium}`,
      display: 'flex',
      flexDirection: 'column',
      gap: tokens.spacing.md
    }}>
      {/* Header with confidence badge */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.primary
        }}>
          🎯 Mastering Profile
        </div>
        <div style={{
          padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
          background: getConfidenceColor(recommendation.confidence_score),
          borderRadius: tokens.borderRadius.sm,
          fontSize: tokens.typography.fontSize.xs,
          fontWeight: tokens.typography.fontWeight.medium,
          color: tokens.colors.text.primary
        }}>
          {(recommendation.confidence_score * 100).toFixed(0)}% match
        </div>
      </div>

      {/* Primary profile name */}
      <div style={{
        fontSize: tokens.typography.fontSize.sm,
        color: tokens.colors.text.primary,
        fontWeight: tokens.typography.fontWeight.medium
      }}>
        {recommendation.primary_profile_name}
      </div>

      {/* Hybrid blend indicator and weights */}
      {isHybrid && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: tokens.spacing.sm,
          padding: tokens.spacing.sm,
          background: tokens.colors.bg.level3,
          borderRadius: tokens.borderRadius.sm,
          border: `1px solid ${tokens.colors.border.light}`
        }}>
          <div style={{
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.secondary,
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            Hybrid Blend
          </div>
          {(recommendation.weighted_profiles ?? []).map((profile, idx) => (
            <div key={idx} style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.secondary
            }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {profile.profile_name}
              </span>
              <span style={{
                marginLeft: tokens.spacing.sm,
                fontWeight: tokens.typography.fontWeight.semibold,
                color: tokens.colors.text.primary,
                minWidth: '40px',
                textAlign: 'right'
              }}>
                {(profile.weight * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Processing changes */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: tokens.spacing.sm
      }}>
        <ProcessingChangeItem
          label="Loudness"
          value={recommendation.predicted_loudness_change}
          unit="dB"
        />
        <ProcessingChangeItem
          label="Crest"
          value={recommendation.predicted_crest_change}
          unit="dB"
        />
        <ProcessingChangeItem
          label="Centroid"
          value={recommendation.predicted_centroid_change}
          unit="Hz"
        />
      </div>

      {/* Reasoning */}
      {recommendation.reasoning && (
        <div style={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.secondary,
          fontStyle: 'italic',
          lineHeight: '1.4'
        }}>
          {recommendation.reasoning}
        </div>
      )}
    </div>
  );
});

MasteringRecommendation.displayName = 'MasteringRecommendation';

interface ProcessingChangeItemProps {
  label: string;
  value: number;
  unit: string;
}

const ProcessingChangeItem: React.FC<ProcessingChangeItemProps> = ({ label, value, unit }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: tokens.spacing.xs,
    padding: tokens.spacing.sm,
    background: tokens.colors.bg.level3,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.light}`
  }}>
    <div style={{
      fontSize: tokens.typography.fontSize.xs,
      color: tokens.colors.text.secondary,
      fontWeight: tokens.typography.fontWeight.medium
    }}>
      {label}
    </div>
    <div style={{
      fontSize: tokens.typography.fontSize.sm,
      color: tokens.colors.text.primary,
      fontWeight: tokens.typography.fontWeight.semibold
    }}>
      {value > 0 ? '+' : ''}{value.toFixed(value % 1 !== 0 ? 1 : 0)} {unit}
    </div>
  </div>
);

function getConfidenceColor(confidence: number): string {
  // High confidence (70%+): green
  if (confidence >= 0.7) {
    return `${tokens.colors.semantic.success}22`; // ~13% opacity
  }
  // Medium confidence (40-70%): yellow
  if (confidence >= 0.4) {
    return `${tokens.colors.semantic.warning}22`; // ~13% opacity
  }
  // Low confidence (<40%): shows hybrid blend, neutral
  return tokens.colors.bg.level3;
}

export default MasteringRecommendation;
