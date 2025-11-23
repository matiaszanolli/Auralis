import { css } from '@emotion/react';

// Direct color values to avoid circular import issues at module load time
const BG_PRIMARY = '#0A0E27';
const BG_SECONDARY = '#1a1f3a';
const BG_SURFACE = '#252b45';
const BG_HOVER = '#2a3150';
const TEXT_PRIMARY = '#ffffff';
const TEXT_SECONDARY = '#8b92b0';
const TEXT_DISABLED = '#5a5f7a';

// Gradient constants (module load-time requirement)
const GRADIENT_AURORA = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
const GRADIENT_NEON_SUNSET = 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)';
const GRADIENT_DEEP_OCEAN = 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)';

export const globalStyles = css`
  :root {
    /* Color variables */
    --bg-primary: ${BG_PRIMARY};
    --bg-secondary: ${BG_SECONDARY};
    --bg-surface: ${BG_SURFACE};
    --bg-hover: ${BG_HOVER};

    --text-primary: ${TEXT_PRIMARY};
    --text-secondary: ${TEXT_SECONDARY};
    --text-disabled: ${TEXT_DISABLED};

    /* Gradient variables */
    --gradient-aurora: ${GRADIENT_AURORA};
    --gradient-sunset: ${GRADIENT_NEON_SUNSET};
    --gradient-ocean: ${GRADIENT_DEEP_OCEAN};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: ${BG_PRIMARY};
    color: ${TEXT_PRIMARY};
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 12px;
    height: 12px;
  }

  ::-webkit-scrollbar-track {
    background: ${BG_SECONDARY};
  }

  ::-webkit-scrollbar-thumb {
    background: ${BG_SURFACE};
    border-radius: 6px;
    border: 2px solid ${BG_SECONDARY};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${BG_HOVER};
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${BG_SURFACE} ${BG_SECONDARY};
  }

  /* Animation keyframes */
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }

  @keyframes glow {
    0%, 100% {
      filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.4));
    }
    50% {
      filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.8));
    }
  }

  @keyframes shimmer {
    0% {
      background-position: -1000px 0;
    }
    100% {
      background-position: 1000px 0;
    }
  }

  @keyframes slideInUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes scaleIn {
    from {
      transform: scale(0.95);
      opacity: 0;
    }
    to {
      transform: scale(1);
      opacity: 1;
    }
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeInDown {
    from {
      opacity: 0;
      transform: translateY(-30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeInLeft {
    from {
      opacity: 0;
      transform: translateX(-30px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes fadeInRight {
    from {
      opacity: 0;
      transform: translateX(30px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  /* Utility classes */
  .gradient-text {
    background: ${GRADIENT_AURORA};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }

  /* Scroll animation classes */
  .animate-fade-in {
    animation: fadeIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .animate-fade-in-up {
    animation: fadeInUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .animate-fade-in-down {
    animation: fadeInDown 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .animate-fade-in-left {
    animation: fadeInLeft 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .animate-fade-in-right {
    animation: fadeInRight 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .animate-scale-in {
    animation: scaleIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  .hover-lift {
    transition: transform 0.3s ease;
  }

  .hover-lift:hover {
    transform: translateY(-4px);
  }

  .hover-scale {
    transition: transform 0.3s ease;
  }

  .hover-scale:hover {
    transform: scale(1.05);
  }

  .smooth-transition {
    transition: all 0.3s ease;
  }

  .glow-effect {
    animation: glow 2s ease-in-out infinite;
  }

  .pulse-effect {
    animation: pulse 2s ease-in-out infinite;
  }

  /* Loading skeleton */
  .skeleton {
    background: linear-gradient(
      90deg,
      ${BG_SURFACE} 0%,
      ${BG_HOVER} 50%,
      ${BG_SURFACE} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
  }

  /* Selection color */
  ::selection {
    background: rgba(102, 126, 234, 0.3);
    color: ${TEXT_PRIMARY};
  }

  /* Focus outline */
  :focus-visible {
    outline: 2px solid #667eea;
    outline-offset: 2px;
  }

  /* Smooth scrolling */
  html {
    scroll-behavior: smooth;
  }
`;

export default globalStyles;
