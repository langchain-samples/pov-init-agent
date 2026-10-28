# Deploying models with Model Serving

## What Model Serving is
Model Serving deploys models behind scalable, authenticated API endpoints. It is available
to Members from **Tools & Frameworks → Model Serving**. Deploying a model takes three
objects: a **registry**, a **packaged model**, and a **deployment**.

## Step 1: Add a registry
In Model Serving, open **Registries → Add Registry** and point it at where the model lives:
NVIDIA NGC (for NIM images), Hugging Face, or an S3-compatible / OCI registry. Supply the
access token for private registries (for example a Hugging Face token for gated models such
as Llama).

## Step 2: Create a packaged model
Open **Packaged Models → Create**. Choose the registry and model, and the serving runtime:
an **NVIDIA NIM** image for supported models, or **vLLM** for other open-weight LLMs. Pick a
**resource template** that sets CPU, memory, and GPU count. The model's weights must fit in
the selected GPUs' memory — large models need a template with more or larger GPUs, or a
quantized variant.

## Step 3: Create a deployment
Open **Deployments → Create**, select the packaged model, and set autoscaling: minimum and
maximum replicas (a minimum of 0 enables scale-to-zero, which frees GPUs when idle at the
cost of a cold start). Enable authentication, then click **Deploy**. When status is Ready,
the deployment page shows the endpoint URL.

## Calling the endpoint
Generate an API token on the deployment's page. LLM deployments on NIM or vLLM expose an
**OpenAI-compatible API**, so you can call `<endpoint>/v1/chat/completions` with the header
`Authorization: Bearer <token>`, or point any OpenAI SDK client at `<endpoint>/v1` with the
token as the API key. A `401` response means the token is missing or wrong.
