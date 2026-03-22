import React, { useCallback, useEffect, useRef } from 'react';
import { tokens } from '@/design-system';
import type { PresetName } from '@/store/slices/playerSlice';
import { PRESETS } from './types';

interface PresetSelectorProps {
  selectedPreset: PresetName;
  disabled?: boolean;
  onPresetChange?: (preset: PresetName) => void;
}

export const PresetSelector = ({
  selectedPreset,
  disabled = false,
  onPresetChange,
}: PresetSelectorProps) => {
  const [showPresetMenu, setShowPresetMenu] = React.useState(false);
  const presetContainerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!showPresetMenu) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (presetContainerRef.current && !presetContainerRef.current.contains(e.target as Node)) {
        setShowPresetMenu(false);
        triggerRef.current?.focus();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowPresetMenu(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showPresetMenu]);

  const handlePresetSelect = useCallback(
    (preset: PresetName) => {
      onPresetChange?.(preset);
      setShowPresetMenu(false);
    },
    [onPresetChange]
  );

  return (
    <div style={styles.presetSection}>
      <label style={styles.sectionLabel}>Preset</label>
      <div ref={presetContainerRef} style={styles.presetSelectorContainer}>
        <button
          ref={triggerRef}
          style={{
            ...styles.presetSelector,
            opacity: disabled ? 0.5 : 1,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
          onClick={() => !disabled && setShowPresetMenu(!showPresetMenu)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={showPresetMenu}
          aria-label="Select enhancement preset"
        >
          <span style={styles.presetIcon}>{PRESETS[selectedPreset].icon}</span>
          <span style={styles.presetLabel}>{PRESETS[selectedPreset].label}</span>
          <span style={styles.presetDropdownIcon} aria-hidden="true">&#x25BC;</span>
        </button>

        {showPresetMenu && (
          <div style={styles.presetMenu} role="listbox" aria-label="Enhancement presets">
            {Object.values(PRESETS).map((preset) => (
              <div
                key={preset.name}
                role="option"
                tabIndex={0}
                aria-selected={selectedPreset === preset.name}
                style={{
                  ...styles.presetItem,
                  backgroundColor:
                    selectedPreset === preset.name
                      ? tokens.colors.accent.primary + '20'
                      : 'transparent',
                  cursor: 'pointer',
                }}
                onClick={() => handlePresetSelect(preset.name)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handlePresetSelect(preset.name);
                  }
                }}
              >
                <div style={styles.presetIcon}>{preset.icon}</div>
                <div>
                  <div style={styles.presetItemLabel}>{preset.label}</div>
                  <div style={styles.presetDescription}>
                    {preset.description}
                  </div>
                </div>
                {selectedPreset === preset.name && (
                  <div style={styles.presetCheckmark} aria-hidden="true">&#x2713;</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  presetSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,
  },

  sectionLabel: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.secondary,
    fontFamily: tokens.typography.fontFamily.primary,
  },

  presetSelectorContainer: {
    position: 'relative',
  },

  presetSelector: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    transition: tokens.transitions.fast,
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,
  },

  presetDropdownIcon: {
    marginLeft: 'auto',
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  },

  presetMenu: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    marginTop: tokens.spacing.xs,
    background: tokens.glass.medium.background,
    backdropFilter: tokens.glass.medium.backdropFilter,
    border: tokens.glass.medium.border,
    boxShadow: tokens.glass.medium.boxShadow,
    borderRadius: tokens.borderRadius.md,
    zIndex: 1000,
    maxHeight: '300px',
    overflowY: 'auto',
  },

  presetItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'pointer',
    transition: tokens.transitions.fast,
  },

  presetIcon: {
    fontSize: tokens.typography.fontSize.lg,
    minWidth: '24px',
    textAlign: 'center' as const,
  },

  presetLabel: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.text.primary,
  },

  presetItemLabel: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.text.primary,
  },

  presetDescription: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    marginTop: tokens.spacing.xs,
  },

  presetCheckmark: {
    marginLeft: 'auto',
    color: tokens.colors.semantic.success,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};
