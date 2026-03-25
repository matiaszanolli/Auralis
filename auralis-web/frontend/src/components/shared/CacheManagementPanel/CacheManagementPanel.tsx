import { useState } from 'react';
import { tokens } from '@/design-system';
import { useCacheStats, useCacheHealth } from '@/hooks/shared/useStandardizedAPI';
import { useStandardizedAPI } from '@/hooks/shared/useStandardizedAPI';
import { ConfirmationDialog } from '@/components/shared/ui/ConfirmationDialog';
import { MemoryGauge } from './MemoryGauge';
import { QuickActions } from './QuickActions';
import { CacheTierCard } from './CacheTierCard';
import { TrackCacheList } from './TrackCacheList';

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

export function CacheManagementPanel({
  onCacheClearRequest,
  refreshInterval: _refreshInterval = 5000,
  showAdvanced = false,
}: CacheManagementPanelProps) {
  const { data: cacheStats, loading: statsLoading, error: statsError, refetch: refetchStats } =
    useCacheStats();
  const { data: cacheHealth, loading: _healthLoading, error: healthError } = useCacheHealth();
  const { refetch: clearCache, loading: clearLoading } = useStandardizedAPI('/api/cache/clear', {
    method: 'POST',
    autoFetch: false,
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
          background: tokens.colors.utility.errorBg,
          borderRadius: '8px',
          color: tokens.colors.semantic.error,
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

  const handleClearTrack = async () => {
    if (!selectedTrackForClear) return;
    try {
      await fetch(`/api/cache/track/${selectedTrackForClear}`, { method: 'DELETE' });
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
          max={260}
        />
      </div>

      <QuickActions
        onClearClick={() => setShowClearConfirmation(true)}
        onRefreshClick={() => refetchStats()}
        clearDisabled={clearLoading || cacheStats.overall.total_chunks === 0}
        refreshDisabled={statsLoading}
        clearLoading={clearLoading}
        statsLoading={statsLoading}
      />

      {/* Tier Info */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        <CacheTierCard title="🔥 Tier 1 (Hot Cache)" data={cacheStats.tier1} />
        <CacheTierCard title="🧊 Tier 2 (Warm Cache)" data={cacheStats.tier2} />
      </div>

      {showAdvanced && Object.keys(cacheStats.tracks).length > 0 && (
        <TrackCacheList
          tracks={cacheStats.tracks}
          onTrackClearClick={(trackId) => {
            setSelectedTrackForClear(trackId);
            setShowTrackClearConfirm(true);
          }}
        />
      )}

      {showClearConfirmation && (
        <ConfirmationDialog
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
        <ConfirmationDialog
          title="Clear Track Cache?"
          message={`This will remove all cached audio data for Track ${selectedTrackForClear}. The track will need to be re-processed on next play.`}
          confirmText="Clear Track Cache"
          cancelText="Cancel"
          isDangerous={true}
          onConfirm={() => handleClearTrack()}
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
