import { useCallback, useEffect, useMemo, useState } from 'react'
import { useGameStore, type GameEvent, type Player } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet, apiDelete, apiPost } from './hooks/useApi'
import GameAudio from './components/GameAudio'
import GameEffects from './components/GameEffects'
import HumanActionPanel from './components/HumanActionPanel'
import MusicStudio from './components/MusicStudio'
import GameList from './components/GameList'
import LandingScreen from './components/LandingScreen'
import HistoryDrawer from './components/HistoryDrawer'

// ----------------------------------------------------------------
// Phase / role metadata
// ----------------------------------------------------------------
interface PhaseMeta {
  label: string
  channel: string
  scene: 'day' | 'night' | 'vote' | 'wolf' | 'dawn'
  glyph: string
}

const PHASE_META: Record<string, PhaseMeta> = {
  setup_game: { label: '准备局', channel: '裁判准备', scene: 'night', glyph: '🌙' },
  night_start: { label: '入夜', channel: '夜晚频道', scene: 'night', glyph: '🌙' },
  night_wolf: { label: '狼人行动', channel: '狼队私聊', scene: 'wolf', glyph: '🐺' },
  night_seer: { label: '预言家查验', channel: '私人查验', scene: 'night', glyph: '👁' },
  night_witch: { label: '女巫行动', channel: '私人行动', scene: 'night', glyph: '🧪' },
  night_resolve: { label: '夜晚结算', channel: '裁判结算', scene: 'dawn', glyph: '🌅' },
  day_announce: { label: '天亮公布', channel: '公开频道', scene: 'day', glyph: '☀' },
  sheriff_election: { label: '警长竞选', channel: '公开竞选', scene: 'day', glyph: '★' },
  day_speech: { label: '白天 · 发言', channel: '公开讨论', scene: 'day', glyph: '☀' },
  day_vote: { label: '白天 · 投票', channel: '投票频道', scene: 'vote', glyph: '⚖' },
  day_resolve: { label: '放逐结算', channel: '裁判结算', scene: 'vote', glyph: '⚖' },
  pending_skills: { label: '技能结算', channel: '技能频道', scene: 'dawn', glyph: '✨' },
  check_win: { label: '胜负检查', channel: '裁判检查', scene: 'dawn', glyph: '⚖' },
  game_over: { label: '游戏结束', channel: '结算频道', scene: 'dawn', glyph: '🏁' },
}

const ROLE_AVATAR: Record<string, string> = {
  wolf: '/assets/avatars/wolf.png',
  seer: '/assets/avatars/seer.png',
  witch: '/assets/avatars/witch.png',
  hunter: '/assets/avatars/hunter.png',
  idiot: '/assets/avatars/idiot.png',
  villager: '/assets/avatars/villager.png',
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

const UNKNOWN_AVATAR = '/assets/ui/cards/unknown_avatar.png'

const ROLE_LABELS: Record<string, string> = {
  wolf: '狼人', seer: '预言家', witch: '女巫', hunter: '猎人',
  idiot: '白痴', guard: '守卫', villager: '平民',
}

const PLAYER_NAMES = ['墨爪', '星眼', '阿杯', '药婆', '弩手', '麦穗', '黑吻', '铃铛', '灯婆', '老弩', '灰耳', '木匠']

type ViewMode = 'god' | 'observer' | 'self'

// ----------------------------------------------------------------
// Top-level app
// ----------------------------------------------------------------
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
    setHumanSeat,
    setTtsEnabled,
    reset,
  } = useGameStore()

  const [showMusicStudio, setShowMusicStudio] = useState(false)
  const [showGameList, setShowGameList] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [speechElapsed, setSpeechElapsed] = useState(0)

  useGameWS(gameId, viewMode === 'self' ? humanSeat : null)

  useEffect(() => {
    if (!gameId) return
    loadGameDetail(gameId)
  }, [gameId, humanSeat])

  useEffect(() => {
    apiGet<{ enabled: boolean }>('/api/tts/status')
      .then((res) => setTtsEnabled(!!res.enabled))
      .catch(() => undefined)
  }, [setTtsEnabled])

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
      // server still warming up
    }
  }

  // Reset speech timer when speaker changes
  useEffect(() => {
    setSpeechElapsed(0)
    if (phase !== 'day_speech' && phase !== 'sheriff_election') return
    const id = setInterval(() => setSpeechElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [phase, events.length])

  const handleGameStarted = useCallback((newGameId: string) => {
    reset()
    setGameId(newGameId)
  }, [reset, setGameId])

  const handleSelectGame = useCallback((gid: string) => {
    reset()
    setGameId(gid)
  }, [reset, setGameId])

  const handleExit = useCallback(() => {
    reset()
  }, [reset])

  const handleToggleTts = useCallback(async () => {
    try {
      const res = await apiPost<{ enabled: boolean }>('/api/tts/toggle', {})
      setTtsEnabled(!!res.enabled)
    } catch (error) {
      console.error('TTS toggle failed:', error)
    }
  }, [setTtsEnabled])

  const handleDeleteGame = useCallback(async () => {
    if (!gameId) return
    if (!confirm('确定删除当前对局？')) return
    await apiDelete(`/api/games/${gameId}`)
    reset()
  }, [gameId, reset])

  const sortedPlayers = useMemo(() => {
    const bySeat = [...players].sort((a, b) => a.seat_index - b.seat_index)
    return Array.from({ length: 12 }, (_, index) =>
      bySeat.find((p) => p.seat_index === index + 1) || null,
    )
  }, [players])

  const voteCounts = useMemo(() => {
    const counts: Record<number, number> = {}
    if (phase !== 'day_vote' && phase !== 'day_resolve' && phase !== 'sheriff_election') return counts
    for (const ev of events) {
      if (ev.event_type !== 'vote_cast') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const target = Number(ev.data?.target_id)
      if (!Number.isFinite(target)) continue
      counts[target] = (counts[target] || 0) + 1
    }
    return counts
  }, [events, phase, round])

  const playerStatuses = useMemo(() => computePlayerStatuses(events, round, phase), [events, round, phase])
  const avatarOverrides = useMemo(() => computeAvatarOverrides(events), [events])

  const currentSpeaker = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type === 'speaking_started') return Number(ev.data?.player_id) || null
      if (ev.event_type === 'public_speech_made' || ev.event_type === 'sheriff_campaign' || ev.event_type === 'death_speech') return null
    }
    return null
  }, [events])

  // -------- Landing screen --------
  if (!gameId) {
    return (
      <div className="app-root">
        <GameAudio phase={null} latestEvent={null} winner={null} />
        <LandingScreen
          onGameStarted={handleGameStarted}
          onOpenGameList={() => setShowGameList(true)}
          onOpenMusic={() => setShowMusicStudio(true)}
        />
        {showGameList && <GameList onSelect={handleSelectGame} onClose={() => setShowGameList(false)} />}
        {showMusicStudio && <MusicStudio onClose={() => setShowMusicStudio(false)} />}
        <ConnectionPill connected={connected} status={status} />
      </div>
    )
  }

  // -------- In-game --------
  const meta = phase ? PHASE_META[phase] : null
  const sceneClass = winner === 'good' ? 'phase-victory-good'
    : winner === 'wolf' ? 'phase-victory-wolf'
    : meta?.scene === 'day' ? 'phase-day'
    : meta?.scene === 'vote' ? 'phase-vote'
    : meta?.scene === 'wolf' ? 'phase-wolf'
    : ''
  const isNight = !!phase && phase.startsWith('night')
  const dayLabel = `第 ${round || 1} 天 · ${isNight ? '夜晚' : '白天'}`
  const phaseGlyph = meta?.glyph || (isNight ? '🌙' : '☀')
  const speechBudget = (phase === 'day_speech' || phase === 'sheriff_election') ? 60 : 0
  const speechRemaining = Math.max(0, speechBudget - speechElapsed)
  const speechProgress = speechBudget > 0 ? Math.min(1, speechElapsed / speechBudget) : 0
  const latestEvent = events.length > 0 ? events[events.length - 1] : null

  const leftSeats = sortedPlayers.slice(0, 6)
  const rightSeats = sortedPlayers.slice(6, 12)
  const latestSeerCheck = findLatestSeerCheck(events)
  const waitingActorId = awaitingHuman?.actor_id ?? null

  return (
    <div className="app-root">
      <GameAudio phase={phase} latestEvent={latestEvent} winner={winner} />
      <GameEffects latestEvent={latestEvent} />

      <div className="game-shell">
        <header className="game-topbar">
          <div className="game-topbar-left">
            <span className="id-chip">房间 {gameId.slice(0, 6)}</span>
            <span className="config-chip">12 人标准版</span>
            {viewMode === 'self' && humanSeat != null && (
              <span className="id-chip" style={{ color: 'var(--good-100)', borderColor: 'rgba(155,210,163,0.5)' }}>
                你 · {humanSeat} 号
              </span>
            )}
            {viewMode === 'god' && <span className="id-chip" style={{ color: 'var(--gold-100)', borderColor: 'rgba(213,175,99,0.5)' }}>上帝视角</span>}
          </div>

          <div className={`phase-pill ${isNight ? 'is-night' : ''}`}>
            <span className="phase-icon">{phaseGlyph}</span>
            {winner ? `${winner === 'good' ? '好人阵营' : '狼人阵营'}胜利` : (meta?.label || dayLabel)}
            {speechBudget > 0 && phase === 'day_speech' && (
              <span className="phase-time">{speechRemaining}s</span>
            )}
          </div>

          <div className="game-topbar-right">
            <button className="topbar-tool" onClick={() => setShowHistory(true)} title="历史记录">
              <span className="ico">📜</span>
              历史
            </button>
            <button className="topbar-tool" onClick={() => setShowGameList(true)} title="对局记录">
              <span className="ico">📚</span>
              记录
            </button>
            <button
              className={`topbar-tool ${ttsEnabled ? 'active' : ''}`}
              onClick={handleToggleTts}
              title="语音"
              style={{ display: 'none' }}
            >
              <span className="ico">{ttsEnabled ? '🔊' : '🔇'}</span>
              语音
            </button>
            <button className="topbar-tool" onClick={() => setShowMusicStudio(true)} title="设置">
              <span className="ico">⚙</span>
              设置
            </button>
          </div>
        </header>

        <main className="game-main">
          <aside className="player-rail">
            {leftSeats.map((p, i) => (
              <PlayerChip
                key={`L-${i + 1}`}
                seatIndex={i + 1}
                player={p}
                phase={phase}
                viewMode={viewMode}
                humanSeat={humanSeat}
                voteCount={voteCounts[i + 1] || 0}
                status={playerStatuses[i + 1]}
                avatarOverride={avatarOverrides[i + 1]}
                isSpeaking={currentSpeaker === i + 1}
                isWaiting={waitingActorId === i + 1 && humanSeat !== i + 1}
                seerHint={latestSeerCheck && Number(latestSeerCheck.data?.target_id) === i + 1
                  ? (latestSeerCheck.data?.result === 'wolf' ? 'wolf' : 'good')
                  : null}
              />
            ))}
          </aside>

          <section className={`stage ${sceneClass}`}>
            <div className="stage-timer-pill">
              <span>{dayLabel.split('·')[0].trim()}</span>
              <span style={{ color: 'var(--text-300)' }}>·</span>
              <span>{isNight ? '夜晚' : '白天'}</span>
            </div>

            <div className="stage-content">
              {currentSpeaker != null && (
                <SpeakerCard
                  seat={currentSpeaker}
                  remaining={speechRemaining}
                  progress={speechProgress}
                />
              )}
              {!currentSpeaker && phase && !winner && (
                <SpeakerCard
                  seat={null}
                  phaseLabel={meta?.label || dayLabel}
                  remaining={speechRemaining}
                  progress={speechProgress}
                />
              )}

              <PhaseTabs phase={phase} />

              <StageInfo
                phase={phase}
                round={round}
                events={events}
                players={players}
                viewMode={viewMode}
                winner={winner}
              />

              <div className="stage-spacer" />

              <div className="stage-actions">
                <button className="stage-btn ghost" onClick={handleExit}>退出对局</button>
                {phase === 'day_vote' && (
                  <button className="stage-btn primary" disabled>裁判收票中</button>
                )}
                {phase === 'day_speech' && (
                  <button className="stage-btn primary" disabled>{currentSpeaker ? `${currentSpeaker}号 发言中` : '等待发言'}</button>
                )}
                {phase === 'sheriff_election' && (
                  <button className="stage-btn primary" disabled>警长竞选中</button>
                )}
                {phase && (phase.startsWith('night') || phase === 'night_resolve') && (
                  <button className="stage-btn primary" disabled>夜晚结算中</button>
                )}
                {!phase && (
                  <button className="stage-btn primary" disabled>对局准备中</button>
                )}
              </div>

              <div className="stage-mini-actions">
                <button className="mini-action" onClick={() => setShowHistory(true)}>
                  <span className="ico">💬</span>
                  聊天
                </button>
                <button className="mini-action" onClick={handleDeleteGame}>
                  <span className="ico">🚪</span>
                  退出
                </button>
              </div>
            </div>
          </section>

          <aside className="player-rail">
            {rightSeats.map((p, i) => (
              <PlayerChip
                key={`R-${i + 7}`}
                seatIndex={i + 7}
                player={p}
                phase={phase}
                viewMode={viewMode}
                humanSeat={humanSeat}
                voteCount={voteCounts[i + 7] || 0}
                status={playerStatuses[i + 7]}
                avatarOverride={avatarOverrides[i + 7]}
                isSpeaking={currentSpeaker === i + 7}
                isWaiting={waitingActorId === i + 7 && humanSeat !== i + 7}
                seerHint={latestSeerCheck && Number(latestSeerCheck.data?.target_id) === i + 7
                  ? (latestSeerCheck.data?.result === 'wolf' ? 'wolf' : 'good')
                  : null}
              />
            ))}
          </aside>
        </main>
      </div>

      <ConnectionPill connected={connected} status={status} />

      {winner && (
        <div className={`endgame-overlay ${winner}`}>
          <div className="endgame-stack">
            <h1>{winner === 'wolf' ? '狼人阵营胜利' : '好人阵营胜利'}</h1>
            <img
              src={`/assets/ui/endgame/${winner === 'wolf' ? 'wolf_victory_badge' : 'good_victory_badge'}.png`}
              alt=""
            />
            <p>第 {round} 天 · 存活 {players.filter(p => p.survived).length} / {players.length}</p>
          </div>
        </div>
      )}

      {showHistory && (
        <HistoryDrawer
          events={events}
          players={players}
          humanSeat={humanSeat}
          onClose={() => setShowHistory(false)}
        />
      )}

      {showGameList && <GameList onSelect={handleSelectGame} onClose={() => setShowGameList(false)} />}
      {showMusicStudio && <MusicStudio onClose={() => setShowMusicStudio(false)} />}

      {awaitingHuman && gameId && viewMode === 'self' && awaitingHuman.actor_id === humanSeat && (
        <HumanActionPanel request={awaitingHuman} gameId={gameId} players={players} />
      )}
    </div>
  )
}

// ----------------------------------------------------------------
// Pieces
// ----------------------------------------------------------------

function ConnectionPill({ connected, status }: { connected: boolean; status: string | null }) {
  return (
    <div className={`connection-pill ${connected ? 'online' : ''}`}>
      <span />
      {connected ? '实时连接' : status === 'completed' ? '对局完成' : '等待连接'}
    </div>
  )
}

interface PlayerChipProps {
  seatIndex: number
  player: Player | null
  phase: string | null
  viewMode: ViewMode
  humanSeat: number | null
  voteCount: number
  status: PlayerStatus
  avatarOverride: string | undefined
  isSpeaking: boolean
  isWaiting: boolean
  seerHint: 'wolf' | 'good' | null
}

type PlayerStatus = 'speaking' | 'voted' | 'targeted' | 'saved' | 'waiting' | 'poisoned' | null | undefined

function PlayerChip({
  seatIndex,
  player,
  phase,
  viewMode,
  humanSeat,
  voteCount,
  status,
  avatarOverride,
  isSpeaking,
  isWaiting,
  seerHint,
}: PlayerChipProps) {
  const isHuman = humanSeat === seatIndex
  const alive = player ? !!player.survived : true
  const acting = isActing(player, phase)

  const revealReason: string | null = !player
    ? 'unknown'
    : viewMode === 'god'
      ? 'god'
      : !player.survived
        ? 'dead'
        : viewMode === 'self' && isHuman
          ? 'self'
          : null

  const trueMeta = getRoleMeta(player, seatIndex)
  const portrait = revealReason ? (avatarOverride || trueMeta.avatar) : UNKNOWN_AVATAR
  const roleLabel = revealReason ? trueMeta.label : '?'
  const name = PLAYER_NAMES[seatIndex - 1] || '玩家'

  return (
    <article
      className={`player-chip ${isSpeaking ? 'is-speaking' : ''} ${isWaiting ? 'is-speaking' : ''} ${acting ? 'is-acting' : ''} ${!alive ? 'is-dead' : ''} ${isHuman ? 'is-human' : ''}`}
    >
      <span className="seat-num">{seatIndex}</span>
      <div className="chip-body">
        <div className="portrait">
          <img src={portrait} alt="" />
        </div>
        <div className="chip-text">
          <div className="role">{revealReason ? roleLabel : '??'}</div>
          <div className="name">玩家{seatIndex < 10 ? `0${seatIndex}` : seatIndex}</div>
        </div>
      </div>
      <div className="status-icons">
        {player?.is_sheriff ? <span className="ico sheriff" title="警长">★</span> : null}
        {status === 'targeted' ? <span className="ico target" title="被指认">!</span> : null}
        {status === 'saved' ? <span className="ico save" title="被救">+</span> : null}
        {status === 'poisoned' ? <span className="ico poison" title="中毒">☠</span> : null}
        {status === 'voted' ? <span className="ico vote" title="已投票">✓</span> : null}
        {seerHint === 'wolf' && <span className="ico target" title="预言家：狼">狼</span>}
        {seerHint === 'good' && <span className="ico save" title="预言家：好人">良</span>}
      </div>
      {voteCount > 0 && <span className="vote-tally">{voteCount}</span>}
    </article>
  )
}

function SpeakerCard({
  seat,
  phaseLabel,
  remaining,
  progress,
}: {
  seat: number | null
  phaseLabel?: string
  remaining: number
  progress: number
}) {
  return (
    <div className="speaker-card">
      {seat != null && <div className="seat-circle">{seat}</div>}
      <div className="speaker-title">
        {seat != null ? <><em>{seat}</em> 号玩家发言中</> : (phaseLabel || '阶段进行中')}
      </div>
      {remaining > 0 && (
        <>
          <div className="speech-bar"><span style={{ transform: `scaleX(${Math.max(0, 1 - progress)})` }} /></div>
          <div className="speech-timer">{remaining}s</div>
        </>
      )}
    </div>
  )
}

function PhaseTabs({ phase }: { phase: string | null }) {
  const tabs: Array<{ key: string; label: string; glyph: string; phases: string[] }> = [
    { key: 'sheriff', label: '警长竞选', glyph: '★', phases: ['sheriff_election'] },
    { key: 'speech', label: '发言阶段', glyph: '🗣', phases: ['day_speech'] },
    { key: 'vote', label: '投票阶段', glyph: '⚖', phases: ['day_vote', 'day_resolve'] },
    { key: 'night', label: '夜晚阶段', glyph: '🌙', phases: ['night_start', 'night_wolf', 'night_seer', 'night_witch', 'night_resolve', 'day_announce'] },
  ]
  const activeIdx = tabs.findIndex((t) => phase && t.phases.includes(phase))
  return (
    <div className="phase-tabs">
      {tabs.map((t, i) => (
        <div
          key={t.key}
          className={`phase-tab ${i === activeIdx ? 'is-active' : i < activeIdx && activeIdx >= 0 ? 'is-done' : ''}`}
        >
          <span className="ico">{t.glyph}</span>
          {t.label}
        </div>
      ))}
    </div>
  )
}

function StageInfo({
  phase,
  round,
  events,
  players,
  viewMode,
  winner,
}: {
  phase: string | null
  round: number
  events: GameEvent[]
  players: Player[]
  viewMode: ViewMode
  winner: string | null
}) {
  const lines: string[] = []

  if (winner) {
    lines.push(winner === 'wolf' ? '· 狼人阵营达成胜利条件' : '· 好人阵营达成胜利条件')
  } else if (phase === 'day_announce') {
    const deaths = events.filter(e => e.event_type === 'player_died' && (e.data?.cause === 'wolf' || e.data?.cause === 'poison') && e.round === round)
    if (deaths.length === 0) lines.push('· 昨晚平安夜，无人出局')
    else deaths.forEach(d => lines.push(`· ${d.data?.player_id ?? '?'} 号玩家昨晚遇害`))
  } else if (phase === 'day_speech') {
    lines.push('· 公开发言频道开启，按顺位轮流陈述')
    const aliveCount = players.filter(p => p.survived).length
    const wolfAlive = players.filter(p => p.survived && p.faction === 'wolf').length
    lines.push(`· 当前存活：${aliveCount} 人，${viewMode === 'god' ? `狼队 ${wolfAlive} 人` : '阵营人数保密'}`)
  } else if (phase === 'day_vote') {
    lines.push('· 公开投票阶段，无投票权者自动弃票')
    lines.push('· 平票将进入加赛或宿命之夜')
  } else if (phase === 'sheriff_election') {
    lines.push('· 警长发言权重 1.5 倍，死亡可传警徽')
    lines.push('· 仅参选玩家进入发言序列')
  } else if (phase === 'night_wolf') {
    lines.push('· 狼队商议夜刀目标')
  } else if (phase === 'night_seer') {
    lines.push('· 预言家正在查验')
  } else if (phase === 'night_witch') {
    lines.push('· 女巫正在抉择解药与毒药')
  } else if (phase && phase.startsWith('night')) {
    lines.push('· 夜幕降临，公开频道暂时关闭')
  } else {
    lines.push('· 对局即将开始')
  }

  return (
    <div className="stage-info">
      {lines.map((l, i) => <span className="line" key={i}>{l}</span>)}
    </div>
  )
}

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

function getRoleMeta(player: Player | null, seatIndex: number): { label: string; avatar: string } {
  if (!player) return { label: '?', avatar: UNKNOWN_AVATAR }
  if (player.faction === 'wolf') {
    return { label: '狼人', avatar: WOLF_VARIANTS[(seatIndex - 1) % WOLF_VARIANTS.length] }
  }
  if (player.role === 'villager') {
    return { label: '平民', avatar: VILLAGER_VARIANTS[(seatIndex - 1) % VILLAGER_VARIANTS.length] }
  }
  return { label: ROLE_LABELS[player.role] || '玩家', avatar: ROLE_AVATAR[player.role] || UNKNOWN_AVATAR }
}

function isActing(player: Player | null, phase: string | null): boolean {
  if (!player || !player.survived || !phase) return false
  if (phase === 'night_wolf') return player.faction === 'wolf'
  if (phase === 'night_seer') return player.role === 'seer'
  if (phase === 'night_witch') return player.role === 'witch'
  if (phase === 'pending_skills') return ['hunter', 'idiot'].includes(player.role)
  return false
}

function findLatestSeerCheck(events: GameEvent[]): GameEvent | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].event_type === 'seer_checked') return events[i]
  }
  return null
}

function computePlayerStatuses(events: GameEvent[], round: number, phase: string | null): Record<number, PlayerStatus> {
  const result: Record<number, PlayerStatus> = {}
  if (phase === 'day_vote' || phase === 'day_resolve' || phase === 'sheriff_election') {
    for (const ev of events) {
      if (ev.event_type !== 'vote_cast') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const voter = Number(ev.data?.voter_id)
      const target = Number(ev.data?.target_id)
      if (Number.isFinite(voter)) result[voter] = 'voted'
      if (Number.isFinite(target) && !result[target]) result[target] = 'targeted'
    }
  }
  if (phase && (phase.startsWith('night') || phase === 'day_announce')) {
    for (const ev of events) {
      if (ev.event_type === 'witch_used_antidote' && ev.round === round) {
        const t = Number(ev.data?.target_id)
        if (Number.isFinite(t)) result[t] = 'saved'
      }
      if (ev.event_type === 'witch_used_poison' && ev.round === round) {
        const t = Number(ev.data?.target_id)
        if (Number.isFinite(t)) result[t] = 'poisoned'
      }
      if (ev.event_type === 'wolf_target_selected' && ev.round === round) {
        const t = Number(ev.data?.target_id)
        if (Number.isFinite(t) && result[t] !== 'saved') result[t] = 'targeted'
      }
    }
  }
  return result
}

function computeAvatarOverrides(events: GameEvent[]): Record<number, string> {
  const result: Record<number, string> = {}
  for (const ev of events) {
    const d = ev.data || {}
    if (ev.event_type === 'hunter_shot') {
      const p = Number(d.player_id)
      if (Number.isFinite(p)) result[p] = '/assets/avatars/hunter_shooting.png'
    } else if (ev.event_type === 'seer_checked') {
      const p = Number(d.player_id)
      if (Number.isFinite(p)) result[p] = '/assets/avatars/seer_v2.png'
    } else if (ev.event_type === 'witch_used_antidote') {
      const p = Number(d.player_id)
      if (Number.isFinite(p)) result[p] = '/assets/avatars/witch_antidote.png'
    } else if (ev.event_type === 'witch_used_poison') {
      const p = Number(d.player_id)
      if (Number.isFinite(p)) result[p] = '/assets/avatars/witch_poison.png'
    } else if (ev.event_type === 'skill_triggered' && (d.skill === 'idiot_reveal' || d.role === 'idiot')) {
      const p = Number(d.player_id ?? d.target_id)
      if (Number.isFinite(p)) result[p] = '/assets/avatars/idiot_reveal.png'
    }
  }
  return result
}
