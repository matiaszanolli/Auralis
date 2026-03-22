import { tokens } from '@/design-system';

interface TierData {
  chunks: number;
  size_mb: number;
  hit_rate: number;
}

interface CacheTierCardProps {
  title: string;
  data: TierData;
}

export function CacheTierCard({ title, data }: CacheTierCardProps) {
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
        {title}
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
            {data.chunks}
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
            {data.size_mb.toFixed(1)} MB
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
                data.hit_rate >= 0.7
                  ? tokens.colors.semantic.success
                  : tokens.colors.semantic.warning,
              fontWeight: tokens.typography.fontWeight.semibold,
            }}
          >
            {(data.hit_rate * 100).toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
