"""Lakebase (Autoscaling Postgres) operational-serving helpers.

Provides OAuth-token connection helpers shared by the sync job and the app so the
live dock board reads low-latency operational state from Postgres.
"""

from __future__ import annotations

import json
import subprocess

import psycopg2

from dock_ops import config


def token_via_cli(profile: str = "fedex-fevm",
                  endpoint: str = config.LAKEBASE_ENDPOINT_RESOURCE) -> str:
    """Mint a short-lived Lakebase OAuth token via the Databricks CLI (local use)."""
    out = subprocess.check_output(
        ["databricks", "--profile", profile, "postgres",
         "generate-database-credential", endpoint]
    )
    return json.loads(out)["token"]


def token_via_sdk(workspace_client,
                  endpoint: str = config.LAKEBASE_ENDPOINT_RESOURCE) -> str:
    """Mint a Lakebase OAuth token via the SDK (Databricks Apps runtime use)."""
    cred = workspace_client.postgres.generate_database_credential(endpoint=endpoint)
    return cred.token


def connect(token: str, user: str, host: str = config.LAKEBASE_HOST,
            dbname: str = config.LAKEBASE_DBNAME):
    """Open a psycopg2 connection to the Lakebase endpoint (SSL required)."""
    return psycopg2.connect(host=host, port=5432, dbname=dbname,
                            user=user, password=token, sslmode="require")
