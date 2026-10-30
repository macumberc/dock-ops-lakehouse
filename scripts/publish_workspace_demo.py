#!/usr/bin/env python3
"""Publish the notebook demo and run a read-only serverless validation.

Usage:
    uv run --no-project python scripts/publish_workspace_demo.py \
        --profile fedex-fevm --catalog <verified_workspace_catalog>

This publishes a new, presenter-scoped workspace folder. It does not replace
the existing app, pipeline, models, Genie space, or underlying demo tables.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HOST = "https://fevm-fedex-fevm.cloud.databricks.com"


def cli(profile: str, *arguments: str) -> dict[str, Any] | list[Any]:
    """Run a profile-scoped Databricks CLI operation and parse its JSON response."""
    command = ["databricks", *arguments, "--profile", profile, "--output", "json"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Databricks command failed: {' '.join(command[:3])}\n{result.stderr.strip()}")
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def sync(profile: str, source: Path, destination: str) -> None:
    """Use the resource-deployment skill's CLI sync path for workspace uploads."""
    subprocess.run(["databricks", "sync", str(source), destination, "--full",
                    "--profile", profile], check=True)


def main() -> None:
    """Verify the target, publish the walkthrough, and capture actual run evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="fedex-fevm")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-name")
    parser.add_argument("--publish-only", action="store_true")
    parser.add_argument("--teardown-launcher", action="store_true",
                        help="Delete only this presenter's published meridian_yoodli_demo folder")
    args = parser.parse_args()

    # Credential and workspace identity checks happen before any external write.
    identity = cli(args.profile, "current-user", "me")
    if not isinstance(identity, dict) or not identity.get("userName"):
        raise RuntimeError("The selected profile did not return a workspace user identity.")
    principal = identity["userName"]
    # Verify the explicit profile's configured host without printing credentials.
    import configparser
    config = configparser.ConfigParser()
    config.read(Path.home() / ".databrickscfg")
    host = config.get(args.profile, "host").rstrip("/")
    if host != EXPECTED_HOST:
        raise RuntimeError(f"Profile {args.profile} resolves to {host}; expected {EXPECTED_HOST}.")
    username = re.sub(r"[^a-z0-9]+", "_", principal.split("@")[0].lower()).strip("_")
    schema_name = args.schema_name or f"dock_ops_{username}"
    remote = f"/Workspace/Users/{principal}/meridian_yoodli_demo"

    if args.teardown_launcher:
        cli(args.profile, "workspace", "delete", remote, "--recursive")
        print(f"Deleted the published demo launcher folder: {remote}. Local source remains available.")
        return

    cli(args.profile, "schemas", "get", f"{args.catalog}.{schema_name}")
    table_response = cli(args.profile, "tables", "list", args.catalog, schema_name)
    table_rows = table_response.get("tables", []) if isinstance(table_response, dict) else table_response
    available = {row["name"] for row in table_rows}
    required = {"silver_visits", "gold_terminal_hourly", "gold_dock_current_state",
                "gold_staffing_forecast", "gold_visit_fact"}
    if required - available:
        raise RuntimeError(f"Demo tables are missing: {sorted(required - available)}. "
                           "Restore the existing demo before publishing its walkthrough.")
    cli(args.profile, "workspace", "mkdirs", remote)
    for directory in ("notebooks", "evidence"):
        sync(args.profile, ROOT / directory, f"{remote}/{directory}")

    manifest: dict[str, Any] = {
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile, "host": host, "presenter": principal,
        "catalog": args.catalog, "schema_name": schema_name,
        "workspace_path": remote,
        "notebook_path": f"{remote}/notebooks/00_demo_walkthrough",
        "data_classification": "synthetic", "validation_status": "not_run",
    }
    directory_response = cli(args.profile, "workspace", "list", f"{remote}/notebooks")
    objects = directory_response.get("objects", []) if isinstance(directory_response, dict) else directory_response
    notebook = next((item for item in objects
                     if Path(item["path"]).stem == "00_demo_walkthrough"), None)
    if notebook is None or notebook.get("object_type") != "NOTEBOOK":
        raise RuntimeError("Workspace sync did not produce the expected demo notebook. "
                           "Inspect the published notebooks folder before running it.")
    manifest["notebook_path"] = notebook["path"]
    manifest["notebook_url"] = f"{host}/#notebook/{notebook['object_id']}"
    target = ROOT / "evidence" / "workspace-demo-current.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2), flush=True)
    if args.publish_only:
        return

    payload = {
        "run_name": "Meridian Freight Yoodli demo validation",
        "tasks": [{"task_key": "validate_demo", "timeout_seconds": 1200,
                   "notebook_task": {"notebook_path": manifest["notebook_path"],
                                     "source": "WORKSPACE", "base_parameters": {
                                         "catalog": args.catalog, "schema_name": schema_name}}}],
    }
    submitted = cli(args.profile, "jobs", "submit", "--json", json.dumps(payload), "--no-wait")
    if not isinstance(submitted, dict):
        raise RuntimeError(f"Unexpected job submission response: {submitted}")
    run_id = submitted["run_id"]
    manifest["run_id"] = run_id
    manifest["validation_status"] = "running"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    deadline = time.monotonic() + 1250
    while time.monotonic() < deadline:
        run = cli(args.profile, "jobs", "get-run", str(run_id))
        if not isinstance(run, dict):
            raise RuntimeError("The job run did not return a JSON object.")
        state = run.get("state", {})
        manifest["run_url"] = run.get("run_page_url")
        if state.get("life_cycle_state") in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            task_id = run["tasks"][0]["run_id"]
            output = cli(args.profile, "jobs", "get-run-output", str(task_id))
            manifest["validation_status"] = state.get("result_state", "FAILED")
            manifest["output"] = output
            target.write_text(json.dumps(manifest, indent=2) + "\n")
            print(json.dumps(manifest, indent=2), flush=True)
            if manifest["validation_status"] != "SUCCESS":
                raise RuntimeError(f"Workspace validation failed. Inspect {manifest['run_url']}.")
            return
        print(f"Run {run_id}: {state.get('life_cycle_state', 'PENDING')}", flush=True)
        time.sleep(10)
    raise TimeoutError(f"Validation run {run_id} exceeded the wait limit. Check its live status.")


if __name__ == "__main__":
    main()
