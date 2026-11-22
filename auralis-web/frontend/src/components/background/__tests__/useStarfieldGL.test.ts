/**
 * useStarfieldGL (#6703): GL resource lifecycle and the per-frame draw.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { initStarfieldGL } from '@/components/background/starfieldGL';
import { useStarfieldGL } from '@/components/background/useStarfieldGL';

vi.mock('@/components/background/starfieldGL', () => ({ initStarfieldGL: vi.fn() }));

const gl = {
  useProgram: vi.fn(),
  uniform1f: vi.fn(),
  uniform2f: vi.fn(),
  viewport: vi.fn(),
  drawArrays: vi.fn(),
  deleteProgram: vi.fn(),
  deleteBuffer: vi.fn(),
  TRIANGLE_STRIP: 5,
};
const program = { name: 'program' };
const buffer = { name: 'buffer' };
const uniforms = { u_parallaxStrength: 'loc-parallax' } as unknown as Record<string, WebGLUniformLocation | null>;

function canvasRef() {
  return { current: document.createElement('canvas') };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(initStarfieldGL).mockReturnValue({
    gl: gl as unknown as WebGLRenderingContext,
    program: program as unknown as WebGLProgram,
    buffer: buffer as unknown as WebGLBuffer,
    uniforms,
  } as ReturnType<typeof initStarfieldGL>);
});

describe('useStarfieldGL', () => {
  it('never creates a context in the light theme', () => {
    const { result } = renderHook(() =>
      useStarfieldGL(canvasRef(), 'light', { speed: 1, enableParallax: true, parallaxStrength: 0.5 })
    );
    expect(initStarfieldGL).not.toHaveBeenCalled();
    expect(result.current.glReady).toBe(false);
  });

  it('draws with parallax zeroed when disabled, and releases program and buffer on unmount', () => {
    const { result, unmount } = renderHook(() =>
      useStarfieldGL(canvasRef(), 'dark', { speed: 1, enableParallax: false, parallaxStrength: 0.5 })
    );
    expect(result.current.glReady).toBe(true);

    result.current.draw(performance.now());
    expect(gl.uniform1f).toHaveBeenCalledWith('loc-parallax', 0);
    expect(gl.drawArrays).toHaveBeenCalledWith(gl.TRIANGLE_STRIP, 0, 4);

    unmount();
    expect(gl.deleteProgram).toHaveBeenCalledWith(program);
    expect(gl.deleteBuffer).toHaveBeenCalledWith(buffer);
  });

  it('a failed init leaves the hook not ready and draw a no-op', () => {
    vi.mocked(initStarfieldGL).mockReturnValue(null);
    const { result } = renderHook(() =>
      useStarfieldGL(canvasRef(), 'dark', { speed: 1, enableParallax: true, parallaxStrength: 0.5 })
    );
    expect(result.current.glReady).toBe(false);
    result.current.draw(performance.now());
    expect(gl.drawArrays).not.toHaveBeenCalled();
  });
});
