import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { vertexShader, fragmentShader } from './shaders'
import { usePipeline } from '../../stores/usePipeline'
import { stateColors } from '../../lib/theme'

/** Full-screen digital light artifacts orb — red & blue chromatic aesthetic */
export function Orb() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const uniformsRef = useRef<Record<string, THREE.IUniform> | null>(null)

  // Subscribe to pipeline store
  const state = usePipeline((s) => s.state)
  const audioLevel = usePipeline((s) => s.audioLevel)

  // Initialize Three.js scene once
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: false,
      powerPreference: 'high-performance',
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.0

    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    const scene = new THREE.Scene()

    const uniforms: Record<string, THREE.IUniform> = {
      u_time: { value: 0.0 },
      u_resolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      u_audioLevel: { value: 0.0 },
      u_color: { value: new THREE.Color(stateColors.idle) },
      u_deform: { value: 0.5 },
      u_glow: { value: 0.35 },
      u_state: { value: 0.0 },
    }
    uniformsRef.current = uniforms

    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader,
      glslVersion: THREE.GLSL3,
    })

    const geometry = new THREE.PlaneGeometry(2, 2)
    scene.add(new THREE.Mesh(geometry, material))

    // Post-processing: bloom
    const composer = new EffectComposer(renderer)
    composer.addPass(new RenderPass(scene, camera))
    const bloom = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      1.0, 0.4, 0.35  // digital aesthetic: selective bloom on bright spots only
    )
    composer.addPass(bloom)
    composer.addPass(new OutputPass())

    // Resize
    const onResize = () => {
      const w = window.innerWidth, h = window.innerHeight
      renderer.setSize(w, h)
      composer.setSize(w, h)
      bloom.setSize(w, h)
      uniforms.u_resolution.value.set(w, h)
    }
    window.addEventListener('resize', onResize)

    // Single animation loop — updates uniforms + renders in the same frame
    const clock = new THREE.Clock()
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t
    let raf: number
    const tick = () => {
      uniforms.u_time.value = clock.getElapsedTime()
      // Smooth interpolation toward target values
      const t = targetRef.current
      const c = uniforms.u_color.value as THREE.Color
      c.lerp(t.color, 0.06)
      uniforms.u_deform.value = lerp(uniforms.u_deform.value as number, t.deform, 0.06)
      uniforms.u_glow.value = lerp(uniforms.u_glow.value as number, t.glow, 0.06)
      uniforms.u_state.value = lerp(uniforms.u_state.value as number, t.state, 0.04)
      composer.render()
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      scene.clear()
      geometry.dispose()
      material.dispose()
      composer.dispose()
      renderer.dispose()
    }
  }, [])

  // Bridge state → target uniforms (smooth transitions via lerp in render loop)
  const targetRef = useRef({ color: new THREE.Color(stateColors.idle), deform: 0.5, glow: 0.35, state: 0.0 })

  useEffect(() => {
    const stateParams: Record<string, { deform: number; glow: number; stateVal: number }> = {
      stopped: { deform: 0.0, glow: 0.1, stateVal: -1.0 },
      loading: { deform: 0.3, glow: 0.5, stateVal: -0.5 },
      idle: { deform: 0.5, glow: 0.35, stateVal: 0.0 },
      listening: { deform: 0.9, glow: 0.6, stateVal: 1.0 },
      thinking: { deform: 0.7, glow: 0.65, stateVal: 2.0 },
      speaking: { deform: 0.85, glow: 0.7, stateVal: 3.0 },
    }
    const params = stateParams[state] || stateParams.idle
    targetRef.current.color.set(stateColors[state] || stateColors.idle)
    targetRef.current.deform = params.deform
    targetRef.current.glow = params.glow
    targetRef.current.state = params.stateVal
  }, [state])

  // Bridge audio level directly (no interpolation needed — already throttled at 20Hz)
  useEffect(() => {
    if (uniformsRef.current) {
      uniformsRef.current.u_audioLevel.value = audioLevel
    }
  }, [audioLevel])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full"
      style={{ zIndex: 0 }}
    />
  )
}
