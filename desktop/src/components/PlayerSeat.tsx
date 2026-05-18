import { Player } from '../stores/game'

const ROLE_CONFIG: Record<string, { emoji: string; label: string; color: string; border: string }> = {
  wolf: { emoji: '🐺', label: '狼人', color: 'text-red-400', border: 'border-red-500/50' },
  seer: { emoji: '🔮', label: '预言家', color: 'text-purple-400', border: 'border-purple-500/50' },
  witch: { emoji: '🧪', label: '女巫', color: 'text-cyan-400', border: 'border-cyan-500/50' },
  hunter: { emoji: '🏹', label: '猎人', color: 'text-orange-400', border: 'border-orange-500/50' },
  idiot: { emoji: '🎭', label: '白痴', color: 'text-yellow-400', border: 'border-yellow-500/50' },
  guard: { emoji: '🛡', label: '守卫', color: 'text-green-400', border: 'border-green-500/50' },
  villager: { emoji: '👤', label: '村民', color: 'text-gray-300', border: 'border-gray-500/50' },
}

const DEATH_CAUSE: Record<string, string> = {
  wolf: '🔪', poison: '☠', hunter_shot: '🏹', exile: '🗳', self_destruct: '💥',
}

interface Props {
  player: Player
  isActing: boolean
}

export default function PlayerSeat({ player, isActing }: Props) {
  const alive = !!player.survived
  const config = ROLE_CONFIG[player.role] || ROLE_CONFIG.villager

  return (
    <div
      className={`
        flex items-center gap-3 px-3 py-2 rounded-xl border backdrop-blur-sm transition-all duration-300
        ${alive ? config.border : 'border-gray-700/30'}
        ${alive ? 'bg-white/5' : 'bg-black/20 opacity-50'}
        ${isActing ? 'border-yellow-400 shadow-[0_0_15px_rgba(250,204,21,0.3)] scale-[1.03] bg-yellow-900/10' : ''}
        ${player.is_sheriff ? 'ring-1 ring-yellow-500/40' : ''}
      `}
    >
      {/* Avatar */}
      <div className={`
        w-10 h-10 rounded-full flex items-center justify-center text-xl shrink-0
        ${alive ? 'bg-black/30' : 'bg-black/50'}
        ${isActing ? 'animate-pulse' : ''}
        ${!alive ? 'grayscale' : ''}
      `}>
        {alive ? config.emoji : '💀'}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-sm font-bold ${alive ? 'text-white' : 'text-gray-500 line-through'}`}>
            {player.seat_index}号
          </span>
          {player.is_sheriff && <span className="text-yellow-400 text-xs">♛</span>}
          {!alive && player.death_cause && (
            <span className="text-xs">{DEATH_CAUSE[player.death_cause] || ''}</span>
          )}
        </div>
        <div className={`text-xs ${config.color} ${!alive ? 'opacity-50' : ''}`}>
          {config.label}
        </div>
      </div>

      {/* Acting indicator */}
      {isActing && (
        <div className="w-2 h-2 rounded-full bg-yellow-400 animate-ping shrink-0" />
      )}
    </div>
  )
}
