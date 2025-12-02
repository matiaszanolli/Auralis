/**
 * Preset Configuration
 *
 * Defines all audio processing presets with their properties:
 * - Unique values, labels, and descriptions
 * - Color gradients for visual representation
 * - Icons for UI display
 * - Circular positions (0-360 degrees)
 */

import {
  AutoAwesome,
  WavesOutlined,
  WhatshotOutlined,
  FlareOutlined,
  BoltOutlined,
} from '@mui/icons-material';
import { gradients } from '../../library/Styles/Color.styles';

export interface Preset {
  value: string;
  label: string;
  description: string;
  gradient: string;
  icon: React.ReactNode;
  angle: number; // Position on the circle (0-360 degrees)
}

/**
 * All available audio processing presets
 * Arranged in circular positions (5 presets at 72° intervals)
 */
export const PRESETS: Preset[] = [
  {
    value: 'adaptive',
    label: 'Adaptive',
    description: 'Intelligent content-aware mastering',
    gradient: gradients.aurora,
    icon: <AutoAwesome />,
    angle: 0, // Top
  },
  {
    value: 'bright',
    label: 'Bright',
    description: 'Enhances clarity and presence',
    gradient: gradients.neonSunset,
    icon: <FlareOutlined />,
    angle: 72, // Top-right
  },
  {
    value: 'punchy',
    label: 'Punchy',
    description: 'Increases impact and dynamics',
    gradient: gradients.electricPurple,
    icon: <BoltOutlined />,
    angle: 144, // Bottom-right
  },
  {
    value: 'warm',
    label: 'Warm',
    description: 'Adds warmth and smoothness',
    gradient: gradients.neonSunset,
    icon: <WhatshotOutlined />,
    angle: 216, // Bottom-left
  },
  {
    value: 'gentle',
    label: 'Gentle',
    description: 'Subtle mastering with minimal processing',
    gradient: gradients.deepOcean,
    icon: <WavesOutlined />,
    angle: 288, // Top-left
  },
];

/**
 * Get preset by value
 */
export const getPresetByValue = (value: string): Preset => {
  return PRESETS.find((p) => p.value === value) || PRESETS[0];
};

/**
 * Calculate circular position for a given angle
 * @param angle - Angle in degrees (0-360)
 * @param radius - Distance from center
 * @returns x, y coordinates
 */
export const getCirclePosition = (angle: number, radius: number) => {
  const rad = ((angle - 90) * Math.PI) / 180; // -90 to start from top
  return {
    x: Math.cos(rad) * radius,
    y: Math.sin(rad) * radius,
  };
};
