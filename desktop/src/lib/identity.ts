/**
 * Anonymous user identity for the lobby system.
 *
 * On first launch we generate a stable UUID and persist it in
 * localStorage. The nickname is also persisted but can be edited from
 * any "create room" / "join room" entry point. The UUID is what the
 * backend uses to track seat ownership across reconnects, kicks, and
 * the room → game transition.
 *
 * There's no server-side account — anyone holding the same UUID is
 * treated as the same person. Clearing localStorage is the only way to
 * "log out".
 */

const USER_ID_KEY = 'lycan-user-id'
const NICKNAME_KEY = 'lycan-nickname'

function generateUuid(): string {
  // crypto.randomUUID is available in all modern browsers + Electron.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback for ancient environments — Math.random is fine since this
  // is an ephemeral local identifier, not a security token.
  return 'u-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function getOrCreateUserId(): string {
  try {
    const existing = localStorage.getItem(USER_ID_KEY)
    if (existing && existing.length > 4) return existing
    const fresh = generateUuid()
    localStorage.setItem(USER_ID_KEY, fresh)
    return fresh
  } catch {
    // localStorage unavailable (private mode, etc.) — return an in-memory
    // identity that survives until reload. Lobby will be limited but the
    // app stays usable.
    return generateUuid()
  }
}

export function getNickname(): string {
  try {
    const saved = localStorage.getItem(NICKNAME_KEY)
    if (saved && saved.trim()) return saved.trim().slice(0, 24)
  } catch {
    // ignore
  }
  return ''
}

export function setNickname(name: string): void {
  const clean = name.trim().slice(0, 24)
  try {
    if (clean) localStorage.setItem(NICKNAME_KEY, clean)
    else localStorage.removeItem(NICKNAME_KEY)
  } catch {
    // ignore
  }
}

/** Default nickname fallback so the UI always renders something. */
export function defaultNicknameFor(userId: string): string {
  return `玩家${userId.slice(0, 4).toUpperCase()}`
}

/** Build the invite URL for a room token, using the current origin. */
export function buildInviteUrl(token: string): string {
  if (typeof window === 'undefined') return `?invite=${token}`
  const { origin, pathname } = window.location
  return `${origin}${pathname}?invite=${token}`
}

/** Extract `?invite=...` from the current URL, if any. */
export function readInviteFromUrl(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('invite')
    return token && token.length > 4 ? token : null
  } catch {
    return null
  }
}

/** Strip the invite param from the URL after we've consumed it, so a
 * page refresh doesn't try to re-join. */
export function clearInviteFromUrl(): void {
  if (typeof window === 'undefined') return
  try {
    const url = new URL(window.location.href)
    url.searchParams.delete('invite')
    window.history.replaceState({}, '', url.toString())
  } catch {
    // ignore
  }
}
