/**
 * Cache Statistics Dashboard Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Real-time display of cache performance metrics including:
 * - Tier 1 and Tier 2 cache hit rates and sizes
 * - Overall system cache statistics
 * - Per-track cache completion status
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { CACHE_STATS_REFRESH_INTERVAL_MS, useCacheStats } from '@/hooks/shared/useStandardizedAPI';
import { PercentageDisplay, FileSizeDisplay, TierCard } from './CacheStatsDashboard/StatCards';
import { TrackCacheList } from './CacheStatsDashboard/TrackCacheList';

interface CacheStatsDashboardProps {
  /**
   * Whether to show per-track details
   */
  showTracks?: boolean;
}

/**
 * Cache Statistics Dashboard Component
 */
export function CacheStatsDashboard({
  showTracks = false,
}: CacheStatsDashboardProps) {
  const { data: cacheStats, loading, error } = useCacheStats();

  // useCacheStats already polls internally — no extra setInterval needed (#2802)

  if (loading && !cacheStats) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          color: themeVars.textSecondary,
          textAlign: 'center',
        }}
      >
        Loading cache statistics...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          background: tokens.colors.utility.errorBg,
          borderRadius: '8px',
          color: tokens.colors.semantic.error,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        Failed to load cache statistics: {error}
      </div>
    );
  }

  if (!cacheStats) {
    return null;
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.lg,
      }}
    >
      {/* Overall Stats */}
      <div
        style={{
          padding: tokens.spacing.lg,
          background: themeVars.surfacePrimary,
          borderRadius: '8px',
          border: `1px solid ${tokens.colors.border.accent}`,
        }}
      >
        <div
          style={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: themeVars.textPrimary,
            marginBottom: tokens.spacing.md,
          }}
        >
          Overall Cache Performance
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: tokens.spacing.lg,
          }}
        >
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: themeVars.textMuted,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Total Size
            </div>
            <FileSizeDisplay sizeMb={cacheStats.overall.total_size_mb} />
          </div>
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: themeVars.textMuted,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Chunks Cached
            </div>
            <div style={{ fontSize: tokens.typography.fontSize.lg, color: themeVars.textPrimary }}>
              {cacheStats.overall.total_chunks}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: themeVars.textMuted,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Overall Hit Rate
            </div>
            <PercentageDisplay value={cacheStats.overall.overall_hit_rate} />
          </div>
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: themeVars.textMuted,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Tracks Cached
            </div>
            <div style={{ fontSize: tokens.typography.fontSize.lg, color: themeVars.textPrimary }}>
              {cacheStats.overall.tracks_cached}
            </div>
          </div>
        </div>
      </div>

      {/* Tier Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        <TierCard tier="tier1" stats={cacheStats.tier1} />
        <TierCard tier="tier2" stats={cacheStats.tier2} />
      </div>

      {/* Per-Track Details */}
      {showTracks && Object.keys(cacheStats.tracks).length > 0 && (
        <div
          style={{
            padding: tokens.spacing.lg,
            background: themeVars.surfaceSecondary,
            borderRadius: '8px',
            border: `1px solid ${tokens.colors.border.light}`,
          }}
        >
          <div
            style={{
              fontSize: tokens.typography.fontSize.md,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: themeVars.textPrimary,
              marginBottom: tokens.spacing.md,
            }}
          >
            Per-Track Cache Status
          </div>

          <TrackCacheList tracks={cacheStats.tracks} />
        </div>
      )}

      {/* Last Update Indicator */}
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color: themeVars.textMuted,
          textAlign: 'center',
        }}
      >
        Auto-refreshing every {CACHE_STATS_REFRESH_INTERVAL_MS / 1000}s
      </div>
    </div>
  );
}

export default CacheStatsDashboard;
