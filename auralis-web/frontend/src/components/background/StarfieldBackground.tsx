/**
 * StarfieldBackground - WebGL Procedural Starfield
 *
 * GPU-accelerated starfield with parallax and audio reactivity. GLSL shaders
 * extracted to starfield.shaders.ts.
 *
 * Render loop (#5661): one rAF loop drives both the analyser sampling
 * (sampleAudioVisualization) and the draw, capped to ~30fps while animating.
 * When nothing is moving — audio inactive and settled, prefers-reduced-motion,
 * a hidden tab, or the light theme — the loop is cancelled after one static
 * frame and restarted by the corresponding change event; it never spins on
 * early returns.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { initStarfieldGL } from './starfieldGL';
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
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const bufferRef = useRef<WebGLBuffer | null>(null);
  const uniformsRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  const startTimeRef = useRef<number>(Date.now());
  const mouseRef = useRef<{ x: number; y: number }>({ x: 0.5, y: 0.5 });

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

  const initWebGL = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return false;
    const resources = initStarfieldGL(canvas);
    if (!resources) return false;
    glRef.current = resources.gl;
    programRef.current = resources.program;
    bufferRef.current = resources.buffer;
    uniformsRef.current = resources.uniforms;
    return true;
  }, []);

  const draw = useCallback((now: number) => {
    const gl = glRef.current;
    const program = programRef.current;
    const canvas = canvasRef.current;
    if (!gl || !program || !canvas) return;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }

    gl.useProgram(program);

    const u = uniformsRef.current;
    const timeElapsed = (now - startTimeRef.current) / 1000 * speed;
    gl.uniform1f(u.u_time, timeElapsed);
    gl.uniform2f(u.u_resolution, width, height);
    gl.uniform2f(u.u_mouse, mouseRef.current.x, mouseRef.current.y);
    gl.uniform1f(u.u_parallaxStrength, enableParallax ? parallaxStrength : 0);

    const audio = getAudioVisualization();
    gl.uniform1f(u.u_bass, audio.bass);
    gl.uniform1f(u.u_mid, audio.mid);
    gl.uniform1f(u.u_treble, audio.treble);
    gl.uniform1f(u.u_loudness, audio.loudness);
    gl.uniform1f(u.u_peak, audio.peak);
    gl.uniform1f(u.u_isPlaying, audio.isActive ? 1.0 : 0.0);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }, [enableParallax, parallaxStrength, speed]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!enableParallax) return;
    mouseRef.current = {
      x: e.clientX / window.innerWidth,
      y: 1 - e.clientY / window.innerHeight,
    };
  }, [enableParallax]);

  // GL resources: created once per context (a light/dark switch or a restored context), NOT on
  // every play/pause the render loop below restarts for (#6036). Context loss is handled here:
  // the browser can drop the context under GPU pressure, after which every call is a silent
  // no-op until it is restored and the program and buffer rebuilt.
  const [glReady, setGlReady] = useState(false);
  useEffect(() => {
    // The light theme composites the canvas at 3.5% opacity for the same GPU
    // cost — skip the context entirely there (#5661).
    if (mode === 'light') return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const release = () => {
      const gl = glRef.current;
      if (gl && programRef.current) gl.deleteProgram(programRef.current);
      if (gl && bufferRef.current) gl.deleteBuffer(bufferRef.current);
      programRef.current = null;
      bufferRef.current = null;
    };
    const handleLost = (event: Event) => {
      event.preventDefault(); // without this the context is never restored
      setGlReady(false);
      programRef.current = null;
      bufferRef.current = null;
    };
    const handleRestored = () => setGlReady(initWebGL());

    canvas.addEventListener('webglcontextlost', handleLost);
    canvas.addEventListener('webglcontextrestored', handleRestored);
    setGlReady(initWebGL());

    return () => {
      canvas.removeEventListener('webglcontextlost', handleLost);
      canvas.removeEventListener('webglcontextrestored', handleRestored);
      release();
      setGlReady(false);
    };
  }, [initWebGL, mode]);

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
