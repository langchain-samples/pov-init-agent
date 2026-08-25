"""Offline evaluation: run the agent over the golden dataset and score it.

Produces an experiment under the dataset with four scores per example:
  - ``match_structure``          — deterministic code eval (sections + score present)
  - ``match_quality``            — LLM-as-judge vs. the reference must-address points
  - ``reasoning_unbiased``       — LLM-as-judge fairness check on the agent's own text
  - ``counterfactual_fairness``  — re-runs the agent on protected-attribute-swapped
                                   variants of the same resume and checks score stability

The last one is what "checks the agent's efficacy" on fairness: a discerning matcher
scores the qualifications the same regardless of a candidate's name or pronouns.
"""

from langsmith import evaluate

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.evaluators import (
    make_counterfactual_fairness_evaluator,
    quality_evaluator,
    reasoning_bias_evaluator,
    structure_evaluator,
)


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
        prompt = (
            f"Assess this candidate for the role.\n\n"
            f"JOB TITLE: {inputs['job_title']}\n\n"
            f"JOB DESCRIPTION:\n{inputs['job_description']}\n\n"
            f"RESUME:\n{inputs['resume']}"
        )
        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        return {"review": _final_text(result)}

    # The counterfactual evaluator re-runs the agent several times per example,
    # so it's the expensive one; it shares the same agent instance.
    counterfactual_fairness_evaluator = make_counterfactual_fairness_evaluator(agent)

    return evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[
            structure_evaluator,
            quality_evaluator,
            reasoning_bias_evaluator,
            counterfactual_fairness_evaluator,
        ],
        experiment_prefix="pov-offline",
        max_concurrency=1,  # the agent shares a writable Context Hub memory backend
        client=client,
    )
