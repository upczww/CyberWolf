import { useCallback, useEffect, useMemo, useState } from 'react'
import { useGameStore, type GameEvent, type Player } from './stores/game'
import { useGameWS } from './hooks/useGameWS'
import { apiGet, apiPost } from './hooks/useApi'
import GameAudio from './components/GameAudio'
import GameEffects from './components/GameEffects'
import HumanActionPanel from './components/HumanActionPanel'
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
  seer: { label: '预言家', avatar: '/assets/avatars/seer.png', tone: 'god' },
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

const UNKNOWN_AVATAR = '/assets/ui/cards/unknown_avatar.png'
const ROLE_CARD_BACK = '/assets/ui/cards/role_card_back.png'

type ViewMode = 'god' | 'observer' | 'self'

type PlayerStatus = 'speaking' | 'voted' | 'targeted' | 'saved' | 'waiting' | null

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
    setViewMode,
    setHumanSeat,
    setTtsEnabled,
    reset,
  } = useGameStore()
  const [showMusicStudio, setShowMusicStudio] = useState(false)
  const [showGameList, setShowGameList] = useState(false)

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
      // server still warming up, director shell stays rendered
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

  const handleToggleTts = useCallback(async () => {
    try {
      const res = await apiPost<{ enabled: boolean }>('/api/tts/toggle', {})
      setTtsEnabled(!!res.enabled)
    } catch (error) {
      console.error('TTS toggle failed:', error)
    }
  }, [setTtsEnabled])

  const sortedPlayers = useMemo(() => {
    const bySeat = [...players].sort((a, b) => a.seat_index - b.seat_index)
    const slots: Array<Player | null> = Array.from({ length: 12 }, (_, index) => {
      return bySeat.find((p) => p.seat_index === index + 1) || null
    })
    return slots
  }, [players])

  const voteCounts = useMemo(() => {
    const counts: Record<number, number> = {}
    if (phase !== 'day_vote' && phase !== 'day_resolve') return counts
    for (const ev of events) {
      if (ev.event_type !== 'vote_cast') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const target = Number(ev.data?.target_id)
      if (!Number.isFinite(target)) continue
      counts[target] = (counts[target] || 0) + 1
    }
    return counts
  }, [events, phase, round])

  const meta = phase ? PHASE_META[phase] : null
  const aliveCount = players.filter((p) => p.survived).length
  const deadCount = players.length ? players.length - aliveCount : 0
  const wolvesAlive = players.filter((p) => p.survived && p.faction === 'wolf').length
  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const conversation = useMemo(() => buildConversation(events, humanSeat), [events, humanSeat])
  const judgeEvents = useMemo(() => buildJudgeEvents(events), [events])
  const playerStatuses = useMemo(() => computePlayerStatuses(events, round, phase), [events, round, phase])
  const currentSpeakerId = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type === 'speaking_started') {
        return Number(ev.data?.player_id) || null
      }
      if (ev.event_type === 'public_speech_made' || ev.event_type === 'sheriff_campaign' || ev.event_type === 'death_speech') {
        return null
      }
    }
    return null
  }, [events])
  const waitingActorId = awaitingHuman?.actor_id ?? null
  const avatarOverrides = useMemo(() => computeAvatarOverrides(events), [events])
  const voteTie = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type === 'vote_resolved') {
        return ev.data?.chosen == null && Object.keys(ev.data?.votes || {}).length > 0
      }
      if (ev.event_type === 'phase_started' && ev.data?.phase === 'day_vote') break
    }
    return false
  }, [events])
  const latestSeerCheck = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type === 'seer_checked') return ev
    }
    return null
  }, [events])
  const sceneBgUrl = sceneBackground(phase, winner)

  return (
    <div className="director-app">
      <GameAudio phase={phase} latestEvent={latestEvent} winner={winner} />
      <GameEffects latestEvent={latestEvent} />
      <div className="director-shell">
        <header className="director-topbar">
          <section className="brand-block">
            <img src="/assets/ui/logo.png" alt="" />
            <div>
              <h1>AI 狼人杀{viewMode === 'self' ? '现场' : '导演台'}</h1>
              <p>
                {viewMode === 'god' && '12 名 AI 玩家自动博弈，裁判引擎掌握真实状态'}
                {viewMode === 'observer' && '旁观席：所有身份保密，仅根据公开信息判断'}
                {viewMode === 'self' && `你是 ${humanSeat ?? '?'} 号玩家，其它身份保密`}
              </p>
            </div>
          </section>

          <section
            className={`phase-banner ${awaitingHuman && viewMode === 'self' && awaitingHuman.actor_id === humanSeat ? 'is-your-turn' : ''}`}
            style={{ backgroundImage: `linear-gradient(90deg, rgba(14,10,8,.22), rgba(14,10,8,.42)), url(/assets/ui/phases/${meta?.asset || 'phase_night.png'})` }}
          >
            <span>第 {round || 1} 轮</span>
            <strong>{winner ? `${winner === 'good' ? '好人阵营' : '狼人阵营'}胜利` : meta?.label || '等待开始'}</strong>
            <span>
              {awaitingHuman && viewMode === 'self' && awaitingHuman.actor_id === humanSeat
                ? '⚡ 你的回合'
                : meta?.channel || '导演频道'}
            </span>
          </section>

          <section className="score-grid">
            <Stat label="存活" value={players.length ? aliveCount : 12} />
            <Stat label="出局" value={deadCount} />
            <Stat label="狼队" value={players.length ? (viewMode === 'god' ? wolvesAlive : '?') : 3} />
            <Stat
              label={viewMode === 'self' ? '我的席位' : '当前回合'}
              value={viewMode === 'self' ? (humanSeat ? `${humanSeat}号` : '未选') : round || 1}
            />
          </section>
        </header>

        <main className="director-main">
          <section className="theater-panel">
            <div
              className="scene-bg"
              style={{
                backgroundImage: `linear-gradient(180deg, rgba(8,8,11,.20), rgba(10,6,4,.9)), url(${sceneBgUrl})`,
              }}
            />
            <div className="channel-note">
              <img src="/assets/ui/icons/claw_slash.png" alt="" />
              <span>{channelNote(phase, winner, meta?.channel)}</span>
            </div>

            <div className="seat-rail rail-top" />
            <div className="seat-rail rail-bottom" />
            <div className="table-core">
              <div className="table-art" />
              {phase === 'night_seer' && (
                <img className="table-effect table-eye" src="/assets/ui/effects/seer_eye_glow_overlay.png" alt="" />
              )}
              {phase === 'night_wolf' && (
                <img className="table-effect table-claw" src="/assets/ui/effects/wolf_claw_overlay.png" alt="" />
              )}
              {!winner && gameId && (
                <div className="judge-card">
                  <h2>当前裁判判定</h2>
                  <p>{buildJudgeSummary(phase, events, viewMode)}</p>
                </div>
              )}
            </div>

            {sortedPlayers.map((player, index) => (
              <PlayerCard
                key={player?.player_id || `empty-${index + 1}`}
                player={player}
                seatIndex={index + 1}
                phase={phase}
                viewMode={viewMode}
                humanSeat={humanSeat}
                voteCount={voteCounts[index + 1] || 0}
                playerStatus={playerStatuses[index + 1]}
                seerHint={latestSeerCheck && Number(latestSeerCheck.data?.target_id) === index + 1 ? (latestSeerCheck.data?.result === 'wolf' ? 'wolf' : 'good') : null}
                avatarOverride={avatarOverrides[index + 1]}
                isEndgame={!!winner}
                isCurrentSpeaker={currentSpeakerId === index + 1}
                isWaiting={waitingActorId === index + 1 && humanSeat !== index + 1}
              />
            ))}
            {voteTie && (
              <img className="tie-mark" src="/assets/ui/vote/tie_mark.png" alt="" />
            )}
            {!gameId && (
              <img className="loading-splash" src="/assets/ui/loading_card.png" alt="" />
            )}
          </section>

          <aside className="side-console">
            <section className="console-panel feed-panel parchment-bg">
              <PanelTitle title="AI 对话流" icon="/assets/ui/icons/ballot_vote.png" />
              <div className="message-feed">
                {conversation.map((item, index) => (
                  <article className={`speech-card ${item.isHuman ? 'is-human' : ''}`} key={`${item.title}-${index}`}>
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
                {conversation.length === 0 && (
                  <div className="message-empty">等待 AI 发言⋯</div>
                )}
              </div>
            </section>

            <section className="console-panel parchment-bg">
              <PanelTitle title="裁判日志" icon="/assets/ui/status/waiting.png" />
              <div className="event-list">
                {judgeEvents.map((item, index) => (
                  <div className="event-row" key={`${item.text}-${index}`}>
                    <img src={item.icon} alt="" />
                    <span>{item.text}</span>
                  </div>
                ))}
                {judgeEvents.length === 0 && (
                  <div className="event-empty">尚无裁判事件</div>
                )}
              </div>
            </section>
          </aside>
        </main>

        <Toolbar
          onGameStarted={handleGameStarted}
          onOpenMusic={() => setShowMusicStudio(true)}
          onOpenGameList={() => setShowGameList(true)}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          humanSeat={humanSeat}
          onHumanSeatChange={setHumanSeat}
          ttsEnabled={ttsEnabled}
          onTtsToggle={handleToggleTts}
        />
      </div>

      <div className={`connection-pill ${connected ? 'online' : ''}`}>
        <span />
        {connected ? '实时连接' : status === 'completed' ? '对局完成' : '等待连接'}
      </div>

      {winner && (
        <div className={`endgame-overlay ${winner}`}>
          <img className="defeat-bg" src="/assets/ui/endgame/defeat_overlay.png" alt="" />
          <div className="endgame-stack">
            <h1>{winner === 'wolf' ? '狼人阵营胜利' : '好人阵营胜利'}</h1>
            <img
              className="winner-badge"
              src={`/assets/ui/endgame/${winner === 'wolf' ? 'wolf_victory_badge' : 'good_victory_badge'}.png`}
              alt=""
            />
            <p>第 {round} 轮 · {players.length ? `存活 ${aliveCount} / ${players.length}` : ''}</p>
          </div>
        </div>
      )}

      {showGameList && <GameList onSelect={handleSelectGame} onClose={() => setShowGameList(false)} />}
      {showMusicStudio && <MusicStudio onClose={() => setShowMusicStudio(false)} />}
      {awaitingHuman && gameId && viewMode === 'self' && awaitingHuman.actor_id === humanSeat && (
        <HumanActionPanel request={awaitingHuman} gameId={gameId} players={players} />
      )}
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
  viewMode,
  humanSeat,
  voteCount,
  playerStatus,
  seerHint,
  avatarOverride,
  isEndgame,
  isCurrentSpeaker,
  isWaiting,
}: {
  player: Player | null
  seatIndex: number
  phase: string | null
  viewMode: ViewMode
  humanSeat: number | null
  voteCount: number
  playerStatus: PlayerStatus | undefined
  seerHint: 'wolf' | 'good' | null
  avatarOverride: string | undefined
  isEndgame: boolean
  isCurrentSpeaker: boolean
  isWaiting: boolean
}) {
  const isHuman = humanSeat === seatIndex
  const role = player?.role || 'unknown'
  const alive = player ? !!player.survived : true
  const acting = isActing(player, phase)

  const revealReason = !player
    ? 'unknown'
    : viewMode === 'god'
      ? 'god'
      : !player.survived
        ? 'dead'
        : viewMode === 'self' && isHuman
          ? 'self'
          : null

  const trueMeta = getRoleMeta(player, seatIndex)
  const effectiveAvatar = revealReason && avatarOverride ? avatarOverride : trueMeta.avatar
  const meta = revealReason
    ? { ...trueMeta, avatar: effectiveAvatar }
    : { label: '?', avatar: UNKNOWN_AVATAR, tone: 'good' as const }

  const statusAsset = getStatusAsset(player, acting, playerStatus)
  const aliveStamp = !player
    ? null
    : !alive
      ? '/assets/ui/endgame/dead_mark.png'
      : isEndgame
        ? '/assets/ui/endgame/alive_mark.png'
        : null
  const exileStamp = player && !alive && player.death_cause === 'exile'
  const isAbstain = !!(player && alive && phase === 'day_resolve' && playerStatus !== 'voted')
  const frameAsset = revealReason && player
    ? (player.faction === 'wolf' ? '/assets/ui/frame_wolf.png' : '/assets/ui/frame_good.png')
    : null

  return (
    <article
      className={`player-card seat-${seatIndex} ${acting ? 'is-acting' : ''} ${!alive ? 'is-dead' : ''} ${isHuman ? 'is-human' : ''} ${isCurrentSpeaker ? 'is-speaking' : ''} ${isWaiting ? 'is-waiting' : ''}`}
    >
      <div className={`avatar-frame ${meta.tone}`}>
        <img className="avatar-img" src={meta.avatar} alt="" />
        {!revealReason && player && (
          <img className="role-card-back" src={ROLE_CARD_BACK} alt="" />
        )}
        {frameAsset ? <img className="card-frame" src={frameAsset} alt="" /> : null}
        {player?.is_sheriff ? <img className="sheriff-badge" src="/assets/ui/badge_sheriff.png" alt="" /> : null}
        {statusAsset ? <img className="status-badge" src={statusAsset} alt="" /> : null}
        {aliveStamp ? <img className="alive-stamp" src={aliveStamp} alt="" /> : null}
        {exileStamp ? <img className="exile-stamp" src="/assets/ui/vote/exile_stamp.png" alt="" /> : null}
        {isAbstain ? <img className="abstain-mark" src="/assets/ui/vote/abstain_mark.png" alt="" /> : null}
        {playerStatus === 'voted' ? <img className="vote-arrow" src="/assets/ui/vote/vote_arrow.png" alt="" /> : null}
        {voteCount > 0 && (
          <span className="vote-count">
            <img src="/assets/ui/vote/vote_count_token.png" alt="" />
            <b>{voteCount}</b>
          </span>
        )}
        {seerHint && (
          <img
            className="seer-result"
            src={seerHint === 'wolf' ? '/assets/ui/results/seer_result_wolf.png' : '/assets/ui/results/seer_result_good.png'}
            alt=""
          />
        )}
        <span className={`identity-plate ${meta.tone}`}>{meta.label}</span>
      </div>
      <div className="seat-name">
        {seatIndex}号 {playerName(role, seatIndex)}
        {isHuman ? ' · 你' : ''}
      </div>
      <div className="seat-state">{seatState(player, role, !!revealReason)}</div>
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

function getRoleMeta(player: Player | null, seatIndex: number) {
  if (!player) return { label: '未知', avatar: UNKNOWN_AVATAR, tone: 'good' as const }
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

function channelNote(phase: string | null, winner: string | null, fallback?: string) {
  if (winner) return `${winner === 'wolf' ? '狼人阵营' : '好人阵营'}获胜，公开频道关闭`
  if (!phase) return '等待对局开始'
  if (phase === 'check_win') return '裁判检查胜负条件中'
  if (phase === 'game_over') return '对局结束'
  if (phase === 'pending_skills') return '猎人/白痴技能结算中'
  const channel = fallback || '导演频道'
  return `${channel}，公开频道${isNightPhase(phase) ? '已冻结' : '正在记录'}`
}

function isActing(player: Player | null, phase: string | null) {
  if (!player || !player.survived || !phase) return false
  if (phase === 'night_wolf') return player.faction === 'wolf'
  if (phase === 'night_seer') return player.role === 'seer'
  if (phase === 'night_witch') return player.role === 'witch'
  if (phase === 'pending_skills') return ['hunter', 'idiot'].includes(player.role)
  return false
}

function getStatusAsset(player: Player | null, acting: boolean, status: PlayerStatus | undefined) {
  if (!player) return null
  if (!player.survived) {
    if (player.death_cause === 'exile') return '/assets/ui/status/exiled.png'
    if (player.death_cause === 'poison') return '/assets/ui/status/poisoned.png'
    return '/assets/ui/status/dead.png'
  }
  if (acting) return '/assets/ui/status/selected.png'
  if (status === 'speaking') return '/assets/ui/status/speaking.png'
  if (status === 'voted') return '/assets/ui/status/voted.png'
  if (status === 'targeted') return '/assets/ui/status/targeted.png'
  if (status === 'saved') return '/assets/ui/status/saved.png'
  if (status === 'waiting') return '/assets/ui/status/waiting.png'
  return null
}

function computePlayerStatuses(events: GameEvent[], round: number, phase: string | null): Record<number, PlayerStatus> {
  const result: Record<number, PlayerStatus> = {}
  // Voted: anyone with a vote_cast event in current round
  if (phase === 'day_vote' || phase === 'day_resolve') {
    for (const ev of events) {
      if (ev.event_type !== 'vote_cast') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const voter = Number(ev.data?.voter_id)
      const target = Number(ev.data?.target_id)
      if (Number.isFinite(voter)) result[voter] = 'voted'
      if (Number.isFinite(target) && !result[target]) result[target] = 'targeted'
    }
  }
  // Speaking: latest public_speech_made player
  if (phase === 'day_speech' || phase === 'sheriff_election') {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type === 'public_speech_made' || ev.event_type === 'sheriff_campaign') {
        const p = Number(ev.data?.player_id)
        if (Number.isFinite(p)) result[p] = 'speaking'
        break
      }
    }
  }
  // Witch saved someone — saved icon for that target (visible during witch/night_resolve/day_announce)
  if (phase && (phase.startsWith('night') || phase === 'day_announce')) {
    for (const ev of events) {
      if (ev.event_type !== 'witch_used_antidote') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const target = Number(ev.data?.target_id)
      if (Number.isFinite(target)) result[target] = 'saved'
    }
    for (const ev of events) {
      if (ev.event_type !== 'wolf_target_selected') continue
      if (typeof ev.round === 'number' && ev.round !== round) continue
      const target = Number(ev.data?.target_id)
      if (Number.isFinite(target) && result[target] !== 'saved') result[target] = 'targeted'
    }
  }
  return result
}

function computeAvatarOverrides(events: GameEvent[]): Record<number, string> {
  const result: Record<number, string> = {}
  // hunter_shot: hunter (player_id) → hunter_shooting.png for the rest of the game
  // witch_used_antidote / witch_used_poison: witch (player_id) → witch_antidote/poison.png latest wins
  // idiot_reveal: idiot (target_id from skill_triggered) → idiot_reveal.png
  for (const ev of events) {
    const d = ev.data || {}
    if (ev.event_type === 'hunter_shot' || ev.content === 'event.hunter_shot') {
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

function sceneBackground(phase: string | null, winner: string | null) {
  if (winner === 'wolf') return '/assets/backgrounds/victory_wolf.jpg'
  if (winner === 'good') return '/assets/backgrounds/victory_good.jpg'
  if (!phase) return '/assets/backgrounds/night_village.jpg'
  if (phase === 'night_wolf') return '/assets/backgrounds/night_wolf_pov.jpg'
  if (phase.startsWith('night')) return '/assets/backgrounds/night_village.jpg'
  if (phase === 'day_announce' || phase === 'night_resolve') return '/assets/backgrounds/dawn_transition.jpg'
  if (phase === 'day_vote' || phase === 'day_resolve') return '/assets/backgrounds/day_execution.jpg'
  if (phase === 'day_speech' || phase === 'sheriff_election') return '/assets/backgrounds/day_meeting.jpg'
  return '/assets/backgrounds/night_village.jpg'
}

function playerName(role: string, seatIndex: number) {
  const names = ['墨爪', '星眼', '阿杯', '药婆', '弩手', '麦穗', '黑吻', '铃铛', '灯婆', '老弩', '灰耳', '木匠']
  return names[seatIndex - 1] || (ROLE_META[role]?.label || '玩家')
}

function seatState(player: Player | null, role: string, revealed: boolean) {
  if (!player) return '等待入座'
  if (!player.survived) return player.death_cause === 'exile' ? '已放逐' : '已出局'
  if (player.is_sheriff) return '警长'
  if (!revealed) return '身份保密'
  if (role === 'witch') return '药剂待定'
  if (role === 'hunter') return '可开枪'
  return player.faction === 'wolf' ? '阵营：狼队' : '阵营：好人'
}

function buildJudgeSummary(phase: string | null, events: GameEvent[], viewMode: ViewMode) {
  if (viewMode !== 'god') {
    if (phase === 'day_speech') return '公开频道开放，根据发言自行判断。'
    if (phase === 'day_vote') return '裁判正在收集投票，公开投票顺序可见。'
    if (phase === 'day_announce') return '裁判公布夜晚结算的公开信息。'
    if (phase === 'sheriff_election') return '警长竞选公开进行。'
    if (phase && phase.startsWith('night')) return '夜晚阶段，公开频道关闭。'
    return events.length ? '只能看到公开信息。' : '等待对局开始。'
  }
  if (phase === 'night_wolf') return '狼队正在私聊决策，候选目标已由规则引擎过滤。'
  if (phase === 'night_seer') return '预言家将获得单人查验结果，其他 AI 不会看到私人信息。'
  if (phase === 'night_witch') return '女巫只看到今晚死亡信息，并提交救药或毒药动作。'
  if (phase === 'day_speech') return '公开频道开放，AI 将根据私有记忆和公共发言轮流博弈。'
  if (phase === 'day_vote') return '裁判收集投票，死者和无票权目标会被自动排除。'
  if (events.length) return '裁判引擎维护真实状态，AI 只能提交当前阶段合法动作。'
  return '启动新局后，12 名 AI 会按身份、私有信息和公开记录自动行动。'
}

function buildConversation(events: GameEvent[], humanSeat: number | null) {
  const speechEvents = events.filter((ev) =>
    ['public_speech_made', 'sheriff_campaign', 'death_speech', 'wolf_team_discussion', 'witch_thought', 'seer_thought'].includes(ev.event_type),
  )
  if (!speechEvents.length) return []

  return speechEvents.map((ev) => {
    const playerId = ev.data?.player_id || ev.data?.actor_id || '?'
    const text = ev.data?.speech || ev.data?.message || ev.data?.text || ev.content || '正在发言'
    const scope = ev.scope === 'wolf_team' ? '狼队频道' : ev.scope === 'role_private' ? '私人频道' : '公开频道'
    const isHuman = humanSeat != null && Number(playerId) === humanSeat
    return {
      title: isHuman ? `${playerId}号 · 你` : `${playerId}号`,
      channel: scope,
      avatar: avatarForEventPlayer(playerId),
      text: String(text),
      isHuman,
    }
  })
}

function buildJudgeEvents(events: GameEvent[]) {
  // Show meaningful events only — strip the noisy ones
  const interesting = events.filter((ev) => !['phase_ended', 'speaking_started', 'speech_order_announced', 'awaiting_human', 'human_submitted'].includes(ev.event_type))
  return interesting.slice(-14).map((ev) => {
    const d = ev.data || {}
    const pid = d.player_id ?? d.target_id ?? '?'
    switch (ev.event_type) {
      case 'seer_checked':
        return { icon: '/assets/ui/icons/seer_eye.png', text: `预言家查验 ${d.target_id ?? '?'} 号 → ${d.result === 'wolf' ? '狼人' : '好人'}` }
      case 'witch_used_poison':
        return { icon: '/assets/ui/icons/poison.png', text: `女巫毒杀 ${d.target_id ?? '?'} 号` }
      case 'witch_used_antidote':
        return { icon: '/assets/ui/icons/antidote.png', text: `女巫救活 ${d.target_id ?? '?'} 号` }
      case 'wolf_target_selected':
        return { icon: '/assets/ui/icons/claw_slash.png', text: `狼队选定目标 ${d.target_id ?? '?'} 号` }
      case 'vote_cast':
        return { icon: '/assets/ui/vote/vote_count_token.png', text: `${d.voter_id ?? '?'} 号投票 → ${d.target_id ?? '?'} 号` }
      case 'vote_resolved':
        return { icon: '/assets/ui/vote/exile_stamp.png', text: d.chosen != null ? `投票结果:放逐 ${d.chosen} 号` : '投票结果:平票' }
      case 'player_died': {
        const cause = d.cause === 'wolf' ? '夜刀' : d.cause === 'poison' ? '毒杀' : d.cause === 'exile' ? '放逐' : d.cause === 'hunter' ? '猎人' : d.cause === 'self_destruct' ? '自爆' : d.cause ?? '出局'
        return { icon: '/assets/ui/status/dead.png', text: `${pid} 号出局 · ${cause}` }
      }
      case 'sheriff_elected':
        return { icon: '/assets/ui/icons/sheriff_star.png', text: `${pid} 号当选警长` }
      case 'sheriff_transferred':
        return { icon: '/assets/ui/icons/sheriff_star.png', text: `警徽传交 → ${d.target_id ?? '?'} 号` }
      case 'sheriff_declare':
        return { icon: '/assets/ui/icons/sheriff_star.png', text: `${pid} 号警上发言` }
      case 'sheriff_campaign':
        return { icon: '/assets/ui/icons/sheriff_star.png', text: `${pid} 号竞选警长` }
      case 'sheriff_direction':
        return { icon: '/assets/ui/icons/sheriff_star.png', text: `警长指定发言方向 ${d.direction ?? '?'}` }
      case 'skill_triggered':
        return { icon: '/assets/ui/effects/hunter_bolt_trail_overlay.png', text: `${pid} 号技能触发 (${d.skill ?? '?'})` }
      case 'wolf_self_destruct':
        return { icon: '/assets/ui/icons/self_destruct.png', text: `${pid} 号狼人自爆` }
      case 'hunter_shot':
        return { icon: '/assets/ui/icons/crossbow_bolt.png', text: `猎人开枪 → ${d.target_id ?? '?'} 号` }
      case 'public_speech_made':
        return { icon: '/assets/ui/icons/ballot_vote.png', text: `${pid} 号公开发言` }
      case 'death_speech':
        return { icon: '/assets/ui/icons/ballot_vote.png', text: `${pid} 号遗言` }
      case 'phase_started':
        return { icon: '/assets/ui/status/waiting.png', text: `阶段:${PHASE_META[d.phase]?.label || d.phase || '?'}` }
      case 'game_ended':
        return { icon: '/assets/ui/endgame/dead_mark.png', text: `游戏结束 · ${d.winner === 'wolf' ? '狼人阵营' : '好人阵营'}获胜` }
      case 'error_raised':
        return { icon: '/assets/ui/status/dead.png', text: `引擎错误:${d.error ?? ev.content}` }
      default:
        return { icon: '/assets/ui/status/waiting.png', text: (ev.content || ev.event_type).replace(/^event\./, '') }
    }
  })
}

function avatarForEventPlayer(playerId: number | string) {
  const n = Number(playerId)
  if (!Number.isFinite(n)) return UNKNOWN_AVATAR
  return n % 5 === 0 ? '/assets/avatars/hunter.png'
    : n % 4 === 0 ? '/assets/avatars/witch.png'
      : n % 3 === 0 ? '/assets/avatars/variants/villager_01.png'
        : n % 2 === 0 ? '/assets/avatars/seer_v2.png'
          : '/assets/avatars/variants/wolf_02.png'
}
