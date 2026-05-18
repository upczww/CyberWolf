import { useEffect } from 'react'
import { useGameStore, GameSummary } from '../stores/game'
import { apiGet } from '../hooks/useApi'

interface Props {
  onSelect: (gameId: string) => void
  onClose: () => void
}

export default function GameList({ onSelect, onClose }: Props) {
  const { games, gameId } = useGameStore()

  useEffect(() => {
    loadGames()
  }, [])

  const loadGames = async () => {
    try {
      const list = await apiGet<GameSummary[]>('/api/games?limit=30')
      useGameStore.getState().setGames(list)
    } catch (e) { /* server not ready */ }
  }

  const handleSelect = (gid: string) => {
    onSelect(gid)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center" onClick={onClose}>
      <div
        className="bg-gray-900 border border-white/10 rounded-xl w-96 max-h-[70vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <h2 className="text-sm font-bold">对局记录</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {games.map((g) => (
            <div
              key={g.id}
              onClick={() => handleSelect(g.id)}
              className={`
                px-4 py-3 cursor-pointer border-b border-white/5 transition-colors
                ${g.id === gameId ? 'bg-white/10 text-white' : 'text-gray-400 hover:bg-white/5'}
              `}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-bold">{g.id.slice(0, 8)}</span>
                <span className={`text-xs ${g.winner === 'good' ? 'text-green-400' : g.winner === 'wolf' ? 'text-red-400' : 'text-yellow-400'}`}>
                  {g.status === 'completed' ? (g.winner === 'good' ? '好人胜' : '狼人胜') : g.status === 'running' ? '进行中' : g.status || ''}
                </span>
              </div>
              {g.started_at && (
                <div className="text-[10px] text-gray-600 mt-0.5">{g.started_at.slice(0, 19).replace('T', ' ')}</div>
              )}
            </div>
          ))}
          {games.length === 0 && (
            <div className="p-6 text-center text-xs text-gray-600">暂无对局记录</div>
          )}
        </div>
      </div>
    </div>
  )
}
