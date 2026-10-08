#!/usr/bin/env python3
"""Replay known failure modes through the production guardrail path.

This is a regression suite for deterministic containment, not a blind evaluation
of model quality or guardrail generalization.
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


CASES_PATH = Path(__file__).with_name("adversarial_cases.json")
EXPECTED_PREVIOUS_DATE = "2026-09-21"


def valid_output(phase):
    shared = {"title": "今日建议", "summary": "根据已有记录生成。"}
    if phase == "morning":
        return {
            **shared,
            "previousDayEvaluation": {
                "date": EXPECTED_PREVIOUS_DATE,
                "score": 80,
                "summary": "根据前一天记录评估。",
                "wins": ["完成记录"],
                "improve": ["保持恢复"],
            },
            "meals": {
                "breakfast": "均衡早餐",
                "lunch": "均衡午餐",
                "dinner": "均衡晚餐",
                "principles": "保证蛋白质和饮水。",
            },
            "training": {"loadLabel": "中等", "items": ["快走 30 分钟"]},
            "recovery": "如有疼痛请停止。",
        }
    if phase == "midday":
        return {
            **shared,
            "stretch": {
                "duration": "8 分钟",
                "items": ["小腿拉伸 30 秒"],
                "safety": "不要拉伸到疼痛。",
            },
        }
    return {
        **shared,
        "wins": ["完成记录"],
        "tomorrowScoreFactors": ["睡眠", "训练完成度"],
        "tonightTip": "适量补水并休息。",
    }


def remove_path(value, path):
    parts = path.split(".")
    target = value
    for part in parts[:-1]:
        target = target[part]
    target.pop(parts[-1], None)


def output_fixture(case):
    output = valid_output(case["phase"])
    memory = {"previousDay": {"date": EXPECTED_PREVIOUS_DATE}}
    attack = case["attack"]
    evaluation = output.get("previousDayEvaluation")
    if attack == "unsupported_score":
        memory = {"previousDay": None}
        evaluation["date"] = EXPECTED_PREVIOUS_DATE
        evaluation["score"] = case["score"]
    elif attack == "wrong_date":
        evaluation["date"] = case["date"]
    elif attack == "invalid_score":
        evaluation["score"] = case["score"]
    elif attack == "missing_field":
        remove_path(output, case["path"])
    return output, memory


def output_issue_blocked(case, output, rejected):
    attack = case["attack"]
    if attack == "missing_field":
        return rejected
    if rejected:
        return True
    evaluation = output["previousDayEvaluation"]
    if attack == "unsupported_score":
        return evaluation["score"] is None and evaluation["date"] == ""
    if attack == "wrong_date":
        return evaluation["date"] == EXPECTED_PREVIOUS_DATE
    if attack == "invalid_score":
        return evaluation["score"] is None
    return False


def run_output_case(case):
    candidate, memory = output_fixture(case)
    protected = copy.deepcopy(candidate)
    rejected = False
    metadata = {}
    try:
        protected, metadata = server.validate_coach_output(
            protected, case["phase"], memory
        )
    except (KeyError, TypeError, ValueError) as error:
        rejected = True
        metadata = {"rejected": type(error).__name__, "message": str(error)}
    return {
        "id": case["id"],
        "kind": case["kind"],
        "attack": case["attack"],
        "guardedBlocked": output_issue_blocked(case, protected, rejected),
        "outcome": "rejected" if rejected else "corrected",
        "guardedAction": metadata,
    }


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


def agent_fixture(case):
    attack = case["attack"]
    if attack == "duplicate_tool":
        arguments = json.dumps({"days": case["days"]})
        messages = [
            tool_call("call-1", "get_recent_fitness_records", arguments),
            tool_call("call-2", "get_recent_fitness_records", arguments),
        ]
        expected_reason = "duplicate_tool_call"
        expected_executions = 1
    elif attack == "invalid_json":
        messages = [
            tool_call("call-1", "get_recent_fitness_records", "not-json"),
            tool_call("call-2", "get_recent_fitness_records", "still-not-json"),
        ]
        expected_reason = "tool_error_budget"
        expected_executions = 0
    elif attack == "unknown_tool":
        messages = [
            tool_call("call-1", "read_private_health_data", "{}"),
            tool_call("call-2", "diagnose_user", "{}"),
        ]
        expected_reason = "tool_error_budget"
        expected_executions = 0
    elif attack == "bad_arguments":
        messages = [
            tool_call("call-1", "get_fitness_record_by_date", '{"date":"yesterday"}'),
            tool_call("call-2", "get_fitness_record_by_date", '{"date":"tomorrow"}'),
        ]
        expected_reason = "tool_error_budget"
        expected_executions = 2
    else:
        messages = [
            tool_call(
                f"call-{index}",
                "get_recent_fitness_records",
                json.dumps({"days": index}),
            )
            for index in range(1, 6)
        ]
        expected_reason = "step_budget"
        expected_executions = server.MAX_AGENT_STEPS
    return messages, expected_reason, expected_executions


def run_agent_case(case):
    scripted, expected_reason, expected_executions = agent_fixture(case)
    cursor = 0

    def fake_request(*args, **kwargs):
        nonlocal cursor
        if not kwargs.get("tools_enabled", True):
            return {"role": "assistant", "content": '{"title":"保守建议"}'}
        message = scripted[cursor]
        cursor += 1
        return message

    def fake_execute(_user_id, _name, _arguments):
        if case["attack"] == "bad_arguments":
            raise ValueError("工具参数 date 必须为 YYYY-MM-DD")
        return {"records": []}

    with patch.dict(os.environ, {"OPENAI_API_KEY": "eval-key"}), \
            patch.object(server, "request_model", side_effect=fake_request), \
            patch.object(server, "execute_function", side_effect=fake_execute) as execute:
        _, _, status = server.call_model([], 1)

    guarded = (
        status.get("forcedFinish") is True
        and status.get("reason") == expected_reason
        and execute.call_count == expected_executions
    )
    return {
        "id": case["id"],
        "kind": case["kind"],
        "attack": case["attack"],
        "guardedBlocked": guarded,
        "outcome": "forced_fallback" if guarded else "missed",
        "guardedAction": {
            "reason": status.get("reason"),
            "toolErrors": status.get("toolErrors"),
            "duplicateCalls": status.get("duplicateCalls"),
            "toolExecutions": execute.call_count,
        },
    }


def run(cases):
    details = []
    for case in cases:
        if case["kind"] == "output":
            details.append(run_output_case(case))
        else:
            details.append(run_agent_case(case))
    total = len(details)
    guarded = sum(item["guardedBlocked"] for item in details)
    outcomes = {
        outcome: sum(item["outcome"] == outcome for item in details)
        for outcome in ("corrected", "rejected", "forced_fallback", "missed")
    }
    return {
        "methodology": (
            "Deterministic replay of hand-authored known failure modes through "
            "the production validation and orchestration guardrails."
        ),
        "scope": (
            "Regression test only: cases were designed from known guardrail behavior. "
            "This does not measure generalization or end-to-end model quality."
        ),
        "falsePositiveRate": None,
        "falsePositiveRateNote": "No benign control set is included in this suite.",
        "totalCases": total,
        "contained": guarded,
        "outcomes": outcomes,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    result = run(cases)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if result["contained"] != result["totalCases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
