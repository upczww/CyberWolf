import { useState } from 'react'
import { useGameStore } from '../stores/game'
import { apiPost, apiDelete } from '../hooks/useApi'

interface Props {
  onGameStarted: (gameId: string) => void
}

export default function Toolbar({ onGameStarted }: Props) {
  const { gameId, status, loading, connected } = useGameStore()
  const [replaying, setReplaying] = useState(false)
  const [replayResult, setReplayResult] = useState<string | null>(null)

  const startGame = async (useLlm: boolean) => {
    useGameStore.getState().setLoading(true)
    try {
      const res = await apiPost<{ game_id: string }>('/api/games/start', {
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: useLlm,
      })
      onGameStarted(res.game_id)
    } catch (e) {
      console.error('Start game failed:', e)
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
    setReplayResult(null)
    try {
      const res = await apiPost<{ success: boolean; report?: any; error?: string }>(`/api/games/${gameId}/replay`)
      if (res.success && res.report) {
        setReplayResult(res.report.summary || JSON.stringify(res.report, null, 2))
      } else {
        setReplayResult(`复盘失败: ${res.error || 'unknown'}`)
      }
    } catch (e) {
      setReplayResult('复盘请求失败')
    } finally {
      setReplaying(false)
    }
  }

  return (
    <div className="border-t border-gray-700 p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => startGame(false)}
          disabled={loading}
          className="px-3 py-1 bg-green-700 hover:bg-green-600 rounded text-sm disabled:opacity-50"
        >
          新局 (无LLM)
        </button>
        <button
          onClick={() => startGame(true)}
          disabled={loading}
          className="px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-sm disabled:opacity-50"
        >
          新局 (LLM)
        </button>
        <button
          onClick={runReplay}
          disabled={!gameId || status !== 'completed' || replaying}
          className="px-3 py-1 bg-purple-700 hover:bg-purple-600 rounded text-sm disabled:opacity-50"
        >
          {replaying ? '分析中...' : '复盘'}
        </button>
        <button
          onClick={deleteGame}
          disabled={!gameId}
          className="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-sm disabled:opacity-50"
        >
          删除
        </button>

        <span className="ml-auto text-xs text-gray-500">
          {connected ? '🟢 已连接' : '⚪ 未连接'}
          {gameId && ` | ${gameId.slice(0, 8)}`}
          {status && ` | ${status}`}
        </span>
      </div>

      {replayResult && (
        <div className="text-xs bg-gray-800 rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
          {replayResult}
        </div>
      )}
    </div>
  )
}
