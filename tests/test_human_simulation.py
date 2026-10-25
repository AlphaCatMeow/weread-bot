import random
import statistics
import unittest
from unittest.mock import patch

from tests.helpers import load_weread_bot


class HumanBehaviorSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()
        random.seed(20261025)

    def _simulator(self, **overrides):
        return self.bot.HumanBehaviorSimulator(
            self.bot.HumanSimulationConfig(**overrides)
        )

    def test_disabled_simulation_is_uniform_within_range(self):
        simulator = self._simulator(enabled=False)
        values = [simulator.get_reading_interval("30-40") for _ in range(500)]
        self.assertTrue(all(30 <= v <= 40 for v in values))
        self.assertFalse(any(simulator.should_take_break(10_000) for _ in range(50)))

    def test_intervals_mix_normal_skim_and_long_reads_within_bounds(self):
        simulator = self._simulator(skim_probability=0.1, long_read_probability=0.1)
        values = [simulator.get_reading_interval("30-60") for _ in range(3000)]

        self.assertTrue(all(4.5 <= v <= 150 for v in values))
        skims = [v for v in values if v <= 12]
        long_reads = [v for v in values if v > 108]
        # 略读连续出现 2-4 页，占比明显高于单页概率
        self.assertGreater(len(skims) / len(values), 0.15)
        self.assertGreater(len(long_reads), 0)

    def test_normal_intervals_are_spread_not_uniform(self):
        simulator = self._simulator(
            skim_probability=0, long_read_probability=0,
            reading_speed_variation=False,
        )
        values = [simulator.get_reading_interval("30-60") for _ in range(2000)]
        self.assertAlmostEqual(statistics.median(values), 45, delta=2.5)
        # 对数正态分布有少量超出原区间的值
        self.assertTrue(any(v > 60 for v in values))
        self.assertTrue(all(15 <= v <= 108 for v in values))

    def test_session_pace_differs_between_sessions(self):
        paces = {round(self._simulator().session_pace, 3) for _ in range(20)}
        self.assertGreater(len(paces), 10)
        self.assertTrue(all(0.8 <= p <= 1.25 for p in paces))

    def test_break_has_cooldown_and_grows_with_fatigue(self):
        simulator = self._simulator(break_probability=1.0)
        decisions = [simulator.should_take_break(0) for _ in range(9)]
        self.assertEqual(decisions, [False] * 8 + [True])

        with patch.object(self.bot.random, "random", return_value=0.15):
            fresh = self._simulator(break_probability=0.1)
            tired = self._simulator(break_probability=0.1)
            fresh.pages_since_break = tired.pages_since_break = 100
            self.assertFalse(fresh.should_take_break(0))
            self.assertTrue(tired.should_take_break(1800))

    def test_break_duration_skews_short(self):
        simulator = self._simulator(break_duration="30-300")
        values = [simulator.get_break_duration() for _ in range(2000)]
        self.assertTrue(all(30 <= v <= 300 for v in values))
        self.assertLess(statistics.median(values), 165)

    def test_config_rejects_probabilities_summing_over_one(self):
        config = self.bot.WeReadConfig(
            human_simulation=self.bot.HumanSimulationConfig(
                skim_probability=0.6, long_read_probability=0.5
            )
        )
        with self.assertRaises(self.bot.ConfigError):
            self.bot.validate_config_semantics(config)


if __name__ == "__main__":
    unittest.main()
