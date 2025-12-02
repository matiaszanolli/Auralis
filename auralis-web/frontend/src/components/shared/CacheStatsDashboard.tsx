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

import React, { useEffect, useState } from 'react';
import { tokens } from '@/design-system';
import { useCacheStats } from '@/hooks/useStandardizedAPI';
import { CacheStats } from '@/services/api/standardizedAPIClient';

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
 * Formats percentage values with color coding
 */
function PercentageDisplay({ value, threshold = 70 }: { value: number; threshold?: number }) {
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
      <div
        style={{
          width: '24px',
          height: '24px',
          borderRadius: '50%',
          background: color,
          opacity: 0.2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: tokens.typography.fontSize.xs,
          color,
          fontWeight: tokens.typography.fontWeight.bold,
        }}
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
function FileSizeDisplay({ sizeMb }: { sizeMb: number }) {
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
function TierCard({ tier, stats }: { tier: 'tier1' | 'tier2'; stats: CacheStats[typeof tier] }) {
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

/**
 * Cache Statistics Dashboard Component
 */
export function CacheStatsDashboard({
  refreshInterval = 5000,
  showTracks = false,
}: CacheStatsDashboardProps) {
  const { data: cacheStats, loading, error, refetch } = useCacheStats();

  // Set up auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, refetch]);

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
          background: 'rgba(239, 68, 68, 0.1)',
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
        Auto-refreshing every {refreshInterval / 1000}s
      </div>
    </div>
  );
}

export default CacheStatsDashboard;
