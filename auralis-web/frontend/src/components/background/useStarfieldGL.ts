/**
 * The starfield's WebGL resources and its draw call (#6703).
 *
 * Owns the context, program, buffer and uniform locations for one canvas,
 * their context-loss / restore lifecycle (#6036), and `draw(now)`, which
 * writes this frame's uniforms (time, resolution, parallax mouse, the audio
 * visualization store) and renders. The render loop that decides *when* to
 * draw stays in StarfieldBackground.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ThemeMode } from '@/theme/semanticTheme';
import { getAudioVisualization } from '@/hooks/audio/audioVisualization';
import { initStarfieldGL } from './starfieldGL';

interface StarfieldGLOptions {
  speed: number;
  enableParallax: boolean;
  parallaxStrength: number;
}

export function useStarfieldGL(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  mode: ThemeMode,
  { speed, enableParallax, parallaxStrength }: StarfieldGLOptions
) {
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const bufferRef = useRef<WebGLBuffer | null>(null);
  const uniformsRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  const startTimeRef = useRef<number>(Date.now());
  /** Normalized pointer position for parallax, written by the caller's mousemove listener. */
  const mouseRef = useRef<{ x: number; y: number }>({ x: 0.5, y: 0.5 });

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
  }, [canvasRef]);

  // GL resources: created once per context (a light/dark switch or a restored context), NOT on
  // every play/pause the render loop restarts for (#6036). Context loss is handled here: the
  // browser can drop the context under GPU pressure, after which every call is a silent no-op
  // until it is restored and the program and buffer rebuilt.
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
  }, [initWebGL, mode, canvasRef]);

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
    gl.uniform1f(u.u_time, (now - startTimeRef.current) / 1000 * speed);
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
  }, [canvasRef, enableParallax, parallaxStrength, speed]);

  return { glReady, draw, mouseRef };
}
