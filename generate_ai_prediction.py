# -*- coding: utf-8 -*-
"""基于已验证候选生成下一期预测；失败时不覆盖已有预测。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from prediction_rules import STRATEGIES, build_prediction_plan, format_plan

BASE_URL = os.environ.get("AI_BASE_URL") or "https://aihubmix.com/v1"
API_KEY = os.environ.get("AI_API_KEY")
MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "model_id": "gpt-4o"},
    {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5", "model_id": "claude-sonnet-4-5"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "model_id": "gemini-2.5-flash"},
    {"id": "deepseek-chat", "name": "DeepSeek Chat", "model_id": "deepseek-chat"},
]
SCRIPT_DIR = Path(__file__).resolve().parent
LOTTERY_HISTORY_FILE = SCRIPT_DIR / "data/lottery_history.json"
AI_PREDICTIONS_FILE = SCRIPT_DIR / "data/ai_predictions.json"
PREDICTIONS_HISTORY_FILE = SCRIPT_DIR / "data/predictions_history.json"
PROMPT_FILE = SCRIPT_DIR / "doc/prompt3.0.md"
GENERATOR_VERSION = "3.1"


class PredictionValidationError(ValueError):
    """模型响应无效，禁止保存为正式预测。"""


class AlreadyGenerated(Exception):
    """相同输入的本期完整预测已经存在。"""


def load_prompt_template():
    return Path(PROMPT_FILE).read_text(encoding="utf-8")


def load_lottery_history():
    return json.loads(Path(LOTTERY_HISTORY_FILE).read_text(encoding="utf-8"))


def get_now_shanghai():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def get_openai_client():
    # 统计和离线测试不依赖 SDK 或凭证，实际调用时才检查。
    api_key = os.environ.get("AI_API_KEY") or API_KEY
    if not api_key:
        raise RuntimeError("请设置环境变量 AI_API_KEY")
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=60.0, max_retries=0)


def extract_json_from_response(response_text):
    text = response_text.strip()
    fence = chr(96) * 3
    match = re.fullmatch(fence + r"(?:json)?\s*(.*?)\s*" + fence, text, flags=re.DOTALL)
    return match.group(1) if match else text


def call_ai_model(client, model_config, prompt):
    response = client.chat.completions.create(
        model=model_config["id"],
        messages=[
            {"role": "system", "content": "只从给定候选中选择，返回要求的 JSON，不添加文字或编造候选。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    if not response.choices or not isinstance(response.choices[0].message.content, str):
        raise PredictionValidationError("模型没有返回文本 JSON")
    raw = response.choices[0].message.content
    try:
        payload = json.loads(extract_json_from_response(raw))
    except json.JSONDecodeError as error:
        error.raw_response = raw[:6000]
        raise
    if isinstance(payload, dict):
        # 路由名取自 SDK 响应，不接受模型在内容中自报。
        payload["_response_model"] = getattr(response, "model", None)
    return payload


def resolve_selections(payload, plan, expected_group_ids=None, locked=None):
    """校验选择协议，保留有效组，错误组定向修复。"""
    expected = set(plan["options"] if expected_group_ids is None else expected_group_ids)
    locked = locked or {}
    if not isinstance(payload, dict) or not isinstance(payload.get("selections"), list):
        return {}, ["必须返回对象，selections 必须是数组"]
    by_group, duplicates = {}, set()
    for selection in payload["selections"]:
        if not isinstance(selection, dict):
            return {}, ["selections 中每项必须是对象"]
        gid = selection.get("group_id")
        if type(gid) is not int or gid not in expected:
            return {}, [f"group_id 必须是待选择组 {sorted(expected)} 中的整数，不得包含其他组"]
        if gid in by_group:
            duplicates.add(gid)
        by_group[gid] = selection
    used_reds = set()
    for gid, cid in locked.items():
        candidate = next(c for c in plan["options"][gid] if c["candidate_id"] == cid)
        used_reds.add(tuple(candidate["red_balls"]))
    valid, errors = {}, []
    for gid in sorted(expected):
        if gid in duplicates:
            errors.append(f"组{gid}: group_id 重复")
            continue
        if gid not in by_group:
            errors.append(f"缺少组{gid}的选择")
            continue
        cid = by_group[gid].get("candidate_id")
        candidate = next((c for c in plan["options"][gid] if c["candidate_id"] == cid), None) if isinstance(cid, str) else None
        if candidate is None:
            errors.append(f"组{gid}: candidate_id 不在该组给定候选中")
            continue
        reds = tuple(candidate["red_balls"])
        if reds in used_reds:
            errors.append(f"组{gid}: 红球组合与已保留的组完全相同，请选择其他候选")
            continue
        valid[gid] = cid
        used_reds.add(reds)
    return valid, errors


def _retryable_api_error(error):
    status = getattr(error, "status_code", None)
    return (
        status in (408, 429) or (isinstance(status, int) and status >= 500)
        or isinstance(error, (TimeoutError, ConnectionError))
        or type(error).__name__ in ("APITimeoutError", "APIConnectionError")
    )


def _repair_prompt(plan, accepted, errors, previous):
    pending = sorted(set(plan["options"]) - set(accepted))
    locked = [next(c for c in plan["options"][gid] if c["candidate_id"] == cid)
              for gid, cid in sorted(accepted.items())]
    context = {
        "errors": errors, "previous_response": previous,
        "locked_groups": [{"group_id": c["group_id"], "red_balls": c["red_balls"]} for c in locked],
        "candidates": {gid: plan["options"][gid] for gid in pending},
    }
    return (
        "修正上次候选选择。只返回待修复组的 selections，每项仅含整数 group_id 与字符串 candidate_id。"
        "已锁定组不要重复返回；新选择的红球组合不得与锁定组或其他组相同。"
        "候选号码和说明不可修改，只输出 JSON。\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    )


def call_ai_model_with_retry(client, model_config, prompt, plan, max_retries=2):
    if type(max_retries) is not int or not 0 <= max_retries <= 2:
        raise ValueError("max_retries 必须为 0、1 或 2")
    accepted, feedback, previous, response_model = {}, [], None, None
    for attempt in range(max_retries + 1):
        request_prompt = _repair_prompt(plan, accepted, feedback, previous) if feedback else prompt
        try:
            payload = call_ai_model(client, model_config, request_prompt)
            previous = payload
            if isinstance(payload, dict):
                response_model = payload.get("_response_model") or response_model
            pending = set(plan["options"]) - set(accepted)
            valid, feedback = resolve_selections(payload, plan, pending, accepted)
            accepted.update(valid)
            if not feedback and len(accepted) == len(plan["options"]):
                predictions = [
                    copy.deepcopy(next(c for c in plan["options"][gid] if c["candidate_id"] == cid))
                    for gid, cid in sorted(accepted.items())
                ]
                return {
                    "model_id": model_config["model_id"], "model_name": model_config["name"],
                    "requested_model": model_config["id"], "response_model": response_model,
                    "validation_status": "passed", "predictions": predictions,
                }
        except (json.JSONDecodeError, PredictionValidationError) as error:
            feedback = [f"输出必须是符合协议的 JSON：{error}"]
            previous = getattr(error, "raw_response", None)
        except Exception as error:
            if not _retryable_api_error(error) or attempt == max_retries:
                raise
            print(f"  ⚠️ {model_config['name']} 暂时不可用，第 {attempt + 1} 次重试")
            time.sleep(2 ** attempt)
            continue
        print(f"  ⚠️ {model_config['name']} 第 {attempt + 1} 次校验失败：{'；'.join(feedback)}")
    raise PredictionValidationError(f"{model_config['name']} 重试耗尽：{'；'.join(feedback)}")


def _valid_saved_model(model):
    """保存/复用前的基础防线，不信任磁盘上的 validation_status。"""
    if not isinstance(model, dict) or not isinstance(model.get("model_id"), str) or not isinstance(model.get("model_name"), str):
        return False
    groups = model.get("predictions")
    if not isinstance(groups, list) or len(groups) != 5:
        return False
    group_ids, combinations = set(), set()
    for group in groups:
        if not isinstance(group, dict):
            return False
        gid, reds, blue = group.get("group_id"), group.get("red_balls"), group.get("blue_ball")
        if type(gid) is not int or gid not in STRATEGIES or gid in group_ids:
            return False
        if not isinstance(reds, list) or len(reds) != 6 or any(
                not isinstance(b, str) or not re.fullmatch(r"[0-9]{2}", b) or not 1 <= int(b) <= 33 for b in reds):
            return False
        if len(set(reds)) != 6 or reds != sorted(reds) or tuple(reds) in combinations:
            return False
        if not isinstance(blue, str) or not re.fullmatch(r"[0-9]{2}", blue) or not 1 <= int(blue) <= 16:
            return False
        if not isinstance(group.get("strategy"), str) or not group["strategy"] or not isinstance(group.get("description"), str):
            return False
        group_ids.add(gid)
        combinations.add(tuple(reds))
    return True


def _input_fingerprint(lottery_data, template):
    from prediction_rules import __file__ as rules_file
    inputs = {
        "history": lottery_data["data"], "next_draw": lottery_data["next_draw"],
        "models": MODELS, "prompt": template, "version": GENERATOR_VERSION,
        "rules_hash": hashlib.sha256(Path(rules_file).read_bytes()).hexdigest(),
    }
    return hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _prediction_cutoff(period, draw_date):
    if not isinstance(period, str) or not re.fullmatch(r"[0-9]{5}", period):
        raise PredictionValidationError("下期期号缺失或非法")
    if not isinstance(draw_date, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", draw_date):
        raise PredictionValidationError("下期开奖日期缺失或非法")
    return datetime.fromisoformat(draw_date + "T21:15:00").replace(tzinfo=ZoneInfo("Asia/Shanghai"))


def _ensure_before_draw(predictions):
    cutoff = _prediction_cutoff(predictions.get("target_period"), predictions.get("prediction_date"))
    if get_now_shanghai() >= cutoff:
        raise PredictionValidationError("已到开奖时间，停止保存本期预测，请先更新真实开奖数据")


def _validate_complete_prediction(predictions):
    if not isinstance(predictions, dict) or predictions.get("status") != "complete":
        raise PredictionValidationError("拒绝保存未完整生成的预测")
    period, draw_date = predictions.get("target_period"), predictions.get("prediction_date")
    _prediction_cutoff(period, draw_date)
    models = predictions.get("models")
    expected = {model["model_id"]: model for model in MODELS}
    if (not isinstance(models, list) or len(models) != len(expected)
            or any(not _valid_saved_model(model) for model in models)
            or {model["model_id"] for model in models} != set(expected)):
        raise PredictionValidationError("拒绝保存缺失、重复或不合法的模型结果")
    for model in models:
        config = expected[model["model_id"]]
        if (model.get("validation_status") != "passed" or model.get("target_period") != period
                or model.get("prediction_date") != draw_date or model.get("requested_model") != config["id"]
                or model.get("model_name") != config["name"]
                or any(group["strategy"] != STRATEGIES[group["group_id"]]
                       or not 0 < len(group["description"]) <= 100 for group in model["predictions"])):
            raise PredictionValidationError("拒绝保存校验状态、策略或模型元数据不一致的预测")


def generate_predictions():
    lottery_data, template = load_lottery_history(), load_prompt_template()
    history = lottery_data.get("data", [])
    if not history:
        raise ValueError("没有真实开奖历史，禁止生成预测")
    next_draw = lottery_data.get("next_draw", {})
    target_period, target_date = next_draw.get("next_period"), next_draw.get("next_date")
    cutoff = _prediction_cutoff(target_period, target_date)
    if (target_period <= max(d["period"] for d in history)
            or target_date <= max(d["date"] for d in history) or get_now_shanghai() >= cutoff):
        raise ValueError("下期开奖信息已过期，请先更新真实开奖数据")

    plan = build_prediction_plan(history)
    fingerprint = _input_fingerprint(lottery_data, template)
    if Path(AI_PREDICTIONS_FILE).exists():
        existing = json.loads(Path(AI_PREDICTIONS_FILE).read_text(encoding="utf-8"))
        if (existing.get("target_period") == target_period and existing.get("input_fingerprint") == fingerprint
                and existing.get("prediction_date") == target_date):
            try:
                _validate_complete_prediction(existing)
            except ValueError:
                pass
            else:
                raise AlreadyGenerated(f"第 {target_period} 期相同输入的完整预测已存在，无需再次调用模型")

    prompt = template.format(target_period=target_period, target_date=target_date, candidate_plan=format_plan(plan))
    client = get_openai_client()
    models, failures = [], []
    try:
        for config in MODELS:
            try:
                model = call_ai_model_with_retry(client, config, prompt, plan)
                model["target_period"], model["prediction_date"] = target_period, target_date
                models.append(model)
            except Exception as error:
                status = getattr(error, "status_code", None)
                if status in (401, 403):
                    raise RuntimeError(f"API 鉴权失败（{status}），请检查 AI_API_KEY/AI_BASE_URL") from error
                failures.append(f"{config['id']}: {type(error).__name__}")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    if failures or len(models) != len(MODELS):
        raise RuntimeError("模型未全部成功，保留已有预测：" + "; ".join(failures))
    return {
        "prediction_date": target_date, "target_period": target_period,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator_version": GENERATOR_VERSION, "input_fingerprint": fingerprint,
        "status": "complete", "failures": [], "models": models,
    }


def calculate_hit_result(prediction_group, actual_result):
    red_hits = [b for b in prediction_group["red_balls"] if b in actual_result["red_balls"]]
    blue_hit = prediction_group["blue_ball"] == actual_result["blue_ball"]
    return {"red_hits": red_hits, "red_hit_count": len(red_hits), "blue_hit": blue_hit,
            "total_hits": len(red_hits) + int(blue_hit)}


def atomic_write_json(path, document):
    path, temporary = Path(path), None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix="." + path.name, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def archive_old_prediction(lottery_data):
    if not Path(AI_PREDICTIONS_FILE).exists():
        return
    old = json.loads(Path(AI_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    period = old.get("target_period")
    if not isinstance(period, str) or not re.fullmatch(r"[0-9]{5}", period):
        raise ValueError("旧预测期号非法，停止覆盖")
    draws = lottery_data.get("data", [])
    if not draws or period > max(draw["period"] for draw in draws):
        return
    history = {"predictions_history": []}
    if Path(PREDICTIONS_HISTORY_FILE).exists():
        history = json.loads(Path(PREDICTIONS_HISTORY_FILE).read_text(encoding="utf-8"))
    records = history.get("predictions_history")
    if not isinstance(records, list):
        raise ValueError("历史预测格式非法，停止覆盖")
    existing = next((r for r in records if r["target_period"] == period), None)
    if existing:
        if existing.get("data_source") == "random_simulation":
            raise ValueError("该期已有历史补录，需核对真实预测后才能替换")
        return
    actual = next((d for d in draws if d["period"] == period), None)
    if actual is None:
        raise ValueError(f"缺少第 {period} 期真实开奖结果，停止覆盖旧预测")
    models = old.get("models")
    if not isinstance(models, list) or not models or not all(_valid_saved_model(m) for m in models):
        raise ValueError("旧预测号码/结构非法，停止覆盖以便人工核对")
    archived = copy.deepcopy(models)
    for model in archived:
        for group in model["predictions"]:
            group["hit_result"] = calculate_hit_result(group, actual)
        best = max(model["predictions"], key=lambda p: p["hit_result"]["total_hits"])
        model["best_group"], model["best_hit_count"] = best["group_id"], best["hit_result"]["total_hits"]
    record = {"prediction_date": old.get("prediction_date"), "target_period": period,
              "actual_result": actual, "models": archived}
    for key in ("generated_at", "generator_version", "input_fingerprint"):
        if key in old:
            record[key] = old[key]
    records.insert(0, record)
    atomic_write_json(PREDICTIONS_HISTORY_FILE, history)


def save_predictions(predictions):
    _validate_complete_prediction(predictions)
    _ensure_before_draw(predictions)
    path = Path(AI_PREDICTIONS_FILE)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        backup = path.with_name(path.stem + "_backup_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + path.suffix)
        atomic_write_json(backup, old)
    _ensure_before_draw(predictions)
    atomic_write_json(path, predictions)


def main():
    try:
        predictions = generate_predictions()
        if not predictions:
            raise RuntimeError("未生成有效预测")
        _validate_complete_prediction(predictions)
        _ensure_before_draw(predictions)
        archive_old_prediction(load_lottery_history())
        save_predictions(predictions)
        print(f"✅ 第 {predictions['target_period']} 期 {len(predictions['models'])} 个模型全部通过校验并保存")
        return 0
    except AlreadyGenerated as message:
        print(f"ℹ️ {message}")
        return 0
    except Exception as error:
        print(f"❌ 预测生成失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
