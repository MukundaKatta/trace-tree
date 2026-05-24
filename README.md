# trace-tree

Render an agent JSONL audit log as an ASCII tree. Zero dependencies. Reads the shapes already produced by [agenttrace](https://github.com/MukundaKatta/agenttrace-foundry), [agentleash](https://github.com/MukundaKatta/agentleash), [agentsnap](https://github.com/MukundaKatta/AgentSnap), [agent-step-log], and generic `parent_id` JSONL.

```bash
pip install trace-tree
```

## Why

You ran your agent overnight. It produced a thousand lines of JSONL. You open the file and your eyes glaze over.

`trace-tree` reads the file once and prints a tree:

```
session-abc12 [4.99 USD, 1 call, 850 ms]
├─ session_open [ts=1779638601.262143]
├─ tool_ok locus.payments.charge [4.99 USD, 12 ms]
│  └─ args_hash=aeff9a9ed25b8e06
├─ budget_denied locus.payments.charge [7.00 USD attempted, 1 ms]
│  └─ error="budget exceeded: 11.99 > 10"
├─ tool_denied locus.payments.charge
│  └─ error="args invalid: -1.0 < min 0.5"
├─ egress_denied
│  ├─ url=https://evil.attacker.example/exfil
│  └─ error="host not in allowlist"
└─ session_close [4.99 USD]
```

That is the entire pitch. You can read the run.

## CLI

```bash
trace-tree runs/audit.jsonl
trace-tree runs/audit.jsonl --parent-key parent_span_id
trace-tree runs/audit.jsonl --ascii --no-timing
python -m trace_tree runs/audit.jsonl --show-args
```

## Library

```python
from trace_tree import render_file, render_lines, Tree

# Quick CLI-style use
print(render_file("runs/audit.jsonl"))

# Composable
tree = Tree.from_jsonl("runs/audit.jsonl", session_key="session_id", parent_key=None)
print(tree.render(max_depth=10, show_timing=True, show_args=False))
```

## What it recognizes

The parser maps a bunch of common field names onto one normalized `Event` shape. If your records have any of these, you are covered:

| concept | accepted keys |
|---|---|
| event kind | `kind`, `event`, `type`, `step`, `name` |
| timestamp | `ts`, `timestamp`, `time`, `t` |
| tool name | `tool`, `tool_name`, `function`, `name` |
| parent id | `parent_span_id`, `parent_id`, `parent` |
| own id | `span_id`, `id`, `step_id` |
| session id | `session_id`, `run_id`, `trace_id`, `session` |
| cost | `usd`, `cost_usd`, `cost`, `price_usd` |
| latency | `latency_ms`, `duration_ms`, `elapsed_ms`, `ms` (top level or under `extra`) |
| error | `error`, `err`, `message` (top level or under `extra`) |
| url | `url`, `endpoint`, `host` |
| args | `args`, `arguments`, `input`, `params`, `args_hash` |

Unknown shapes still render. The Event row just collapses to its kind.

### Two construction modes

- Default: events are grouped by `session_id`. Each session becomes a root.
- Parent chain: pass `parent_key="parent_span_id"` (or `parent_id`) and trace-tree builds a real parent-child tree.

## API

```python
from trace_tree import Event, Tree, parse_file, parse_lines, render_file, render_lines
```

- `parse_file(path)` -> `list[Event]`
- `parse_lines(iterable_of_strings)` -> `list[Event]`
- `Tree.from_jsonl(path, session_key="session_id", parent_key=None)`
- `Tree.from_events(events, session_key=..., parent_key=...)`
- `tree.render(max_depth=100, show_timing=True, show_args=False, ascii_only=False)` -> `str`
- `render_file(...)` and `render_lines(...)` are one-shot wrappers around both steps.

## Companions

`trace-tree` is the read-side of a small stack:

- [agenttrace](https://github.com/MukundaKatta/agenttrace-foundry) writes the audit log.
- [agentleash](https://github.com/MukundaKatta/agentleash) writes a stricter audit log (budget + egress + arg validation).
- [agentsnap](https://github.com/MukundaKatta/AgentSnap) snapshots tool-call traces.

You can mix them. trace-tree accepts all three shapes in the same file.

## License

MIT
