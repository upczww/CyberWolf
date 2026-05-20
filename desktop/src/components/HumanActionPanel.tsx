import { useEffect, useMemo, useState } from 'react'
import { apiPost } from '../hooks/useApi'
import { useGameStore, type AwaitingHumanRequest, type Player } from '../stores/game'

interface Props {
  request: AwaitingHumanRequest
  gameId: string
  players: Player[]
}

const TOOL_TITLES: Record<string, string> = {
  vote_target: '请投出你的一票',
  seer_check: '预言家请睁眼',
  witch_antidote: '女巫请睁眼',
  witch_poison: '女巫请投毒',
  wolf_kill_proposal: '狼人请行动',
  hunter_shoot: '猎人请开枪',
  public_speech: '请发表你的发言',
  death_speech: '请留下你的遗言',
  sheriff_candidacy: '警长竞选',
}

const ROLE_LABELS: Record<string, string> = {
  wolf: '狼人', seer: '预言家', witch: '女巫', hunter: '猎人',
  idiot: '白痴', guard: '守卫', villager: '村民',
}

const ROLE_AVATARS: Record<string, string> = {
  wolf: '/assets/avatars/wolf.png',
  seer: '/assets/avatars/seer.png',
  witch: '/assets/avatars/witch.png',
  hunter: '/assets/avatars/hunter.png',
  idiot: '/assets/avatars/idiot.png',
  villager: '/assets/avatars/villager.png',
}

export default function HumanActionPanel({ request, gameId, players }: Props) {
  const { clearAwaitingHuman } = useGameStore()
  const [remaining, setRemaining] = useState(Math.max(5, Math.floor(request.timeout_seconds || 60)))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [speechText, setSpeechText] = useState('')

  useEffect(() => {
    setRemaining(Math.max(5, Math.floor(request.timeout_seconds || 60)))
    setError(null)
    setSpeechText('')
  }, [request.actor_id, request.tool_name, request.phase, request.round, request.timeout_seconds])

  useEffect(() => {
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(id)
  }, [request.actor_id, request.tool_name])

  const alivePlayers = useMemo(
    () => players.filter((p) => p.survived).sort((a, b) => a.seat_index - b.seat_index),
    [players],
  )
  const candidates = useMemo(
    () => alivePlayers.filter((p) => p.seat_index !== request.actor_id),
    [alivePlayers, request.actor_id],
  )

  const submit = async (args: Record<string, unknown>) => {
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await apiPost<{ accepted: boolean; reason?: string }>(
        `/api/games/${gameId}/human_action`,
        { actor_id: request.actor_id, tool_name: request.tool_name, args },
      )
      if (!res.accepted) {
        setError(res.reason || '后端未接受')
      } else {
        clearAwaitingHuman()
      }
    } catch (e) {
      setError(`提交失败: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  const skip = () => submit(request.local_args || {})

  const title = TOOL_TITLES[request.tool_name] || request.tool_name
  const role = request.role || 'villager'
  const isSpeech = request.tool_name === 'public_speech' || request.tool_name === 'death_speech'
  const isWitchAntidote = request.tool_name === 'witch_antidote'
  const isWitchPoison = request.tool_name === 'witch_poison'
  const canSelfDestruct =
    request.role === 'wolf' &&
    ['day_speech', 'day_vote', 'sheriff_election'].includes(request.phase)
  const hint = roleHint(request.role, request.tool_name, request.phase)
  const timelineSteps = buildTimeline(request.phase, request.tool_name)

  return (
    <div className="skill-overlay">
      <div className="skill-card">
        <header>
          <span className="role-tag">{ROLE_LABELS[role] || '人类'} · {request.actor_id} 号</span>
          <span className={`skill-timer ${remaining <= 10 ? 'urgent' : ''}`}>{remaining}s</span>
        </header>

        <h2 className="skill-title">{title}</h2>

        {(isWitchAntidote || isWitchPoison) && (
          <div className="skill-prompt">
            <span className="glyph">{isWitchAntidote ? '🧪' : '☠'}</span>
            <span>
              {isWitchAntidote ? '药剂' : '毒药'} ·
              <em>{String(request.local_args?.target_id ?? '?')}</em>号玩家
              {isWitchAntidote ? '被狼人击杀' : '将被毒杀'}
            </span>
          </div>
        )}

        {hint && <div className="skill-hint">{hint}</div>}

        {isSpeech && (
          <SpeechComposer
            value={speechText}
            onChange={setSpeechText}
            onSubmit={() => submit({ public_speech: speechText.trim() || `玩家${request.actor_id}的发言`, internal_thought: '' })}
            onSkip={() => submit({ public_speech: `玩家${request.actor_id}选择沉默`, internal_thought: '' })}
            submitting={submitting}
          />
        )}

        {request.tool_name === 'vote_target' && (
          <TargetGrid
            candidates={candidates}
            onPick={(target) => submit({ target_id: target })}
            onAbstain={() => submit({ target_id: null })}
            submitting={submitting}
            allowAbstain
          />
        )}

        {request.tool_name === 'wolf_kill_proposal' && (
          <TargetGrid
            candidates={alivePlayers.filter((p) => p.faction !== 'wolf')}
            onPick={(target) => submit({ target_id: target })}
            submitting={submitting}
          />
        )}

        {request.tool_name === 'seer_check' && (
          <TargetGrid
            candidates={candidates}
            onPick={(target) => submit({ target_id: target })}
            submitting={submitting}
          />
        )}

        {request.tool_name === 'hunter_shoot' && (
          <TargetGrid
            candidates={candidates}
            onPick={(target) => submit({ target_id: target })}
            onAbstain={() => submit({ target_id: null })}
            submitting={submitting}
            allowAbstain
            abstainLabel="不开枪"
          />
        )}

        {isWitchAntidote && (
          <div className="skill-choices">
            <button className="skill-choice primary" onClick={() => submit({ use_antidote: true })} disabled={submitting}>
              <span className="glyph">🧪</span>
              <b>使用解药</b>
              <small>救回今晚目标</small>
            </button>
            <button className="skill-choice" onClick={skip} disabled={submitting}>
              <span className="glyph">👁</span>
              <b>静默观察</b>
              <small>暂不出手</small>
            </button>
            <button className="skill-choice" onClick={() => submit({ use_antidote: false })} disabled={submitting}>
              <span className="glyph">✕</span>
              <b>不使用</b>
              <small>保留至后续</small>
            </button>
          </div>
        )}

        {isWitchPoison && (
          <>
            <p style={{ textAlign: 'center', color: 'var(--text-200)', fontSize: 13, letterSpacing: '0.08em', marginBottom: 10 }}>
              选择毒杀目标（或跳过）
            </p>
            <TargetGrid
              candidates={candidates}
              onPick={(target) => submit({ target_id: target })}
              onAbstain={() => submit({ target_id: null })}
              submitting={submitting}
              allowAbstain
              abstainLabel="不投毒"
            />
          </>
        )}

        {request.tool_name === 'sheriff_candidacy' && (
          <div className="skill-choices">
            <button className="skill-choice primary" onClick={() => submit({ target_id: request.actor_id })} disabled={submitting}>
              <span className="glyph">★</span>
              <b>我要竞选</b>
              <small>发言权重 1.5</small>
            </button>
            <button className="skill-choice" onClick={() => submit({ target_id: null })} disabled={submitting}>
              <span className="glyph">—</span>
              <b>不参选</b>
              <small>放弃警徽</small>
            </button>
          </div>
        )}

        {timelineSteps.length > 0 && (
          <div className="skill-timeline">
            {timelineSteps.map((s, i) => (
              <span key={s.label} style={{ display: 'contents' }}>
                <div className={`step ${s.state}`}>
                  <span className="ico">{s.glyph}</span>
                  <span>{s.label}</span>
                </div>
                {i < timelineSteps.length - 1 && <span className="sep">·</span>}
              </span>
            ))}
          </div>
        )}

        <footer>
          <button className="ghost-btn" onClick={skip} disabled={submitting}>跳过（AI 推荐）</button>
          {canSelfDestruct && (
            <button
              className="self-destruct"
              onClick={() => {
                if (!confirm('确定狼人自爆？当前阶段立即结束。')) return
                submit({ _wolf_self_destruct: true })
              }}
              disabled={submitting}
            >
              💥 狼人自爆
            </button>
          )}
          {error ? <span className="panel-error">{error}</span> : null}
        </footer>
      </div>
    </div>
  )
}

function TargetGrid({
  candidates,
  onPick,
  onAbstain,
  submitting,
  allowAbstain = false,
  abstainLabel = '弃权',
}: {
  candidates: Player[]
  onPick: (seat: number) => void
  onAbstain?: () => void
  submitting: boolean
  allowAbstain?: boolean
  abstainLabel?: string
}) {
  return (
    <div className="skill-targets">
      {candidates.map((p) => (
        <button
          key={p.player_id}
          className="skill-target"
          onClick={() => onPick(p.seat_index)}
          disabled={submitting}
        >
          <span className="seat-num">{p.seat_index}</span>
          <img src={portraitFor(p)} alt="" />
          <b>{p.seat_index}号</b>
        </button>
      ))}
      {allowAbstain && onAbstain && (
        <button className="skill-target abstain" onClick={onAbstain} disabled={submitting}>
          <span className="seat-num" style={{ background: '#4a5670' }}>·</span>
          <b style={{ marginTop: 8 }}>{abstainLabel}</b>
        </button>
      )}
    </div>
  )
}

function portraitFor(p: Player): string {
  if (p.faction === 'wolf') return '/assets/ui/cards/unknown_avatar.png'
  if (p.role && ROLE_AVATARS[p.role]) return ROLE_AVATARS[p.role]
  return '/assets/ui/cards/unknown_avatar.png'
}

interface TimelineStep {
  label: string
  glyph: string
  state: 'is-done' | 'is-active' | 'is-todo'
}

function buildTimeline(phase: string, tool: string): TimelineStep[] {
  // Show the night sequence when relevant
  if (phase.startsWith('night') || tool.startsWith('witch') || tool === 'seer_check' || tool === 'wolf_kill_proposal') {
    return [
      { label: '狼人行动', glyph: '🐺', state: phaseOrder('night_wolf', phase) },
      { label: '预言家查验', glyph: '👁', state: phaseOrder('night_seer', phase) },
      { label: '女巫行动', glyph: '🧪', state: phaseOrder('night_witch', phase) },
    ]
  }
  if (phase === 'sheriff_election') {
    return [
      { label: '竞选报名', glyph: '★', state: 'is-active' },
      { label: '竞选发言', glyph: '🗣', state: 'is-todo' },
      { label: '警长投票', glyph: '⚖', state: 'is-todo' },
    ]
  }
  if (phase === 'day_speech' || phase === 'day_vote' || phase === 'day_announce') {
    return [
      { label: '警长竞选', glyph: '★', state: 'is-done' },
      { label: '发言阶段', glyph: '🗣', state: phase === 'day_speech' ? 'is-active' : 'is-done' },
      { label: '投票阶段', glyph: '⚖', state: phase === 'day_vote' ? 'is-active' : (phase === 'day_announce' ? 'is-done' : 'is-todo') },
      { label: '夜晚结算', glyph: '🌙', state: 'is-todo' },
    ]
  }
  return []
}

function phaseOrder(target: string, current: string): 'is-done' | 'is-active' | 'is-todo' {
  const order = ['night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_resolve']
  const ci = order.indexOf(current)
  const ti = order.indexOf(target)
  if (ti < 0 || ci < 0) return target === current ? 'is-active' : 'is-todo'
  if (ti < ci) return 'is-done'
  if (ti === ci) return 'is-active'
  return 'is-todo'
}

function roleHint(role: string, tool: string, phase: string): string | null {
  if (!role) return null
  if (role === 'wolf') {
    if (tool === 'wolf_kill_proposal') return '夜刀目标：优先击杀强神（预言家／女巫／猎人）。注意不要刀到同伴。'
    if (tool === 'vote_target' && phase === 'sheriff_election') return '警长竞选投票：狼队通常抱团给设计好的悍跳狼。'
    if (tool === 'vote_target') return '白天投票：跟刀好人或制造混乱；别投己方狼人除非必须做局。'
    if (tool === 'public_speech') return '可悍跳预言家／装好人／带节奏。点 💥 自爆可立即结束发言并取消投票。'
    if (tool === 'sheriff_candidacy') return '狼队通常派一名悍跳预言家。其他狼一般不上警。'
    if (tool === 'death_speech') return '继续身份伪装／划水／不暴露同伴。'
  }
  if (role === 'seer') {
    if (tool === 'seer_check') return '查验目标：验你怀疑的对象。首夜通常验"看起来威胁大"的玩家。'
    if (tool === 'public_speech') return '作为预言家应主动跳身份，通报昨夜查验结果。'
    if (tool === 'vote_target') return '跟自己验出的狼或可疑对象。'
    if (tool === 'sheriff_candidacy') return '预言家几乎必上警争夺警徽，死亡可传警徽流。'
  }
  if (role === 'witch') {
    if (tool === 'witch_antidote') return '解药：首夜可自救；之后救强神价值最高。同时使用解药＋毒药会浪费一晚。'
    if (tool === 'witch_poison') return '毒药：看到明显是狼的目标再用；乱毒强神是大忌。'
    if (tool === 'public_speech') return '可隐藏身份，也可在关键时点亮"我是女巫，昨夜救了 X／毒了 Y"。'
  }
  if (role === 'hunter') {
    if (tool === 'hunter_shoot') return '被毒不能开枪；否则可以带走一名怀疑对象。'
    if (tool === 'public_speech') return '可明跳"我是猎人，大家投我警将开枪"或藏身份。'
  }
  if (role === 'idiot' && tool === 'public_speech') return '白痴尽量伪装村民。被投出后翻牌可继续存活但失去投票权。'
  if (role === 'villager' && tool === 'public_speech') return '村民最重要的是逻辑梳理＋给神队让位。'
  if (tool === 'sheriff_candidacy') return '警长发言权重 1.5 倍，死亡可传警徽。综合身份与局势决定是否参选。'
  return null
}

function SpeechComposer({
  value,
  onChange,
  onSubmit,
  onSkip,
  submitting,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  onSkip: () => void
  submitting: boolean
}) {
  return (
    <div className="speech-composer">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入你的发言…"
        rows={4}
        disabled={submitting}
      />
      <div style={{ display: 'flex', gap: 10, marginTop: 12, justifyContent: 'flex-end' }}>
        <button className="ghost-btn" onClick={onSkip} disabled={submitting}>选择沉默</button>
        <button
          className="stage-btn primary"
          style={{ minWidth: 140, height: 42, fontSize: 14 }}
          onClick={onSubmit}
          disabled={submitting || !value.trim()}
        >
          发布发言
        </button>
      </div>
    </div>
  )
}
