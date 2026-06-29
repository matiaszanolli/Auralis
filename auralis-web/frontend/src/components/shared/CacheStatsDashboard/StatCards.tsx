/**
 * Cache-stats sub-cards
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Presentational pieces extracted from CacheStatsDashboard to keep the main
 * component under the 300-line rule (#4187).
 */

import { tokens } from '@/design-system';
import { CacheStats } from '@/services/api/standardizedAPIClient';

/**
 * Formats percentage values with color coding
 */
export function PercentageDisplay({ value, threshold = 70 }: { value: number; threshold?: number }) {
  const percentage = Math.round(value * 100);
  const color =
    percentage >= threshold
      ? tokens.colors.semantic.success
      : percentage >= threshold * 0.7
        ? tokens.colors.semantic.warning
        : tokens.colors.semantic.error;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.sm,
      }}
    >
      {/* Use hex-alpha background instead of opacity so the text remains visible (#3990) */}
      <div
        style={{
          width: '24px',
          height: '24px',
          borderRadius: '50%',
          background: `${color}33`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: tokens.typography.fontSize.xs,
          color,
          fontWeight: tokens.typography.fontWeight.bold,
        }}
        aria-hidden="true"
      >
        {percentage}%
      </div>
      <span style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
        {percentage}%
      </span>
    </div>
  );
}

/**
 * Formats file sizes to human-readable format
 */
export function FileSizeDisplay({ sizeMb }: { sizeMb: number }) {
  const display = sizeMb >= 1024 ? `${(sizeMb / 1024).toFixed(2)} GB` : `${sizeMb.toFixed(1)} MB`;
  return (
    <span style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.sm }}>
      {display}
    </span>
  );
}

/**
 * Single tier statistics card
 */
export function TierCard({ tier, stats }: { tier: 'tier1' | 'tier2'; stats: CacheStats[typeof tier] }) {
  const tierLabel = tier === 'tier1' ? 'Tier 1 (Hot)' : 'Tier 2 (Warm)';

  return (
    <div
      style={{
        padding: tokens.spacing.lg,
        background: tokens.colors.bg.tertiary,
        borderRadius: '8px',
        border: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <div
        style={{
          fontSize: tokens.typography.fontSize.md,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.primary,
          marginBottom: tokens.spacing.md,
        }}
      >
        {tierLabel}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.md }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: tokens.spacing.md,
          }}
        >
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Chunks
            </div>
            <div style={{ fontSize: tokens.typography.fontSize.lg, color: tokens.colors.text.primary }}>
              {stats.chunks}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Size
            </div>
            <FileSizeDisplay sizeMb={stats.size_mb} />
          </div>
        </div>

        <div
          style={{
            borderTop: `1px solid ${tokens.colors.border.light}`,
            paddingTop: tokens.spacing.md,
          }}
        >
          <div
            style={{
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.tertiary,
              marginBottom: tokens.spacing.sm,
            }}
          >
            Hit Rate
          </div>
          <PercentageDisplay value={stats.hit_rate} />
          <div
            style={{
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.tertiary,
              marginTop: tokens.spacing.sm,
            }}
          >
            Hits: {stats.hits} | Misses: {stats.misses}
          </div>
        </div>
      </div>
    </div>
  );
}
