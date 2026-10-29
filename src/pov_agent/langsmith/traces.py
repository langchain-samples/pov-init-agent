"""Generate seed traces by running the agent over the seed support scenarios.

Voice scenarios run through real audio (see ``pov_agent.voice``): each becomes a
``voice_call`` trace with speech-to-text, agent, and text-to-speech spans, and
the agent's spoken reply attached as audio.

Running the compiled graph with tracing enabled auto-creates the tracing project
and records a multi-step trace per turn. Every trace passes through the SDK
anonymizer installed by ``build_agent`` before it leaves the process. We then
read back the root run ids so the bootstrap can drop a few into the queue.
"""

import os
import time

from langchain_core.tracers.langchain import wait_for_all_tracers

from pov_agent.config import PROJECT
from pov_agent.langsmith.seed_data import SCENARIOS
from pov_agent.voice import run_voice_or_text_turn


def generate_traces(client, n: int = len(SCENARIOS)) -> list[str]:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", PROJECT)

    # Import lazily: the agent pulls its prompt/skill from the Context Hub repo,
    # which the bootstrap creates in the step before this one.
    from pov_agent.agent import build_agent

    agent = build_agent()
    for item in SCENARIOS[:n]:
        run_voice_or_text_turn(agent, item, metadata={"source": "bootstrap-seed"})

    wait_for_all_tracers()  # flush the background tracer before we query

    # Ingestion lags slightly; poll briefly for the root runs to appear.
    for _ in range(10):
        runs = list(client.list_runs(project_name=PROJECT, is_root=True, limit=n))
        if runs:
            return [str(r.id) for r in runs]
        time.sleep(2)
    return []
