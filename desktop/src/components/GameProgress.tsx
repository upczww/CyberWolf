import { useEffect, useRef, useState } from 'react'
import type { GameEvent } from '../stores/game'

/**
 * GameProgress — friendly progress prompts for the seated human player.
 *
 * Renders two transient banners on top of the in-game UI:
 *   • PhaseFlash    — a centered title when the phase changes
 *                     (e.g. 狼人请睁眼 / 天亮了).
 *   • EventFlash    — a centered ticker for major resolutions
 *                     (e.g. 4 号当选警长 / 平票进入加赛 / 8 号被放逐).
 *
 * Each banner shows a game-art icon (from /assets/ui/icons, resolved by
 * phase / event_type / cause) rather than an emoji glyph.
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
// PhaseFlash has no auto-dismiss timer — it stays on screen until the
// next phase's intro narration replaces it, so night phases (which the
// backend holds for 15-30s) keep their title visible the whole way.
// EventFlash items pop one at a time from a queue.
const EVENT_FLASH_MS = 3800

// Progress banners use game-art icons (not emoji). `glyph` holds an
// asset URL rendered as <img>.
const ICON = '/assets/ui/icons'

// Phase-intro / in-phase narration → contextual icon. Keyed first on the
// 遗言 glyph hint, then phase, then tone (kind) as a fallback.
function narrationIcon(data: Record<string, unknown>): string {
  const phase = String(data?.phase ?? '')
  const kind = String(data?.kind ?? 'info')
  const glyph = String(data?.glyph ?? '')
  if (glyph === '🪦') return `${ICON}/status/icon_status_last_words.png`
  switch (phase) {
    case 'setup_game':        return `${ICON}/actions/icon_action_confirm.png`
    case 'night_start':       return `${ICON}/status/icon_status_identity_hidden.png`
    case 'night_wolf':        return `${ICON}/skills/icon_skill_wolf_kill.png`
    case 'night_seer':        return `${ICON}/skills/icon_skill_seer_check.png`
    case 'night_witch':       return `${ICON}/skills/icon_skill_witch_heal.png`
    case 'night_guard':       return `${ICON}/skills/icon_skill_guard_protect.png`
    case 'night_hunter':      return `${ICON}/skills/icon_skill_hunter_shoot.png`
    case 'night_idiot_reveal':return `${ICON}/skills/icon_skill_idiot_reveal.png`
    case 'night_resolve':     return `${ICON}/actions/icon_action_record.png`
    case 'day_announce':      return kind === 'wolf'
      ? `${ICON}/status/icon_status_dead.png`
      : `${ICON}/status/icon_status_saved.png`
    case 'sheriff_election':  return `${ICON}/actions/icon_action_campaign.png`
    case 'day_speech':        return `${ICON}/status/icon_status_speaking.png`
    case 'day_vote':          return `${ICON}/actions/icon_action_vote.png`
    case 'day_resolve':       return `${ICON}/status/icon_status_voted.png`
    default:                  return kindIcon(kind)
  }
}

function kindIcon(kind: string): string {
  switch (kind) {
    case 'gold': return `${ICON}/status/icon_status_sheriff.png`
    case 'wolf': return `${ICON}/roles/icon_role_werewolf.png`
    case 'good': return `${ICON}/skills/icon_result_good.png`
    default:     return '/assets/ui/components/toast_info.png'
  }
}

function causeIcon(cause: unknown): string {
  switch (cause) {
    case 'wolf':
    case 'wolf_kill':     return `${ICON}/status/icon_status_knifed.png`
    case 'poison':        return `${ICON}/status/icon_status_poisoned.png`
    case 'exile':         return `${ICON}/status/icon_status_exiled.png`
    case 'hunter':
    case 'hunter_shot':   return `${ICON}/status/icon_status_shot.png`
    case 'self_destruct': return `${ICON}/status/icon_status_self_destruct.png`
    default:              return `${ICON}/status/icon_status_dead.png`
  }
}

interface FlashItem {
  id: number
  glyph: string  // asset URL
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
        const glyph = narrationIcon(ev.data || {})
        // Big banner — show immediately. The banner stays visible until
        // the NEXT intro narration replaces it (or game ends). No
        // auto-dismiss timer: backend night phases hold for 15-30s and
        // we want the phase title visible the whole time, not just for
        // PHASE_FLASH_MS then a blank stretch until the next role-call.
        const isNight = String(ev.data?.phase || '').startsWith('night')
        const sub = `第 ${ev.data?.round || round || 1} ${isNight ? '夜' : '天'}`
        setPhaseFlash({ glyph, title: text, sub })
        if (phaseTimer.current) {
          window.clearTimeout(phaseTimer.current)
          phaseTimer.current = null
        }
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
          <img className="phase-flash-glyph" src={phaseFlash.glyph} alt="" />
          <div className="phase-flash-stack">
            <b>{phaseFlash.title}</b>
            <span>{phaseFlash.sub}</span>
          </div>
        </div>
      )}
      {active && (
        <div className={`event-flash tone-${active.tone}`} key={active.id}>
          <img className="event-flash-glyph" src={active.glyph} alt="" />
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
    return { id: nextFlashId(), glyph: narrationIcon(d), text, tone }
  }
  switch (ev.event_type) {
    case 'sheriff_elected': {
      const pid = d.player_id ?? d.target_id
      const glyph = `${ICON}/status/icon_status_sheriff.png`
      if (pid == null) return { id: nextFlashId(), glyph, text: '无人当选警长', tone: 'neutral' }
      const isMe = humanSeat != null && Number(pid) === humanSeat
      return { id: nextFlashId(), glyph, text: isMe ? `你当选为警长` : `${pid} 号当选警长`, tone: 'gold' }
    }
    case 'sheriff_transferred': {
      const pid = d.target_id ?? d.player_id
      return { id: nextFlashId(), glyph: `${ICON}/status/icon_status_sheriff.png`, text: pid == null ? '警徽撕毁' : `警徽传给 ${pid} 号`, tone: 'gold' }
    }
    case 'vote_resolved': {
      const chosen = d.chosen
      const glyph = `${ICON}/actions/icon_action_vote.png`
      if (chosen == null) return { id: nextFlashId(), glyph: `${ICON}/status/icon_status_pk.png`, text: '平票，未放逐', tone: 'neutral' }
      const isMe = humanSeat != null && Number(chosen) === humanSeat
      return { id: nextFlashId(), glyph, text: isMe ? '你被投票放逐' : `${chosen} 号被投票放逐`, tone: 'wolf' }
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
        glyph: causeIcon(cause),
        text: isMe ? `你出局 · ${causeText}` : `${pid ?? '?'} 号出局 · ${causeText}`,
        tone: 'wolf',
      }
    }
    case 'hunter_shot': {
      const target = d.target_id
      return { id: nextFlashId(), glyph: `${ICON}/skills/icon_skill_hunter_shoot.png`, text: target == null ? '猎人未开枪' : `猎人开枪 → ${target} 号`, tone: 'wolf' }
    }
    case 'wolf_self_destruct': {
      const pid = d.player_id
      return { id: nextFlashId(), glyph: `${ICON}/status/icon_status_self_destruct.png`, text: `${pid ?? '?'} 号狼人自爆`, tone: 'wolf' }
    }
    case 'game_ended': {
      const w = d.winner
      return {
        id: nextFlashId(),
        glyph: w === 'wolf' ? `${ICON}/status/icon_wolf_win.png` : `${ICON}/status/icon_good_win.png`,
        text: w === 'wolf' ? '狼人阵营胜利' : '好人阵营胜利',
        tone: w === 'wolf' ? 'wolf' : 'good',
      }
    }
    default:
      return null
  }
}
