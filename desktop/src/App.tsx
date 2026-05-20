import { useCallback, useEffect, useMemo, useState } from 'react'
import GameAudio from './components/GameAudio'
import GameEffects from './components/GameEffects'
import HumanActionPanel from './components/HumanActionPanel'
import { apiGet, apiPost } from './hooks/useApi'
import { useGameWS } from './hooks/useGameWS'
import { useGameStore, type GameEvent, type Player } from './stores/game'

type ViewMode = 'god' | 'observer' | 'self'
type PhaseTone = 'day' | 'night' | 'vote' | 'skill' | 'result'
type RoleTone = 'good' | 'god' | 'wolf' | 'neutral' | 'unknown'
type DrawerTab = 'chat' | 'vote' | 'settle'

interface RoleMeta {
  label: string
  camp: string
  tone: RoleTone
  portrait: string
  icon: string
}

interface PhaseMeta {
  label: string
  shortLabel: string
  tone: PhaseTone
  icon: string
  background: string
  actionLabel: string
}

interface VisiblePlayer {
  player: Player
  meta: RoleMeta
  hidden: boolean
  portrait: string
}

const A = '/assets/ui'
const UNKNOWN_CLOAK = `${A}/portraits/unknown/portrait_unknown_cloak_01.png`
const UNKNOWN_AI = `${A}/portraits/unknown/portrait_unknown_ai_01.png`

const ROLE_META: Record<string, RoleMeta> = {
  villager: {
    label: '平民',
    camp: '好人阵营',
    tone: 'good',
    portrait: `${A}/portraits/roles/portrait_villager_male_01.png`,
    icon: `${A}/icons/roles/icon_role_villager.png`,
  },
  wolf: {
    label: '狼人',
    camp: '狼人阵营',
    tone: 'wolf',
    portrait: `${A}/portraits/roles/portrait_werewolf_01.png`,
    icon: `${A}/icons/roles/icon_role_werewolf.png`,
  },
  werewolf: {
    label: '狼人',
    camp: '狼人阵营',
    tone: 'wolf',
    portrait: `${A}/portraits/roles/portrait_werewolf_01.png`,
    icon: `${A}/icons/roles/icon_role_werewolf.png`,
  },
  seer: {
    label: '预言家',
    camp: '神职',
    tone: 'god',
    portrait: `${A}/portraits/roles/portrait_seer_01.png`,
    icon: `${A}/icons/roles/icon_role_seer.png`,
  },
  witch: {
    label: '女巫',
    camp: '神职',
    tone: 'god',
    portrait: `${A}/portraits/roles/portrait_witch_01.png`,
    icon: `${A}/icons/roles/icon_role_witch.png`,
  },
  hunter: {
    label: '猎人',
    camp: '神职',
    tone: 'god',
    portrait: `${A}/portraits/roles/portrait_hunter_01.png`,
    icon: `${A}/icons/roles/icon_role_hunter.png`,
  },
  idiot: {
    label: '白痴',
    camp: '神职',
    tone: 'god',
    portrait: `${A}/portraits/roles/portrait_idiot_01.png`,
    icon: `${A}/icons/roles/icon_role_idiot.png`,
  },
  guard: {
    label: '守卫',
    camp: '神职',
    tone: 'god',
    portrait: `${A}/portraits/roles/portrait_guard_01.png`,
    icon: `${A}/icons/roles/icon_role_guard.png`,
  },
  unknown: {
    label: '未知',
    camp: '身份未公开',
    tone: 'unknown',
    portrait: UNKNOWN_CLOAK,
    icon: `${A}/icons/status/icon_status_identity_hidden.png`,
  },
}

const EXTRA_PORTRAITS = [
  `${A}/portraits/extra/portrait_elder_male_01.png`,
  `${A}/portraits/extra/portrait_elder_female_01.png`,
  `${A}/portraits/extra/portrait_boy_01.png`,
  `${A}/portraits/extra/portrait_girl_01.png`,
  `${A}/portraits/extra/portrait_villager_lantern_01.png`,
  `${A}/portraits/roles/portrait_villager_female_01.png`,
]

const PHASE_META: Record<string, PhaseMeta> = {
  day_speech: {
    label: '第 1 天 · 白天',
    shortLabel: '发言阶段',
    tone: 'day',
    icon: `${A}/icons/actions/icon_action_chat.png`,
    background: `${A}/backgrounds/bg_global_moonlit_village_day.png`,
    actionLabel: '号玩家发言中',
  },
  day_vote: {
    label: '第 1 天 · 白天',
    shortLabel: '投票阶段',
    tone: 'vote',
    icon: `${A}/icons/actions/icon_action_vote.png`,
    background: `${A}/backgrounds/bg_phase_vote.png`,
    actionLabel: '等待投票',
  },
  sheriff_election: {
    label: '第 1 天 · 白天 · 警长竞选',
    shortLabel: '警长竞选',
    tone: 'day',
    icon: `${A}/icons/actions/icon_action_campaign.png`,
    background: `${A}/backgrounds/bg_phase_sheriff_election.png`,
    actionLabel: '警长竞选阶段',
  },
  night_wolf: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '狼人行动',
    tone: 'night',
    icon: `${A}/icons/skills/icon_skill_wolf_kill.png`,
    background: `${A}/backgrounds/bg_phase_wolf_action.png`,
    actionLabel: '狼队夜刀目标',
  },
  night_witch: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '女巫行动',
    tone: 'skill',
    icon: `${A}/icons/skills/icon_skill_witch_heal.png`,
    background: `${A}/backgrounds/bg_phase_witch_action.png`,
    actionLabel: '女巫请睁眼',
  },
  night_seer: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '预言家行动',
    tone: 'skill',
    icon: `${A}/icons/skills/icon_skill_seer_check.png`,
    background: `${A}/backgrounds/bg_phase_seer_action.png`,
    actionLabel: '预言家查验',
  },
  night_guard: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '守卫行动',
    tone: 'skill',
    icon: `${A}/icons/skills/icon_skill_guard_protect.png`,
    background: `${A}/backgrounds/bg_phase_night_overview.png`,
    actionLabel: '守卫行动',
  },
  game_over: {
    label: '游戏结束',
    shortLabel: '结算',
    tone: 'result',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_global_result_hall.png`,
    actionLabel: '查看结果',
  },
}

const PHASE_STEPS = [
  ['警长竞选', 'sheriff_election', `${A}/icons/actions/icon_action_campaign.png`],
  ['发言阶段', 'day_speech', `${A}/icons/actions/icon_action_chat.png`],
  ['放逐投票', 'day_vote', `${A}/icons/actions/icon_action_vote.png`],
  ['夜晚阶段', 'night_witch', `${A}/icons/actions/icon_landing_ai_autoplay.png`],
] as const

const DEMO_PLAYERS: Player[] = [
  player(1, 'villager', 'good'),
  player(2, 'witch', 'good'),
  player(3, 'hunter', 'good'),
  player(4, 'villager', 'good'),
  player(5, 'seer', 'good'),
  player(6, 'villager', 'good'),
  player(7, 'guard', 'good'),
  player(8, 'werewolf', 'wolf'),
  player(9, 'werewolf', 'wolf'),
  player(10, 'villager', 'good'),
  player(11, 'idiot', 'good'),
  player(12, 'villager', 'good'),
]

const DEMO_EVENTS: GameEvent[] = [
  event('phase_started', '游戏开始，12人标准场。', { phase: 'setup_game' }, 1),
  event('phase_started', '昨晚是平安夜，无人出局。', { phase: 'day_speech' }, 2),
  event('sheriff_campaign', '4号玩家报名竞选警长。', { player_id: 4 }, 3),
  event('public_speech_made', '1号玩家认为8号发言逻辑有问题。', { player_id: 1, public_speech: '我觉得8号发言逻辑有问题。' }, 4),
  event('public_speech_made', '7号玩家支持4号。', { player_id: 7, public_speech: '支持4号。' }, 5),
  event('vote_cast', '8号投给4号。', { voter_id: 8, target_id: 4 }, 6),
  event('vote_cast', '9号投给8号。', { voter_id: 9, target_id: 8 }, 7),
]

const STATUS_LEGEND = [
  ['警长', `${A}/icons/status/icon_status_sheriff.png`],
  ['被刀', `${A}/icons/skills/icon_skill_wolf_kill.png`],
  ['被驱逐', `${A}/icons/status/icon_status_exiled.png`],
  ['被毒死', `${A}/icons/skills/icon_skill_witch_poison.png`],
  ['被救', `${A}/icons/status/icon_status_guarded.png`],
  ['死亡', `${A}/icons/status/icon_status_dead.png`],
  ['被猎人射中', `${A}/icons/skills/icon_hunter_target.png`],
] as const

function player(seat: number, role: string, faction: string): Player {
  return {
    player_id: seat,
    seat_index: seat,
    role,
    faction,
    is_sheriff: seat === 1 || seat === 7 ? 1 : 0,
    survived: 1,
  }
}

function event(eventType: string, content: string, data: Record<string, unknown>, seq: number): GameEvent {
  return {
    game_id: 'demo',
    phase: 'day_speech',
    scope: 'public',
    event_type: eventType,
    content,
    data,
    seq,
    round: 1,
  }
}

export default function App() {
  const {
    gameId,
    players,
    events,
    phase,
    round,
    winner,
    connected,
    viewMode,
    humanSeat,
    ttsEnabled,
    awaitingHuman,
    setGameId,
    setPlayers,
    setEvents,
    setPhase,
    setRound,
    setStatus,
    setWinner,
    setViewMode,
    setHumanSeat,
    setTtsEnabled,
    reset,
  } = useGameStore()

  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyTab, setHistoryTab] = useState<DrawerTab>('vote')
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [skillOpen, setSkillOpen] = useState(false)
  const [legendOpen, setLegendOpen] = useState(false)
  const [landingMode, setLandingMode] = useState<ViewMode>('self')
  const [loadingStart, setLoadingStart] = useState(false)

  useGameWS(gameId, viewMode === 'self' ? humanSeat : null)

  useEffect(() => {
    if (!gameId || gameId === 'demo') return
    loadGameDetail(gameId)
  }, [gameId, humanSeat, viewMode])

  useEffect(() => {
    apiGet<{ enabled: boolean }>('/api/tts/status')
      .then((res) => setTtsEnabled(!!res.enabled))
      .catch(() => undefined)
  }, [setTtsEnabled])

  const visiblePlayers = players.length ? players : DEMO_PLAYERS
  const visibleEvents = events.length ? events : DEMO_EVENTS
  const visiblePhase = phase || 'day_speech'
  const meta = PHASE_META[visiblePhase] || PHASE_META.day_speech
  const latestEvent = visibleEvents[visibleEvents.length - 1] || null
  const voteCounts = useMemo(() => buildVoteCounts(visibleEvents), [visibleEvents])
  const currentSpeaker = latestSpeaker(visibleEvents) || 3
  const roomId = gameId && gameId !== 'demo' ? gameId.slice(0, 6) : '123456'

  const loadGameDetail = async (gid: string) => {
    try {
      const seatParam = viewMode === 'self' && humanSeat != null ? `?seat=${humanSeat}` : ''
      const detail = await apiGet<any>(`/api/games/${gid}${seatParam}`)
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
      seedDemoGame()
    }
  }

  const seedDemoGame = useCallback((nextPhase = 'day_speech', nextViewMode: ViewMode = viewMode) => {
    setGameId('demo')
    setPlayers(DEMO_PLAYERS)
    setEvents(DEMO_EVENTS)
    setPhase(nextPhase)
    setRound(1)
    setStatus('running')
    setWinner(null)
    setViewMode(nextViewMode)
    if (nextViewMode === 'self') setHumanSeat(3)
  }, [setEvents, setGameId, setHumanSeat, setPhase, setPlayers, setRound, setStatus, setViewMode, setWinner, viewMode])

  const startGame = async (useLlm: boolean, mode: ViewMode = landingMode) => {
    setLoadingStart(true)
    setViewMode(mode)
    setHumanSeat(mode === 'self' ? 3 : null)
    try {
      const payload: Record<string, unknown> = { config_id: '12p_pre_witch_hunter_idiot', use_llm: useLlm }
      if (mode === 'self') payload.human_join = true
      const res = await apiPost<{ game_id: string; human_seat?: number | null }>('/api/games/start', payload)
      reset()
      setViewMode(mode)
      setHumanSeat(mode === 'self' && typeof res.human_seat === 'number' ? res.human_seat : null)
      setGameId(res.game_id)
    } catch {
      seedDemoGame('day_speech', mode)
    } finally {
      setLoadingStart(false)
    }
  }

  const toggleTts = async () => {
    try {
      const res = await apiPost<{ enabled: boolean }>('/api/tts/toggle', {})
      setTtsEnabled(!!res.enabled)
    } catch {
      setTtsEnabled(!ttsEnabled)
    }
  }

  const resetToLanding = () => {
    reset()
    setHistoryOpen(false)
    setInspectorOpen(false)
    setSkillOpen(false)
    setLegendOpen(false)
  }

  if (!gameId) {
    return (
      <LandingScreen
        mode={landingMode}
        loading={loadingStart}
        ttsEnabled={ttsEnabled}
        onModeChange={setLandingMode}
        onStart={(useLlm) => startGame(useLlm)}
        onToggleTts={toggleTts}
      />
    )
  }

  return (
    <div className={`sample-app phase-${meta.tone}`} style={{ '--scene-bg': `url("${meta.background}")` } as React.CSSProperties}>
      <GameAudio phase={visiblePhase} latestEvent={latestEvent} winner={winner} ttsEnabled={ttsEnabled} />
      <GameEffects latestEvent={gameId === 'demo' ? null : latestEvent} />

      <TopBar
        roomId={roomId}
        round={round || 1}
        meta={meta}
        remaining={visiblePhase === 'day_speech' ? 60 : visiblePhase === 'night_witch' ? 120 : 45}
        onHistory={() => {
          setHistoryOpen(true)
          setHistoryTab('vote')
        }}
        onInspector={() => setInspectorOpen(true)}
        onSettings={toggleTts}
        ttsEnabled={ttsEnabled}
      />

      <main className="game-board">
        <PlayerColumn
          players={visiblePlayers.slice(0, 6)}
          viewMode={viewMode}
          humanSeat={humanSeat}
          activeSeat={currentSpeaker}
          voteCounts={voteCounts}
        />

        <CenterStage
          phase={visiblePhase}
          meta={meta}
          players={visiblePlayers}
          events={visibleEvents}
          currentSpeaker={currentSpeaker}
          winner={winner}
          connected={connected}
          inspectorOpen={inspectorOpen}
          onCloseInspector={() => setInspectorOpen(false)}
          onSetPhase={setPhase}
          onVote={() => setPhase('day_vote')}
          onSkill={() => {
            setPhase('night_witch')
            setSkillOpen(true)
          }}
          onReset={resetToLanding}
        />

        <PlayerColumn
          players={visiblePlayers.slice(6, 12)}
          viewMode={viewMode}
          humanSeat={humanSeat}
          activeSeat={currentSpeaker}
          voteCounts={voteCounts}
          reverse
        />
      </main>

      <footer className="bottom-dock">
        <DockButton icon={`${A}/icons/actions/icon_action_chat.png`} label="聊天" />
        <DockButton icon={`${A}/icons/actions/icon_landing_match_records.png`} label="送礼" />
      </footer>

      {historyOpen && (
        <HistoryDrawer
          tab={historyTab}
          events={visibleEvents}
          players={visiblePlayers}
          onTab={setHistoryTab}
          onClose={() => setHistoryOpen(false)}
        />
      )}
      {legendOpen && <StatusLegend onClose={() => setLegendOpen(false)} />}
      {skillOpen && (
        <SkillModal
          phase={visiblePhase}
          players={visiblePlayers}
          onClose={() => setSkillOpen(false)}
          onProtect={() => {
            setSkillOpen(false)
            setPhase('day_speech')
          }}
        />
      )}
      {awaitingHuman && gameId && (
        <HumanActionPanel request={awaitingHuman} gameId={gameId} players={visiblePlayers} />
      )}
      <button className="legend-hotspot" onClick={() => setLegendOpen(true)}>状态图标</button>
    </div>
  )
}

function TopBar({
  roomId,
  round,
  meta,
  remaining,
  ttsEnabled,
  onHistory,
  onInspector,
  onSettings,
}: {
  roomId: string
  round: number
  meta: PhaseMeta
  remaining: number
  ttsEnabled: boolean
  onHistory: () => void
  onInspector: () => void
  onSettings: () => void
}) {
  return (
    <header className="game-topbar">
      <button className="round-icon" aria-label="菜单"><span /><span /><span /></button>
      <div className="room-meta">
        <span>房间 {roomId}</span>
        <b>12人标准场</b>
      </div>
      <div className="day-stack">
        <div className="day-pill">
          <span>{meta.label.replace('第 1', `第 ${round}`)}</span>
          <img src={meta.tone === 'night' || meta.tone === 'skill' ? `${A}/icons/actions/icon_landing_ai_autoplay.png` : `${A}/icons/actions/icon_speed_config.png`} alt="" />
        </div>
        <div className="phase-mini">
          <span>{meta.shortLabel}</span>
          <b>{remaining}s</b>
        </div>
      </div>
      <div className="top-actions">
        <IconButton icon={`${A}/icons/actions/icon_action_record.png`} label="记录" onClick={onHistory} />
        <IconButton icon={`${A}/icons/actions/icon_action_history.png`} label="历史" onClick={onInspector} />
        <IconButton icon={`${A}/icons/actions/icon_action_settings.png`} label="设置" onClick={onSettings} active={ttsEnabled} />
      </div>
    </header>
  )
}

function LandingScreen({
  mode,
  loading,
  ttsEnabled,
  onModeChange,
  onStart,
  onToggleTts,
}: {
  mode: ViewMode
  loading: boolean
  ttsEnabled: boolean
  onModeChange: (mode: ViewMode) => void
  onStart: (useLlm: boolean) => void
  onToggleTts: () => void
}) {
  return (
    <div className="landing-page">
      <div className="landing-bg" />
      <header className="landing-top">
        <div className="profile-chip">
          <img src={`${A}/portraits/roles/portrait_villager_male_01.png`} alt="" />
          <div>
            <b>玩家昵称七个字</b>
            <span>ID: 123456</span>
          </div>
        </div>
        <div className="landing-sound">
          <IconButton icon={ttsEnabled ? `${A}/icons/actions/icon_landing_sound_on.png` : `${A}/icons/actions/icon_landing_sound_off.png`} label={ttsEnabled ? '声音开' : '声音关'} onClick={onToggleTts} active={ttsEnabled} />
          <IconButton icon={`${A}/icons/actions/icon_landing_help.png`} label="帮助" />
          <IconButton icon={`${A}/icons/actions/icon_landing_settings.png`} label="设置" />
        </div>
      </header>

      <section className="landing-logo">
        <img src={`${A}/logo/logo_werewolf_title_large.png`} alt="狼人杀" />
        <span>12人标准版</span>
      </section>

      <section className="mode-cards">
        <ModeCard
          active={mode === 'self'}
          tone="blue"
          icon={`${A}/icons/actions/icon_landing_personal_mode.png`}
          title="个人视角"
          text="沉浸体验，只属于你的推理之旅"
          bullets={['你是唯一的真人玩家', '其他玩家由AI扮演', '只可见自己的身份与白天操作']}
          onClick={() => onModeChange('self')}
          onStart={() => onStart(true)}
          loading={loading && mode === 'self'}
        />
        <ModeCard
          active={mode === 'god'}
          tone="red"
          icon={`${A}/icons/actions/icon_landing_god_mode.png`}
          title="上帝视角"
          text="掌控全局，洞悉所有秘密与真相"
          bullets={['上帝视角观战所有信息', '查看所有身份与技能', '复盘分析，掌控全局']}
          onClick={() => onModeChange('god')}
          onStart={() => onStart(false)}
          loading={loading && mode === 'god'}
        />
      </section>

      <footer className="landing-nav">
        <LandingNavItem icon={`${A}/icons/actions/icon_landing_match_records.png`} label="对局记录" />
        <LandingNavItem icon={`${A}/icons/actions/icon_landing_ai_autoplay.png`} label="AI 托管" badge="NEW" />
        <LandingNavItem icon={`${A}/icons/actions/icon_landing_ai_summary.png`} label="游戏总结" />
        <LandingNavItem icon={`${A}/icons/actions/icon_landing_achievement.png`} label="成就" />
        <LandingNavItem icon={`${A}/icons/actions/icon_landing_ranking.png`} label="排行榜" />
      </footer>
      <span className="version-mark">版本：1.0.0</span>
    </div>
  )
}

function ModeCard({
  active,
  tone,
  icon,
  title,
  text,
  bullets,
  loading,
  onClick,
  onStart,
}: {
  active: boolean
  tone: 'blue' | 'red'
  icon: string
  title: string
  text: string
  bullets: string[]
  loading: boolean
  onClick: () => void
  onStart: () => void
}) {
  return (
    <article className={`mode-card mode-${tone} ${active ? 'active' : ''}`} onClick={onClick}>
      <img className="mode-icon" src={icon} alt="" />
      <h2>{title}</h2>
      <p>{text}</p>
      <ul>
        {bullets.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <button onClick={(event) => {
        event.stopPropagation()
        onStart()
      }}>{loading ? '启动中' : '开始游戏'}<span>›</span></button>
    </article>
  )
}

function LandingNavItem({ icon, label, badge }: { icon: string; label: string; badge?: string }) {
  return (
    <button className="landing-nav-item">
      <span>{badge}</span>
      <img src={icon} alt="" />
      <b>{label}</b>
    </button>
  )
}

function PlayerColumn({
  players,
  viewMode,
  humanSeat,
  activeSeat,
  voteCounts,
  reverse = false,
}: {
  players: Player[]
  viewMode: ViewMode
  humanSeat: number | null
  activeSeat: number
  voteCounts: Record<number, number>
  reverse?: boolean
}) {
  return (
    <section className={`seat-column ${reverse ? 'seat-column-right' : 'seat-column-left'}`}>
      {players.map((player) => (
        <PlayerCard
          key={player.seat_index}
          visible={visiblePlayer(player, viewMode, humanSeat)}
          active={player.seat_index === activeSeat}
          voteCount={voteCounts[player.seat_index] || 0}
          reverse={reverse}
        />
      ))}
    </section>
  )
}

function PlayerCard({
  visible,
  active,
  voteCount,
  reverse = false,
}: {
  visible: VisiblePlayer
  active: boolean
  voteCount: number
  reverse?: boolean
}) {
  const { player, meta, hidden, portrait } = visible
  const dead = !player.survived
  return (
    <article className={`player-card tone-${meta.tone} ${active ? 'active' : ''} ${dead ? 'dead' : ''} ${reverse ? 'reverse' : ''}`}>
      <div className="seat-number">{player.seat_index}</div>
      <div className="player-copy">
        <span>{`玩家${player.seat_index}`}</span>
        <strong>{hidden ? '未知' : meta.label}</strong>
      </div>
      <img className="player-portrait" src={portrait} alt="" />
      <div className="status-stack">
        {player.is_sheriff ? <img src={`${A}/icons/status/icon_status_sheriff.png`} alt="" /> : null}
        {voteCount ? <b>{voteCount}</b> : null}
      </div>
    </article>
  )
}

function CenterStage({
  phase,
  meta,
  players,
  events,
  currentSpeaker,
  winner,
  connected,
  inspectorOpen,
  onCloseInspector,
  onSetPhase,
  onVote,
  onSkill,
  onReset,
}: {
  phase: string
  meta: PhaseMeta
  players: Player[]
  events: GameEvent[]
  currentSpeaker: number
  winner: string | null
  connected: boolean
  inspectorOpen: boolean
  onCloseInspector: () => void
  onSetPhase: (phase: string | null) => void
  onVote: () => void
  onSkill: () => void
  onReset: () => void
}) {
  const latest = events[events.length - 1]
  if (inspectorOpen || phase === 'sheriff_election') {
    return <SheriffPanel players={players} onClose={onCloseInspector} onSetPhase={onSetPhase} />
  }

  return (
    <section className="center-stage">
      <div className="village-window" />
      <section className="speaker-status">
        <h1>
          <span>{currentSpeaker}</span>
          {winner ? `${winner === 'wolf' ? '狼人' : '好人'}阵营胜利` : `${currentSpeaker}${meta.actionLabel}`}
        </h1>
        <div className="timer-row">
          <img src={`${A}/icons/actions/icon_speed_config.png`} alt="" />
          <div className="timer-track"><span /></div>
          <b>{phase === 'night_witch' ? '120s' : '60s'}</b>
        </div>
      </section>

      <nav className="phase-tabs">
        {PHASE_STEPS.map(([label, stepPhase, icon]) => (
          <button key={label} className={phase === stepPhase ? 'active' : ''} onClick={() => onSetPhase(stepPhase)}>
            <img src={icon} alt="" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {phase === 'day_vote' ? <VotePanel players={players} /> : <NoticePanel latest={latest} connected={connected} />}

      <section className="stage-actions">
        <button className="ghost-action" onClick={onReset}>结束发言</button>
        <button className="primary-action" onClick={isSkillPhase(phase) ? onSkill : onVote}>
          {isSkillPhase(phase) ? '技能行动' : '投票'}
        </button>
      </section>
    </section>
  )
}

function NoticePanel({ latest, connected }: { latest?: GameEvent; connected: boolean }) {
  return (
    <section className="notice-panel">
      <p><i />昨晚是平安夜，无人出局。</p>
      <p><i />警长决定顺序发言。</p>
      <p><i />{latest?.content || (connected ? '实时连接已建立。' : '离线演示模式，界面数据用于预览。')}</p>
    </section>
  )
}

function VotePanel({ players }: { players: Player[] }) {
  return (
    <section className="vote-panel">
      <header>
        <b>放逐投票</b>
        <span>选择你认为最像狼人的玩家</span>
      </header>
      <div className="vote-grid">
        {players.filter((p) => p.survived).map((player) => (
          <button key={player.seat_index} className={player.seat_index === 8 ? 'selected' : ''}>{player.seat_index}</button>
        ))}
        <button>弃票</button>
      </div>
      <button className="primary-action">确认投票</button>
    </section>
  )
}

function SheriffPanel({
  players,
  onClose,
  onSetPhase,
}: {
  players: Player[]
  onClose: () => void
  onSetPhase: (phase: string | null) => void
}) {
  const candidates = players.filter((p) => [1, 4, 7].includes(p.seat_index))
  return (
    <section className="sheriff-stage">
      <header className="sheriff-title">
        <img src={`${A}/icons/status/icon_status_sheriff.png`} alt="" />
        <h1>警长竞选阶段</h1>
        <p>竞选警长可获得1.5票归票权，出局时可指定一名玩家出局。</p>
      </header>
      <button className="drawer-close floating" onClick={onClose}>×</button>
      <div className="sheriff-grid">
        <section className="sheriff-card">
          <h2>竞选报名</h2>
          <p>点击下方按钮报名竞选警长</p>
          <button className="primary-action">我要竞选警长</button>
          <button className="ghost-action">放弃竞选</button>
        </section>
        <section className="sheriff-card">
          <h2>当前竞选者（3/12）</h2>
          <div className="candidate-row">
            {candidates.map((player) => (
              <div key={player.seat_index} className="candidate-avatar">
                <img src={portraitForPlayer(player)} alt="" />
                <b>{player.seat_index}</b>
                <span>玩家{player.seat_index}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
      <section className="speech-order">
        <h3>竞选发言顺序 <span>（按编号升序）</span></h3>
        <div>
          {candidates.map((player, index) => (
            <span key={player.seat_index}>
              <b>{player.seat_index}</b> 玩家{player.seat_index}
              {index < candidates.length - 1 ? <i>→</i> : null}
            </span>
          ))}
        </div>
      </section>
      <section className="sheriff-vote">
        <h3>警下投票</h3>
        <div className="round-vote-row">
          {[1,2,3,4,5,6,7,8,9,10,11,12].map((seat) => (
            <button key={seat} className={seat === 4 || seat === 7 ? 'selected' : ''}>{seat}</button>
          ))}
          <button>弃票</button>
        </div>
        <div className="sheriff-actions">
          <button className="primary-action" onClick={() => onSetPhase('day_speech')}>开始投票<br /><small>倒计时：60s</small></button>
          <button className="ghost-action" onClick={() => onSetPhase('day_speech')}>稍后投票</button>
        </div>
      </section>
    </section>
  )
}

function SkillModal({
  phase,
  players,
  onClose,
  onProtect,
}: {
  phase: string
  players: Player[]
  onClose: () => void
  onProtect: () => void
}) {
  const victim = players.find((p) => p.seat_index === 8)
  const skill = skillForPhase(phase)
  return (
    <section className="skill-backdrop">
      <div className="skill-card">
        <button className="drawer-close floating" onClick={onClose}>×</button>
        <img className="skill-orb" src={skill.icon} alt="" />
        <h2>{skill.title}</h2>
        <p>昨晚 <b>{victim?.seat_index || 8}</b> 号玩家被狼人击杀</p>
        <div className="skill-actions">
          <button className="heal" onClick={onProtect}><img src={`${A}/icons/skills/icon_skill_witch_heal.png`} alt="" />使用解药<br /><span>救8号</span></button>
          <button className="poison" onClick={onProtect}><img src={`${A}/icons/skills/icon_skill_witch_poison.png`} alt="" />使用毒药</button>
          <button className="skip" onClick={onClose}><img src={`${A}/icons/actions/icon_action_close.png`} alt="" />不使用</button>
        </div>
        <p className="skill-hint">每晚只能使用一种药剂，不能自救</p>
        <div className="night-steps">
          <span><img src={`${A}/icons/skills/icon_skill_wolf_kill.png`} alt="" />狼人行动<small>已结束</small></span>
          <span className="active"><img src={`${A}/icons/skills/icon_skill_witch_heal.png`} alt="" />女巫行动<small>进行中</small></span>
          <span><img src={`${A}/icons/skills/icon_skill_seer_check.png`} alt="" />预言家行动<small>即将开始</small></span>
        </div>
      </div>
    </section>
  )
}

function HistoryDrawer({
  tab,
  events,
  players,
  onTab,
  onClose,
}: {
  tab: DrawerTab
  events: GameEvent[]
  players: Player[]
  onTab: (tab: DrawerTab) => void
  onClose: () => void
}) {
  return (
    <aside className="history-drawer">
      <header>
        <h2>历史记录</h2>
        <button className="drawer-close" onClick={onClose}>×</button>
      </header>
      <div className="drawer-tabs">
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => onTab('chat')}>发言记录</button>
        <button className={tab === 'vote' ? 'active' : ''} onClick={() => onTab('vote')}>投票记录</button>
        <button className={tab === 'settle' ? 'active' : ''} onClick={() => onTab('settle')}>结算记录</button>
      </div>
      {tab === 'chat' && (
        <section className="drawer-feed">
          {events
            .filter((ev) => ['public_speech_made', 'sheriff_campaign', 'death_speech'].includes(ev.event_type))
            .slice()
            .reverse()
            .map((ev, index) => {
              const seat = Number(ev.data?.player_id || ev.data?.actor_id || 0)
              const speech = String(ev.data?.public_speech || ev.data?.speech || ev.content || '')
              return (
                <article key={`${ev.event_type}-${index}`} className="record-row">
                  <img src={avatarForSeat(players, seat)} alt="" />
                  <div>
                    <b>{seat ? `${seat}号玩家` : '系统'}</b>
                    <p>{speech}</p>
                  </div>
                  <time>第{ev.round || 1}天</time>
                </article>
              )
            })}
          {events.filter((ev) => ['public_speech_made','sheriff_campaign','death_speech'].includes(ev.event_type)).length === 0 && (
            <div className="drawer-empty">暂无发言记录</div>
          )}
        </section>
      )}
      {tab === 'vote' && <VoteRecords events={events} players={players} />}
      {tab === 'settle' && <SettleRecords events={events} />}
    </aside>
  )
}

interface VoteGroup {
  key: string
  title: string
  result: string
  focus: number | null
  byVoter: Record<number, number | null>
}

function buildVoteGroups(events: GameEvent[]): VoteGroup[] {
  const groups: VoteGroup[] = []
  let current: VoteGroup | null = null
  for (const ev of events) {
    if (ev.event_type === 'phase_started') {
      const phase = ev.data?.phase as string
      const round = typeof ev.round === 'number' ? ev.round : 1
      if (phase === 'sheriff_election') {
        current = { key: `s-${round}`, title: `第 ${round} 天 警长竞选`, result: '竞选中', focus: null, byVoter: {} }
        groups.push(current)
      } else if (phase === 'day_vote') {
        current = { key: `d-${round}`, title: `第 ${round} 天 放逐投票`, result: '投票中', focus: null, byVoter: {} }
        groups.push(current)
      }
    }
    if (!current) continue
    if (ev.event_type === 'vote_cast') {
      const voter = Number(ev.data?.voter_id)
      const target = ev.data?.target_id
      if (Number.isFinite(voter)) current.byVoter[voter] = target == null ? null : Number(target)
    }
    if (ev.event_type === 'sheriff_elected') {
      const sid = Number(ev.data?.player_id ?? ev.data?.target_id)
      if (Number.isFinite(sid)) {
        current.focus = sid
        current.result = `${sid} 号当选警长`
      }
    }
    if (ev.event_type === 'vote_resolved') {
      const chosen = ev.data?.chosen
      if (chosen == null) {
        current.result = '平票，未放逐'
        current.focus = null
      } else {
        current.focus = Number(chosen)
        current.result = `${chosen} 号出局`
      }
    }
  }
  return groups
}

function VoteRecords({ events, players }: { events: GameEvent[]; players: Player[] }) {
  const groups = buildVoteGroups(events)
  if (groups.length === 0) {
    return <section className="vote-records"><div className="drawer-empty">尚无投票记录</div></section>
  }
  const seatList = Array.from({ length: 12 }, (_, i) => i + 1)
  return (
    <section className="vote-records">
      {groups.map((g) => (
        <article key={g.key} className="vote-record-card">
          <header><b>{g.title}</b><span>{g.result}</span></header>
          <div className="vote-grid">
            {seatList.map((seat) => {
              const target = g.byVoter[seat]
              const exiled = g.focus === seat
              const player = players.find((p) => p.seat_index === seat)
              const dead = player && !player.survived
              return (
                <div
                  key={`${g.key}-${seat}`}
                  className={`vote-cell ${exiled ? 'exiled' : ''} ${dead ? 'dead' : ''}`}
                  title={target != null ? `${seat} 号 → ${target} 号` : `${seat} 号 弃票`}
                >
                  <b>{seat}</b>
                  <i>{target != null ? `→ ${target}` : '弃'}</i>
                </div>
              )
            })}
          </div>
        </article>
      ))}
    </section>
  )
}

function SettleRecords({ events }: { events: GameEvent[] }) {
  const rows: Array<{ key: string; round: number; glyph: string; text: string; tone: 'good' | 'bad' | 'neutral' }> = []
  events.forEach((ev, idx) => {
    const round = typeof ev.round === 'number' ? ev.round : 1
    const d = ev.data || {}
    const key = `${idx}-${ev.event_type}`
    switch (ev.event_type) {
      case 'player_died': {
        const cause = d.cause
        const causeText = cause === 'wolf' ? '夜刀' : cause === 'poison' ? '毒杀'
          : cause === 'exile' ? '放逐' : cause === 'hunter' ? '猎人' : cause === 'self_destruct' ? '自爆' : '出局'
        rows.push({ key, round, glyph: '☠', text: `${d.player_id ?? '?'} 号 · ${causeText}`, tone: 'bad' })
        break
      }
      case 'witch_used_antidote':
        rows.push({ key, round, glyph: '🧪', text: `女巫救活 ${d.target_id ?? '?'} 号`, tone: 'good' }); break
      case 'witch_used_poison':
        rows.push({ key, round, glyph: '☠', text: `女巫毒杀 ${d.target_id ?? '?'} 号`, tone: 'bad' }); break
      case 'seer_checked':
        rows.push({
          key, round, glyph: '👁',
          text: `预言家查验 ${d.target_id ?? '?'} 号 → ${d.result === 'wolf' ? '狼人' : '好人'}`,
          tone: d.result === 'wolf' ? 'bad' : 'good',
        }); break
      case 'sheriff_elected':
        rows.push({ key, round, glyph: '★', text: `${d.player_id ?? '?'} 号当选警长`, tone: 'good' }); break
      case 'hunter_shot':
        rows.push({ key, round, glyph: '🏹', text: `猎人开枪 → ${d.target_id ?? '?'} 号`, tone: 'bad' }); break
      case 'wolf_self_destruct':
        rows.push({ key, round, glyph: '💥', text: `${d.player_id ?? '?'} 号狼人自爆`, tone: 'bad' }); break
      case 'vote_resolved':
        rows.push({
          key, round, glyph: '⚖',
          text: d.chosen != null ? `投票结算 · 放逐 ${d.chosen} 号` : '投票结算 · 平票',
          tone: 'neutral',
        }); break
      case 'game_ended':
        rows.push({
          key, round, glyph: '🏁',
          text: `游戏结束 · ${d.winner === 'wolf' ? '狼人阵营' : '好人阵营'}获胜`,
          tone: 'neutral',
        }); break
    }
  })
  if (rows.length === 0) {
    return <section className="settle-records"><div className="drawer-empty">尚无结算记录</div></section>
  }
  return (
    <section className="settle-records">
      {rows.map((r) => (
        <article key={r.key} className={`settle-row tone-${r.tone}`}>
          <span className="g">{r.glyph}</span>
          <p>{r.text}</p>
          <em>第 {r.round} 天</em>
        </article>
      ))}
    </section>
  )
}

function StatusLegend({ onClose }: { onClose: () => void }) {
  return (
    <aside className="status-legend">
      <header>
        <h2>状态图标</h2>
        <button className="drawer-close" onClick={onClose}>×</button>
      </header>
      {STATUS_LEGEND.map(([label, icon]) => (
        <div key={label}>
          <img src={icon} alt="" />
          <span>{label}</span>
        </div>
      ))}
    </aside>
  )
}

function IconButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: string
  label: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button className={`icon-button ${active ? 'active' : ''}`} onClick={onClick}>
      <img src={icon} alt="" />
      <span>{label}</span>
    </button>
  )
}

function DockButton({ icon, label }: { icon: string; label: string }) {
  return (
    <button className="dock-button">
      <img src={icon} alt="" />
      <span>{label}</span>
    </button>
  )
}

function visiblePlayer(player: Player, viewMode: ViewMode, humanSeat: number | null): VisiblePlayer {
  const selfCanSee = viewMode === 'self' && player.seat_index === humanSeat
  const revealAll = viewMode === 'god' || viewMode === 'observer'
  const hidden = !(selfCanSee || revealAll)
  if (hidden) {
    return {
      player,
      meta: ROLE_META.unknown,
      hidden: true,
      portrait: player.seat_index % 3 === 0 ? UNKNOWN_AI : UNKNOWN_CLOAK,
    }
  }
  return {
    player,
    meta: roleMeta(player),
    hidden: false,
    portrait: portraitForPlayer(player),
  }
}

function roleMeta(player: Player): RoleMeta {
  return ROLE_META[player.role] || ROLE_META.villager
}

function portraitForPlayer(player: Player): string {
  if (player.role === 'villager') {
    const extraIndex = (player.seat_index - 1) % EXTRA_PORTRAITS.length
    return EXTRA_PORTRAITS[extraIndex]
  }
  return roleMeta(player).portrait
}

function avatarForSeat(players: Player[], seat: number): string {
  const player = players.find((item) => item.seat_index === seat)
  return player ? portraitForPlayer(player) : UNKNOWN_CLOAK
}

function buildVoteCounts(events: GameEvent[]): Record<number, number> {
  const counts: Record<number, number> = {}
  for (const ev of events) {
    if (ev.event_type !== 'vote_cast') continue
    const target = Number(ev.data?.target_id)
    if (Number.isFinite(target)) counts[target] = (counts[target] || 0) + 1
  }
  return counts
}

function latestSpeaker(events: GameEvent[]): number | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i]
    if (ev.event_type === 'speaking_started' || ev.event_type === 'public_speech_made') {
      const seat = Number(ev.data?.player_id || ev.data?.actor_id)
      return Number.isFinite(seat) ? seat : null
    }
  }
  return null
}

function eventTitle(ev: GameEvent): string {
  const titles: Record<string, string> = {
    phase_started: '阶段开始',
    public_speech_made: '玩家发言',
    sheriff_campaign: '警长竞选',
    vote_cast: '投票',
    vote_resolved: '投票结算',
    seer_checked: '预言家查验',
    wolf_killed: '狼人刀人',
    witch_saved: '女巫救人',
    witch_poisoned: '女巫毒人',
    hunter_shot: '猎人开枪',
  }
  return titles[ev.event_type] || ev.event_type
}

function isSkillPhase(phase: string): boolean {
  return ['night_wolf', 'night_seer', 'night_witch', 'night_guard'].includes(phase)
}

function skillForPhase(phase: string) {
  if (phase === 'night_wolf') {
    return { title: '狼队夜刀目标', icon: `${A}/icons/skills/icon_skill_wolf_kill.png` }
  }
  if (phase === 'night_seer') {
    return { title: '预言家查验', icon: `${A}/icons/skills/icon_skill_seer_check.png` }
  }
  if (phase === 'night_guard') {
    return { title: '守卫行动', icon: `${A}/icons/skills/icon_skill_guard_protect.png` }
  }
  return { title: '女巫请睁眼', icon: `${A}/icons/skills/icon_skill_witch_heal.png` }
}
