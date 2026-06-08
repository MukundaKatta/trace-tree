"""ASCII box-drawing primitives for the tree view.

Kept tiny on purpose. The tree builder walks the structure and asks for the
right prefix at each step.
"""

from __future__ import annotations


# Box characters. We stick to the common subset so output is paste-safe in
# most terminals and most code-block renderers.
BRANCH = "+- "  # last child (single-byte fallback)
TEE = "|- "  # middle child
PIPE = "|  "  # vertical continuation
BLANK = "   "  # no continuation


# Pretty unicode variants. Default to these; callers can pass ascii_only=True.
U_BRANCH = "└─ "
U_TEE = "├─ "
U_PIPE = "│  "
U_BLANK = "   "


def prefix(ancestors_last: list[bool], is_last: bool, ascii_only: bool = False) -> str:
    """Build the line prefix for a child given which ancestors were last children.

    ancestors_last is the path from root to this node's parent, each element
    True if that ancestor was a last child of its own parent. is_last says
    whether the current node is its parent's last child.
    """
    if ascii_only:
        pipe, blank, tee, branch = PIPE, BLANK, TEE, BRANCH
    else:
        pipe, blank, tee, branch = U_PIPE, U_BLANK, U_TEE, U_BRANCH

    parts = []
    for last in ancestors_last:
        parts.append(blank if last else pipe)
    parts.append(branch if is_last else tee)
    return "".join(parts)


def child_prefix(
    ancestors_last: list[bool], is_last: bool, ascii_only: bool = False
) -> str:
    """Build the continuation prefix for children-of-children lines.

    Used when we put a second info line under a node (like an args_hash or
    an error message). It needs to align under the node content, not under
    the branch marker.
    """
    if ascii_only:
        pipe, blank = PIPE, BLANK
    else:
        pipe, blank = U_PIPE, U_BLANK

    parts = []
    for last in ancestors_last:
        parts.append(blank if last else pipe)
    # The current node's column: blank if last, otherwise a pipe.
    parts.append(blank if is_last else pipe)
    return "".join(parts)


def fmt_usd(usd: float) -> str:
    """Format a dollar amount the way the example output does."""
    if usd == 0:
        return "0 USD"
    if abs(usd) < 0.01:
        return f"{usd:.4f} USD"
    return f"{usd:.2f} USD"


def fmt_ms(ms: float | None) -> str | None:
    if ms is None:
        return None
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    return f"{int(round(ms))} ms"
