/**
 * Code-based game animations triggered by events.
 * All effects are CSS + Framer Motion, no image assets needed.
 */
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GameEvent } from '../stores/game'

interface Props {
  latestEvent: GameEvent | null
}

type EffectType = 'slash' | 'poison' | 'heal' | 'seer' | 'shoot' | 'death' | 'vote' | 'victory_good' | 'victory_wolf' | 'shake' | null

export default function GameEffects({ latestEvent }: Props) {
  const [effect, setEffect] = useState<EffectType>(null)

  useEffect(() => {
    if (!latestEvent) return
    const etype = latestEvent.event_type
    const content = latestEvent.content

    if (etype === 'wolf_target_selected') trigger('slash')
    else if (etype === 'witch_used_poison') trigger('poison')
    else if (etype === 'witch_used_antidote') trigger('heal')
    else if (etype === 'seer_checked') trigger('seer')
    else if (content === 'event.hunter_shot') trigger('shoot')
    else if (etype === 'player_died') trigger('death')
    else if (etype === 'vote_resolved') trigger('vote')
    else if (etype === 'game_ended') {
      trigger(latestEvent.data?.winner === 'good' ? 'victory_good' : 'victory_wolf')
    }
  }, [latestEvent])

  const trigger = (type: EffectType) => {
    setEffect(type)
    setTimeout(() => setEffect(null), 1500)
  }

  return (
    <AnimatePresence>
      {effect === 'slash' && <SlashEffect />}
      {effect === 'poison' && <PoisonEffect />}
      {effect === 'heal' && <HealEffect />}
      {effect === 'seer' && <SeerEffect />}
      {effect === 'shoot' && <ShootEffect />}
      {effect === 'death' && <DeathEffect />}
      {effect === 'vote' && <VoteEffect />}
      {effect === 'victory_good' && <VictoryEffect color="gold" />}
      {effect === 'victory_wolf' && <VictoryEffect color="red" />}
    </AnimatePresence>
  )
}

/** Three red claw slashes + screen shake */
function SlashEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50"
      initial={{ x: 0 }}
      animate={{ x: [0, -4, 4, -2, 2, 0] }}
      transition={{ duration: 0.3 }}
      exit={{ opacity: 0 }}
    >
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute bg-red-500/80 rounded-full"
          style={{
            width: '3px',
            height: '120%',
            left: `${40 + i * 8}%`,
            top: '-10%',
            transform: 'rotate(25deg)',
            boxShadow: '0 0 15px rgba(220,38,38,0.8)',
          }}
          initial={{ scaleY: 0, opacity: 0 }}
          animate={{ scaleY: 1, opacity: [0, 1, 1, 0] }}
          transition={{ duration: 0.6, delay: i * 0.1 }}
        />
      ))}
    </motion.div>
  )
}

/** Purple radial expansion + floating particles */
function PoisonEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center"
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="w-64 h-64 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(147,51,234,0.5) 0%, transparent 70%)',
        }}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: [0, 2.5], opacity: [0, 0.8, 0] }}
        transition={{ duration: 1.2 }}
      />
      {Array.from({ length: 12 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-2 h-2 rounded-full bg-purple-400"
          style={{ left: `${30 + Math.random() * 40}%`, top: '50%' }}
          initial={{ y: 0, opacity: 1 }}
          animate={{ y: -150 - Math.random() * 100, opacity: 0 }}
          transition={{ duration: 1 + Math.random() * 0.5, delay: Math.random() * 0.3 }}
        />
      ))}
    </motion.div>
  )
}

/** Green sparkle particles spiraling upward */
function HealEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center"
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="w-32 h-32 rounded-full"
        style={{ boxShadow: '0 0 60px rgba(34,197,94,0.6)' }}
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: [0.5, 1.5, 1], opacity: [0, 1, 0] }}
        transition={{ duration: 1.2 }}
      />
      {Array.from({ length: 16 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1.5 h-1.5 rounded-full bg-green-400"
          style={{
            left: `${45 + Math.cos(i * 0.5) * 10}%`,
            top: '55%',
          }}
          initial={{ y: 0, opacity: 1, scale: 1 }}
          animate={{
            y: -120 - Math.random() * 80,
            x: Math.sin(i) * 40,
            opacity: 0,
            scale: 0.3,
          }}
          transition={{ duration: 1.2, delay: i * 0.05 }}
        />
      ))}
    </motion.div>
  )
}

/** Purple ring scan */
function SeerEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center"
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="w-48 h-48 rounded-full border-4 border-purple-400"
        style={{ boxShadow: '0 0 30px rgba(147,51,234,0.5), inset 0 0 30px rgba(147,51,234,0.3)' }}
        initial={{ scale: 2, opacity: 0 }}
        animate={{ scale: [2, 0.8, 1], opacity: [0, 1, 0] }}
        transition={{ duration: 1 }}
      />
      {/* Scan line */}
      <motion.div
        className="absolute h-0.5 bg-purple-300"
        style={{ width: '50%', top: '50%', boxShadow: '0 0 10px rgba(196,181,253,0.8)' }}
        initial={{ x: '-100%', opacity: 0 }}
        animate={{ x: ['−100%', '100%'], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 0.8, delay: 0.3 }}
      />
    </motion.div>
  )
}

/** White bolt line + impact ring */
function ShootEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50"
      exit={{ opacity: 0 }}
    >
      {/* Bolt trail */}
      <motion.div
        className="absolute top-1/2 h-0.5 bg-white"
        style={{ left: '10%', boxShadow: '0 0 8px white' }}
        initial={{ width: 0, opacity: 1 }}
        animate={{ width: '60%', opacity: [1, 1, 0] }}
        transition={{ duration: 0.3 }}
      />
      {/* Impact ring */}
      <motion.div
        className="absolute top-1/2 left-[70%] -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full border-2 border-white"
        initial={{ scale: 0, opacity: 1 }}
        animate={{ scale: 4, opacity: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
      />
    </motion.div>
  )
}

/** Card shatter — fragments fly outward */
function DeathEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center"
      exit={{ opacity: 0 }}
    >
      {Array.from({ length: 8 }).map((_, i) => {
        const angle = (i / 8) * Math.PI * 2
        return (
          <motion.div
            key={i}
            className="absolute w-6 h-8 bg-gray-600/60 border border-gray-400/30"
            style={{ clipPath: 'polygon(10% 0%, 90% 20%, 100% 80%, 0% 100%)' }}
            initial={{ x: 0, y: 0, rotate: 0, opacity: 1 }}
            animate={{
              x: Math.cos(angle) * 150,
              y: Math.sin(angle) * 150,
              rotate: Math.random() * 360,
              opacity: 0,
            }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        )
      })}
    </motion.div>
  )
}

/** Paper vote slips falling */
function VoteEffect() {
  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50"
      exit={{ opacity: 0 }}
    >
      {Array.from({ length: 10 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-4 h-5 bg-yellow-100/70 border border-yellow-300/50 rounded-sm"
          style={{ left: `${15 + Math.random() * 70}%`, top: '-5%' }}
          initial={{ y: 0, rotate: 0, opacity: 1 }}
          animate={{
            y: window.innerHeight + 50,
            rotate: Math.random() * 720 - 360,
            opacity: [1, 1, 0.5],
          }}
          transition={{ duration: 1.5 + Math.random(), delay: Math.random() * 0.5, ease: 'easeIn' }}
        />
      ))}
    </motion.div>
  )
}

/** Victory fireworks — bursts of colored particles */
function VictoryEffect({ color }: { color: 'gold' | 'red' }) {
  const baseColor = color === 'gold' ? 'bg-yellow-400' : 'bg-red-500'
  const centers = [
    { x: 30, y: 30 }, { x: 70, y: 25 }, { x: 50, y: 50 },
    { x: 20, y: 60 }, { x: 80, y: 55 },
  ]

  return (
    <motion.div
      className="fixed inset-0 pointer-events-none z-50"
      exit={{ opacity: 0 }}
    >
      {centers.map((center, ci) => (
        <div key={ci}>
          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i / 12) * Math.PI * 2
            return (
              <motion.div
                key={`${ci}-${i}`}
                className={`absolute w-2 h-2 rounded-full ${baseColor}`}
                style={{
                  left: `${center.x}%`,
                  top: `${center.y}%`,
                  boxShadow: `0 0 6px ${color === 'gold' ? 'rgba(250,204,21,0.8)' : 'rgba(239,68,68,0.8)'}`,
                }}
                initial={{ x: 0, y: 0, scale: 1, opacity: 1 }}
                animate={{
                  x: Math.cos(angle) * (80 + Math.random() * 40),
                  y: Math.sin(angle) * (80 + Math.random() * 40),
                  scale: 0,
                  opacity: 0,
                }}
                transition={{ duration: 1 + Math.random() * 0.5, delay: ci * 0.2 }}
              />
            )
          })}
        </div>
      ))}
    </motion.div>
  )
}
