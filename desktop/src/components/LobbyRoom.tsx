import { useEffect, useMemo, useRef, useState } from 'react'
import { apiPost } from '../hooks/useApi'
import { useRoomWS, type RoomLite, type RoomSeatLite } from '../hooks/useRoomWS'
import { buildInviteUrl, defaultNicknameFor } from '../lib/identity'
import ConfirmDialog from './ConfirmDialog'

interface Props {
  initialRoom: RoomLite
  userId: string
  // Called with the spawned game_id + the human seat assigned to THIS user
  // once the host hits start. The seat may be null if the user wasn't
  // seated in the room (shouldn't normally happen).
  onStarted: (gameId: string, mySeat: number | null, mySeatToken: string | null) => void
  onLeave: () => void
  onClosed: (reason?: string) => void
}

/**
 * Pre-game lobby for multi-human matches.
 *
 * 12-seat grid: each seat is either a human (nickname + kick button if
 * you're the host) or an "AI" placeholder. Host has an invite-link
 * button + start button; non-hosts just see the roster and wait. The
 * room WS keeps everyone in sync.
 */
export default function LobbyRoom({
  initialRoom, userId, onStarted, onLeave, onClosed,
}: Props) {
  const [room, setRoom] = useState<RoomLite>(initialRoom)
  const [busy, setBusy] = useState<'start' | 'leave' | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [leaveAsk, setLeaveAsk] = useState(false)
  const [kickAsk, setKickAsk] = useState<number | null>(null)
  const startedRef = useRef(false)

  const finishStarted = (gameId: string, mySeat: number | null, mySeatToken: string | null) => {
    if (startedRef.current) return
    startedRef.current = true
    onStarted(gameId, mySeat, mySeatToken)
  }

  useRoomWS(room.id, userId, {
    onState: (next) => setRoom(next),
    onStarted: (gameId, seatOwners, seatToken) => {
      const mySeat = findMySeat(seatOwners, userId)
      finishStarted(gameId, mySeat, seatToken)
    },
    onClosed: (reason) => onClosed(reason),
  })

  const isHost = room.host_user_id === userId
  const mySeat = useMemo(
    () => room.seats.find((s) => s.user_id === userId) || null,
    [room.seats, userId],
  )
  const inviteUrl = useMemo(() => buildInviteUrl(room.invite_token), [room.invite_token])
  const humanCount = room.seats.filter((s) => s.user_id).length

  // Auto-clear copied-confirmation after a beat.
  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(id)
  }, [copied])

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
    } catch {
      // Clipboard API can fail in non-secure contexts — fall back to
      // a temporary input + execCommand.
      try {
        const el = document.createElement('input')
        el.value = inviteUrl
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
        setCopied(true)
      } catch {
        setError('复制失败，请手动选中链接复制')
      }
    }
  }

  const handleStart = async () => {
    if (!isHost || busy) return
    setBusy('start')
    setError(null)
    try {
      const res = await apiPost<{ game_id?: string; error?: string; your_seat?: number | null; seat_token?: string | null }>(
        `/api/rooms/${room.id}/start`,
        { host_user_id: userId },
      )
      if (res.error || !res.game_id) {
        setError(res.error || '启动失败')
        setBusy(null)
        return
      }
      finishStarted(res.game_id, res.your_seat ?? null, res.seat_token ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '网络错误')
      setBusy(null)
    }
  }

  const handleLeave = () => {
    if (busy) return
    setLeaveAsk(true)
  }

  const confirmLeave = async () => {
    setLeaveAsk(false)
    setBusy('leave')
    try {
      await apiPost(`/api/rooms/${room.id}/leave`, { user_id: userId })
    } catch {
      // network failure — still navigate away
    }
    onLeave()
  }

  const handleKick = (seatIndex: number) => {
    if (!isHost) return
    setKickAsk(seatIndex)
  }

  const confirmKick = async () => {
    const seatIndex = kickAsk
    setKickAsk(null)
    if (seatIndex == null) return
    try {
      await apiPost(`/api/rooms/${room.id}/kick`, { host_user_id: userId, seat_index: seatIndex })
    } catch (err) {
      setError(err instanceof Error ? err.message : '踢出失败')
    }
  }

  return (
    <div className="lobby-page">
      <header className="lobby-top">
        <div className="lobby-title">
          <h1>组队对战</h1>
          <span>房间 #{room.id.slice(0, 6).toUpperCase()} · {humanCount}/12 人 · {room.use_llm ? 'LLM 模式' : '本地模式'}</span>
        </div>
        <div className="lobby-actions">
          {isHost && (
            <button className="lobby-btn ghost" onClick={copyInvite} title={inviteUrl}>
              {copied ? '✓ 已复制' : '复制邀请链接'}
            </button>
          )}
          {isHost && (
            <button
              className="lobby-btn primary"
              onClick={handleStart}
              disabled={busy === 'start'}
            >
              {busy === 'start' ? '启动中…' : `开始游戏 (${humanCount} 人 + ${12 - humanCount} AI)`}
            </button>
          )}
          <button className="lobby-btn danger" onClick={handleLeave} disabled={busy === 'leave'}>
            {isHost ? '解散房间' : '退出房间'}
          </button>
        </div>
      </header>

      {error && <div className="lobby-error">{error}</div>}

      <section className="lobby-seats">
        {room.seats.map((seat) => (
          <LobbySeat
            key={seat.seat_index}
            seat={seat}
            isMe={!!(mySeat && mySeat.seat_index === seat.seat_index)}
            isHostSeat={seat.seat_index === 1}
            canKick={isHost && seat.seat_index !== 1 && !!seat.user_id}
            onKick={() => handleKick(seat.seat_index)}
          />
        ))}
      </section>

      <footer className="lobby-hint">
        {isHost
          ? '👑 你是房主 — 复制邀请链接分享给好友，他们点开即可入座。AI 座位会在开始时自动补齐。'
          : '⏳ 等待房主开始游戏…'}
      </footer>

      {leaveAsk && (
        <ConfirmDialog
          title={isHost ? '解散房间' : '退出房间'}
          message={isHost
            ? '退出会解散整个房间，所有已加入的玩家会被踢出。确认退出？'
            : '确认退出当前房间？'}
          confirmLabel={isHost ? '解散房间' : '退出'}
          cancelLabel="留下"
          tone="danger"
          onConfirm={confirmLeave}
          onCancel={() => setLeaveAsk(false)}
        />
      )}
      {kickAsk != null && (
        <ConfirmDialog
          title="踢出玩家"
          message={`确认踢出 ${kickAsk} 号玩家？该座位会变回 AI。`}
          confirmLabel="踢出"
          cancelLabel="取消"
          tone="danger"
          onConfirm={confirmKick}
          onCancel={() => setKickAsk(null)}
        />
      )}
    </div>
  )
}

interface LobbySeatProps {
  seat: RoomSeatLite
  isMe: boolean
  isHostSeat: boolean
  canKick: boolean
  onKick: () => void
}

function LobbySeat({ seat, isMe, isHostSeat, canKick, onKick }: LobbySeatProps) {
  const occupied = !!seat.user_id
  const nickname = seat.nickname || (seat.user_id ? defaultNicknameFor(seat.user_id) : 'AI')
  const tone = isHostSeat ? 'host' : occupied ? 'human' : 'ai'
  return (
    <article className={`lobby-seat tone-${tone} ${isMe ? 'is-me' : ''}`}>
      <div className="lobby-seat-num">{seat.seat_index}</div>
      <div className="lobby-seat-body">
        <b>{nickname}</b>
        <span>
          {isHostSeat ? '👑 房主' : occupied ? '已就座' : 'AI 玩家'}
          {isMe && ' · 你'}
        </span>
      </div>
      {canKick && (
        <button className="lobby-seat-kick" onClick={onKick} title="踢出该玩家">
          ✕
        </button>
      )}
    </article>
  )
}

function findMySeat(seatOwners: Record<string, string>, userId: string): number | null {
  for (const [seatStr, owner] of Object.entries(seatOwners)) {
    if (owner === userId) return Number(seatStr)
  }
  return null
}
