"""Run the console on the port assigned by Databricks Apps."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("DATABRICKS_APP_PORT", "8000")))
