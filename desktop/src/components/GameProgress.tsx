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

// Long enough for the human to register the phase and react. The backend
// holds 天黑请闭眼 for 5s before night_wolf begins; keep the banner up for
// at least that long so it doesn't disappear into a blank screen between
// role calls.
const PHASE_FLASH_MS = 5500
// EventFlash items pop one at a time from a queue. 2.4s per item felt
// snappy in isolation but rushed when 3–4 items fire in a row (dawn
// announcement + per-death-speech intros), so each ticker line now
// gets a longer reading window.
const EVENT_FLASH_MS = 3800

// Backend ``kind`` → frontend glyph default. The engine can override by
// emitting `data.glyph` explicitly.
const KIND_GLYPH: Record<string, string> = {
  info:    '🌙',
  good:    '🌟',
  gold:    '★',
  wolf:    '🐺',
  neutral: 'ℹ',
}

interface FlashItem {
  id: number
  glyph: string
  text: string
  tone: 'gold' | 'good' | 'wolf' | 'neutral'
}

export default function GameProgress({ phase, round, events, humanSeat, winner }: Props) {
  // ---- Phase flash (driven by backend narration events with style=intro) ----
  const [phaseFlash, setPhaseFlash] = useState<{ glyph: string; title: string; sub: string } | null>(null)

  // ---- Event flash queue ----
  const [queue, setQueue] = useState<FlashItem[]>([])
  const lastSeenSeq = useRef<number>(-1)
  const phaseTimer = useRef<number | null>(null)
  useEffect(() => {
    if (!events.length) return
    // Pull only newly-arrived events; assume the events array is append-only
    // ordered by seq when present, otherwise by index. Narration events
    // styled "intro" go to the big PhaseFlash banner; everything else
    // (in-phase narrations + resolution events) joins the small ticker.
    const newItems: FlashItem[] = []
    for (const ev of events) {
      const seq = typeof ev.seq === 'number' ? ev.seq : -1
      if (seq <= lastSeenSeq.current) continue
      if (seq > lastSeenSeq.current) lastSeenSeq.current = seq

      if (ev.event_type === 'narration' && ev.data?.style === 'intro') {
        const text = String(ev.data?.text || '')
        if (!text) continue
        const kind = String(ev.data?.kind || 'info')
        const glyph = typeof ev.data?.glyph === 'string' && ev.data.glyph
          ? ev.data.glyph
          : (KIND_GLYPH[kind] || KIND_GLYPH.info)
        // Big banner — show immediately, replacing any current intro.
        const isNight = String(ev.data?.phase || '').startsWith('night')
        const sub = `第 ${ev.data?.round || round || 1} ${isNight ? '夜' : '天'}`
        setPhaseFlash({ glyph, title: text, sub })
        if (phaseTimer.current) window.clearTimeout(phaseTimer.current)
        phaseTimer.current = window.setTimeout(() => setPhaseFlash(null), PHASE_FLASH_MS)
        continue
      }

      const item = eventToFlash(ev, humanSeat)
      if (item) newItems.push(item)
    }
    if (newItems.length) setQueue((q) => [...q, ...newItems])
  }, [events, humanSeat, round])

  // Clean up phase timer on unmount
  useEffect(() => () => {
    if (phaseTimer.current) window.clearTimeout(phaseTimer.current)
  }, [])

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
  // Backend-authored narration takes precedence — these carry their own
  // localized text and tone, so we just render verbatim.
  if (ev.event_type === 'narration') {
    const text = typeof d.text === 'string' ? d.text : ''
    if (!text) return null
    const tone = (d.kind === 'wolf' || d.kind === 'good' || d.kind === 'gold' || d.kind === 'neutral')
      ? d.kind as FlashItem['tone']
      : 'neutral'
    const glyph = typeof d.glyph === 'string' && d.glyph.length > 0
      ? d.glyph
      : (tone === 'wolf' ? '🐺' : tone === 'good' ? '🌙' : tone === 'gold' ? '★' : 'ℹ')
    return { id: nextFlashId(), glyph, text, tone }
  }
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
