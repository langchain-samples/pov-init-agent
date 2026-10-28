# Nimbus AI Platform overview

## What Nimbus AI Platform is
Nimbus AI Platform is a private AI platform that runs on your own GPU cluster. It packages
GPU compute, storage, and networking with a pre-installed AI software stack, so teams can
start with inference and RAG and grow into fine-tuning without sending data to a public
cloud. Clusters come in several sizes (small, medium, large, extra large) that differ in
GPU count and type.

## Software stack
The platform has two software layers:
- **Nimbus Workbench** — the data-science and MLOps web app users log in to. It provides
  notebooks, the Tools & Frameworks catalog (MLflow, Kubeflow, Ray, Spark, Airflow, and more),
  data-source connectors, and **Model Serving** for deploying models behind API endpoints.
- **Serving runtimes** — optimized, containerized model-serving images (NVIDIA NIM) and vLLM
  for open-weight LLMs.

Administrators provision, update, and monitor the cluster from the **Nimbus Console**.

## Where to go for common tasks
- Interactive development: create a notebook server (see "Notebooks in Nimbus Workbench").
- Serve an LLM or other model behind an API endpoint: use Model Serving (see "Deploying models with Model Serving").
- Bring your own application or open-source tool: use the Import Framework (see "Importing your own framework").
- Experiment tracking: MLflow (see "Experiment tracking with MLflow").
- Connect data: Data Sources (see "Connecting data sources").
