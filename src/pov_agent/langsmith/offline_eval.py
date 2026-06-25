"""Offline evaluation: run the agent over the golden dataset and score it.

Produces an experiment under the dataset with two scores per example:
``report_structure`` (deterministic code eval) and ``coverage`` (LLM-as-judge).
"""

from langsmith import evaluate

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.evaluators import coverage_evaluator, structure_evaluator


def _final_text(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    content = messages[-1].content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


def run_offline_eval(client):
    from pov_agent.agent import build_agent

    agent = build_agent()

    def target(inputs: dict) -> dict:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Write a report on: {inputs['topic']}"}]}
        )
        return {"report": _final_text(result)}

    return evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[structure_evaluator, coverage_evaluator],
        experiment_prefix="pov-offline",
        max_concurrency=1,  # the agent shares a writable Context Hub memory backend
        client=client,
    )
