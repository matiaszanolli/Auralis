import{a as o}from"./vendor-ZvUuodmP.js";import{t as a}from"./tokens-DlAeTiWz.js";const e=o`
  :root {
    /* Color variables - mapped from tokens */
    --bg-primary: ${a.colors.bg.level1};
    --bg-secondary: ${a.colors.bg.level2};
    --bg-surface: ${a.colors.bg.level3};
    --bg-hover: ${a.colors.bg.level4};

    --text-primary: ${a.colors.text.primary};
    --text-secondary: ${a.colors.text.secondary};
    --text-disabled: ${a.colors.text.disabled};

    /* Gradient variables - from tokens */
    --gradient-aurora: ${a.gradients.aurora};
    --gradient-aqua: ${a.gradients.aqua};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: ${a.colors.bg.level0};
    color: ${a.colors.text.primary};
    font-family: ${a.typography.fontFamily.primary};
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 12px;
    height: 12px;
  }

  ::-webkit-scrollbar-track {
    background: ${a.colors.bg.level2};
  }

  ::-webkit-scrollbar-thumb {
    background: ${a.colors.bg.level3};
    border-radius: 6px;
    border: 2px solid ${a.colors.bg.level2};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${a.colors.bg.level4};
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${a.colors.bg.level3} ${a.colors.bg.level2};
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
      filter: drop-shadow(0 0 8px rgba(115, 102, 240, 0.4));
    }
    50% {
      filter: drop-shadow(0 0 16px rgba(115, 102, 240, 0.8));
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
    background: ${a.gradients.aurora};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }

  /* Scroll animation classes */
  .animate-fade-in {
    animation: fadeIn 0.6s ${a.transitions.easeOut} forwards;
  }

  .animate-fade-in-up {
    animation: fadeInUp 0.6s ${a.transitions.easeOut} forwards;
  }

  .animate-fade-in-down {
    animation: fadeInDown 0.6s ${a.transitions.easeOut} forwards;
  }

  .animate-fade-in-left {
    animation: fadeInLeft 0.6s ${a.transitions.easeOut} forwards;
  }

  .animate-fade-in-right {
    animation: fadeInRight 0.6s ${a.transitions.easeOut} forwards;
  }

  .animate-scale-in {
    animation: scaleIn 0.6s ${a.transitions.easeOut} forwards;
  }

  .hover-lift {
    transition: transform ${a.transitions.slow};
  }

  .hover-lift:hover {
    transform: translateY(-4px);
  }

  .hover-scale {
    transition: transform ${a.transitions.slow};
  }

  .hover-scale:hover {
    transform: scale(1.05);
  }

  .smooth-transition {
    transition: ${a.transitions.all};
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
      ${a.colors.bg.level3} 0%,
      ${a.colors.bg.level4} 50%,
      ${a.colors.bg.level3} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: ${a.borderRadius.sm};
  }

  /* Selection color */
  ::selection {
    background: rgba(115, 102, 240, 0.3);
    color: ${a.colors.text.primary};
  }

  /* Focus outline - using accent color */
  :focus-visible {
    outline: 2px solid ${a.colors.accent.primary};
    outline-offset: 2px;
  }

  /* Smooth scrolling */
  html {
    scroll-behavior: smooth;
  }
`;export{e as default,e as globalStyles};
