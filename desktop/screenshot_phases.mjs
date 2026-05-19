// Capture one screenshot per phase by starting a slow RNG game and polling.
// Usage: node screenshot_phases.mjs [vite-url] [phase-delay]
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdirSync } from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VITE_URL = process.argv[2] || 'http://localhost:5180/'
const PHASE_DELAY = Number(process.argv[3] || 4)
const OUT_DIR = path.resolve(__dirname, 'screenshots/phases')

mkdirSync(OUT_DIR, { recursive: true })

async function main() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 960 }, deviceScaleFactor: 1 })
  const page = await ctx.newPage()
  await page.goto(VITE_URL, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)

  // 1) Snapshot the splash / initial state
  await page.screenshot({ path: path.join(OUT_DIR, '00_init.png') })

  // 2) Kick off a slow RNG game via direct API and feed gameId into store
  const startResp = await page.evaluate(async (delay) => {
    const r = await fetch('/api/games/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_id: '12p_pre_witch_hunter_idiot',
        use_llm: false,
        phase_delay_seconds: delay,
      }),
    })
    return r.json()
  }, PHASE_DELAY)
  console.log('Started game:', startResp.game_id, 'delay', PHASE_DELAY)

  await page.evaluate((gid) => {
    const store = window.__useGameStore
    if (!store) throw new Error('__useGameStore not exposed — rebuild frontend')
    const s = store.getState()
    s.reset()
    s.setGameId(gid)
  }, startResp.game_id)
  await page.waitForTimeout(800)

  // 3) Poll phase changes and screenshot each distinct phase
  const seen = new Set()
  const startedAt = Date.now()
  const maxMs = 5 * 60 * 1000
  let lastWinner = null
  let counter = 1

  while (Date.now() - startedAt < maxMs) {
    const snapshot = await page.evaluate(() => {
      const phase = document.querySelector('.phase-banner strong')?.textContent || null
      const round = (() => {
        const t = document.querySelector('.phase-banner span:first-child')?.textContent || ''
        const m = t.match(/(\d+)/)
        return m ? Number(m[1]) : null
      })()
      const winner = document.querySelector('.endgame-overlay') ? (document.querySelector('.endgame-overlay').classList.contains('wolf') ? 'wolf' : 'good') : null
      return { phase, round, winner }
    })

    const key = `${snapshot.round}_${snapshot.phase}`
    if (snapshot.phase && !seen.has(key)) {
      seen.add(key)
      const safe = String(snapshot.phase).replace(/[^A-Za-z一-龥_]/g, '_')
      const name = `${String(counter).padStart(2, '0')}_R${snapshot.round}_${safe}.png`
      await page.screenshot({ path: path.join(OUT_DIR, name) })
      console.log('Captured', name)
      counter += 1
    }

    if (snapshot.winner && lastWinner !== snapshot.winner) {
      lastWinner = snapshot.winner
      await page.waitForTimeout(800)
      await page.screenshot({ path: path.join(OUT_DIR, '99_endgame.png') })
      console.log('Captured endgame (', snapshot.winner, ')')
      break
    }

    await page.waitForTimeout(700)
  }

  await ctx.close()
  await browser.close()
  console.log('Phase screenshots written to', OUT_DIR)
}

main().catch((e) => { console.error(e); process.exit(1) })
