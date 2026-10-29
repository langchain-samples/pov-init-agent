"""One command to populate a fresh LangSmith workspace.

Run with:  uv run pov-bootstrap

Steps run in dependency order and are idempotent — safe to re-run.
"""

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# .env is this repo's source of truth: load it (winning over variables already
# exported in the shell, e.g. another tool's LANGSMITH_API_KEY or
# LANGSMITH_PROJECT) BEFORE importing pov_agent.config, which reads PROJECT and
# other settings at import time.
load_dotenv(override=True)

from pov_agent.config import ONLINE_EVALUATOR_NAME, PROJECT  # noqa: E402
from pov_agent.langsmith.annotation_queues import ensure_queue
from pov_agent.langsmith.automations import create_automations
from pov_agent.langsmith.context_hub import push_context_hub
from pov_agent.langsmith.datasets import ensure_production_dataset, populate_dataset
from pov_agent.langsmith.guardrails import GUARDRAIL_PROMPT_NAME, push_guardrail_prompt
from pov_agent.langsmith.offline_eval import run_offline_eval
from pov_agent.langsmith.traces import generate_traces
from pov_agent.privacy import install_trace_masking

_ONLINE_EVAL_FILE = Path(__file__).parent / "online_eval.py"


def _require_keys() -> None:
    import os

    if not os.environ.get("LANGSMITH_API_KEY"):
        sys.exit("LANGSMITH_API_KEY is not set. Copy .env.example to .env and fill it in.")
    using_gateway = os.environ.get("USE_LANGSMITH_GATEWAY", "true").lower() == "true"
    if not using_gateway and not any(
        os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
    ):
        print("⚠️  No LLM provider key found (ANTHROPIC/OPENAI/GOOGLE). Set the one your MODEL uses.")


def _upload_online_evaluator() -> None:
    """Upload the code evaluator that scores every live reply's channel format."""
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


def _confirm_workspace(client) -> None:
    """Print where the bootstrap is about to write, so a stray exported key is obvious."""
    try:
        session = client.read_project(project_name=PROJECT)
        tenant = session.tenant_id
    except Exception:
        tenant = None
    if tenant is None:
        try:
            resp = client.request_with_retries("GET", "/sessions", request_kwargs={"params": {"limit": 1}})
            sessions = resp.json()
            tenant = sessions[0].get("tenant_id") if sessions else "(new/empty workspace)"
        except Exception as exc:
            tenant = f"(could not resolve: {exc})"
    print(f"Target LangSmith workspace: {tenant}  |  project: {PROJECT}")


def main() -> None:
    _require_keys()
    # SDK masking (Level 3): one anonymizing client, used for every API call
    # here and installed as the process-wide tracing client.
    client = install_trace_masking()
    web = getattr(client, "_web_url", None) or "https://smith.langchain.com"
    _confirm_workspace(client)

    print("1/7 Context Hub + Prompt Hub — pushing system prompt, AGENTS.md, the support-playbook "
          "skill, and the guardrail judge prompt…")
    push_context_hub(client)
    push_guardrail_prompt(client)

    print("2/7 Dataset — creating golden voice + chat support turns…")
    populate_dataset(client)

    print(f"3/7 Traces — running the agent over seed turns into project '{PROJECT}' (redacted before egress)…")
    run_ids = generate_traces(client)
    print(f"     captured {len(run_ids)} root run(s)")

    print("4/7 Annotation queue — creating rubric and queueing runs for review…")
    queue = ensure_queue(client, run_ids)

    print("5/7 Offline eval — format, leak, action, resolution, privacy, guardrail, and channel-parity evaluators…")
    run_offline_eval(client)

    print("6/7 Online evaluator — attaching the channel-format evaluator to live traces…")
    _upload_online_evaluator()

    print("7/7 Automations — adding rules (queue routing + dataset growth)…")
    project_id = client.read_project(project_name=PROJECT).id
    create_automations(client, project_id, queue.id, ensure_production_dataset(client))

    print("\n✅ Done. Open your workspace and explore:")
    print(f"   {web}")
    print(f"   • Tracing project '{PROJECT}'  — traces + the online evaluator + automations")
    print("   • Datasets & Experiments        — the eval dataset and the offline experiment")
    print("   • Annotation Queues             — support turns waiting for human review")
    print("   • Context Hub                   — the agent repo (prompt, AGENTS.md, skill)")
    print(f"   • Prompts                       — '{GUARDRAIL_PROMPT_NAME}', the guardrail judge")


if __name__ == "__main__":
    main()
