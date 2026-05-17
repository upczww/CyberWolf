import { Player } from '../stores/game'
import PlayerSeat from './PlayerSeat'

interface Props {
  players: Player[]
  currentPhase: string | null
}

// Calculate positions for 12 seats in an ellipse
function getSeatPositions(count: number): { x: number; y: number }[] {
  const positions: { x: number; y: number }[] = []
  const cx = 50  // center x %
  const cy = 50  // center y %
  const rx = 38  // radius x %
  const ry = 40  // radius y %

  for (let i = 0; i < count; i++) {
    // Start from top, go clockwise
    const angle = (Math.PI * 2 * i) / count - Math.PI / 2
    positions.push({
      x: cx + rx * Math.cos(angle),
      y: cy + ry * Math.sin(angle),
    })
  }
  return positions
}

const PHASE_ROLE_MAP: Record<string, string> = {
  night_wolf: 'wolf',
  night_seer: 'seer',
  night_witch: 'witch',
  night_guard: 'guard',
  pending_skills: 'hunter',
}

export default function CircularTable({ players, currentPhase }: Props) {
  const sorted = [...players].sort((a, b) => a.seat_index - b.seat_index)
  const positions = getSeatPositions(sorted.length || 12)
  const actingRole = currentPhase ? PHASE_ROLE_MAP[currentPhase] || null : null

  return (
    <div className="relative w-full h-full">
      {/* Table center - current phase info */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
        <div className="w-32 h-32 rounded-full bg-black/30 backdrop-blur-sm border border-white/10 flex items-center justify-center">
          <div>
            <div className="text-3xl mb-1">
              {currentPhase?.includes('night') ? '🌙' : currentPhase?.includes('day') || currentPhase?.includes('sheriff') ? '☀' : '⚔'}
            </div>
            <div className="text-xs text-gray-400">
              {currentPhase === 'night_wolf' ? '狼人行动' :
               currentPhase === 'night_seer' ? '预言家查验' :
               currentPhase === 'night_witch' ? '女巫行动' :
               currentPhase === 'day_speech' ? '发言中' :
               currentPhase === 'day_vote' ? '投票中' :
               currentPhase === 'sheriff_election' ? '警长竞选' :
               currentPhase === 'game_over' ? '游戏结束' : ''}
            </div>
          </div>
        </div>
      </div>

      {/* Player seats around the table */}
      {sorted.map((player, i) => {
        const isActing = !!player.survived && actingRole !== null && (
          player.role === actingRole || (actingRole === 'wolf' && player.faction === 'wolf')
        )
        return (
          <PlayerSeat
            key={player.player_id}
            player={player}
            isActing={isActing}
            position={positions[i] || { x: 50, y: 50 }}
          />
        )
      })}
    </div>
  )
}
