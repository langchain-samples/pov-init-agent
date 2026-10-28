# Running distributed jobs: Spark and Ray

## Spark
Spark runs on the cluster through the Spark Operator. Two ways to use it:
- **Interactive** — from a notebook, start a Spark interactive session (served through Livy)
  and run PySpark cells against the cluster.
- **Batch** — open **Data Engineering → Spark Applications → Create Application**, upload or
  point to your PySpark script, set driver/executor resources, and submit. Logs for each
  application are available from its row on the Spark Applications page.

## Ray
A KubeRay-managed Ray cluster is available from Tools & Frameworks. From a notebook, connect
with `ray.init(address="ray://<head-address>:10001")`, using the Ray client address shown on
the Ray tile's details page, then submit tasks or Ray Train / Ray Serve workloads. Request
GPUs per task with `@ray.remote(num_gpus=1)`.

## Pipelines and scheduling
Kubeflow Pipelines (build with the `kfp` SDK from a notebook) chain steps into reproducible
ML pipelines; Airflow schedules recurring jobs from DAGs synced from a Git repository that an
administrator configures.
