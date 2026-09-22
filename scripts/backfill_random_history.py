#!/usr/bin/env python3
"""用明确标注的随机模拟补齐缺失历史；不会调用 AI，也不会改写已有记录。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import tempfile
from datetime import date, datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
START_PERIOD = "25121"
DEFAULT_SEED = "double-color-ball-random-history-v1"
SIMULATION_METHOD = (
    "开奖后随机补录，非开奖前 AI 预测。每期独立生成 5 组；每组从 01–33 "
    "均匀无放回抽取 6 个红球，从 01–16 均匀抽取 1 个蓝球，不按开奖结果筛选。"
    "使用 SHA-256(seed + ':' + target_period) 派生该期的随机种子；"
    "开奖结果仅用于生成号码后计算命中。prediction_date 为 null；"
    "generated_at 是实际补录时间，actual_result.date 是开奖日期。"
)


def validate_period(value, context):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{5}", value):
        raise ValueError(f"{context}: 期号必须是 5 位数字字符串")
    return value


def validate_ball(value, maximum, context):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[0-9]{2}", value)
        or not 1 <= int(value) <= maximum
    ):
        raise ValueError(f"{context}: 号码必须是 01–{maximum:02d} 的两位字符串")


def validate_draws(document):
    if not isinstance(document, dict) or not isinstance(document.get("data"), list):
        raise ValueError("开奖历史必须包含 data 数组")
    draws = {}
    for index, draw in enumerate(document["data"]):
        context = f"开奖历史 data[{index}]"
        if not isinstance(draw, dict):
            raise ValueError(f"{context}: 必须是对象")
        period = validate_period(draw.get("period"), context)
        if period in draws:
            raise ValueError(f"开奖历史包含重复期号 {period}")
        red_balls = draw.get("red_balls")
        if not isinstance(red_balls, list) or len(red_balls) != 6:
            raise ValueError(f"{context}: 必须包含 6 个红球")
        for ball in red_balls:
            validate_ball(ball, 33, context)
        if len(set(red_balls)) != 6:
            raise ValueError(f"{context}: 红球不能重复")
        validate_ball(draw.get("blue_ball"), 16, context)
        draw_date = draw.get("date")
        if not isinstance(draw_date, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", draw_date
        ):
            raise ValueError(f"{context}: 开奖日期必须是 YYYY-MM-DD")
        date.fromisoformat(draw_date)
        draws[period] = draw
    if START_PERIOD not in draws:
        raise ValueError(f"开奖输入未覆盖起始期 {START_PERIOD}，无法完整补录")
    return draws


def validate_history(document):
    if not isinstance(document, dict) or not isinstance(
        document.get("predictions_history"), list
    ):
        raise ValueError("预测历史必须包含 predictions_history 数组")
    periods = set()
    for index, record in enumerate(document["predictions_history"]):
        context = f"预测历史 predictions_history[{index}]"
        if not isinstance(record, dict):
            raise ValueError(f"{context}: 必须是对象")
        period = validate_period(record.get("target_period"), context)
        if period in periods:
            raise ValueError(f"预测历史包含重复期号 {period}，请先核对，脚本不会覆盖")
        periods.add(period)
    return periods


def build_record(draw, seed, generated_at):
    period = draw["period"]
    seed_digest = hashlib.sha256(f"{seed}:{period}".encode("utf-8")).hexdigest()
    rng = random.Random(int(seed_digest, 16))
    predictions = [
        {
            "group_id": group_id,
            "strategy": f"补录第 {group_id} 组",
            "red_balls": [f"{ball:02d}" for ball in sorted(rng.sample(range(1, 34), 6))],
            "blue_ball": f"{rng.randint(1, 16):02d}",
            "description": "开奖后补录的参考号码，非开奖前 AI 预测。",
        }
        for group_id in range(1, 6)
    ]
    # 先生成全部号码，再与真实开奖结果比对；命中情况不参与随机选号。
    for prediction in predictions:
        red_hits = [ball for ball in prediction["red_balls"] if ball in draw["red_balls"]]
        blue_hit = prediction["blue_ball"] == draw["blue_ball"]
        prediction["hit_result"] = {
            "red_hits": red_hits,
            "red_hit_count": len(red_hits),
            "blue_hit": blue_hit,
            "total_hits": len(red_hits) + int(blue_hit),
        }
    best_prediction = max(predictions, key=lambda group: group["hit_result"]["total_hits"])
    return {
        "prediction_date": None,
        "target_period": period,
        "data_source": "random_simulation",
        "generated_at": generated_at,
        "simulation_seed": seed,
        "simulation_method": SIMULATION_METHOD,
        "actual_result": draw,
        "models": [
            {
                "model_id": "random-simulation",
                "model_name": "历史补录",
                "predictions": predictions,
                "best_group": best_prediction["group_id"],
                "best_hit_count": best_prediction["hit_result"]["total_hits"],
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED, help="固定随机种子，默认 %(default)s")
    parser.add_argument("--dry-run", action="store_true", help="仅列出待补期号，不写文件")
    parser.add_argument("--lottery-history", type=Path, default=ROOT / "data/lottery_history.json")
    parser.add_argument(
        "--predictions-history", type=Path, default=ROOT / "data/predictions_history.json"
    )
    args = parser.parse_args()
    if not args.seed:
        parser.error("--seed 不得为空")
    if args.lottery_history.resolve() == args.predictions_history.resolve():
        parser.error("开奖输入和预测历史输出不能是同一个文件")

    try:
        lottery_document = json.loads(args.lottery_history.read_text(encoding="utf-8"))
        original_bytes = args.predictions_history.read_bytes()
        history_document = json.loads(original_bytes)
        draws = validate_draws(lottery_document)
        existing_periods = validate_history(history_document)
        missing_periods = sorted(
            (period for period in draws if period >= START_PERIOD and period not in existing_periods),
            reverse=True,
        )
        print(f"开奖覆盖：{START_PERIOD}–{max(draws)}；已有 {len(existing_periods)} 期")
        print(f"待补录随机模拟：{len(missing_periods)} 期，每期 5 组；seed={args.seed}")
        if missing_periods:
            print("待补期号：" + ", ".join(missing_periods))
        if args.dry_run or not missing_periods:
            print("未写入文件。" if args.dry_run else "没有缺失期，文件保持不变。")
            return 0

        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        new_records = [build_record(draws[period], args.seed, generated_at) for period in missing_periods]
        history_document["predictions_history"] = sorted(
            history_document["predictions_history"] + new_records,
            key=lambda record: record["target_period"],
            reverse=True,
        )
        history_document["历史预测记录"] = (
            "本文件保存已开奖期号的预测与历史补录数据。"
            "data_source=random_simulation 的记录为开奖后补录，不代表 AI 模型实测表现。"
        )
        output_text = json.dumps(history_document, ensure_ascii=False, indent=2) + "\n"
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=args.predictions_history.parent,
                prefix=".predictions_history.", suffix=".tmp", delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(output_text)
            os.chmod(temporary_path, args.predictions_history.stat().st_mode & 0o777)
            if args.predictions_history.read_bytes() != original_bytes:
                raise ValueError("预测历史在运行期间发生变化，已取消写入以避免覆盖")
            os.replace(temporary_path, args.predictions_history)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        print(f"已写入 {len(new_records)} 期随机模拟；所有已有记录保留。")
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(f"补录失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
