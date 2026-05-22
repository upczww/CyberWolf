const DEFAULT_PHASE_MAX_SECONDS = 60

export const PHASE_MAX_SECONDS: Record<string, number> = {
  setup_game: 30,
  night_start: 15,
  night_wolf: 30,
  night_seer: 30,
  night_witch: 60,
  night_guard: 30,
  night_resolve: 30,
  sheriff_election: 180,
  day_announce: 30,
  day_speech: 180,
  day_vote: 120,
  day_resolve: 30,
  pending_skills: 60,
  check_win: 10,
  game_over: 10,
}

export function phaseMaxSeconds(phase: string | null | undefined): number {
  return PHASE_MAX_SECONDS[phase || ''] ?? DEFAULT_PHASE_MAX_SECONDS
}
