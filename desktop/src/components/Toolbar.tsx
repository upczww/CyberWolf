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

const STEPS: Array<{ label: string; icon: string; phases: string[] }> = [
  { label: '入夜', icon: '/assets/ui/phases/phase_night.png', phases: ['night_start'] },
  { label: '狼人', icon: '/assets/ui/icons/claw_slash.png', phases: ['night_wolf'] },
  { label: '预言家', icon: '/assets/ui/icons/seer_eye.png', phases: ['night_seer'] },
  { label: '女巫', icon: '/assets/ui/icons/antidote.png', phases: ['night_witch'] },
  { label: '天亮', icon: '/assets/ui/phases/phase_dawn.png', phases: ['day_announce', 'night_resolve'] },
  { label: '讨论', icon: '/assets/ui/icons/ballot_vote.png', phases: ['day_speech', 'sheriff_election'] },
  { label: '投票', icon: '/assets/ui/vote/vote_count_token.png', phases: ['day_vote', 'day_resolve'] },
]

const VIEW_OPTIONS: Array<{ value: 'god' | 'observer' | 'self'; label: string; hint: string }> = [
  { value: 'god', label: '导演', hint: '看到所有真实身份' },
  { value: 'observer', label: '旁观', hint: '所有身份保密' },
  { value: 'self', label: '参局', hint: '仅看到自己的身份' },
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
    // Always clear humanSeat on mode change; backend assigns at random when starting a self game.
    onHumanSeatChange(null)
  }

  const startGame = async (useLlm: boolean) => {
    useGameStore.getState().setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: useLlm,
      }
      if (viewMode === 'self') {
        payload.human_join = true
        // server picks human_seat at random
      }
      const res = await apiPost<{ game_id: string; human_seat?: number | null }>('/api/games/start', payload)
      if (viewMode === 'self' && typeof res.human_seat === 'number') {
        onHumanSeatChange(res.human_seat)
      }
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
          {loading ? '启动中' : '新局'}
        </button>
        <button onClick={() => startGame(false)} disabled={loading}>演示</button>
        <button onClick={runReplay} disabled={!gameId || status !== 'completed' || replaying}>
          {replaying ? '分析中' : '复盘'}
        </button>
        {onOpenGameList ? <button onClick={onOpenGameList}>牌局</button> : null}
        {onOpenMusic ? <button onClick={onOpenMusic}>音频</button> : null}
        <button className={`tts-toggle ${ttsEnabled ? 'on' : ''}`} onClick={onTtsToggle} title="语音播报">
          {ttsEnabled ? '语音' : '静音'}
        </button>
        <button className="danger" onClick={deleteGame} disabled={!gameId}>删局</button>
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
          <span className="seat-info">
            {humanSeat == null ? '席位随机分配' : `你的席位:${humanSeat} 号`}
          </span>
        )}
      </section>

      <section className="phase-steps">
        {STEPS.map((step) => (
          <span className={isStepActive(step, phase) ? 'active' : ''} key={step.label}>
            <img src={step.icon} alt="" />
            <b>{step.label}</b>
          </span>
        ))}
      </section>

      <section className="toolbar-note">
        <img src={connected ? '/assets/ui/status/selected.png' : '/assets/ui/status/waiting.png'} alt="" />
        <span>
          <b>{connected ? '实时连接' : '离线预览'}</b>
          {viewMode === 'god' && ' · 导演可见全部身份'}
          {viewMode === 'observer' && ' · 旁观仅看公开信息'}
          {viewMode === 'self' && (
            humanSeat == null
              ? ' · 参局后随机席位'
              : ` · 你是 ${humanSeat} 号`
          )}
        </span>
      </section>

      {replayText ? <pre className="replay-report">{replayText}</pre> : null}
    </footer>
  )
}

function isStepActive(step: { phases: string[] }, phase: string | null) {
  if (!phase) return false
  return step.phases.includes(phase)
}
