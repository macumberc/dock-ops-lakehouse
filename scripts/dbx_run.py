#!/usr/bin/env python3
"""Local orchestration helper: run a Databricks notebook as a serverless job and
capture its output as committable text evidence.

Uses the Databricks CLI (profile-based auth) so there is no separate SDK auth to
manage. Every on-cluster phase of the build is driven through here so evidence
capture is uniform.

Usage:
    python scripts/dbx_run.py <local_notebook.py> <ws_name> [--params k=v ...] [--evidence path]

It will:
  1. import the local notebook (.py source) to the workspace,
  2. submit a serverless one-time run with the dock_ops wheel installed,
  3. poll to completion,
  4. print + optionally save the notebook exit result (JSON) and the run URL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

PROFILE = "fedex-fevm"
WS_BASE = "/Workspace/Users/chad.macumber@databricks.com/dock_ops/notebooks"
WHEEL = (
    "/Volumes/fedex_fevm_catalog/dock_ops_chad_macumber/raw/libs/"
    "dock_ops_lakehouse-0.1.0-py3-none-any.whl"
)


def cli(*args: str, check: bool = True) -> str:
    """Run a databricks CLI command and return stdout."""
    cmd = ["databricks", "--profile", PROFILE, *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.stderr.write(f"CMD FAILED: {' '.join(cmd)}\n{res.stderr}\n")
        raise SystemExit(res.returncode)
    return res.stdout


def import_notebook(local_path: str, ws_name: str) -> str:
    """Import a local .py notebook source into the workspace, overwriting."""
    ws_path = f"{WS_BASE}/{ws_name}"
    cli("workspace", "import", ws_path, "--file", local_path,
        "--language", "PYTHON", "--format", "SOURCE", "--overwrite")
    return ws_path


def submit_run(ws_path: str, run_name: str, params: dict[str, str]) -> int:
    """Submit a serverless notebook run and return the parent run_id."""
    spec = {
        "run_name": run_name,
        "tasks": [
            {
                "task_key": "task",
                "notebook_task": {
                    "notebook_path": ws_path,
                    "base_parameters": params,
                },
                "environment_key": "default",
            }
        ],
        "environments": [
            {
                "environment_key": "default",
                "spec": {"client": "4", "dependencies": [WHEEL]},
            }
        ],
    }
    out = cli("jobs", "submit", "--json", json.dumps(spec), "--no-wait")
    return int(json.loads(out)["run_id"])


def poll(run_id: int, timeout_s: int = 3600) -> dict:
    """Poll a run until terminal; return the full run JSON."""
    start = time.time()
    while True:
        run = json.loads(cli("jobs", "get-run", str(run_id)))
        life = run.get("state", {}).get("life_cycle_state", "")
        if life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            return run
        if time.time() - start > timeout_s:
            raise SystemExit(f"Timed out after {timeout_s}s (state={life})")
        time.sleep(15)


def get_output(run: dict) -> dict:
    """Fetch the notebook exit result from the task run."""
    task_run_id = run["tasks"][0]["run_id"]
    out = json.loads(cli("jobs", "get-run-output", str(task_run_id)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_notebook")
    ap.add_argument("ws_name")
    ap.add_argument("--params", nargs="*", default=[])
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    params = dict(p.split("=", 1) for p in args.params)
    ws_path = import_notebook(args.local_notebook, args.ws_name)
    print(f"imported -> {ws_path}")
    run_id = submit_run(ws_path, args.ws_name, params)
    print(f"submitted run_id={run_id}; polling...")
    run = poll(run_id, args.timeout)
    state = run.get("state", {})
    result_state = state.get("result_state")
    run_url = run.get("run_page_url", "")
    print(f"result_state={result_state}  url={run_url}")

    out = get_output(run)
    notebook_result = out.get("notebook_output", {}).get("result")
    err = out.get("error")
    if err:
        print(f"ERROR: {err}")
        print(out.get("error_trace", "")[:4000])

    parsed = None
    if notebook_result:
        try:
            parsed = json.loads(notebook_result)
            print("notebook exit result:")
            print(json.dumps(parsed, indent=2)[:6000])
        except Exception:
            print("notebook exit (raw):", notebook_result[:4000])

    if args.evidence:
        payload = {
            "run_name": args.ws_name,
            "run_id": run_id,
            "result_state": result_state,
            "run_url": run_url,
            "result": parsed if parsed is not None else notebook_result,
            "error": err,
        }
        with open(args.evidence, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"evidence written -> {args.evidence}")

    if result_state != "SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
