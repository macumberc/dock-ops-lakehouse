#!/usr/bin/env python3
"""Ask the Genie space a set of questions via the Conversation API and capture the
natural-language question -> generated SQL -> result rows as committable text evidence.
"""

from __future__ import annotations

import json
import subprocess
import time

PROFILE = "fedex-fevm"
SPACE = "01f1a3243b00149fa4876211f8b5c004"
QUESTIONS = [
    "Which terminal has the highest total detention fees?",
    "What hours of the day are we most understaffed next week?",
    "How many docks are currently occupied at each terminal right now?",
]


def cli(*args: str) -> dict:
    out = subprocess.check_output(["databricks", "--profile", PROFILE, *args])
    return json.loads(out)


def ask(question: str) -> dict:
    start = cli("genie", "start-conversation", "--no-wait", SPACE, question)
    conv, msg = start["conversation_id"], start["message_id"]
    status = None
    for _ in range(40):
        m = cli("genie", "get-message", SPACE, conv, msg)
        status = m.get("status")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(6)
    result = {"question": question, "status": status, "sql": None, "text": None, "rows": None, "columns": None}
    if status != "COMPLETED":
        result["error"] = (m.get("error") or {})
        return result
    for att in m.get("attachments", []):
        if att.get("query"):
            result["sql"] = att["query"].get("query")
            result["query_description"] = att["query"].get("description")
            att_id = att.get("attachment_id")
            try:
                qr = cli("genie", "get-message-attachment-query-result", SPACE, conv, msg, att_id)
                sr = qr.get("statement_response", {})
                result["columns"] = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                result["rows"] = sr.get("result", {}).get("data_array")
            except Exception as e:
                result["result_error"] = str(e)[:200]
        if att.get("text"):
            result["text"] = att["text"].get("content")
    return result


def main() -> None:
    results = [ask(q) for q in QUESTIONS]
    payload = {"space_id": SPACE, "results": results}
    with open("evidence/09_genie.json", "w") as f:
        json.dump(payload, f, indent=2)
    for r in results:
        print("Q:", r["question"], "->", r["status"])
        print("  SQL:", (r.get("sql") or "").replace("\n", " ")[:200])
        print("  ROWS:", r.get("rows"))
        print()


if __name__ == "__main__":
    main()
