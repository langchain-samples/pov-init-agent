# Experiment tracking with MLflow

## MLflow in Nimbus Workbench
MLflow comes preinstalled in the Tools & Frameworks catalog. Notebook servers come
pre-configured with the MLflow tracking URI and credentials as environment variables, so you
don't need to call `mlflow.set_tracking_uri()` from a notebook.

## Logging a run from a notebook
```python
import mlflow

mlflow.set_experiment("churn-model")
with mlflow.start_run():
    mlflow.log_param("max_depth", 6)
    mlflow.log_metric("auc", 0.91)
    mlflow.sklearn.log_model(model, "model")
```
Run artifacts (models, plots) are stored in the platform's object storage automatically.

## Registering and viewing models
Open the **MLflow** tile from Tools & Frameworks to browse experiments and compare runs.
Register a model from a run with `mlflow.register_model("runs:/<run_id>/model", "<name>")` or
from the MLflow UI. Registered models can then be served with Model Serving by adding the
model's storage location as a registry.
