import { useCallback, useEffect } from 'react'
import { useGameStore } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet } from './hooks/useApi'
import PlayerRing from './components/PlayerRing'
import EventFeed from './components/EventFeed'
import PhaseBar from './components/PhaseBar'
import Toolbar from './components/Toolbar'
import GameList from './components/GameList'

export default function App() {
  const { gameId, players, events, phase, round, winner, setGameId, setPlayers, setEvents, setPhase, setRound, setStatus, setWinner, reset } = useGameStore()

  // Connect WebSocket to current game
  useGameWS(gameId)

  // Load game detail when gameId changes
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
      // Extract state from snapshot
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
    <div className="h-screen flex flex-col bg-gray-900 text-white">
      {/* Phase bar */}
      <PhaseBar phase={phase} round={round} winner={winner} players={players} />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Game list sidebar */}
        <GameList onSelect={handleSelectGame} />

        {/* Player ring */}
        <div className="w-80 border-r border-gray-700 overflow-y-auto">
          <PlayerRing players={players} currentPhase={phase} />
        </div>

        {/* Event feed */}
        <EventFeed events={events} />
      </div>

      {/* Toolbar */}
      <Toolbar onGameStarted={handleGameStarted} />
    </div>
  )
}
