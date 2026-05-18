import { Player } from '../stores/game'
import PlayerSeat from './PlayerSeat'

interface Props {
  players: Player[]
  currentPhase: string | null
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
  const actingRole = currentPhase ? PHASE_ROLE_MAP[currentPhase] || null : null

  // Split: seats 1-6 left, seats 7-12 right
  const leftPlayers = sorted.filter(p => p.seat_index <= 6)
  const rightPlayers = sorted.filter(p => p.seat_index > 6)

  return (
    <div className="flex h-full">
      {/* Left column — seats 1-6 */}
      <div className="flex-1 flex flex-col justify-evenly py-4 px-6">
        {leftPlayers.map((player) => {
          const isActing = !!player.survived && actingRole !== null && (
            player.role === actingRole || (actingRole === 'wolf' && player.faction === 'wolf')
          )
          return (
            <PlayerSeat
              key={player.player_id}
              player={player}
              isActing={isActing}
            />
          )
        })}
      </div>

      {/* Center — phase indicator */}
      <div className="w-32 flex items-center justify-center">
        <div className="w-24 h-24 rounded-full bg-black/30 backdrop-blur-sm border border-white/10 flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl">
              {currentPhase?.includes('night') ? '🌙' : currentPhase?.includes('day') || currentPhase?.includes('sheriff') ? '☀' : '⚔'}
            </div>
            <div className="text-[10px] text-gray-400 mt-1">
              {currentPhase === 'night_wolf' ? '狼人行动' :
               currentPhase === 'night_seer' ? '预言查验' :
               currentPhase === 'night_witch' ? '女巫行动' :
               currentPhase === 'day_speech' ? '发言中' :
               currentPhase === 'day_vote' ? '投票中' :
               currentPhase === 'sheriff_election' ? '警长竞选' :
               currentPhase === 'game_over' ? '游戏结束' : ''}
            </div>
          </div>
        </div>
      </div>

      {/* Right column — seats 7-12 */}
      <div className="flex-1 flex flex-col justify-evenly py-4 px-6">
        {rightPlayers.map((player) => {
          const isActing = !!player.survived && actingRole !== null && (
            player.role === actingRole || (actingRole === 'wolf' && player.faction === 'wolf')
          )
          return (
            <PlayerSeat
              key={player.player_id}
              player={player}
              isActing={isActing}
            />
          )
        })}
      </div>
    </div>
  )
}
