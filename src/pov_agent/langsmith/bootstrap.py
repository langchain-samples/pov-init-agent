"""One command to populate a fresh LangSmith workspace.

Run with:  uv run pov-bootstrap

Steps run in dependency order and are idempotent — safe to re-run.
"""

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

from pov_agent.config import ONLINE_EVALUATOR_NAME, PROJECT
from pov_agent.langsmith.annotation_queues import ensure_queue
from pov_agent.langsmith.automations import create_automations
from pov_agent.langsmith.context_hub import push_context_hub
from pov_agent.langsmith.datasets import populate_dataset
from pov_agent.langsmith.offline_eval import run_offline_eval
from pov_agent.langsmith.traces import generate_traces

_ONLINE_EVAL_FILE = Path(__file__).parent / "online_eval.py"


def _require_keys() -> None:
    import os

    if not os.environ.get("LANGSMITH_API_KEY"):
        sys.exit("LANGSMITH_API_KEY is not set. Copy .env.example to .env and fill it in.")
    if not any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")):
        print("⚠️  No LLM provider key found (ANTHROPIC/OPENAI/GOOGLE). Set the one your MODEL uses.")


def _upload_online_evaluator() -> None:
    """Upload the code evaluator that scores every live trace's structure."""
    cmd = [
        "langsmith", "evaluator", "upload", str(_ONLINE_EVAL_FILE),
        "--function", "perform_eval",
        "--name", ONLINE_EVALUATOR_NAME,
        "--project", PROJECT,
        "--sampling-rate", "1.0",
        "--replace", "--yes",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   (online evaluator upload reported: {result.stderr.strip() or result.stdout.strip()})")


def main() -> None:
    load_dotenv()
    _require_keys()
    client = Client()
    web = getattr(client, "_web_url", None) or "https://smith.langchain.com"

    print("1/7 Context Hub — pushing system prompt, AGENTS.md, and the match-rubric skill…")
    push_context_hub(client)

    print("2/7 Dataset — creating golden resume/job-description pairs…")
    dataset_id = populate_dataset(client)

    print(f"3/7 Traces — running the agent over seed pairs into project '{PROJECT}'…")
    run_ids = generate_traces(client)
    print(f"     captured {len(run_ids)} root run(s)")

    print("4/7 Annotation queue — creating rubric and queueing runs for review…")
    queue = ensure_queue(client, run_ids)

    print("5/7 Offline eval — scoring the agent (structure + quality + fairness judges + counterfactual)…")
    run_offline_eval(client)

    print("6/7 Online evaluator — attaching the structure evaluator to live traces…")
    _upload_online_evaluator()

    print("7/7 Automations — adding rules (queue routing + dataset growth)…")
    project_id = client.read_project(project_name=PROJECT).id
    create_automations(client, project_id, queue.id, dataset_id)

    print("\n✅ Done. Open your workspace and explore:")
    print(f"   {web}")
    print(f"   • Tracing project '{PROJECT}'  — traces + the online evaluator + automations")
    print("   • Datasets & Experiments        — the eval dataset and the offline experiment")
    print("   • Annotation Queues             — match reviews waiting for human review")
    print("   • Context Hub                   — the agent repo (prompt, AGENTS.md, skill)")


if __name__ == "__main__":
    main()
