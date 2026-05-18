import { useEffect, useRef } from 'react'
import type { GameEvent } from '../stores/game'

interface Props {
  phase: string | null
  latestEvent: GameEvent | null
  winner: string | null
}

const BGM_VOLUME = 0.28
const SFX_VOLUME = 0.72

const NIGHT_PHASES = new Set(['night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_resolve'])

export default function GameAudio({ phase, latestEvent, winner }: Props) {
  const bgmRef = useRef<HTMLAudioElement | null>(null)
  const currentBgmRef = useRef<string | null>(null)
  const lastEventSignatureRef = useRef<string | null>(null)

  useEffect(() => {
    const target = bgmForPhase(phase, winner)

    if (!target) {
      stopBgm(bgmRef.current)
      bgmRef.current = null
      currentBgmRef.current = null
      return
    }

    if (currentBgmRef.current === target.src) return

    stopBgm(bgmRef.current)
    const audio = new Audio(target.src)
    audio.loop = target.loop
    audio.volume = BGM_VOLUME
    audio.preload = 'auto'
    bgmRef.current = audio
    currentBgmRef.current = target.src
    void audio.play().catch(() => undefined)

    return () => {
      stopBgm(audio)
    }
  }, [phase, winner])

  useEffect(() => {
    if (!latestEvent) return

    const signature = eventSignature(latestEvent)
    if (signature === lastEventSignatureRef.current) return
    lastEventSignatureRef.current = signature

    const src = sfxForEvent(latestEvent)
    if (!src) return

    const audio = new Audio(src)
    audio.volume = SFX_VOLUME
    audio.preload = 'auto'
    void audio.play().catch(() => undefined)
  }, [latestEvent])

  return null
}

function bgmForPhase(phase: string | null, winner: string | null) {
  if (winner || phase === 'game_over') {
    return {
      src: winner === 'wolf' ? '/assets/bgm/victory_wolf.wav' : '/assets/bgm/victory_good.wav',
      loop: false,
    }
  }

  if (!phase) return null
  if (NIGHT_PHASES.has(phase)) return { src: '/assets/bgm/night_loop.wav', loop: true }
  if (phase === 'sheriff_election') return { src: '/assets/bgm/sheriff_campaign.wav', loop: true }
  if (phase === 'day_vote' || phase === 'day_resolve') return { src: '/assets/bgm/vote_tension.wav', loop: true }
  if (phase === 'day_announce' || phase === 'day_speech') return { src: '/assets/bgm/day_discussion.wav', loop: true }
  return null
}

function sfxForEvent(event: GameEvent) {
  const type = event.event_type
  const content = event.content
  const data = event.data || {}
  const eventPhase = data.phase || event.phase

  if (type === 'phase_started' && NIGHT_PHASES.has(eventPhase)) return '/assets/sfx/phase_night.wav'
  if (type === 'phase_started' && eventPhase === 'day_announce') return '/assets/sfx/phase_dawn.wav'
  if (type === 'wolf_target_selected') return '/assets/sfx/skill_wolf_kill.wav'
  if (type === 'seer_checked') return '/assets/sfx/skill_seer_check.wav'
  if (type === 'witch_used_antidote') return '/assets/sfx/skill_antidote.wav'
  if (type === 'witch_used_poison') return '/assets/sfx/skill_poison.wav'
  if (type === 'hunter_shot' || content === 'event.hunter_shot') return '/assets/sfx/skill_hunter_shoot.wav'
  if (type === 'wolf_self_destruct') return '/assets/sfx/skill_self_destruct.wav'
  if (type === 'vote_resolved') return '/assets/sfx/vote_result.wav'
  if (type === 'player_died' && (data.cause === 'exile' || data.death_cause === 'exile')) return '/assets/sfx/exile.wav'
  if (type === 'sheriff_elected') return '/assets/sfx/sheriff_elected.wav'
  if (type === 'game_ended') {
    return data.winner === 'wolf' ? '/assets/sfx/victory_wolf.wav' : '/assets/sfx/victory_good.wav'
  }

  return null
}

function eventSignature(event: GameEvent) {
  return [
    event.seq ?? 'no-seq',
    event.created_at ?? 'no-time',
    event.event_type,
    event.content,
    JSON.stringify(event.data || {}),
  ].join(':')
}

function stopBgm(audio: HTMLAudioElement | null) {
  if (!audio) return
  audio.pause()
  audio.currentTime = 0
}
