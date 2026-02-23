/** GLSL Shaders for the Jarvis Orb — Digital Light Artifacts (Red & Blue) */

export const vertexShader = /* glsl */ `
  out vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`

export const fragmentShader = /* glsl */ `
  precision highp float;

  in vec2 vUv;
  out vec4 fragColor;

  uniform float u_time;
  uniform vec2  u_resolution;
  uniform float u_audioLevel;
  uniform vec3  u_color;
  uniform float u_deform;
  uniform float u_glow;
  uniform float u_state;

  #define PI  3.14159265359
  #define TAU 6.28318530718

  // ── Palette — digital red & blue ──────────────────────────
  const vec3 RED  = vec3(1.0, 0.08, 0.22);
  const vec3 BLUE = vec3(0.1, 0.35, 1.0);
  const vec3 CYAN = vec3(0.0, 0.82, 1.0);

  // ── Utilities ─────────────────────────────────────────────
  mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
  float hash(float n) { return fract(sin(n) * 43758.5453123); }

  // ── 1. Core — dual-color energy center ────────────────────
  vec3 core(vec2 uv) {
    float dist = length(uv);
    float angle = atan(uv.y, uv.x);

    // Angular color split: red smoothly transitions to blue around center
    float split = sin(angle + u_time * 0.4) * 0.5 + 0.5;
    vec3 coreColor = mix(RED, BLUE, split);

    // White-hot center
    float hot = 0.015 / (dist * dist + 0.012);

    // Colored mid-range glow
    float mid = 0.05 / (dist + 0.08);

    // Wide ambient haze
    float haze = exp(-dist * dist * 4.5) * 0.35;

    float breath = 1.0 + u_audioLevel * 0.6;

    // Listening: rapid pulse
    float pulse = 1.0;
    if (u_state > 0.5 && u_state < 1.5) {
      pulse = 0.85 + 0.15 * sin(u_time * 15.0);
    }

    vec3 col = vec3(0.0);
    col += vec3(1.0, 0.97, 0.95) * hot * 0.4 * breath * pulse;
    col += coreColor * mid * 0.7 * breath * pulse;
    col += coreColor * haze * u_glow;

    return col;
  }

  // ── 2. Chromatic orbit — ring with red/blue separation ────
  vec3 chromaOrbit(vec2 uv, float R, float tilt, float speed,
                   float thickness, float idx) {
    float t = u_time;

    // Rotate + squish for elliptical shape
    vec2 ruv = rot2(t * speed * 0.5 + idx * 1.1) * uv;
    float squeeze = 0.5 + 0.5 * abs(sin(tilt));
    squeeze = max(squeeze, 0.15);
    ruv.y /= squeeze;

    // Thinking: speed up orbits
    if (u_state > 1.5 && u_state < 2.5) {
      ruv = rot2(t * 1.2 + idx * 0.5) * ruv;
    }

    // Chromatic offset: red shifted one way, blue the other
    float chrOff = 0.012 * (1.0 + u_audioLevel * 0.5);
    float offAngle = t * 0.2 + idx;
    vec2 rOff = vec2(cos(offAngle), sin(offAngle)) * chrOff;

    float distR = length(ruv + rOff);
    float distB = length(ruv - rOff);

    float lw = thickness * (1.0 + u_audioLevel * 0.6);

    // Gaussian ring profile
    float ringR = exp(-(distR - R) * (distR - R) / (lw * lw));
    float ringB = exp(-(distB - R) * (distB - R) / (lw * lw));

    // Arc mask: partial ring visibility
    float angle = atan(ruv.y, ruv.x);
    float arc = smoothstep(0.0, 0.4, sin(angle * 1.5 + idx * 2.0 + t * 0.3))
              * smoothstep(-0.1, 0.2, sin(angle * 0.7 - idx + t * 0.15));

    // Traveling data dot along the ring
    float dotSpeed = 1.0 + idx * 0.4;
    if (u_state > 1.5 && u_state < 2.5) dotSpeed *= 2.5;
    float dotAngle = t * dotSpeed + idx * TAU / 6.0;
    vec2 dotPos = vec2(cos(dotAngle), sin(dotAngle) / squeeze) * R;
    float dotDist = length(ruv - dotPos);
    float dot1 = 0.001 / (dotDist * dotDist + 0.0005);

    // Second dot on opposite side
    vec2 dot2Pos = vec2(cos(dotAngle + PI), sin(dotAngle + PI) / squeeze) * R;
    float dot2Dist = length(ruv - dot2Pos);
    float dot2 = 0.0005 / (dot2Dist * dot2Dist + 0.0003);

    vec3 dotColor = mix(CYAN, vec3(1.0), 0.5);

    vec3 col = vec3(0.0);
    col += RED * ringR * arc * 0.55;
    col += BLUE * ringB * arc * 0.55;
    col += dotColor * dot1 * 0.15;
    col += dotColor * dot2 * 0.08;

    return col;
  }

  // ── 3. Data particles — orbiting fragments ────────────────
  vec3 dataParticles(vec2 uv) {
    vec3 col = vec3(0.0);

    for (float i = 0.0; i < 18.0; i++) {
      float angle = hash(i * 3.7) * TAU + u_time * (0.08 + hash(i * 5.1) * 0.12);
      float r = 0.15 + hash(i * 2.3) * 0.55;
      r += sin(u_time * 0.4 + i * 1.3) * 0.06;

      // Thinking: orbit faster, closer
      if (u_state > 1.5 && u_state < 2.5) {
        angle += u_time * 0.8;
        r *= 0.4 + 0.6 * abs(sin(u_time * 1.5 + i * 0.7));
      }
      // Speaking: expand with audio
      if (u_state > 2.5) {
        r += u_audioLevel * 0.2;
      }

      vec2 pos = vec2(cos(angle), sin(angle)) * r;
      float d = length(uv - pos);
      float glow = 0.0003 / (d * d + 0.0002);

      // Alternate red, blue, cyan
      vec3 pColor;
      float ci = mod(i, 3.0);
      if (ci < 1.0) pColor = RED;
      else if (ci < 2.0) pColor = BLUE;
      else pColor = CYAN;

      col += pColor * glow * 0.08;
    }

    return col;
  }

  // ── 4. Digital grid — faint rectangular grid ──────────────
  vec3 digitalGrid(vec2 uv) {
    float dist = length(uv);
    float fade = exp(-dist * 2.0) * 0.12;
    if (fade < 0.001) return vec3(0.0);

    float gridScale = 12.0;
    vec2 g = abs(fract(uv * gridScale) - 0.5);
    float lines = smoothstep(0.02, 0.0, min(g.x, g.y));

    // Color alternation per cell
    vec2 cell = floor(uv * gridScale);
    float cellHash = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
    vec3 gridColor = mix(RED, BLUE, step(0.5, cellHash)) * 0.5;

    // Pulse radiating from center
    float pulse = sin(dist * 10.0 - u_time * 2.0) * 0.5 + 0.5;

    return gridColor * lines * fade * u_deform * pulse;
  }

  // ── 5. Light rays — radial beams from center ──────────────
  vec3 lightRays(vec2 uv) {
    float dist = length(uv);
    float angle = atan(uv.y, uv.x);

    // Multiple ray frequencies
    float rays = 0.0;
    rays += pow(max(sin(angle * 8.0 + u_time * 0.3), 0.0), 16.0);
    rays += pow(max(sin(angle * 5.0 - u_time * 0.2 + 1.5), 0.0), 24.0) * 0.5;

    float radialFade = exp(-dist * 2.5) * 0.3 / (dist + 0.15);

    // Chromatic: rays alternate red and blue
    float colorSelect = sin(angle * 4.0 + u_time * 0.1) * 0.5 + 0.5;
    vec3 rayColor = mix(RED * 0.3, BLUE * 0.3, colorSelect);

    return rayColor * rays * radialFade * u_glow;
  }

  // ── 6. Scan lines + glitch ────────────────────────────────
  vec3 postEffects(vec2 uv, vec3 col) {
    // CRT scan lines
    float scan = 1.0 + sin(uv.y * 180.0 + u_time * 1.5) * 0.02 * u_deform;
    col *= scan;

    // Occasional horizontal glitch displacement
    float glitchTrigger = step(0.97, sin(u_time * 7.3) * sin(u_time * 13.1));
    float band = step(0.0, sin(uv.y * 40.0 + u_time * 100.0)) * 0.5;
    col = mix(col, col.bgr * 1.3, band * 0.3 * glitchTrigger);

    return col;
  }

  // ═══════════════════════════════════════════════════════════
  void main() {
    vec2 uv = (vUv * 2.0 - 1.0);
    uv.x *= u_resolution.x / u_resolution.y;

    vec3 col = vec3(0.0);

    // 1. Background grid
    col += digitalGrid(uv);

    // 2. Light rays
    col += lightRays(uv);

    // 3. Six chromatic orbits with red/blue separation
    col += chromaOrbit(uv, 0.50, 1.2,  0.20, 0.006, 0.0);
    col += chromaOrbit(uv, 0.38, 0.8, -0.15, 0.005, 1.0);
    col += chromaOrbit(uv, 0.62, 1.5,  0.25, 0.007, 2.0);
    col += chromaOrbit(uv, 0.28, 1.0, -0.30, 0.005, 3.0);
    col += chromaOrbit(uv, 0.75, 0.6,  0.12, 0.004, 4.0);
    col += chromaOrbit(uv, 0.45, 1.8, -0.22, 0.006, 5.0);

    // 4. Data particles
    col += dataParticles(uv);

    // 5. Core energy
    col += core(uv);

    // 6. Post effects (scan lines + glitch)
    col = postEffects(uv, col);

    // 7. Vignette
    col *= 1.0 - dot(uv * 0.22, uv * 0.22);

    // 8. Soft clamp — prevent bloom blowout while keeping dynamic range
    col = col / (1.0 + col * 0.25);

    // Stopped: very dim
    if (u_state < -0.5) {
      col *= 0.1;
    }

    fragColor = vec4(col, 1.0);
  }
`
