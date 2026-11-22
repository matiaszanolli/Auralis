/**
 * StarfieldBackground - WebGL Procedural Starfield
 *
 * GPU-accelerated starfield with parallax and audio reactivity. GLSL shaders
 * live in starfield.shaders.ts; the GL resources and the draw call in
 * useStarfieldGL.ts; this component owns the render loop.
 *
 * Render loop (#5661): one rAF loop drives both the analyser sampling
 * (sampleAudioVisualization) and the draw, capped to ~30fps while animating.
 * When nothing is moving — audio inactive and settled, prefers-reduced-motion,
 * a hidden tab, or the light theme — the loop is cancelled after one static
 * frame and restarted by the corresponding change event; it never spins on
 * early returns.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useStarfieldGL } from './useStarfieldGL';
import {
  getAudioVisualization,
  sampleAudioVisualization,
  subscribeToIsActive,
} from '@/hooks/audio/audioVisualization';
import { useAudioVisualization } from '@/hooks/audio/useAudioVisualization';
import { usePrefersReducedMotion } from '@/hooks/shared/usePrefersReducedMotion';
import { useTheme } from '@/contexts/ThemeContext';

/** Draw cap while animating: the shader is ~30 noise evaluations per pixel. */
const FRAME_INTERVAL_MS = 1000 / 30;

interface StarfieldBackgroundProps {
  enableParallax?: boolean;
  parallaxStrength?: number;
  speed?: number;
  zIndex?: number;
  className?: string;
  /** Feed the starfield from the audio visualization store (default: true) */
  enableAudioReactivity?: boolean;
}

export const StarfieldBackground = ({
  enableParallax = true,
  parallaxStrength = 0.5,
  speed = 1.0,
  zIndex = -1,
  className,
  enableAudioReactivity = true,
}: StarfieldBackgroundProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Wire playback state to the visualization store this loop samples.
  useAudioVisualization(enableAudioReactivity);

  // Restart the (cancelled) loop when the store's isActive flips.
  const [audioIsActive, setAudioIsActive] = useState(getAudioVisualization().isActive);
  useEffect(
    () =>
      subscribeToIsActive(() => setAudioIsActive(getAudioVisualization().isActive)),
    []
  );

  const { mode } = useTheme();
  const prefersReducedMotion = usePrefersReducedMotion();

  const { glReady, draw, mouseRef } = useStarfieldGL(canvasRef, mode, {
    speed,
    enableParallax,
    parallaxStrength,
  });

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!enableParallax) return;
    mouseRef.current = {
      x: e.clientX / window.innerWidth,
      y: 1 - e.clientY / window.innerHeight,
    };
  }, [enableParallax, mouseRef]);

  useEffect(() => {
    if (mode === 'light' || !glReady) return;

    let rafId = 0;
    let running = false;
    let settledIdle = false; // sampler reached zero while audio was inactive
    let lastDraw = -Infinity;

    const tick = (now: number) => {
      // A hidden tab resumes through the visibilitychange restart below;
      // the loop is cancelled here, not spinning on early returns.
      if (document.hidden) {
        running = false;
        return;
      }

      const settled = sampleAudioVisualization(now);
      if (now - lastDraw >= FRAME_INTERVAL_MS) {
        draw(now);
        lastDraw = now;
      }

      if (settled && !getAudioVisualization().isActive) {
        running = false;
        settledIdle = true;
        return;
      }
      rafId = requestAnimationFrame(tick);
    };

    const start = () => {
      if (running) return;
      settledIdle = false;
      running = true;
      rafId = requestAnimationFrame(tick);
    };

    if (prefersReducedMotion) {
      // One static frame with the current store values; no animation at all.
      sampleAudioVisualization(performance.now());
      draw(performance.now());
      settledIdle = true;
    } else {
      start();
    }

    const handleVisibilityChange = () => {
      if (!document.hidden && !running && !settledIdle) start();
    };
    // Assigning canvas.width clears the drawing buffer, and draw() only resizes it inside a
    // frame, so a window resized while the loop is idle showed a blank canvas (#6036).
    const handleResize = () => {
      if (!running && !document.hidden) draw(performance.now());
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('resize', handleResize, { passive: true });
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      running = false;
      cancelAnimationFrame(rafId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [glReady, draw, handleMouseMove, prefersReducedMotion, mode, audioIsActive]);

  if (mode === 'light') return null;

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex,
        pointerEvents: 'none',
      }}
      aria-hidden="true"
    />
  );
};

export default StarfieldBackground;
