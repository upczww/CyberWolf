import { create } from 'zustand'

export interface GameEvent {
  game_id: string
  phase: string
  scope: string
  event_type: string
  content: string
  data: Record<string, any>
  seq?: number
  round?: number
  created_at?: string
}

export interface Player {
  player_id: number
  seat_index: number
  role: string
  faction: string
  is_sheriff: number
  survived: number
  death_cause?: string
  death_round?: number
}

export interface GameSummary {
  id: string
  config_id?: string
  status?: string
  winner?: string
  started_at?: string
  ended_at?: string
}

interface GameState {
  // Current game
  gameId: string | null
  players: Player[]
  events: GameEvent[]
  status: string | null
  winner: string | null
  phase: string | null
  round: number

  // Game list
  games: GameSummary[]

  // UI state
  loading: boolean
  connected: boolean

  // View mode + human player
  viewMode: 'god' | 'observer' | 'self'
  humanSeat: number | null
  ttsEnabled: boolean

  // Actions
  setGameId: (id: string | null) => void
  setPlayers: (players: Player[]) => void
  addEvent: (event: GameEvent) => void
  setEvents: (events: GameEvent[]) => void
  setStatus: (status: string | null) => void
  setWinner: (winner: string | null) => void
  setPhase: (phase: string | null) => void
  setRound: (round: number) => void
  setGames: (games: GameSummary[]) => void
  setLoading: (loading: boolean) => void
  setConnected: (connected: boolean) => void
  setViewMode: (mode: 'god' | 'observer' | 'self') => void
  setHumanSeat: (seat: number | null) => void
  setTtsEnabled: (enabled: boolean) => void
  reset: () => void
}

export const useGameStore = create<GameState>((set) => ({
  gameId: null,
  players: [],
  events: [],
  status: null,
  winner: null,
  phase: null,
  round: 1,
  games: [],
  loading: false,
  connected: false,
  viewMode: 'god',
  humanSeat: null,
  ttsEnabled: false,

  setGameId: (id) => set({ gameId: id }),
  setPlayers: (players) => set({ players }),
  addEvent: (event) => set((s) => ({ events: [...s.events, event] })),
  setEvents: (events) => set({ events }),
  setStatus: (status) => set({ status }),
  setWinner: (winner) => set({ winner }),
  setPhase: (phase) => set({ phase }),
  setRound: (round) => set({ round }),
  setGames: (games) => set({ games }),
  setLoading: (loading) => set({ loading }),
  setConnected: (connected) => set({ connected }),
  setViewMode: (viewMode) => set({ viewMode }),
  setHumanSeat: (humanSeat) => set({ humanSeat }),
  setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
  reset: () => set({ gameId: null, players: [], events: [], status: null, winner: null, phase: null, round: 1 }),
}))
