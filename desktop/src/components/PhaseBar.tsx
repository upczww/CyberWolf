interface Props {
  phase: string | null
  round: number
  winner: string | null
  players: { survived: number; faction: string; role: string }[]
}

const PHASE_NAMES: Record<string, string> = {
  setup_game: '初始化',
  night_start: '夜晚开始',
  night_wolf: '狼人行动',
  night_seer: '预言家查验',
  night_witch: '女巫行动',
  night_resolve: '夜晚结算',
  day_announce: '天亮公布',
  sheriff_election: '警长竞选',
  day_speech: '白天发言',
  day_vote: '投票',
  day_resolve: '放逐结算',
  pending_skills: '技能结算',
  check_win: '胜负检查',
  game_over: '游戏结束',
}

const GOD_ROLES = new Set(['seer', 'witch', 'hunter', 'idiot', 'guard'])

export default function PhaseBar({ phase, round, winner, players }: Props) {
  const godsAlive = players.filter(p => p.survived && GOD_ROLES.has(p.role)).length
  const villagersAlive = players.filter(p => p.survived && p.role === 'villager').length
  const wolvesAlive = players.filter(p => p.survived && p.faction === 'wolf').length

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
      <div className="flex items-center gap-4">
        <span className="text-lg font-bold">R{round}</span>
        <span className="text-cyan-400 font-medium">
          {phase ? PHASE_NAMES[phase] || phase : '-'}
        </span>
      </div>

      <div className="flex items-center gap-3 text-sm">
        <span className="text-purple-400 font-bold">神{godsAlive}</span>
        <span className="text-gray-300 font-bold">民{villagersAlive}</span>
        <span className="text-red-400 font-bold">狼{wolvesAlive}</span>
      </div>

      {winner && (
        <div className="text-green-400 font-bold animate-pulse">
          🏆 {winner === 'good' ? '好人阵营' : '狼人阵营'}获胜
        </div>
      )}
    </div>
  )
}
