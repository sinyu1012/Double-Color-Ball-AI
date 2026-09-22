"""预测生成的离线回归测试；所有网络调用均替换，文件仅写入临时目录。"""

import copy
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

import generate_ai_prediction as generator


MODEL = {"id": "test-model", "name": "Test Model", "model_id": "test-team"}


def make_plan():
    options = {}
    for group_id in range(1, 6):
        options[group_id] = []
        for index in range(1, 3):
            reds = [group_id + offset for offset in (0, 5, 10, 15, 20, 25)]
            reds[-1] += index - 1
            options[group_id].append({
                "candidate_id": f"g{group_id}-c{index}",
                "group_id": group_id,
                "strategy": generator.STRATEGIES[group_id],
                "red_balls": [f"{number:02d}" for number in reds],
                "blue_ball": f"{group_id:02d}",
                "description": f"程序计算的第 {group_id} 组说明",
            })
    return {"options": options, "adjustments": [], "target_period": "26110"}


def selections(group_ids=range(1, 6), candidate_index=1):
    return {"selections": [
        {"group_id": group_id, "candidate_id": f"g{group_id}-c{candidate_index}"}
        for group_id in group_ids
    ]}


def prediction_document(period="26110"):
    plan = make_plan()
    return {
        "target_period": period,
        "prediction_date": "2026-09-22",
        "generated_at": "2026-09-21T12:00:00+08:00",
        "status": "complete",
        "failures": [],
        "models": [{
            "model_id": MODEL["model_id"],
            "model_name": MODEL["name"],
            "requested_model": MODEL["id"],
            "target_period": period,
            "prediction_date": "2026-09-22",
            "validation_status": "passed",
            "predictions": [copy.deepcopy(plan["options"][gid][0]) for gid in range(1, 6)],
        }],
    }


class APIStatusError(Exception):
    def __init__(self, status_code, body=None, request_id=None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.request_id = request_id


class SelectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()

    def test_five_known_candidates_are_valid(self):
        valid, errors = generator.resolve_selections(selections(), self.plan)
        self.assertEqual(errors, [])
        self.assertEqual(valid, {gid: f"g{gid}-c1" for gid in range(1, 6)})

    def test_malformed_top_level_is_reported_without_crashing(self):
        for payload in (None, [], "text", {}, {"selections": None}, {"selections": {}},
                        {"selections": [None]}, {"selections": [True]}):
            with self.subTest(payload=payload):
                valid, errors = generator.resolve_selections(payload, self.plan)
                self.assertTrue(errors)
                self.assertNotEqual(set(valid), set(range(1, 6)))

    def test_duplicate_group_invalidates_the_ambiguous_group(self):
        payload = selections()
        payload["selections"].append({"group_id": 1, "candidate_id": "g1-c2"})
        valid, errors = generator.resolve_selections(payload, self.plan)
        self.assertTrue(errors)
        self.assertNotIn(1, valid)
        self.assertEqual(set(valid), {2, 3, 4, 5})

    def test_unknown_candidate_cannot_inject_balls_or_switch_strategy(self):
        payload = selections()
        payload["selections"][0].update({
            "candidate_id": "invented", "red_balls": ["01"], "strategy": "热号",
        })
        valid, errors = generator.resolve_selections(payload, self.plan)
        self.assertTrue(errors)
        self.assertNotIn(1, valid)

    def test_candidate_from_another_group_is_rejected(self):
        payload = selections()
        payload["selections"][1]["candidate_id"] = "g1-c1"
        valid, errors = generator.resolve_selections(payload, self.plan)
        self.assertTrue(errors)
        self.assertNotIn(2, valid)

    def test_boolean_or_fractional_group_id_is_not_silently_coerced(self):
        for bad_group_id in (True, 1.5, None, 0, 6):
            with self.subTest(group_id=bad_group_id):
                payload = selections()
                payload["selections"][0]["group_id"] = bad_group_id
                valid, errors = generator.resolve_selections(payload, self.plan)
                self.assertTrue(errors)
                self.assertNotIn(1, valid)

    def test_identical_red_combinations_across_groups_cannot_pass(self):
        self.plan["options"][2][0]["red_balls"] = list(self.plan["options"][1][0]["red_balls"])
        valid, errors = generator.resolve_selections(selections(), self.plan)
        self.assertTrue(errors)
        self.assertFalse(1 in valid and 2 in valid)


class ModelRetryTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.prompt = generator.load_prompt_template().format(
            target_period="26110", target_date="2026-09-22",
            candidate_plan=json.dumps(self.plan, ensure_ascii=False),
        )

    def run_model(self, max_retries=2):
        return generator.call_ai_model_with_retry(object(), MODEL, self.prompt, self.plan,
                                                  max_retries=max_retries)

    def test_canonical_fields_come_from_configuration_and_precomputed_candidates(self):
        payload = selections()
        payload.update({"model_id": "fake", "model_name": "fake", "predictions": []})
        payload["selections"][0].update({"red_balls": ["99"], "description": "凭空编造统计"})
        with mock.patch.object(generator, "call_ai_model", return_value=payload) as call:
            result = self.run_model()
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["model_id"], MODEL["model_id"])
        self.assertEqual(result["model_name"], MODEL["name"])
        self.assertEqual(result["requested_model"], MODEL["id"])
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual([group["group_id"] for group in result["predictions"]], list(range(1, 6)))
        for group in result["predictions"]:
            canonical = self.plan["options"][group["group_id"]][0]
            for field in ("strategy", "red_balls", "blue_ball", "description"):
                self.assertEqual(group[field], canonical[field])

    def test_exhausted_invalid_responses_raise_instead_of_returning_last_result(self):
        with mock.patch.object(generator, "call_ai_model", return_value={"predictions": None}) as call:
            with self.assertRaises(generator.PredictionValidationError):
                self.run_model()
        self.assertEqual(call.call_count, 3)

    def test_only_failed_group_needs_to_be_replied_to_on_retry(self):
        first = selections()
        first["selections"][-1]["candidate_id"] = "invented"
        with mock.patch.object(generator, "call_ai_model",
                               side_effect=[first, selections([5], candidate_index=2)]) as call:
            result = self.run_model()
        self.assertEqual(call.call_count, 2)
        groups = {group["group_id"]: group for group in result["predictions"]}
        for group_id in range(1, 5):
            self.assertEqual(groups[group_id]["red_balls"], self.plan["options"][group_id][0]["red_balls"])
        self.assertEqual(groups[5]["red_balls"], self.plan["options"][5][1]["red_balls"])
        retry_prompt = call.call_args_list[1].args[2]
        self.assertNotEqual(retry_prompt, call.call_args_list[0].args[2])
        self.assertTrue(retry_prompt.startswith(self.prompt + "\n\n"))
        context = json.loads(retry_prompt.split("修复上下文：\n", 1)[1])
        self.assertEqual(context["pending_group_ids"], [5])
        self.assertEqual(set(context["candidates"]), {"5"})
        self.assertEqual(context["locked_groups"], [
            {key: self.plan["options"][gid][0][key]
             for key in ("group_id", "candidate_id", "red_balls", "blue_ball")}
            for gid in range(1, 5)
        ])
        self.assertIn("g1-c1", retry_prompt)
        self.assertIn("invented", retry_prompt)

    def test_invalid_json_is_retried_with_feedback(self):
        error = json.JSONDecodeError("invalid JSON", "not json", 0)
        with mock.patch.object(generator, "call_ai_model", side_effect=[error, selections()]) as call:
            result = self.run_model()
        self.assertEqual(call.call_count, 2)
        self.assertEqual(len(result["predictions"]), 5)
        retry_prompt = call.call_args_list[1].args[2]
        self.assertIn("JSON", retry_prompt)
        self.assertTrue(retry_prompt.startswith(self.prompt + "\n\n"))
        context = json.loads(retry_prompt.split("修复上下文：\n", 1)[1])
        self.assertEqual(context["pending_group_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(context["locked_groups"], [])

    def test_malformed_response_is_retried_before_any_normalization(self):
        for malformed in (None, [], {"selections": None}):
            with self.subTest(payload=malformed):
                with mock.patch.object(generator, "call_ai_model",
                                       side_effect=[malformed, selections()]) as call:
                    result = self.run_model()
                self.assertEqual(call.call_count, 2)
                self.assertEqual(len(result["predictions"]), 5)

    def test_repair_response_cannot_replace_previously_valid_groups(self):
        first = selections()
        first["selections"][-1]["candidate_id"] = "invented"
        with mock.patch.object(generator, "call_ai_model",
                               side_effect=[first, selections(candidate_index=2),
                                            selections([5], candidate_index=2)]) as call:
            result = self.run_model()
        self.assertEqual(call.call_count, 3)
        for retry_call in call.call_args_list[1:]:
            retry_prompt = retry_call.args[2]
            self.assertEqual(retry_prompt.count(self.prompt), 1)
            context = json.loads(retry_prompt.split("修复上下文：\n", 1)[1])
            self.assertEqual(context["pending_group_ids"], [5])
            self.assertEqual([group["candidate_id"] for group in context["locked_groups"]],
                             [f"g{gid}-c1" for gid in range(1, 5)])
        groups = {group["group_id"]: group for group in result["predictions"]}
        for group_id in range(1, 5):
            self.assertEqual(groups[group_id]["red_balls"], self.plan["options"][group_id][0]["red_balls"])
        self.assertEqual(groups[5]["red_balls"], self.plan["options"][5][1]["red_balls"])

    def test_authentication_and_permission_errors_are_not_retried(self):
        for status in (400, 401, 403):
            with self.subTest(status=status):
                with mock.patch.object(generator, "call_ai_model", side_effect=APIStatusError(status)) as call:
                    with self.assertRaises(Exception):
                        self.run_model()
                self.assertEqual(call.call_count, 1)

    def test_transient_errors_have_bounded_backoff_and_stop_after_budget(self):
        for error in (APIStatusError(429), APIStatusError(503), TimeoutError("request timed out")):
            with self.subTest(error=error):
                with mock.patch.object(generator, "call_ai_model", side_effect=error) as call, \
                        mock.patch.object(generator.time, "sleep") as sleep:
                    with self.assertRaises((RuntimeError, ValueError, APIStatusError, TimeoutError)):
                        self.run_model()
                self.assertEqual(call.call_count, 3)
                self.assertEqual(sleep.call_count, 2)
                for sleep_call in sleep.call_args_list:
                    self.assertGreater(sleep_call.args[0], 0)
                    self.assertLessEqual(sleep_call.args[0], 60)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.current = self.directory / "ai_predictions.json"
        self.archive = self.directory / "predictions_history.json"
        self.original = prediction_document("26109")
        self.current.write_text(json.dumps(self.original, ensure_ascii=False), encoding="utf-8")
        self.archive.write_text('{"predictions_history": []}', encoding="utf-8")
        for field, path in (("AI_PREDICTIONS_FILE", self.current), ("PREDICTIONS_HISTORY_FILE", self.archive)):
            patcher = mock.patch.object(generator, field, str(path))
            patcher.start()
            self.addCleanup(patcher.stop)
        for patcher in (
            mock.patch.object(generator, "MODELS", [MODEL]),
            mock.patch.object(generator, "get_now_shanghai",
                              return_value=datetime(2026, 9, 21, 12, tzinfo=ZoneInfo("Asia/Shanghai"))),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def lottery_data(self):
        return {"data": [{
            "period": "26109", "date": "2026-09-20", "red_balls": ["01", "06", "11", "16", "21", "26"],
            "blue_ball": "01",
        }], "next_draw": {
            "next_period": "26110", "next_date": "2026-09-22", "next_date_display": "2026年09月22日",
        }}

    def generation_context(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        fake_models = [MODEL, {"id": "second-model", "name": "Second", "model_id": "second-team"}]
        replacements = {
            "load_lottery_history": self.lottery_data(),
            "load_prompt_template": "期号：{target_period}",
            "get_now_shanghai": datetime(2026, 9, 21, 12, tzinfo=ZoneInfo("Asia/Shanghai")),
            "build_prediction_plan": make_plan(),
            "format_plan": "离线候选",
            "get_openai_client": object(),
        }
        for name, result in replacements.items():
            stack.enter_context(mock.patch.object(generator, name, return_value=result))
        stack.enter_context(mock.patch.object(generator, "MODELS", fake_models))
        return stack

    def test_successful_save_keeps_a_backup_of_previous_document(self):
        new_document = prediction_document()
        generator.save_predictions(new_document)
        self.assertEqual(json.loads(self.current.read_text(encoding="utf-8")), new_document)
        backups = list(self.directory.glob("ai_predictions_backup_*.json"))
        self.assertTrue(backups)
        self.assertTrue(any(json.loads(path.read_text(encoding="utf-8")) == self.original for path in backups))

    def test_incomplete_or_inconsistent_document_is_rejected_before_any_write(self):
        cases = []
        for field, value in (("status", "partial"), ("models", []), ("target_period", None)):
            document = prediction_document()
            document[field] = value
            cases.append(document)
        for field, value in (("target_period", "26109"), ("prediction_date", "2026-09-20"),
                             ("model_id", "unknown"), ("requested_model", "invented-model"),
                             ("model_name", "Invented"), ("validation_status", "failed")):
            document = prediction_document()
            document["models"][0][field] = value
            cases.append(document)
        document = prediction_document()
        document["models"] *= 2
        cases.append(document)
        for document in cases:
            with self.subTest(document=document):
                before = self.current.read_bytes()
                with self.assertRaises(generator.PredictionValidationError):
                    generator.save_predictions(document)
                self.assertEqual(self.current.read_bytes(), before)
                self.assertEqual(list(self.directory.glob("ai_predictions_backup_*.json")), [])

    def test_generation_crossing_draw_time_cannot_archive_or_save(self):
        current_before, archive_before = self.current.read_bytes(), self.archive.read_bytes()
        with mock.patch.object(generator, "generate_predictions", return_value=prediction_document()), \
                mock.patch.object(generator, "get_now_shanghai",
                                  return_value=datetime(2026, 9, 22, 21, 15, tzinfo=ZoneInfo("Asia/Shanghai"))), \
                mock.patch.object(generator, "archive_old_prediction") as archive, \
                mock.patch.object(generator, "save_predictions") as save:
            self.assertEqual(generator.main(), 1)
        archive.assert_not_called()
        save.assert_not_called()
        self.assertEqual(self.current.read_bytes(), current_before)
        self.assertEqual(self.archive.read_bytes(), archive_before)

    def test_crossing_draw_time_during_backup_preserves_current_document(self):
        before = self.current.read_bytes()
        times = [datetime(2026, 9, 22, 21, 14, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
                 datetime(2026, 9, 22, 21, 15, tzinfo=ZoneInfo("Asia/Shanghai"))]
        with mock.patch.object(generator, "get_now_shanghai", side_effect=times):
            with self.assertRaises(generator.PredictionValidationError):
                generator.save_predictions(prediction_document())
        self.assertEqual(self.current.read_bytes(), before)

    def test_serialization_failure_does_not_truncate_existing_prediction(self):
        before = self.current.read_bytes()
        invalid = prediction_document()
        invalid["unserializable"] = object()
        with self.assertRaises((TypeError, ValueError)):
            generator.save_predictions(invalid)
        self.assertEqual(self.current.read_bytes(), before)

    def test_replace_failure_does_not_destroy_existing_prediction(self):
        before = self.current.read_bytes()
        with mock.patch.object(generator.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                generator.save_predictions(prediction_document())
        self.assertEqual(self.current.read_bytes(), before)

    def test_archiving_twice_keeps_one_record_and_preserves_original_file(self):
        before = self.current.read_bytes()
        generator.archive_old_prediction(self.lottery_data())
        generator.archive_old_prediction(self.lottery_data())
        records = json.loads(self.archive.read_text(encoding="utf-8"))["predictions_history"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["target_period"], "26109")
        self.assertEqual(records[0]["models"][0]["predictions"][0]["hit_result"]["total_hits"], 7)
        self.assertEqual(self.current.read_bytes(), before)

    def test_unreadable_archive_fails_instead_of_discarding_existing_history(self):
        self.archive.write_text("broken JSON", encoding="utf-8")
        before = self.current.read_bytes()
        with self.assertRaises(Exception):
            generator.archive_old_prediction(self.lottery_data())
        self.assertEqual(self.current.read_bytes(), before)
        self.assertEqual(self.archive.read_text(encoding="utf-8"), "broken JSON")

    def test_archive_requires_actual_result_before_replacing_an_old_prediction(self):
        lottery = self.lottery_data()
        lottery["data"][0]["period"] = "26110"
        before = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            generator.archive_old_prediction(lottery)
        self.assertEqual(self.archive.read_bytes(), before)

    def test_existing_backfill_is_not_silently_treated_as_archived_real_prediction(self):
        backfill = {
            "target_period": "26109", "prediction_date": None,
            "data_source": "random_simulation", "models": [],
        }
        self.archive.write_text(json.dumps({"predictions_history": [backfill]}), encoding="utf-8")
        before = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            generator.archive_old_prediction(self.lottery_data())
        self.assertEqual(self.archive.read_bytes(), before)

    def test_main_returns_failure_and_never_saves_when_generation_fails(self):
        with mock.patch.object(generator, "generate_predictions", side_effect=RuntimeError("all models failed")), \
                mock.patch.object(generator, "save_predictions") as save:
            self.assertEqual(generator.main(), 1)
        save.assert_not_called()

    def test_main_treats_no_result_as_failure(self):
        with mock.patch.object(generator, "generate_predictions", return_value=None), \
                mock.patch.object(generator, "save_predictions") as save:
            self.assertEqual(generator.main(), 1)
        save.assert_not_called()

    def test_archive_failure_stops_main_before_overwriting_prediction(self):
        self.archive.write_text("broken JSON", encoding="utf-8")
        before = self.current.read_bytes()
        with mock.patch.object(generator, "generate_predictions", return_value=prediction_document()), \
                mock.patch.object(generator, "load_lottery_history", return_value=self.lottery_data()), \
                mock.patch.object(generator, "save_predictions") as save:
            self.assertEqual(generator.main(), 1)
        save.assert_not_called()
        self.assertEqual(self.current.read_bytes(), before)

    def test_all_models_failing_raises_and_preserves_current_document(self):
        self.generation_context()
        before = self.current.read_bytes()
        with mock.patch.object(generator, "call_ai_model_with_retry", side_effect=RuntimeError("model unavailable")), \
                mock.patch.object(generator, "save_predictions") as save:
            with self.assertRaises(RuntimeError):
                generator.generate_predictions()
        save.assert_not_called()
        self.assertEqual(self.current.read_bytes(), before)

    def test_partial_model_failure_is_not_reported_as_full_success(self):
        self.generation_context()
        model_result = prediction_document()["models"][0]
        before = self.current.read_bytes()
        error = APIStatusError(400, body={"error": {
            "message": "Missing required parameter: max_tokens", "param": "max_tokens",
        }}, request_id="request-test-400")
        with mock.patch.object(generator, "call_ai_model_with_retry",
                               side_effect=[model_result, error]) as call:
            with self.assertRaisesRegex(RuntimeError, "HTTP 400.*request-test-400.*max_tokens"):
                generator.generate_predictions()
        self.assertEqual(call.call_count, 2)
        self.assertEqual(self.current.read_bytes(), before)

    def test_api_failure_logs_redact_credentials_and_exclude_unrelated_body_fields(self):
        self.generation_context()
        secret = "test-private-api-key"
        error = APIStatusError(400, body={"error": {
            "message": f"Invalid request\n{secret} Bearer upstream-private-token sk-provider-private-token",
            "code": secret, "param": "model", "headers": "private-header",
        }, "request": "private-request"}, request_id=secret)
        with mock.patch.dict(generator.os.environ, {"AI_API_KEY": secret}), \
                mock.patch.object(generator, "call_ai_model_with_retry", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                generator.generate_predictions()
        output = self.output.getvalue() + str(caught.exception)
        for private in (secret, "upstream-private-token", "sk-provider-private-token",
                        "private-header", "private-request"):
            self.assertNotIn(private, output)
        self.assertIn("[REDACTED]", output)
        self.assertIn("param=model", output)

    def test_successful_same_input_rerun_is_idempotent_without_another_api_call(self):
        self.generation_context()

        def successful_model(_client, model_config, *_args, **_kwargs):
            result = copy.deepcopy(prediction_document()["models"][0])
            result.update({"model_id": model_config["model_id"], "model_name": model_config["name"],
                           "requested_model": model_config["id"]})
            return result

        with mock.patch.object(generator, "call_ai_model_with_retry", side_effect=successful_model) as call:
            generated = generator.generate_predictions()
        self.assertEqual(call.call_count, 2)
        generator.save_predictions(generated)
        before = self.current.read_bytes()
        with mock.patch.object(generator, "call_ai_model_with_retry") as rerun, \
                mock.patch.object(generator, "save_predictions") as save:
            self.assertEqual(generator.main(), 0)
        rerun.assert_not_called()
        save.assert_not_called()
        self.assertEqual(self.current.read_bytes(), before)


class OfflineIntegrationTests(unittest.TestCase):
    def test_real_rules_prompt_and_sdk_response_reach_atomic_save_and_skip_rerun(self):
        lottery = generator.load_lottery_history()
        plan = generator.build_prediction_plan(lottery["data"])
        used, choices = set(), []
        for gid, candidates in plan["options"].items():
            candidate = next(candidate for candidate in candidates
                             if tuple(candidate["red_balls"]) not in used)
            used.add(tuple(candidate["red_balls"]))
            choices.append({"group_id": gid, "candidate_id": candidate["candidate_id"]})

        def respond(**kwargs):
            self.assertIn(lottery["next_draw"]["next_period"], kwargs["messages"][1]["content"])
            self.assertIn("双色球候选组合选择 v4.0", kwargs["messages"][1]["content"])
            self.assertEqual(kwargs["timeout"], 180.0 if kwargs["model"] == "gemini-2.5-flash" else 60.0)
            payload = json.dumps({"selections": choices})
            return SimpleNamespace(model=kwargs["model"] + "-resolved", choices=[
                SimpleNamespace(message=SimpleNamespace(content="```json\n" + payload + "\n```")),
            ])

        client = mock.Mock()
        client.chat.completions.create.side_effect = respond
        target_day = datetime.fromisoformat(lottery["next_draw"]["next_date"])
        now = target_day.replace(hour=12, tzinfo=ZoneInfo("Asia/Shanghai"))
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            current, archive = Path(directory) / "current.json", Path(directory) / "history.json"
            stack.enter_context(mock.patch.object(generator, "AI_PREDICTIONS_FILE", current))
            stack.enter_context(mock.patch.object(generator, "PREDICTIONS_HISTORY_FILE", archive))
            stack.enter_context(mock.patch.object(generator, "get_now_shanghai", return_value=now))
            get_client = stack.enter_context(mock.patch.object(generator, "get_openai_client", return_value=client))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(generator.main(), 0)
            saved = json.loads(current.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "complete")
            self.assertEqual(saved["generator_version"], "4.1")
            claude = next(model for model in saved["models"] if model["model_id"].startswith("claude-"))
            self.assertEqual(claude["model_name"], "Claude Sonnet 4.6")
            self.assertEqual(claude["requested_model"], "claude-sonnet-4-6")
            self.assertEqual(len(saved["models"]), len(generator.MODELS))
            for model in saved["models"]:
                self.assertEqual(model["response_model"], model["requested_model"] + "-resolved")
                self.assertEqual(len(model["predictions"]), 5)
                for group in model["predictions"]:
                    self.assertIn(group, plan["options"][group["group_id"]])
            before = current.read_bytes()
            self.assertEqual(generator.main(), 0)
            self.assertEqual(current.read_bytes(), before)
            self.assertEqual(client.chat.completions.create.call_count, len(generator.MODELS))
            get_client.assert_called_once()
            client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
