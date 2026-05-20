import { useEffect, useRef } from 'react'
import type { GameEvent } from '../stores/game'

interface Props {
  phase: string | null
  latestEvent: GameEvent | null
  winner: string | null
  ttsEnabled: boolean
}

const BGM_VOLUME = 0.28
const SFX_VOLUME = 0.72
const NARRATION_VOLUME = 0.9
const NARRATION_DELAY_MS = 260

const NIGHT_PHASES = new Set(['night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_resolve'])

export default function GameAudio({ phase, latestEvent, winner, ttsEnabled }: Props) {
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

    const sfxSrc = sfxForEvent(latestEvent)
    const narrationSrc = ttsEnabled ? narrationForEvent(latestEvent) : null

    if (!sfxSrc && !narrationSrc) return

    if (sfxSrc) playOneShot(sfxSrc, SFX_VOLUME)
    let narrationTimer: number | null = null
    if (narrationSrc) {
      narrationTimer = window.setTimeout(() => {
        playOneShot(narrationSrc, NARRATION_VOLUME)
      }, sfxSrc ? NARRATION_DELAY_MS : 0)
    }

    return () => {
      if (narrationTimer != null) window.clearTimeout(narrationTimer)
    }
  }, [latestEvent, ttsEnabled])

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

function narrationForEvent(event: GameEvent) {
  if (event.event_type !== 'phase_started') return null
  const phase = event.data?.phase || event.phase
  if (!phase) return null
  const file = PHASE_NARRATION_FILES[phase]
  return file ? `/assets/narration/${file}` : null
}

const PHASE_NARRATION_FILES: Record<string, string> = {
  setup_game: 'setup_game.wav',
  night_start: 'night_start.wav',
  night_wolf: 'night_wolf.wav',
  night_seer: 'night_seer.wav',
  night_witch: 'night_witch.wav',
  night_resolve: 'night_resolve.wav',
  day_announce: 'day_announce.wav',
  sheriff_election: 'sheriff_election.wav',
  day_speech: 'day_speech.wav',
  day_vote: 'day_vote.wav',
  day_resolve: 'day_resolve.wav',
  pending_skills: 'pending_skills.wav',
  check_win: 'check_win.wav',
  game_over: 'game_over.wav',
}

function playOneShot(src: string, volume: number) {
  const audio = new Audio(src)
  audio.volume = volume
  audio.preload = 'auto'
  void audio.play().catch(() => undefined)
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
