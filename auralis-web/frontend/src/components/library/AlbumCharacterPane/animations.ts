import { keyframes } from '@mui/material';

export const breathePulse = keyframes`
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.85;
    transform: scale(1.02);
  }
`;

export const subtleGlow = keyframes`
  0%, 100% {
    box-shadow: 0 0 8px 2px rgba(115, 102, 240, 0.15);
  }
  50% {
    box-shadow: 0 0 16px 4px rgba(115, 102, 240, 0.35);
  }
`;

export const energyDrift = keyframes`
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
  }
  33% {
    transform: translate(-48%, -52%) scale(1.05);
  }
  66% {
    transform: translate(-52%, -48%) scale(0.98);
  }
`;

export const particleFloat = keyframes`
  0% {
    transform: translateY(100%) translateX(0) scale(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
    transform: translateY(80%) translateX(5px) scale(1);
  }
  50% {
    opacity: 0.8;
    transform: translateY(40%) translateX(-5px) scale(0.8);
  }
  90% {
    opacity: 0.3;
    transform: translateY(10%) translateX(3px) scale(0.5);
  }
  100% {
    transform: translateY(0%) translateX(0) scale(0);
    opacity: 0;
  }
`;

export const arcPulse = keyframes`
  0%, 100% {
    opacity: 0.6;
    filter: blur(8px);
  }
  50% {
    opacity: 1;
    filter: blur(4px);
  }
`;

export const barGlow = keyframes`
  0%, 100% {
    filter: drop-shadow(0 0 4px rgba(115, 102, 240, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(115, 102, 240, 0.8));
  }
`;
