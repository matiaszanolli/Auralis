import { useRef, useEffect, useCallback, useState } from 'react';
import {
  PerformanceOptimizer,
  PerformanceConfig,
  PerformanceMetrics,
  PerformanceMonitor
} from '@/utils/performanceOptimizer';

interface OptimizationHookOptions extends Partial<PerformanceConfig> {
  enableMonitoring?: boolean;
  autoAdjustQuality?: boolean;
  onStatsUpdate?: (stats: PerformanceMetrics) => void;
}

interface OptimizationHookResult {
  optimizer: PerformanceOptimizer | null;
  stats: PerformanceMetrics;
  qualityLevel: number;
  shouldRender: () => boolean;
  optimizeData: (data: number[]) => number[];
  startRender: () => void;
  endRender: () => void;
  updateConfig: (config: Partial<PerformanceConfig>) => void;
  monitor: PerformanceMonitor | null;
}

export const useVisualizationOptimization = (
  options: OptimizationHookOptions = {}
): OptimizationHookResult => {
  const {
    enableMonitoring = true,
    autoAdjustQuality = true,
    onStatsUpdate,
    ...optimizerConfig
  } = options;

  // Stabilize optimizerConfig so it can be used as an effect dependency — the
  // rest spread creates a new object each render, but the contents are
  // primitives so JSON serialization gives a stable string key.
  const configKey = JSON.stringify(optimizerConfig);

  const optimizerRef = useRef<PerformanceOptimizer>();
  const monitorRef = useRef<PerformanceMonitor>();
  const [stats, setStats] = useState<PerformanceMetrics>({
    fps: 0,
    frameTime: 0,
    renderTime: 0,
    cpuUsage: 0,
    memoryUsage: 0,
    droppedFrames: 0,
    adaptiveQuality: 1.0,
    dataPoints: 0,
    bufferHealth: 1.0
  });
  const [qualityLevel, setQualityLevel] = useState(1.0);

  // Stable ref for onStatsUpdate so the interval effect doesn't restart on
  // every render when callers pass an inline callback (#2775).
  const onStatsUpdateRef = useRef(onStatsUpdate);
  onStatsUpdateRef.current = onStatsUpdate;

  // Initialize optimizer and monitor — re-run when config props change so the
  // optimizer is never "stuck" at mount-time values (fixes #2701).
  useEffect(() => {
    optimizerRef.current = new PerformanceOptimizer({
      adaptiveQuality: autoAdjustQuality,
      ...optimizerConfig
    });

    if (enableMonitoring) {
      monitorRef.current = optimizerRef.current.getPerformanceMonitor();
    }

    return () => {
      optimizerRef.current?.cleanup();
    };
  }, [autoAdjustQuality, enableMonitoring, configKey]);

  // Stats update loop — uses ref for onStatsUpdate to keep deps stable (#2775)
  useEffect(() => {
    if (!enableMonitoring) return;

    const interval = setInterval(() => {
      if (optimizerRef.current) {
        const currentStats = optimizerRef.current.getMetrics();
        const currentQuality = optimizerRef.current.getQualityLevel();

        setStats(currentStats);
        setQualityLevel(currentQuality);
        onStatsUpdateRef.current?.(currentStats);
      }
    }, 1000); // Update stats every second

    return () => clearInterval(interval);
  }, [enableMonitoring]);

  const shouldRender = useCallback((): boolean => {
    if (!optimizerRef.current) return true;
    return optimizerRef.current.shouldRender();
  }, []);

  const optimizeData = useCallback((data: number[]): number[] => {
    if (!optimizerRef.current) return data;

    if (enableMonitoring && monitorRef.current) {
      monitorRef.current.start('dataOptimization');
    }

    const optimized = optimizerRef.current.optimizeData(data);

    if (enableMonitoring && monitorRef.current) {
      monitorRef.current.end('dataOptimization');
    }

    return optimized;
  }, [enableMonitoring]);

  const startRender = useCallback((): void => {
    if (optimizerRef.current) {
      optimizerRef.current.startRender();
    }

    if (enableMonitoring && monitorRef.current) {
      monitorRef.current.start('render');
    }
  }, [enableMonitoring]);

  const endRender = useCallback((): void => {
    if (optimizerRef.current) {
      optimizerRef.current.endRender();
    }

    if (enableMonitoring && monitorRef.current) {
      monitorRef.current.end('render');
    }
  }, [enableMonitoring]);

  const updateConfig = useCallback((config: Partial<PerformanceConfig>): void => {
    // Note: PerformanceOptimizer uses profiles instead of dynamic config
    // To change behavior, use setProfile() instead
    if (optimizerRef.current && config) {
      // Profile-based configuration is applied at initialization
      // For runtime changes, use updateCPUUsage() or updateBufferHealth()
      if (typeof config.adaptiveQuality === 'boolean' && config.adaptiveQuality) {
        // Adaptive quality is enabled
        optimizerRef.current.updateBufferHealth(90, 100);
      }
    }
  }, []);

  return {
    optimizer: optimizerRef.current ?? null,
    stats,
    qualityLevel,
    shouldRender,
    optimizeData,
    startRender,
    endRender,
    updateConfig,
    monitor: monitorRef.current ?? null
  };
};

// Hook for managing canvas rendering with optimization
interface CanvasRenderOptions {
  width: number;
  height: number;
  enableWebGL?: boolean;
  optimization?: OptimizationHookOptions;
}

export const useOptimizedCanvas = (
  canvasRef: React.RefObject<HTMLCanvasElement>,
  renderFunction: (ctx: CanvasRenderingContext2D | WebGLRenderingContext, optimizedData: any) => void,
  data: any,
  options: CanvasRenderOptions
) => {
  const optimization = useVisualizationOptimization(options.optimization);
  const [context, setContext] = useState<CanvasRenderingContext2D | WebGLRenderingContext | null>(null);

  // Initialize canvas context
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.width = options.width;
    canvas.height = options.height;

    let ctx: CanvasRenderingContext2D | WebGLRenderingContext | null = null;

    if (options.enableWebGL) {
      ctx = (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')) as WebGLRenderingContext | null;
    }

    if (!ctx) {
      ctx = canvas.getContext('2d') as CanvasRenderingContext2D | null;
    }

    setContext(ctx as CanvasRenderingContext2D | WebGLRenderingContext | null);
  }, [canvasRef, options.width, options.height, options.enableWebGL]);

  // Optimized render function
  const render = useCallback(() => {
    if (!context || !data) return;

    // Check if we should render this frame
    if (!optimization.shouldRender()) {
      return;
    }

    optimization.startRender();

    try {
      // Optimize data if it's an array of numbers
      const optimizedData = Array.isArray(data) && typeof data[0] === 'number'
        ? optimization.optimizeData(data)
        : data;

      // Clear canvas
      if (context instanceof CanvasRenderingContext2D) {
        context.clearRect(0, 0, options.width, options.height);
      } else if (context instanceof WebGLRenderingContext) {
        context.clear(context.COLOR_BUFFER_BIT);
      }

      // Render with optimized data
      renderFunction(context, optimizedData);
    } catch (error) {
      console.error('Render error:', error);
    } finally {
      optimization.endRender();
    }
  }, [context, data, renderFunction, optimization, options.width, options.height]);

  return {
    render,
    context,
    stats: optimization.stats,
    qualityLevel: optimization.qualityLevel,
    updateConfig: optimization.updateConfig
  };
};

// Hook for WebGL-based high-performance rendering
export const useWebGLRenderer = (
  canvasRef: React.RefObject<HTMLCanvasElement>,
  options: { width: number; height: number }
) => {
  const [gl, setGL] = useState<WebGLRenderingContext | null>(null);
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.width = options.width;
    canvas.height = options.height;

    const context = (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')) as WebGLRenderingContext | null;

    if (context) {
      setGL(context);
      setIsSupported(true);

      // Set up WebGL state
      context.viewport(0, 0, options.width, options.height);
      context.clearColor(0.0, 0.0, 0.0, 1.0);
    } else {
      setIsSupported(false);
      console.warn('WebGL not supported');
    }
  }, [canvasRef, options.width, options.height]);

  const createShader = useCallback((type: number, source: string): WebGLShader | null => {
    if (!gl) return null;

    const shader = gl.createShader(type);
    if (!shader) return null;

    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compilation error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }

    return shader;
  }, [gl]);

  const createProgram = useCallback((vertexSource: string, fragmentSource: string): WebGLProgram | null => {
    if (!gl) return null;

    const vertexShader = createShader(gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = createShader(gl.FRAGMENT_SHADER, fragmentSource);

    if (!vertexShader || !fragmentShader) return null;

    const program = gl.createProgram();
    if (!program) return null;

    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program linking error:', gl.getProgramInfoLog(program));
      return null;
    }

    // Clean up shaders
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);

    return program;
  }, [gl, createShader]);

  const createBuffer = useCallback((data: Float32Array): WebGLBuffer | null => {
    if (!gl) return null;

    const buffer = gl.createBuffer();
    if (!buffer) return null;

    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);

    return buffer;
  }, [gl]);

  return {
    gl,
    isSupported,
    createShader,
    createProgram,
    createBuffer
  };
};

// Hook for managing multiple synchronized visualizations
export const useSynchronizedVisualizations = (
  visualizations: Array<{
    ref: React.RefObject<HTMLCanvasElement>;
    renderFn: (ctx: any, data: any) => void;
    data: any;
    options?: CanvasRenderOptions;
  }>
) => {
  const masterOptimization = useVisualizationOptimization({
    targetFPS: 60,
    adaptiveQuality: true,
    enableMonitoring: true
  });

  const [renderStats, setRenderStats] = useState<{ [key: string]: number }>({});

  // Store visualizations in a ref so the rAF loop doesn't restart
  // when callers pass an inline array literal.
  const visualizationsRef = useRef(visualizations);
  visualizationsRef.current = visualizations;

  // Store masterOptimization in a ref so renderAll doesn't depend on
  // the object identity (recreated each render), preventing rAF restarts (#3046).
  const masterOptRef = useRef(masterOptimization);
  masterOptRef.current = masterOptimization;

  const renderAll = useCallback(() => {
    const opt = masterOptRef.current;
    if (!opt.shouldRender()) return;

    opt.startRender();

    const frameStats: { [key: string]: number } = {};

    visualizationsRef.current.forEach((viz, index) => {
      const startTime = performance.now();

      try {
        const canvas = viz.ref.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Use master optimization for data processing
        const optimizedData = Array.isArray(viz.data) && typeof viz.data[0] === 'number'
          ? opt.optimizeData(viz.data)
          : viz.data;

        viz.renderFn(ctx, optimizedData);

        frameStats[`viz_${index}`] = performance.now() - startTime;
      } catch (error) {
        console.error(`Visualization ${index} render error:`, error);
      }
    });

    setRenderStats(frameStats);
    opt.endRender();
  }, []);

  // Auto-render loop
  useEffect(() => {
    let animationFrameId: number;

    const animate = () => {
      renderAll();
      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [renderAll]);

  return {
    renderAll,
    stats: masterOptimization.stats,
    qualityLevel: masterOptimization.qualityLevel,
    renderStats,
    updateConfig: masterOptimization.updateConfig
  };
};