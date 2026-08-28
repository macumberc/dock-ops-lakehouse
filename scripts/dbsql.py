#!/usr/bin/env python3
"""Reusable SQL helper: run a query on the serverless warehouse and return rows,
with a markdown-table formatter for committing query-result evidence as text.
"""

from __future__ import annotations

import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

PROFILE = "fedex-fevm"
WAREHOUSE_ID = "2a0649a9f0fb7773"

_w: WorkspaceClient | None = None


def client() -> WorkspaceClient:
    global _w
    if _w is None:
        _w = WorkspaceClient(profile=PROFILE)
    return _w


def run(sql: str, warehouse_id: str = WAREHOUSE_ID) -> tuple[list[str], list[list]]:
    """Execute SQL, waiting for completion; return (columns, rows)."""
    w = client()
    resp = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=warehouse_id, wait_timeout="50s"
    )
    # Poll if still running.
    while resp.status and resp.status.state in (
        StatementState.PENDING,
        StatementState.RUNNING,
    ):
        resp = w.statement_execution.get_statement(resp.statement_id)
    if resp.status and resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status.error else resp.status.state
        raise RuntimeError(f"SQL failed: {msg}\n{sql[:500]}")
    cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
    data = resp.result.data_array if (resp.result and resp.result.data_array) else []
    return cols, data


def md_table(cols: list[str], rows: list[list], max_rows: int = 50) -> str:
    """Render rows as a GitHub-flavored markdown table."""
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows[:max_rows]:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    if len(rows) > max_rows:
        out.append(f"| _…{len(rows) - max_rows} more rows_ |" + " |" * (len(cols) - 1))
    return "\n".join(out)


if __name__ == "__main__":
    q = sys.argv[1]
    c, r = run(q)
    print(md_table(c, r))
