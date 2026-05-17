import { useState } from 'react'
import { useGameStore } from '../stores/game'
import { apiPost, apiDelete } from '../hooks/useApi'

interface Props {
  onGameStarted: (gameId: string) => void
}

export default function Toolbar({ onGameStarted }: Props) {
  const { gameId, status, loading, connected } = useGameStore()
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
    } catch (e) {
      console.error('Start failed:', e)
    } finally {
      useGameStore.getState().setLoading(false)
    }
  }

  const deleteGame = async () => {
    if (!gameId || !confirm('确定删除当前对局？')) return
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
        setReplayText(`${r.summary || ''}\n转折: ${r.turning_point || '-'}\n获胜: ${r.winner_reason || '-'}`)
      } else {
        setReplayText(`失败: ${res.error || 'unknown'}`)
      }
    } catch { setReplayText('请求失败') }
    finally { setReplaying(false) }
  }

  return (
    <div className="relative z-20 bg-black/50 backdrop-blur-md border-t border-white/10 px-4 py-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => startGame(false)}
          disabled={loading}
          className="px-4 py-1.5 bg-green-600/80 hover:bg-green-500/80 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors disabled:opacity-40"
        >
          ⚡ 新局
        </button>
        <button
          onClick={() => startGame(true)}
          disabled={loading}
          className="px-4 py-1.5 bg-blue-600/80 hover:bg-blue-500/80 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors disabled:opacity-40"
        >
          🤖 新局 (LLM)
        </button>
        <button
          onClick={runReplay}
          disabled={!gameId || status !== 'completed' || replaying}
          className="px-4 py-1.5 bg-purple-600/80 hover:bg-purple-500/80 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors disabled:opacity-40"
        >
          {replaying ? '⏳ 分析中...' : '📊 复盘'}
        </button>
        <button
          onClick={deleteGame}
          disabled={!gameId}
          className="px-4 py-1.5 bg-red-800/60 hover:bg-red-700/60 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors disabled:opacity-40"
        >
          🗑 删除
        </button>

        <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
          <span className={connected ? 'text-green-400' : 'text-gray-600'}>
            {connected ? '● 已连接' : '○ 未连接'}
          </span>
          {gameId && <span className="font-mono">{gameId.slice(0, 8)}</span>}
        </div>
      </div>

      {replayText && (
        <div className="text-xs bg-white/5 border border-white/10 rounded-lg p-3 max-h-24 overflow-y-auto whitespace-pre-wrap text-gray-300">
          {replayText}
        </div>
      )}
    </div>
  )
}
