import { useState } from 'react'
import { useGameStore } from '../stores/game'
import { apiDelete, apiPost } from '../hooks/useApi'

interface Props {
  onGameStarted: (gameId: string) => void
  onOpenMusic?: () => void
  onOpenGameList?: () => void
  viewMode: 'god' | 'observer' | 'self'
  onViewModeChange: (mode: 'god' | 'observer' | 'self') => void
  humanSeat: number | null
  onHumanSeatChange: (seat: number | null) => void
  ttsEnabled: boolean
  onTtsToggle: () => void
}

const STEPS = ['入夜', '狼人', '预言家', '女巫', '天亮', '讨论', '投票']

const VIEW_OPTIONS: Array<{ value: 'god' | 'observer' | 'self'; label: string; hint: string }> = [
  { value: 'god', label: '上帝视角', hint: '看到所有真实身份' },
  { value: 'observer', label: '旁观席', hint: '所有身份保密' },
  { value: 'self', label: '我加入', hint: '仅看到自己的身份' },
]

export default function Toolbar({
  onGameStarted,
  onOpenMusic,
  onOpenGameList,
  viewMode,
  onViewModeChange,
  humanSeat,
  onHumanSeatChange,
  ttsEnabled,
  onTtsToggle,
}: Props) {
  const { gameId, status, loading, connected, phase } = useGameStore()
  const [replaying, setReplaying] = useState(false)
  const [replayText, setReplayText] = useState<string | null>(null)

  const handleViewModeChange = (mode: 'god' | 'observer' | 'self') => {
    onViewModeChange(mode)
    if (mode === 'self' && humanSeat == null) {
      onHumanSeatChange(1)
    }
    if (mode !== 'self') {
      onHumanSeatChange(null)
    }
  }

  const startGame = async (useLlm: boolean) => {
    useGameStore.getState().setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: useLlm,
      }
      if (viewMode === 'self' && humanSeat) {
        payload.human_seat = humanSeat
      }
      const res = await apiPost<{ game_id: string }>('/api/games/start', payload)
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
        <button className="primary" onClick={() => startGame(true)} disabled={loading || (viewMode === 'self' && humanSeat == null)}>
          {loading ? '启动中' : '新局 AI'}
        </button>
        <button onClick={() => startGame(false)} disabled={loading}>规则演示</button>
        <button onClick={runReplay} disabled={!gameId || status !== 'completed' || replaying}>
          {replaying ? '分析中' : '复盘'}
        </button>
        {onOpenGameList ? <button onClick={onOpenGameList}>对局库</button> : null}
        {onOpenMusic ? <button onClick={onOpenMusic}>音频台</button> : null}
        <button className={`tts-toggle ${ttsEnabled ? 'on' : ''}`} onClick={onTtsToggle} title="语音播报">
          {ttsEnabled ? '🔊 语音' : '🔇 静音'}
        </button>
        <button className="danger" onClick={deleteGame} disabled={!gameId}>删除</button>
      </section>

      <section className="view-mode-toggle">
        {VIEW_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={viewMode === opt.value ? 'active' : ''}
            onClick={() => handleViewModeChange(opt.value)}
            title={opt.hint}
          >
            {opt.label}
          </button>
        ))}
        {viewMode === 'self' && (
          <label className="seat-picker">
            席位
            <select
              value={humanSeat ?? 1}
              onChange={(e) => onHumanSeatChange(Number(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n} 号</option>
              ))}
            </select>
          </label>
        )}
      </section>

      <section className="phase-steps">
        {STEPS.map((step) => (
          <span className={isStepActive(step, phase) ? 'active' : ''} key={step}>{step}</span>
        ))}
      </section>

      <section className="toolbar-note">
        <img src="/assets/ui/effects/antidote_glow_overlay.png" alt="" />
        <span>
          {connected ? '实时接收裁判事件' : '服务未连接时仍可预览导演台布局'}。
          {viewMode === 'god' && '导演模式：可看到所有 AI 的真实身份与决策。'}
          {viewMode === 'observer' && '旁观模式：仅依据公开信息推断。'}
          {viewMode === 'self' && `参与模式：你将作为 ${humanSeat ?? '?'} 号玩家，其它身份保密（行动接入开发中）。`}
        </span>
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
