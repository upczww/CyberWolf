import { Player } from '../stores/game'
import PlayerSeat from './PlayerSeat'

const PHASE_ROLE_MAP: Record<string, string> = {
  night_wolf: 'wolf',
  night_seer: 'seer',
  night_witch: 'witch',
  night_guard: 'guard',
  pending_skills: 'hunter',
}

interface Props {
  player: Player
  currentPhase: string | null
}

export default function CircularTable({ player, currentPhase }: Props) {
  const actingRole = currentPhase ? PHASE_ROLE_MAP[currentPhase] || null : null
  const isActing = !!player.survived && actingRole !== null && (
    player.role === actingRole || (actingRole === 'wolf' && player.faction === 'wolf')
  )

  return <PlayerSeat player={player} isActing={isActing} />
}
