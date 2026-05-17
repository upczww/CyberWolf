import { useEffect, useState } from 'react'

interface Props {
  phase: string | null
}

const NIGHT_PHASES = new Set([
  'night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_guard', 'night_resolve',
])

export default function Background({ phase }: Props) {
  const isNight = phase ? NIGHT_PHASES.has(phase) : true
  const [stars, setStars] = useState<{ x: number; y: number; size: number; delay: number }[]>([])

  useEffect(() => {
    // Generate random stars once
    const s = Array.from({ length: 40 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2 + 1,
      delay: Math.random() * 3,
    }))
    setStars(s)
  }, [])

  return (
    <div className="fixed inset-0 -z-10 transition-all duration-[2000ms] overflow-hidden">
      {/* Sky gradient */}
      <div
        className={`absolute inset-0 transition-all duration-[2000ms] ${
          isNight
            ? 'bg-gradient-to-b from-[#0a0e27] via-[#1a1a3e] to-[#0d1117]'
            : 'bg-gradient-to-b from-[#4a90d9] via-[#87ceeb] to-[#f0e68c]'
        }`}
      />

      {/* Moon (night) */}
      <div
        className={`absolute top-8 right-16 w-16 h-16 rounded-full transition-all duration-[2000ms] ${
          isNight
            ? 'opacity-100 bg-gradient-to-br from-yellow-100 to-yellow-200 shadow-[0_0_40px_rgba(255,255,200,0.4)]'
            : 'opacity-0 scale-50'
        }`}
      >
        {/* Moon craters */}
        <div className="absolute top-3 left-4 w-3 h-3 rounded-full bg-yellow-300/30" />
        <div className="absolute top-7 left-8 w-2 h-2 rounded-full bg-yellow-300/20" />
      </div>

      {/* Sun (day) */}
      <div
        className={`absolute top-8 right-16 w-20 h-20 rounded-full transition-all duration-[2000ms] ${
          isNight
            ? 'opacity-0 scale-50'
            : 'opacity-100 bg-gradient-to-br from-yellow-300 to-orange-400 shadow-[0_0_60px_rgba(255,200,0,0.5)]'
        }`}
      />

      {/* Stars (night only) */}
      {stars.map((star, i) => (
        <div
          key={i}
          className={`absolute rounded-full bg-white transition-opacity duration-[2000ms] ${
            isNight ? 'opacity-70' : 'opacity-0'
          }`}
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            animation: `twinkle ${2 + star.delay}s ease-in-out infinite`,
            animationDelay: `${star.delay}s`,
          }}
        />
      ))}

      {/* Ground/fog overlay */}
      <div
        className={`absolute bottom-0 left-0 right-0 h-32 transition-all duration-[2000ms] ${
          isNight
            ? 'bg-gradient-to-t from-[#0a0e27]/80 to-transparent'
            : 'bg-gradient-to-t from-[#2d5a27]/30 to-transparent'
        }`}
      />

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/40" />
    </div>
  )
}
