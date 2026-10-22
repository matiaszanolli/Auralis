import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';

/**
 * Global animation keyframes. Split out of globalStyles.ts (#5841).
 */
export const keyframeStyles = css`
  /* Animation keyframes */
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }

  /* Spinner rotation — was injected per-render via inline <style> in
     BufferingIndicator (#4188). */
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Connection-status ring pulse. Defined once here (uniquely named to avoid
     colliding with the opacity 'pulse' above); the runtime status colour is fed
     via the --pulse-shadow-start/--pulse-shadow-end custom properties set on the
     element, instead of re-injecting a colour-interpolated <style> on every
     status change (#4188). */
  @keyframes connection-status-pulse {
    0% {
      box-shadow: 0 0 0 0 var(--pulse-shadow-start, transparent);
    }
    70% {
      box-shadow: 0 0 0 10px var(--pulse-shadow-end, transparent);
    }
    100% {
      box-shadow: 0 0 0 0 var(--pulse-shadow-end, transparent);
    }
  }

  @keyframes glow {
    0%, 100% {
      filter: drop-shadow(0 0 8px ${tokens.colors.opacityScale.accent.veryStrong});
    }
    50% {
      filter: drop-shadow(0 0 16px ${tokens.colors.opacityScale.accent.vivid});
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
`;
