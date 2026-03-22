import { tokens } from '@/design-system';

interface TrackInfo {
  track_id: string;
  completion_percent: number;
  fully_cached: boolean;
}

interface TrackCacheListProps {
  tracks: Record<string, TrackInfo>;
  onTrackClearClick: (trackId: string) => void;
}

export function TrackCacheList({ tracks, onTrackClearClick }: TrackCacheListProps) {
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
        {Object.entries(tracks).map(([trackId, trackInfo]) => (
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
              onClick={() => onTrackClearClick(trackId)}
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
                (e.target as HTMLButtonElement).style.color = tokens.colors.semantic.error;
                (e.target as HTMLButtonElement).style.borderColor = tokens.colors.semantic.error;
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
  );
}
