import { useEffect, useMemo, useState } from 'react'
import { apiPost } from '../hooks/useApi'
import { useGameStore, type AwaitingHumanRequest, type GameEvent, type Player } from '../stores/game'

interface Props {
  request: AwaitingHumanRequest
  gameId: string
  players: Player[]
}

const TOOL_TITLES: Record<string, string> = {
  vote_target: '投票放逐',
  seer_check: '预言家查验',
  witch_antidote: '使用解药？',
  witch_poison: '使用毒药',
  wolf_kill_proposal: '狼队夜刀目标',
  hunter_shoot: '猎人开枪',
  public_speech: '公开发言',
  death_speech: '遗言',
  sheriff_candidacy: '警长竞选',
  sheriff_transfer: '警长传警徽',
}

const UNKNOWN_AVATAR = '/assets/ui/icons/status/icon_status_identity_hidden.png'
const ROLE_CARD_BACK = '/assets/ui/role_intro/role_intro_card_base_neutral.png'
const SHERIFF_BADGE = '/assets/ui/icons/status/icon_status_sheriff.png'

export default function HumanActionPanel({ request, gameId, players }: Props) {
  const { clearAwaitingHuman, events } = useGameStore()
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
  // Sheriff-election vote: backend ships the allowed candidate seats in
  // local_args.candidates. Filter the target grid to those only so the
  // human can't pick a non-candidate.
  const allowedSeats = useMemo<Set<number> | null>(() => {
    const raw = request.local_args?.candidates
    if (!Array.isArray(raw) || raw.length === 0) return null
    return new Set(raw.map((s: unknown) => Number(s)).filter((n) => Number.isFinite(n)))
  }, [request.local_args])
  const candidates = useMemo(() => {
    const base = alivePlayers.filter((p) => p.seat_index !== request.actor_id)
    if (allowedSeats && request.phase === 'sheriff_election' && request.tool_name === 'vote_target') {
      return base.filter((p) => allowedSeats.has(p.seat_index))
    }
    return base
  }, [alivePlayers, request.actor_id, allowedSeats, request.phase, request.tool_name])

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
        const reason = res.reason || 'not_pending'
        if (reason === 'no_human_in_game' || reason === 'not_pending') {
          setError('当前行动已过期，已交由 AI 接管')
          window.setTimeout(() => clearAwaitingHuman(), 1200)
          return
        }
        setError(reason || '后端未接受')
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
  const isSpeech = request.tool_name === 'public_speech' || request.tool_name === 'death_speech'
  const isWitchAntidote = request.tool_name === 'witch_antidote'
  const isWitchPoison = request.tool_name === 'witch_poison'
  const canSelfDestruct =
    request.role === 'wolf' &&
    ['day_speech', 'day_vote', 'sheriff_election'].includes(request.phase)
  const hint = roleHint(request.role, request.tool_name, request.phase)

  return (
    <div className="human-action-overlay">
      <div className="human-action-panel">
        <header>
          <span className="panel-tag">{request.role ? `${roleLabel(request.role)} · ${request.actor_id} 号` : `人类席位 · ${request.actor_id} 号`}</span>
          <h2>{title}</h2>
          <span className={`panel-timer ${remaining <= 10 ? 'urgent' : ''}`}>{remaining}s</span>
        </header>

        {hint && <p className="panel-hint">{hint}</p>}

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
            events={events}
            toolName={request.tool_name}
          />
        )}

        {request.tool_name === 'wolf_kill_proposal' && (
          <TargetGrid
            candidates={alivePlayers.filter((p) => p.faction !== 'wolf')}
            onPick={(target) => submit({ target_id: target })}
            submitting={submitting}
            events={events}
            toolName={request.tool_name}
          />
        )}

        {request.tool_name === 'seer_check' && (
          <TargetGrid
            candidates={candidates}
            onPick={(target) => submit({ target_id: target })}
            submitting={submitting}
            events={events}
            toolName={request.tool_name}
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
          <div className="witch-action">
            <p>今晚的死亡目标是 <b>{String(request.local_args?.target_id ?? '?')}</b> 号,是否使用解药?</p>
            <div className="action-buttons">
              <button onClick={() => submit({ use_antidote: true })} disabled={submitting}>使用解药</button>
              <button className="ghost" onClick={() => submit({ use_antidote: false })} disabled={submitting}>不使用</button>
            </div>
          </div>
        )}

        {isWitchPoison && (
          <div className="witch-action">
            <p>选择毒杀目标(或跳过):</p>
            <TargetGrid
              candidates={candidates}
              onPick={(target) => submit({ target_id: target })}
              onAbstain={() => submit({ target_id: null })}
              submitting={submitting}
              allowAbstain
              abstainLabel="不投毒"
            />
          </div>
        )}

        {request.tool_name === 'sheriff_candidacy' && (
          <div className="witch-action">
            <p>是否参选警长?警长发言权重 1.5,死亡可传警徽。</p>
            <div className="action-buttons">
              <button onClick={() => submit({ target_id: request.actor_id })} disabled={submitting}>参选</button>
              <button className="ghost" onClick={() => submit({ target_id: null })} disabled={submitting}>不参选</button>
            </div>
          </div>
        )}

        {request.tool_name === 'sheriff_transfer' && (
          <div className="witch-action">
            <p>你已出局，请将警徽传给一名存活玩家（也可撕毁警徽）：</p>
            <TargetGrid
              candidates={candidates}
              onPick={(target) => submit({ target_id: target })}
              onAbstain={() => submit({ target_id: null })}
              submitting={submitting}
              allowAbstain
              abstainLabel="撕毁警徽"
              events={events}
              toolName={request.tool_name}
            />
          </div>
        )}

        <footer>
          <button className="ghost" onClick={skip} disabled={submitting}>跳过(使用 AI 推荐)</button>
          {canSelfDestruct && (
            <button
              className="danger self-destruct"
              onClick={() => {
                if (!confirm('确定狼人自爆?当前阶段立即结束。')) return
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
  events = [],
  toolName = '',
  abstainLabel = '弃权',
}: {
  candidates: Player[]
  onPick: (seat: number) => void
  onAbstain?: () => void
  submitting: boolean
  allowAbstain?: boolean
  events?: GameEvent[]
  toolName?: string
  abstainLabel?: string
}) {
  return (
    <div className="target-grid">
      {candidates.map((p) => (
        <button
          key={p.player_id}
          onClick={() => onPick(p.seat_index)}
          disabled={submitting}
          className="target-button"
        >
          <span className="target-portrait">
            <img className="target-avatar" src={UNKNOWN_AVATAR} alt="" />
            <img className="target-card-back" src={ROLE_CARD_BACK} alt="" />
            {p.is_sheriff ? <img className="target-sheriff" src={SHERIFF_BADGE} alt="" /> : null}
          </span>
          <small className="target-reason">{candidateReason(p, events, toolName)}</small>
          <b>{p.seat_index} 号</b>
          <small>{p.survived ? '可选择' : '已出局'}</small>
        </button>
      ))}
      {allowAbstain && onAbstain && (
        <button className="target-button abstain" onClick={onAbstain} disabled={submitting}>
          <span className="target-portrait">
            <img className="target-avatar" src="/assets/ui/vote/abstain_mark.png" alt="" />
          </span>
          <b>{abstainLabel}</b>
          <small>保留行动</small>
        </button>
      )}
    </div>
  )
}

function candidateReason(player: Player, events: GameEvent[], toolName: string) {
  if (!player.survived) return '已出局'
  if (player.is_sheriff) return '持有警徽'

  let votes = 0
  for (const ev of events) {
    if (ev.event_type !== 'vote_cast') continue
    if (Number(ev.data?.target_id) === player.seat_index) votes += 1
  }
  if (votes > 0) return `${votes} 票指向`

  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i]
    const target = Number(ev.data?.target_id ?? ev.data?.chosen)
    if (target !== player.seat_index) continue
    if (ev.event_type === 'wolf_target_selected') return '昨夜被刀'
    if (ev.event_type === 'seer_checked') return '曾被查验'
    if (ev.event_type === 'witch_used_antidote') return '曾被救下'
    if (ev.event_type === 'witch_used_poison') return '毒药目标'
    if (ev.event_type === 'vote_resolved') return '上轮焦点'
  }

  if (toolName === 'seer_check') return '可查验'
  if (toolName === 'wolf_kill_proposal') return '可夜刀'
  if (toolName === 'hunter_shoot') return '可带走'
  if (toolName === 'witch_poison') return '可下毒'
  return '可投票'
}

const ROLE_LABELS: Record<string, string> = {
  wolf: '狼人', seer: '预言家', witch: '女巫', hunter: '猎人', idiot: '白痴', guard: '守卫', villager: '村民',
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] || role || '未知'
}

function roleHint(role: string, tool: string, phase: string): string | null {
  if (!role) return null
  // Wolf
  if (role === 'wolf') {
    if (tool === 'wolf_kill_proposal') return '夜刀目标:优先击杀强神(预言家/女巫/猎人)。注意不要刀同伴。'
    if (tool === 'vote_target' && phase === 'sheriff_election') return '警长竞选投票:狼队通常抱团给设计好的悍跳狼,争夺警徽流。'
    if (tool === 'vote_target') return '白天投票:跟刀好人或制造混乱;别投己方狼人除非必须做局。'
    if (tool === 'public_speech') return '发言阶段:可悍跳预言家/装好人/带节奏。点 💥 自爆可立即结束发言并取消投票放逐。'
    if (tool === 'sheriff_candidacy') return '警长竞选:狼队通常派一名悍跳预言家。其他狼一般不上警。'
    if (tool === 'death_speech') return '遗言:可继续身份伪装/划水/不暴露同伴。'
  }
  // Seer
  if (role === 'seer') {
    if (tool === 'seer_check') return '查验目标:验你怀疑的对象。第一晚通常验"看起来威胁大"的玩家。'
    if (tool === 'public_speech') return '发言:作为预言家应主动跳身份,通报昨夜查验结果("X 号是狼/好人")。'
    if (tool === 'vote_target') return '投票:跟自己验出的狼或可疑对象。'
    if (tool === 'sheriff_candidacy') return '警长竞选:预言家几乎必上警争夺警徽,死亡可传警徽流。'
  }
  // Witch
  if (role === 'witch') {
    if (tool === 'witch_antidote') return '解药:首夜可自救;之后救强神价值最高。同时使用解药+毒药会浪费一晚。'
    if (tool === 'witch_poison') return '毒药:看到明显是狼的目标再用;乱毒强神是大忌。'
    if (tool === 'public_speech') return '发言:可隐藏身份,也可在关键时点亮"我是女巫,昨夜救了 X / 毒了 Y"。'
    if (tool === 'vote_target') return '投票:基于私有的死亡 + 救药信息推理。'
  }
  // Hunter
  if (role === 'hunter') {
    if (tool === 'hunter_shoot') return '猎人开枪:被毒不能开枪;否则可以带走一名怀疑对象。'
    if (tool === 'public_speech') return '发言:可明跳"我是猎人,大家投我警将开枪"或藏身份。'
    if (tool === 'vote_target') return '投票:猎人不怕暴露,可大胆投票。'
  }
  // Idiot
  if (role === 'idiot') {
    if (tool === 'public_speech') return '发言:白痴尽量伪装村民。被投出后翻牌可继续存活但失去投票权。'
    if (tool === 'vote_target') return '投票:跟好人节奏,别乱站边。'
  }
  // Villager
  if (role === 'villager') {
    if (tool === 'public_speech') return '发言:村民最重要的是逻辑梳理 + 给神队让位。'
    if (tool === 'vote_target') return '投票:跟预言家给的狼或综合多神判断。'
    if (tool === 'sheriff_candidacy') return '警长竞选:普通村民原则上不上警,避免扰乱预言家视角。'
  }
  // Generic sheriff_candidacy fallback
  if (tool === 'sheriff_candidacy') {
    return '警长竞选:警长发言权重 1.5 倍,死亡可传警徽。综合身份与局势决定是否参选。'
  }
  // Generic sheriff_transfer fallback (any role can hold the badge)
  if (tool === 'sheriff_transfer') {
    if (role === 'wolf') return '传警徽：传给你的狼队同伴或一名你能伪装信任的好人；撕毁警徽也是常见操作。'
    return '传警徽：传给你最信任的好人/神职；若没有清晰目标可撕毁警徽以避免误判。'
  }
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
        placeholder="输入你的发言..."
        rows={4}
        disabled={submitting}
      />
      <div className="action-buttons">
        <button onClick={onSubmit} disabled={submitting || !value.trim()}>发布发言</button>
        <button className="ghost" onClick={onSkip} disabled={submitting}>选择沉默</button>
      </div>
    </div>
  )
}
