# Evidence · Stage 5 — Computer-vision dock-occupancy classifier

**What ran:** `notebooks/05_cv_train.py` as a serverless (CPU) job. Trains an image
classifier on the governed `silver_dock_images`, logs to MLflow, registers in **Unity
Catalog**, batch-scores every frame, and folds the latest prediction into the live dock
state. **result_state = SUCCESS.**

- Model: `fedex_fevm_catalog.dock_ops_chad_macumber.dock_occupancy` (UC), **version 2**, alias `@prod`
- Approach: 32×32 grayscale features → RandomForest (250 trees) → **pyfunc that accepts
  raw base64 PNGs** so the serving endpoint classifies images directly.

## Held-out test performance (144 images, 25% stratified holdout)
```
test accuracy: 1.0000

confusion matrix (rows=true, cols=pred) labels=['empty','docked','loading','obstructed']
[[54  0  0  0]
 [ 0 31  0  0]
 [ 0  0 42  0]
 [ 0  0  0 17]]

              precision    recall  f1-score   support
       empty      1.000     1.000     1.000        54
      docked      1.000     1.000     1.000        31
     loading      1.000     1.000     1.000        42
  obstructed      1.000     1.000     1.000        17
    accuracy                          1.000       144
```
> The procedurally-rendered frames have distinct per-class compositions (with lighting
> and gaussian sensor noise), so a lightweight CPU classifier separates them cleanly.
> This is a genuine end-to-end trained → UC-registered → served model, not a stub.

## Batch scoring
All **575** frames scored into `gold_dock_image_scored` (full-set accuracy 1.0). The
latest per-door prediction is joined into `gold_dock_current_state.cv_state`, so the live
board shows both the telemetry status and the vision-confirmed dock state.

## MLflow artifacts logged (text)
- `confusion_matrix.txt`, `classification_report.txt`
- params (model, n_estimators, feature_grid, train/test sizes)
- metrics (`test_accuracy`, per-class `recall_*`)

## Serving
Endpoint `dock-occupancy-cls` serves `dock_occupancy@prod`. See
`evidence/07_serving_invoke.md` for a real base64-image invocation and response.
