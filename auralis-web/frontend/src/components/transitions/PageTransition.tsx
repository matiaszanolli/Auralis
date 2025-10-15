/**
 * PageTransition Component
 *
 * Provides smooth page transition animations using framer-motion.
 * Features fade + slide animations with 300ms duration and smooth easing.
 *
 * Usage:
 * ```tsx
 * <AnimatePresence mode="wait">
 *   <PageTransition key={location.pathname}>
 *     <YourPageContent />
 *   </PageTransition>
 * </AnimatePresence>
 * ```
 */

import React from 'react';
import { motion } from 'framer-motion';

interface PageTransitionProps {
  children: React.ReactNode;
}

// Animation variants for smooth page transitions
const pageVariants = {
  initial: {
    opacity: 0,
    x: -20,
  },
  animate: {
    opacity: 1,
    x: 0,
  },
  exit: {
    opacity: 0,
    x: 20,
  },
};

// Smooth cubic-bezier easing
const pageTransition = {
  duration: 0.3,
  ease: [0.4, 0, 0.2, 1], // Material Design standard easing
};

/**
 * PageTransition Component
 *
 * Wraps page content with smooth fade and slide animations.
 * Use with AnimatePresence for enter/exit animations.
 */
export const PageTransition: React.FC<PageTransitionProps> = ({ children }) => {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
      transition={pageTransition}
      style={{
        width: '100%',
        height: '100%',
      }}
    >
      {children}
    </motion.div>
  );
};

// Variant: Fade only (no slide)
export const FadeTransition: React.FC<PageTransitionProps> = ({ children }) => {
  const fadeVariants = {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  };

  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={fadeVariants}
      transition={pageTransition}
      style={{
        width: '100%',
        height: '100%',
      }}
    >
      {children}
    </motion.div>
  );
};

// Variant: Scale + Fade
export const ScaleTransition: React.FC<PageTransitionProps> = ({ children }) => {
  const scaleVariants = {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  };

  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={scaleVariants}
      transition={pageTransition}
      style={{
        width: '100%',
        height: '100%',
      }}
    >
      {children}
    </motion.div>
  );
};

export default PageTransition;
