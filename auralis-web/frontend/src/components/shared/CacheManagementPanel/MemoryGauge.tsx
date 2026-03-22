import { tokens } from '@/design-system';

export function MemoryGauge({ current, max }: { current: number; max: number }) {
  const percentage = (current / max) * 100;
  const color =
    percentage >= 90
      ? tokens.colors.semantic.error
      : percentage >= 70
        ? tokens.colors.semantic.warning
        : tokens.colors.semantic.success;

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
