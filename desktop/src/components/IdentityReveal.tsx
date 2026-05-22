import { useEffect, useRef, useState } from 'react'
import { portraitForPlayer } from '../lib/portraits'
import { apiPost } from '../hooks/useApi'
import { useGameStore, type Player } from '../stores/game'

interface Props {
  gameId: string
  player: Player
  onClose: () => void
}

const CONFIRM_TIMEOUT_S = 30

interface RoleMeta {
  label: string
  camp: string
  campTone: 'good' | 'wolf' | 'neutral'
  description: string
  ability: string
}

function metaFor(role: string, faction: string): RoleMeta {
  const tone: 'good' | 'wolf' | 'neutral' = faction === 'wolf' ? 'wolf' : 'good'
  const map: Record<string, RoleMeta> = {
    villager: {
      label: '平民', camp: '好人阵营', campTone: 'good',
      description: '你是普通村民，没有特殊技能。',
      ability: '依靠白天发言与投票，跟随预言家、女巫、猎人等神职找出狼人。',
    },
    wolf: {
      label: '狼人', camp: '狼人阵营', campTone: 'wolf',
      description: '你是狼人，每晚和狼队商议刀人。',
      ability: '夜晚与狼队投票决定击杀目标。白天可悍跳神职、误导好人、或自爆终结发言。',
    },
    werewolf: {
      label: '狼人', camp: '狼人阵营', campTone: 'wolf',
      description: '你是狼人，每晚和狼队商议刀人。',
      ability: '夜晚与狼队投票决定击杀目标。白天可悍跳神职、误导好人、或自爆终结发言。',
    },
    seer: {
      label: '预言家', camp: '神职', campTone: 'good',
      description: '你是预言家，每晚可以查验一名玩家的真实阵营。',
      ability: '夜晚 → 查验某玩家是「狼人」还是「好人」。白天主动跳身份并公布验人结果是基本打法。',
    },
    witch: {
      label: '女巫', camp: '神职', campTone: 'good',
      description: '你是女巫，拥有一瓶解药和一瓶毒药。',
      ability: '夜晚可以救活今晚被刀的玩家（每局仅一次），或毒杀任意一人（每局仅一次）。同一晚不能同时使用解药+毒药。',
    },
    hunter: {
      label: '猎人', camp: '神职', campTone: 'good',
      description: '你是猎人，被刀或被投票出局时可以开枪带走一人。',
      ability: '被女巫毒杀时无法开枪。开枪目标会立即出局并触发其自身的死亡技能。',
    },
    idiot: {
      label: '白痴', camp: '神职', campTone: 'good',
      description: '你是白痴，被投票放逐时翻牌存活、但失去投票权。',
      ability: '被狼刀依然死亡。翻牌后可以继续发言、辅助好人推理。',
    },
    guard: {
      label: '守卫', camp: '神职', campTone: 'good',
      description: '你是守卫，每晚可以守护一名玩家。',
      ability: '被守护的玩家当晚免疫狼刀。不能连续两晚守护同一人。',
    },
  }
  return map[role] || map.villager
}

const STORAGE_KEY_PREFIX = 'lycan-identity-revealed:'

export default function IdentityReveal({ gameId, player, onClose }: Props) {
  const humanSeatToken = useGameStore((s) => s.humanSeatToken)
  const meta = metaFor(player.role, player.faction)
  const portrait = portraitForPlayer(player, gameId)
  const [closing, setClosing] = useState(false)
  const [remaining, setRemaining] = useState(CONFIRM_TIMEOUT_S)
  const submittedRef = useRef(false)

  useEffect(() => {
    // Lock body scroll while modal is open
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  // Local countdown — purely visual. Backend has its own 30s awaiter
  // (handle_setup_game -> _await_human_action('confirm_identity', 30s)).
  // We submit when the player clicks; on local timeout we still submit so
  // the network round-trip beats backend's fallback when possible.
  useEffect(() => {
    if (closing) return
    const id = window.setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          window.clearInterval(id)
          handleClose()
          return 0
        }
        return r - 1
      })
    }, 1000)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closing])

  const submitConfirmation = async () => {
    if (submittedRef.current) return
    submittedRef.current = true
    try {
      await apiPost(`/api/games/${gameId}/human_action`, {
        actor_id: player.seat_index,
        tool_name: 'confirm_identity',
        args: { confirmed: true },
        seat_token: humanSeatToken,
      })
    } catch {
      // If the backend awaiter has already timed out and resolved with its
      // local_args fallback, this 404s — that's fine, the game progressed.
    }
  }

  const handleClose = () => {
    if (closing) return
    setClosing(true)
    try {
      sessionStorage.setItem(STORAGE_KEY_PREFIX + gameId, '1')
    } catch {
      // ignore quota errors
    }
    // Backend gates the next phase on this submission — fire it before the
    // visual close animation finishes.
    submitConfirmation()
    window.setTimeout(onClose, 240)
  }

  const progress = Math.max(0, remaining / CONFIRM_TIMEOUT_S)
  const urgent = remaining <= 10

  return (
    <div className={`identity-overlay ${closing ? 'is-closing' : ''}`} role="dialog" aria-modal="true">
      <div className={`identity-panel tone-${meta.campTone}`}>
        <header className="identity-head">
          <div className="identity-seat">{player.seat_index}</div>
          <div className="identity-head-text">
            <h2>{meta.label}</h2>
            <span className={`identity-camp camp-${meta.campTone}`}>{meta.camp}</span>
          </div>
          <div className={`identity-timer ${urgent ? 'urgent' : ''}`}>{remaining}s</div>
        </header>
        <img className="identity-art" src={portrait} alt={meta.label} />
        <p className="identity-description">{meta.description}</p>
        <div className="identity-ability">
          <span className="identity-ability-label">技能</span>
          <p>{meta.ability}</p>
        </div>
        <div className="identity-countdown">
          <span style={{ transform: `scaleX(${progress})` }} />
        </div>
        <button className="identity-confirm" onClick={handleClose}>
          进入游戏
          <span>›</span>
        </button>
        <div className="identity-hint">⚠ 仅你自己可见此身份牌 · 超时自动确认</div>
      </div>
    </div>
  )
}

export function hasSeenIdentityReveal(gameId: string): boolean {
  try {
    return sessionStorage.getItem(STORAGE_KEY_PREFIX + gameId) === '1'
  } catch {
    return false
  }
}
