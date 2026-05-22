import { useEffect, useRef } from 'react'
import { useGameStore } from '../stores/game'
import { normalizeGameEvent } from '../lib/gameFlow'

export function useGameWS(gameId: string | null, seat: number | null = null, seatToken: string | null = null) {
  const wsRef = useRef<WebSocket | null>(null)
  const {
    addEvent, setConnected,
    setAwaitingHuman, clearAwaitingHuman,
  } = useGameStore()

  useEffect(() => {
    if (!gameId) {
      setConnected(false)
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const params = new URLSearchParams()
    if (seat != null) params.set('seat', String(seat))
    if (seatToken) params.set('seat_token', seatToken)
    const query = params.toString() ? `?${params.toString()}` : ''
    const ws = new WebSocket(`${protocol}//${host}/ws/games/${gameId}${query}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      // Pull any in-flight awaiting_human state in case we connected after the event was emitted
      if (seat != null && seatToken) {
        const pendingParams = new URLSearchParams({ seat: String(seat), seat_token: seatToken })
        fetch(`/api/games/${gameId}/human_pending?${pendingParams.toString()}`)
          .then((r) => r.json())
          .then((data: {
            pending?: Array<{
              actor_id: number
              tool_name: string
              phase: string
              role?: string
              round?: number
              timeout_seconds?: number
              local_args?: Record<string, any>
            }>
            seat?: number | null
          }) => {
            if (!data?.pending || data.pending.length === 0) {
              clearAwaitingHuman()
              return
            }
            const own = data.pending.find((p) => p.actor_id === seat)
            if (!own) {
              clearAwaitingHuman()
              return
            }
            setAwaitingHuman({
              actor_id: own.actor_id,
              tool_name: own.tool_name,
              phase: own.phase,
              role: own.role || '',
              round: own.round || 0,
              timeout_seconds: own.timeout_seconds || 60,
              local_args: own.local_args || {},
            })
          })
          .catch(() => undefined)
      }
    }
    ws.onclose = () => setConnected(false)

    ws.onmessage = (msg) => {
      const payload = JSON.parse(msg.data)

      if (payload.type === 'history') {
        const ev = normalizeEvent(payload.event)
        addEvent(ev)
      } else if (payload.type === 'history_complete') {
        // History loading done
      } else if (payload.type === 'live') {
        const ev = normalizeEvent(payload.event)
        addEvent(ev)
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [gameId, seat, seatToken])
}

function normalizeEvent(raw: any) {
  return normalizeGameEvent(raw)
}
