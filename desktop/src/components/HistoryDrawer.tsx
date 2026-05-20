import { useMemo, useState } from 'react'
import type { GameEvent, Player } from '../stores/game'

type TabKey = 'speech' | 'vote' | 'settle'

interface Props {
  events: GameEvent[]
  players: Player[]
  humanSeat: number | null
  onClose: () => void
}

const ROLE_LABELS: Record<string, string> = {
  wolf: '狼人', seer: '预言家', witch: '女巫', hunter: '猎人',
  idiot: '白痴', guard: '守卫', villager: '村民',
}

export default function HistoryDrawer({ events, players, humanSeat, onClose }: Props) {
  const [tab, setTab] = useState<TabKey>('vote')

  const groupedVotes = useMemo(() => buildVoteGroups(events), [events])
  const speeches = useMemo(() => buildSpeechRows(events, players), [events, players])
  const settlements = useMemo(() => buildSettlementRows(events), [events])

  return (
    <>
      <div className="drawer-mask" onClick={onClose} />
      <aside className="history-drawer" role="dialog" aria-label="历史记录">
        <header>
          <h2>历史记录</h2>
          <button className="close" onClick={onClose} aria-label="关闭">✕</button>
        </header>
        <div className="history-tabs">
          <button className={tab === 'speech' ? 'active' : ''} onClick={() => setTab('speech')}>发言记录</button>
          <button className={tab === 'vote' ? 'active' : ''} onClick={() => setTab('vote')}>投票记录</button>
          <button className={tab === 'settle' ? 'active' : ''} onClick={() => setTab('settle')}>结算记录</button>
        </div>

        <div className="history-body">
          {tab === 'vote' && (
            groupedVotes.length === 0
              ? <div className="history-empty">尚无投票记录</div>
              : groupedVotes.map((g) => (
                  <section className="history-group" key={g.key}>
                    <div className="group-title">
                      第 {g.round} 天 · {g.kind === 'sheriff' ? '警长竞选' : '投票阶段'}
                      <em>{g.chosen != null ? `放逐 ${g.chosen}号` : g.kind === 'sheriff' ? '票选完成' : '平票'}</em>
                    </div>
                    <div className="history-vote-grid">
                      {Array.from({ length: 12 }, (_, i) => i + 1).map((seat) => {
                        const target = g.byVoter[seat]
                        const exiled = g.chosen === seat
                        const isSelf = humanSeat === seat
                        return (
                          <div
                            key={seat}
                            className={`history-vote-cell ${exiled ? 'is-exiled' : ''} ${isSelf ? 'is-self' : ''}`}
                            title={target != null ? `${seat}号 → ${target}号` : `${seat}号 弃票`}
                          >
                            <span className="seat">{seat}号</span>
                            <span className="arrow">{target != null ? `→ ${target}号` : '弃票'}</span>
                          </div>
                        )
                      })}
                    </div>
                  </section>
                ))
          )}

          {tab === 'speech' && (
            speeches.length === 0
              ? <div className="history-empty">尚无发言记录</div>
              : speeches.map((row, i) => (
                  <div className="history-speech-row" key={`sp-${i}`}>
                    <img src={row.avatar} alt="" />
                    <div>
                      <div className="hs-head">
                        <span>第{row.round}天 · {row.seat}号 {row.role ? ROLE_LABELS[row.role] || '' : ''}</span>
                        <span className="hs-time">{row.scope}</span>
                      </div>
                      <p>{row.text}</p>
                    </div>
                  </div>
                ))
          )}

          {tab === 'settle' && (
            settlements.length === 0
              ? <div className="history-empty">尚无结算记录</div>
              : settlements.map((row, i) => (
                  <div className={`history-event-row ${row.tone === 'bad' ? 'is-bad' : row.tone === 'good' ? 'is-good' : ''}`} key={`st-${i}`}>
                    <span className="e-ico">{row.glyph}</span>
                    <div>
                      <b>第 {row.round} 天</b> · {row.text}
                    </div>
                    <span className="e-time">{row.time}</span>
                  </div>
                ))
          )}
        </div>
      </aside>
    </>
  )
}

interface VoteGroup {
  key: string
  round: number
  kind: 'sheriff' | 'day'
  byVoter: Record<number, number | null>
  chosen: number | null
}

function buildVoteGroups(events: GameEvent[]): VoteGroup[] {
  const groups: VoteGroup[] = []
  let current: VoteGroup | null = null

  for (const ev of events) {
    if (ev.event_type === 'phase_started') {
      const phase = ev.data?.phase as string
      const round = typeof ev.round === 'number' ? ev.round : 1
      if (phase === 'sheriff_election') {
        current = { key: `sheriff-${round}`, round, kind: 'sheriff', byVoter: {}, chosen: null }
        groups.push(current)
      } else if (phase === 'day_vote') {
        current = { key: `day-${round}`, round, kind: 'day', byVoter: {}, chosen: null }
        groups.push(current)
      }
    }
    if (!current) continue
    if (ev.event_type === 'vote_cast') {
      const voter = Number(ev.data?.voter_id)
      const target = ev.data?.target_id
      if (Number.isFinite(voter)) {
        current.byVoter[voter] = target == null ? null : Number(target)
      }
    }
    if (ev.event_type === 'sheriff_elected') {
      const sheriff = Number(ev.data?.player_id ?? ev.data?.target_id)
      if (Number.isFinite(sheriff)) current.chosen = sheriff
    }
    if (ev.event_type === 'vote_resolved') {
      const chosen = ev.data?.chosen
      current.chosen = chosen == null ? null : Number(chosen)
    }
  }
  return groups
}

interface SpeechRow {
  round: number
  seat: number
  role: string | null
  scope: string
  text: string
  avatar: string
}

const SPEECH_TYPES = new Set([
  'public_speech_made', 'sheriff_campaign', 'sheriff_declare', 'death_speech',
])

function buildSpeechRows(events: GameEvent[], players: Player[]): SpeechRow[] {
  const out: SpeechRow[] = []
  for (const ev of events) {
    if (!SPEECH_TYPES.has(ev.event_type)) continue
    const seat = Number(ev.data?.player_id ?? ev.data?.actor_id)
    if (!Number.isFinite(seat)) continue
    const player = players.find((p) => p.seat_index === seat) || null
    const text = String(ev.data?.speech ?? ev.data?.message ?? ev.data?.text ?? ev.content ?? '')
    out.push({
      round: typeof ev.round === 'number' ? ev.round : 1,
      seat,
      role: player?.role || null,
      scope: ev.event_type === 'sheriff_campaign' ? '警上发言' : ev.event_type === 'death_speech' ? '遗言' : '白天发言',
      text,
      avatar: avatarForSeat(seat),
    })
  }
  return out
}

interface SettleRow {
  round: number
  text: string
  glyph: string
  tone?: 'bad' | 'good' | 'neutral'
  time: string
}

function buildSettlementRows(events: GameEvent[]): SettleRow[] {
  const out: SettleRow[] = []
  for (const ev of events) {
    const round = typeof ev.round === 'number' ? ev.round : 1
    const t = ev.created_at ? short(ev.created_at) : ''
    switch (ev.event_type) {
      case 'player_died': {
        const cause = ev.data?.cause
        const causeText = cause === 'wolf' ? '夜刀' : cause === 'poison' ? '毒杀'
          : cause === 'exile' ? '放逐' : cause === 'hunter' ? '猎人' : cause === 'self_destruct' ? '自爆' : '出局'
        out.push({ round, text: `${ev.data?.player_id ?? '?'} 号出局 · ${causeText}`, glyph: '☠', tone: 'bad', time: t })
        break
      }
      case 'wolf_target_selected':
        out.push({ round, text: `狼队夜刀 ${ev.data?.target_id ?? '?'} 号`, glyph: '🩸', tone: 'bad', time: t })
        break
      case 'witch_used_antidote':
        out.push({ round, text: `女巫救活 ${ev.data?.target_id ?? '?'} 号`, glyph: '🧪', tone: 'good', time: t })
        break
      case 'witch_used_poison':
        out.push({ round, text: `女巫毒杀 ${ev.data?.target_id ?? '?'} 号`, glyph: '☠', tone: 'bad', time: t })
        break
      case 'seer_checked':
        out.push({
          round,
          text: `预言家查验 ${ev.data?.target_id ?? '?'} 号 → ${ev.data?.result === 'wolf' ? '狼人' : '好人'}`,
          glyph: '👁', tone: ev.data?.result === 'wolf' ? 'bad' : 'good', time: t,
        })
        break
      case 'sheriff_elected':
        out.push({ round, text: `${ev.data?.player_id ?? '?'} 号当选警长`, glyph: '★', tone: 'good', time: t })
        break
      case 'hunter_shot':
        out.push({ round, text: `猎人开枪 → ${ev.data?.target_id ?? '?'} 号`, glyph: '🏹', tone: 'bad', time: t })
        break
      case 'wolf_self_destruct':
        out.push({ round, text: `${ev.data?.player_id ?? '?'} 号狼人自爆`, glyph: '💥', tone: 'bad', time: t })
        break
      case 'vote_resolved':
        out.push({
          round,
          text: ev.data?.chosen != null ? `投票结算 · 放逐 ${ev.data?.chosen} 号` : '投票结算 · 平票',
          glyph: '⚖', tone: 'neutral', time: t,
        })
        break
      case 'game_ended':
        out.push({ round, text: `游戏结束 · ${ev.data?.winner === 'wolf' ? '狼人阵营' : '好人阵营'}获胜`, glyph: '🏁', tone: 'neutral', time: t })
        break
    }
  }
  return out
}

function avatarForSeat(seat: number): string {
  const variants = [
    '/assets/avatars/variants/villager_01.png',
    '/assets/avatars/variants/villager_02.png',
    '/assets/avatars/variants/villager_03.png',
    '/assets/avatars/seer.png',
    '/assets/avatars/witch.png',
    '/assets/avatars/hunter.png',
    '/assets/avatars/variants/wolf_01.png',
    '/assets/avatars/variants/wolf_02.png',
  ]
  return variants[(seat - 1) % variants.length]
}

function short(s: string): string {
  // s might be ISO; show HH:MM:SS
  const idx = s.indexOf('T')
  if (idx >= 0) return s.slice(idx + 1, idx + 9)
  return s.slice(0, 8)
}
