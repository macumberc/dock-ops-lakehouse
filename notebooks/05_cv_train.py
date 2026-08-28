# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Computer-vision dock-occupancy classifier
# MAGIC Meridian Freight Systems. Trains a CPU image classifier on the governed
# MAGIC `silver_dock_images` to label each dock-camera frame
# MAGIC (`empty` / `docked` / `loading` / `obstructed`), logs it to MLflow, registers it
# MAGIC in **Unity Catalog**, and serves it as a **pyfunc that accepts raw base64 PNGs**.
# MAGIC Batch predictions are written to `gold_dock_image_scored` and fold into the live
# MAGIC dock state. Runs on serverless CPU — no GPU required.

# COMMAND ----------

import base64, io, json, tempfile, os
import numpy as np
import pandas as pd
from PIL import Image
import mlflow
from mlflow.models.signature import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

S = "fedex_fevm_catalog.dock_ops_chad_macumber"
MODEL = f"{S}.dock_occupancy"
FEAT = 32  # grayscale FEATxFEAT feature grid

# COMMAND ----------
# DBTITLE 1,Featurization (shared by training, scoring, and the served pyfunc)

def featurize_bytes(png_bytes: bytes) -> np.ndarray:
    """Downsample a PNG to a FEATxFEAT grayscale vector in [0,1]."""
    im = Image.open(io.BytesIO(png_bytes)).convert("L").resize((FEAT, FEAT))
    return np.asarray(im, dtype=np.float32).flatten() / 255.0

# COMMAND ----------
# DBTITLE 1,Load labeled images from the governed silver table
pdf = (spark.table(f"{S}.silver_dock_images")
       .select("dock_id", "terminal", "frame_ts", "true_label", "content")
       .toPandas())
print("images loaded:", len(pdf))
X = np.vstack([featurize_bytes(c) for c in pdf["content"]])
y = pdf["true_label"].values
labels = ["empty", "docked", "loading", "obstructed"]
print("feature matrix:", X.shape, "| label counts:", pdf["true_label"].value_counts().to_dict())

# COMMAND ----------
# DBTITLE 1,Train / evaluate
Xtr, Xte, ytr, yte, idx_tr, idx_te = train_test_split(
    X, y, np.arange(len(y)), test_size=0.25, random_state=42, stratify=y
)
clf = RandomForestClassifier(n_estimators=250, max_depth=18, random_state=42, n_jobs=-1)
clf.fit(Xtr, ytr)
pred = clf.predict(Xte)
acc = float(accuracy_score(yte, pred))
cm = confusion_matrix(yte, pred, labels=labels)
report = classification_report(yte, pred, labels=labels, digits=3)
cm_text = "confusion matrix (rows=true, cols=pred) labels=%s\n%s" % (labels, cm)
print(f"test accuracy: {acc:.4f}")
print(cm_text)
print(report)

# COMMAND ----------
# DBTITLE 1,pyfunc wrapper — classifies raw base64 PNGs (serving-friendly)

class DockOccupancyModel(mlflow.pyfunc.PythonModel):
    """Serve dock-occupancy predictions directly from base64-encoded PNG frames."""

    FEAT = 32
    LABELS = ["empty", "docked", "loading", "obstructed"]

    def load_context(self, context):
        import joblib
        self._clf = joblib.load(context.artifacts["sk_model"])

    def _featurize(self, b64: str) -> np.ndarray:
        raw = base64.b64decode(b64)
        im = Image.open(io.BytesIO(raw)).convert("L").resize((self.FEAT, self.FEAT))
        return np.asarray(im, dtype=np.float32).flatten() / 255.0

    def predict(self, context, model_input):
        if isinstance(model_input, pd.DataFrame):
            col = "image_b64" if "image_b64" in model_input.columns else model_input.columns[0]
            imgs = model_input[col].tolist()
        else:
            imgs = list(model_input)
        feats = np.vstack([self._featurize(b) for b in imgs])
        return self._clf.predict(feats).tolist()

# COMMAND ----------
# DBTITLE 1,Log + register in Unity Catalog + set prod alias
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/chad.macumber@databricks.com/dock_ops/cv_experiment")

# input example: a base64 PNG from the test set
ex_bytes = pdf["content"].iloc[int(idx_te[0])]
ex_b64 = base64.b64encode(ex_bytes).decode()
input_example = pd.DataFrame({"image_b64": [ex_b64]})
signature = infer_signature(input_example, np.array(["empty"]))

with mlflow.start_run(run_name="dock_occupancy_rf") as run:
    mlflow.log_params({"model": "RandomForest", "n_estimators": 250, "max_depth": 18,
                       "feature_grid": FEAT, "n_train": len(ytr), "n_test": len(yte)})
    mlflow.log_metric("test_accuracy", acc)
    for lbl in labels:
        # per-class recall from the confusion matrix
        i = labels.index(lbl); tot = cm[i].sum()
        mlflow.log_metric(f"recall_{lbl}", float(cm[i, i] / tot) if tot else 0.0)
    mlflow.log_text(cm_text, "confusion_matrix.txt")
    mlflow.log_text(report, "classification_report.txt")

    tmp = tempfile.mkdtemp()
    sk_path = os.path.join(tmp, "sk_model.joblib")
    import joblib; joblib.dump(clf, sk_path)

    mlflow.pyfunc.log_model(
        artifact_path="model",
        python_model=DockOccupancyModel(),
        artifacts={"sk_model": sk_path},
        signature=signature,
        input_example=input_example,
        pip_requirements=["scikit-learn", "pillow", "numpy", "pandas", "joblib", "cloudpickle"],
        registered_model_name=MODEL,
    )
    run_id = run.info.run_id

client = mlflow.MlflowClient()
ver = max(int(m.version) for m in client.search_model_versions(f"name='{MODEL}'"))
client.set_registered_model_alias(MODEL, "prod", ver)
print(f"registered {MODEL} version {ver} alias prod")

# COMMAND ----------
# DBTITLE 1,Batch-score ALL images -> gold_dock_image_scored
all_pred = clf.predict(X)
scored = pdf[["dock_id", "terminal", "frame_ts", "true_label"]].copy()
scored["predicted_label"] = all_pred
scored["correct"] = (scored["true_label"] == scored["predicted_label"])
sdf = spark.createDataFrame(scored)
(sdf.write.mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(f"{S}.gold_dock_image_scored"))
overall_acc = float(scored["correct"].mean())
print("gold_dock_image_scored rows:", sdf.count(), "| full-set accuracy:", round(overall_acc, 4))

# COMMAND ----------
# DBTITLE 1,Fold latest CV prediction into the live dock state
spark.sql(f"""
CREATE OR REPLACE TABLE {S}.gold_dock_current_state AS
WITH latest_cv AS (
  SELECT dock_id, predicted_label, frame_ts,
         ROW_NUMBER() OVER (PARTITION BY dock_id ORDER BY frame_ts DESC) rn
  FROM {S}.gold_dock_image_scored
)
SELECT s.*, c.predicted_label AS cv_state, c.frame_ts AS cv_frame_ts
FROM {S}.gold_dock_current_state s
LEFT JOIN latest_cv c ON s.dock_id = c.dock_id AND c.rn = 1
""")
print("gold_dock_current_state augmented with cv_state")

# COMMAND ----------
# DBTITLE 1,Exit with evidence
result = {
    "test_accuracy": round(acc, 4),
    "full_set_accuracy": round(overall_acc, 4),
    "labels": labels,
    "confusion_matrix": cm.tolist(),
    "classification_report": report,
    "model": MODEL,
    "model_version": ver,
    "run_id": run_id,
    "scored_rows": int(sdf.count()),
}
dbutils.notebook.exit(json.dumps(result, default=str))
