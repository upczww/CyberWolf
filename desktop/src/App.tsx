import { useCallback, useEffect, useMemo, useState } from 'react'
import { useGameStore, type GameEvent, type Player } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet } from './hooks/useApi'
import GameAudio from './components/GameAudio'
import GameEffects from './components/GameEffects'
import MusicStudio from './components/MusicStudio'
import Toolbar from './components/Toolbar'
import GameList from './components/GameList'

const PHASE_META: Record<string, { label: string; asset: string; channel: string }> = {
  setup_game: { label: '准备局', asset: 'phase_day_discussion.png', channel: '裁判准备' },
  night_start: { label: '入夜', asset: 'phase_night.png', channel: '夜晚频道' },
  night_wolf: { label: '狼人行动', asset: 'phase_night.png', channel: '狼队私聊' },
  night_seer: { label: '预言家查验', asset: 'phase_night.png', channel: '私人查验' },
  night_witch: { label: '女巫行动', asset: 'phase_night.png', channel: '私人行动' },
  night_resolve: { label: '夜晚结算', asset: 'phase_dawn.png', channel: '裁判结算' },
  day_announce: { label: '天亮公布', asset: 'phase_dawn.png', channel: '公开频道' },
  sheriff_election: { label: '警长竞选', asset: 'phase_day_discussion.png', channel: '公开竞选' },
  day_speech: { label: '白天发言', asset: 'phase_day_discussion.png', channel: '公开讨论' },
  day_vote: { label: '投票放逐', asset: 'phase_vote.png', channel: '投票频道' },
  day_resolve: { label: '放逐结算', asset: 'phase_vote.png', channel: '裁判结算' },
  pending_skills: { label: '技能结算', asset: 'phase_last_words.png', channel: '技能频道' },
  check_win: { label: '胜负检查', asset: 'phase_endgame.png', channel: '裁判检查' },
  game_over: { label: '游戏结束', asset: 'phase_endgame.png', channel: '结算频道' },
}

const ROLE_META: Record<string, { label: string; avatar: string; tone: 'wolf' | 'god' | 'good' }> = {
  wolf: { label: '狼人', avatar: '/assets/avatars/wolf.png', tone: 'wolf' },
  seer: { label: '预言家', avatar: '/assets/avatars/seer_v2.png', tone: 'god' },
  witch: { label: '女巫', avatar: '/assets/avatars/witch.png', tone: 'god' },
  hunter: { label: '猎人', avatar: '/assets/avatars/hunter.png', tone: 'god' },
  idiot: { label: '白痴', avatar: '/assets/avatars/idiot.png', tone: 'god' },
  guard: { label: '守卫', avatar: '/assets/avatars/variants/villager_03.png', tone: 'god' },
  villager: { label: '村民', avatar: '/assets/avatars/villager.png', tone: 'good' },
}

const VILLAGER_VARIANTS = [
  '/assets/avatars/villager.png',
  '/assets/avatars/variants/villager_01.png',
  '/assets/avatars/variants/villager_02.png',
  '/assets/avatars/variants/villager_03.png',
]

const WOLF_VARIANTS = [
  '/assets/avatars/wolf.png',
  '/assets/avatars/variants/wolf_01.png',
  '/assets/avatars/variants/wolf_02.png',
]

const PHASE_ORDER = ['入夜', '狼人', '预言家', '女巫', '天亮', '讨论', '投票']

export default function App() {
  const {
    gameId,
    players,
    events,
    phase,
    round,
    status,
    winner,
    connected,
    setGameId,
    setPlayers,
    setEvents,
    setPhase,
    setRound,
    setStatus,
    setWinner,
    reset,
  } = useGameStore()
  const [showMusicStudio, setShowMusicStudio] = useState(false)
  const [showGameList, setShowGameList] = useState(false)
  const [showTrueRoles, setShowTrueRoles] = useState(true)

  useGameWS(gameId)

  useEffect(() => {
    if (!gameId) return
    loadGameDetail(gameId)
  }, [gameId])

  const loadGameDetail = async (gid: string) => {
    try {
      const detail = await apiGet<any>(`/api/games/${gid}`)
      if (detail.error) return
      setPlayers(detail.players || [])
      setEvents((detail.events || []).map((ev: any) => ({
        ...ev,
        data: ev.data_json || ev.data || {},
        event_type: ev.event_type,
      })))
      const state = detail.snapshot?.state_json
      if (state) {
        setPhase(state.phase || null)
        setRound(state.round || 1)
        setStatus(detail.game?.status || null)
        setWinner(state.winner || null)
      }
    } catch {
      // The desktop can still render its director shell while the server starts.
    }
  }

  const handleGameStarted = useCallback((newGameId: string) => {
    reset()
    setGameId(newGameId)
  }, [reset, setGameId])

  const handleSelectGame = useCallback((gid: string) => {
    reset()
    setGameId(gid)
  }, [reset, setGameId])

  const sortedPlayers = useMemo(() => {
    const bySeat = [...players].sort((a, b) => a.seat_index - b.seat_index)
    const slots: Array<Player | null> = Array.from({ length: 12 }, (_, index) => {
      return bySeat.find((p) => p.seat_index === index + 1) || null
    })
    return slots
  }, [players])

  const meta = phase ? PHASE_META[phase] : null
  const aliveCount = players.filter((p) => p.survived).length
  const deadCount = players.length ? players.length - aliveCount : 0
  const wolvesAlive = players.filter((p) => p.survived && p.faction === 'wolf').length
  const suspicionPeak = inferSuspicionPeak(events)
  const latestEvent = events.length > 0 ? events[events.length - 1] : null

  return (
    <div className="director-app">
      <GameAudio phase={phase} latestEvent={latestEvent} winner={winner} />
      <GameEffects latestEvent={latestEvent} />
      <div className="director-shell">
        <header className="director-topbar">
          <section className="brand-block">
            <img src="/assets/ui/logo.png" alt="" />
            <div>
              <h1>AI 狼人杀导演台</h1>
              <p>12 名 AI 玩家自动博弈，裁判引擎掌握真实状态</p>
            </div>
          </section>

          <section
            className="phase-banner"
            style={{ backgroundImage: `linear-gradient(90deg, rgba(14,10,8,.22), rgba(14,10,8,.42)), url(/assets/ui/phases/${meta?.asset || 'phase_night.png'})` }}
          >
            <span>第 {round || 1} 轮</span>
            <strong>{winner ? `${winner === 'good' ? '好人阵营' : '狼人阵营'}胜利` : meta?.label || '等待开始'}</strong>
            <span>{meta?.channel || '导演频道'}</span>
          </section>

          <section className="score-grid">
            <Stat label="存活" value={players.length ? aliveCount : 12} />
            <Stat label="死亡" value={deadCount} />
            <Stat label="狼队" value={players.length ? wolvesAlive : 3} />
            <Stat label="嫌疑峰值" value={suspicionPeak} />
          </section>
        </header>

        <main className="director-main">
          <section className="theater-panel">
            <div className="scene-bg" />
            <div className="channel-note">
              <img src="/assets/ui/icons/claw_slash.png" alt="" />
              <span>{meta?.channel || '等待裁判推进'}，公开频道{isNightPhase(phase) ? '已冻结' : '正在记录'}</span>
            </div>

            <div className="seat-rail rail-top" />
            <div className="seat-rail rail-bottom" />
            <div className="table-core">
              <div className="table-art" />
              <img className="table-effect table-eye" src="/assets/ui/effects/seer_eye_glow_overlay.png" alt="" />
              <img className="table-effect table-claw" src="/assets/ui/effects/wolf_claw_overlay.png" alt="" />
              <div className="judge-card">
                <h2>当前裁判判定</h2>
                <p>{buildJudgeSummary(phase, events)}</p>
              </div>
            </div>

            {sortedPlayers.map((player, index) => (
              <PlayerCard
                key={player?.player_id || `empty-${index + 1}`}
                player={player}
                seatIndex={index + 1}
                phase={phase}
                showTrueRole={showTrueRoles}
              />
            ))}
          </section>

          <aside className="side-console">
            <section className="console-panel feed-panel">
              <PanelTitle title="AI 对话流" icon="/assets/ui/icons/ballot_vote.png" />
              <div className="message-feed">
                {buildConversation(events).map((item, index) => (
                  <article className="speech-card" key={`${item.title}-${index}`}>
                    <img src={item.avatar} alt="" />
                    <div>
                      <b>
                        {item.title}
                        <i>{item.channel}</i>
                      </b>
                      <p>{item.text}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="console-panel">
              <PanelTitle title="推理面板" icon="/assets/ui/results/seer_result_wolf.png" />
              <div className="logic-grid">
                <Logic label="互斥身份声明" value={players.length ? `${Math.max(1, wolvesAlive)} 组` : '2 组'} />
                <Logic label="跟票集中度" value={events.some((e) => e.event_type === 'vote_cast') ? '高' : '待观察'} />
                <Logic label="狼队压力" value={wolvesAlive <= 1 ? '濒危' : '均衡'} />
                <Logic label="公开发言" value={`${events.filter((e) => e.event_type?.includes('speech')).length || 0} 条`} />
              </div>
              <SuspicionBars events={events} />
            </section>

            <section className="console-panel">
              <PanelTitle title="裁判日志" icon="/assets/ui/status/waiting.png" />
              <div className="event-list">
                {buildJudgeEvents(events).map((item, index) => (
                  <div className="event-row" key={`${item.text}-${index}`}>
                    <img src={item.icon} alt="" />
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </main>

        <Toolbar
          onGameStarted={handleGameStarted}
          onOpenMusic={() => setShowMusicStudio(true)}
          onOpenGameList={() => setShowGameList(true)}
          showTrueRoles={showTrueRoles}
          onToggleRoles={() => setShowTrueRoles((value) => !value)}
        />
      </div>

      <div className={`connection-pill ${connected ? 'online' : ''}`}>
        <span />
        {connected ? '实时连接' : status === 'completed' ? '对局完成' : '等待连接'}
      </div>

      {showGameList && <GameList onSelect={handleSelectGame} onClose={() => setShowGameList(false)} />}
      {showMusicStudio && <MusicStudio onClose={() => setShowMusicStudio(false)} />}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="score-card">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function PlayerCard({
  player,
  seatIndex,
  phase,
  showTrueRole,
}: {
  player: Player | null
  seatIndex: number
  phase: string | null
  showTrueRole: boolean
}) {
  const role = player?.role || 'unknown'
  const meta = getRoleMeta(player, seatIndex)
  const alive = player ? !!player.survived : true
  const acting = isActing(player, phase)
  const statusAsset = getStatusAsset(player, acting)
  const roleLabel = player ? (showTrueRole ? meta.label : claimLabel(player)) : '未知'

  return (
    <article className={`player-card seat-${seatIndex} ${acting ? 'is-acting' : ''} ${!alive ? 'is-dead' : ''}`}>
      <div className={`avatar-frame ${meta.tone}`}>
        <img className="avatar-img" src={player ? meta.avatar : '/assets/ui/cards/unknown_avatar.png'} alt="" />
        {player?.is_sheriff ? <img className="sheriff-badge" src="/assets/ui/badge_sheriff.png" alt="" /> : null}
        {statusAsset ? <img className="status-badge" src={statusAsset} alt="" /> : null}
        <span className={`identity-plate ${meta.tone}`}>{roleLabel}</span>
      </div>
      <div className="seat-name">{seatIndex}号 {playerName(role, seatIndex)}</div>
      <div className="seat-state">{seatState(player, role)}</div>
    </article>
  )
}

function PanelTitle({ title, icon }: { title: string; icon: string }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <img src={icon} alt="" />
    </div>
  )
}

function Logic({ label, value }: { label: string; value: string }) {
  return (
    <div className="logic-card">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function SuspicionBars({ events }: { events: GameEvent[] }) {
  const scores = suspicionScores(events)
  const rows = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 3)
  const displayRows = rows.length ? rows : [['11', 86], ['7', 68], ['4', 41]]

  return (
    <div className="heat-list">
      {displayRows.map(([seat, score]) => (
        <div className="heat-row" key={seat}>
          <span>{seat}号</span>
          <div className="heat-bar"><span style={{ width: `${Math.min(96, Number(score))}%` }} /></div>
          <b>{score}</b>
        </div>
      ))}
    </div>
  )
}

function getRoleMeta(player: Player | null, seatIndex: number) {
  if (!player) return { label: '未知', avatar: '/assets/ui/cards/unknown_avatar.png', tone: 'good' as const }
  if (player.faction === 'wolf') {
    return { ...ROLE_META.wolf, avatar: WOLF_VARIANTS[(seatIndex - 1) % WOLF_VARIANTS.length] }
  }
  if (player.role === 'villager') {
    return { ...ROLE_META.villager, avatar: VILLAGER_VARIANTS[(seatIndex - 1) % VILLAGER_VARIANTS.length] }
  }
  return ROLE_META[player.role] || ROLE_META.villager
}

function isNightPhase(phase: string | null) {
  return !!phase && phase.startsWith('night')
}

function isActing(player: Player | null, phase: string | null) {
  if (!player || !player.survived || !phase) return false
  if (phase === 'night_wolf') return player.faction === 'wolf'
  if (phase === 'night_seer') return player.role === 'seer'
  if (phase === 'night_witch') return player.role === 'witch'
  if (phase === 'pending_skills') return ['hunter', 'idiot'].includes(player.role)
  return false
}

function getStatusAsset(player: Player | null, acting: boolean) {
  if (!player) return null
  if (!player.survived) {
    if (player.death_cause === 'exile') return '/assets/ui/status/exiled.png'
    if (player.death_cause === 'poison') return '/assets/ui/status/poisoned.png'
    return '/assets/ui/status/dead.png'
  }
  if (acting) return '/assets/ui/status/selected.png'
  if (player.is_sheriff) return null
  return null
}

function claimLabel(player: Player) {
  if (!player.survived) return ROLE_META[player.role]?.label || '已公开'
  return player.faction === 'wolf' ? '声称好人' : '未知'
}

function playerName(role: string, seatIndex: number) {
  const names = ['墨爪', '星眼', '阿杯', '药婆', '弩手', '麦穗', '黑吻', '铃铛', '灯婆', '老弩', '灰耳', '木匠']
  return names[seatIndex - 1] || (ROLE_META[role]?.label || '玩家')
}

function seatState(player: Player | null, role: string) {
  if (!player) return '等待入座'
  if (!player.survived) return player.death_cause === 'exile' ? '已放逐' : '已出局'
  if (player.is_sheriff) return '警长'
  if (role === 'witch') return '药剂待定'
  if (role === 'hunter') return '可开枪'
  return player.faction === 'wolf' ? '公开身份：好人' : '公开身份：未知'
}

function buildJudgeSummary(phase: string | null, events: GameEvent[]) {
  if (phase === 'night_wolf') return '狼队正在私聊决策，候选目标已由规则引擎过滤。'
  if (phase === 'night_seer') return '预言家将获得单人查验结果，其他 AI 不会看到私人信息。'
  if (phase === 'night_witch') return '女巫只看到今晚死亡信息，并提交救药或毒药动作。'
  if (phase === 'day_speech') return '公开频道开放，AI 将根据私有记忆和公共发言轮流博弈。'
  if (phase === 'day_vote') return '裁判收集投票，死者和无票权目标会被自动排除。'
  if (events.length) return '裁判引擎维护真实状态，AI 只能提交当前阶段合法动作。'
  return '启动新局后，12 名 AI 会按身份、私有信息和公开记录自动行动。'
}

function buildConversation(events: GameEvent[]) {
  const speechEvents = events.filter((ev) => ['public_speech_made', 'sheriff_campaign', 'death_speech'].includes(ev.event_type)).slice(-4)
  if (!speechEvents.length) {
    return [
      { title: '7号 黑吻', channel: '狼队私聊', avatar: '/assets/avatars/variants/wolf_02.png', text: '今晚不碰警长，先切断村民信息源。' },
      { title: '1号 墨爪', channel: '行动计划', avatar: '/assets/avatars/wolf.png', text: '我明天继续踩 4 号，把毒药压力引过去。' },
      { title: '裁判', channel: '系统事件', avatar: '/assets/ui/cards/unknown_avatar.png', text: '公开频道暂停，狼队正在提交夜刀目标。' },
      { title: '2号 星眼', channel: '下一行动', avatar: '/assets/avatars/seer_v2.png', text: '等待狼队完成后，将进入预言家查验阶段。' },
    ]
  }

  return speechEvents.map((ev) => {
    const playerId = ev.data?.player_id || ev.data?.actor_id || '?'
    const text = ev.data?.speech || ev.content || '正在发言'
    return {
      title: `${playerId}号 AI`,
      channel: ev.scope === 'wolf_team' ? '狼队频道' : ev.scope === 'role_private' ? '私人频道' : '公开频道',
      avatar: avatarForEventPlayer(playerId),
      text: String(text).slice(0, 92),
    }
  })
}

function buildJudgeEvents(events: GameEvent[]) {
  const mapped = events.slice(-5).map((ev) => {
    if (ev.event_type === 'seer_checked') return { icon: '/assets/ui/icons/seer_eye.png', text: `预言家查验 ${ev.data?.target_id || '?'} 号。` }
    if (ev.event_type === 'witch_used_poison') return { icon: '/assets/ui/icons/poison.png', text: `女巫使用毒药，目标 ${ev.data?.target_id || '?'} 号。` }
    if (ev.event_type === 'witch_used_antidote') return { icon: '/assets/ui/icons/antidote.png', text: `女巫使用解药，救下 ${ev.data?.target_id || '?'} 号。` }
    if (ev.event_type === 'vote_cast') return { icon: '/assets/ui/vote/vote_count_token.png', text: `${ev.data?.voter_id || '?'} 号投给 ${ev.data?.target_id || '?'} 号。` }
    if (ev.event_type === 'player_died') return { icon: '/assets/ui/status/dead.png', text: `${ev.data?.player_id || '?'} 号出局。` }
    return { icon: '/assets/ui/status/waiting.png', text: PHASE_META[ev.data?.phase]?.label || ev.content || ev.event_type }
  })

  return mapped.length ? mapped : [
    { icon: '/assets/ui/icons/seer_eye.png', text: '昨夜 2号查验 5号，结果为好人。' },
    { icon: '/assets/ui/icons/poison.png', text: '女巫保留毒药，解药已消耗。' },
    { icon: '/assets/ui/vote/vote_count_token.png', text: '昨日投票：7号 3票，4号 2票。' },
  ]
}

function avatarForEventPlayer(playerId: number | string) {
  const n = Number(playerId)
  if (!Number.isFinite(n)) return '/assets/ui/cards/unknown_avatar.png'
  return n % 5 === 0 ? '/assets/avatars/hunter.png'
    : n % 4 === 0 ? '/assets/avatars/witch.png'
      : n % 3 === 0 ? '/assets/avatars/variants/villager_01.png'
        : n % 2 === 0 ? '/assets/avatars/seer_v2.png'
          : '/assets/avatars/variants/wolf_02.png'
}

function suspicionScores(events: GameEvent[]) {
  const scores: Record<string, number> = {}
  for (const ev of events) {
    const target = ev.data?.target_id || ev.data?.chosen
    if (!target) continue
    const key = String(target)
    scores[key] = (scores[key] || 24) + (ev.event_type === 'vote_cast' ? 18 : 12)
  }
  return scores
}

function inferSuspicionPeak(events: GameEvent[]) {
  const scores = suspicionScores(events)
  const [seat] = Object.entries(scores).sort((a, b) => b[1] - a[1])[0] || []
  return seat ? `${seat}号` : '11号'
}
