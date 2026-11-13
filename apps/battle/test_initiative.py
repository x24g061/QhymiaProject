from django.test import SimpleTestCase

from apps.battle.initiative import (
    calculate_gauge_gain,
    action_priority,
)


class InitiativeTests(SimpleTestCase):

    def simulate(self, agi_a, agi_b, loops=20):
        reference = max(1, agi_a, agi_b)
        gauges = [0.0, 0.0]
        counts = [0, 0]

        for _ in range(loops):
            for index, agi in enumerate((agi_a, agi_b)):
                gauges[index] += calculate_gauge_gain(
                    agi, reference
                )

                # 1ループ最大1行動
                if gauges[index] >= 100:
                    counts[index] += 1
                    gauges[index] -= 100

        return tuple(counts)

    def test_equal_agility(self):
        self.assertEqual(
            self.simulate(1000, 1000),
            (18, 18),
        )

    def test_double_agility(self):
        self.assertEqual(
            self.simulate(80, 40),
            (18, 9),
        )

    def test_triple_agility(self):
        self.assertEqual(
            self.simulate(3000, 1000),
            (18, 6),
        )

    def test_large_agility_gap(self):
        self.assertEqual(
            self.simulate(9000, 2000),
            (18, 4),
        )

    def test_gain_limits(self):
        self.assertEqual(
            calculate_gauge_gain(0, 1000),
            1.0,
        )
        self.assertEqual(
            calculate_gauge_gain(10000, 1000),
            95.0,
        )

    def test_earlier_arrival_goes_first(self):
        early = action_priority(70, 60, 40)
        late = action_priority(80, 30, 90)

        self.assertLess(early, late)

    def test_agility_breaks_arrival_tie(self):
        fast = action_priority(10, 90, 100)
        slow = action_priority(50, 50, 50)

        self.assertLess(fast, slow)

    def test_excess_gauge_is_preserved(self):
        gauge = 95.0
        gauge += calculate_gauge_gain(100, 100)

        self.assertEqual(gauge - 100, 85.0)
