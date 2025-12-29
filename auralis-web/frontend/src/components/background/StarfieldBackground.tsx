/**
 * StarfieldBackground - WebGL Procedural Starfield
 *
 * A lightweight GPU-accelerated starfield background using vanilla WebGL.
 * Features:
 * - Procedural twinkling stars with varying brightness/size
 * - Subtle nebula/galaxy clouds matching the purple/blue theme
 * - Optional parallax on mouse movement
 * - Automatically pauses when tab is hidden
 * - ~60fps at minimal GPU cost
 *
 * @component
 */

import React, { useEffect, useRef, useCallback } from 'react';

// Vertex shader - simple fullscreen quad
const VERTEX_SHADER = `
  attribute vec2 a_position;
  varying vec2 v_uv;

  void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`;

// Fragment shader - procedural starfield with nebula
const FRAGMENT_SHADER = `
  precision highp float;

  varying vec2 v_uv;

  uniform float u_time;
  uniform vec2 u_resolution;
  uniform vec2 u_mouse;
  uniform float u_parallaxStrength;

  // Theme colors (from design tokens)
  const vec3 BG_COLOR = vec3(0.043, 0.063, 0.125);      // #0B1020
  const vec3 NEBULA_PURPLE = vec3(0.451, 0.4, 0.941);   // #7366F0
  const vec3 NEBULA_CYAN = vec3(0.278, 0.839, 1.0);     // #47D6FF
  const vec3 NEBULA_PINK = vec3(0.925, 0.282, 0.6);     // #EC4899

  // Pseudo-random function
  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  // Smooth noise
  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  // Fractal Brownian Motion for nebula clouds
  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;

    for (int i = 0; i < 5; i++) {
      value += amplitude * noise(p * frequency);
      amplitude *= 0.5;
      frequency *= 2.0;
    }

    return value;
  }

  // Star layer with twinkling
  float stars(vec2 uv, float scale, float timeFactor) {
    vec2 gridUV = uv * scale;
    vec2 gridID = floor(gridUV);
    vec2 gridFract = fract(gridUV);

    float starBrightness = 0.0;

    // Check 3x3 neighborhood for smoother distribution
    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        vec2 offset = vec2(float(x), float(y));
        vec2 cellID = gridID + offset;

        // Random position within cell
        float rand1 = hash(cellID);
        float rand2 = hash(cellID + vec2(42.0, 17.0));
        vec2 starPos = offset + vec2(rand1, rand2) - gridFract;

        // Star size and brightness (varies per star)
        float starSize = hash(cellID + vec2(13.0, 37.0));

        // Only show ~30% of cells as stars
        if (starSize > 0.7) {
          float dist = length(starPos);

          // Twinkle effect (unique phase per star)
          float twinklePhase = hash(cellID + vec2(7.0, 23.0)) * 6.28318;
          float twinkleSpeed = 0.5 + hash(cellID + vec2(31.0, 41.0)) * 1.5;
          float twinkle = 0.5 + 0.5 * sin(u_time * twinkleSpeed + twinklePhase);

          // Star intensity
          float brightness = smoothstep(0.08, 0.0, dist);
          brightness *= (0.3 + 0.7 * starSize) * (0.5 + 0.5 * twinkle);

          // Larger stars have subtle glow
          if (starSize > 0.9) {
            brightness += smoothstep(0.2, 0.0, dist) * 0.15 * twinkle;
          }

          starBrightness += brightness;
        }
      }
    }

    return starBrightness;
  }

  void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 uvAspect = vec2(uv.x * aspect, uv.y);

    // Apply parallax offset based on mouse position
    vec2 parallaxOffset = (u_mouse - 0.5) * u_parallaxStrength * 0.02;
    uvAspect += parallaxOffset;

    // Base color
    vec3 color = BG_COLOR;

    // Nebula clouds (very subtle, slow-moving)
    float nebula1 = fbm(uvAspect * 2.0 + u_time * 0.02);
    float nebula2 = fbm(uvAspect * 3.0 - u_time * 0.015 + vec2(5.0, 3.0));
    float nebula3 = fbm(uvAspect * 1.5 + u_time * 0.01 + vec2(10.0, 7.0));

    // Layer nebula colors with very low opacity
    vec3 nebulaColor = vec3(0.0);
    nebulaColor += NEBULA_PURPLE * smoothstep(0.4, 0.7, nebula1) * 0.08;
    nebulaColor += NEBULA_CYAN * smoothstep(0.45, 0.75, nebula2) * 0.05;
    nebulaColor += NEBULA_PINK * smoothstep(0.5, 0.8, nebula3) * 0.03;

    // Add vignette to nebula (more visible in center)
    float vignette = 1.0 - length((uv - 0.5) * 1.5);
    vignette = smoothstep(0.0, 0.7, vignette);
    nebulaColor *= vignette;

    color += nebulaColor;

    // Multiple star layers for depth (parallax effect)
    float layer1 = stars(uvAspect + parallaxOffset * 0.5, 80.0, 1.0);   // Distant, many stars
    float layer2 = stars(uvAspect + parallaxOffset * 1.0, 40.0, 0.8);   // Medium distance
    float layer3 = stars(uvAspect + parallaxOffset * 1.5, 20.0, 0.6);   // Closer, fewer but brighter

    // Combine star layers with different intensities
    float starField = layer1 * 0.4 + layer2 * 0.6 + layer3 * 0.8;

    // Star color (slightly warm for distant, cooler for closer)
    vec3 starColor = mix(
      vec3(1.0, 0.95, 0.9),   // Warm white
      vec3(0.9, 0.95, 1.0),   // Cool white
      layer3 / (layer1 + layer2 + layer3 + 0.001)
    );

    // Add some colored stars (rare)
    float coloredStar = hash(floor(uvAspect * 50.0));
    if (coloredStar > 0.97) {
      starColor = mix(starColor, NEBULA_CYAN, 0.3);
    } else if (coloredStar > 0.94) {
      starColor = mix(starColor, NEBULA_PURPLE, 0.2);
    }

    color += starColor * starField;

    // Subtle edge darkening
    float edgeDark = 1.0 - pow(length((uv - 0.5) * 1.8), 2.0) * 0.3;
    color *= max(edgeDark, 0.7);

    gl_FragColor = vec4(color, 1.0);
  }
`;

interface StarfieldBackgroundProps {
  /** Enable parallax effect on mouse movement (default: true) */
  enableParallax?: boolean;
  /** Parallax strength 0-1 (default: 0.5) */
  parallaxStrength?: number;
  /** Animation speed multiplier (default: 1.0) */
  speed?: number;
  /** CSS z-index (default: -1) */
  zIndex?: number;
  /** Additional CSS class */
  className?: string;
}

export const StarfieldBackground: React.FC<StarfieldBackgroundProps> = ({
  enableParallax = true,
  parallaxStrength = 0.5,
  speed = 1.0,
  zIndex = -1,
  className,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glRef = useRef<WebGLRenderingContext | null>(null);
  const programRef = useRef<WebGLProgram | null>(null);
  const animationFrameRef = useRef<number>(0);
  const startTimeRef = useRef<number>(Date.now());
  const mouseRef = useRef<{ x: number; y: number }>({ x: 0.5, y: 0.5 });
  const isVisibleRef = useRef<boolean>(true);

  // Compile shader
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

  // Initialize WebGL
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

    // Compile shaders
    const vertexShader = compileShader(gl, VERTEX_SHADER, gl.VERTEX_SHADER);
    const fragmentShader = compileShader(gl, FRAGMENT_SHADER, gl.FRAGMENT_SHADER);

    if (!vertexShader || !fragmentShader) return false;

    // Create program
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

    // Create fullscreen quad
    const vertices = new Float32Array([
      -1, -1,
       1, -1,
      -1,  1,
       1,  1,
    ]);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);

    const positionLoc = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(positionLoc);
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

    return true;
  }, [compileShader]);

  // Render frame
  const render = useCallback(() => {
    const gl = glRef.current;
    const program = programRef.current;
    const canvas = canvasRef.current;

    if (!gl || !program || !canvas || !isVisibleRef.current) {
      animationFrameRef.current = requestAnimationFrame(render);
      return;
    }

    // Update canvas size if needed
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    }

    gl.useProgram(program);

    // Set uniforms
    const timeElapsed = (Date.now() - startTimeRef.current) / 1000 * speed;
    gl.uniform1f(gl.getUniformLocation(program, 'u_time'), timeElapsed);
    gl.uniform2f(gl.getUniformLocation(program, 'u_resolution'), width, height);
    gl.uniform2f(gl.getUniformLocation(program, 'u_mouse'), mouseRef.current.x, mouseRef.current.y);
    gl.uniform1f(
      gl.getUniformLocation(program, 'u_parallaxStrength'),
      enableParallax ? parallaxStrength : 0
    );

    // Draw
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

    animationFrameRef.current = requestAnimationFrame(render);
  }, [enableParallax, parallaxStrength, speed]);

  // Handle mouse movement
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!enableParallax) return;
    mouseRef.current = {
      x: e.clientX / window.innerWidth,
      y: 1 - e.clientY / window.innerHeight, // Invert Y for WebGL
    };
  }, [enableParallax]);

  // Handle visibility change
  const handleVisibilityChange = useCallback(() => {
    isVisibleRef.current = !document.hidden;
  }, []);

  // Initialize and cleanup
  useEffect(() => {
    const success = initWebGL();
    if (success) {
      animationFrameRef.current = requestAnimationFrame(render);
    }

    // Event listeners
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelAnimationFrame(animationFrameRef.current);
      window.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('visibilitychange', handleVisibilityChange);

      // Cleanup WebGL resources
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
