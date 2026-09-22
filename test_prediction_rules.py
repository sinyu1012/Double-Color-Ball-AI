"""Offline regression checks for statistics and the previously infeasible balance pool."""

import copy
from collections import Counter
from datetime import date, timedelta
from itertools import combinations
import unittest

import prediction_rules as rules


# Fixed real draw snapshot; later feed updates must not change this regression case.
DRAW_FIXTURE = """26109 2026-09-20 09 12 15 26 30 33 06
26108 2026-09-17 06 11 13 14 20 28 16
26107 2026-09-15 01 05 09 17 24 33 04
26106 2026-09-13 06 11 13 14 22 30 14
26105 2026-09-10 02 04 13 14 15 30 08
26104 2026-09-08 11 12 13 19 20 31 03
26103 2026-09-06 04 11 20 27 28 30 15
26102 2026-09-03 03 04 10 13 16 25 09
26101 2026-09-01 05 06 08 09 24 25 12
26100 2026-08-30 03 04 09 13 22 31 04
26099 2026-08-27 01 12 14 18 30 31 02
26098 2026-08-25 08 16 18 22 25 26 07
26097 2026-08-23 05 16 24 26 29 30 02
26096 2026-08-20 01 04 16 22 26 31 04
26095 2026-08-18 04 06 14 21 22 33 16
26094 2026-08-16 06 13 15 17 24 25 01
26093 2026-08-13 05 08 15 20 21 24 09
26092 2026-08-11 09 11 12 25 30 33 11
26091 2026-08-09 02 13 14 16 20 24 05
26090 2026-08-06 02 04 15 23 25 27 03
26089 2026-08-04 05 18 23 24 27 33 03
26088 2026-08-02 06 07 11 18 22 33 05
26087 2026-07-30 04 06 10 18 23 31 11
26086 2026-07-28 02 05 14 25 30 32 05
26085 2026-07-26 06 09 13 17 24 28 15
26084 2026-07-23 01 05 06 10 12 16 05
26083 2026-07-21 07 14 15 23 28 33 03
26082 2026-07-19 05 07 10 14 21 28 04
26081 2026-07-16 06 10 12 15 24 27 12
26080 2026-07-14 04 05 11 19 27 32 01"""


def fixture_history():
    return [
        {"period": parts[0], "date": parts[1],
         "red_balls": parts[2:8], "blue_ball": parts[8]}
        for parts in (line.split() for line in DRAW_FIXTURE.splitlines())
    ]


def synthetic_history(red_positions, blue_positions=()):
    """Place ball 01 at explicitly chosen offsets in a 40-draw observation window."""
    return [
        {"period": str(10000 - offset),
         "date": (date(2026, 9, 20) - timedelta(days=offset)).isoformat(),
         "red_balls": [1 if offset in red_positions else 20, 10, 12, 14, 16, 18],
         "blue_ball": 1 if offset in blue_positions else 2}
        for offset in range(40)
    ]


def statistics(history):
    # Isolate the documented statistic semantics from candidate feasibility.
    return rules._compute_stats(rules._validated_history(history))


def geometry(reds):
    odd = sum(n % 2 for n in reds)
    big = sum(n >= 17 for n in reds)
    zones = [sum(low <= n <= high for n in reds)
             for low, high in ((1, 11), (12, 22), (23, 33))]
    adjacent = sum(n + 1 in reds for n in reds)
    return odd, big, zones, adjacent


def balanced(reds):
    odd, big, zones, adjacent = geometry(reds)
    return (odd in (3, 4) and big in (2, 3) and 100 <= sum(reds) <= 120
            and adjacent <= 1 and 1 <= zones[0] <= 2
            and 2 <= zones[1] <= 3 and 1 <= zones[2] <= 3)


class StatisticsRegressionTests(unittest.TestCase):
    def test_completed_gaps_exclude_both_censored_edges(self):
        stats = statistics(synthetic_history({2, 6, 15}, {0, 20}))
        red = stats["red"]["01"]
        self.assertEqual(red["current_omission"], 2)
        self.assertEqual(red["previous_omission"], 3)
        self.assertEqual(red["mean_completed_omission"], 5.5)  # gaps 3 and 8
        self.assertEqual(red["counts"], {"5": 1, "10": 2, "20": 3, "30": 3})
        self.assertFalse(red["omission_is_lower_bound"])
        blue = stats["blue"]["01"]
        self.assertEqual(blue["current_omission"], 0)
        self.assertEqual(blue["mean_completed_omission"], 19)
        unseen = stats["red"]["33"]
        self.assertEqual(unseen["current_omission"], 40)
        self.assertTrue(unseen["omission_is_lower_bound"])
        self.assertIsNone(unseen["previous_omission"])
        self.assertIsNone(unseen["mean_completed_omission"])
        once = statistics(synthetic_history({4}))["red"]["01"]
        self.assertIsNone(once["mean_completed_omission"])

    def test_cold_and_cycle_scores_obey_exact_boundaries(self):
        # (current omission, completed previous gap, cold score, cycle bonus)
        cases = [
            (0, 15, 0, 20), (0, 16, 22.4, 20),
            (1, 2, .8, 0), (1, 3, .8, 20),
            (2, 16, 22.4, 0), (3, 16, 2.4, 0),
            (4, 1, 3.2, 0), (5, 1, 5, 0),
            (10, 1, 10, 0), (11, 1, 16.5, 0),
            (20, 1, 30, 0), (21, 1, 16.8, 0),
        ]
        for current, previous, cold_score, bonus in cases:
            with self.subTest(current=current, previous=previous):
                stat = statistics(synthetic_history(
                    {current, current + previous + 1}))["red"]["01"]
                self.assertEqual(stat["previous_omission"], previous)
                self.assertAlmostEqual(stat["cold_score"], cold_score)
                self.assertEqual(stat["cycle_score"] - stat["trend"], bonus)

    def test_boolean_and_fractional_numbers_are_rejected_before_coercion(self):
        for field in ("red_balls", "blue_ball"):
            for invalid in (True, False, 1.0, 1.5):
                with self.subTest(field=field, invalid=invalid):
                    history = fixture_history()
                    if field == "red_balls":
                        history[0][field][0] = invalid
                    else:
                        history[0][field] = invalid
                    with self.assertRaisesRegex(ValueError, "必须为整数或数字字符串"):
                        rules.build_prediction_plan(history)


class CandidateRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = fixture_history()
        cls.plan = rules.build_prediction_plan(cls.history)

    def test_known_infeasible_middle_pool_expands_without_relaxing_constraints(self):
        counts = Counter(ball for draw in self.history for ball in draw["red_balls"])
        middle = [n for n in range(1, 34) if 2 <= counts[f"{n:02d}"] <= 5]
        self.assertEqual(len(middle), 17)
        # In this pool every small ball is in zone 1: requiring >=3 smalls
        # contradicts the <=2 zone-1 limit. Exhaustive check fixes that regression.
        self.assertFalse(any(balanced(reds) for reds in combinations(middle, 6)))
        for candidate in self.plan["options"][3]:
            reds = list(map(int, candidate["red_balls"]))
            self.assertTrue(balanced(reds))
            self.assertTrue(set(reds) - set(middle))
            self.assertIn(
                "红球原候选池17球不足8个合法组合，按距30期出现2-5次区间的距离扩池至19球；硬约束保持不变",
                candidate["adjustments"],
            )

    def test_every_candidate_is_valid_and_preserves_strategy_constraints(self):
        counts = {
            window: Counter(ball for draw in self.history[:window]
                            for ball in draw["red_balls"])
            for window in (5, 10, 30)
        }
        balls = [f"{n:02d}" for n in range(1, 34)]
        omissions = {
            ball: next((i for i, draw in enumerate(self.history)
                        if ball in draw["red_balls"]), len(self.history))
            for ball in balls
        }
        heat_top = set(sorted(balls, key=lambda b: (
            -(counts[5][b] * 5 + counts[10][b] * 3 + counts[30][b] * 2), b))[:10])
        cold_top = set(sorted(balls, key=lambda b: (-omissions[b], b))[:10])
        trend_top = set(sorted(balls, key=lambda b: (
            -(counts[5][b] * 20 + counts[10][b] * 5 - counts[30][b] * 5), b))[:10])
        seen_ids = set()
        for group_id, candidates in self.plan["options"].items():
            self.assertEqual(len(candidates), 8)
            seen_reds = set()
            for candidate in candidates:
                with self.subTest(candidate=candidate["candidate_id"]):
                    self.assertNotIn(candidate["candidate_id"], seen_ids)
                    seen_ids.add(candidate["candidate_id"])
                    self.assertEqual(candidate["group_id"], group_id)
                    self.assertEqual(candidate["strategy"], rules.STRATEGIES[group_id])
                    reds = list(map(int, candidate["red_balls"]))
                    self.assertEqual(len(reds), 6)
                    self.assertEqual(reds, sorted(set(reds)))
                    self.assertTrue(all(1 <= n <= 33 for n in reds))
                    self.assertEqual(candidate["red_balls"], [f"{n:02d}" for n in reds])
                    self.assertNotIn(tuple(reds), seen_reds)
                    seen_reds.add(tuple(reds))
                    self.assertRegex(candidate["blue_ball"], r"^(0[1-9]|1[0-6])$")
                    self.assertLessEqual(len(candidate["description"]), 100)
                    self.assertIn("蓝球" + candidate["blue_ball"], candidate["description"])
                    odd, big, zones, _ = geometry(reds)
                    if group_id == 1:
                        self.assertTrue(all(1 <= size <= 3 for size in zones))
                    elif group_id == 2:
                        self.assertEqual(odd, 3)
                        self.assertIn(big, (2, 3, 4))
                        self.assertGreaterEqual(len({n % 10 for n in reds}), 5)
                    elif group_id == 3:
                        self.assertTrue(balanced(reds))
                    elif group_id == 5:
                        self.assertIn(odd, (3, 4))
                        self.assertIn(big, (2, 3))
                        self.assertTrue(100 <= sum(reds) <= 120)
                        chosen = set(candidate["red_balls"])
                        self.assertGreaterEqual(len(chosen & heat_top), 2)
                        self.assertTrue(chosen & cold_top)
                        self.assertTrue(chosen & trend_top)

    def test_descriptions_report_selected_numbers_and_actual_statistics(self):
        for group_id, candidates in self.plan["options"].items():
            for candidate in candidates:
                reds = list(map(int, candidate["red_balls"]))
                odd, big, zones, adjacent = geometry(reds)
                description = candidate["description"]
                blue = candidate["blue_ball"]
                blue_count = sum(draw["blue_ball"] == blue for draw in self.history[:20])
                if group_id in (2, 3, 5):
                    self.assertIn(f"奇偶{odd}:{6-odd}、大小{big}:{6-big}", description)
                if group_id in (3, 5):
                    self.assertIn(f"和值{sum(reds)}", description)
                if group_id in (1, 3):
                    self.assertIn(f"蓝球{blue}近20期{blue_count}次", description)
                    self.assertIn("区间" + "-".join(map(str, zones)), description)
                if group_id == 3:
                    self.assertIn(f"连号{adjacent}对", description)
        # Exact known arithmetic examples also protect heat/cycle/composite copy.
        self.assertEqual(self.plan["options"][1][0]["description"],
                         "05热度29、调整分29.0；区间3-2-1；蓝球02近20期2次")
        self.assertEqual(self.plan["options"][4][0]["description"],
                         "09趋势+30.0、周期分+30.0；蓝球03遗漏5期、平均空期6.0期")
        self.assertEqual(self.plan["options"][5][0]["description"],
                         "09综合49.2；奇偶3:3、大小2:4；和值109；蓝球09综合57.0")

    def test_order_is_deterministic_and_input_is_not_mutated(self):
        original = copy.deepcopy(self.history)
        self.assertEqual(rules.build_prediction_plan(list(reversed(self.history))), self.plan)
        self.assertEqual(rules.build_prediction_plan(self.history), self.plan)
        self.assertEqual(self.history, original)
        self.assertEqual(self.plan["sources"]["latest_period"], "26109")
        self.assertEqual(self.plan["options"][3][0]["red_balls"],
                         ["01", "07", "12", "17", "31", "32"])
        # A full five-group selection with distinct red combinations must exist.
        def choose(group_id, selected):
            if group_id == 6:
                return True
            return any(
                tuple(option["red_balls"]) not in selected
                and choose(group_id + 1, selected | {tuple(option["red_balls"])})
                for option in self.plan["options"][group_id]
            )
        self.assertTrue(choose(1, set()))


if __name__ == "__main__":
    unittest.main()

