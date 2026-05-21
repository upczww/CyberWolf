import type { AwaitingHumanRequest, GameEvent } from '../stores/game'

export interface BackendProgress {
  phase: string | null
  round: number
  status: string | null
  winner: string | null
  awaitingHuman: AwaitingHumanRequest | null
}

export function normalizeGameEvent(raw: any): GameEvent {
  return {
    ...raw,
    data: raw?.data_json || raw?.data || {},
    event_type: raw?.event_type,
  } as GameEvent
}

export function mergeGameEvents(existing: GameEvent[], incoming: GameEvent | GameEvent[]): GameEvent[] {
  const nextEvents = Array.isArray(incoming) ? incoming : [incoming]
  const byKey = new Map<string, GameEvent>()

  for (const event of existing) {
    byKey.set(eventKey(event), event)
  }
  for (const rawEvent of nextEvents) {
    const event = normalizeGameEvent(rawEvent)
    byKey.set(eventKey(event), event)
  }

  return Array.from(byKey.values()).sort(compareEvents)
}

export function deriveBackendProgress(events: GameEvent[], initial?: Partial<BackendProgress>): BackendProgress {
  const progress: BackendProgress = {
    phase: initial?.phase ?? null,
    round: initial?.round ?? 1,
    status: initial?.status ?? null,
    winner: initial?.winner ?? null,
    awaitingHuman: initial?.awaitingHuman ?? null,
  }

  for (const event of events) {
    const data = event.data || {}
    if (event.event_type === 'phase_started') {
      progress.phase = String(data.phase || event.phase || progress.phase || '')
      progress.round = toNumber(data.round, progress.round)
    } else if (event.event_type === 'awaiting_human') {
      progress.awaitingHuman = {
        actor_id: Number(data.actor_id),
        tool_name: String(data.tool_name ?? ''),
        phase: String(data.phase ?? event.phase ?? ''),
        role: String(data.role ?? ''),
        round: toNumber(data.round, progress.round),
        timeout_seconds: toNumber(data.timeout_seconds, 60),
        local_args: data.local_args || {},
      }
    } else if (event.event_type === 'human_submitted') {
      const pending = progress.awaitingHuman
      const sameActor = pending?.actor_id === Number(data.actor_id)
      const sameTool = pending?.tool_name === String(data.tool_name ?? '')
      if (!pending || (sameActor && sameTool)) {
        progress.awaitingHuman = null
      }
    } else if (event.event_type === 'game_ended') {
      progress.status = 'completed'
      progress.winner = data.winner || null
      progress.phase = 'game_over'
    }
  }

  return progress
}

function eventKey(event: GameEvent): string {
  if (typeof event.seq === 'number') {
    return `${event.game_id || ''}:seq:${event.seq}`
  }
  return [
    event.game_id || '',
    event.created_at || '',
    event.phase || '',
    event.event_type || '',
    event.content || '',
    JSON.stringify(event.data || {}),
  ].join('|')
}

function compareEvents(a: GameEvent, b: GameEvent): number {
  if (typeof a.seq === 'number' && typeof b.seq === 'number') {
    return a.seq - b.seq
  }
  if (typeof a.seq === 'number') return -1
  if (typeof b.seq === 'number') return 1
  return 0
}

function toNumber(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}
