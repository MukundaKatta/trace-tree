"""Read JSONL audit log files and normalize records into Event objects.

Recognizes a handful of common shapes:

* agenttrace: kind, tool, latency_ms, cost_usd, parent_span_id
* agentleash audit log: ts, session_id, kind, tool, args_hash, usd, error
* agentsnap traces: a top-level run with a steps list (each step is a tool call)
* agent-step-log: ts, step, role, content
* generic JSONL with parent_id or parent_span_id

Anything we do not recognize gets a best-effort normalize so the tree still
renders something useful.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# Field aliases. The first hit wins.
_KIND_KEYS = ("kind", "event", "type", "step", "name")
_TS_KEYS = ("ts", "timestamp", "time", "t")
_TOOL_KEYS = ("tool", "tool_name", "function", "name")
_PARENT_KEYS = ("parent_span_id", "parent_id", "parent")
_ID_KEYS = ("span_id", "id", "step_id")
_SESSION_KEYS = ("session_id", "run_id", "trace_id", "session")
_USD_KEYS = ("usd", "cost_usd", "cost", "price_usd")
_LATENCY_KEYS = ("latency_ms", "duration_ms", "elapsed_ms", "ms")
_ERROR_KEYS = ("error", "err", "message")
_URL_KEYS = ("url", "endpoint", "host")
_ARGS_KEYS = ("args", "arguments", "input", "params", "args_hash")


@dataclass
class Event:
    """A single normalized record from the audit log.

    Fields are deliberately loose. Most logs only fill a subset.
    """

    raw: dict[str, Any]
    ts: float | None = None
    kind: str = "event"
    tool: str | None = None
    session_id: str | None = None
    span_id: str | None = None
    parent_id: str | None = None
    usd: float = 0.0
    latency_ms: float | None = None
    error: str | None = None
    url: str | None = None
    args: Any = None
    args_hash: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _first(d: dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def normalize(record: dict[str, Any]) -> Event:
    """Coerce one JSON record into an Event. Unknown shapes still flow through."""
    kind = _to_str(_first(record, _KIND_KEYS)) or "event"
    tool = _to_str(_first(record, _TOOL_KEYS))

    # args_hash gets its own field because agentleash and agenttrace both ship it.
    args_hash = _to_str(record.get("args_hash"))
    # Pull args from the most specific key that is NOT args_hash.
    args_val: Any = None
    for k in _ARGS_KEYS:
        if k == "args_hash":
            continue
        if k in record and record[k] is not None:
            args_val = record[k]
            break

    # latency: agenttrace ships latency_ms, agentleash sometimes ships duration_ms
    # in extra. Try the top level first.
    latency = _to_float(_first(record, _LATENCY_KEYS))
    if latency is None and isinstance(record.get("extra"), dict):
        latency = _to_float(_first(record["extra"], _LATENCY_KEYS))

    # error: agentleash sometimes nests it under extra too
    error = _to_str(_first(record, _ERROR_KEYS))
    if error is None and isinstance(record.get("extra"), dict):
        error = _to_str(_first(record["extra"], _ERROR_KEYS))

    return Event(
        raw=record,
        ts=_to_float(_first(record, _TS_KEYS)),
        kind=kind,
        tool=tool,
        session_id=_to_str(_first(record, _SESSION_KEYS)),
        span_id=_to_str(_first(record, _ID_KEYS)),
        parent_id=_to_str(_first(record, _PARENT_KEYS)),
        usd=_to_float(_first(record, _USD_KEYS)) or 0.0,
        latency_ms=latency,
        error=error,
        url=_to_str(_first(record, _URL_KEYS)),
        args=args_val,
        args_hash=args_hash,
        extra=record.get("extra") if isinstance(record.get("extra"), dict) else {},
    )


def _explode_agentsnap(record: dict[str, Any]) -> list[Event]:
    """Some snapshots are a single object containing a steps list. Walk it."""
    out: list[Event] = []
    session = _to_str(_first(record, _SESSION_KEYS)) or _to_str(record.get("name"))
    if session:
        out.append(
            normalize(
                {"kind": "session_open", "session_id": session, "ts": record.get("ts")}
            )
        )
    steps = record.get("steps")
    if isinstance(steps, list):
        for s in steps:
            if not isinstance(s, dict):
                continue
            ev = normalize(s)
            if ev.session_id is None:
                ev.session_id = session
            out.append(ev)
    return out


def parse_lines(lines: Iterable[str]) -> list[Event]:
    """Parse an iterable of JSONL lines into Events. Blank lines are skipped."""
    events: list[Event] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Keep bad lines visible so the tree shows there was data we could not read.
            events.append(
                Event(raw={"_raw": line}, kind="parse_error", error="invalid json")
            )
            continue
        if isinstance(obj, dict) and isinstance(obj.get("steps"), list):
            events.extend(_explode_agentsnap(obj))
        elif isinstance(obj, dict):
            events.append(normalize(obj))
        else:
            events.append(Event(raw={"_raw": obj}, kind="event"))
    return events


def parse_file(path: str | Path) -> list[Event]:
    """Read a .jsonl file and return normalized events."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        return parse_lines(fh)
