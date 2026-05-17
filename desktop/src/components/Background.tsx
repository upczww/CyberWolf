/**
 * Layered game background:
 * - Layer 0: Sky gradient (day/night transition via CSS)
 * - Layer 1: tsParticles (stars at night, dust motes during day)
 * - Layer 2: Moon/Sun celestial body
 * - Layer 3: Fog/atmosphere overlay
 */
import { useEffect, useMemo, useState, useCallback } from 'react'
import Particles, { initParticlesEngine } from '@tsparticles/react'
import { loadSlim } from '@tsparticles/slim'
import type { ISourceOptions } from '@tsparticles/engine'

interface Props {
  phase: string | null
}

const NIGHT_PHASES = new Set([
  'night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_guard', 'night_resolve',
])

export default function Background({ phase }: Props) {
  const isNight = phase ? NIGHT_PHASES.has(phase) : true
  const [engineReady, setEngineReady] = useState(false)

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine)
    }).then(() => setEngineReady(true))
  }, [])

  const particleOptions: ISourceOptions = useMemo(() => ({
    fullScreen: false,
    particles: {
      number: { value: isNight ? 60 : 15 },
      color: { value: isNight ? '#ffffff' : '#f5e6d3' },
      opacity: {
        value: { min: 0.1, max: isNight ? 0.8 : 0.3 },
        animation: { enable: true, speed: 0.5, sync: false },
      },
      size: {
        value: { min: 0.5, max: isNight ? 2.5 : 1.5 },
        animation: { enable: isNight, speed: 1, sync: false },
      },
      move: {
        enable: true,
        speed: isNight ? 0.2 : 0.5,
        direction: isNight ? 'none' : 'bottom',
        outModes: { default: 'out' },
      },
      twinkle: {
        particles: { enable: isNight, frequency: 0.03, color: '#ffffff' },
      },
    },
    detectRetina: true,
  }), [isNight])

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      {/* Layer 0: Sky gradient */}
      <div
        className={`absolute inset-0 transition-all duration-[3000ms] ${
          isNight
            ? 'bg-gradient-to-b from-[#070b1a] via-[#101530] to-[#0d1117]'
            : 'bg-gradient-to-b from-[#3a7bd5] via-[#6db3f2] to-[#f0e4a8]'
        }`}
      />

      {/* Layer 1: tsParticles (stars / dust) */}
      {engineReady && (
        <Particles
          className="absolute inset-0"
          options={particleOptions}
        />
      )}

      {/* Layer 2: Celestial body */}
      {/* Moon */}
      <div
        className={`absolute top-8 right-20 w-16 h-16 rounded-full transition-all duration-[3000ms] ${
          isNight
            ? 'opacity-100 bg-gradient-to-br from-yellow-100 to-yellow-200 shadow-[0_0_50px_rgba(255,255,200,0.4)]'
            : 'opacity-0 scale-50 translate-y-10'
        }`}
      >
        <div className="absolute top-3 left-4 w-3 h-3 rounded-full bg-yellow-300/30" />
        <div className="absolute top-7 left-8 w-2 h-2 rounded-full bg-yellow-300/20" />
      </div>
      {/* Sun */}
      <div
        className={`absolute top-10 right-20 w-20 h-20 rounded-full transition-all duration-[3000ms] ${
          isNight
            ? 'opacity-0 scale-50 translate-y-10'
            : 'opacity-100 bg-gradient-to-br from-yellow-300 to-orange-400 shadow-[0_0_80px_rgba(255,180,0,0.5)]'
        }`}
      />

      {/* Layer 3: Atmosphere overlay */}
      <div
        className={`absolute bottom-0 left-0 right-0 h-40 transition-all duration-[3000ms] ${
          isNight
            ? 'bg-gradient-to-t from-black/60 to-transparent'
            : 'bg-gradient-to-t from-[#1a4a1a]/20 to-transparent'
        }`}
      />

      {/* Readability overlay */}
      <div className="absolute inset-0 bg-black/30" />
    </div>
  )
}
