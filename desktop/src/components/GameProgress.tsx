import { useEffect, useRef, useState } from 'react'
import type { GameEvent } from '../stores/game'

/**
 * GameProgress — friendly progress prompts for the seated human player.
 *
 * Renders two transient banners on top of the in-game UI:
 *   • PhaseFlash    — a centered title when the phase changes
 *                     (e.g. "🐺 狼人请睁眼", "☀ 天亮了").
 *   • EventFlash    — a centered ticker for major resolutions
 *                     (e.g. "★ 4 号当选警长", "⚖ 平票，进入加赛",
 *                      "☠ 8 号被放逐").
 *
 * Both auto-dismiss after a short window. Multiple flashes queue so a fast
 * burst of resolution events still gets shown one-by-one.
 */

interface Props {
  phase: string | null
  round: number
  events: GameEvent[]
  humanSeat: number | null
  winner: string | null
}

const PHASE_FLASH_MS = 2200
const EVENT_FLASH_MS = 2400

const PHASE_FLASH: Record<string, { glyph: string; title: string }> = {
  night_start:       { glyph: '🌙', title: '夜幕降临' },
  night_wolf:        { glyph: '🐺', title: '狼人请睁眼' },
  night_seer:        { glyph: '👁',  title: '预言家请睁眼' },
  night_witch:       { glyph: '🧪', title: '女巫请睁眼' },
  night_guard:       { glyph: '🛡', title: '守卫请守护' },
  night_resolve:     { glyph: '🌅', title: '天将亮起' },
  day_announce:      { glyph: '☀',  title: '天亮了' },
  sheriff_election:  { glyph: '★',  title: '警长竞选' },
  day_speech:        { glyph: '🗣',  title: '发言阶段' },
  day_vote:          { glyph: '⚖',  title: '投票阶段' },
  day_resolve:       { glyph: '⚖',  title: '投票结算' },
  pending_skills:    { glyph: '✨', title: '技能结算' },
}

interface FlashItem {
  id: number
  glyph: string
  text: string
  tone: 'gold' | 'good' | 'wolf' | 'neutral'
}

export default function GameProgress({ phase, round, events, humanSeat, winner }: Props) {
  // ---- Phase flash ----
  const [phaseFlash, setPhaseFlash] = useState<{ glyph: string; title: string; sub: string } | null>(null)
  const prevPhase = useRef<string | null>(null)
  useEffect(() => {
    if (!phase) return
    if (phase === prevPhase.current) return
    const next = PHASE_FLASH[phase]
    prevPhase.current = phase
    if (!next) {
      setPhaseFlash(null)
      return
    }
    const isNight = phase.startsWith('night')
    const sub = `第 ${round || 1} ${isNight ? '夜' : '天'}`
    setPhaseFlash({ glyph: next.glyph, title: next.title, sub })
    const t = window.setTimeout(() => setPhaseFlash(null), PHASE_FLASH_MS)
    return () => window.clearTimeout(t)
  }, [phase, round])

  // ---- Event flash queue ----
  const [queue, setQueue] = useState<FlashItem[]>([])
  const lastSeenSeq = useRef<number>(-1)
  useEffect(() => {
    if (!events.length) return
    // Pull only newly-arrived events; assume the events array is append-only
    // ordered by seq when present, otherwise by index.
    const newItems: FlashItem[] = []
    for (const ev of events) {
      const seq = typeof ev.seq === 'number' ? ev.seq : -1
      if (seq <= lastSeenSeq.current) continue
      const item = eventToFlash(ev, humanSeat)
      if (item) newItems.push(item)
      if (seq > lastSeenSeq.current) lastSeenSeq.current = seq
    }
    if (newItems.length) setQueue((q) => [...q, ...newItems])
  }, [events, humanSeat])

  // Pop one flash at a time from the queue
  const [active, setActive] = useState<FlashItem | null>(null)
  useEffect(() => {
    if (active || !queue.length) return
    const next = queue[0]
    setQueue((q) => q.slice(1))
    setActive(next)
    const t = window.setTimeout(() => setActive(null), EVENT_FLASH_MS)
    return () => window.clearTimeout(t)
  }, [queue, active])

  // ---- Game-over big banner is handled separately by App.tsx ----
  if (winner) return null

  return (
    <>
      {phaseFlash && (
        <div className="phase-flash" key={`${phaseFlash.title}-${phaseFlash.sub}`}>
          <span className="phase-flash-glyph">{phaseFlash.glyph}</span>
          <div className="phase-flash-stack">
            <b>{phaseFlash.title}</b>
            <span>{phaseFlash.sub}</span>
          </div>
        </div>
      )}
      {active && (
        <div className={`event-flash tone-${active.tone}`} key={active.id}>
          <span className="event-flash-glyph">{active.glyph}</span>
          <span className="event-flash-text">{active.text}</span>
        </div>
      )}
    </>
  )
}

let _flashIdCounter = 0
function nextFlashId(): number {
  _flashIdCounter += 1
  return _flashIdCounter
}

function eventToFlash(ev: GameEvent, humanSeat: number | null): FlashItem | null {
  const d = ev.data || {}
  switch (ev.event_type) {
    case 'sheriff_elected': {
      const pid = d.player_id ?? d.target_id
      if (pid == null) return { id: nextFlashId(), glyph: '★', text: '无人当选警长', tone: 'neutral' }
      const isMe = humanSeat != null && Number(pid) === humanSeat
      return { id: nextFlashId(), glyph: '★', text: isMe ? `你当选为警长` : `${pid} 号当选警长`, tone: 'gold' }
    }
    case 'sheriff_transferred': {
      const pid = d.target_id ?? d.player_id
      return { id: nextFlashId(), glyph: '★', text: pid == null ? '警徽撕毁' : `警徽传给 ${pid} 号`, tone: 'gold' }
    }
    case 'vote_resolved': {
      const chosen = d.chosen
      if (chosen == null) return { id: nextFlashId(), glyph: '⚖', text: '平票，未放逐', tone: 'neutral' }
      const isMe = humanSeat != null && Number(chosen) === humanSeat
      return { id: nextFlashId(), glyph: '⚖', text: isMe ? '你被投票放逐' : `${chosen} 号被投票放逐`, tone: 'wolf' }
    }
    case 'player_died': {
      const pid = d.player_id
      const cause = d.cause
      const causeText = cause === 'wolf' ? '夜刀'
        : cause === 'poison' ? '毒杀'
        : cause === 'exile' ? '放逐'
        : cause === 'hunter' ? '猎人开枪'
        : cause === 'self_destruct' ? '狼人自爆'
        : '出局'
      const isMe = humanSeat != null && Number(pid) === humanSeat
      return {
        id: nextFlashId(),
        glyph: '☠',
        text: isMe ? `你出局 · ${causeText}` : `${pid ?? '?'} 号出局 · ${causeText}`,
        tone: 'wolf',
      }
    }
    case 'hunter_shot': {
      const target = d.target_id
      return { id: nextFlashId(), glyph: '🏹', text: target == null ? '猎人未开枪' : `猎人开枪 → ${target} 号`, tone: 'wolf' }
    }
    case 'wolf_self_destruct': {
      const pid = d.player_id
      return { id: nextFlashId(), glyph: '💥', text: `${pid ?? '?'} 号狼人自爆`, tone: 'wolf' }
    }
    case 'game_ended': {
      const w = d.winner
      return {
        id: nextFlashId(),
        glyph: w === 'wolf' ? '🐺' : '🌟',
        text: w === 'wolf' ? '狼人阵营胜利' : '好人阵营胜利',
        tone: w === 'wolf' ? 'wolf' : 'good',
      }
    }
    default:
      return null
  }
}
