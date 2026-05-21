import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import GameAudio from './components/GameAudio'
import GameEffects from './components/GameEffects'
import GameProgress from './components/GameProgress'
import HumanActionPanel from './components/HumanActionPanel'
import IdentityReveal, { hasSeenIdentityReveal } from './components/IdentityReveal'
import LobbyRoom from './components/LobbyRoom'
import { apiDelete, apiGet, apiPost } from './hooks/useApi'
import { useGameWS } from './hooks/useGameWS'
import type { RoomLite } from './hooks/useRoomWS'
import {
  clearInviteFromUrl, defaultNicknameFor, getNickname, getOrCreateUserId,
  readInviteFromUrl, setNickname as persistNickname,
} from './lib/identity'
import { UNKNOWN_CLOAK, portraitForPlayer, unknownPortraitForSeat } from './lib/portraits'
import { useGameStore, type GameEvent, type Player } from './stores/game'

type ViewMode = 'god' | 'observer' | 'self'
type PhaseTone = 'day' | 'night' | 'vote' | 'skill' | 'result'
type RoleTone = 'good' | 'god' | 'wolf' | 'neutral' | 'unknown'
type DrawerTab = 'chat' | 'vote' | 'settle'

interface RoleMeta {
  label: string
  camp: string
  tone: RoleTone
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
const AUDIO_PREF_KEY = 'lycan.audio.enabled'

const ROLE_META: Record<string, RoleMeta> = {
  villager: {
    label: '平民',
    camp: '好人阵营',
    tone: 'good',
    icon: `${A}/icons/roles/icon_role_villager.png`,
  },
  wolf: {
    label: '狼人',
    camp: '狼人阵营',
    tone: 'wolf',
    icon: `${A}/icons/roles/icon_role_werewolf.png`,
  },
  werewolf: {
    label: '狼人',
    camp: '狼人阵营',
    tone: 'wolf',
    icon: `${A}/icons/roles/icon_role_werewolf.png`,
  },
  seer: {
    label: '预言家',
    camp: '神职',
    tone: 'god',
    icon: `${A}/icons/roles/icon_role_seer.png`,
  },
  witch: {
    label: '女巫',
    camp: '神职',
    tone: 'god',
    icon: `${A}/icons/roles/icon_role_witch.png`,
  },
  hunter: {
    label: '猎人',
    camp: '神职',
    tone: 'god',
    icon: `${A}/icons/roles/icon_role_hunter.png`,
  },
  idiot: {
    label: '白痴',
    camp: '神职',
    tone: 'god',
    icon: `${A}/icons/roles/icon_role_idiot.png`,
  },
  guard: {
    label: '守卫',
    camp: '神职',
    tone: 'god',
    icon: `${A}/icons/roles/icon_role_guard.png`,
  },
  unknown: {
    label: '未知',
    camp: '身份未公开',
    tone: 'unknown',
    icon: `${A}/icons/status/icon_status_identity_hidden.png`,
  },
}

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
  setup_game: {
    label: '准备开局',
    shortLabel: '准备',
    tone: 'night',
    icon: `${A}/icons/actions/icon_landing_ai_autoplay.png`,
    background: `${A}/backgrounds/bg_global_moonlit_village_night.png`,
    actionLabel: '对局准备中…',
  },
  night_start: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '夜幕降临',
    tone: 'night',
    icon: `${A}/icons/actions/icon_landing_ai_autoplay.png`,
    background: `${A}/backgrounds/bg_phase_night_overview.png`,
    actionLabel: '天黑请闭眼',
  },
  night_resolve: {
    label: '第 1 夜 · 夜晚',
    shortLabel: '夜晚结算',
    tone: 'night',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_phase_night_overview.png`,
    actionLabel: '裁判结算夜晚行动',
  },
  day_announce: {
    label: '第 1 天 · 白天',
    shortLabel: '天亮公布',
    tone: 'day',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_global_moonlit_village_day.png`,
    actionLabel: '裁判正在公布昨夜结果',
  },
  day_resolve: {
    label: '第 1 天 · 白天',
    shortLabel: '投票结算',
    tone: 'vote',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_phase_exile_result.png`,
    actionLabel: '裁判结算投票',
  },
  pending_skills: {
    label: '技能结算',
    shortLabel: '技能结算',
    tone: 'skill',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_phase_hunter_action.png`,
    actionLabel: '号玩家发动技能',
  },
  check_win: {
    label: '胜负检查',
    shortLabel: '胜负检查',
    tone: 'result',
    icon: `${A}/icons/actions/icon_match_summary.png`,
    background: `${A}/backgrounds/bg_global_result_hall.png`,
    actionLabel: '裁判判定胜负',
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

const STATUS_LEGEND = [
  ['警长', `${A}/icons/status/icon_status_sheriff.png`],
  ['被刀', `${A}/icons/skills/icon_skill_wolf_kill.png`],
  ['被驱逐', `${A}/icons/status/icon_status_exiled.png`],
  ['被毒死', `${A}/icons/skills/icon_skill_witch_poison.png`],
  ['被救', `${A}/icons/status/icon_status_guarded.png`],
  ['死亡', `${A}/icons/status/icon_status_dead.png`],
  ['被猎人射中', `${A}/icons/skills/icon_hunter_target.png`],
] as const

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
  const [legendOpen, setLegendOpen] = useState(false)
  const [landingMode, setLandingMode] = useState<ViewMode>('self')
  // Multi-human lobby state. `room` non-null means we're in the lobby
  // pre-game screen; once the host starts, we transition to the normal
  // game UI (gameId set, room cleared).
  const [room, setRoom] = useState<RoomLite | null>(null)
  const [lobbyError, setLobbyError] = useState<string | null>(null)
  const userIdRef = useRef<string>('')
  if (!userIdRef.current) userIdRef.current = getOrCreateUserId()
  const [loadingStart, setLoadingStart] = useState(false)
  const startingRef = useRef(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [identityRevealed, setIdentityRevealed] = useState(false)

  useGameWS(gameId, viewMode === 'self' ? humanSeat : null)

  useEffect(() => {
    if (!gameId || gameId === 'demo') return
    loadGameDetail(gameId)
  }, [gameId, humanSeat, viewMode])

  useEffect(() => {
    const saved = window.localStorage.getItem(AUDIO_PREF_KEY)
    if (saved != null) setTtsEnabled(saved === 'true')
  }, [setTtsEnabled])

  // Identity reveal lifecycle: reset flag whenever a new game starts.
  useEffect(() => {
    if (!gameId) {
      setIdentityRevealed(false)
      return
    }
    setIdentityRevealed(hasSeenIdentityReveal(gameId))
  }, [gameId])

  // All game state below is driven by the backend — no client-side
  // simulation. If the API hasn't filled the store yet we render with
  // safe empty defaults until phase_started / WS events arrive.
  const visiblePhase = phase || 'setup_game'
  const meta = PHASE_META[visiblePhase] || PHASE_META.day_speech
  const latestEvent = events[events.length - 1] || null
  const voteCounts = useMemo(() => buildVoteCounts(events), [events])
  // Tools whose awaiter should NOT promote the actor to "current
  // speaker" — these are silent backend prompts (candidacy yes/no,
  // identity confirmation, private night actions). The player rail
  // highlight should only follow real speech / vote turns.
  const silentAwaiterTools = new Set([
    'sheriff_candidacy',
    'confirm_identity',
    'witch_antidote',
    'witch_poison',
    'seer_check',
    'wolf_kill_proposal',
    'guard_protect',
    'hunter_shoot',
  ])
  const awaitingForHighlight = awaitingHuman && !silentAwaiterTools.has(awaitingHuman.tool_name)
    ? awaitingHuman.actor_id
    : null
  const currentSpeaker = latestSpeaker(events) || awaitingForHighlight || humanSeat || 0
  const roomId = gameId ? gameId.slice(0, 6) : '------'

  // Derive current sheriff seat from events. loadGameDetail only runs
  // once at game start, so the player snapshot's is_sheriff flag is
  // stale by the time sheriff_elected fires via WS — overlay it from
  // events so the badge shows up live (and follows transfers).
  const sheriffSeat = useMemo<number | null>(() => {
    let current: number | null = null
    for (const ev of events) {
      if (ev.event_type === 'sheriff_elected') {
        const pid = ev.data?.player_id
        current = pid == null ? null : Number(pid)
      } else if (ev.event_type === 'sheriff_transferred') {
        const pid = ev.data?.target_id ?? ev.data?.player_id
        current = pid == null ? null : Number(pid)
      }
    }
    return current
  }, [events])

  const playersWithSheriff = useMemo<Player[]>(() => {
    if (sheriffSeat == null) return players
    return players.map((p) => ({
      ...p,
      is_sheriff: p.seat_index === sheriffSeat ? 1 : 0,
    }))
  }, [players, sheriffSeat])

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
      setStartError('Backend service is unavailable; the current game could not load.')
    }
  }

  const startGame = async (useLlm: boolean, mode: ViewMode = landingMode) => {
    if (startingRef.current) return
    startingRef.current = true
    setStartError(null)
    setLoadingStart(true)
    setViewMode(mode)
    setHumanSeat(null)
    try {
      const payload: Record<string, unknown> = { config_id: '12p_pre_witch_hunter_idiot', use_llm: useLlm }
      if (mode === 'self') payload.human_join = true
      const res = await apiPost<{ game_id: string; human_seat?: number | null }>('/api/games/start', payload)
      reset()
      setViewMode(mode)
      setHumanSeat(mode === 'self' && typeof res.human_seat === 'number' ? res.human_seat : null)
      setGameId(res.game_id)
    } catch {
      setStartError('Backend service is unavailable; the real game could not start.')
      reset()
    } finally {
      setLoadingStart(false)
      startingRef.current = false
    }
  }

  const toggleTts = () => {
    const enabled = !ttsEnabled
    setTtsEnabled(enabled)
    window.localStorage.setItem(AUDIO_PREF_KEY, String(enabled))
  }

  const resetToLanding = () => {
    reset()
    setHistoryOpen(false)
    setLegendOpen(false)
    setRoom(null)
    setLobbyError(null)
  }

  /** Prompt for a nickname (uses saved one if available) and persist it. */
  const ensureNickname = (): string | null => {
    const saved = getNickname()
    const prompt = window.prompt('请输入你的昵称（仅本地保存）', saved || defaultNicknameFor(userIdRef.current))
    if (prompt == null) return null  // user cancelled
    const clean = prompt.trim().slice(0, 24) || defaultNicknameFor(userIdRef.current)
    persistNickname(clean)
    return clean
  }

  /** Create a fresh lobby room (entry point from the "组队对战" mode card). */
  const createLobby = useCallback(async (useLlm: boolean) => {
    const nickname = ensureNickname()
    if (nickname == null) return
    setLobbyError(null)
    try {
      const res = await apiPost<{ room?: RoomLite; error?: string }>(
        '/api/rooms',
        { user_id: userIdRef.current, nickname, use_llm: useLlm },
      )
      if (res.error || !res.room) {
        setLobbyError(res.error || '创建房间失败')
        return
      }
      setRoom(res.room)
    } catch (err) {
      setLobbyError(err instanceof Error ? err.message : '网络错误')
    }
  }, [])

  /** Auto-join: if the URL carried ?invite=<token> on first load, resolve
   * the token to a room and claim a seat. Strips the param so a refresh
   * doesn't loop. */
  useEffect(() => {
    const token = readInviteFromUrl()
    if (!token) return
    clearInviteFromUrl()
    let cancelled = false
    void (async () => {
      try {
        const resolved = await apiGet<{ room?: RoomLite; error?: string }>(
          `/api/rooms/by-token/${encodeURIComponent(token)}`,
        )
        if (cancelled) return
        if (resolved.error || !resolved.room) {
          setLobbyError(resolved.error || '邀请链接无效')
          return
        }
        if (resolved.room.status !== 'lobby') {
          setLobbyError(`房间已${resolved.room.status === 'started' ? '开始游戏' : '关闭'}`)
          return
        }
        // Need a nickname to join — use saved or prompt.
        let nickname = getNickname()
        if (!nickname) {
          const picked = ensureNickname()
          if (picked == null) return
          nickname = picked
        }
        const join = await apiPost<{ your_seat?: number; room?: RoomLite; error?: string }>(
          `/api/rooms/${resolved.room.id}/join`,
          { user_id: userIdRef.current, nickname },
        )
        if (cancelled) return
        if (join.error || !join.room) {
          setLobbyError(join.error || '加入房间失败')
          return
        }
        setRoom(join.room)
      } catch (err) {
        if (!cancelled) setLobbyError(err instanceof Error ? err.message : '网络错误')
      }
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** Called by LobbyRoom when the host starts the game. The room's
   * room_started WS broadcast carries seat ownership so this user knows
   * which seat (if any) they're playing. */
  const handleLobbyStarted = useCallback((startedGameId: string, mySeat: number | null) => {
    setRoom(null)
    setLobbyError(null)
    // Multi-human game is rendered via the existing 'self' personal-mode
    // pipeline — same modal stack, same per-seat awaiting filter.
    setViewMode('self')
    setHumanSeat(mySeat)
    setGameId(startedGameId)
  }, [setGameId, setHumanSeat, setViewMode])

  // Hard exit: tell the backend to cancel the engine task + drop the row,
  // then clear local state. Backend is authoritative — even if the DELETE
  // request fails (e.g. game already ended), we still reset the UI.
  const exitGame = useCallback(async () => {
    if (!gameId) {
      resetToLanding()
      return
    }
    if (!window.confirm('确定退出当前对局？后端引擎会立即停止并删除该局记录。')) return
    try {
      await apiDelete(`/api/games/${gameId}`)
    } catch {
      // ignore — frontend resets either way
    }
    resetToLanding()
  }, [gameId])

  if (room) {
    return (
      <LobbyRoom
        initialRoom={room}
        userId={userIdRef.current}
        onStarted={handleLobbyStarted}
        onLeave={resetToLanding}
        onClosed={(reason) => {
          setLobbyError(reason === 'host_left' ? '房主已解散房间' : '房间已关闭')
          setRoom(null)
        }}
      />
    )
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
        onCreateLobby={createLobby}
        error={startError || lobbyError}
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
        onMenu={resetToLanding}
        onHistory={() => {
          setHistoryOpen(true)
          setHistoryTab('vote')
        }}
        onInspector={() => {
          setHistoryOpen(true)
          setHistoryTab('settle')
        }}
        onToggleSound={toggleTts}
        onExit={exitGame}
        ttsEnabled={ttsEnabled}
      />

      <main className="game-board">
        <PlayerColumn
          players={playersWithSheriff.slice(0, 6)}
          gameId={gameId}
          viewMode={viewMode}
          humanSeat={humanSeat}
          activeSeat={currentSpeaker}
          voteCounts={voteCounts}
        />

        <CenterStage
          phase={visiblePhase}
          meta={meta}
          players={playersWithSheriff}
          gameId={gameId}
          events={events}
          currentSpeaker={currentSpeaker}
          winner={winner}
          connected={connected}
        />

        <PlayerColumn
          players={playersWithSheriff.slice(6, 12)}
          gameId={gameId}
          viewMode={viewMode}
          humanSeat={humanSeat}
          activeSeat={currentSpeaker}
          voteCounts={voteCounts}
          reverse
        />
      </main>

      <footer className="bottom-dock">
        <DockButton
          icon={`${A}/icons/actions/icon_action_chat.png`}
          label="聊天"
          onClick={() => {
            setHistoryTab('chat')
            setHistoryOpen(true)
          }}
        />
      </footer>

      {historyOpen && (
        <HistoryDrawer
          tab={historyTab}
          events={events}
          players={playersWithSheriff}
          gameId={gameId}
          onTab={setHistoryTab}
          onClose={() => setHistoryOpen(false)}
        />
      )}
      {legendOpen && <StatusLegend onClose={() => setLegendOpen(false)} />}

      {/* In-game modal stack — strict priority, only one is mounted at a time
          so dialogs never visually overlap.
          1) IdentityReveal — must finish before anything else (开局必读)
          2) HumanActionPanel — your turn
          3) InfoDialog — passive notifications */}
      {(() => {
        // Race guard: in self mode, once the game has started we must NOT
        // show any other modal until either IdentityReveal has been
        // dismissed or the player roster has loaded enough for us to know
        // we don't need it. Otherwise an awaiting_human arriving on the
        // WS before loadGameDetail completes could flash a HumanActionPanel
        // before the identity card had a chance.
        const inSelfRoom =
          gameId && gameId !== 'demo' && viewMode === 'self' && humanSeat != null
        const playerKnown = inSelfRoom
          && players.some((p) => p.seat_index === humanSeat && p.role && p.role !== 'unknown')
        if (inSelfRoom && !identityRevealed && !playerKnown) {
          // Identity should fire but player data isn't ready yet → block.
          return null
        }

        const needsIdentity =
          inSelfRoom
          && !identityRevealed
          && (() => {
            const me = players.find((p) => p.seat_index === humanSeat)
            return !!me && !!me.role && me.role !== 'unknown'
          })()

        // 1) IdentityReveal — must finish before anything else (开局必读)
        if (needsIdentity) {
          const me = players.find((p) => p.seat_index === humanSeat)!
          return (
            <IdentityReveal
              gameId={gameId!}
              player={me}
              onClose={() => setIdentityRevealed(true)}
            />
          )
        }

        // 2) HumanActionPanel — your turn
        const needsHumanAction =
          !!awaitingHuman && !!gameId
          && viewMode === 'self' && humanSeat != null
          && awaitingHuman.actor_id === humanSeat
        if (needsHumanAction) {
          return <HumanActionPanel request={awaitingHuman!} gameId={gameId!} players={playersWithSheriff} />
        }

        return null
      })()}

      {/* Top-level personal-mode "AI 正在行动" hint — hidden when the
          HumanActionPanel is already on screen (it's its own giant cue). */}
      {viewMode === 'self' && humanSeat != null && !winner && (() => {
        const isMyTurn = !!awaitingHuman && awaitingHuman.actor_id === humanSeat
        if (isMyTurn) return null
        const me = players.find((p) => p.seat_index === humanSeat)
        const isAlive = me ? !!me.survived : true
        const hint = selfWaitingHint(visiblePhase, currentSpeaker, humanSeat, isAlive)
        if (!hint) return null
        return (
          <div className={`self-status-banner ${!isAlive ? 'observer' : ''}`}>
            {isAlive
              ? <><span className="dot" /><span className="dot" /><span className="dot" /></>
              : <span className="bell">👻</span>}
            <span>{hint}</span>
          </div>
        )
      })()}

      {/* Phase + event flashes for the seated human (skip for god/observer view) */}
      {gameId && gameId !== 'demo' && viewMode === 'self' && humanSeat != null && (
        <GameProgress
          phase={phase}
          round={round}
          events={events}
          humanSeat={humanSeat}
          winner={winner}
        />
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
  onMenu,
  onHistory,
  onInspector,
  onToggleSound,
  onExit,
}: {
  roomId: string
  round: number
  meta: PhaseMeta
  remaining: number
  ttsEnabled: boolean
  onMenu: () => void
  onHistory: () => void
  onInspector: () => void
  onToggleSound: () => void
  onExit: () => void
}) {
  return (
    <header className="game-topbar">
      <button className="round-icon" aria-label="菜单" onClick={onMenu}><span /><span /><span /></button>
      <div className="room-meta">
        <span>房间 {roomId}</span>
        <b>12人标准场</b>
      </div>
      <div className="day-stack">
        <div className="day-pill">
          <span>{formatPhaseLabel(meta.label, round)}</span>
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
        <IconButton
          icon={ttsEnabled ? `${A}/icons/actions/icon_landing_sound_on.png` : `${A}/icons/actions/icon_landing_sound_off.png`}
          label={ttsEnabled ? '声音开' : '声音关'}
          onClick={onToggleSound}
          active={ttsEnabled}
        />
        <IconButton icon={`${A}/icons/actions/icon_game_stop.png`} label="退出" onClick={onExit} danger />
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
  onCreateLobby,
  error,
}: {
  mode: ViewMode
  loading: boolean
  ttsEnabled: boolean
  onModeChange: (mode: ViewMode) => void
  onStart: (useLlm: boolean) => void
  onToggleTts: () => void
  onCreateLobby: (useLlm: boolean) => void
  error?: string | null
}) {
  const [panel, setPanel] = useState<{ title: string; body: string } | null>(null)
  return (
    <div className="landing-page">
      <div className="landing-bg" />
      <header className="landing-top">
        <div className="profile-chip">
          <img src={`${A}/portraits/roles/portrait_villager_male_01_bust.png`} alt="" />
          <div>
            <b>玩家昵称七个字</b>
            <span>ID: 123456</span>
          </div>
        </div>
        <div className="landing-sound">
          <IconButton
            icon={`${A}/icons/actions/icon_landing_match_records.png`}
            label="对局记录"
            onClick={() => setPanel({ title: '对局记录', body: '这里展示历史对局入口。进入对局后可在右侧记录面板查看聊天、投票和结算记录。' })}
          />
          <IconButton icon={ttsEnabled ? `${A}/icons/actions/icon_landing_sound_on.png` : `${A}/icons/actions/icon_landing_sound_off.png`} label={ttsEnabled ? '声音开' : '声音关'} onClick={onToggleTts} active={ttsEnabled} />
          <IconButton icon={`${A}/icons/actions/icon_landing_help.png`} label="帮助" onClick={() => setPanel({ title: '帮助', body: '个人视角只显示自己的身份和操作；上帝视角显示全局身份、技能与投票。点击两张模式卡可选择开局方式。' })} />
          <IconButton icon={`${A}/icons/actions/icon_landing_settings.png`} label="设置" onClick={() => setPanel({ title: '设置', body: `声音状态：${ttsEnabled ? '已开启' : '已关闭'}。你可以点击声音按钮实时切换。` })} />
        </div>
      </header>

      <section className="landing-logo">
        <img src={`${A}/logo/logo_werewolf_title_large.png`} alt="狼人杀" />
        <span>12人标准版</span>
      </section>

      {error && <div className="landing-error">{error}</div>}

      <section className="mode-cards">
        <ModeCard
          active={mode === 'self'}
          tone="blue"
          icon={`${A}/icons/actions/icon_landing_personal_mode.png`}
          silhouette={`${A}/portraits/extra/landing_role_personal.png`}
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
          silhouette={`${A}/portraits/extra/landing_role_god.png`}
          title="上帝视角"
          text="掌控全局，洞悉所有秘密与真相"
          bullets={['上帝视角观战所有信息', '查看所有身份与技能', '复盘分析，掌控全局']}
          onClick={() => onModeChange('god')}
          onStart={() => onStart(true)}
          loading={loading && mode === 'god'}
        />
        {/* 组队对战 mode card hidden — feature still under iteration.
            Lobby backend + LobbyRoom component + invite-link auto-join
            remain wired so existing invite URLs keep working. */}
      </section>

      <span className="version-mark">版本：1.0.0</span>
      {panel && <InfoDialog title={panel.title} body={panel.body} onClose={() => setPanel(null)} />}
    </div>
  )
}

function ModeCard({
  active,
  tone,
  icon,
  silhouette,
  title,
  text,
  bullets,
  loading,
  onClick,
  onStart,
}: {
  active: boolean
  tone: 'blue' | 'red' | 'gold'
  icon: string
  silhouette: string
  title: string
  text: string
  bullets: string[]
  loading: boolean
  onClick: () => void
  onStart: () => void
}) {
  return (
    <article
      className={`mode-card mode-${tone} ${active ? 'active' : ''}`}
      role="button"
      tabIndex={0}
      onMouseEnter={onClick}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onClick()
        }
      }}
    >
      <img className="mode-icon" src={icon} alt="" />
      <h2>{title}</h2>
      <p>{text}</p>
      <div className="mode-hero">
        <img className="mode-silhouette" src={silhouette} alt="" />
      </div>
      <ul>
        {bullets.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <button onClick={(event) => {
        event.stopPropagation()
        onClick()
        onStart()
      }}>{loading ? '启动中' : '开始游戏'}<span>›</span></button>
    </article>
  )
}

function PlayerColumn({
  players,
  gameId,
  viewMode,
  humanSeat,
  activeSeat,
  voteCounts,
  reverse = false,
}: {
  players: Player[]
  gameId: string | null
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
          visible={visiblePlayer(player, viewMode, humanSeat, gameId)}
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
  const deathBadge = dead ? deathBadgeIcon(player.death_cause) : null
  return (
    <article className={`player-card tone-${meta.tone} ${active ? 'active' : ''} ${dead ? 'dead' : ''} ${reverse ? 'reverse' : ''}`}>
      <div className="player-info">
        <div className="seat-number">{player.seat_index}</div>
        <div className="player-copy">
          <span>{`玩家${player.seat_index}`}</span>
          <strong>{hidden ? '未知' : meta.label}</strong>
        </div>
      </div>
      <img className="player-portrait" src={portrait} alt="" />
      <div className="status-stack">
        {player.is_sheriff ? <img src={`${A}/icons/status/icon_status_sheriff.png`} alt="警长" title="警长" /> : null}
        {deathBadge ? <img src={deathBadge.icon} alt={deathBadge.label} title={deathBadge.label} /> : null}
        {voteCount ? <b>{voteCount}</b> : null}
      </div>
    </article>
  )
}

function deathBadgeIcon(cause?: string): { icon: string; label: string } | null {
  switch (cause) {
    case 'wolf':
    case 'wolf_kill':
      return { icon: `${A}/icons/skills/icon_skill_wolf_kill.png`, label: '被狼刀' }
    case 'poison':
      return { icon: `${A}/icons/skills/icon_skill_witch_poison.png`, label: '被毒' }
    case 'hunter':
    case 'hunter_shot':
      return { icon: `${A}/icons/skills/icon_skill_hunter_shoot.png`, label: '被猎人开枪' }
    case 'exile':
      return { icon: `${A}/icons/status/icon_status_exiled.png`, label: '被放逐' }
    case 'self_destruct':
      return { icon: `${A}/icons/actions/icon_action_explode.png`, label: '自爆' }
    default:
      return { icon: `${A}/icons/status/icon_status_exiled.png`, label: '已出局' }
  }
}

function CenterStage({
  phase,
  meta,
  players,
  gameId,
  events,
  currentSpeaker,
  winner,
  connected,
}: {
  phase: string
  meta: PhaseMeta
  players: Player[]
  gameId: string | null
  events: GameEvent[]
  currentSpeaker: number
  winner: string | null
  connected: boolean
}) {
  const latest = events[events.length - 1]
  if (phase === 'sheriff_election') {
    return <SheriffPanel players={players} gameId={gameId} events={events} />
  }

  return (
    <section className="center-stage">
      {/* No miniature village panorama here — the full-screen .sample-app
          background already shows the current phase scene. */}
      <section className="speaker-status">
        {/* Speaker-relative labels start with "号" (e.g. "号玩家发言中").
            Anything else is system narration ("裁判结算投票", "天黑请闭眼")
            and must NOT be prefixed by a seat number. */}
        <h1>
          {winner
            ? `${winner === 'wolf' ? '狼人' : '好人'}阵营胜利`
            : meta.actionLabel.startsWith('号') && currentSpeaker
              ? `${currentSpeaker}${meta.actionLabel}`
              : (meta.actionLabel || meta.shortLabel)}
        </h1>
        <div className="timer-row">
          <img src={`${A}/icons/actions/icon_speed_config.png`} alt="" />
          <div className="timer-track"><span /></div>
          <b>{phase === 'night_witch' ? '120s' : '60s'}</b>
        </div>
      </section>

      <nav className="phase-tabs">
        {PHASE_STEPS.map(([label, stepPhase, icon]) => (
          <button key={label} className={phase === stepPhase ? 'active' : ''} disabled>
            <img src={icon} alt="" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {phase === 'day_speech' && (
        <SpeechOrderPanel events={events} currentSpeaker={currentSpeaker} />
      )}

      {phase === 'day_vote'
        ? <VotePanel players={players} events={events} />
        : <NoticePanel latest={latest} connected={connected} />}
    </section>
  )
}

function SpeechOrderPanel({
  events,
  currentSpeaker,
}: {
  events: GameEvent[]
  currentSpeaker: number
}) {
  // Backend emits a speech_order_announced event at the start of
  // day_speech with the full speaking order; latest one wins (handles
  // multi-round games).
  const order = useMemo<number[]>(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i]
      if (ev.event_type !== 'speech_order_announced') continue
      const raw = ev.data?.order
      if (!Array.isArray(raw)) continue
      return raw.map((s: unknown) => Number(s)).filter((n) => Number.isFinite(n))
    }
    return []
  }, [events])

  // Which seats have already finished speaking this round? Inferred from
  // public_speech_made events since the last speech_order_announced.
  const spoken = useMemo<Set<number>>(() => {
    const set = new Set<number>()
    let cursor = events.length - 1
    while (cursor >= 0 && events[cursor].event_type !== 'speech_order_announced') cursor -= 1
    for (let i = cursor + 1; i < events.length; i += 1) {
      const ev = events[i]
      if (ev.event_type === 'public_speech_made') {
        const seat = Number(ev.data?.player_id)
        if (Number.isFinite(seat)) set.add(seat)
      }
    }
    return set
  }, [events])

  if (order.length === 0) return null

  return (
    <section className="speech-order">
      <h3>发言顺序 <span>（依次发言）</span></h3>
      <div>
        {order.map((seat, index) => {
          const isCurrent = seat === currentSpeaker && !spoken.has(seat)
          const isDone = spoken.has(seat)
          const className = isCurrent ? 'current' : isDone ? 'done' : ''
          return (
            <span key={`${seat}-${index}`} className={className}>
              <b>{seat}</b> 号
              {index < order.length - 1 ? <i>→</i> : null}
            </span>
          )
        })}
      </div>
    </section>
  )
}

// Internal lifecycle events that shouldn't surface in the notice panel
// — they're plumbing for the engine/UI, not narration for the player.
const SUPPRESSED_NOTICE_EVENT_TYPES = new Set([
  'speaking_started',
  'phase_started',
  'phase_ended',
  'awaiting_human',
  'human_submitted',
  'speech_order_announced',
])

function NoticePanel({ latest, connected }: { latest?: GameEvent; connected: boolean }) {
  const latestText = latest && !SUPPRESSED_NOTICE_EVENT_TYPES.has(latest.event_type)
    ? eventSummary(latest)
    : null
  return (
    <section className="notice-panel">
      <p><i />{connected ? '实时连接已建立。' : '正在等待后端连接。'}</p>
      <p><i />{latestText || '等待后端事件推进对局。'}</p>
    </section>
  )
}

function eventSummary(event: GameEvent): string {
  // Only narration-style or human-readable events reach here (system
  // lifecycle events are filtered upstream). Fall back to content/type
  // for unknown shapes but never expose raw "event.speaking_started".
  const raw = event.content || event.event_type || ''
  if (raw.startsWith('event.')) return ''
  return raw
}

function VotePanel({
  players,
  events,
}: {
  players: Player[]
  events: GameEvent[]
}) {
  // Display-only tally. Backend only emits vote_resolved at the END of a
  // vote round (anti-leak: no per-vote events during the round). So during
  // the round we show an empty grid; once vote_resolved arrives, we render
  // the full tally from its `votes` dict.
  const round = events.reduce((acc, ev) => Math.max(acc, ev.round || 0), 0)
  const resolved = [...events].reverse().find(
    (ev) => ev.event_type === 'vote_resolved' && (ev.round || 0) === round,
  )
  const votesMap: Record<number, number | null> = (resolved?.data?.votes as any) || {}
  const tally: Record<number, number> = {}
  let abstain = 0
  for (const target of Object.values(votesMap)) {
    if (target == null) abstain += 1
    else tally[Number(target)] = (tally[Number(target)] || 0) + 1
  }
  const totalVotes = Object.keys(votesMap).length
  return (
    <section className="vote-panel">
      <header>
        <b>放逐投票</b>
        <span>{totalVotes > 0 ? `共 ${totalVotes} 票 · 已结算` : '等待全部玩家投票…'}</span>
      </header>
      <div className="vote-grid">
        {players.filter((p) => p.survived).map((player) => {
          const count = tally[player.seat_index] || 0
          return (
            <button
              key={player.seat_index}
              className={count > 0 ? 'has-votes' : ''}
              disabled
            >
              {player.seat_index}
              {count > 0 && <em> · {count}</em>}
            </button>
          )
        })}
        <button className={abstain > 0 ? 'has-votes' : ''} disabled>
          弃票{abstain > 0 && <em> · {abstain}</em>}
        </button>
      </div>
    </section>
  )
}

function SheriffPanel({
  players,
  gameId,
  events,
}: {
  players: Player[]
  gameId: string | null
  events: GameEvent[]
}) {
  // Candidates list comes ONLY from the aggregated sheriff_elected event.
  // While the candidacy + speech window is open the panel shows "等待报名…"
  // so we don't leak the candidate set incrementally as each campaign
  // speech arrives. Same principle as vote_resolved — backend ships one
  // complete result, frontend renders it once.
  const candidates = useMemo(() => {
    const resolved = [...events].reverse().find((ev) => ev.event_type === 'sheriff_elected')
    const fromResolved = (resolved?.data?.candidates as number[] | undefined) || []
    const candidateSeats = new Set(fromResolved.map((s) => Number(s)))
    return players.filter((p) => candidateSeats.has(p.seat_index))
  }, [events, players])
  const resolvedSheriff = [...events].reverse().find((ev) => ev.event_type === 'sheriff_elected')
  const sheriffVotes: Record<number, number | null> = (resolvedSheriff?.data?.votes as any) || {}
  const tally: Record<number, number> = {}
  let abstain = 0
  for (const target of Object.values(sheriffVotes)) {
    if (target == null) abstain += 1
    else tally[Number(target)] = (tally[Number(target)] || 0) + 1
  }
  return (
    <section className="sheriff-stage">
      <header className="sheriff-title">
        <img src={`${A}/icons/status/icon_status_sheriff.png`} alt="" />
        <h1>警长竞选阶段</h1>
        <p>报名 / 发言 / 投票全部由后端按顺序驱动，请等待行动面板弹出。</p>
      </header>
      <div className="sheriff-grid">
        <section className="sheriff-card">
          <h2>竞选报名</h2>
          <p>玩家通过行动面板提交是否参选；其他人的报名会在阶段结束时统一公布。</p>
        </section>
        <section className="sheriff-card">
          <h2>当前竞选者（{candidates.length}/12）</h2>
          <div className="candidate-row">
            {candidates.map((player) => (
              // Only the seat number is public during sheriff election —
              // no avatar (identity hidden until natural reveal).
              <div key={player.seat_index} className="candidate-chip">
                <b>{player.seat_index}</b>
                <span>号</span>
              </div>
            ))}
            {candidates.length === 0 && (
              <span className="candidate-empty">等待报名…</span>
            )}
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
          {candidates.length === 0 && <span className="candidate-empty">—</span>}
        </div>
      </section>
      <section className="sheriff-vote">
        <h3>警下投票</h3>
        <div className="round-vote-row">
          {players.filter((p) => p.survived).map((p) => {
            const count = tally[p.seat_index] || 0
            return (
              <button key={p.seat_index} className={count > 0 ? 'has-votes' : ''} disabled>
                {p.seat_index}{count > 0 && <em> · {count}</em>}
              </button>
            )
          })}
          <button className={abstain > 0 ? 'has-votes' : ''} disabled>
            弃票{abstain > 0 && <em> · {abstain}</em>}
          </button>
        </div>
      </section>
    </section>
  )
}

// SkillModal removed — was a demo-only witch yes/no preview with hardcoded
// "8 号" target. Real witch input now goes through HumanActionPanel
// (witch_antidote / witch_poison tools), driven by the backend awaiting_human
// event for the actual witch seat.

function HistoryDrawer({
  tab,
  events,
  players,
  gameId,
  onTab,
  onClose,
}: {
  tab: DrawerTab
  events: GameEvent[]
  players: Player[]
  gameId: string | null
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
                  <img src={avatarForSeat(players, seat, gameId)} alt="" />
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
  // Backend now publishes aggregated resolution events only:
  //   * sheriff_elected.data = {player_id, candidates, votes, ...}
  //   * vote_resolved.data   = {votes, chosen}
  // The full {voter: target} map lives on the resolution event, so we no
  // longer need to walk individual vote_cast events.
  const groups: VoteGroup[] = []
  for (const ev of events) {
    const round = typeof ev.round === 'number' ? ev.round : 1
    if (ev.event_type === 'sheriff_elected') {
      const sid = ev.data?.player_id ?? null
      const votes = (ev.data?.votes as Record<string, number | null> | undefined) || {}
      const byVoter: Record<number, number | null> = {}
      for (const [voter, target] of Object.entries(votes)) {
        const v = Number(voter)
        if (Number.isFinite(v)) byVoter[v] = target == null ? null : Number(target)
      }
      groups.push({
        key: `s-${round}-${ev.seq ?? groups.length}`,
        title: `第 ${round} 天 警长竞选`,
        result: sid != null ? `${sid} 号当选警长` : (ev.data?.reason === 'no candidates' ? '无人参选' : '平票，未当选'),
        focus: sid == null ? null : Number(sid),
        byVoter,
      })
    } else if (ev.event_type === 'vote_resolved') {
      const chosen = ev.data?.chosen
      const votes = (ev.data?.votes as Record<string, number | null> | undefined) || {}
      const byVoter: Record<number, number | null> = {}
      for (const [voter, target] of Object.entries(votes)) {
        const v = Number(voter)
        if (Number.isFinite(v)) byVoter[v] = target == null ? null : Number(target)
      }
      groups.push({
        key: `d-${round}-${ev.seq ?? groups.length}`,
        title: `第 ${round} 天 放逐投票`,
        result: chosen == null ? '平票，未放逐' : `${chosen} 号出局`,
        focus: chosen == null ? null : Number(chosen),
        byVoter,
      })
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

function InfoDialog({ title, body, onClose }: { title: string; body: string; onClose: () => void }) {
  return (
    <section className="info-backdrop" onClick={onClose}>
      <article className="info-dialog" onClick={(event) => event.stopPropagation()}>
        <button className="drawer-close" onClick={onClose}>×</button>
        <h2>{title}</h2>
        <p>{body}</p>
        <button className="primary-action" onClick={onClose}>确认</button>
      </article>
    </section>
  )
}

function IconButton({
  icon,
  label,
  active,
  danger,
  onClick,
}: {
  icon: string
  label: string
  active?: boolean
  danger?: boolean
  onClick?: () => void
}) {
  return (
    <button className={`icon-button ${active ? 'active' : ''} ${danger ? 'danger' : ''}`} onClick={onClick}>
      <img src={icon} alt="" />
      <span>{label}</span>
    </button>
  )
}

function DockButton({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button className="dock-button" onClick={onClick}>
      <img src={icon} alt="" />
      <span>{label}</span>
    </button>
  )
}

function visiblePlayer(player: Player, viewMode: ViewMode, humanSeat: number | null, gameId: string | null): VisiblePlayer {
  const selfCanSee = viewMode === 'self' && player.seat_index === humanSeat
  const revealAll = viewMode === 'god' || viewMode === 'observer'
  const hidden = !(selfCanSee || revealAll)
  if (hidden) {
    return {
      player,
      meta: ROLE_META.unknown,
      hidden: true,
      portrait: unknownPortraitForSeat(player.seat_index),
    }
  }
  return {
    player,
    meta: roleMeta(player),
    hidden: false,
    portrait: portraitForPlayer(player, gameId),
  }
}

function roleMeta(player: Player): RoleMeta {
  return ROLE_META[player.role] || ROLE_META.villager
}

function avatarForSeat(players: Player[], seat: number, gameId: string | null): string {
  const player = players.find((item) => item.seat_index === seat)
  return player ? portraitForPlayer(player, gameId) : UNKNOWN_CLOAK
}

function buildVoteCounts(events: GameEvent[]): Record<number, number> {
  // Reads from the latest aggregated resolution event in the most-recent
  // round only. Individual vote_cast events no longer exist.
  const counts: Record<number, number> = {}
  let bestSeq = -Infinity
  let bestVotes: Record<string, number | null> | null = null
  for (const ev of events) {
    if (ev.event_type !== 'vote_resolved' && ev.event_type !== 'sheriff_elected') continue
    const seq = typeof ev.seq === 'number' ? ev.seq : 0
    if (seq <= bestSeq) continue
    const v = (ev.data?.votes as Record<string, number | null> | undefined) || {}
    if (Object.keys(v).length === 0) continue
    bestSeq = seq
    bestVotes = v
  }
  if (bestVotes) {
    for (const target of Object.values(bestVotes)) {
      if (target == null) continue
      counts[Number(target)] = (counts[Number(target)] || 0) + 1
    }
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

/** Replace any "第 N" prefix in a static phase label with the live round. */
function formatPhaseLabel(label: string, round: number): string {
  return label.replace(/第\s*\d+/, `第 ${Math.max(round, 1)}`)
}

function selfWaitingHint(
  phase: string,
  currentSpeaker: number,
  humanSeat: number | null,
  isAlive: boolean = true,
): string | null {
  // When the human is out, swap action-phase hints for an observer prompt so
  // we don't keep telling them to "wait their turn".
  if (!isAlive) {
    if (phase === 'game_over' || phase === 'check_win') return '裁判正在结算胜负…'
    return '你已出局 · 进入观战模式'
  }
  switch (phase) {
    case 'setup_game':
      return '裁判正在准备对局，请稍候…'
    case 'night_start':
      return '夜幕降临，请闭眼等待…'
    case 'night_wolf':
      return '狼人正在商议夜刀目标…'
    case 'night_seer':
      return '预言家正在查验…'
    case 'night_witch':
      return '女巫正在抉择解药与毒药…'
    case 'night_guard':
      return '守卫正在守护一名玩家…'
    case 'night_resolve':
      return '天将亮起 · 裁判结算夜晚行动…'
    case 'day_announce':
      return '裁判正在公布昨夜结果…'
    case 'sheriff_election':
      return '警长竞选进行中…'
    case 'day_speech':
      if (humanSeat != null && currentSpeaker === humanSeat) return null
      return `等待 ${currentSpeaker} 号玩家发言…`
    case 'day_vote':
      return '其他玩家正在投票…'
    case 'day_resolve':
      return '裁判正在结算投票…'
    case 'pending_skills':
      return '出局玩家正在抉择死亡技能…'
    case 'check_win':
      return '裁判正在检查胜负…'
    default:
      return 'AI 思考中…'
  }
}

// skillForPhase removed — was only used by the deleted SkillModal demo.
// Real per-skill UI lives in HumanActionPanel which gets tool_name from the
// backend awaiting_human event directly.
