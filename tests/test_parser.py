"""Parser shape coverage. Each known shape should round-trip into an Event."""

from __future__ import annotations

import json

from trace_tree.parser import normalize, parse_lines


def test_agentleash_shape_normalizes() -> None:
    raw = {
        "ts": 1779638601.262,
        "session_id": "s1",
        "kind": "tool_ok",
        "tool": "locus.payments.charge",
        "args_hash": "aeff",
        "url": None,
        "usd": 4.99,
        "error": None,
        "extra": {"latency_ms": 12},
    }
    ev = normalize(raw)
    assert ev.kind == "tool_ok"
    assert ev.tool == "locus.payments.charge"
    assert ev.session_id == "s1"
    assert ev.usd == 4.99
    assert ev.args_hash == "aeff"
    assert ev.latency_ms == 12  # pulled from extra


def test_agenttrace_shape_normalizes() -> None:
    raw = {
        "kind": "tool_call",
        "tool": "search",
        "latency_ms": 230,
        "cost_usd": 0.0001,
        "parent_span_id": "root",
        "span_id": "s1",
    }
    ev = normalize(raw)
    assert ev.tool == "search"
    assert ev.latency_ms == 230
    assert ev.usd == 0.0001
    assert ev.parent_id == "root"
    assert ev.span_id == "s1"


def test_agent_step_log_shape_normalizes() -> None:
    raw = {"ts": 1, "step": "thinking", "role": "assistant", "content": "..."}
    ev = normalize(raw)
    assert ev.kind == "thinking"  # step alias
    assert ev.ts == 1


def test_generic_jsonl_with_parent_id() -> None:
    raw = {"id": "a", "parent_id": "root", "type": "noop"}
    ev = normalize(raw)
    assert ev.kind == "noop"
    assert ev.span_id == "a"
    assert ev.parent_id == "root"


def test_agentsnap_steps_explode_into_events() -> None:
    obj = {
        "session_id": "snap1",
        "steps": [
            {"kind": "tool_call", "tool": "search"},
            {"kind": "tool_ok", "tool": "search", "latency_ms": 10},
        ],
    }
    events = parse_lines([json.dumps(obj)])
    # 1 synthetic session_open + 2 steps
    assert len(events) == 3
    assert events[0].kind == "session_open"
    assert events[1].tool == "search"
    assert events[2].latency_ms == 10


def test_parse_lines_handles_blank_lines() -> None:
    lines = ["", '{"kind":"x"}', "  ", '{"kind":"y"}']
    events = parse_lines(lines)
    assert [e.kind for e in events] == ["x", "y"]


def test_parse_lines_keeps_bad_json_as_parse_error() -> None:
    events = parse_lines(['{"kind":"ok"}', "not json"])
    assert events[0].kind == "ok"
    assert events[1].kind == "parse_error"
    assert events[1].error == "invalid json"


def test_normalize_falls_back_to_event_kind_when_missing() -> None:
    ev = normalize({"foo": "bar"})
    assert ev.kind == "event"
    assert ev.usd == 0.0


def test_normalize_coerces_string_usd() -> None:
    ev = normalize({"kind": "x", "usd": "1.25"})
    assert ev.usd == 1.25


def test_url_pulled_when_present() -> None:
    ev = normalize({"kind": "egress_denied", "url": "https://x.example/exfil"})
    assert ev.url == "https://x.example/exfil"
