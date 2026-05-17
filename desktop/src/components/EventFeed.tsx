import { useEffect, useRef } from 'react'
import { GameEvent } from '../stores/game'

const SCOPE_COLORS: Record<string, string> = {
  public: 'text-cyan-400',
  wolf_team: 'text-red-400',
  role_private: 'text-yellow-400',
  god: 'text-purple-400',
  system: 'text-green-400',
}

function formatEvent(ev: GameEvent): { text: string; highlight?: boolean } {
  const data = ev.data || {}
  const etype = ev.event_type

  if (etype === 'phase_started') {
    const phaseNames: Record<string, string> = {
      night_start: '🌙 夜晚开始',
      night_wolf: '🐺 狼人行动',
      night_seer: '🔮 预言家查验',
      night_witch: '🧪 女巫行动',
      night_resolve: '夜晚结算',
      day_announce: '☀ 天亮公布',
      sheriff_election: '👑 警长竞选',
      day_speech: '💬 白天发言',
      day_vote: '🗳 投票',
      pending_skills: '⚡ 技能结算',
      check_win: '🏁 胜负检查',
    }
    return { text: phaseNames[data.phase] || data.phase || '', highlight: true }
  }
  if (etype === 'wolf_target_selected') return { text: `🐺 狼队选择刀 ${data.target_id}号` }
  if (etype === 'seer_checked') {
    const r = data.result === 'wolf' ? '🔴狼人' : '🟢好人'
    return { text: `🔮 预言家查验 ${data.target_id}号：${r}` }
  }
  if (etype === 'witch_used_antidote') return { text: `💊 女巫救了 ${data.target_id}号` }
  if (etype === 'witch_used_poison') return { text: `☠ 女巫毒了 ${data.target_id}号` }
  if (etype === 'player_died') {
    const cause: Record<string, string> = { wolf: '被狼杀', poison: '被毒死', hunter_shot: '被枪杀', exile: '被放逐', self_destruct: '自爆' }
    return { text: `💀 ${data.player_id}号 ${cause[data.cause] || '死亡'}` }
  }
  if (etype === 'public_speech_made') return { text: `💬 ${data.player_id}号: ${(data.speech || '').slice(0, 60)}` }
  if (etype === 'sheriff_campaign') return { text: `👑 ${data.player_id}号竞选: ${(data.speech || '').slice(0, 60)}` }
  if (etype === 'death_speech') return { text: `🪦 ${data.player_id}号遗言: ${(data.speech || '').slice(0, 60)}` }
  if (etype === 'vote_cast') return { text: `  🗳 ${data.voter_id}号 → ${data.target_id}号` }
  if (etype === 'vote_resolved') return { text: `📊 投票结果：${data.chosen ? `${data.chosen}号出局` : '无人出局'}`, highlight: true }
  if (etype === 'sheriff_elected') return { text: `👑 ${data.player_id ? `${data.player_id}号当选警长` : '无人当选'}`, highlight: true }
  if (etype === 'sheriff_transferred') return { text: `👑 警徽转给 ${data.target_id || '撕毁'}号` }
  if (etype === 'game_ended') {
    const w = data.winner === 'good' ? '好人阵营' : '狼人阵营'
    return { text: `🏆 ${w} 获胜！`, highlight: true }
  }
  if (etype === 'sheriff_declare') return { text: `✋ ${data.player_id}号参选警长` }
  if (etype === 'wolf_self_destruct') return { text: `💥 ${data.player_id}号狼人自爆！`, highlight: true }
  if (ev.content === 'event.hunter_shot') return { text: `🏹 ${data.actor_id}号猎人开枪带走 ${data.target_id}号！`, highlight: true }
  if (ev.content === 'event.idiot_revealed') return { text: `🎭 ${data.actor_id || data.player_id}号白痴翻牌` }
  if (etype === 'phase_ended') return { text: '' }
  if (etype === 'speaking_started') return { text: '' }

  return { text: ev.content || etype }
}

interface Props {
  events: GameEvent[]
}

export default function EventFeed({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-sm">
      {events.map((ev, i) => {
        const { text, highlight } = formatEvent(ev)
        if (!text) return null
        const scopeColor = SCOPE_COLORS[ev.scope] || 'text-gray-400'
        return (
          <div
            key={i}
            className={`${scopeColor} ${highlight ? 'font-bold text-base' : ''}`}
          >
            {highlight && <hr className="border-gray-700 my-1" />}
            {text}
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
