import { css } from '@emotion/react';
import { colors, gradients } from '../theme/auralisTheme';

export const globalStyles = css`
  :root {
    /* Color variables */
    --bg-primary: ${colors.background.primary};
    --bg-secondary: ${colors.background.secondary};
    --bg-surface: ${colors.background.surface};
    --bg-hover: ${colors.background.hover};

    --text-primary: ${colors.text.primary};
    --text-secondary: ${colors.text.secondary};
    --text-disabled: ${colors.text.disabled};

    /* Gradient variables */
    --gradient-aurora: ${gradients.aurora};
    --gradient-sunset: ${gradients.neonSunset};
    --gradient-ocean: ${gradients.deepOcean};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: ${colors.background.primary};
    color: ${colors.text.primary};
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 12px;
    height: 12px;
  }

  ::-webkit-scrollbar-track {
    background: ${colors.background.secondary};
  }

  ::-webkit-scrollbar-thumb {
    background: ${colors.background.surface};
    border-radius: 6px;
    border: 2px solid ${colors.background.secondary};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${colors.background.hover};
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${colors.background.surface} ${colors.background.secondary};
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
    background: ${gradients.aurora};
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
      ${colors.background.surface} 0%,
      ${colors.background.hover} 50%,
      ${colors.background.surface} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
  }

  /* Selection color */
  ::selection {
    background: rgba(102, 126, 234, 0.3);
    color: ${colors.text.primary};
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
