import { useEffect, useRef } from 'react'
import { useGameStore, GameEvent } from '../stores/game'

export function useGameWS(gameId: string | null, seat: number | null = null) {
  const wsRef = useRef<WebSocket | null>(null)
  const {
    addEvent, setEvents, setConnected, setPhase, setRound, setStatus, setWinner,
    setAwaitingHuman, clearAwaitingHuman,
  } = useGameStore()

  useEffect(() => {
    if (!gameId) {
      setConnected(false)
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const query = seat != null ? `?seat=${seat}` : ''
    const ws = new WebSocket(`${protocol}//${host}/ws/games/${gameId}${query}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      // Pull any in-flight awaiting_human state in case we connected after the event was emitted
      if (seat != null) {
        fetch(`/api/games/${gameId}/human_pending`)
          .then((r) => r.json())
          .then((data: { pending?: Array<{ actor_id: number; tool_name: string; phase: string }>; seat?: number | null }) => {
            if (!data?.pending || data.pending.length === 0) return
            const own = data.pending.find((p) => p.actor_id === seat)
            if (!own) return
            setAwaitingHuman({
              actor_id: own.actor_id,
              tool_name: own.tool_name,
              phase: own.phase,
              role: '',
              round: 0,
              timeout_seconds: 60,
              local_args: {},
            })
          })
          .catch(() => undefined)
      }
    }
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

        if (ev.event_type === 'phase_started' && ev.data?.phase) {
          setPhase(ev.data.phase)
          if (ev.data.round) setRound(ev.data.round)
        }
        if (ev.event_type === 'game_ended') {
          setStatus('completed')
          setWinner(ev.data?.winner || null)
        }
        if (ev.event_type === 'awaiting_human') {
          setAwaitingHuman({
            actor_id: Number(ev.data?.actor_id),
            tool_name: String(ev.data?.tool_name ?? ''),
            phase: String(ev.data?.phase ?? ''),
            role: String(ev.data?.role ?? ''),
            round: Number(ev.data?.round ?? 0),
            timeout_seconds: Number(ev.data?.timeout_seconds ?? 60),
            local_args: ev.data?.local_args || {},
          })
        }
        if (ev.event_type === 'human_submitted') {
          clearAwaitingHuman()
        }
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [gameId, seat])
}
