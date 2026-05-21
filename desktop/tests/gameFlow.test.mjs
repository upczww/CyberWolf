import assert from 'node:assert/strict'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import test from 'node:test'
import ts from 'typescript'

const root = dirname(dirname(fileURLToPath(import.meta.url)))

async function loadTsModule(relativePath) {
  const sourcePath = join(root, relativePath)
  const source = readFileSync(sourcePath, 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
      strict: true,
    },
  }).outputText
  const outPath = join(tmpdir(), 'lycan-tui-flow-tests', `${relativePath.replace(/[\\/]/g, '_')}.mjs`)
  mkdirSync(dirname(outPath), { recursive: true })
  writeFileSync(outPath, compiled)
  return import(pathToFileURL(outPath).href)
}

const flow = await loadTsModule('src/lib/gameFlow.ts')
const portraits = await loadTsModule('src/lib/portraits.ts')

function ev(seq, type, phase, data = {}) {
  return {
    game_id: 'game-1',
    phase,
    scope: 'public',
    event_type: type,
    content: `event.${type}`,
    data,
    seq,
    round: data.round ?? 1,
  }
}

test('mergeGameEvents deduplicates REST and WebSocket history by seq', () => {
  const base = [
    ev(1, 'phase_started', 'setup_game', { phase: 'setup_game', round: 1 }),
    ev(2, 'phase_ended', 'setup_game', { phase: 'setup_game', round: 1 }),
  ]
  const wsHistory = [
    ev(1, 'phase_started', 'setup_game', { phase: 'setup_game', round: 1 }),
    ev(2, 'phase_ended', 'setup_game', { phase: 'setup_game', round: 1 }),
    ev(3, 'phase_started', 'night_start', { phase: 'night_start', round: 1 }),
  ]

  const merged = flow.mergeGameEvents(base, wsHistory)

  assert.deepEqual(merged.map((item) => item.seq), [1, 2, 3])
})

test('deriveBackendProgress follows only backend events', () => {
  const progress = flow.deriveBackendProgress([
    ev(1, 'phase_started', 'setup_game', { phase: 'setup_game', round: 1 }),
    ev(2, 'phase_started', 'night_wolf', { phase: 'night_wolf', round: 1 }),
    ev(3, 'awaiting_human', 'night_wolf', {
      actor_id: 8,
      tool_name: 'wolf_kill_proposal',
      phase: 'night_wolf',
      role: 'wolf',
      round: 1,
      timeout_seconds: 120,
      local_args: { target_id: 3 },
    }),
  ])

  assert.equal(progress.phase, 'night_wolf')
  assert.equal(progress.round, 1)
  assert.equal(progress.awaitingHuman?.actor_id, 8)
})

test('deriveBackendProgress clears pending human action on matching submission', () => {
  const progress = flow.deriveBackendProgress([
    ev(1, 'phase_started', 'sheriff_election', { phase: 'sheriff_election', round: 1 }),
    ev(2, 'awaiting_human', 'sheriff_election', {
      actor_id: 7,
      tool_name: 'sheriff_candidacy',
      phase: 'sheriff_election',
      role: 'villager',
      round: 1,
      timeout_seconds: 75,
      local_args: { target_id: null },
    }),
    ev(3, 'human_submitted', 'sheriff_election', {
      actor_id: 7,
      tool_name: 'sheriff_candidacy',
    }),
  ])

  assert.equal(progress.awaitingHuman, null)
})

test('deriveBackendProgress clears stale awaiting when phase advances without human_submitted', () => {
  // Simulates the case where backend timed out or cancelled the awaiter
  // without emitting human_submitted, then the next phase started. The
  // previous phase's modal must not leak into the new phase.
  const progress = flow.deriveBackendProgress([
    ev(1, 'phase_started', 'night_wolf', { phase: 'night_wolf', round: 1 }),
    ev(2, 'awaiting_human', 'night_wolf', {
      actor_id: 8,
      tool_name: 'wolf_kill_proposal',
      phase: 'night_wolf',
      role: 'wolf',
      round: 1,
      timeout_seconds: 120,
      local_args: { target_id: 3 },
    }),
    ev(3, 'phase_started', 'night_seer', { phase: 'night_seer', round: 1 }),
  ])

  assert.equal(progress.phase, 'night_seer')
  assert.equal(progress.awaitingHuman, null)
})

test('deriveBackendProgress keeps awaiting that matches the current phase', () => {
  // A new awaiting_human within the same phase should remain pending.
  const progress = flow.deriveBackendProgress([
    ev(1, 'phase_started', 'night_witch', { phase: 'night_witch', round: 2 }),
    ev(2, 'awaiting_human', 'night_witch', {
      actor_id: 5,
      tool_name: 'witch_antidote',
      phase: 'night_witch',
      role: 'witch',
      round: 2,
      timeout_seconds: 105,
      local_args: { use_antidote: false },
    }),
  ])

  assert.equal(progress.awaitingHuman?.tool_name, 'witch_antidote')
  assert.equal(progress.awaitingHuman?.phase, 'night_witch')
})

test('portraitForPlayer picks stable per-game villager and werewolf variants', () => {
  const villager = { role: 'villager', seat_index: 3 }
  const wolf = { role: 'wolf', seat_index: 8 }

  const villagerPortrait = portraits.portraitForPlayer(villager, 'game-a')
  const wolfPortrait = portraits.portraitForPlayer(wolf, 'game-a')

  assert.ok(portraits.VILLAGER_PORTRAITS.includes(villagerPortrait))
  assert.ok(portraits.WEREWOLF_PORTRAITS.includes(wolfPortrait))
  assert.equal(portraits.portraitForPlayer(villager, 'game-a'), villagerPortrait)
  assert.equal(portraits.portraitForPlayer(wolf, 'game-a'), wolfPortrait)

  const villagerAcrossGames = new Set(
    ['game-a', 'game-b', 'game-c', 'game-d', 'game-e'].map((gameId) => portraits.portraitForPlayer(villager, gameId)),
  )
  const wolfAcrossGames = new Set(
    ['game-a', 'game-b', 'game-c', 'game-d', 'game-e'].map((gameId) => portraits.portraitForPlayer(wolf, gameId)),
  )

  assert.ok(villagerAcrossGames.size > 1)
  assert.ok(wolfAcrossGames.size > 1)
})
