// Capture UI screens that mirror desktop/sample_*.png mockups.
// Doesn't require a backend — relies on the in-app demo seed.
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdirSync } from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VITE_URL = process.argv[2] || 'http://localhost:5173/'
const OUT_DIR = path.resolve(__dirname, 'screenshots')
mkdirSync(OUT_DIR, { recursive: true })

const VIEWPORT = { width: 1920, height: 1080 }

async function seedDemo(page, phase = 'day_speech') {
  await page.evaluate((nextPhase) => {
    const store = window.__useGameStore
    if (!store) {
      console.warn('store unavailable, demo seeding skipped')
      return
    }
    const s = store.getState()
    // Mimic what App.seedDemoGame does.
    const players = Array.from({ length: 12 }, (_, i) => ({
      player_id: i + 1,
      seat_index: i + 1,
      role: ['villager','witch','hunter','villager','seer','villager','guard','wolf','wolf','villager','idiot','villager'][i],
      faction: ['good','good','good','good','good','good','good','wolf','wolf','good','good','good'][i],
      is_sheriff: (i + 1) === 1 || (i + 1) === 7 ? 1 : 0,
      survived: 1,
    }))
    const baseEv = (type, content, data, seq) => ({
      game_id: 'demo', phase: 'day_speech', scope: 'public',
      event_type: type, content, data, seq, round: 1,
    })
    const events = [
      baseEv('phase_started', '游戏开始', { phase: 'setup_game' }, 1),
      baseEv('phase_started', '警长竞选阶段', { phase: 'sheriff_election' }, 2),
      baseEv('sheriff_campaign', '4 号竞选警长', { player_id: 4 }, 3),
      baseEv('vote_cast', '1→4', { voter_id: 1, target_id: 4 }, 4),
      baseEv('vote_cast', '2→4', { voter_id: 2, target_id: 4 }, 5),
      baseEv('vote_cast', '3→4', { voter_id: 3, target_id: 4 }, 6),
      baseEv('vote_cast', '5→7', { voter_id: 5, target_id: 7 }, 7),
      baseEv('vote_cast', '6→4', { voter_id: 6, target_id: 4 }, 8),
      baseEv('vote_cast', '8→4', { voter_id: 8, target_id: 4 }, 9),
      baseEv('vote_cast', '9→4', { voter_id: 9, target_id: 4 }, 10),
      baseEv('vote_cast', '10→4', { voter_id: 10, target_id: 4 }, 11),
      baseEv('vote_cast', '11→7', { voter_id: 11, target_id: 7 }, 12),
      baseEv('vote_cast', '12→4', { voter_id: 12, target_id: 4 }, 13),
      baseEv('sheriff_elected', '4 号当选警长', { player_id: 4 }, 14),
      baseEv('phase_started', '白天发言', { phase: 'day_speech' }, 15),
      baseEv('public_speech_made', '1 号发言', { player_id: 1, public_speech: '我觉得 8 号发言逻辑有问题。' }, 16),
      baseEv('public_speech_made', '7 号发言', { player_id: 7, public_speech: '支持 4 号的发言。' }, 17),
      baseEv('phase_started', '放逐投票', { phase: 'day_vote' }, 18),
      baseEv('vote_cast', '1→8', { voter_id: 1, target_id: 8 }, 19),
      baseEv('vote_cast', '2→8', { voter_id: 2, target_id: 8 }, 20),
      baseEv('vote_cast', '3→8', { voter_id: 3, target_id: 8 }, 21),
      baseEv('vote_cast', '4→8', { voter_id: 4, target_id: 8 }, 22),
      baseEv('vote_cast', '5→8', { voter_id: 5, target_id: 8 }, 23),
      baseEv('vote_cast', '6→8', { voter_id: 6, target_id: 8 }, 24),
      baseEv('vote_cast', '7→8', { voter_id: 7, target_id: 8 }, 25),
      baseEv('vote_cast', '8→3', { voter_id: 8, target_id: 3 }, 26),
      baseEv('vote_cast', '9→3', { voter_id: 9, target_id: 3 }, 27),
      baseEv('vote_cast', '10→8', { voter_id: 10, target_id: 8 }, 28),
      baseEv('vote_cast', '11→8', { voter_id: 11, target_id: 8 }, 29),
      baseEv('vote_cast', '12→8', { voter_id: 12, target_id: 8 }, 30),
      baseEv('vote_resolved', '放逐 8 号', { chosen: 8 }, 31),
      baseEv('player_died', '8 号出局', { player_id: 8, cause: 'exile' }, 32),
      baseEv('seer_checked', '预言家查验 9 号 → 狼', { player_id: 5, target_id: 9, result: 'wolf' }, 33),
    ]
    s.setGameId('demo')
    s.setPlayers(players)
    s.setEvents(events)
    s.setPhase(nextPhase)
    s.setRound(1)
    s.setStatus('running')
    s.setWinner(null)
    s.setViewMode('god')
    s.setHumanSeat(null)
  }, phase)
  await page.waitForTimeout(400)
}

async function shot(page, name) {
  const file = path.join(OUT_DIR, `compare-${name}.png`)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', file)
}

async function main() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 })
  const page = await ctx.newPage()

  // capture console errors so we can surface them
  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`))

  await page.goto(VITE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(800)

  // 1. Landing screen
  await shot(page, '01-landing')

  // 2. Day speech (sample.png / sample_talk.png)
  await seedDemo(page, 'day_speech')
  await shot(page, '02-day-speech')

  // 3. Sheriff election (sample_inspector.png)
  await seedDemo(page, 'sheriff_election')
  await shot(page, '03-sheriff-election')

  // 4. Day vote (sample_vote.png — note: sample_vote also shows drawer)
  await seedDemo(page, 'day_vote')
  await shot(page, '04-day-vote')

  // 5. Open history drawer on day_vote (sample_vote.png)
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find((b) => /记录|历史/.test(b.textContent || ''))
    btn?.click()
  })
  await page.waitForTimeout(300)
  await shot(page, '05-history-drawer')

  // close drawer before next shot
  await page.evaluate(() => {
    const closeBtn = document.querySelector('.history-drawer .drawer-close')
    if (closeBtn instanceof HTMLElement) closeBtn.click()
  })
  await page.waitForTimeout(200)

  // 6. Witch action (sample_skill.png)
  await seedDemo(page, 'night_witch')
  // Open SkillModal via the in-stage skill button if present.
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find((b) => /技能|使用/.test(b.textContent || ''))
    btn?.click()
  })
  await page.waitForTimeout(300)
  await shot(page, '06-night-witch')

  if (consoleErrors.length) {
    console.log('\nconsole errors:')
    consoleErrors.slice(0, 20).forEach((e) => console.log(' -', e))
  }

  await browser.close()
}

main().catch((e) => { console.error(e); process.exit(1) })
