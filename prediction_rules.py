"""Deterministic statistics and feasible candidate sets for model selection.

Only pass actual lottery draws, never prediction/backfill records, to this module.
Positions are measured from the latest draw (position zero). Current omission is
that first position, or a lower bound equal to the available history length when
unseen. A completed omission is ``positions[i + 1] - positions[i] - 1``;
mean_completed_omission excludes both censored edges and is None with <2 hits.
previous_omission is the latest completed gap, used by rebound/turning signals.

Red heat = count5*5 + count10*3 + count30*2. Trend uses observed draw frequency:
(count5/5 - count30/30)*100 + (count10/10 - count30/30)*50.
Heat is multiplied by .5 after a latest-draw hit, .7 after >=3 missed draws.
Cold score uses omission * (1, 1.5, .8) for gaps 5..10, 11..20, other;
a rebound (previous gap >15, current <=2) uses max(base, previous gap)*1.4.
Cycle score adds 20 when previous gap >=3 and current omission <=1.

Composite red: heat minmax*.30 + current/max_current*100*.25 + balance*.20
+ trend minmax*.25. Balance is 80 for count30 2..5, 50 for >5, else 60.
Minmax is 0..100 over all balls of that color; constant inputs map to 50.
Blue composite: count20 minmax*.30 + current/max_current*100*.30
+ 100/(1+abs(current-mean_completed))*.20 + 100/(1+distance(count20,2..4))*.20.
The cycle component is zero without any completed gap.

Rank ties always use ascending ball numbers. Ranked pools are enumerated in
lexicographic rank order, retaining the first eight valid *distinct red* sets.
Heat/cycle start at their respective adjusted-score Top8, cold at Top12,
composite at Top8. Balance starts with every count30=2..5 ball, ordered by
distance from 3.5 then ball number, and expands by distance from the 2..5 band.
Blue choices: heat maximizes count20 within omission 3..10; cold maximizes
omission within 8..15; balance minimizes distance from count20=3 within 2..4;
cycle minimizes absolute distance from mean completed omission. Empty blue
pools expand by distance to their stated band (cold tries 3..20 first).
Every actual expansion is included in the affected candidate's adjustments.
Expansion only enumerates newly introduced combinations; each possible red set
is examined at most once per strategy, bounded by C(33,6). Pool expansion never
relaxes parity, size, sum, diversity, zone, adjacency, or lottery validity rules.
These deterministic rankings do not establish predictive advantage.
"""

from datetime import date
from itertools import combinations
import json
import re


STRATEGIES = {
    1: "增强型热号追随者",
    2: "增强型冷号逆向者",
    3: "增强型平衡策略师",
    4: "增强型周期理论家",
    5: "增强型综合决策者",
}
OPTIONS_PER_GROUP = 8


def _integer(value, label, maximum):
    # int(value) would silently accept floats and bools; forbid both before parsing.
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,2}", value):
        parsed = int(value)
    else:
        raise ValueError(f"{label} 必须为整数或数字字符串")
    if not 1 <= parsed <= maximum:
        raise ValueError(f"{label} 超出 1..{maximum}")
    return parsed


def _validated_history(history):
    if not isinstance(history, list) or len(history) < 30:
        raise ValueError("至少需要 30 期真实开奖数据")
    draws, periods = [], set()
    for entry in history:
        if not isinstance(entry, dict):
            raise ValueError("开奖记录必须为对象")
        period = entry.get("period")
        if type(period) is int and period > 0:
            period = str(period)
        if not isinstance(period, str) or not re.fullmatch(r"[0-9]+", period):
            raise ValueError("开奖期号必须为正整数或数字字符串")
        period = str(int(period))
        if int(period) <= 0 or period in periods:
            raise ValueError(f"开奖期号无效或重复: {period}")
        periods.add(period)
        try:
            draw_date = date.fromisoformat(entry["date"]).isoformat()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{period} 开奖日期无效") from exc
        reds = entry.get("red_balls")
        if not isinstance(reds, list) or len(reds) != 6:
            raise ValueError(f"{period} 必须有 6 个红球")
        reds = sorted(_integer(ball, f"{period} 红球", 33) for ball in reds)
        if len(set(reds)) != 6:
            raise ValueError(f"{period} 红球重复")
        blue = _integer(entry.get("blue_ball"), f"{period} 蓝球", 16)
        draws.append({"period": period, "date": draw_date, "reds": reds, "blue": blue})
    draws.sort(key=lambda draw: int(draw["period"]), reverse=True)
    if any(draws[i]["date"] <= draws[i + 1]["date"] for i in range(len(draws) - 1)):
        raise ValueError("开奖期号与日期顺序不一致或日期重复")
    return draws


def _minmax(values):
    lo, hi = min(values.values()), max(values.values())
    return {ball: (50.0 if hi == lo else (value - lo) * 100 / (hi - lo))
            for ball, value in values.items()}


def _distance(value, low, high):
    return max(low - value, value - high, 0)


def _ball_stats(draws, color, maximum):
    stats = {}
    for number in range(1, maximum + 1):
        positions = [index for index, draw in enumerate(draws)
                     if (number in draw["reds"] if color == "red" else number == draw["blue"])]
        gaps = [b - a - 1 for a, b in zip(positions, positions[1:])]
        stats[f"{number:02d}"] = {
            "counts": {str(window): sum(pos < window for pos in positions)
                       for window in (5, 10, 20, 30)},
            "current_omission": positions[0] if positions else len(draws),
            "omission_is_lower_bound": not positions,
            "previous_omission": gaps[0] if gaps else None,
            "mean_completed_omission": sum(gaps) / len(gaps) if gaps else None,
        }
    return stats


def _compute_stats(draws):
    red = _ball_stats(draws, "red", 33)
    blue = _ball_stats(draws, "blue", 16)
    for stat in red.values():
        counts, omission, previous = stat["counts"], stat["current_omission"], stat["previous_omission"]
        stat["heat"] = counts["5"] * 5 + counts["10"] * 3 + counts["30"] * 2
        # Integer counts make this algebraically equivalent expression exact.
        stat["trend"] = counts["5"] * 20 + counts["10"] * 5 - counts["30"] * 5
        stat["heat_score"] = stat["heat"] * (.5 if omission == 0 else .7 if omission >= 3 else 1)
        base = omission * (1 if 5 <= omission <= 10 else 1.5 if 11 <= omission <= 20 else .8)
        stat["cold_score"] = max(base, previous) * 1.4 if previous is not None and previous > 15 and omission <= 2 else base
        stat["cycle_score"] = stat["trend"] + (20 if previous is not None and previous >= 3 and omission <= 1 else 0)
        stat["balance_score"] = 80 if 2 <= counts["30"] <= 5 else 50 if counts["30"] > 5 else 60
    heat = _minmax({ball: stat["heat"] for ball, stat in red.items()})
    trend = _minmax({ball: stat["trend"] for ball, stat in red.items()})
    max_red_gap = max(stat["current_omission"] for stat in red.values())
    for ball, stat in red.items():
        stat["heat_normalized"] = heat[ball]
        stat["trend_normalized"] = trend[ball]
        stat["omission_normalized"] = stat["current_omission"] * 100 / max_red_gap if max_red_gap else 50.0
        stat["composite_score"] = heat[ball] * .30 + stat["omission_normalized"] * .25 + stat["balance_score"] * .20 + trend[ball] * .25
    frequencies = _minmax({ball: stat["counts"]["20"] for ball, stat in blue.items()})
    max_blue_gap = max(stat["current_omission"] for stat in blue.values())
    for ball, stat in blue.items():
        mean = stat["mean_completed_omission"]
        stat["frequency_score"] = frequencies[ball]
        stat["omission_score"] = stat["current_omission"] * 100 / max_blue_gap if max_blue_gap else 50.0
        stat["cycle_score"] = 100 / (1 + abs(stat["current_omission"] - mean)) if mean is not None else 0.0
        stat["balance_score"] = 100 / (1 + _distance(stat["counts"]["20"], 2, 4))
        stat["composite_score"] = stat["frequency_score"] * .30 + stat["omission_score"] * .30 + stat["cycle_score"] * .20 + stat["balance_score"] * .20
    odd_counts, big_counts = {}, {}
    for draw in draws[:30]:
        odd, big, _, _ = _shape(draw["reds"])
        odd_counts[odd] = odd_counts.get(odd, 0) + 1
        big_counts[big] = big_counts.get(big, 0) + 1
    return {"red": red, "blue": blue, "shapes": {"odd_counts": odd_counts, "big_counts": big_counts}}


def _shape(reds):
    odd = sum(ball % 2 for ball in reds)
    big = sum(ball >= 17 for ball in reds)
    zones = tuple(sum(low <= ball <= high for ball in reds) for low, high in ((1, 11), (12, 22), (23, 33)))
    ordered = sorted(reds)
    adjacent = sum(b - a == 1 for a, b in zip(ordered, ordered[1:]))
    return odd, big, zones, adjacent


def _rank(stats, field):
    return sorted(range(1, len(stats) + 1), key=lambda n: (-stats[f"{n:02d}"][field], n))


def _red_candidates(ranking, initial_size, predicate):
    """Enumerate existing pool once, then only combinations containing each new ball."""
    found = []
    for size in range(max(initial_size, 6), len(ranking) + 1):
        if size == max(initial_size, 6):
            candidates = combinations(ranking[:size], 6)
        else:
            candidates = (prefix + (ranking[size - 1],) for prefix in combinations(ranking[:size - 1], 5))
        for candidate in candidates:
            if predicate(candidate):
                found.append((tuple(sorted(candidate)), size))
                if len(found) == OPTIONS_PER_GROUP:
                    return found
    raise ValueError("完整红球候选池仍不足 8 个合法组合，停止生成；未放宽硬约束")


def _blue_choice(group_id, blue):
    balls = list(blue)
    adjustment = []
    if group_id == 1:
        eligible = [ball for ball in balls if 3 <= blue[ball]["current_omission"] <= 10]
        if not eligible:
            eligible = balls
            adjustment.append("蓝球无遗漏3-10期候选，按距该区间最近优先，再按20期频次排序")
        key = lambda ball: (_distance(blue[ball]["current_omission"], 3, 10), -blue[ball]["counts"]["20"], ball)
    elif group_id == 2:
        eligible = [ball for ball in balls if 8 <= blue[ball]["current_omission"] <= 15]
        if not eligible:
            eligible = [ball for ball in balls if 3 <= blue[ball]["current_omission"] <= 20]
            adjustment.append("蓝球无遗漏8-15期候选，扩展至3-20期并按距8-15期区间最近排序")
        if not eligible:
            eligible = balls
            adjustment.append("蓝球3-20期候选仍为空，扩展至全部16球并按距8-15期区间最近排序")
        key = lambda ball: (_distance(blue[ball]["current_omission"], 8, 15), -blue[ball]["current_omission"], ball)
    elif group_id == 3:
        eligible = [ball for ball in balls if 2 <= blue[ball]["counts"]["20"] <= 4]
        if not eligible:
            eligible = balls
            adjustment.append("蓝球无20期出现2-4次候选，按距该频次区间最近排序")
        key = lambda ball: (_distance(blue[ball]["counts"]["20"], 2, 4), abs(blue[ball]["counts"]["20"] - 3), ball)
    elif group_id == 4:
        eligible = [ball for ball in balls if blue[ball]["mean_completed_omission"] is not None]
        if eligible:
            key = lambda ball: (abs(blue[ball]["current_omission"] - blue[ball]["mean_completed_omission"]), ball)
        else:
            eligible = balls
            adjustment.append("蓝球无完整遗漏间隔，回退至20期频次最高号码")
            key = lambda ball: (-blue[ball]["counts"]["20"], ball)
    else:
        eligible = balls
        key = lambda ball: (-blue[ball]["composite_score"], ball)
    return min(eligible, key=key), adjustment


def _description(group_id, reds, blue_ball, stats):
    odd, big, zones, adjacent = _shape(reds)
    red, blue = stats["red"], stats["blue"][blue_ball]
    first = f"{reds[0]:02d}"
    def omission_text(stat):
        prefix = "至少" if stat["omission_is_lower_bound"] else ""
        return f"{prefix}{stat['current_omission']}期"

    if group_id == 1:
        return f"{first}热度{red[first]['heat']}、调整分{red[first]['heat_score']:.1f}；区间{'-'.join(map(str, zones))}；蓝球{blue_ball}近20期{blue['counts']['20']}次"
    if group_id == 2:
        return f"{first}遗漏{omission_text(red[first])}；奇偶{odd}:{6-odd}、大小{big}:{6-big}；尾数{len({n % 10 for n in reds})}种；蓝球{blue_ball}遗漏{omission_text(blue)}"
    if group_id == 3:
        return f"奇偶{odd}:{6-odd}、大小{big}:{6-big}；和值{sum(reds)}、连号{adjacent}对；区间{'-'.join(map(str, zones))}；蓝球{blue_ball}近20期{blue['counts']['20']}次"
    if group_id == 4:
        mean = blue["mean_completed_omission"]
        mean_text = f"{mean:.1f}期" if mean is not None else "暂无完整间隔"
        return f"{first}趋势{red[first]['trend']:+.1f}、周期分{red[first]['cycle_score']:+.1f}；蓝球{blue_ball}遗漏{omission_text(blue)}、平均空期{mean_text}"
    return f"{first}综合{red[first]['composite_score']:.1f}；奇偶{odd}:{6-odd}、大小{big}:{6-big}；和值{sum(reds)}；蓝球{blue_ball}综合{blue['composite_score']:.1f}"


def build_prediction_plan(history: list) -> dict:
    """Validate real draws and build eight canonical options per strategy; no I/O."""
    draws = _validated_history(history)
    stats = _compute_stats(draws)
    red = stats["red"]
    heat_top = set(_rank(red, "heat")[:10])
    cold_top = set(_rank(red, "current_omission")[:10])
    trend_top = set(_rank(red, "trend")[:10])

    def valid_cold(reds):
        return (sum(n % 2 for n in reds) == 3 and 2 <= sum(n >= 17 for n in reds) <= 4
                and len({n % 10 for n in reds}) >= 5)

    def valid_balance(reds):
        odd, big, zones, adjacent = _shape(reds)
        return (odd in (3, 4) and big in (2, 3) and 100 <= sum(reds) <= 120
                and adjacent <= 1 and 1 <= zones[0] <= 2 and 2 <= zones[1] <= 3 and 1 <= zones[2] <= 3)

    def valid_composite(reds):
        selected = set(reds)
        return (sum(n % 2 for n in reds) in (3, 4) and sum(n >= 17 for n in reds) in (2, 3)
                and 100 <= sum(reds) <= 120 and len(selected & heat_top) >= 2
                and bool(selected & cold_top) and bool(selected & trend_top))

    balance_rank = sorted(range(1, 34), key=lambda n: (
        _distance(red[f"{n:02d}"]["counts"]["30"], 2, 5),
        abs(red[f"{n:02d}"]["counts"]["30"] - 3.5), n))
    middle_count = sum(2 <= stat["counts"]["30"] <= 5 for stat in red.values())
    specifications = {
        1: (_rank(red, "heat_score"), 8, lambda reds: all(1 <= n <= 3 for n in _shape(reds)[2])),
        2: (_rank(red, "cold_score"), 12, valid_cold),
        3: (balance_rank, middle_count, valid_balance),
        4: (_rank(red, "cycle_score"), 8, lambda reds: True),
        5: (_rank(red, "composite_score"), 8, valid_composite),
    }
    options = {}
    for group_id, (ranking, initial_size, predicate) in specifications.items():
        blue_ball, blue_adjustments = _blue_choice(group_id, stats["blue"])
        try:
            choices = _red_candidates(ranking, initial_size, predicate)
        except ValueError as exc:
            raise ValueError(f"策略{group_id}：{exc}") from exc
        options[group_id] = []
        for index, (reds, pool_size) in enumerate(choices, 1):
            adjustments = list(blue_adjustments)
            if pool_size > initial_size:
                rule = "按距30期出现2-5次区间的距离扩池" if group_id == 3 else "按策略得分降序扩池"
                adjustments.append(f"红球原候选池{initial_size}球不足8个合法组合，{rule}至{pool_size}球；硬约束保持不变")
            description = _description(group_id, reds, blue_ball, stats)
            if len(description) > 100:
                raise ValueError(f"策略{group_id}程序生成描述超过100字")
            option = {"candidate_id": f"{group_id}-{index:02d}", "group_id": group_id,
                      "strategy": STRATEGIES[group_id], "red_balls": [f"{n:02d}" for n in reds],
                      "blue_ball": blue_ball, "description": description}
            if adjustments:
                option["adjustments"] = adjustments
            options[group_id].append(option)
    return {
        "options": options,
        "stats": stats,
        "sources": {"history_count": len(draws), "latest_period": draws[0]["period"],
                    "oldest_period": draws[-1]["period"], "latest_date": draws[0]["date"],
                    "oldest_date": draws[-1]["date"]},
    }


def format_plan(plan: dict) -> str:
    """Keep the full statistics in Python; send only grounded candidates to the model."""
    compact = {
        "source": plan["sources"],
        "groups": [{"group_id": group_id, "strategy": STRATEGIES[group_id],
                    "candidates": [{key: value for key, value in candidate.items()
                                    if key not in ("group_id", "strategy")}
                                   for candidate in plan["options"][group_id]]}
                   for group_id in STRATEGIES],
    }
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
