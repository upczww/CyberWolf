/**
 * BGM Studio — generate, preview, and manage game background music.
 * Uses MusicGen (facebook/musicgen-small) via server API.
 */
import { useEffect, useState, useRef } from 'react'
import { apiGet, apiPost } from '../hooks/useApi'

interface Preset {
  prompt: string
  filename: string
}

interface BGMFile {
  filename: string
  path: string
  size_kb: number
}

interface GenerateResult {
  success: boolean
  filename: string
  path: string
  size_kb: number
  duration_seconds: number
  prompt: string
}

export default function MusicStudio({ onClose }: { onClose: () => void }) {
  const [presets, setPresets] = useState<Record<string, Preset>>({})
  const [files, setFiles] = useState<BGMFile[]>([])
  const [customCaption, setCustomCaption] = useState('')
  const [customFilename, setCustomFilename] = useState('bgm_custom')
  const [duration, setDuration] = useState(30)
  const [generating, setGenerating] = useState<string | null>(null)
  const [playing, setPlaying] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    loadPresets()
    loadFiles()
  }, [])

  const loadPresets = async () => {
    try {
      const data = await apiGet<Record<string, Preset>>('/api/music/presets')
      setPresets(data)
    } catch { /* server not ready */ }
  }

  const loadFiles = async () => {
    try {
      const data = await apiGet<BGMFile[]>('/api/music/files')
      setFiles(data)
    } catch { /* server not ready */ }
  }

  const generatePreset = async (name: string) => {
    setGenerating(name)
    setError(null)
    try {
      await apiPost<GenerateResult>(`/api/music/generate/${name}`)
      await loadFiles()
    } catch (e) {
      setError(`生成失败: ${e}`)
    } finally {
      setGenerating(null)
    }
  }

  const generateCustom = async () => {
    if (!customCaption.trim()) return
    setGenerating('custom')
    setError(null)
    try {
      await apiPost<GenerateResult>('/api/music/generate', {
        caption: customCaption,
        lyrics: '[Instrumental]',
        duration: duration,
        filename: customFilename,
      })
      await loadFiles()
    } catch (e) {
      setError(`生成失败: ${e}`)
    } finally {
      setGenerating(null)
    }
  }

  const playFile = (path: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
    }
    if (playing === path) {
      setPlaying(null)
      return
    }
    const audio = new Audio(path)
    audio.loop = true
    audio.play()
    audio.onended = () => setPlaying(null)
    audioRef.current = audio
    setPlaying(path)
  }

  const stopAll = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setPlaying(null)
  }

  useEffect(() => {
    return () => { stopAll() }
  }, [])

  const PRESET_LABELS: Record<string, string> = {
    night: '🌙 夜晚',
    day: '☀ 白天',
    vote: '🗳 投票',
    sheriff: '👑 竞选',
    victory_good: '🏆 好人胜',
    victory_wolf: '🐺 狼人胜',
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center">
      <div className="bg-gray-900 border border-white/10 rounded-xl w-[800px] max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-bold">🎵 BGM Studio — MusicGen</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Presets */}
          <section>
            <h3 className="text-sm font-bold text-gray-400 uppercase mb-3">预设生成</h3>
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(PRESET_LABELS).map(([key, label]) => {
                const preset = presets[key]
                const isGenerating = generating === key
                const existingFile = files.find(f => f.filename === `${preset?.filename || key}.wav`)
                return (
                  <div key={key} className="bg-gray-800 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{label}</span>
                      {existingFile && (
                        <span className="text-xs text-green-400">✓ {existingFile.size_kb}KB</span>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => generatePreset(key)}
                        disabled={!!generating}
                        className="flex-1 px-2 py-1 bg-blue-600/80 hover:bg-blue-500 rounded text-xs disabled:opacity-40"
                      >
                        {isGenerating ? '⏳ 生成中...' : existingFile ? '🔄 重新生成' : '🎵 生成'}
                      </button>
                      {existingFile && (
                        <button
                          onClick={() => playFile(existingFile.path)}
                          className={`px-2 py-1 rounded text-xs ${playing === existingFile.path ? 'bg-red-600' : 'bg-green-600/80 hover:bg-green-500'}`}
                        >
                          {playing === existingFile.path ? '⏹' : '▶'}
                        </button>
                      )}
                    </div>
                    {preset && (
                      <p className="text-[10px] text-gray-500 leading-tight line-clamp-2">{preset.caption}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          {/* Custom generation */}
          <section>
            <h3 className="text-sm font-bold text-gray-400 uppercase mb-3">自定义生成</h3>
            <div className="space-y-3">
              <textarea
                value={customCaption}
                onChange={(e) => setCustomCaption(e.target.value)}
                placeholder="描述音乐风格，例如: Dark ambient orchestral, mysterious cello, haunting piano, cinematic game soundtrack"
                className="w-full h-20 bg-gray-800 border border-white/10 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-blue-500"
              />
              <div className="flex items-center gap-3">
                <input
                  value={customFilename}
                  onChange={(e) => setCustomFilename(e.target.value)}
                  placeholder="文件名"
                  className="bg-gray-800 border border-white/10 rounded px-2 py-1 text-sm w-40 focus:outline-none focus:border-blue-500"
                />
                <label className="text-xs text-gray-400">
                  时长:
                  <select
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="ml-1 bg-gray-800 border border-white/10 rounded px-1 py-0.5 text-sm"
                  >
                    <option value={15}>15s</option>
                    <option value={20}>20s</option>
                    <option value={30}>30s</option>
                    <option value={60}>60s</option>
                  </select>
                </label>
                <button
                  onClick={generateCustom}
                  disabled={!!generating || !customCaption.trim()}
                  className="px-4 py-1 bg-purple-600/80 hover:bg-purple-500 rounded text-sm disabled:opacity-40"
                >
                  {generating === 'custom' ? '⏳ 生成中...' : '🎵 生成'}
                </button>
              </div>
            </div>
          </section>

          {/* Generated files */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-gray-400 uppercase">已生成文件</h3>
              <button onClick={stopAll} className="text-xs text-red-400 hover:text-red-300">⏹ 停止播放</button>
            </div>
            {files.length === 0 ? (
              <p className="text-xs text-gray-600">暂无生成的 BGM，点击上方按钮开始生成</p>
            ) : (
              <div className="space-y-1">
                {files.map((f) => (
                  <div
                    key={f.filename}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm ${playing === f.path ? 'bg-green-900/30 border border-green-500/30' : 'bg-gray-800/50'}`}
                  >
                    <span className="font-mono text-xs">{f.filename}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{f.size_kb}KB</span>
                      <button
                        onClick={() => playFile(f.path)}
                        className={`px-2 py-0.5 rounded text-xs ${playing === f.path ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600/80 hover:bg-green-500'}`}
                      >
                        {playing === f.path ? '⏹ 停止' : '▶ 播放'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Error */}
          {error && (
            <div className="text-xs text-red-400 bg-red-900/20 rounded-lg p-2">{error}</div>
          )}

          {/* Info */}
          <div className="text-[10px] text-gray-600 space-y-0.5">
            <p>模型: ACE-Step 1.5 · 许可: MIT（可商用）· VRAM: &lt;4GB · 48kHz 立体声</p>
            <p>用 [Instrumental] + 风格描述生成纯音乐。RTX 3090 约 10 秒/首。</p>
            <p>生成文件保存在 desktop/public/assets/bgm/</p>
          </div>
        </div>
      </div>
    </div>
  )
}
