"""
mcp_transport.py
~~~~~~~~~~~~~~~~
Lightweight MCP transport recorder for the in-process supervisor flow.

When the supervisor calls TASK_AGENT / MEMORY_AGENT / PLANNING_AGENT it
does so in-process, not over HTTP, so the Starlette TransportMetrics-
Middleware in mcp_server.py never fires.  This module fills that gap by
measuring the byte footprint of every logical MCP call:

    request_bytes  = JSON-encoded {tool, arguments}
    response_bytes = JSON-encoded result

Both values are written to the existing `mcp_transport` DB table so the
dashboard transport counters reflect real activity.

Each row is tagged with the current execution_id so the dashboard can
show per-execution transport stats alongside the lifetime totals.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_mcp_call(
    db,
    tool: str,
    arguments: Any,
    result: Any,
    execution_id: Optional[str] = None,
) -> None:
    """
    Measure and persist one logical MCP tool call.
    Never raises — failures are printed to stderr so the caller
    (parallel worker) always returns its result tuple.
    """

    try:
        request_payload = {"tool": tool, "arguments": arguments}
        request_bytes   = _byte_size(request_payload)
        response_bytes  = _byte_size(result)

        db.save_mcp_transport({
            "execution_id":  execution_id,
            "method":        "TOOL",
            "path":          f"/mcp/tools/{tool}",
            "request_bytes": request_bytes,
            "response_bytes": response_bytes,
            "status_code":   200,
            "created_at":    datetime.now().isoformat(),
        })

    except Exception as exc:
        import sys
        print(
            f"[mcp_transport] WARNING: failed to record transport "
            f"for {tool!r} (exec={execution_id}): {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _byte_size(value: Any) -> int:
    """Return the UTF-8 byte length of the JSON representation of *value*."""
    try:
        return len(
            json.dumps(value, default=str).encode("utf-8")
        )
    except Exception:
        return len(str(value).encode("utf-8"))
