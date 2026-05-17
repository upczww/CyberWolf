import { useEffect, useRef } from 'react'
import { useGameStore, GameEvent } from '../stores/game'

export function useGameWS(gameId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const { addEvent, setEvents, setConnected, setPhase, setRound, setStatus, setWinner } = useGameStore()

  useEffect(() => {
    if (!gameId) {
      setConnected(false)
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/ws/games/${gameId}`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)

    ws.onmessage = (msg) => {
      const payload = JSON.parse(msg.data)

      if (payload.type === 'history') {
        const ev = payload.event as GameEvent
        addEvent(ev)
      } else if (payload.type === 'history_complete') {
        // History loading done
      } else if (payload.type === 'live') {
        const ev = payload.event as GameEvent
        addEvent(ev)

        // Update game state from events
        if (ev.event_type === 'phase_started' && ev.data?.phase) {
          setPhase(ev.data.phase)
          if (ev.data.round) setRound(ev.data.round)
        }
        if (ev.event_type === 'game_ended') {
          setStatus('completed')
          setWinner(ev.data?.winner || null)
        }
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [gameId])
}
