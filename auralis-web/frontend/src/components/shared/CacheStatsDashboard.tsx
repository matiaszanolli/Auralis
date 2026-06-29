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
import { useCacheStats } from '@/hooks/shared/useStandardizedAPI';
import { PercentageDisplay, FileSizeDisplay, TierCard } from './CacheStatsDashboard/StatCards';

interface CacheStatsDashboardProps {
  /**
   * Refresh interval in milliseconds (default 5000ms)
   */
  refreshInterval?: number;
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
          color: tokens.colors.text.secondary,
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
          background: tokens.colors.bg.secondary,
          borderRadius: '8px',
          border: `1px solid ${tokens.colors.border.accent}`,
        }}
      >
        <div
          style={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
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
                color: tokens.colors.text.tertiary,
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
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Chunks Cached
            </div>
            <div style={{ fontSize: tokens.typography.fontSize.lg, color: tokens.colors.text.primary }}>
              {cacheStats.overall.total_chunks}
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
              Overall Hit Rate
            </div>
            <PercentageDisplay value={cacheStats.overall.overall_hit_rate} />
          </div>
          <div>
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              Tracks Cached
            </div>
            <div style={{ fontSize: tokens.typography.fontSize.lg, color: tokens.colors.text.primary }}>
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
            Per-Track Cache Status
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: tokens.spacing.sm,
              maxHeight: '300px',
              overflowY: 'auto',
            }}
          >
            {Object.entries(cacheStats.tracks).map(([trackId, trackInfo]) => (
              <div
                key={trackId}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: tokens.spacing.sm,
                  background: tokens.colors.bg.elevated,
                  borderRadius: '4px',
                }}
              >
                <span style={{ fontSize: tokens.typography.fontSize.sm, color: tokens.colors.text.secondary }}>
                  Track {trackInfo.track_id}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.md }}>
                  <div
                    style={{
                      width: '100px',
                      height: '4px',
                      background: tokens.colors.border.light,
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${trackInfo.completion_percent}%`,
                        background: trackInfo.fully_cached
                          ? tokens.colors.semantic.success
                          : tokens.colors.semantic.warning,
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontSize: tokens.typography.fontSize.xs,
                      color: tokens.colors.text.tertiary,
                      minWidth: '40px',
                      textAlign: 'right',
                    }}
                  >
                    {Math.round(trackInfo.completion_percent)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Last Update Indicator */}
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
        }}
      >
        Auto-refreshing every 5s
      </div>
    </div>
  );
}

export default CacheStatsDashboard;
