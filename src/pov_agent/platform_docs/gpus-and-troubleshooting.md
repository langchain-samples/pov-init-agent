# GPUs, quotas, and troubleshooting

## Requesting GPUs
Workloads request GPUs through Kubernetes resource limits, for example
`resources: { limits: { nvidia.com/gpu: 1 } }` in a pod spec or Helm values. Notebooks set
this with the **GPUs** field and Model Serving sets it through the resource template.
Administrators set per-user **resource quotas** (CPU, memory, GPU) in Nimbus Workbench.

## Pod or notebook stuck in Pending
A workload stays **Pending** when the scheduler can't place it. The usual causes:
1. **Quota exceeded** — the request would push you past your GPU quota. Check your usage and
   quota in Nimbus Workbench; stop idle notebooks or deployments you own, or ask an
   administrator to raise the quota.
2. **No free GPUs** — all GPUs are allocated to other workloads. Scale-to-zero Model Serving
   deployments and stopped notebooks free capacity.
3. **Request can't fit on one node** — e.g. asking for more GPUs than any single node has.

Run `kubectl describe pod <name>` (or check the workload's events in the UI) and read the
`Events` section; `Insufficient nvidia.com/gpu` or `exceeded quota` names the cause.

## Model Serving deployment not becoming Ready
Open the deployment's page and check its logs. Out-of-memory errors while loading weights
mean the model doesn't fit the resource template's GPUs: choose a larger template or a
quantized model. Pull errors usually mean the registry token is missing or expired.
