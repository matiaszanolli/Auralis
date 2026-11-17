/**
 * WebGL setup for StarfieldBackground, split out of the component (#6036): compiles the shaders,
 * links the program, caches uniform locations and uploads the full-screen quad.
 */

import { VERTEX_SHADER, FRAGMENT_SHADER } from './starfield.shaders';

export interface StarfieldGL {
  gl: WebGLRenderingContext;
  program: WebGLProgram;
  buffer: WebGLBuffer | null;
  uniforms: Record<string, WebGLUniformLocation | null>;
}

const UNIFORM_NAMES = [
  'u_time', 'u_resolution', 'u_mouse', 'u_parallaxStrength',
  'u_bass', 'u_mid', 'u_treble', 'u_loudness', 'u_peak', 'u_isPlaying',
];

function compileShader(gl: WebGLRenderingContext, source: string, type: number): WebGLShader | null {
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
}

/** The canvas's WebGL state, or null when there is no context or the program does not build. */
export function initStarfieldGL(canvas: HTMLCanvasElement): StarfieldGL | null {
  const gl = canvas.getContext('webgl', {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    preserveDrawingBuffer: false,
  });

  if (!gl) {
    console.warn('[StarfieldBackground] WebGL not supported');
    return null;
  }

  const vertexShader = compileShader(gl, VERTEX_SHADER, gl.VERTEX_SHADER);
  const fragmentShader = compileShader(gl, FRAGMENT_SHADER, gl.FRAGMENT_SHADER);
  if (!vertexShader || !fragmentShader) return null;

  const program = gl.createProgram();
  if (!program) return null;

  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);

  // A linked program keeps its own copy: the shader objects are released here, not leaked on
  // every re-init (#6036).
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('[StarfieldBackground] Program link error:', gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }

  // Cache uniform locations (called once, not per frame — fixes #3099)
  const uniforms: Record<string, WebGLUniformLocation | null> = {};
  for (const name of UNIFORM_NAMES) {
    uniforms[name] = gl.getUniformLocation(program, name);
  }

  const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);

  const positionLoc = gl.getAttribLocation(program, 'a_position');
  gl.enableVertexAttribArray(positionLoc);
  gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

  return { gl, program, buffer, uniforms };
}
