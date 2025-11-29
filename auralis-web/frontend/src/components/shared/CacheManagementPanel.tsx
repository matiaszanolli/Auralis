/**
 * Cache Management Panel Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Advanced cache management UI with visual controls for:
 * - Clearing entire cache
 * - Clearing specific tracks
 * - Cache statistics visualization
 * - Memory usage monitoring
 *
 * Phase C.2: Advanced UI Components
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { useCacheStats, useCacheHealth } from '@/hooks/useStandardizedAPI';
import { useStandardizedAPI } from '@/hooks/useStandardizedAPI';
import { CacheStats } from '@/services/api/standardizedAPIClient';

interface CacheManagementPanelProps {
  /**
   * Callback when cache clear is requested
   */
  onCacheClearRequest?: () => void;
  /**
   * Refresh interval in milliseconds (default 5000ms)
   */
  refreshInterval?: number;
  /**
   * Show advanced options
   */
  showAdvanced?: boolean;
}

/**
 * Confirmation modal for cache clearing
 */
function ConfirmationModal({
  title,
  message,
  confirmText = 'Clear',
  cancelText = 'Cancel',
  isDangerous = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDangerous?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: tokens.colors.bg.secondary,
          borderRadius: '12px',
          border: `1px solid ${tokens.colors.border.medium}`,
          padding: tokens.spacing.lg,
          maxWidth: '400px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3
          style={{
            margin: `0 0 ${tokens.spacing.md} 0`,
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
          }}
        >
          {title}
        </h3>

        <p
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            fontSize: tokens.typography.fontSize.base,
            color: tokens.colors.text.secondary,
            lineHeight: tokens.typography.lineHeight.normal,
          }}
        >
          {message}
        </p>

        <div
          style={{
            display: 'flex',
            gap: tokens.spacing.md,
            justifyContent: 'flex-end',
          }}
        >
          <button
            onClick={onCancel}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: tokens.colors.bg.tertiary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: '6px',
              color: tokens.colors.text.primary,
              cursor: 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.medium,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.elevated;
            }}
            onMouseOut={(e) => {
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.tertiary;
            }}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: isDangerous ? tokens.colors.accent.error : tokens.colors.accent.primary,
              border: 'none',
              borderRadius: '6px',
              color: tokens.colors.text.primary,
              cursor: 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.medium,
              transition: 'all 0.2s',
              opacity: 0.9,
            }}
            onMouseOver={(e) => {
              (e.target as HTMLButtonElement).style.opacity = '1';
            }}
            onMouseOut={(e) => {
              (e.target as HTMLButtonElement).style.opacity = '0.9';
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Memory usage gauge
 */
function MemoryGauge({ current, max }: { current: number; max: number }) {
  const percentage = (current / max) * 100;
  const color =
    percentage >= 90
      ? tokens.colors.accent.error
      : percentage >= 70
        ? tokens.colors.accent.warning
        : tokens.colors.accent.success;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.sm,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.secondary,
        }}
      >
        <span>Memory Usage</span>
        <span>
          {current.toFixed(1)} / {max.toFixed(1)} MB
        </span>
      </div>
      <div
        style={{
          height: '8px',
          background: tokens.colors.bg.elevated,
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${percentage}%`,
            background: color,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color,
          fontWeight: tokens.typography.fontWeight.semibold,
        }}
      >
        {percentage.toFixed(1)}% Used
      </div>
    </div>
  );
}

/**
 * Cache Management Panel Component
 */
export function CacheManagementPanel({
  onCacheClearRequest,
  refreshInterval = 5000,
  showAdvanced = false,
}: CacheManagementPanelProps) {
  const { data: cacheStats, loading: statsLoading, error: statsError, refetch: refetchStats } =
    useCacheStats();
  const { data: cacheHealth, loading: healthLoading, error: healthError } = useCacheHealth();
  const { refetch: clearCache, loading: clearLoading } = useStandardizedAPI('/api/cache/clear', {
    method: 'POST',
  });

  const [showClearConfirmation, setShowClearConfirmation] = useState(false);
  const [selectedTrackForClear, setSelectedTrackForClear] = useState<string | null>(null);
  const [showTrackClearConfirm, setShowTrackClearConfirm] = useState(false);

  if (statsLoading && !cacheStats) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          color: tokens.colors.text.secondary,
          textAlign: 'center',
        }}
      >
        Loading cache management...
      </div>
    );
  }

  if (statsError || healthError) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '8px',
          color: tokens.colors.accent.error,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        Failed to load cache data: {statsError || healthError}
      </div>
    );
  }

  if (!cacheStats || !cacheHealth) {
    return null;
  }

  const handleClearCache = async () => {
    try {
      await clearCache();
      setShowClearConfirmation(false);
      refetchStats();
      onCacheClearRequest?.();
    } catch (error) {
      console.error('Failed to clear cache:', error);
    }
  };

  const handleClearTrack = async (trackId: string) => {
    try {
      await clearCache(`/api/cache/clear-track/${trackId}`);
      setShowTrackClearConfirm(false);
      setSelectedTrackForClear(null);
      refetchStats();
    } catch (error) {
      console.error('Failed to clear track cache:', error);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.lg,
      }}
    >
      {/* Header */}
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
          Cache Management
        </div>

        <MemoryGauge
          current={cacheHealth.total_size_mb}
          max={260} // Default max from Phase B.2
        />
      </div>

      {/* Quick Actions */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: tokens.spacing.md,
        }}
      >
        <button
          onClick={() => setShowClearConfirmation(true)}
          disabled={clearLoading || cacheStats.overall.total_chunks === 0}
          style={{
            padding: tokens.spacing.md,
            background: tokens.colors.accent.error,
            border: 'none',
            borderRadius: '8px',
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.semibold,
            cursor: clearLoading ? 'not-allowed' : 'pointer',
            opacity: clearLoading ? 0.6 : 0.9,
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => {
            if (!clearLoading) {
              (e.target as HTMLButtonElement).style.opacity = '1';
            }
          }}
          onMouseOut={(e) => {
            if (!clearLoading) {
              (e.target as HTMLButtonElement).style.opacity = '0.9';
            }
          }}
        >
          {clearLoading ? 'Clearing...' : '🗑️ Clear All Cache'}
        </button>

        <button
          onClick={() => refetchStats()}
          disabled={statsLoading}
          style={{
            padding: tokens.spacing.md,
            background: tokens.colors.bg.tertiary,
            border: `1px solid ${tokens.colors.border.medium}`,
            borderRadius: '8px',
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.semibold,
            cursor: statsLoading ? 'not-allowed' : 'pointer',
            opacity: statsLoading ? 0.6 : 0.9,
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => {
            if (!statsLoading) {
              (e.target as HTMLButtonElement).style.opacity = '1';
            }
          }}
          onMouseOut={(e) => {
            if (!statsLoading) {
              (e.target as HTMLButtonElement).style.opacity = '0.9';
            }
          }}
        >
          {statsLoading ? 'Refreshing...' : '🔄 Refresh Stats'}
        </button>
      </div>

      {/* Tier Info */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        {/* Tier 1 */}
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
            🔥 Tier 1 (Hot Cache)
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: tokens.spacing.sm,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Chunks:</span>
              <span style={{ color: tokens.colors.text.primary, fontWeight: tokens.typography.fontWeight.semibold }}>
                {cacheStats.tier1.chunks}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Size:</span>
              <span style={{ color: tokens.colors.text.primary, fontWeight: tokens.typography.fontWeight.semibold }}>
                {cacheStats.tier1.size_mb.toFixed(1)} MB
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Hit Rate:</span>
              <span
                style={{
                  color:
                    cacheStats.tier1.hit_rate >= 0.7
                      ? tokens.colors.accent.success
                      : tokens.colors.accent.warning,
                  fontWeight: tokens.typography.fontWeight.semibold,
                }}
              >
                {(cacheStats.tier1.hit_rate * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Tier 2 */}
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
            🧊 Tier 2 (Warm Cache)
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: tokens.spacing.sm,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Chunks:</span>
              <span style={{ color: tokens.colors.text.primary, fontWeight: tokens.typography.fontWeight.semibold }}>
                {cacheStats.tier2.chunks}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Size:</span>
              <span style={{ color: tokens.colors.text.primary, fontWeight: tokens.typography.fontWeight.semibold }}>
                {cacheStats.tier2.size_mb.toFixed(1)} MB
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                color: tokens.colors.text.secondary,
              }}
            >
              <span>Hit Rate:</span>
              <span
                style={{
                  color:
                    cacheStats.tier2.hit_rate >= 0.7
                      ? tokens.colors.accent.success
                      : tokens.colors.accent.warning,
                  fontWeight: tokens.typography.fontWeight.semibold,
                }}
              >
                {(cacheStats.tier2.hit_rate * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced: Per-Track Management */}
      {showAdvanced && Object.keys(cacheStats.tracks).length > 0 && (
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
            📋 Per-Track Cache Management
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: tokens.spacing.sm,
              maxHeight: '400px',
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
                  padding: tokens.spacing.md,
                  background: tokens.colors.bg.elevated,
                  borderRadius: '6px',
                }}
              >
                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: tokens.spacing.xs,
                  }}
                >
                  <div
                    style={{
                      fontSize: tokens.typography.fontSize.sm,
                      color: tokens.colors.text.secondary,
                    }}
                  >
                    Track {trackInfo.track_id}
                  </div>
                  <div
                    style={{
                      fontSize: tokens.typography.fontSize.xs,
                      color: tokens.colors.text.tertiary,
                    }}
                  >
                    {Math.round(trackInfo.completion_percent)}% cached
                    {trackInfo.fully_cached && ' ✅'}
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSelectedTrackForClear(trackId);
                    setShowTrackClearConfirm(true);
                  }}
                  style={{
                    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
                    background: tokens.colors.bg.secondary,
                    border: `1px solid ${tokens.colors.border.light}`,
                    borderRadius: '4px',
                    color: tokens.colors.text.secondary,
                    fontSize: tokens.typography.fontSize.xs,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  onMouseOver={(e) => {
                    (e.target as HTMLButtonElement).style.color = tokens.colors.accent.error;
                    (e.target as HTMLButtonElement).style.borderColor = tokens.colors.accent.error;
                  }}
                  onMouseOut={(e) => {
                    (e.target as HTMLButtonElement).style.color = tokens.colors.text.secondary;
                    (e.target as HTMLButtonElement).style.borderColor = tokens.colors.border.light;
                  }}
                >
                  Clear
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modals */}
      {showClearConfirmation && (
        <ConfirmationModal
          title="Clear All Cache?"
          message={`This will remove ${cacheStats.overall.total_chunks} cached chunks (${cacheStats.overall.total_size_mb.toFixed(1)} MB). This action cannot be undone.`}
          confirmText="Clear All"
          cancelText="Cancel"
          isDangerous={true}
          onConfirm={handleClearCache}
          onCancel={() => setShowClearConfirmation(false)}
        />
      )}

      {showTrackClearConfirm && selectedTrackForClear && (
        <ConfirmationModal
          title="Clear Track Cache?"
          message={`This will remove all cached chunks for Track ${selectedTrackForClear}. This action cannot be undone.`}
          confirmText="Clear"
          cancelText="Cancel"
          isDangerous={true}
          onConfirm={() => handleClearTrack(selectedTrackForClear)}
          onCancel={() => {
            setShowTrackClearConfirm(false);
            setSelectedTrackForClear(null);
          }}
        />
      )}
    </div>
  );
}

export default CacheManagementPanel;
