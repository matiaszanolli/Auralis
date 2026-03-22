import { tokens } from '@/design-system';
import type { PresetName } from '@/store/slices/playerSlice';

const PRESETS = [
  { name: 'Adaptive', icon: '🎯', value: 'adaptive' },
  { name: 'Gentle', icon: '🌸', value: 'gentle' },
  { name: 'Warm', icon: '🔥', value: 'warm' },
  { name: 'Bright', icon: '✨', value: 'bright' },
  { name: 'Punchy', icon: '💥', value: 'punchy' },
] as const;

export function PresetSelector({
  activePreset,
  onSelect,
}: {
  activePreset: string;
  onSelect: (preset: PresetName) => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: tokens.spacing.sm,
        paddingTop: tokens.spacing.md,
        borderTop: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      {PRESETS.map((preset) => (
        <button
          key={preset.value}
          onClick={() => onSelect(preset.value)}
          aria-label={preset.name}
          aria-pressed={activePreset === preset.value}
          style={{
            flex: 1,
            padding: tokens.spacing.sm,
            border: `2px solid ${activePreset === preset.value ? tokens.colors.accent.primary : tokens.colors.border.light}`,
            borderRadius: '6px',
            background: activePreset === preset.value ? `${tokens.colors.accent.primary}20` : tokens.colors.bg.tertiary,
            color: tokens.colors.text.primary,
            cursor: 'pointer',
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: activePreset === preset.value ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
            transition: 'all 0.2s',
          }}
        >
          {preset.icon}
        </button>
      ))}
    </div>
  );
}
