import { useEffect, useMemo, useState } from 'react'
import { apiPost } from '../hooks/useApi'
import { useGameStore, type AwaitingHumanRequest, type Player } from '../stores/game'

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
  const isSpeech = request.tool_name === 'public_speech' || request.tool_name === 'death_speech'
  const isWitchAntidote = request.tool_name === 'witch_antidote'
  const isWitchPoison = request.tool_name === 'witch_poison'

  return (
    <div className="human-action-overlay">
      <div className="human-action-panel">
        <header>
          <span className="panel-tag">人类席位 · {request.actor_id} 号</span>
          <h2>{title}</h2>
          <span className={`panel-timer ${remaining <= 10 ? 'urgent' : ''}`}>{remaining}s</span>
        </header>

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

        <footer>
          <button className="ghost" onClick={skip} disabled={submitting}>跳过(使用 AI 推荐)</button>
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
    <div className="target-grid">
      {candidates.map((p) => (
        <button
          key={p.player_id}
          onClick={() => onPick(p.seat_index)}
          disabled={submitting}
          className="target-button"
        >
          <span>{p.seat_index} 号</span>
        </button>
      ))}
      {allowAbstain && onAbstain && (
        <button className="target-button abstain" onClick={onAbstain} disabled={submitting}>
          {abstainLabel}
        </button>
      )}
    </div>
  )
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
