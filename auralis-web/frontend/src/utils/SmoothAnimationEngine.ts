/**
 * Smooth Animation Engine for Phase 5.3
 *
 * Provides professional-quality animations and transitions for real-time
 * audio visualization with easing functions, tweening, and performance optimization.
 */

// Easing functions for smooth animations
export const EasingFunctions = {
  linear: (t: number) => t,
  easeInQuad: (t: number) => t * t,
  easeOutQuad: (t: number) => t * (2 - t),
  easeInOutQuad: (t: number) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
  easeInCubic: (t: number) => t * t * t,
  easeOutCubic: (t: number) => (--t) * t * t + 1,
  easeInOutCubic: (t: number) => t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1,
  easeInQuart: (t: number) => t * t * t * t,
  easeOutQuart: (t: number) => 1 - (--t) * t * t * t,
  easeInOutQuart: (t: number) => t < 0.5 ? 8 * t * t * t * t : 1 - 8 * (--t) * t * t * t,
  easeInElastic: (t: number) => {
    if (t === 0 || t === 1) return t;
    const p = 0.3;
    const s = p / 4;
    return -(Math.pow(2, 10 * (t -= 1)) * Math.sin((t - s) * (2 * Math.PI) / p));
  },
  easeOutElastic: (t: number) => {
    if (t === 0 || t === 1) return t;
    const p = 0.3;
    const s = p / 4;
    return Math.pow(2, -10 * t) * Math.sin((t - s) * (2 * Math.PI) / p) + 1;
  },
  easeInBounce: (t: number) => 1 - EasingFunctions.easeOutBounce(1 - t),
  easeOutBounce: (t: number) => {
    if (t < 1 / 2.75) {
      return 7.5625 * t * t;
    } else if (t < 2 / 2.75) {
      return 7.5625 * (t -= 1.5 / 2.75) * t + 0.75;
    } else if (t < 2.5 / 2.75) {
      return 7.5625 * (t -= 2.25 / 2.75) * t + 0.9375;
    } else {
      return 7.5625 * (t -= 2.625 / 2.75) * t + 0.984375;
    }
  },
  audioTaper: (t: number) => {
    // Custom easing for audio level transitions
    return Math.pow(t, 2.2); // Similar to audio taper curve
  },
  smoothStep: (t: number) => {
    // Smooth step function for visualization transitions
    return t * t * (3 - 2 * t);
  },
};

export type EasingFunction = keyof typeof EasingFunctions;

interface AnimationTarget {
  id: string;
  startValue: number | number[];
  endValue: number | number[];
  currentValue: number | number[];
  duration: number;
  startTime: number;
  easing: EasingFunction;
  onUpdate?: (value: number | number[], progress: number) => void;
  onComplete?: () => void;
  loop?: boolean;
  pingPong?: boolean;
  delay?: number;
}

interface SpringConfig {
  tension: number;
  friction: number;
  mass: number;
}

interface SpringTarget {
  id: string;
  currentValue: number | number[];
  targetValue: number | number[];
  velocity: number | number[];
  config: SpringConfig;
  onUpdate?: (value: number | number[], velocity: number | number[]) => void;
  onComplete?: () => void;
  threshold: number; // When to consider animation complete
}

export class SmoothAnimationEngine {
  private animations = new Map<string, AnimationTarget>();
  private springs = new Map<string, SpringTarget>();
  private animationFrameId: number | null = null;
  private isRunning = false;
  private lastTime = 0;

  // Performance monitoring
  private frameCount = 0;
  private lastFpsTime = 0;
  private currentFps = 0;

  constructor() {
    this.start();
  }

  // Basic Animation Methods
  animate(
    id: string,
    startValue: number | number[],
    endValue: number | number[],
    duration: number,
    easing: EasingFunction = 'easeOutQuad',
    options: {
      onUpdate?: (value: number | number[], progress: number) => void;
      onComplete?: () => void;
      loop?: boolean;
      pingPong?: boolean;
      delay?: number;
    } = {}
  ): void {
    const animation: AnimationTarget = {
      id,
      startValue: Array.isArray(startValue) ? [...startValue] : startValue,
      endValue: Array.isArray(endValue) ? [...endValue] : endValue,
      currentValue: Array.isArray(startValue) ? [...startValue] : startValue,
      duration,
      startTime: performance.now() + (options.delay || 0),
      easing,
      onUpdate: options.onUpdate,
      onComplete: options.onComplete,
      loop: options.loop,
      pingPong: options.pingPong,
      delay: options.delay,
    };

    this.animations.set(id, animation);
  }

  // Spring Animation (for natural motion)
  animateSpring(
    id: string,
    currentValue: number | number[],
    targetValue: number | number[],
    config: Partial<SpringConfig> = {},
    options: {
      onUpdate?: (value: number | number[], velocity: number | number[]) => void;
      onComplete?: () => void;
      threshold?: number;
    } = {}
  ): void {
    const springConfig: SpringConfig = {
      tension: 170,
      friction: 26,
      mass: 1,
      ...config,
    };

    const spring: SpringTarget = {
      id,
      currentValue: Array.isArray(currentValue) ? [...currentValue] : currentValue,
      targetValue: Array.isArray(targetValue) ? [...targetValue] : targetValue,
      velocity: Array.isArray(currentValue) ? new Array(currentValue.length).fill(0) : 0,
      config: springConfig,
      onUpdate: options.onUpdate,
      onComplete: options.onComplete,
      threshold: options.threshold || 0.001,
    };

    this.springs.set(id, spring);
  }

  // Advanced Animation Methods
  animateSequence(
    id: string,
    keyframes: Array<{
      value: number | number[];
      duration: number;
      easing?: EasingFunction;
      onComplete?: () => void;
    }>
  ): void {
    let currentKeyframe = 0;

    const animateNext = () => {
      if (currentKeyframe >= keyframes.length) return;

      const keyframe = keyframes[currentKeyframe];
      const prevValue = currentKeyframe === 0 ? keyframe.value : keyframes[currentKeyframe - 1].value;

      this.animate(
        `${id}_sequence_${currentKeyframe}`,
        prevValue,
        keyframe.value,
        keyframe.duration,
        keyframe.easing || 'easeOutQuad',
        {
          onUpdate: (value, progress) => {
            // Update the main animation target
            const mainAnim = this.animations.get(id);
            if (mainAnim && mainAnim.onUpdate) {
              mainAnim.onUpdate(value, progress);
            }
          },
          onComplete: () => {
            keyframe.onComplete?.();
            currentKeyframe++;
            animateNext();
          },
        }
      );
    };

    animateNext();
  }

  // Smooth value interpolation for real-time data
  smoothValue(
    id: string,
    newValue: number | number[],
    smoothingFactor: number = 0.1,
    options: {
      onUpdate?: (value: number | number[]) => void;
      threshold?: number;
    } = {}
  ): void {
    const existing = this.springs.get(id);
    const currentValue = existing?.currentValue || newValue;

    this.animateSpring(
      id,
      currentValue,
      newValue,
      {
        tension: 50 + smoothingFactor * 100,
        friction: 20 + smoothingFactor * 10,
      },
      {
        onUpdate: options.onUpdate,
        threshold: options.threshold || 0.01,
      }
    );
  }

  // Audio-specific animations
  animateAudioLevel(
    id: string,
    currentLevel: number,
    targetLevel: number,
    isRising: boolean = true,
    options: {
      onUpdate?: (value: number | number[]) => void;
      ballistics?: 'fast' | 'medium' | 'slow';
    } = {}
  ): void {
    // Audio level ballistics (attack/release characteristics)
    const ballistics = options.ballistics || 'medium';

    const configs = {
      fast: { attack: 0.1, release: 0.3 },
      medium: { attack: 0.2, release: 0.5 },
      slow: { attack: 0.4, release: 0.8 },
    };

    const smoothing = isRising ? configs[ballistics].attack : configs[ballistics].release;

    this.smoothValue(id, targetLevel, smoothing, {
      onUpdate: options.onUpdate,
    });
  }

  animateSpectrumBars(
    id: string,
    spectrumData: number[],
    options: {
      onUpdate?: (value: number | number[]) => void;
      smoothing?: number;
      falloffRate?: number;
    } = {}
  ): void {
    const smoothing = options.smoothing || 0.2;
    const falloffRate = options.falloffRate || 0.05;

    // Get previous values for falloff calculation
    const existing = this.springs.get(id);
    const prevValues = (existing?.currentValue as number[]) || new Array(spectrumData.length).fill(0);

    // Apply falloff to create natural spectrum bar decay
    const targetValues = spectrumData.map((value, index) => {
      const prevValue = prevValues[index] || 0;
      return value > prevValue ? value : Math.max(value, prevValue - falloffRate);
    });

    this.smoothValue(id, targetValues, smoothing, {
      onUpdate: options.onUpdate,
    });
  }

  // VU Meter specific animation
  animateVUMeter(
    id: string,
    currentValue: number,
    targetValue: number,
    options: {
      onUpdate?: (value: number | number[]) => void;
      peakHold?: boolean;
      peakHoldTime?: number;
    } = {}
  ): void {
    // Classic VU meter ballistics
    const isRising = targetValue > currentValue;
    const smoothing = isRising ? 0.1 : 0.4; // Fast attack, slow release

    this.smoothValue(id, targetValue, smoothing, {
      onUpdate: options.onUpdate,
    });

    // Peak hold functionality
    if (options.peakHold && targetValue > currentValue) {
      const peakId = `${id}_peak`;
      const peakHoldTime = options.peakHoldTime || 2000; // 2 seconds

      // Set peak value
      this.animate(
        peakId,
        targetValue,
        targetValue,
        peakHoldTime,
        'linear',
        {
          onComplete: () => {
            // Fade out peak
            this.animate(
              `${peakId}_fadeout`,
              targetValue,
              0,
              500,
              'easeOutQuad'
            );
          },
        }
      );
    }
  }

  // Phase correlation animation (for goniometer)
  animatePhaseCorrelation(
    leftChannel: number[],
    rightChannel: number[],
    options: {
      onUpdate?: (points: Array<{ x: number; y: number }>) => void;
      trailLength?: number;
      smoothing?: number;
    } = {}
  ): void {
    const trailLength = options.trailLength || 50;

    // Convert L/R to X/Y coordinates for goniometer
    const points = leftChannel.map((left, index) => {
      const right = rightChannel[index] || 0;
      return {
        x: (left + right) / 2,  // Mid (sum)
        y: (left - right) / 2,  // Side (difference)
      };
    });

    // Call update callback with the trail points
    if (options.onUpdate) {
      options.onUpdate(points.slice(-trailLength));
    }
  }

  // Control Methods
  stop(id: string): void {
    this.animations.delete(id);
    this.springs.delete(id);
  }

  stopAll(): void {
    this.animations.clear();
    this.springs.clear();
  }

  pause(): void {
    this.isRunning = false;
  }

  resume(): void {
    this.isRunning = true;
    this.lastTime = performance.now();
  }

  isAnimating(id: string): boolean {
    return this.animations.has(id) || this.springs.has(id);
  }

  // Animation Engine Core
  private start(): void {
    this.isRunning = true;
    this.tick();
  }

  private tick = (currentTime?: number): void => {
    if (!this.isRunning) return;

    const time = currentTime || performance.now();
    const deltaTime = this.lastTime ? time - this.lastTime : 16.67; // Assume 60fps for first frame
    this.lastTime = time;

    // Update FPS counter
    this.updateFps(time);

    // Process tween animations
    this.updateAnimations(time);

    // Process spring animations
    this.updateSprings(deltaTime);

    // Continue the loop
    this.animationFrameId = requestAnimationFrame(this.tick);
  };

  private updateAnimations(currentTime: number): void {
    const toRemove: string[] = [];

    this.animations.forEach((animation, id) => {
      if (currentTime < animation.startTime) return; // Delayed animation

      const elapsed = currentTime - animation.startTime;
      const progress = Math.min(elapsed / animation.duration, 1);

      // Apply easing
      const easedProgress = EasingFunctions[animation.easing](progress);

      // Interpolate value
      let currentValue: number | number[];

      if (Array.isArray(animation.startValue) && Array.isArray(animation.endValue)) {
        currentValue = animation.startValue.map((start, index) => {
          const end = animation.endValue[index] as number;
          return start + (end - start) * easedProgress;
        });
      } else {
        const start = animation.startValue as number;
        const end = animation.endValue as number;
        currentValue = start + (end - start) * easedProgress;
      }

      animation.currentValue = currentValue;

      // Notify update
      animation.onUpdate?.(currentValue, progress);

      // Check completion
      if (progress >= 1) {
        if (animation.loop) {
          // Restart animation
          animation.startTime = currentTime;
          if (animation.pingPong) {
            // Swap start and end values
            [animation.startValue, animation.endValue] = [animation.endValue, animation.startValue];
          }
        } else {
          animation.onComplete?.();
          toRemove.push(id);
        }
      }
    });

    // Remove completed animations
    toRemove.forEach(id => this.animations.delete(id));
  }

  private updateSprings(deltaTime: number): void {
    const dt = Math.min(deltaTime / 1000, 0.064); // Cap at ~15fps to prevent instability
    const toRemove: string[] = [];

    this.springs.forEach((spring, id) => {
      if (Array.isArray(spring.currentValue)) {
        this.updateSpringArray(spring, dt);
      } else {
        this.updateSpringScalar(spring, dt);
      }

      // Check if spring has settled
      const isSettled = this.isSpringSettled(spring);

      spring.onUpdate?.(spring.currentValue, spring.velocity);

      if (isSettled) {
        spring.onComplete?.();
        toRemove.push(id);
      }
    });

    toRemove.forEach(id => this.springs.delete(id));
  }

  private updateSpringScalar(spring: SpringTarget, dt: number): void {
    const current = spring.currentValue as number;
    const target = spring.targetValue as number;
    const velocity = spring.velocity as number;

    // Spring physics calculation
    const displacement = current - target;
    const springForce = -spring.config.tension * displacement;
    const dampingForce = -spring.config.friction * velocity;
    const acceleration = (springForce + dampingForce) / spring.config.mass;

    // Update velocity and position
    const newVelocity = velocity + acceleration * dt;
    const newPosition = current + newVelocity * dt;

    spring.velocity = newVelocity;
    spring.currentValue = newPosition;
  }

  private updateSpringArray(spring: SpringTarget, dt: number): void {
    const current = spring.currentValue as number[];
    const target = spring.targetValue as number[];
    const velocity = spring.velocity as number[];

    const newCurrent = [...current];
    const newVelocity = [...velocity];

    for (let i = 0; i < current.length; i++) {
      const displacement = current[i] - target[i];
      const springForce = -spring.config.tension * displacement;
      const dampingForce = -spring.config.friction * velocity[i];
      const acceleration = (springForce + dampingForce) / spring.config.mass;

      newVelocity[i] = velocity[i] + acceleration * dt;
      newCurrent[i] = current[i] + newVelocity[i] * dt;
    }

    spring.velocity = newVelocity;
    spring.currentValue = newCurrent;
  }

  private isSpringSettled(spring: SpringTarget): boolean {
    if (Array.isArray(spring.currentValue)) {
      const current = spring.currentValue as number[];
      const target = spring.targetValue as number[];
      const velocity = spring.velocity as number[];

      return current.every((val, i) =>
        Math.abs(val - target[i]) < spring.threshold &&
        Math.abs(velocity[i]) < spring.threshold
      );
    } else {
      const current = spring.currentValue as number;
      const target = spring.targetValue as number;
      const velocity = spring.velocity as number;

      return Math.abs(current - target) < spring.threshold &&
             Math.abs(velocity) < spring.threshold;
    }
  }

  private updateFps(currentTime: number): void {
    this.frameCount++;

    if (currentTime - this.lastFpsTime >= 1000) {
      this.currentFps = this.frameCount;
      this.frameCount = 0;
      this.lastFpsTime = currentTime;
    }
  }

  // Public API
  getFps(): number {
    return this.currentFps;
  }

  getActiveAnimationCount(): number {
    return this.animations.size + this.springs.size;
  }

  getCurrentValue(id: string): number | number[] | null {
    const animation = this.animations.get(id);
    if (animation) return animation.currentValue;

    const spring = this.springs.get(id);
    if (spring) return spring.currentValue;

    return null;
  }

  // Cleanup
  destroy(): void {
    this.isRunning = false;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    this.animations.clear();
    this.springs.clear();
  }
}

// Global animation engine instance
export const globalAnimationEngine = new SmoothAnimationEngine();

// React hook for smooth animations
export function useSmoothAnimation() {
  const [engine] = React.useState(() => globalAnimationEngine);

  React.useEffect(() => {
    return () => {
      // Cleanup handled by global engine
    };
  }, []);

  return {
    animate: (id: string, start: number | number[], end: number | number[], duration: number, easing?: EasingFunction, options?: any) =>
      engine.animate(id, start, end, duration, easing, options),

    animateSpring: (id: string, current: number | number[], target: number | number[], config?: Partial<SpringConfig>, options?: any) =>
      engine.animateSpring(id, current, target, config, options),

    smoothValue: (id: string, value: number | number[], smoothing?: number, options?: any) =>
      engine.smoothValue(id, value, smoothing, options),

    animateAudioLevel: (id: string, current: number, target: number, isRising?: boolean, options?: any) =>
      engine.animateAudioLevel(id, current, target, isRising, options),

    animateSpectrum: (id: string, data: number[], options?: any) =>
      engine.animateSpectrumBars(id, data, options),

    animateVU: (id: string, current: number, target: number, options?: any) =>
      engine.animateVUMeter(id, current, target, options),

    stop: (id: string) => engine.stop(id),
    stopAll: () => engine.stopAll(),
    isAnimating: (id: string) => engine.isAnimating(id),
    getCurrentValue: (id: string) => engine.getCurrentValue(id),
    getFps: () => engine.getFps(),
  };
}

// Import React for the hook
import React from 'react';

export default SmoothAnimationEngine;