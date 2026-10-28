import { useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function reducedMotionRequested(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia(QUERY).matches;
}

/**
 * True while the user's system asks for reduced motion (#5676).
 *
 * The global CSS rule only neutralises CSS animations and transitions; a WebGL render loop or a
 * timer that swaps content on its own needs to be switched off in code. Follows live changes to
 * the preference. False wherever matchMedia is unavailable.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(reducedMotionRequested);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined;
    const media = window.matchMedia(QUERY);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    setReduced(media.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  return reduced;
}
