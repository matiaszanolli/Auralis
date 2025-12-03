/**
 * Keyboard Shortcut Definitions
 *
 * Configuration-driven shortcut definitions to eliminate repetition in useKeyboardShortcuts.
 * Each definition maps a config handler to its keyboard shortcuts.
 */

import { ShortcutDefinition } from '@/services/keyboardShortcutsService';
import { KeyboardShortcutsConfig } from './useKeyboardShortcuts';

interface ShortcutConfigEntry {
  key: string;
  category: 'Playback' | 'Navigation' | 'Library' | 'Queue' | 'Global' | 'Presets';
  description: string;
  modifiers?: { ctrl?: boolean; shift?: boolean; meta?: boolean; alt?: boolean };
}

interface ConfigHandlerMap {
  configKey: keyof KeyboardShortcutsConfig;
  shortcuts: ShortcutConfigEntry[];
  handler: (config: KeyboardShortcutsConfig) => ((...args: any[]) => void) | undefined;
}

/**
 * Map of config handlers to their shortcuts
 * This eliminates 200+ lines of repetitive if/push code
 */
export const SHORTCUT_CONFIG_MAP: ConfigHandlerMap[] = [
  {
    configKey: 'onPlayPause',
    shortcuts: [
      { key: ' ', category: 'Playback', description: 'Play/Pause' }
    ],
    handler: (config) => config.onPlayPause
  },
  {
    configKey: 'onNext',
    shortcuts: [
      { key: 'ArrowRight', category: 'Playback', description: 'Next track' }
    ],
    handler: (config) => config.onNext
  },
  {
    configKey: 'onPrevious',
    shortcuts: [
      { key: 'ArrowLeft', category: 'Playback', description: 'Previous track' }
    ],
    handler: (config) => config.onPrevious
  },
  {
    configKey: 'onSeekForward',
    shortcuts: [
      { key: 'ArrowRight', category: 'Playback', description: 'Seek forward', modifiers: { shift: true } }
    ],
    handler: (config) => config.onSeekForward
  },
  {
    configKey: 'onSeekBackward',
    shortcuts: [
      { key: 'ArrowLeft', category: 'Playback', description: 'Seek backward', modifiers: { shift: true } }
    ],
    handler: (config) => config.onSeekBackward
  },
  {
    configKey: 'onVolumeUp',
    shortcuts: [
      { key: 'ArrowUp', category: 'Playback', description: 'Volume up' }
    ],
    handler: (config) => config.onVolumeUp
  },
  {
    configKey: 'onVolumeDown',
    shortcuts: [
      { key: 'ArrowDown', category: 'Playback', description: 'Volume down' }
    ],
    handler: (config) => config.onVolumeDown
  },
  {
    configKey: 'onMute',
    shortcuts: [
      { key: '0', category: 'Playback', description: 'Mute/Unmute' },
      { key: 'm', category: 'Playback', description: 'Mute/Unmute', modifiers: { ctrl: true } }
    ],
    handler: (config) => config.onMute
  },
  {
    configKey: 'onToggleEnhancement',
    shortcuts: [
      { key: 'm', category: 'Global', description: 'Toggle enhancement' }
    ],
    handler: (config) => config.onToggleEnhancement
  },
  {
    configKey: 'onToggleLyrics',
    shortcuts: [
      { key: 'l', category: 'Global', description: 'Toggle lyrics' }
    ],
    handler: (config) => config.onToggleLyrics
  },
  {
    configKey: 'onShowSongs',
    shortcuts: [
      { key: '1', category: 'Navigation', description: 'Show Songs' }
    ],
    handler: (config) => config.onShowSongs
  },
  {
    configKey: 'onShowAlbums',
    shortcuts: [
      { key: '2', category: 'Navigation', description: 'Show Albums' }
    ],
    handler: (config) => config.onShowAlbums
  },
  {
    configKey: 'onShowArtists',
    shortcuts: [
      { key: '3', category: 'Navigation', description: 'Show Artists' }
    ],
    handler: (config) => config.onShowArtists
  },
  {
    configKey: 'onShowPlaylists',
    shortcuts: [
      { key: '4', category: 'Navigation', description: 'Show Playlists' }
    ],
    handler: (config) => config.onShowPlaylists
  },
  {
    configKey: 'onFocusSearch',
    shortcuts: [
      { key: '/', category: 'Navigation', description: 'Focus search' },
      { key: 'k', category: 'Navigation', description: 'Quick search', modifiers: { ctrl: true } },
      { key: 'k', category: 'Navigation', description: 'Quick search', modifiers: { meta: true } }
    ],
    handler: (config) => config.onFocusSearch
  },
  {
    configKey: 'onEscape',
    shortcuts: [
      { key: 'Escape', category: 'Navigation', description: 'Clear search / Close dialogs' }
    ],
    handler: (config) => config.onEscape
  },
  {
    configKey: 'onPlaySelected',
    shortcuts: [
      { key: 'Enter', category: 'Library', description: 'Play selected' }
    ],
    handler: (config) => config.onPlaySelected
  },
  {
    configKey: 'onToggleFavorite',
    shortcuts: [
      { key: 'l', category: 'Library', description: 'Toggle favorite' }
    ],
    handler: (config) => config.onToggleFavorite
  },
  {
    configKey: 'onAddToPlaylist',
    shortcuts: [
      { key: 'p', category: 'Library', description: 'Add to playlist' }
    ],
    handler: (config) => config.onAddToPlaylist
  },
  {
    configKey: 'onAddToQueue',
    shortcuts: [
      { key: 'q', category: 'Library', description: 'Add to queue' }
    ],
    handler: (config) => config.onAddToQueue
  },
  {
    configKey: 'onShowInfo',
    shortcuts: [
      { key: 'i', category: 'Library', description: 'Show info' }
    ],
    handler: (config) => config.onShowInfo
  },
  {
    configKey: 'onDelete',
    shortcuts: [
      { key: 'Delete', category: 'Library', description: 'Delete' }
    ],
    handler: (config) => config.onDelete
  },
  {
    configKey: 'onClearQueue',
    shortcuts: [
      { key: 'c', category: 'Queue', description: 'Clear queue', modifiers: { shift: true } }
    ],
    handler: (config) => config.onClearQueue
  },
  {
    configKey: 'onShuffleQueue',
    shortcuts: [
      { key: 's', category: 'Queue', description: 'Shuffle queue', modifiers: { shift: true } }
    ],
    handler: (config) => config.onShuffleQueue
  },
  {
    configKey: 'onShowHelp',
    shortcuts: [
      { key: '?', category: 'Global', description: 'Show help' }
    ],
    handler: (config) => config.onShowHelp
  },
  {
    configKey: 'onOpenSettings',
    shortcuts: [
      { key: ',', category: 'Global', description: 'Open settings', modifiers: { ctrl: true } },
      { key: ',', category: 'Global', description: 'Open settings', modifiers: { meta: true } }
    ],
    handler: (config) => config.onOpenSettings
  }
];

/**
 * Special case: Preset selection (1-5 keys map to different presets)
 * Handled separately because it needs dynamic preset name
 */
export const PRESET_SHORTCUTS: ShortcutConfigEntry[] = [
  { key: '1', category: 'Presets', description: 'Adaptive preset' },
  { key: '2', category: 'Presets', description: 'Gentle preset' },
  { key: '3', category: 'Presets', description: 'Warm preset' },
  { key: '4', category: 'Presets', description: 'Bright preset' },
  { key: '5', category: 'Presets', description: 'Punchy preset' }
];

export const PRESET_NAMES = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];

/**
 * Convert config entry and modifiers to ShortcutDefinition
 */
export function createShortcutDefinition(
  entry: ShortcutConfigEntry
): Omit<ShortcutDefinition, 'handler'> {
  // Map Presets to Global category since ShortcutDefinition doesn't include Presets
  const category = (entry.category === 'Presets' ? 'Global' : entry.category) as ShortcutDefinition['category'];

  return {
    key: entry.key,
    category,
    description: entry.description,
    ...(entry.modifiers?.ctrl && { ctrl: true }),
    ...(entry.modifiers?.shift && { shift: true }),
    ...(entry.modifiers?.meta && { meta: true }),
    ...(entry.modifiers?.alt && { alt: true })
  };
}
