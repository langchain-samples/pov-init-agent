"""Offline evaluation: run the agent over the golden dataset and score it.

Produces an experiment under the dataset with three scores per example:
  - ``correctness``    — openevals CORRECTNESS_PROMPT (LLM-as-judge) vs. the reference answer
  - ``fairness``       — openevals FAIRNESS_PROMPT (LLM-as-judge), 1.0 = no bias detected
  - ``cites_sources``  — deterministic: the answer cites real docs on a ``Sources:`` line

``ci_gate.py`` calls the same function and fails the build if any mean score drops
below ``config.CI_THRESHOLDS``.
"""

from langsmith import evaluate

from pov_agent.config import DATASET_NAME, resolve_agent_version
from pov_agent.langsmith.evaluators import OFFLINE_EVALUATORS


def make_target(version: str | None = None, local_context: bool = False):
    from pov_agent.agent import ask, build_agent

    agent = build_agent(version, local_context=local_context)

    def target(inputs: dict) -> dict:
        out = {"answer": ask(agent, inputs["question"])}
        # Fairness probes: also answer the same question asked neutrally, so the
        # fairness judge can compare the two answers (counterfactual pair).
        if inputs.get("neutral_question"):
            out["counterfactual_answer"] = ask(agent, inputs["neutral_question"])
        return out

    return target


def run_offline_eval(
    client,
    version: str | None = None,
    *,
    local_context: bool = False,
    data=DATASET_NAME,
    experiment_prefix: str | None = None,
    metadata: dict | None = None,
    max_concurrency: int = 1,
):
    version = resolve_agent_version(version)
    return evaluate(
        make_target(version, local_context=local_context),
        data=data,
        evaluators=OFFLINE_EVALUATORS,
        experiment_prefix=experiment_prefix or f"pov-offline-{version}",
        metadata={"agent_version": version, **(metadata or {})},
        # The Context Hub backend shares one writable memory file, so stay serial
        # unless the agent runs on a throwaway local copy (local_context=True).
        max_concurrency=max_concurrency,
        client=client,
    )


def mean_scores(results) -> dict[str, float]:
    """Mean score per feedback key across an ExperimentResults."""
    totals: dict[str, list[float]] = {}
    for row in results:
        for res in row["evaluation_results"]["results"]:
            if res.score is not None:
                totals.setdefault(res.key, []).append(float(res.score))
    return {k: round(sum(v) / len(v), 3) for k, v in totals.items()}
