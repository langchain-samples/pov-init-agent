"""Create the evaluation dataset from the seed resume/JD pairs. Idempotent."""

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.seed_data import SEED_PAIRS


def populate_dataset(client) -> str:
    """Return the dataset id, creating the dataset + examples if needed."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        if any(client.list_examples(dataset_id=dataset.id)):
            return str(dataset.id)  # already populated
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Golden resume/job-description pairs with the points each match review must address.",
        )

    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {
                    "job_title": item["job_title"],
                    "job_description": item["job_description"],
                    "resume": item["resume"],
                },
                "outputs": {"must_address": item["must_address"]},
            }
            for item in SEED_PAIRS
        ],
    )
    return str(dataset.id)
