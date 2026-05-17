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
    } catch (e) {
      // Server not ready yet
    }
  }

  return (
    <div className="w-48 border-r border-gray-700 overflow-y-auto">
      <div className="p-2 text-xs text-gray-500 font-bold uppercase">对局列表</div>
      {games.map((g) => (
        <div
          key={g.id}
          onClick={() => onSelect(g.id)}
          className={`
            px-2 py-1 cursor-pointer text-xs truncate
            ${g.id === gameId ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800'}
          `}
        >
          <span className="font-mono">{g.id.slice(0, 8)}</span>
          <span className="ml-1">
            {g.status === 'completed' ? (g.winner === 'good' ? '✅' : '❌') : g.status === 'running' ? '🔄' : ''}
          </span>
        </div>
      ))}
      {games.length === 0 && (
        <div className="p-2 text-xs text-gray-600">暂无对局</div>
      )}
    </div>
  )
}
