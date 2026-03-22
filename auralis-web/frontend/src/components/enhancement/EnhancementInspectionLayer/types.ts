import type { PresetName } from '@/store/slices/playerSlice';

export interface EnhancementInspectionLayerProps {
  selectedPreset: PresetName;
  intensity: number;
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'error' | 'failed';
  fingerprintMessage?: string | null;
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';
  progress: number;
  processedChunks: number;
  totalChunks: number;
  currentTime: number;
  isPaused: boolean;
  error?: string | null;
  isStreaming: boolean;
  disabled?: boolean;
  onPresetChange?: (preset: PresetName) => void;
  onIntensityChange?: (intensity: number) => void;
  onPlayEnhanced?: () => void;
  onTogglePause?: () => void;
  onStop?: () => void;
  onDismissError?: () => void;
}

export interface PresetInfo {
  name: PresetName;
  label: string;
  description: string;
  icon: string;
}

export const PRESETS: Record<PresetName, PresetInfo> = {
  adaptive: {
    name: 'adaptive',
    label: 'Adaptive',
    description: 'Analyzes content and adjusts in real-time',
    icon: '🔄',
  },
  gentle: {
    name: 'gentle',
    label: 'Gentle',
    description: 'Subtle enhancement, preserves original character',
    icon: '🌿',
  },
  warm: {
    name: 'warm',
    label: 'Warm',
    description: 'Enhanced mid-range warmth and presence',
    icon: '🔥',
  },
  bright: {
    name: 'bright',
    label: 'Bright',
    description: 'Enhanced high-end clarity and definition',
    icon: '✨',
  },
  punchy: {
    name: 'punchy',
    label: 'Punchy',
    description: 'Aggressive dynamics and impact',
    icon: '💥',
  },
};
