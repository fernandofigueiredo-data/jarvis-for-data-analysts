import { Canvas, useFrame } from '@react-three/fiber'
import { useReducedMotion } from 'framer-motion'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useJarvis } from '../store'
import type { Phase } from '../types'
import { C, PHASE_COLOR, resolveToken } from './ui'

const R = 1.2

const SPEED: Record<Phase, number> = { idle: 0.12, listening: 0.22, thinking: 0.7, tooling: 0.5, speaking: 0.28 }
const GLOW: Record<Phase, number> = { idle: 0.55, listening: 0.95, thinking: 0.8, tooling: 0.8, speaking: 0.85 }
const TARGET = Object.fromEntries(
  // o WebGL não lê var(--…): resolve os tokens do design system uma vez (o CSS já carregou, o globo é lazy)
  Object.entries(PHASE_COLOR).map(([k, v]) => [k, new THREE.Color(resolveToken(v))]),
) as Record<Phase, THREE.Color>

/** Ponto em coordenadas esféricas (lat/lon em graus). */
function sph(lat: number, lon: number, r = R) {
  const la = THREE.MathUtils.degToRad(lat)
  const lo = THREE.MathUtils.degToRad(lon)
  return new THREE.Vector3(r * Math.cos(la) * Math.cos(lo), r * Math.sin(la), r * Math.cos(la) * Math.sin(lo))
}

function rng(seed: number) {
  return () => {
    seed = (seed * 16807) % 2147483647
    return (seed - 1) / 2147483646
  }
}

function glowTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.25, 'rgba(255,255,255,0.8)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 64, 64)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

function circlePoints(r: number, seg = 128) {
  const pts: THREE.Vector3[] = []
  for (let i = 0; i <= seg; i++) {
    const a = (i / seg) * Math.PI * 2
    pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r))
  }
  return pts
}

const atmosphereVert = /* glsl */ `
  varying vec3 vN; varying vec3 vV;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }`
const atmosphereFrag = /* glsl */ `
  uniform vec3 uColor; uniform float uIntensity;
  varying vec3 vN; varying vec3 vV;
  void main() {
    float f = pow(1.0 - abs(dot(vN, vV)), 2.4);
    gl_FragColor = vec4(uColor, f * uIntensity);
  }`

function CoreScene() {
  const spin = useRef<THREE.Group>(null!)
  const pulse = useRef<THREE.Group>(null!)
  const rings = useRef<THREE.Group[]>([])
  const sats = useRef<THREE.Mesh[]>([])
  const baseRing = useRef<THREE.Group>(null!)
  const dust = useRef<THREE.Points>(null!)

  const state = useRef({ color: new THREE.Color(resolveToken(PHASE_COLOR.idle)), speed: SPEED.idle, glow: GLOW.idle, level: 0 })
  // Reduzir Movimento: a cor ainda acompanha a fase, mas nada gira nem pulsa (o valor muda ao vivo)
  const still = useRef(false)
  still.current = useReducedMotion() ?? false

  const tex = useMemo(glowTexture, [])

  // malha de latitude/longitude como segmentos de linha
  const gridGeo = useMemo(() => {
    const pts: THREE.Vector3[] = []
    for (let lat = -75; lat <= 75; lat += 15) {
      for (let lon = 0; lon < 360; lon += 4) pts.push(sph(lat, lon), sph(lat, lon + 4))
    }
    // meridianos: grandes círculos passando pelos polos
    const meridian = (lon: number, t: number) => {
      const la = THREE.MathUtils.degToRad(t)
      const lo = THREE.MathUtils.degToRad(lon)
      return new THREE.Vector3(R * Math.cos(la) * Math.cos(lo), R * Math.sin(la), R * Math.cos(la) * Math.sin(lo))
    }
    for (let lon = 0; lon < 180; lon += 15) {
      for (let t = 0; t < 360; t += 4) pts.push(meridian(lon, t), meridian(lon, t + 4))
    }
    return new THREE.BufferGeometry().setFromPoints(pts)
  }, [])

  // nós na superfície + arcos entre eles
  const { nodeGeo, hubGeo, arcGeo } = useMemo(() => {
    const rand = rng(7)
    const nodes: THREE.Vector3[] = []
    for (let i = 0; i < 90; i++) {
      const lat = Math.asin(rand() * 2 - 1) * (180 / Math.PI)
      nodes.push(sph(lat, rand() * 360, R * 1.005))
    }
    const hubs = nodes.filter((_, i) => i % 9 === 0)
    const arcPts: THREE.Vector3[] = []
    for (let i = 0; i < hubs.length; i++) {
      const a = hubs[i]
      const b = hubs[(i + 3) % hubs.length]
      const mid = a.clone().add(b).normalize().multiplyScalar(R * (1.18 + rand() * 0.15))
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b)
      const cp = curve.getPoints(40)
      for (let j = 0; j < cp.length - 1; j++) arcPts.push(cp[j], cp[j + 1])
    }
    return {
      nodeGeo: new THREE.BufferGeometry().setFromPoints(nodes),
      hubGeo: new THREE.BufferGeometry().setFromPoints(hubs),
      arcGeo: new THREE.BufferGeometry().setFromPoints(arcPts),
    }
  }, [])

  const dustGeo = useMemo(() => {
    const rand = rng(42)
    const pts: THREE.Vector3[] = []
    for (let i = 0; i < 260; i++) {
      const dir = new THREE.Vector3(rand() * 2 - 1, (rand() * 2 - 1) * 0.7, rand() * 2 - 1).normalize()
      pts.push(dir.multiplyScalar(R * (1.35 + rand() * 1.4)))
    }
    return new THREE.BufferGeometry().setFromPoints(pts)
  }, [])

  const ringDefs = useMemo(
    () => [
      { r: R * 1.38, tilt: [1.25, 0, 0.35] as const, speed: 0.5 },
      { r: R * 1.55, tilt: [1.75, 0.4, -0.25] as const, speed: -0.35 },
      { r: R * 1.72, tilt: [1.45, -0.5, 0.15] as const, speed: 0.22 },
    ],
    [],
  )
  const ringGeos = useMemo(
    () => ringDefs.map((d) => new THREE.BufferGeometry().setFromPoints(circlePoints(d.r))),
    [ringDefs],
  )
  const baseGeos = useMemo(() => {
    return {
      inner: new THREE.BufferGeometry().setFromPoints(circlePoints(R * 0.95)),
      outer: new THREE.BufferGeometry().setFromPoints(circlePoints(R * 1.45)),
      dashed: new THREE.BufferGeometry().setFromPoints(circlePoints(R * 1.25, 180)),
    }
  }, [])

  const atmosphere = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: atmosphereVert,
        fragmentShader: atmosphereFrag,
        uniforms: { uColor: { value: new THREE.Color(resolveToken(PHASE_COLOR.idle)) }, uIntensity: { value: 0.6 } },
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
      }),
    [],
  )

  // materiais que acompanham a cor da fase
  const mats = useMemo(() => {
    const base = { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending } as const
    return {
      grid: new THREE.LineBasicMaterial({ ...base, opacity: 0.32 }),
      arc: new THREE.LineBasicMaterial({ ...base, opacity: 0.5 }),
      ring: new THREE.LineBasicMaterial({ ...base, opacity: 0.45 }),
      base: new THREE.LineBasicMaterial({ ...base, opacity: 0.4 }),
      dashed: new THREE.LineDashedMaterial({ ...base, opacity: 0.55, dashSize: 0.06, gapSize: 0.05 }),
      node: new THREE.PointsMaterial({ ...base, size: 0.05, map: tex, opacity: 0.9 }),
      hub: new THREE.PointsMaterial({ ...base, size: 0.16, map: tex, opacity: 1 }),
      dust: new THREE.PointsMaterial({ ...base, size: 0.03, map: tex, opacity: 0.6 }),
      sat: new THREE.MeshBasicMaterial({ color: resolveToken(C.text) }),
      satGlow: new THREE.SpriteMaterial({ ...base, map: tex, opacity: 0.9 }),
      core: new THREE.MeshBasicMaterial({ ...base, opacity: 0.06 }),
      disc: new THREE.MeshBasicMaterial({ ...base, map: tex, opacity: 0.35 }),
    }
  }, [tex])

  const dashedLine = useMemo(() => {
    // <line> colide com o elemento SVG no JSX; tracejado exige distâncias por vértice
    const l = new THREE.Line(baseGeos.dashed, mats.dashed)
    l.computeLineDistances()
    return l
  }, [baseGeos, mats])

  const light = useMemo(() => new THREE.Color(), [])
  const white = useMemo(() => new THREE.Color('#ffffff'), [])

  useFrame((frame, dt) => {
    const { phase, level } = useJarvis.getState()
    const s = state.current
    const k = 1 - Math.exp(-dt * 3)
    s.color.lerp(TARGET[phase], k)
    s.speed += (SPEED[phase] - s.speed) * k
    s.glow += (GLOW[phase] - s.glow) * k
    s.level += ((phase === 'speaking' ? level : 0) - s.level) * (1 - Math.exp(-dt * 12))
    const t = frame.clock.elapsedTime

    light.copy(s.color).lerp(white, 0.45)
    for (const m of [mats.grid, mats.arc, mats.ring, mats.base, mats.dashed, mats.dust, mats.core, mats.disc])
      m.color.copy(s.color)
    mats.node.color.copy(light)
    mats.hub.color.copy(light)
    mats.satGlow.color.copy(s.color)
    atmosphere.uniforms.uColor.value.copy(s.color)

    if (still.current) {
      pulse.current.scale.setScalar(1)
      atmosphere.uniforms.uIntensity.value = s.glow
      sats.current.forEach((m, i) => m && m.position.set(Math.cos(i * 2) * ringDefs[i].r, 0, Math.sin(i * 2) * ringDefs[i].r))
      return
    }

    let amp = 0.012 * Math.sin(t * 1.3)
    if (phase === 'listening') amp = 0.035 * Math.sin(t * 4.5)
    if (phase === 'thinking' || phase === 'tooling') amp = 0.02 * Math.sin(t * 7)
    if (phase === 'speaking') amp = s.level * 0.11
    pulse.current.scale.setScalar(1 + amp)

    atmosphere.uniforms.uIntensity.value = s.glow * (1 + amp * 6)
    mats.grid.opacity = 0.22 + s.glow * 0.18
    mats.hub.size = 0.14 + Math.max(0, amp) * 1.2 + 0.03 * Math.sin(t * 3)

    spin.current.rotation.y += s.speed * dt
    rings.current.forEach((g, i) => g && (g.rotation.y += ringDefs[i].speed * dt * (0.6 + s.speed * 2)))
    sats.current.forEach((m, i) => {
      if (!m) return
      const a = t * ringDefs[i].speed * 1.6 + i * 2
      m.position.set(Math.cos(a) * ringDefs[i].r, 0, Math.sin(a) * ringDefs[i].r)
    })
    baseRing.current.rotation.y -= dt * 0.15
    dust.current.rotation.y += dt * 0.02 * (1 + s.speed * 2)
  })

  return (
    <group position={[0, 0.12, 0]}>
      <group ref={pulse}>
        <group rotation={[0.38, 0, 0.12]}>
          <group ref={spin}>
            <lineSegments geometry={gridGeo} material={mats.grid} />
            <lineSegments geometry={arcGeo} material={mats.arc} />
            <points geometry={nodeGeo} material={mats.node} />
            <points geometry={hubGeo} material={mats.hub} />
          </group>
          <mesh material={mats.core}>
            <sphereGeometry args={[R * 0.98, 48, 48]} />
          </mesh>
        </group>
        <mesh material={atmosphere}>
          <sphereGeometry args={[R * 1.22, 64, 64]} />
        </mesh>
      </group>

      {ringDefs.map((d, i) => (
        <group key={i} rotation={[d.tilt[0], d.tilt[1], d.tilt[2]]}>
          <group ref={(g) => void (rings.current[i] = g!)}>
            <lineLoop geometry={ringGeos[i]} material={mats.ring} />
            <mesh ref={(m) => void (sats.current[i] = m!)} material={mats.sat}>
              <sphereGeometry args={[0.035, 12, 12]} />
              <sprite material={mats.satGlow} scale={0.32} />
            </mesh>
          </group>
        </group>
      ))}

      <points ref={dust} geometry={dustGeo} material={mats.dust} />

      <group position={[0, -R * 1.3, 0]} ref={baseRing}>
        <lineLoop geometry={baseGeos.inner} material={mats.base} />
        <lineLoop geometry={baseGeos.outer} material={mats.base} />
        <primitive object={dashedLine} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} material={mats.disc}>
          <circleGeometry args={[R * 1.3, 64]} />
        </mesh>
      </group>
    </group>
  )
}

export default function Globe() {
  return (
    <Canvas
      camera={{ position: [0, 0.8, 5.1], fov: 42 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance', preserveDrawingBuffer: true }}
      onCreated={({ camera }) => camera.lookAt(0, -0.12, 0)}
      style={{ position: 'absolute', inset: 0 }}
    >
      <CoreScene />
    </Canvas>
  )
}
