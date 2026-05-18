import { useState } from 'react'
import { useGameStore } from '../stores/game'
import { apiDelete, apiPost } from '../hooks/useApi'

interface Props {
  onGameStarted: (gameId: string) => void
  onOpenMusic?: () => void
  onOpenGameList?: () => void
  showTrueRoles?: boolean
  onToggleRoles?: () => void
}

const STEPS = ['入夜', '狼人', '预言家', '女巫', '天亮', '讨论', '投票']

export default function Toolbar({
  onGameStarted,
  onOpenMusic,
  onOpenGameList,
  showTrueRoles = true,
  onToggleRoles,
}: Props) {
  const { gameId, status, loading, connected, phase } = useGameStore()
  const [replaying, setReplaying] = useState(false)
  const [replayText, setReplayText] = useState<string | null>(null)

  const startGame = async (useLlm: boolean) => {
    useGameStore.getState().setLoading(true)
    try {
      const res = await apiPost<{ game_id: string }>('/api/games/start', {
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: useLlm,
      })
      onGameStarted(res.game_id)
    } catch (error) {
      console.error('Start failed:', error)
    } finally {
      useGameStore.getState().setLoading(false)
    }
  }

  const deleteGame = async () => {
    if (!gameId || !confirm('确定删除当前对局吗？')) return
    await apiDelete(`/api/games/${gameId}`)
    useGameStore.getState().reset()
  }

  const runReplay = async () => {
    if (!gameId) return
    setReplaying(true)
    setReplayText(null)
    try {
      const res = await apiPost<{ success: boolean; report?: any; error?: string }>(`/api/games/${gameId}/replay`)
      if (res.success && res.report) {
        const r = res.report
        setReplayText(`${r.summary || ''}\n转折点：${r.turning_point || '-'}\n胜因：${r.winner_reason || '-'}`)
      } else {
        setReplayText(`复盘失败：${res.error || 'unknown'}`)
      }
    } catch {
      setReplayText('复盘请求失败')
    } finally {
      setReplaying(false)
    }
  }

  return (
    <footer className="director-toolbar">
      <section className="toolbar-actions">
        <button className="primary" onClick={() => startGame(true)} disabled={loading}>
          {loading ? '启动中' : '新局 AI'}
        </button>
        <button onClick={() => startGame(false)} disabled={loading}>规则演示</button>
        <button onClick={runReplay} disabled={!gameId || status !== 'completed' || replaying}>
          {replaying ? '分析中' : '复盘'}
        </button>
        {onOpenGameList ? <button onClick={onOpenGameList}>对局库</button> : null}
        {onOpenMusic ? <button onClick={onOpenMusic}>音频台</button> : null}
        <button onClick={onToggleRoles} disabled={!onToggleRoles}>
          {showTrueRoles ? '隐藏身份' : '显示身份'}
        </button>
        <button className="danger" onClick={deleteGame} disabled={!gameId}>删除</button>
      </section>

      <section className="phase-steps">
        {STEPS.map((step) => (
          <span className={isStepActive(step, phase) ? 'active' : ''} key={step}>{step}</span>
        ))}
      </section>

      <section className="toolbar-note">
        <img src="/assets/ui/effects/antidote_glow_overlay.png" alt="" />
        <span>{connected ? '实时接收裁判事件' : '服务未连接时仍可预览导演台布局'}。导演模式可以观察 AI 记忆、行动理由和规则校验，但不改写真实局势。</span>
      </section>

      {replayText ? <pre className="replay-report">{replayText}</pre> : null}
    </footer>
  )
}

function isStepActive(step: string, phase: string | null) {
  if (!phase) return false
  if (step === '入夜') return phase === 'night_start'
  if (step === '狼人') return phase === 'night_wolf'
  if (step === '预言家') return phase === 'night_seer'
  if (step === '女巫') return phase === 'night_witch'
  if (step === '天亮') return phase === 'day_announce'
  if (step === '讨论') return phase === 'day_speech' || phase === 'sheriff_election'
  if (step === '投票') return phase === 'day_vote' || phase === 'day_resolve'
  return false
}
