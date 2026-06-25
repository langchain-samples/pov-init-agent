"""Create the evaluation dataset from the seed topics. Idempotent."""

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.seed_data import SEED_TOPICS


def populate_dataset(client) -> str:
    """Return the dataset id, creating the dataset + examples if needed."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        if any(client.list_examples(dataset_id=dataset.id)):
            return str(dataset.id)  # already populated
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Golden report topics with the points each report must cover.",
        )

    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {"topic": item["topic"]},
                "outputs": {"must_cover": item["must_cover"]},
            }
            for item in SEED_TOPICS
        ],
    )
    return str(dataset.id)
