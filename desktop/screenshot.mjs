// Headless screenshot pass for LycanTUI desktop UI
// Usage: node scripts/screenshot.js [vite-url]
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdirSync } from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VITE_URL = process.argv[2] || 'http://localhost:5180/'
const OUT_DIR = path.resolve(__dirname, 'screenshots')

mkdirSync(OUT_DIR, { recursive: true })

const VIEWS = [
  { w: 1440, h: 900, name: 'desktop' },
  { w: 1920, h: 1080, name: 'fhd' },
  { w: 1024, h: 720, name: 'small' },
]

async function main() {
  const browser = await chromium.launch()
  for (const v of VIEWS) {
    const ctx = await browser.newContext({ viewport: { width: v.w, height: v.h }, deviceScaleFactor: 1 })
    const page = await ctx.newPage()
    await page.goto(VITE_URL, { waitUntil: 'networkidle' })

    // 1) Initial state, god mode
    await page.waitForTimeout(400)
    await page.screenshot({ path: path.join(OUT_DIR, `${v.name}-01-init.png`), fullPage: false })

    // 2) Start RNG game, wait completion
    await page.evaluate(async () => {
      const r = await fetch('/api/games/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config_id: '12p_pre_witch_hunter_idiot', use_llm: false }),
      })
      const j = await r.json()
      window.__lastGameId = j.game_id
    })
    // Trigger UI via 规则演示 button so store picks up gameId
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.toolbar-actions button')].find(b => b.textContent.includes('规则演示'))
      btn && btn.click()
    })
    await page.waitForTimeout(2500)
    await page.screenshot({ path: path.join(OUT_DIR, `${v.name}-02-god-endgame.png`), fullPage: false })

    // 3) Observer mode
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.view-mode-toggle button')].find(b => b.textContent.includes('旁观'))
      btn && btn.click()
    })
    await page.waitForTimeout(300)
    await page.screenshot({ path: path.join(OUT_DIR, `${v.name}-03-observer-endgame.png`), fullPage: false })

    // 4) Self mode with seat 7
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.view-mode-toggle button')].find(b => b.textContent.includes('我加入'))
      btn && btn.click()
    })
    await page.waitForTimeout(200)
    await page.evaluate(() => {
      const sel = document.querySelector('.seat-picker select')
      if (sel) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set
        setter.call(sel, '7')
        sel.dispatchEvent(new Event('change', { bubbles: true }))
      }
    })
    await page.waitForTimeout(300)
    await page.screenshot({ path: path.join(OUT_DIR, `${v.name}-04-self-seat7-endgame.png`), fullPage: false })

    await ctx.close()
  }
  await browser.close()
  console.log('Screenshots written to', OUT_DIR)
}

main().catch((e) => { console.error(e); process.exit(1) })
