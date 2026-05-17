import { useEffect } from 'react'
import { useGameStore, GameSummary } from '../stores/game'
import { apiGet } from '../hooks/useApi'

interface Props {
  onSelect: (gameId: string) => void
}

export default function GameList({ onSelect }: Props) {
  const { games, gameId } = useGameStore()

  useEffect(() => {
    loadGames()
    const interval = setInterval(loadGames, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadGames = async () => {
    try {
      const list = await apiGet<GameSummary[]>('/api/games?limit=20')
      useGameStore.getState().setGames(list)
    } catch (e) { /* server not ready */ }
  }

  return (
    <div className="w-44 bg-black/40 backdrop-blur-sm border-r border-white/10 overflow-y-auto">
      <div className="p-3 text-xs text-gray-400 font-bold uppercase tracking-wider">
        对局记录
      </div>
      {games.map((g) => (
        <div
          key={g.id}
          onClick={() => onSelect(g.id)}
          className={`
            px-3 py-2 cursor-pointer text-xs border-b border-white/5 transition-colors
            ${g.id === gameId ? 'bg-white/10 text-white' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}
          `}
        >
          <div className="font-mono font-bold">{g.id.slice(0, 8)}</div>
          <div className="flex items-center gap-1 mt-0.5">
            {g.status === 'completed' ? (
              <span className={g.winner === 'good' ? 'text-green-400' : 'text-red-400'}>
                {g.winner === 'good' ? '好人胜' : '狼人胜'}
              </span>
            ) : g.status === 'running' ? (
              <span className="text-yellow-400 animate-pulse">进行中</span>
            ) : (
              <span className="text-gray-600">{g.status}</span>
            )}
          </div>
        </div>
      ))}
      {games.length === 0 && (
        <div className="p-3 text-xs text-gray-600">按下方按钮开始第一局</div>
      )}
    </div>
  )
}
