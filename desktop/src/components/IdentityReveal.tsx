import { useEffect, useState } from 'react'
import type { Player } from '../stores/game'

interface Props {
  gameId: string
  player: Player
  onClose: () => void
}

const A = '/assets/ui'

interface RoleMeta {
  label: string
  camp: string
  campTone: 'good' | 'wolf' | 'neutral'
  description: string
  ability: string
  art: string
  cardBase: string
}

function metaFor(role: string, faction: string): RoleMeta {
  const tone: 'good' | 'wolf' | 'neutral' = faction === 'wolf' ? 'wolf' : 'good'
  const cardBase = `${A}/role_intro/role_intro_card_base_${tone}.png`
  const map: Record<string, RoleMeta> = {
    villager: {
      label: '平民', camp: '好人阵营', campTone: 'good',
      description: '你是普通村民，没有特殊技能。',
      ability: '依靠白天发言与投票，跟随预言家、女巫、猎人等神职找出狼人。',
      art: `${A}/role_intro/role_intro_villager.png`, cardBase,
    },
    wolf: {
      label: '狼人', camp: '狼人阵营', campTone: 'wolf',
      description: '你是狼人，每晚和狼队商议刀人。',
      ability: '夜晚与狼队投票决定击杀目标。白天可悍跳神职、误导好人、或自爆终结发言。',
      art: `${A}/role_intro/role_intro_werewolf.png`, cardBase,
    },
    werewolf: {
      label: '狼人', camp: '狼人阵营', campTone: 'wolf',
      description: '你是狼人，每晚和狼队商议刀人。',
      ability: '夜晚与狼队投票决定击杀目标。白天可悍跳神职、误导好人、或自爆终结发言。',
      art: `${A}/role_intro/role_intro_werewolf.png`, cardBase,
    },
    seer: {
      label: '预言家', camp: '神职', campTone: 'good',
      description: '你是预言家，每晚可以查验一名玩家的真实阵营。',
      ability: '夜晚 → 查验某玩家是「狼人」还是「好人」。白天主动跳身份并公布验人结果是基本打法。',
      art: `${A}/role_intro/role_intro_seer.png`, cardBase,
    },
    witch: {
      label: '女巫', camp: '神职', campTone: 'good',
      description: '你是女巫，拥有一瓶解药和一瓶毒药。',
      ability: '夜晚可以救活今晚被刀的玩家（每局仅一次），或毒杀任意一人（每局仅一次）。同一晚不能同时使用解药+毒药。',
      art: `${A}/role_intro/role_intro_witch.png`, cardBase,
    },
    hunter: {
      label: '猎人', camp: '神职', campTone: 'good',
      description: '你是猎人，被刀或被投票出局时可以开枪带走一人。',
      ability: '被女巫毒杀时无法开枪。开枪目标会立即出局并触发其自身的死亡技能。',
      art: `${A}/role_intro/role_intro_hunter.png`, cardBase,
    },
    idiot: {
      label: '白痴', camp: '神职', campTone: 'good',
      description: '你是白痴，被投票放逐时翻牌存活、但失去投票权。',
      ability: '被狼刀依然死亡。翻牌后可以继续发言、辅助好人推理。',
      art: `${A}/role_intro/role_intro_idiot.png`, cardBase,
    },
    guard: {
      label: '守卫', camp: '神职', campTone: 'good',
      description: '你是守卫，每晚可以守护一名玩家。',
      ability: '被守护的玩家当晚免疫狼刀。不能连续两晚守护同一人。',
      art: `${A}/role_intro/role_intro_guard.png`, cardBase,
    },
  }
  return map[role] || map.villager
}

const STORAGE_KEY_PREFIX = 'lycan-identity-revealed:'

export default function IdentityReveal({ gameId, player, onClose }: Props) {
  const meta = metaFor(player.role, player.faction)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    // Lock body scroll while modal is open
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const handleClose = () => {
    setClosing(true)
    try {
      sessionStorage.setItem(STORAGE_KEY_PREFIX + gameId, '1')
    } catch {
      // ignore quota errors
    }
    window.setTimeout(onClose, 240)
  }

  return (
    <div className={`identity-overlay ${closing ? 'is-closing' : ''}`} role="dialog" aria-modal="true">
      <div className={`identity-card tone-${meta.campTone}`} style={{ backgroundImage: `url(${meta.cardBase})` }}>
        <div className="identity-seat">{player.seat_index}</div>
        <h2 className="identity-title">{meta.label}</h2>
        <div className={`identity-camp camp-${meta.campTone}`}>{meta.camp}</div>
        <img className="identity-art" src={meta.art} alt={meta.label} />
        <p className="identity-description">{meta.description}</p>
        <div className="identity-ability">
          <span className="identity-ability-label">技能</span>
          <p>{meta.ability}</p>
        </div>
        <button className="identity-confirm" onClick={handleClose}>
          进入游戏
          <span>›</span>
        </button>
        <div className="identity-hint">⚠ 仅你自己可见这张身份牌</div>
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
