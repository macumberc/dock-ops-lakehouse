#!/usr/bin/env bash
# Tear down every resource this build created in the fedex-fevm workspace.
# Synthetic data only — safe to remove. Run: bash scripts/teardown.sh
set -uo pipefail
P=fedex-fevm
echo "Tearing down dock-ops build in $P ..."

# 1. Databricks App
databricks --profile $P apps delete dock-ops-app 2>&1 | head -1 || true

# 2. Serving endpoint (CV)
databricks --profile $P serving-endpoints delete dock-occupancy-cls 2>&1 | head -1 || true

# 3. Genie space
databricks --profile $P genie trash-space 01f1a3243b00149fa4876211f8b5c004 2>&1 | head -1 || true

# 4. Lakebase project (removes branch/endpoint/roles/synced tables)
databricks --profile $P postgres delete-project projects/dock-ops 2>&1 | head -1 || true

# 5. Lakeflow pipeline
databricks --profile $P pipelines delete 9f101d4c-0023-4662-9a2a-33afcf87dd37 2>&1 | head -1 || true

# 6. UC schema (CASCADE drops all tables, models, functions, volume)
databricks --profile $P schemas delete fedex_fevm_catalog.dock_ops_chad_macumber --force 2>&1 | head -1 || \
  echo "  (drop schema via SQL: DROP SCHEMA fedex_fevm_catalog.dock_ops_chad_macumber CASCADE)"

# 7. Presenter walkthrough and saved evidence published by the Yoodli launcher.
uv run --no-project python scripts/publish_workspace_demo.py \
  --profile "$P" --catalog fedex_fevm_catalog --teardown-launcher

echo "Teardown complete."
