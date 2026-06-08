"""Build and render a Tree of Events.

Two modes of tree construction:

1. parent_key mode: every event has a parent_id (or parent_span_id). We link
   children directly to parents and the roots are events with no parent.
2. session_key mode: events are flat, grouped by session_id. Each session is
   a root, every event is a direct child of its session. This is what
   agentleash and agent-step-log look like.

The Tree exposes a render() method that walks the structure with the
ASCII box-drawing helpers in render.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .parser import Event, parse_file, parse_lines
from .render import child_prefix, fmt_ms, fmt_usd, prefix


@dataclass
class Node:
    """One position in the rendered tree.

    A node can wrap an Event or be a synthetic session root (event is None
    and label carries the session id).
    """

    label: str
    event: Event | None = None
    children: list["Node"] = field(default_factory=list)
    # Aggregated stats shown next to a session root.
    agg_usd: float = 0.0
    agg_calls: int = 0
    agg_latency_ms: float = 0.0


def _label_for_event(ev: Event, show_timing: bool, show_args: bool) -> str:
    """The text that appears on the line for one event."""
    head = ev.kind
    if ev.tool:
        head = f"{head} {ev.tool}"

    bits: list[str] = []
    if ev.usd:
        bits.append(
            fmt_usd(ev.usd) + " attempted"
            if ev.kind == "budget_denied"
            else fmt_usd(ev.usd)
        )
    if show_timing:
        ms = fmt_ms(ev.latency_ms)
        if ms:
            bits.append(ms)
    if show_args and ev.args is not None and not ev.args_hash:
        # Inline very short args. Long ones go to a child line.
        try:
            inline = json.dumps(ev.args, separators=(",", ":"))
        except (TypeError, ValueError):
            inline = str(ev.args)
        if len(inline) <= 40:
            bits.append(f"args={inline}")

    if ev.ts is not None and not bits:
        # Only show ts inline when there is no other useful info, to keep
        # the line compact. Matches the example output.
        bits.append(f"ts={ev.ts}")

    if bits:
        return f"{head} [{', '.join(bits)}]"
    return head


def _detail_lines(ev: Event, show_args: bool) -> list[str]:
    """Lines that hang as children of an event for extra detail."""
    out: list[str] = []
    if ev.args_hash:
        out.append(f"args_hash={ev.args_hash}")
    if ev.url:
        out.append(f"url={ev.url}")
    if ev.error:
        # Quote the error so it reads cleanly. Keep it single-line.
        err = ev.error.replace("\n", " ").strip()
        if len(err) > 120:
            err = err[:117] + "..."
        out.append(f'error="{err}"')
    if show_args and ev.args is not None and not ev.args_hash:
        try:
            txt = json.dumps(ev.args, separators=(",", ":"))
        except (TypeError, ValueError):
            txt = str(ev.args)
        if len(txt) > 40:
            out.append(f"args={txt}")
    return out


@dataclass
class Tree:
    """A renderable tree of Nodes plus a flat list of events for stats."""

    roots: list[Node]
    events: list[Event]

    # --- constructors -------------------------------------------------

    @classmethod
    def from_events(
        cls,
        events: list[Event],
        session_key: str | None = "session_id",
        parent_key: str | None = None,
    ) -> "Tree":
        """Build a Tree from a flat event list.

        parent_key wins when set. Otherwise we group by session_key. If
        neither is set, we make one synthetic "session" root with every
        event as a direct child.
        """
        if parent_key:
            return cls._from_parent_chain(events, parent_key)
        return cls._from_sessions(events, session_key)

    @classmethod
    def from_jsonl(
        cls,
        path: str | Path,
        session_key: str | None = "session_id",
        parent_key: str | None = None,
    ) -> "Tree":
        events = parse_file(path)
        return cls.from_events(events, session_key=session_key, parent_key=parent_key)

    @classmethod
    def from_lines(
        cls,
        lines: Iterable[str],
        session_key: str | None = "session_id",
        parent_key: str | None = None,
    ) -> "Tree":
        events = parse_lines(lines)
        return cls.from_events(events, session_key=session_key, parent_key=parent_key)

    # --- internal builders --------------------------------------------

    @classmethod
    def _from_sessions(cls, events: list[Event], session_key: str | None) -> "Tree":
        # Group events by their session id (or a single bucket if absent).
        buckets: dict[str, list[Event]] = {}
        order: list[str] = []
        for ev in events:
            key = (ev.session_id or "(no session)") if session_key else "(flat)"
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(ev)

        # Kinds whose USD represents actual spend (not an attempted or
        # denied call). Denied/blocked entries report the attempted amount
        # for visibility but should not roll up into the session total.
        spend_kinds = ("tool_ok", "call_ok", "ok", "model_call", "spend")
        roots: list[Node] = []
        for key in order:
            bucket = buckets[key]
            root = Node(label=key)
            for ev in bucket:
                root.children.append(Node(label="", event=ev))
                if ev.kind in spend_kinds:
                    root.agg_usd += ev.usd
                    root.agg_calls += 1
                if ev.latency_ms:
                    root.agg_latency_ms += ev.latency_ms
            roots.append(root)
        return cls(roots=roots, events=events)

    @classmethod
    def _from_parent_chain(cls, events: list[Event], parent_key: str) -> "Tree":
        # Map id -> Node. We accept either span_id or whatever the caller put
        # in parent_key for matching.
        by_id: dict[str, Node] = {}
        order: list[Node] = []
        for ev in events:
            node = Node(label="", event=ev)
            order.append(node)
            ident = ev.span_id
            if ident and ident not in by_id:
                by_id[ident] = node

        # Track the assigned parent of each node so we can reject links that
        # would form a cycle (e.g. A's parent is B while B's parent is A).
        parent_of: dict[int, Node] = {}

        def _would_cycle(child: Node, parent: Node) -> bool:
            # Attaching child under parent creates a cycle iff child is parent
            # or already an ancestor of parent. Walk up from parent.
            cur: Node | None = parent
            while cur is not None:
                if cur is child:
                    return True
                cur = parent_of.get(id(cur))
            return False

        roots: list[Node] = []
        for node in order:
            ev = node.event
            assert ev is not None  # for type checker; we just built it
            parent_id = ev.raw.get(parent_key) or ev.parent_id
            parent = by_id.get(parent_id) if isinstance(parent_id, str) else None
            if parent and parent is not node and not _would_cycle(node, parent):
                parent.children.append(node)
                parent_of[id(node)] = parent
            else:
                # No parent, self-reference, or a cyclic link: keep the node
                # visible as a root rather than silently dropping it.
                roots.append(node)
        return cls(roots=roots, events=events)

    # --- render -------------------------------------------------------

    def render(
        self,
        max_depth: int = 100,
        show_timing: bool = True,
        show_args: bool = False,
        ascii_only: bool = False,
    ) -> str:
        """Walk the tree and return the rendered ASCII output."""
        lines: list[str] = []
        for root in self.roots:
            lines.append(self._render_root_label(root, show_timing, show_args))
            self._render_children(
                root.children,
                ancestors_last=[],
                depth=1,
                max_depth=max_depth,
                show_timing=show_timing,
                show_args=show_args,
                ascii_only=ascii_only,
                lines=lines,
            )
        return "\n".join(lines)

    def _render_root_label(self, root: Node, show_timing: bool, show_args: bool) -> str:
        # Session roots have a synthetic label and aggregated stats.
        # Event roots (parent-chain mode) render like any other event.
        if root.event is not None:
            return _label_for_event(root.event, show_timing, show_args)

        bits: list[str] = []
        if root.agg_usd:
            bits.append(fmt_usd(root.agg_usd))
        if root.agg_calls:
            bits.append(f"{root.agg_calls} call" + ("s" if root.agg_calls != 1 else ""))
        if show_timing and root.agg_latency_ms:
            ms = fmt_ms(root.agg_latency_ms)
            if ms:
                bits.append(ms)
        if bits:
            return f"{root.label} [{', '.join(bits)}]"
        return root.label

    def _render_children(
        self,
        children: list[Node],
        ancestors_last: list[bool],
        depth: int,
        max_depth: int,
        show_timing: bool,
        show_args: bool,
        ascii_only: bool,
        lines: list[str],
    ) -> None:
        if depth > max_depth:
            return
        n = len(children)
        for i, node in enumerate(children):
            is_last = i == n - 1
            label = self._label_for_node(node, show_timing, show_args)
            lines.append(prefix(ancestors_last, is_last, ascii_only) + label)

            # Detail lines (args_hash, url, error) hang as virtual children
            # of this node, indented under it.
            details = _detail_lines(node.event, show_args) if node.event else []
            # If the node has real children too, the detail lines must keep
            # the pipe live, so they look like tees, not branches.
            real_children = node.children
            for j, det in enumerate(details):
                last_detail = (j == len(details) - 1) and not real_children
                cprefix = child_prefix(ancestors_last, is_last, ascii_only)
                marker = (
                    ("└─ " if not ascii_only else "+- ")
                    if last_detail
                    else ("├─ " if not ascii_only else "|- ")
                )
                lines.append(cprefix + marker + det)

            if real_children:
                self._render_children(
                    real_children,
                    ancestors_last + [is_last],
                    depth + 1,
                    max_depth,
                    show_timing,
                    show_args,
                    ascii_only,
                    lines,
                )

    def _label_for_node(self, node: Node, show_timing: bool, show_args: bool) -> str:
        if node.event is None:
            return node.label
        return _label_for_event(node.event, show_timing, show_args)
