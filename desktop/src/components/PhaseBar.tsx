interface Props {
  phase: string | null
  round: number
  winner: string | null
  players: { survived: number; faction: string; role: string }[]
}

const PHASE_NAMES: Record<string, string> = {
  setup_game: '初始化',
  night_start: '🌙 夜晚开始',
  night_wolf: '🐺 狼人行动',
  night_seer: '🔮 预言家查验',
  night_witch: '🧪 女巫行动',
  night_resolve: '夜晚结算',
  day_announce: '☀ 天亮公布',
  sheriff_election: '👑 警长竞选',
  day_speech: '💬 白天发言',
  day_vote: '🗳 投票',
  day_resolve: '放逐结算',
  pending_skills: '⚡ 技能结算',
  check_win: '胜负检查',
  game_over: '🏆 游戏结束',
}

const GOD_ROLES = new Set(['seer', 'witch', 'hunter', 'idiot', 'guard'])

export default function PhaseBar({ phase, round, winner, players }: Props) {
  const godsAlive = players.filter(p => p.survived && GOD_ROLES.has(p.role)).length
  const villagersAlive = players.filter(p => p.survived && p.role === 'villager').length
  const wolvesAlive = players.filter(p => p.survived && p.faction === 'wolf').length

  return (
    <div className="relative z-20 flex items-center justify-between px-6 py-3 bg-black/50 backdrop-blur-md border-b border-white/10">
      <div className="flex items-center gap-4">
        <span className="text-xl font-bold text-white/90">R{round}</span>
        <span className="text-cyan-300 font-medium text-lg">
          {phase ? PHASE_NAMES[phase] || phase : '等待开始'}
        </span>
      </div>

      <div className="flex items-center gap-4 text-sm font-bold">
        <span className="text-purple-400">神 {godsAlive}</span>
        <span className="text-gray-300">民 {villagersAlive}</span>
        <span className="text-red-400">狼 {wolvesAlive}</span>
      </div>

      {winner && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-2xl font-bold text-green-400 animate-pulse drop-shadow-[0_0_10px_rgba(74,222,128,0.5)]">
            🏆 {winner === 'good' ? '好人阵营' : '狼人阵营'}获胜！
          </div>
        </div>
      )}
    </div>
  )
}
