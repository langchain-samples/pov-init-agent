"""Generate seed traces by running the agent over the seed docs questions.

Running the compiled graph with tracing enabled auto-creates the tracing project
and records a multi-step trace per question (docs searches, page reads, answer).
We then read back the root run ids so the bootstrap can drop a few into the
annotation queue.
"""

import os
import time

from langchain_core.tracers.langchain import wait_for_all_tracers

from pov_agent.config import PROJECT
from pov_agent.langsmith.seed_data import SEED_QUESTIONS


def generate_traces(client, n: int = 10) -> list[str]:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", PROJECT)

    # Import lazily: the agent reads its skill + memory from the Context Hub repo,
    # which the bootstrap creates in the step before this one.
    from pov_agent.agent import ask, build_agent

    agent = build_agent()
    for item in SEED_QUESTIONS[:n]:
        ask(agent, item["question"], metadata={"source": "bootstrap-seed", "asker": item["asker"]})

    wait_for_all_tracers()  # flush the background tracer before we query

    # Ingestion lags slightly; poll briefly for the root runs to appear.
    for _ in range(10):
        runs = list(client.list_runs(project_name=PROJECT, is_root=True, limit=n))
        if runs:
            return [str(r.id) for r in runs]
        time.sleep(2)
    return []
