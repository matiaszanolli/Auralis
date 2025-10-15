/**
 * useScrollAnimation Hook
 *
 * Provides intersection observer-based scroll animations for elements.
 * Elements fade in and slide up when they come into view.
 *
 * Usage:
 * ```tsx
 * const ref = useScrollAnimation();
 *
 * return <div ref={ref}>Content fades in on scroll</div>;
 * ```
 */

import { useEffect, useRef } from 'react';

interface UseScrollAnimationOptions {
  /**
   * Percentage of element visible before animation triggers (0-1)
   * @default 0.1
   */
  threshold?: number;

  /**
   * Margin around the viewport for earlier/later triggering
   * @default '0px'
   */
  rootMargin?: string;

  /**
   * CSS class to add when element enters viewport
   * @default 'animate-fade-in'
   */
  animationClass?: string;

  /**
   * Whether to stop observing after animation triggers once
   * @default true
   */
  once?: boolean;
}

/**
 * Animates a single element when it scrolls into view
 */
export const useScrollAnimation = (options: UseScrollAnimationOptions = {}) => {
  const {
    threshold = 0.1,
    rootMargin = '0px',
    animationClass = 'animate-fade-in',
    once = true
  } = options;

  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          entry.target.classList.add(animationClass);

          // Stop observing after first trigger if 'once' is true
          if (once) {
            observer.unobserve(entry.target);
          }
        } else if (!once) {
          // Remove class when out of view if not 'once'
          entry.target.classList.remove(animationClass);
        }
      },
      { threshold, rootMargin }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [threshold, rootMargin, animationClass, once]);

  return ref;
};

/**
 * Animates multiple elements with staggered timing
 *
 * Usage:
 * ```tsx
 * const { refs, setRef } = useStaggerAnimation({ delay: 100 });
 *
 * return (
 *   <>
 *     <div ref={(el) => setRef(el, 0)}>Item 1</div>
 *     <div ref={(el) => setRef(el, 1)}>Item 2</div>
 *     <div ref={(el) => setRef(el, 2)}>Item 3</div>
 *   </>
 * );
 * ```
 */
interface UseStaggerAnimationOptions {
  /**
   * Delay between each item's animation (in milliseconds)
   * @default 100
   */
  delay?: number;

  /**
   * Percentage of element visible before animation triggers (0-1)
   * @default 0.1
   */
  threshold?: number;

  /**
   * CSS class to add when element enters viewport
   * @default 'animate-fade-in'
   */
  animationClass?: string;
}

export const useStaggerAnimation = (options: UseStaggerAnimationOptions = {}) => {
  const {
    delay = 100,
    threshold = 0.1,
    animationClass = 'animate-fade-in'
  } = options;

  const refs = useRef<(HTMLElement | null)[]>([]);
  const observedIndexes = useRef<Set<number>>(new Set());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = refs.current.indexOf(entry.target as HTMLElement);

            if (index !== -1 && !observedIndexes.current.has(index)) {
              observedIndexes.current.add(index);

              setTimeout(() => {
                entry.target.classList.add(animationClass);
              }, index * delay);
            }
          }
        });
      },
      { threshold }
    );

    refs.current.forEach(ref => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, [delay, threshold, animationClass]);

  const setRef = (el: HTMLElement | null, index: number) => {
    refs.current[index] = el;
  };

  return { refs, setRef };
};

/**
 * Animates elements when they scroll into view with various animation types
 *
 * Usage:
 * ```tsx
 * const ref = useScrollAnimation({ animation: 'fade-in-up' });
 *
 * return <div ref={ref}>Content fades in from bottom</div>;
 * ```
 */
interface UseAdvancedScrollAnimationOptions extends UseScrollAnimationOptions {
  /**
   * Type of animation to apply
   * @default 'fade-in-up'
   */
  animation?: 'fade-in' | 'fade-in-up' | 'fade-in-down' | 'fade-in-left' | 'fade-in-right' | 'scale-in';
}

export const useAdvancedScrollAnimation = (options: UseAdvancedScrollAnimationOptions = {}) => {
  const {
    animation = 'fade-in-up',
    threshold = 0.1,
    rootMargin = '0px',
    once = true
  } = options;

  const animationClass = `animate-${animation}`;

  return useScrollAnimation({
    threshold,
    rootMargin,
    animationClass,
    once
  });
};

export default useScrollAnimation;
