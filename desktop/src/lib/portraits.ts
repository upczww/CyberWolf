import type { Player } from '../stores/game'

const A = '/assets/ui'

export const UNKNOWN_CLOAK = `${A}/portraits/unknown/portrait_unknown_cloak_01_bust.png`
export const UNKNOWN_AI = `${A}/portraits/unknown/portrait_unknown_ai_01_bust.png`

export const VILLAGER_PORTRAITS = [
  `${A}/portraits/extra/portrait_elder_male_01_bust.png`,
  `${A}/portraits/extra/portrait_elder_female_01_bust.png`,
  `${A}/portraits/roles/portrait_villager_male_01_bust.png`,
  `${A}/portraits/roles/portrait_villager_female_01_bust.png`,
  `${A}/portraits/extra/portrait_boy_01_bust.png`,
  `${A}/portraits/extra/portrait_girl_01_bust.png`,
]

export const WEREWOLF_PORTRAITS = [
  `${A}/portraits/roles/portrait_werewolf_01_bust.png`,
  `${A}/portraits/roles/portrait_werewolf_02_bust.png`,
  `${A}/portraits/roles/portrait_werewolf_03_bust.png`,
  `${A}/portraits/roles/portrait_werewolf_04_bust.png`,
  `${A}/portraits/roles/portrait_werewolf_05_bust.png`,
  `${A}/portraits/roles/portrait_werewolf_06_bust.png`,
]

const FIXED_ROLE_PORTRAITS: Record<string, string> = {
  seer: `${A}/portraits/roles/portrait_seer_01_bust.png`,
  witch: `${A}/portraits/roles/portrait_witch_01_bust.png`,
  hunter: `${A}/portraits/roles/portrait_hunter_01_bust.png`,
  guard: `${A}/portraits/roles/portrait_guard_01_bust.png`,
  idiot: `${A}/portraits/roles/portrait_idiot_01_bust.png`,
}

export function portraitForPlayer(player: Pick<Player, 'role' | 'seat_index'>, gameId?: string | null): string {
  // Unknown / masked roles must never resolve to a real role portrait —
  // that would leak identity in personal mode where the backend sends
  // role='unknown' for other seats. Fall back to the cloak.
  if (!player.role || player.role === 'unknown') {
    return unknownPortraitForSeat(player.seat_index)
  }
  const role = normalizeRole(player.role)
  if (role === 'villager') {
    return pickStable(VILLAGER_PORTRAITS, gameId, player.seat_index, role)
  }
  if (role === 'werewolf') {
    return pickStable(WEREWOLF_PORTRAITS, gameId, player.seat_index, role)
  }
  return FIXED_ROLE_PORTRAITS[role] || unknownPortraitForSeat(player.seat_index)
}

export function unknownPortraitForSeat(seatIndex: number): string {
  return seatIndex % 3 === 0 ? UNKNOWN_AI : UNKNOWN_CLOAK
}

function normalizeRole(role: string): string {
  if (role === 'wolf') return 'werewolf'
  return role
}

function pickStable(items: string[], gameId: string | null | undefined, seatIndex: number, role: string): string {
  const key = `${gameId || 'demo'}:${role}:${seatIndex}`
  return items[hashString(key) % items.length]
}

function hashString(value: string): number {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}
