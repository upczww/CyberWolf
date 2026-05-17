import { Player } from '../stores/game'

const ROLE_CONFIG: Record<string, { emoji: string; label: string; color: string; bgColor: string }> = {
  wolf: { emoji: '🐺', label: '狼人', color: 'text-red-400', bgColor: 'from-red-900/60 to-red-950/60' },
  seer: { emoji: '🔮', label: '预言家', color: 'text-purple-400', bgColor: 'from-purple-900/60 to-purple-950/60' },
  witch: { emoji: '🧪', label: '女巫', color: 'text-cyan-400', bgColor: 'from-cyan-900/60 to-cyan-950/60' },
  hunter: { emoji: '🏹', label: '猎人', color: 'text-orange-400', bgColor: 'from-orange-900/60 to-orange-950/60' },
  idiot: { emoji: '🎭', label: '白痴', color: 'text-yellow-400', bgColor: 'from-yellow-900/60 to-yellow-950/60' },
  guard: { emoji: '🛡', label: '守卫', color: 'text-green-400', bgColor: 'from-green-900/60 to-green-950/60' },
  villager: { emoji: '👤', label: '村民', color: 'text-gray-300', bgColor: 'from-gray-800/60 to-gray-900/60' },
}

interface Props {
  player: Player
  isActing: boolean
  position: { x: number; y: number }
}

export default function PlayerSeat({ player, isActing, position }: Props) {
  const alive = !!player.survived
  const config = ROLE_CONFIG[player.role] || ROLE_CONFIG.villager

  return (
    <div
      className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-500"
      style={{ left: `${position.x}%`, top: `${position.y}%` }}
    >
      <div
        className={`
          relative w-20 h-24 rounded-xl border-2 backdrop-blur-sm
          bg-gradient-to-b ${config.bgColor}
          transition-all duration-300
          ${alive ? 'border-white/20' : 'border-gray-700/30 opacity-50 grayscale'}
          ${isActing ? 'border-yellow-400 shadow-[0_0_20px_rgba(250,204,21,0.4)] scale-110' : ''}
          ${player.is_sheriff ? 'ring-2 ring-yellow-500/50' : ''}
        `}
      >
        {/* Avatar circle */}
        <div className={`
          mx-auto mt-2 w-12 h-12 rounded-full flex items-center justify-center text-2xl
          ${alive ? 'bg-black/30' : 'bg-black/50'}
          ${isActing ? 'animate-pulse' : ''}
        `}>
          {alive ? config.emoji : '💀'}
        </div>

        {/* Player number */}
        <div className={`text-center text-xs font-bold mt-1 ${alive ? 'text-white' : 'text-gray-500 line-through'}`}>
          {player.seat_index}号
        </div>

        {/* Role name */}
        <div className={`text-center text-[10px] ${config.color} ${!alive ? 'opacity-50' : ''}`}>
          {config.label}
        </div>

        {/* Sheriff badge */}
        {player.is_sheriff ? (
          <div className="absolute -top-1 -right-1 text-lg animate-bounce">♛</div>
        ) : null}

        {/* Death cause indicator */}
        {!alive && player.death_cause && (
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 text-xs bg-black/70 px-1 rounded">
            {player.death_cause === 'wolf' ? '🔪' : player.death_cause === 'poison' ? '☠' : player.death_cause === 'exile' ? '🗳' : player.death_cause === 'hunter_shot' ? '🏹' : '💥'}
          </div>
        )}

        {/* Acting glow */}
        {isActing && (
          <div className="absolute inset-0 rounded-xl border-2 border-yellow-400 animate-ping opacity-30" />
        )}
      </div>
    </div>
  )
}
