import { useCallback, useEffect } from 'react'
import { useGameStore } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet } from './hooks/useApi'
import Background from './components/Background'
import CircularTable from './components/CircularTable'
import EventFeed from './components/EventFeed'
import GameEffects from './components/GameEffects'
import PhaseBar from './components/PhaseBar'
import Toolbar from './components/Toolbar'
import GameList from './components/GameList'

export default function App() {
  const { gameId, players, events, phase, round, winner, setGameId, setPlayers, setEvents, setPhase, setRound, setStatus, setWinner, reset } = useGameStore()

  useGameWS(gameId)

  useEffect(() => {
    if (!gameId) return
    loadGameDetail(gameId)
  }, [gameId])

  const loadGameDetail = async (gid: string) => {
    try {
      const detail = await apiGet<any>(`/api/games/${gid}`)
      if (detail.error) return
      setPlayers(detail.players || [])
      setEvents((detail.events || []).map((ev: any) => ({
        ...ev,
        data: ev.data_json || ev.data || {},
        event_type: ev.event_type,
      })))
      const state = detail.snapshot?.state_json
      if (state) {
        setPhase(state.phase || null)
        setRound(state.round || 1)
        setStatus(detail.game?.status || null)
        setWinner(state.winner || null)
      }
    } catch (e) {
      console.error('Failed to load game:', e)
    }
  }

  const handleGameStarted = useCallback((newGameId: string) => {
    reset()
    setGameId(newGameId)
  }, [])

  const handleSelectGame = useCallback((gid: string) => {
    reset()
    setGameId(gid)
  }, [])

  return (
    <div className="h-screen flex flex-col relative overflow-hidden">
      {/* Animated background */}
      <Background phase={phase} />

      {/* Game event effects (slash, poison, heal, etc.) */}
      <GameEffects latestEvent={events.length > 0 ? events[events.length - 1] : null} />

      {/* Phase bar */}
      <PhaseBar phase={phase} round={round} winner={winner} players={players} />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Game list sidebar */}
        <GameList onSelect={handleSelectGame} />

        {/* Circular table (center) */}
        <div className="flex-1 relative">
          <CircularTable players={players} currentPhase={phase} />
        </div>

        {/* Event feed (right panel) */}
        <div className="w-80 border-l border-white/10 bg-black/40 backdrop-blur-sm flex flex-col">
          <div className="px-3 py-2 border-b border-white/10 text-sm font-bold text-gray-300">
            事件日志
          </div>
          <EventFeed events={events} />
        </div>
      </div>

      {/* Toolbar */}
      <Toolbar onGameStarted={handleGameStarted} />
    </div>
  )
}
