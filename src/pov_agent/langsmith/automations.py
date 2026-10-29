"""Automation rules (run rules) for the tracing project.

Rules have no Python SDK wrapper, so we POST to /runs/rules via the Client's
authenticated request helper (it adds the api key + workspace headers for us).

Two rules, the two most useful for a trial:
  1. Sample live support turns into the human review (annotation) queue.
  2. Sample live support turns into a *production samples* dataset.

Rule 2 deliberately does NOT write to the golden eval dataset: sampled traces
have the trace's input shape and no reference outputs, so mixing them into the
golden set breaks offline evals. They're raw material for labeling instead.

Both act on traces that were anonymized before egress (SDK masking), so the
queue and the dataset only ever receive redacted conversations.
"""

from pov_agent.config import PROJECT


def _existing_rule_names(client, project_id: str) -> set[str]:
    try:
        resp = client.request_with_retries(
            "GET", "/runs/rules", request_kwargs={"params": {"session_id": project_id}}
        )
        resp.raise_for_status()
        return {r.get("display_name") for r in resp.json()}
    except Exception:
        return set()


def create_automations(client, project_id: str, queue_id: str, production_dataset_id: str) -> None:
    project_id, queue_id, dataset_id = str(project_id), str(queue_id), str(production_dataset_id)
    rules = [
        {
            "display_name": "POC: route sampled support turns to review queue",
            "sampling_rate": 0.5,
            "session_id": project_id,
            "filter": "eq(is_root, true)",
            "add_to_annotation_queue_id": queue_id,
            "is_enabled": True,
        },
        {
            "display_name": "POC: sample production turns for labeling",
            "sampling_rate": 0.3,
            "session_id": project_id,
            "filter": "eq(is_root, true)",
            "add_to_dataset_id": dataset_id,
            "is_enabled": True,
        },
    ]

    existing = _existing_rule_names(client, project_id)
    created = 0
    for rule in rules:
        if rule["display_name"] in existing:
            continue
        resp = client.request_with_retries("POST", "/runs/rules", request_kwargs={"json": rule})
        resp.raise_for_status()
        created += 1
    return created
