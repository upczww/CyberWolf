/**
 * Event-driven action cues for key Werewolf moments.
 *
 * The goal is clarity first: every critical action should show who acted,
 * who was targeted, and what the ruling/result was.
 */
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { GameEvent } from '../stores/game'

interface Props {
  latestEvent: GameEvent | null
}

type CueKind =
  | 'wolf_kill'
  | 'seer_check'
  | 'witch_antidote'
  | 'witch_poison'
  | 'vote_cast'
  | 'vote_resolved'
  | 'hunter_shot'
  | 'death'
  | 'self_destruct'
  | 'victory_good'
  | 'victory_wolf'

type CueTone = 'wolf' | 'seer' | 'heal' | 'poison' | 'vote' | 'exile' | 'hunter' | 'death' | 'gold'

interface ActionCue {
  kind: CueKind
  tone: CueTone
  icon: string
  title: string
  subtitle: string
  from?: string
  to?: string
  result?: string
  duration: number
}

interface ActiveCue {
  id: number
  cue: ActionCue
}

const ICONS = {
  claw: '/assets/ui/icons/skills/icon_skill_wolf_kill.png',
  seer: '/assets/ui/icons/skills/icon_skill_seer_check.png',
  antidote: '/assets/ui/icons/skills/icon_skill_witch_heal.png',
  poison: '/assets/ui/icons/skills/icon_skill_witch_poison.png',
  vote: '/assets/ui/icons/actions/icon_action_vote.png',
  hunter: '/assets/ui/icons/skills/icon_skill_hunter_shoot.png',
  selfDestruct: '/assets/ui/icons/actions/icon_action_explode.png',
  exile: '/assets/ui/icons/status/icon_status_exiled.png',
  goodVictory: '/assets/ui/icons/status/icon_good_win.png',
  wolfVictory: '/assets/ui/icons/status/icon_wolf_win.png',
}

// Events that supersede an in-flight cue and should dismiss it immediately,
// even if its duration timer hasn't elapsed. Without this, a long cue (e.g.
// 1900ms "狼刀锁定") visually overlaps the next phase's UI when the engine
// transitions faster than the animation — e.g. seer starts checking while
// the wolf-kill overlay is still on screen.
const SUPERSEDING_EVENT_TYPES = new Set([
  'phase_started',
  'awaiting_human',
  'game_ended',
])

export default function GameEffects({ latestEvent }: Props) {
  const [active, setActive] = useState<ActiveCue | null>(null)

  useEffect(() => {
    if (!latestEvent) return
    if (SUPERSEDING_EVENT_TYPES.has(latestEvent.event_type)) {
      setActive(null)
      return
    }
    const cue = cueFromEvent(latestEvent)
    if (!cue) return

    const id = Date.now()
    setActive({ id, cue })
    const timer = window.setTimeout(() => {
      setActive(null)
    }, cue.duration)

    return () => window.clearTimeout(timer)
  }, [latestEvent])

  return (
    <AnimatePresence>
      {active && <ActionCueOverlay key={active.id} cue={active.cue} />}
    </AnimatePresence>
  )
}

function cueFromEvent(event: GameEvent): ActionCue | null {
  const d = event.data || {}
  const type = event.event_type
  const content = event.content

  if (type === 'wolf_target_selected') {
    const target = seatLabel(d.target_id)
    const actor = seatLabel(firstValue(d.player_id, d.actor_id, d.source_id, firstVoteActor(d.votes)))
    return {
      kind: 'wolf_kill',
      tone: 'wolf',
      icon: ICONS.claw,
      title: '狼刀锁定',
      subtitle: '狼队夜间袭击目标已确定',
      from: actor,
      to: target,
      result: target ? `${target} 成为夜刀目标` : '夜刀目标已记录',
      duration: 1900,
    }
  }

  if (type === 'seer_checked') {
    const target = seatLabel(d.target_id)
    const result = seerResultText(d.result)
    return {
      kind: 'seer_check',
      tone: 'seer',
      icon: ICONS.seer,
      title: '预言家查验',
      subtitle: '查验光束已指向目标',
      from: seatLabel(firstValue(d.player_id, d.actor_id)),
      to: target,
      result: target ? `${target} 的身份倾向：${result}` : `查验结果：${result}`,
      duration: 2050,
    }
  }

  if (type === 'witch_used_antidote') {
    const target = seatLabel(d.target_id)
    return {
      kind: 'witch_antidote',
      tone: 'heal',
      icon: ICONS.antidote,
      title: '女巫使用解药',
      subtitle: '解药生效，抵消本夜致命伤害',
      from: seatLabel(firstValue(d.player_id, d.actor_id)),
      to: target,
      result: target ? `${target} 被救下` : '解药已生效',
      duration: 1900,
    }
  }

  if (type === 'witch_used_poison') {
    const target = seatLabel(d.target_id)
    return {
      kind: 'witch_poison',
      tone: 'poison',
      icon: ICONS.poison,
      title: '女巫使用毒药',
      subtitle: '毒药目标已确认',
      from: seatLabel(firstValue(d.player_id, d.actor_id)),
      to: target,
      result: target ? `${target} 中毒出局` : '毒药已投放',
      duration: 1950,
    }
  }

  if (type === 'vote_cast') {
    const from = seatLabel(d.voter_id)
    const to = seatLabel(d.target_id)
    return {
      kind: 'vote_cast',
      tone: 'vote',
      icon: ICONS.vote,
      title: '投票记录',
      subtitle: '本票已计入白天投票',
      from,
      to,
      result: from && to ? `${from} 投给 ${to}` : '投票已记录',
      duration: 1350,
    }
  }

  if (type === 'vote_resolved') {
    const chosen = seatLabel(d.chosen)
    const tied = !chosen
    return {
      kind: 'vote_resolved',
      tone: tied ? 'vote' : 'exile',
      icon: tied ? ICONS.vote : ICONS.exile,
      // One-line death message — no subtitle/from/to chrome (per request).
      title: tied ? '平票 · 无人被放逐' : `${chosen} 被投票放逐`,
      subtitle: '',
      duration: 1800,
    }
  }

  if (type === 'hunter_shot' || content === 'event.hunter_shot') {
    const target = seatLabel(d.target_id)
    return {
      kind: 'hunter_shot',
      tone: 'hunter',
      icon: ICONS.hunter,
      title: '猎人发动技能',
      subtitle: '猎枪目标已确认',
      from: seatLabel(firstValue(d.player_id, d.actor_id)),
      to: target,
      result: target ? `猎人带走 ${target}` : '猎人开枪',
      duration: 1800,
    }
  }

  if (type === 'wolf_self_destruct') {
    return {
      kind: 'self_destruct',
      tone: 'wolf',
      icon: ICONS.selfDestruct,
      title: '狼人自爆',
      subtitle: '发言中断，立即进入夜晚',
      from: seatLabel(firstValue(d.player_id, d.actor_id)),
      result: '自爆生效',
      duration: 2200,
    }
  }

  if (type === 'player_died') {
    const target = seatLabel(d.player_id || d.target_id)
    // Single-line "X 号 + cause" message, no extra chrome.
    const causeText = deathCauseText(d.cause)
    return {
      kind: 'death',
      tone: 'death',
      icon: deathIcon(d.cause),
      title: target ? `${target}${causeText}` : '出局已结算',
      subtitle: '',
      duration: 1500,
    }
  }

  return null
}

function ActionCueOverlay({ cue }: { cue: ActionCue }) {
  return (
    <motion.div
      className={`effect-overlay effect-tone-${cue.tone}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <motion.div
        className="effect-vignette"
        initial={{ opacity: 0 }}
        animate={{ opacity: [0, 1, 0.72] }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.45 }}
      />

      <motion.div
        className="effect-motion-stage"
        initial={{ scale: 0.96, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.98, y: -10, opacity: 0 }}
        transition={{ duration: 0.28, ease: 'easeOut' }}
      >
        <ActionSymbol cue={cue} />
        <motion.section
          className="effect-card"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.06 }}
        >
          <div className="effect-card-header">
            <img src={cue.icon} alt="" />
            <div>
              <span>裁判动作</span>
              <h2>{cue.title}</h2>
            </div>
          </div>
          {cue.subtitle && <p>{cue.subtitle}</p>}
          {(cue.from || cue.to) && (
            <div className="effect-route">
              {cue.from ? <SeatPill label="发起" value={cue.from} /> : <span className="effect-seat-placeholder" />}
              <motion.div
                className="effect-route-arrow"
                initial={{ scaleX: 0, opacity: 0 }}
                animate={{ scaleX: 1, opacity: cue.from && cue.to ? 1 : 0.45 }}
                transition={{ duration: 0.28, delay: 0.16 }}
              />
              {cue.to ? <SeatPill label="目标" value={cue.to} /> : <span className="effect-seat-placeholder" />}
            </div>
          )}
          {cue.result && <strong>{cue.result}</strong>}
        </motion.section>
      </motion.div>
    </motion.div>
  )
}

function SeatPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="effect-seat-pill">
      <small>{label}</small>
      <b>{value}</b>
    </span>
  )
}

function ActionSymbol({ cue }: { cue: ActionCue }) {
  return (
    <div className={`effect-symbol effect-symbol-${cue.kind}`}>
      <KindBackdrop kind={cue.kind} />
      <motion.img
        src={cue.icon}
        alt=""
        className="effect-symbol-icon"
        initial={{ scale: 0.52, rotate: -8, opacity: 0 }}
        animate={{ scale: [0.52, 1.12, 1], rotate: [-8, 3, 0], opacity: 1 }}
        transition={{ duration: 0.42, ease: 'easeOut' }}
      />
      <KindAccent kind={cue.kind} />
    </div>
  )
}

function KindBackdrop({ kind }: { kind: CueKind }) {
  if (kind === 'wolf_kill' || kind === 'self_destruct') {
    return <motion.img src="/assets/ui/icons/skills/icon_skill_wolf_kill.png" alt="" className="effect-art effect-art-claw" {...popSweep(-10)} />
  }

  if (kind === 'seer_check') {
    return <motion.img src="/assets/ui/icons/skills/icon_skill_seer_check.png" alt="" className="effect-art effect-art-seer" {...pulseIn()} />
  }

  if (kind === 'witch_antidote') {
    return <motion.img src="/assets/ui/icons/skills/icon_skill_witch_heal.png" alt="" className="effect-art effect-art-antidote" {...pulseIn()} />
  }

  if (kind === 'witch_poison') {
    return <motion.img src="/assets/ui/icons/skills/icon_skill_witch_poison.png" alt="" className="effect-art effect-art-poison" {...driftIn()} />
  }

  if (kind === 'hunter_shot') {
    return <motion.img src="/assets/ui/icons/skills/icon_skill_hunter_shoot.png" alt="" className="effect-art effect-art-hunter" {...boltIn()} />
  }

  if (kind === 'vote_resolved') {
    return <motion.img src="/assets/ui/icons/status/icon_status_exiled.png" alt="" className="effect-art effect-art-exile" {...stampIn()} />
  }

  return null
}

function KindAccent({ kind }: { kind: CueKind }) {
  if (kind === 'vote_cast') {
    return (
      <div className="effect-vote-slip-row">
        <motion.img src="/assets/ui/icons/actions/icon_vote_token.png" alt="" initial={{ x: -54, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.28 }} />
        <motion.img src="/assets/ui/icons/actions/icon_tutorial_next.png" alt="" initial={{ scaleX: 0, opacity: 0 }} animate={{ scaleX: 1, opacity: 1 }} transition={{ duration: 0.28, delay: 0.12 }} />
        <motion.img src="/assets/ui/icons/actions/icon_vote_token.png" alt="" initial={{ x: 54, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.28, delay: 0.18 }} />
      </div>
    )
  }

  if (kind === 'seer_check') {
    return (
      <motion.div
        className="effect-scan-line"
        initial={{ x: '-90%', opacity: 0 }}
        animate={{ x: ['-90%', '90%'], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 0.9, delay: 0.22 }}
      />
    )
  }

  if (kind === 'death') {
    return (
      <motion.div
        className="effect-break-mark"
        initial={{ scale: 0, rotate: -16, opacity: 0 }}
        animate={{ scale: [0, 1.18, 1], rotate: [-16, 3, 0], opacity: [0, 1, 0.92] }}
        transition={{ duration: 0.42 }}
      />
    )
  }

  return null
}

function popSweep(rotate: number) {
  return {
    initial: { opacity: 0, scale: 0.78, rotate },
    animate: { opacity: [0, 0.95, 0.36], scale: [0.78, 1.16, 1.24], rotate: [rotate, 0, 4] },
    transition: { duration: 0.85, ease: 'easeOut' as const },
  }
}

function pulseIn() {
  return {
    initial: { opacity: 0, scale: 0.68 },
    animate: { opacity: [0, 0.95, 0.48], scale: [0.68, 1.18, 1.32] },
    transition: { duration: 1.05, ease: 'easeOut' as const },
  }
}

function driftIn() {
  return {
    initial: { opacity: 0, scale: 0.72, y: 18 },
    animate: { opacity: [0, 0.9, 0.52], scale: [0.72, 1.2, 1.34], y: [18, -2, -18] },
    transition: { duration: 1.1, ease: 'easeOut' as const },
  }
}

function boltIn() {
  return {
    initial: { opacity: 0, x: -110, scaleX: 0.78 },
    animate: { opacity: [0, 1, 0.52], x: [-110, 18, 58], scaleX: [0.78, 1, 1.05] },
    transition: { duration: 0.58, ease: 'easeOut' as const },
  }
}

function stampIn() {
  return {
    initial: { opacity: 0, scale: 1.8, rotate: -14 },
    animate: { opacity: [0, 1, 0.86], scale: [1.8, 0.92, 1], rotate: [-14, 2, 0] },
    transition: { duration: 0.36, ease: 'easeOut' as const },
  }
}

function seatLabel(value: unknown) {
  const seat = Number(value)
  if (!Number.isFinite(seat) || seat < 1 || seat > 12) return undefined
  return `${seat}号`
}

function firstValue(...values: unknown[]) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== '') return value
  }
  return undefined
}

function firstVoteActor(votes: unknown) {
  if (!votes || typeof votes !== 'object') return undefined
  return Object.keys(votes as Record<string, unknown>)[0]
}

function seerResultText(result: unknown) {
  if (result === 'wolf' || result === 'werewolf') return '狼人'
  if (result === 'good' || result === 'villager') return '好人'
  return '未知'
}

function deathCauseText(cause: unknown) {
  // Reads naturally appended after a seat label: "8 号被狼人击杀".
  // Cause is undefined / 'unknown' for night deaths — backend hides
  // how-they-died from the public announcement, so we just say
  // "X 号死亡". Cause IS visible to the perpetrator's role via the
  // private events (and surfaces on the seat's badge there).
  if (cause === 'wolf' || cause === 'wolf_kill') return ' 被狼人击杀'
  if (cause === 'poison') return ' 被女巫毒杀'
  if (cause === 'hunter' || cause === 'hunter_shot') return ' 被猎人开枪带走'
  if (cause === 'exile') return ' 被投票放逐'
  if (cause === 'self_destruct') return ' 狼人自爆离场'
  return ' 死亡'
}

function deathIcon(cause: unknown) {
  if (cause === 'poison') return ICONS.poison
  if (cause === 'hunter_shot') return ICONS.hunter
  if (cause === 'exile') return ICONS.exile
  if (cause === 'self_destruct') return ICONS.selfDestruct
  return ICONS.claw
}
