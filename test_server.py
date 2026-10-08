import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import server


def tool_call(call_id, name, arguments):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }],
    }


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.api_key = patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
        self.api_key.start()
        self.addCleanup(self.api_key.stop)

    def test_duplicate_tool_call_executes_once_and_forces_finish(self):
        responses = [
            tool_call("call-1", "get_recent_fitness_records", '{"days":7}'),
            tool_call("call-2", "get_recent_fitness_records", '{"days":7}'),
            {"role": "assistant", "content": '{"title":"降级结果"}'},
        ]
        model_calls = []

        def fake_request(*args, **kwargs):
            model_calls.append(kwargs)
            return responses.pop(0)

        with patch.object(server, "request_model", side_effect=fake_request), \
                patch.object(server, "execute_function", return_value={"records": []}) as execute:
            plan, used_tools, status = server.call_model([], 1)

        self.assertEqual(plan["title"], "降级结果")
        self.assertEqual(used_tools, ["get_recent_fitness_records"])
        self.assertEqual(execute.call_count, 1)
        self.assertTrue(status["forcedFinish"])
        self.assertEqual(status["reason"], "duplicate_tool_call")
        self.assertEqual(status["duplicateCalls"], 1)
        self.assertFalse(model_calls[-1]["tools_enabled"])

    def test_tool_error_is_returned_to_model_for_correction(self):
        captured_messages = []
        responses = [
            tool_call("call-1", "get_fitness_record_by_date", '{"date":"bad"}'),
            {"role": "assistant", "content": '{"title":"已修正"}'},
        ]

        def fake_request(*args, **kwargs):
            captured_messages.append(json.loads(json.dumps(args[3])))
            return responses.pop(0)

        with patch.object(server, "request_model", side_effect=fake_request), \
                patch.object(server, "execute_function", side_effect=ValueError("日期格式错误")):
            plan, _, status = server.call_model([], 1)

        tool_result = json.loads(captured_messages[1][-1]["content"])
        self.assertEqual(plan["title"], "已修正")
        self.assertEqual(tool_result["error"]["code"], "INVALID_ARGUMENT")
        self.assertTrue(tool_result["error"]["retryable"])
        self.assertEqual(status["toolErrors"], 1)
        self.assertFalse(status["forcedFinish"])

    def test_error_budget_forces_tool_free_final_response(self):
        responses = [
            tool_call("call-1", "get_recent_fitness_records", "not-json"),
            tool_call("call-2", "get_recent_fitness_records", "still-not-json"),
            {"role": "assistant", "content": '{"title":"保守建议"}'},
        ]
        model_calls = []

        def fake_request(*args, **kwargs):
            model_calls.append(kwargs)
            return responses.pop(0)

        with patch.object(server, "request_model", side_effect=fake_request):
            plan, _, status = server.call_model([], 1)

        self.assertEqual(plan["title"], "保守建议")
        self.assertEqual(status["reason"], "tool_error_budget")
        self.assertEqual(status["toolErrors"], server.MAX_TOOL_ERRORS)
        self.assertFalse(model_calls[-1]["tools_enabled"])


class ModelRequestTests(unittest.TestCase):
    def request_body(self, tools_enabled):
        with patch.object(server, "urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = b'{"choices":[{"message":{"content":"{}"}}]}'
            server.request_model(
                "https://example.com/v1", "test-key", "test-model",
                [{"role": "system", "content": "Return JSON"}],
                tools_enabled=tools_enabled,
            )
            return json.loads(urlopen.call_args.args[0].data)

    def test_tool_request_does_not_combine_tools_with_response_format(self):
        body = self.request_body(tools_enabled=True)
        self.assertIn("tools", body)
        self.assertNotIn("response_format", body)

    def test_tool_free_request_keeps_json_mode(self):
        body = self.request_body(tools_enabled=False)
        self.assertNotIn("tools", body)
        self.assertEqual(body["response_format"], {"type": "json_object"})


class RecordPersistenceTests(unittest.TestCase):
    def create_user(self):
        with server.db() as (connection, placeholder):
            cursor = server.query(
                connection,
                f"INSERT INTO users (email,password_hash,created_at) VALUES ({placeholder},{placeholder},{placeholder})",
                ("test@example.com", "hash", "now"),
            )
            return cursor.lastrowid

    def test_check_in_can_be_saved_before_ai_plan_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "fitness.db")
            with patch.object(server, "DB_PATH", database):
                server.init_db()
                user_id = self.create_user()
                check_in = {"date": "2026-09-22", "morning": {"sleep": "7"}}
                server.save_record(user_id, check_in)
                self.assertEqual(server.list_records(user_id), [check_in])

    def test_facts_and_ai_outputs_are_stored_in_separate_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DB_PATH", os.path.join(directory, "fitness.db")):
                server.init_db()
                user_id = self.create_user()
                record = {
                    "date": "2026-09-22", "goal": "fat-loss", "height": 158,
                    "morning": {"sleep": "7"}, "plan": {"title": "客户端旧计划"},
                }
                server.save_record(user_id, record)
                output = {"title": "服务端计划", "summary": "已验证"}
                metadata = {"dataStatus": "complete", "sources": [{"id": "record:2026-09-22"}]}
                server.save_coach_output(user_id, "2026-09-22", "morning", output, metadata, "test-model")

                facts = server.fact_records(user_id)
                merged = server.list_records(user_id)
                self.assertNotIn("plan", facts[0])
                self.assertEqual(merged[0]["plan"], output)
                self.assertEqual(merged[0]["coachMetadata"]["morning"], metadata)
                self.assertEqual(server.load_profile(user_id)["confirmed"], {"height": 158, "goal": "fat-loss"})

    def test_fixed_memory_retrieves_profile_previous_day_and_server_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DB_PATH", os.path.join(directory, "fitness.db")):
                server.init_db()
                user_id = self.create_user()
                server.save_record(user_id, {
                    "date": "2026-09-21", "goal": "fat-loss", "height": 158,
                    "morning": {"weight": "55.4", "sleep": "6.5", "energy": "3"},
                    "midday": {"exercises": [{"name": "快走", "duration": "30"}], "totalDuration": 30},
                    "evening": {"food": "三餐"},
                })
                server.save_record(user_id, {
                    "date": "2026-09-22", "goal": "fat-loss", "height": 158,
                    "morning": {"weight": "55.1", "sleep": "7", "energy": "4"},
                })

                memory, provenance = server.build_memory_context(user_id, {
                    "phase": "morning", "date": "2026-09-22",
                })

                self.assertEqual(memory["confirmedProfile"]["goal"], "fat-loss")
                self.assertEqual(memory["previousDay"]["date"], "2026-09-21")
                self.assertEqual(memory["recent14DayStats"]["recordCount"], 2)
                self.assertEqual(memory["recent14DayStats"]["weight"]["changeKg"], -0.3)
                self.assertEqual(provenance["dataStatus"], "complete")
                self.assertIn("server_derived_stats", {source["type"] for source in provenance["sources"]})

    def test_resubmitting_one_phase_invalidates_only_that_ai_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DB_PATH", os.path.join(directory, "fitness.db")):
                server.init_db()
                user_id = self.create_user()
                record = {"date": "2026-09-22", "morning": {"sleep": "7"}, "midday": {"totalDuration": 20}}
                server.save_record(user_id, record)
                metadata = {"dataStatus": "complete", "sources": []}
                server.save_coach_output(user_id, record["date"], "morning", {"title": "早间"}, metadata, "test")
                server.save_coach_output(user_id, record["date"], "midday", {"title": "训练后"}, metadata, "test")
                record["_invalidatePhase"] = "midday"
                server.save_record(user_id, record)

                merged = server.list_records(user_id)[0]
                self.assertEqual(merged["plan"]["title"], "早间")
                self.assertNotIn("stretch", merged)

    def test_startup_migrates_legacy_mixed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "fitness.db")
            with patch.object(server, "DB_PATH", database):
                with server.db() as (connection, _):
                    server.query(connection, "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT, created_at TEXT)")
                    server.query(connection, "CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT)")
                    server.query(connection, "CREATE TABLE records (user_id INTEGER, date TEXT, record_json TEXT, created_at TEXT, updated_at TEXT, PRIMARY KEY(user_id,date))")
                    server.query(connection, "INSERT INTO users VALUES (1,'test@example.com','hash','now')")
                    legacy = {"date": "2026-09-22", "goal": "health", "morning": {"sleep": "7"}, "plan": {"title": "旧计划"}}
                    server.query(connection, "INSERT INTO records VALUES (1,'2026-09-22',?,'now','now')", (json.dumps(legacy),))

                server.init_db()

                self.assertNotIn("plan", server.fact_records(1)[0])
                self.assertEqual(server.list_records(1)[0]["plan"]["title"], "旧计划")
                self.assertTrue(server.coach_outputs(1)[0]["metadata"]["migrated"])


class FactValidationTests(unittest.TestCase):
    def test_unverified_previous_day_score_is_removed(self):
        output = {
            "title": "今日计划", "summary": "根据今天状态安排。",
            "previousDayEvaluation": {
                "date": "2026-09-21", "score": 88, "summary": "表现不错。",
                "wins": ["完成训练"], "improve": ["早点休息"],
            },
            "meals": {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "principles": "均衡饮食"},
            "training": {"loadLabel": "中等", "items": ["快走 30 分钟"]},
            "recovery": "如有疼痛请停止。",
        }
        validated, validation = server.validate_coach_output(output, "morning", {"previousDay": None})
        self.assertIsNone(validated["previousDayEvaluation"]["score"])
        self.assertEqual(validated["previousDayEvaluation"]["date"], "")
        self.assertIn("cleared_unverified_previous_day_score", validation["adjustments"])


class RetrievalAndObservabilityTests(unittest.TestCase):
    def test_reranker_combines_similarity_recency_and_keyword_overlap(self):
        candidates = [
            {"date": "2026-09-01", "content": "游泳 30 分钟", "similarity": 0.91},
            {"date": "2026-09-21", "content": "膝盖疼痛 快走", "similarity": 0.88},
            {"date": "2026-09-20", "content": "正常训练", "similarity": 0.70},
        ]
        ranked = server.rerank_candidates(candidates, "今天膝盖疼痛", "2026-09-22", limit=2)
        self.assertEqual(ranked[0]["date"], "2026-09-21")
        self.assertEqual(len(ranked), 2)
        self.assertIn("rerankScore", ranked[0])

    def test_cost_and_nearest_rank_percentile_are_deterministic(self):
        self.assertEqual(server.estimate_cost(1_000_000, 500_000, 0.15, 0.60), 0.45)
        self.assertEqual(server.percentile([10, 20, 30, 40, 50], 95), 50.0)
        self.assertIsNone(server.percentile([], 95))

    def test_trace_persistence_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DB_PATH", os.path.join(directory, "fitness.db")):
                server.init_db()
                with server.db() as (connection, placeholder):
                    cursor = server.query(connection,
                        f"INSERT INTO users (email,password_hash,created_at) VALUES ({placeholder},{placeholder},{placeholder})",
                        ("trace@example.com", "hash", "now"))
                    user_id = cursor.lastrowid
                trace = server.TraceRecorder(user_id, "2026-09-22", "morning")
                trace.started_clock = time.perf_counter() - 0.1
                trace.model = "test-model"
                trace.prompt_tokens = 100
                trace.completion_tokens = 20
                trace.finish("ok")
                server.persist_trace(trace)

                metrics = server.trace_metrics(user_id)
                traces = server.recent_traces(user_id)
                self.assertEqual(metrics["requestCount"], 1)
                self.assertGreaterEqual(metrics["p95LatencyMs"], 100)
                self.assertEqual(metrics["promptTokens"], 100)
                self.assertEqual(traces[0]["traceId"], trace.trace_id)

    def test_embedding_response_records_usage(self):
        response_body = {
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 7, "total_tokens": 7},
        }
        trace = server.TraceRecorder(1, "2026-09-22", "morning")
        with patch.dict(os.environ, {
                "EMBEDDING_API_KEY": "test-key", "EMBEDDING_DIMENSIONS": "3",
                "EMBEDDING_COST_PER_1M": "0.02"}), patch.object(server, "urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = json.dumps(response_body).encode()
            embeddings = server.request_embeddings(["测试"], trace=trace)
        self.assertEqual(embeddings, [[0.1, 0.2, 0.3]])
        self.assertEqual(trace.embedding_tokens, 7)
        self.assertEqual(trace.events[0]["name"], "llm.embedding")

    def test_memory_context_includes_reranked_vector_facts_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DB_PATH", os.path.join(directory, "fitness.db")):
                server.init_db()
                with server.db() as (connection, placeholder):
                    cursor = server.query(connection,
                        f"INSERT INTO users (email,password_hash,created_at) VALUES ({placeholder},{placeholder},{placeholder})",
                        ("vector@example.com", "hash", "now"))
                    user_id = cursor.lastrowid
                server.save_record(user_id, {
                    "date": "2026-09-21", "goal": "health", "height": 158,
                    "morning": {"sleep": "6", "notes": "膝盖疼痛"},
                })
                match = {
                    "date": "2026-09-21",
                    "content": json.dumps({"date": "2026-09-21", "morning": {"notes": "膝盖疼痛"}}),
                    "similarity": 0.9, "rerankScore": 0.88,
                }
                with patch.object(server, "vector_store_enabled", return_value=True), \
                        patch.object(server, "ensure_record_embeddings", return_value={"enabled": True, "indexed": 1}), \
                        patch.object(server, "hybrid_vector_retrieve", return_value=[match]):
                    memory, provenance = server.build_memory_context(user_id, {
                        "phase": "morning", "date": "2026-09-22", "notes": "膝盖不适",
                    })
                self.assertEqual(memory["semanticMatches"][0]["date"], "2026-09-21")
                self.assertEqual(memory["vectorRetrieval"]["retrieved"], 1)
                self.assertIn("hybrid_pgvector_reranked", {item["type"] for item in provenance["sources"]})


if __name__ == "__main__":
    unittest.main()
