import { useState } from 'react'
import { apiPost } from '../hooks/useApi'
import { useGameStore } from '../stores/game'

interface Props {
  onGameStarted: (gameId: string) => void
  onOpenGameList: () => void
  onOpenMusic: () => void
}

type ViewMode = 'self' | 'god'

interface StartOptions {
  mode: ViewMode
  useLlm: boolean
}

export default function LandingScreen({ onGameStarted, onOpenGameList, onOpenMusic }: Props) {
  const { setViewMode, setHumanSeat } = useGameStore()
  const [starting, setStarting] = useState<ViewMode | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startGame = async ({ mode, useLlm }: StartOptions) => {
    if (starting) return
    setStarting(mode)
    setError(null)
    try {
      const payload: Record<string, unknown> = {
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: useLlm,
      }
      if (mode === 'self') payload.human_join = true
      const res = await apiPost<{ game_id: string; human_seat?: number | null }>(
        '/api/games/start',
        payload,
      )
      setViewMode(mode)
      if (mode === 'self' && typeof res.human_seat === 'number') {
        setHumanSeat(res.human_seat)
      } else {
        setHumanSeat(null)
      }
      onGameStarted(res.game_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动失败')
    } finally {
      setStarting(null)
    }
  }

  return (
    <div className="landing">
      <div className="landing-moon" aria-hidden />
      <img className="landing-wolf-silhouette" src="/assets/avatars/wolf.png" alt="" />

      <div className="landing-topbar">
        <div className="landing-profile">
          <div className="avatar">
            <img src="/assets/avatars/variants/villager_01.png" alt="" />
          </div>
          <div className="meta">
            <b>玩家昵称七个字</b>
            <span>ID: 123456</span>
          </div>
        </div>
        <div className="landing-actions">
          <button className="icon-btn" title="声音" onClick={onOpenMusic}>🔊</button>
          <button className="icon-btn" title="帮助">?</button>
          <button className="icon-btn" title="设置">⚙</button>
        </div>
      </div>

      <div className="landing-title">
        <h1>狼人杀</h1>
        <div className="subtitle">12 人标准版</div>
      </div>

      <div className="landing-signboard" aria-hidden>
        <b>月圆之夜</b>
        谁是狼人
      </div>

      <div className="landing-mode-grid">
        <article className="mode-card mode-self">
          <div className="mode-icon">👤</div>
          <h2>个人视角</h2>
          <div className="mode-tag">沉浸体验 · 开启属于你的推理之旅</div>
          <div className="mode-art" />
          <ul>
            <li>你将是唯一的真人玩家</li>
            <li>其他玩家由 AI 扮演</li>
            <li>只可见己方身份与白天信息</li>
          </ul>
          <button
            className="mode-btn"
            onClick={() => startGame({ mode: 'self', useLlm: true })}
            disabled={!!starting}
          >
            {starting === 'self' ? '启动中…' : '开始游戏'}
            <span className="arrow">›</span>
          </button>
        </article>

        <article className="mode-card mode-god">
          <div className="mode-icon">👁</div>
          <h2>上帝视角</h2>
          <div className="mode-tag">掌控全局 · 洞悉所有秘密与真相</div>
          <div className="mode-art" />
          <ul>
            <li>上帝视角可见所有信息</li>
            <li>查看所有身份与托底</li>
            <li>复盘分析 · 掌控全局</li>
          </ul>
          <button
            className="mode-btn"
            onClick={() => startGame({ mode: 'god', useLlm: true })}
            disabled={!!starting}
          >
            {starting === 'god' ? '启动中…' : '开始游戏'}
            <span className="arrow">›</span>
          </button>
        </article>
      </div>

      {error && (
        <div style={{ position: 'absolute', bottom: 64, left: 0, right: 0, textAlign: 'center', color: '#d77065', letterSpacing: '0.08em' }}>
          ⚠ {error}
        </div>
      )}

      <nav className="landing-footer">
        <button className="landing-footer-btn" onClick={onOpenGameList}>
          <span className="icon">📜</span>
          对局记录
        </button>
        <button className="landing-footer-btn">
          <span className="icon">🤖</span>
          <span className="badge">NEW</span>
          AI 托管
        </button>
        <button className="landing-footer-btn">
          <span className="icon">📊</span>
          游戏总结
        </button>
        <button className="landing-footer-btn">
          <span className="icon">🏆</span>
          成就
        </button>
        <button className="landing-footer-btn">
          <span className="icon">📈</span>
          排行榜
        </button>
      </nav>

      <div className="landing-version">版本: 1.0.0</div>
    </div>
  )
}
