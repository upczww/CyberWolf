import { useEffect, useRef } from 'react'

export interface RoomSeatLite {
  seat_index: number
  user_id: string | null
  nickname: string | null
  joined_at: string | null
}

export interface RoomLite {
  id: string
  config_id: string
  host_user_id: string
  invite_token: string
  status: 'lobby' | 'started' | 'closed'
  game_id: string | null
  use_llm: boolean
  created_at: string
  started_at: string | null
  closed_at: string | null
  seats: RoomSeatLite[]
}

interface Callbacks {
  onState: (room: RoomLite) => void
  onStarted: (gameId: string, seatOwners: Record<string, string>, seatToken: string | null) => void
  onClosed: (reason?: string) => void
}

/**
 * Subscribe to a lobby room's WS feed. Receives:
 *  - initial `room_state` snapshot on connect
 *  - `room_state` updates whenever any seat changes
 *  - `room_started { game_id, seat_owners }` when host hits start
 *  - `room_closed { reason }` when host leaves / room dissolves
 *
 * Cleanup closes the socket on unmount or roomId change.
 */
export function useRoomWS(
  roomId: string | null,
  userId: string | null,
  callbacks: Callbacks,
) {
  const wsRef = useRef<WebSocket | null>(null)
  const cbRef = useRef(callbacks)
  cbRef.current = callbacks

  useEffect(() => {
    if (!roomId) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const q = userId ? `?user_id=${encodeURIComponent(userId)}` : ''
    const ws = new WebSocket(`${protocol}//${host}/ws/rooms/${roomId}${q}`)
    wsRef.current = ws

    ws.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data)
        if (payload.type === 'room_state' && payload.room) {
          cbRef.current.onState(payload.room as RoomLite)
        } else if (payload.type === 'room_started' && payload.game_id) {
          cbRef.current.onStarted(
            payload.game_id,
            payload.your_seat != null ? { [payload.your_seat]: userId || '' } : (payload.seat_owners || {}),
            payload.seat_token || null,
          )
        } else if (payload.type === 'room_closed') {
          cbRef.current.onClosed(payload.reason)
        }
      } catch {
        // ignore malformed
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [roomId, userId])
}
