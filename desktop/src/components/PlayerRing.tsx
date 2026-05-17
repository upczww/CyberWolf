import { Player } from '../stores/game'

const ROLE_EMOJI: Record<string, string> = {
  wolf: '🐺',
  seer: '🔮',
  witch: '🧪',
  hunter: '🏹',
  idiot: '🎭',
  guard: '🛡',
  villager: '👤',
}

const ROLE_COLOR: Record<string, string> = {
  wolf: 'border-red-500 text-red-400',
  seer: 'border-purple-500 text-purple-400',
  witch: 'border-cyan-500 text-cyan-400',
  hunter: 'border-orange-500 text-orange-400',
  idiot: 'border-yellow-500 text-yellow-400',
  guard: 'border-green-500 text-green-400',
  villager: 'border-gray-500 text-gray-400',
}

interface Props {
  players: Player[]
  currentPhase: string | null
}

export default function PlayerRing({ players, currentPhase }: Props) {
  const sorted = [...players].sort((a, b) => a.seat_index - b.seat_index)

  // Which role is "acting" based on phase
  const actingRole = (() => {
    if (!currentPhase) return null
    const map: Record<string, string> = {
      night_wolf: 'wolf',
      night_seer: 'seer',
      night_witch: 'witch',
      night_guard: 'guard',
    }
    return map[currentPhase] || null
  })()

  return (
    <div className="grid grid-cols-6 gap-2 p-4">
      {sorted.map((p) => {
        const alive = !!p.survived
        const isActing = alive && actingRole && (
          p.role === actingRole || (actingRole === 'wolf' && p.faction === 'wolf')
        )
        const roleColor = ROLE_COLOR[p.role] || 'border-gray-600'

        return (
          <div
            key={p.player_id}
            className={`
              relative rounded-lg border-2 p-2 text-center transition-all
              ${alive ? roleColor : 'border-gray-700 opacity-40'}
              ${isActing ? 'ring-2 ring-yellow-400 animate-pulse' : ''}
            `}
          >
            <div className="text-2xl">{ROLE_EMOJI[p.role] || '❔'}</div>
            <div className={`text-sm font-bold ${alive ? '' : 'line-through'}`}>
              {p.seat_index}号
            </div>
            <div className="text-xs opacity-70">
              {p.role === 'wolf' ? '狼人' : p.role === 'seer' ? '预言家' : p.role === 'witch' ? '女巫' : p.role === 'hunter' ? '猎人' : p.role === 'idiot' ? '白痴' : '村民'}
            </div>
            {p.is_sheriff ? <span className="absolute top-0 right-0 text-yellow-400">♛</span> : null}
            {!alive && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-3xl opacity-50">💀</span>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
