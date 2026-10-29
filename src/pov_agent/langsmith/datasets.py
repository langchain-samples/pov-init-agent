"""Create the evaluation dataset from the seed support scenarios. Idempotent.

Re-running adds any scenarios that aren't in the dataset yet (matched on the
customer message), so new scenarios in ``seed_data.py`` flow in without
duplicating existing examples.

The examples are synthetic. Dataset uploads are a direct LangSmith write — SDK
masking (an anonymizer on the Client) only scrubs *runs*, not examples — so a
dataset must never be seeded with real customer conversations. The automation
that grows the dataset from production copies runs that were already
anonymized before egress.
"""

from pov_agent.config import DATASET_NAME, PRODUCTION_DATASET_NAME
from pov_agent.langsmith.seed_data import INPUT_KEYS, REFERENCE_KEYS, SCENARIOS


def ensure_production_dataset(client) -> str:
    """The dataset the 'sample production turns' automation writes to.

    Kept separate from the golden eval dataset on purpose: sampled traces carry
    the trace's own input shape and no reference outputs, so they're raw material
    for human labeling, not eval examples. Promote them into the golden dataset
    once someone has written references for them.
    """
    if client.has_dataset(dataset_name=PRODUCTION_DATASET_NAME):
        return str(client.read_dataset(dataset_name=PRODUCTION_DATASET_NAME).id)
    dataset = client.create_dataset(
        dataset_name=PRODUCTION_DATASET_NAME,
        description="Sampled (already redacted) production support turns, awaiting human references "
                    "before promotion into the golden eval dataset.",
    )
    return str(dataset.id)


def populate_dataset(client) -> str:
    """Return the dataset id, creating the dataset and adding missing examples.
    Existing examples are never modified."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        existing = {(ex.inputs or {}).get("message") for ex in client.list_examples(dataset_id=dataset.id)}
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=(
                "Golden voice + chat support turns for a smart-TV brand: standard, adversarial "
                "(guardrail G1–G6), and benign-boundary cases, with resolution points, privacy "
                "expectations, and expected/forbidden actions. Synthetic data."
            ),
        )
        existing = set()

    missing = [item for item in SCENARIOS if item["message"] not in existing]
    if missing:
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {
                    "inputs": {k: item[k] for k in INPUT_KEYS},
                    "outputs": {k: item[k] for k in REFERENCE_KEYS},
                    "metadata": {"channel": item["channel"], "kind": item["kind"],
                                 "guardrail": item["guardrail"]},
                }
                for item in missing
            ],
        )
    return str(dataset.id)
