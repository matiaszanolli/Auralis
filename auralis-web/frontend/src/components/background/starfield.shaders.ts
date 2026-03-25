/**
 * GLSL shaders for StarfieldBackground WebGL renderer.
 *
 * Extracted from StarfieldBackground.tsx to keep the component under 300 lines.
 */

// Vertex shader - simple fullscreen quad
export const VERTEX_SHADER = `
  attribute vec2 a_position;
  varying vec2 v_uv;

  void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`;

// Fragment shader - procedural starfield with vibrant nebulae and aurora
// Now with audio reactivity for immersive playback experience
export const FRAGMENT_SHADER = `
  precision highp float;

  varying vec2 v_uv;

  uniform float u_time;
  uniform vec2 u_resolution;
  uniform vec2 u_mouse;
  uniform float u_parallaxStrength;

  // Audio reactivity uniforms (all normalized 0-1)
  uniform float u_bass;      // Low frequency energy (20-250Hz)
  uniform float u_mid;       // Mid frequency energy (250-4000Hz)
  uniform float u_treble;    // High frequency energy (4000-20000Hz)
  uniform float u_loudness;  // Overall audio energy
  uniform float u_peak;      // Transient/beat detection
  uniform float u_isPlaying; // 1.0 when audio playing, 0.0 when stopped

  // Theme colors (vibrant cosmic palette)
  const vec3 BG_COLOR = vec3(0.035, 0.05, 0.10);        // Deep space blue-black
  const vec3 NEBULA_VIOLET = vec3(0.45, 0.35, 0.95);    // Rich violet
  const vec3 NEBULA_PURPLE = vec3(0.6, 0.2, 0.8);       // Deep purple
  const vec3 NEBULA_CYAN = vec3(0.2, 0.8, 1.0);         // Electric cyan
  const vec3 NEBULA_TEAL = vec3(0.1, 0.6, 0.7);         // Deep teal
  const vec3 NEBULA_PINK = vec3(0.9, 0.3, 0.6);         // Hot pink
  const vec3 NEBULA_MAGENTA = vec3(0.8, 0.2, 0.5);      // Magenta
  const vec3 AURORA_GREEN = vec3(0.2, 0.9, 0.4);        // Aurora green

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
  float fbm(vec2 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;

    for (int i = 0; i < 6; i++) {
      if (i >= octaves) break;
      value += amplitude * noise(p * frequency);
      amplitude *= 0.5;
      frequency *= 2.0;
    }

    return value;
  }

  // Ridged noise for dramatic nebula edges
  float ridgedNoise(vec2 p) {
    return 1.0 - abs(noise(p) * 2.0 - 1.0);
  }

  // Ridged FBM for more dramatic cloud formations
  float ridgedFbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;

    for (int i = 0; i < 5; i++) {
      value += amplitude * ridgedNoise(p * frequency);
      amplitude *= 0.5;
      frequency *= 2.0;
    }

    return value;
  }

  // Aurora wave function
  float aurora(vec2 uv, float time) {
    float wave = 0.0;

    // Multiple wave layers with different frequencies
    wave += sin(uv.x * 3.0 + time * 0.3 + sin(uv.x * 1.5 + time * 0.2) * 2.0) * 0.5;
    wave += sin(uv.x * 5.0 - time * 0.4 + cos(uv.x * 2.0 + time * 0.15) * 1.5) * 0.3;
    wave += sin(uv.x * 8.0 + time * 0.5 + sin(uv.x * 3.0 - time * 0.25) * 1.0) * 0.2;

    // Vertical position with wave distortion
    float auroraY = 0.7 + wave * 0.08;
    float dist = abs(uv.y - auroraY);

    // Sharp falloff for aurora bands
    float intensity = smoothstep(0.15, 0.0, dist);
    intensity *= smoothstep(0.0, 0.3, uv.y); // Fade at bottom
    intensity *= smoothstep(1.0, 0.6, uv.y); // Fade at top

    // Add shimmer
    float shimmer = noise(vec2(uv.x * 20.0 + time * 2.0, uv.y * 5.0));
    intensity *= 0.7 + 0.3 * shimmer;

    return intensity;
  }

  // Star layer with twinkling
  float stars(vec2 uv, float scale, float timeFactor) {
    vec2 gridUV = uv * scale;
    vec2 gridID = floor(gridUV);
    vec2 gridFract = fract(gridUV);

    float starBrightness = 0.0;

    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        vec2 offset = vec2(float(x), float(y));
        vec2 cellID = gridID + offset;

        float rand1 = hash(cellID);
        float rand2 = hash(cellID + vec2(42.0, 17.0));
        vec2 starPos = offset + vec2(rand1, rand2) - gridFract;

        float starSize = hash(cellID + vec2(13.0, 37.0));

        if (starSize > 0.7) {
          float dist = length(starPos);

          float twinklePhase = hash(cellID + vec2(7.0, 23.0)) * 6.28318;
          float twinkleSpeed = 0.5 + hash(cellID + vec2(31.0, 41.0)) * 1.5;
          float twinkle = 0.5 + 0.5 * sin(u_time * twinkleSpeed + twinklePhase);

          float brightness = smoothstep(0.08, 0.0, dist);
          brightness *= (0.3 + 0.7 * starSize) * (0.5 + 0.5 * twinkle);

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

    // Parallax offset
    vec2 parallaxOffset = (u_mouse - 0.5) * u_parallaxStrength * 0.02;
    uvAspect += parallaxOffset;

    // === FORWARD DRIFT (constant when playing) ===
    // Smooth, consistent forward motion through space during playback
    // Speed is constant - no modulation from audio to avoid jerky motion
    float baseDriftSpeed = 0.025 * u_isPlaying;
    uvAspect.y -= u_time * baseDriftSpeed;

    // Audio reactivity factors (smoothed for visual appeal)
    float audioBoost = 1.0 + u_loudness * 0.3;              // Overall brightness boost
    float bassPulse = 1.0 + u_bass * 0.25 + u_peak * 0.4;   // Bass/beat pulse
    float trebleSparkle = 1.0 + u_treble * 0.5;             // Star twinkle enhancement
    float midGlow = 1.0 + u_mid * 0.35;                     // Aurora/nebula glow

    // Base deep space color (slightly brighter when loud)
    vec3 color = BG_COLOR * (1.0 + u_loudness * 0.15);

    // === NEBULA LAYERS (rich, colorful gas clouds) ===

    // Large-scale nebula structure (slow moving)
    float nebula1 = fbm(uvAspect * 1.2 + u_time * 0.015, 6);
    float nebula2 = fbm(uvAspect * 1.8 - u_time * 0.012 + vec2(5.0, 3.0), 5);
    float nebula3 = ridgedFbm(uvAspect * 2.5 + u_time * 0.008 + vec2(10.0, 7.0));

    // Medium-scale detail
    float detail1 = fbm(uvAspect * 4.0 + u_time * 0.02, 4);
    float detail2 = fbm(uvAspect * 6.0 - u_time * 0.018 + vec2(3.0, 8.0), 4);

    // Combine nebula with rich colors
    vec3 nebulaColor = vec3(0.0);

    // Primary violet/purple nebula (large, dominant)
    float purpleIntensity = smoothstep(0.35, 0.65, nebula1) * smoothstep(0.3, 0.6, detail1);
    nebulaColor += mix(NEBULA_VIOLET, NEBULA_PURPLE, detail1) * purpleIntensity * 0.25;

    // Cyan/teal accents (mid-layer)
    float cyanIntensity = smoothstep(0.4, 0.7, nebula2) * smoothstep(0.35, 0.65, detail2);
    nebulaColor += mix(NEBULA_CYAN, NEBULA_TEAL, detail2) * cyanIntensity * 0.18;

    // Pink/magenta highlights (smaller, brighter spots)
    float pinkIntensity = smoothstep(0.5, 0.8, nebula3) * smoothstep(0.45, 0.75, detail1);
    nebulaColor += mix(NEBULA_PINK, NEBULA_MAGENTA, nebula3) * pinkIntensity * 0.15;

    // Add depth variation (nebula brighter in certain regions)
    float depthMask = fbm(uvAspect * 0.8 + vec2(20.0, 15.0), 3);
    nebulaColor *= 0.6 + 0.8 * smoothstep(0.3, 0.7, depthMask);

    // Subtle breathing/pulsing (enhanced by bass)
    float breathe = 0.9 + 0.1 * sin(u_time * 0.3);
    breathe *= bassPulse; // Bass makes nebula pulse
    nebulaColor *= breathe;

    // Audio boost to nebula intensity
    nebulaColor *= audioBoost;

    // === AURORA EFFECT (flowing bands in upper region) ===
    float auroraIntensity = aurora(uv, u_time);

    // Aurora color gradient (green to cyan to purple)
    vec3 auroraColor = mix(AURORA_GREEN, NEBULA_CYAN, smoothstep(0.0, 0.5, auroraIntensity));
    auroraColor = mix(auroraColor, NEBULA_VIOLET, smoothstep(0.5, 1.0, auroraIntensity));

    // Add aurora to scene (enhanced by mid frequencies - vocals/instruments)
    float auroraMultiplier = 0.12 * midGlow;
    nebulaColor += auroraColor * auroraIntensity * auroraMultiplier;

    // === VIGNETTE (focus nebula in interesting regions) ===
    // Offset vignette slightly to upper-left for visual interest
    vec2 vignetteCenter = vec2(0.45, 0.55);
    float vignette = 1.0 - length((uv - vignetteCenter) * vec2(1.3, 1.1));
    vignette = smoothstep(-0.1, 0.6, vignette);
    nebulaColor *= 0.4 + 0.6 * vignette;

    color += nebulaColor;

    // === STAR LAYERS (enhanced by treble/high frequencies) ===
    float layer1 = stars(uvAspect + parallaxOffset * 0.5, 80.0, 1.0);
    float layer2 = stars(uvAspect + parallaxOffset * 1.0, 40.0, 0.8);
    float layer3 = stars(uvAspect + parallaxOffset * 1.5, 20.0, 0.6);

    // Star brightness enhanced by treble (cymbals, hi-hats make stars sparkle)
    float starField = (layer1 * 0.4 + layer2 * 0.6 + layer3 * 0.8) * trebleSparkle;

    // Star colors (warmer distant, cooler close)
    vec3 starColor = mix(
      vec3(1.0, 0.95, 0.9),
      vec3(0.9, 0.95, 1.0),
      layer3 / (layer1 + layer2 + layer3 + 0.001)
    );

    // Colored stars (more frequent)
    float coloredStar = hash(floor(uvAspect * 50.0));
    if (coloredStar > 0.95) {
      starColor = mix(starColor, NEBULA_CYAN, 0.4);
    } else if (coloredStar > 0.90) {
      starColor = mix(starColor, NEBULA_VIOLET, 0.3);
    } else if (coloredStar > 0.87) {
      starColor = mix(starColor, NEBULA_PINK, 0.25);
    }

    color += starColor * starField;

    // === FINAL ADJUSTMENTS ===
    // Subtle edge darkening
    float edgeDark = 1.0 - pow(length((uv - 0.5) * 1.6), 2.0) * 0.25;
    color *= max(edgeDark, 0.75);

    // Slight overall glow in nebula areas
    color += nebulaColor * 0.05;

    // === AUDIO PEAK FLASH ===
    // Brief brightness flash on transients (drums, attacks)
    color += vec3(0.03, 0.02, 0.04) * u_peak * u_isPlaying;

    // Subtle overall contrast boost when audio is playing
    float contrastBoost = 1.0 + u_isPlaying * u_loudness * 0.1;
    color = mix(vec3(0.5), color, contrastBoost);

    gl_FragColor = vec4(color, 1.0);
  }
`;
