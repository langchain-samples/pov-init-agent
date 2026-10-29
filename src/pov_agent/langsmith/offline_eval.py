"""Offline evaluation: run the agent over the golden dataset and score it.

Produces an experiment under the dataset with seven scores per example
(``guardrail_upheld`` on adversarial turns, ``stayed_on_task`` on the rest):
  - ``channel_format``          — deterministic: speakable on voice, concise on chat
  - ``no_sensitive_data_leak``  — deterministic: no raw PII/ACR values in the reply
  - ``action_correctness``      — deterministic: expected actions taken, forbidden ones not
  - ``resolution_quality``      — LLM-as-judge vs. the reference must-address points
  - ``privacy_compliant``       — LLM-as-judge vs. the privacy policy + per-turn expectation
  - ``guardrail_upheld`` /      — guardrail judge (Prompt Hub): did an adversarial turn
    ``stayed_on_task``            break G1–G6? did a legitimate turn get over-refused?
  - ``channel_parity``          — replays the turn on the other channel; same actions?

The client passed in is the masking client from ``privacy.build_tracing_client``,
so experiment runs and judge calls are scrubbed before they are stored.
"""

from langsmith import evaluate

from pov_agent.config import DATASET_NAME
from pov_agent.langsmith.evaluators import (
    action_correctness_evaluator,
    channel_format_evaluator,
    make_channel_parity_evaluator,
    privacy_policy_evaluator,
    resolution_quality_evaluator,
    sensitive_data_leak_evaluator,
)
from pov_agent.langsmith.guardrails import guardrail_evaluator
from pov_agent.voice import run_voice_or_text_turn


def run_offline_eval(client):
    from pov_agent.agent import build_agent

    agent = build_agent()

    def target(inputs: dict) -> dict:
        # Voice examples go through real audio: synthesized caller audio (cached)
        # → speech-to-text → agent → text-to-speech. Channel parity replays as text.
        return run_voice_or_text_turn(agent, inputs, metadata={"source": "offline-eval"})

    return evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[
            channel_format_evaluator,
            sensitive_data_leak_evaluator,
            action_correctness_evaluator,
            resolution_quality_evaluator,
            privacy_policy_evaluator,
            guardrail_evaluator,                    # Prompt Hub judge: guardrail_upheld / stayed_on_task
            make_channel_parity_evaluator(agent),  # re-runs the agent once per example
        ],
        experiment_prefix="pov-offline",
        max_concurrency=2,
        client=client,
    )
