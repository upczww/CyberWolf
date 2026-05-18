import { useCallback, useEffect, useState } from 'react'
import { useGameStore } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet } from './hooks/useApi'
import Background from './components/Background'
import CircularTable from './components/CircularTable'
import EventFeed from './components/EventFeed'
import GameEffects from './components/GameEffects'
import PhaseBar from './components/PhaseBar'
import MusicStudio from './components/MusicStudio'
import Toolbar from './components/Toolbar'
import GameList from './components/GameList'

export default function App() {
  const { gameId, players, events, phase, round, winner, setGameId, setPlayers, setEvents, setPhase, setRound, setStatus, setWinner, reset } = useGameStore()
  const [showMusicStudio, setShowMusicStudio] = useState(false)
  const [showGameList, setShowGameList] = useState(false)

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
      // server not ready
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

  // Split players: 1-6 left, 7-12 right
  const sorted = [...players].sort((a, b) => a.seat_index - b.seat_index)
  const leftPlayers = sorted.filter(p => p.seat_index <= 6)
  const rightPlayers = sorted.filter(p => p.seat_index > 6)

  return (
    <div className="h-screen flex flex-col relative overflow-hidden">
      {/* Animated background */}
      <Background phase={phase} />

      {/* Game event effects */}
      <GameEffects latestEvent={events.length > 0 ? events[events.length - 1] : null} />

      {/* Title bar */}
      <PhaseBar phase={phase} round={round} winner={winner} players={players} />

      {/* Main: left players | center (title + events) | right players */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Left players */}
        <div className="w-52 flex flex-col justify-evenly py-2 px-2 bg-black/20 backdrop-blur-sm border-r border-white/5">
          {leftPlayers.map((player) => (
            <CircularTable key={player.player_id} player={player} currentPhase={phase} />
          ))}
          {leftPlayers.length === 0 && Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 rounded-xl border border-white/5 bg-white/5" />
          ))}
        </div>

        {/* Center: phase title + event log */}
        <div className="flex-1 flex flex-col bg-black/30 backdrop-blur-sm">
          {/* Center title */}
          <CenterTitle phase={phase} round={round} winner={winner} />
          {/* Event feed */}
          <EventFeed events={events} />
        </div>

        {/* Right players */}
        <div className="w-52 flex flex-col justify-evenly py-2 px-2 bg-black/20 backdrop-blur-sm border-l border-white/5">
          {rightPlayers.map((player) => (
            <CircularTable key={player.player_id} player={player} currentPhase={phase} />
          ))}
          {rightPlayers.length === 0 && Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 rounded-xl border border-white/5 bg-white/5" />
          ))}
        </div>
      </div>

      {/* Toolbar */}
      <Toolbar
        onGameStarted={handleGameStarted}
        onOpenMusic={() => setShowMusicStudio(true)}
        onOpenGameList={() => setShowGameList(true)}
      />

      {/* Modals */}
      {showGameList && <GameList onSelect={handleSelectGame} onClose={() => setShowGameList(false)} />}
      {showMusicStudio && <MusicStudio onClose={() => setShowMusicStudio(false)} />}
    </div>
  )
}

function CenterTitle({ phase, round, winner }: { phase: string | null; round: number; winner: string | null }) {
  const PHASE_NAMES: Record<string, string> = {
    setup_game: '初始化',
    night_start: '🌙 夜晚开始',
    night_wolf: '🐺 狼人行动',
    night_seer: '🔮 预言家查验',
    night_witch: '🧪 女巫行动',
    night_resolve: '夜晚结算',
    day_announce: '☀ 天亮公布',
    sheriff_election: '👑 警长竞选',
    day_speech: '💬 白天发言',
    day_vote: '🗳 投票',
    day_resolve: '放逐结算',
    pending_skills: '⚡ 技能结算',
    check_win: '胜负检查',
    game_over: '🏆 游戏结束',
  }

  return (
    <div className="px-4 py-2 border-b border-white/10 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold text-white/80">R{round}</span>
        <span className="text-sm text-cyan-300 font-medium">
          {phase ? PHASE_NAMES[phase] || phase : '等待开始'}
        </span>
      </div>
      {winner && (
        <span className="text-sm font-bold text-green-400 animate-pulse">
          🏆 {winner === 'good' ? '好人阵营' : '狼人阵营'}获胜
        </span>
      )}
    </div>
  )
}
