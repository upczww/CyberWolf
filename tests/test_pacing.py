import asyncio
import time
import unittest
from types import SimpleNamespace

from app.domain.roles import Phase
from app.engine.pacing import (
    MIN_VISIBLE_ACTION_HOLD_SECONDS,
    phase_max_seconds,
    phase_remaining_seconds,
    start_phase_budget,
    hold_visible_action,
)


class PacingTests(unittest.TestCase):
    def test_phase_budget_has_expected_caps(self) -> None:
        self.assertEqual(phase_max_seconds(Phase.NIGHT_WOLF), 30.0)
        self.assertEqual(phase_max_seconds(Phase.DAY_VOTE), 120.0)
        self.assertEqual(phase_max_seconds(Phase.DAY_SPEECH), 180.0)

    def test_start_phase_budget_sets_deadline(self) -> None:
        services = SimpleNamespace(_phase_deadline_at=None)
        start_phase_budget(services, Phase.DAY_VOTE)

        remaining = phase_remaining_seconds(services)

        self.assertIsNotNone(remaining)
        self.assertGreater(remaining, 119.0)
        self.assertLessEqual(remaining, 120.0)

    def test_visible_action_hold_uses_remaining_budget(self) -> None:
        async def run_case() -> float:
            services = SimpleNamespace(_phase_deadline_at=time.monotonic() + 0.02)
            started = time.monotonic() - MIN_VISIBLE_ACTION_HOLD_SECONDS
            before = time.monotonic()
            await hold_visible_action(started, services)
            return time.monotonic() - before

        elapsed = asyncio.run(run_case())

        self.assertLess(elapsed, 0.05)


if __name__ == "__main__":
    unittest.main()
