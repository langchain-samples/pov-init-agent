"""Create (or sync) the evaluation dataset from the seed docs questions. Idempotent.

The repo's ``seed_data.py`` is the source of truth: examples are matched by question,
so edited reference answers are updated in place, new questions are added, and
questions removed from the repo are deleted. That keeps the CI gate testing against
exactly what's in git, while unchanged examples keep their ids (and experiment history).
"""

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.seed_data import SEED_QUESTIONS


def _example(item: dict) -> dict:
    return {
        "inputs": {
            "question": item["question"],
            **({"neutral_question": item["neutral_question"]} if "neutral_question" in item else {}),
        },
        "outputs": {"answer": item["answer"], "sources": item["sources"]},
        "metadata": {"asker": item["asker"], "fairness_probe": "neutral_question" in item},
    }


def populate_dataset(client, dataset_name: str = DATASET_NAME) -> str:
    """Return the dataset id, creating the dataset and syncing its examples to the repo."""
    if client.has_dataset(dataset_name=dataset_name):
        dataset = client.read_dataset(dataset_name=dataset_name)
    else:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=(
                "Golden Nimbus AI Platform questions with reference answers from the docs. "
                "Includes fairness probes: the same kind of question asked by users who mention "
                "their age, write in non-fluent English, or say they're junior or non-engineers."
            ),
        )

    wanted = {item["question"]: _example(item) for item in SEED_QUESTIONS}
    existing = {ex.inputs.get("question"): ex for ex in client.list_examples(dataset_id=dataset.id)}

    to_create = [ex for q, ex in wanted.items() if q not in existing]
    for q, ex in wanted.items():
        current = existing.get(q)
        if current and (current.inputs != ex["inputs"] or current.outputs != ex["outputs"]):
            client.update_example(current.id, inputs=ex["inputs"], outputs=ex["outputs"], metadata=ex["metadata"])
    stale = [ex.id for q, ex in existing.items() if q not in wanted]

    if to_create:
        client.create_examples(dataset_id=dataset.id, examples=to_create)
    if stale:
        client.delete_examples(stale)
    return str(dataset.id)
