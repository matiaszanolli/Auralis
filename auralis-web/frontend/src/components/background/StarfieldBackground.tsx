/**
 * StarfieldBackground - WebGL Procedural Starfield
 *
 * GPU-accelerated starfield with parallax, audio reactivity, and tab-pause.
 * GLSL shaders extracted to starfield.shaders.ts.
 */

import React, { useEffect, useRef, useCallback } from 'react';
import { VERTEX_SHADER, FRAGMENT_SHADER } from './starfield.shaders';

/** Audio reactivity data from useAudioVisualization hook */
export interface AudioReactivityData {
  bass: number;
  mid: number;
  treble: number;
  loudness: number;
  peak: number;
  isActive: boolean;
}

interface StarfieldBackgroundProps {
  enableParallax?: boolean;
  parallaxStrength?: number;
  speed?: number;
  zIndex?: number;
  className?: string;
  audioReactivity?: AudioReactivityData;
}

export const StarfieldBackground = ({
  enableParallax = true,
  parallaxStrength = 0.5,
  speed = 1.0,
  zIndex = -1,
  className,
  audioReactivity,
}: StarfieldBackgroundProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const animationFrameRef = useRef<number>(0);
  const startTimeRef = useRef<number>(Date.now());
  const mouseRef = useRef<{ x: number; y: number }>({ x: 0.5, y: 0.5 });
  const isVisibleRef = useRef<boolean>(true);
  const uniformsRef = useRef<Record<string, WebGLUniformLocation | null>>({});
  const audioRef = useRef<AudioReactivityData>({
    bass: 0, mid: 0, treble: 0, loudness: 0, peak: 0, isActive: false
  });

  const compileShader = useCallback((
    gl: WebGLRenderingContext,
    source: string,
    type: number
  ): WebGLShader | null => {
    const shader = gl.createShader(type);
    if (!shader) return null;

    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('[StarfieldBackground] Shader compile error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }

    return shader;
  }, []);

  const initWebGL = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return false;

    const gl = canvas.getContext('webgl', {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      preserveDrawingBuffer: false,
    });

    if (!gl) {
      console.warn('[StarfieldBackground] WebGL not supported');
      return false;
    }

    glRef.current = gl;

    const vertexShader = compileShader(gl, VERTEX_SHADER, gl.VERTEX_SHADER);
    const fragmentShader = compileShader(gl, FRAGMENT_SHADER, gl.FRAGMENT_SHADER);

    if (!vertexShader || !fragmentShader) return false;

    const program = gl.createProgram();
    if (!program) return false;

    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('[StarfieldBackground] Program link error:', gl.getProgramInfoLog(program));
      return false;
    }

    programRef.current = program;

    // Cache uniform locations (called once, not per frame — fixes #3099)
    const uniformNames = [
      'u_time', 'u_resolution', 'u_mouse', 'u_parallaxStrength',
      'u_bass', 'u_mid', 'u_treble', 'u_loudness', 'u_peak', 'u_isPlaying',
    ];
    const locs: Record<string, WebGLUniformLocation | null> = {};
    for (const name of uniformNames) {
      locs[name] = gl.getUniformLocation(program, name);
    }
    uniformsRef.current = locs;

    const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);

    const positionLoc = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(positionLoc);
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

    return true;
  }, [compileShader]);

  const render = useCallback(() => {
    const gl = glRef.current;
    const program = programRef.current;
    const canvas = canvasRef.current;

    if (!gl || !program || !canvas || !isVisibleRef.current) {
      animationFrameRef.current = requestAnimationFrame(render);
      return;
    }

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }

    gl.useProgram(program);

    const u = uniformsRef.current;
    const timeElapsed = (Date.now() - startTimeRef.current) / 1000 * speed;
    gl.uniform1f(u.u_time, timeElapsed);
    gl.uniform2f(u.u_resolution, width, height);
    gl.uniform2f(u.u_mouse, mouseRef.current.x, mouseRef.current.y);
    gl.uniform1f(u.u_parallaxStrength, enableParallax ? parallaxStrength : 0);

    const audio = audioRef.current;
    gl.uniform1f(u.u_bass, audio.bass);
    gl.uniform1f(u.u_mid, audio.mid);
    gl.uniform1f(u.u_treble, audio.treble);
    gl.uniform1f(u.u_loudness, audio.loudness);
    gl.uniform1f(u.u_peak, audio.peak);
    gl.uniform1f(u.u_isPlaying, audio.isActive ? 1.0 : 0.0);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

    animationFrameRef.current = requestAnimationFrame(render);
  }, [enableParallax, parallaxStrength, speed]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!enableParallax) return;
    mouseRef.current = {
      x: e.clientX / window.innerWidth,
      y: 1 - e.clientY / window.innerHeight,
    };
  }, [enableParallax]);

  const handleVisibilityChange = useCallback(() => {
    isVisibleRef.current = !document.hidden;
  }, []);

  // Update audio ref directly — rAF loop reads from the ref.
  if (audioReactivity) {
    audioRef.current = audioReactivity;
  }

  useEffect(() => {
    const success = initWebGL();
    if (success) {
      animationFrameRef.current = requestAnimationFrame(render);
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelAnimationFrame(animationFrameRef.current);
      window.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('visibilitychange', handleVisibilityChange);

      const gl = glRef.current;
      if (gl && programRef.current) {
        gl.deleteProgram(programRef.current);
      }
    };
  }, [initWebGL, render, handleMouseMove, handleVisibilityChange]);

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
