"""CI eval gate: run the offline experiment and fail if quality regresses.

Run with:  uv run pov-eval-gate [--version v1|v2]

What it does:
  1. Resolves the agent version (``--version`` > ``AGENT_VERSION`` env > repo-root
     ``AGENT_VERSION`` file).
  2. Makes sure the golden dataset exists (idempotent).
  3. Runs a LangSmith experiment — correctness + fairness (openevals LLM-as-judge)
     and cites_sources (code) — tagged with the version, commit, and branch.
  4. Compares each mean score to ``config.CI_THRESHOLDS`` and exits non-zero if any
     falls short, which fails the GitHub Actions check on the push / PR.

The agent runs with ``local_context=True`` (a throwaway copy of the hub content), so
the gate needs only a LangSmith key and a model key — no Context Hub repo.
"""

import argparse
import os
import subprocess
import sys

from dotenv import load_dotenv
from langsmith import Client

from pov_agent.config import CI_THRESHOLDS, DATASET_NAME, resolve_agent_version
from pov_agent.langsmith.datasets import populate_dataset
from pov_agent.langsmith.offline_eval import mean_scores, run_offline_eval


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def check_thresholds(scores: dict[str, float], thresholds: dict[str, float] = CI_THRESHOLDS) -> list[str]:
    """Return human-readable failures; empty means the gate passes. Pure function."""
    failures = []
    for key, minimum in thresholds.items():
        got = scores.get(key)
        if got is None:
            failures.append(f"{key}: no scores recorded (threshold {minimum:.2f})")
        elif got < minimum:
            failures.append(f"{key}: {got:.2f} < {minimum:.2f}")
    return failures


def _report(version: str, scores: dict[str, float], failures: list[str], url: str) -> str:
    status = "❌ FAILED" if failures else "✅ PASSED"
    lines = [
        f"## Platform docs assistant eval gate — agent `{version}`: {status}",
        "",
        "| Evaluator | Mean score | Threshold | Result |",
        "|---|---|---|---|",
    ]
    for key, minimum in CI_THRESHOLDS.items():
        got = scores.get(key)
        ok = got is not None and got >= minimum
        lines.append(f"| `{key}` | {'—' if got is None else f'{got:.2f}'} | ≥ {minimum:.2f} | {'✅' if ok else '❌'} |")
    lines += ["", f"LangSmith experiment: {url}"]
    if failures:
        lines += ["", "**Failures:** " + "; ".join(failures)]
    return "\n".join(lines)


def run_gate(version: str | None = None, dataset_name: str = DATASET_NAME, max_concurrency: int = 4) -> dict:
    """Run the experiment and check thresholds. Returns a result dict ("passed", "scores", …)."""
    load_dotenv()
    version = resolve_agent_version(version)
    client = Client()
    populate_dataset(client, dataset_name)

    sha = os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or _git("rev-parse", "--abbrev-ref", "HEAD")
    print(f"Running eval gate for agent {version} on {branch}@{sha[:7]} against '{dataset_name}'…")

    results = run_offline_eval(
        client,
        version,
        local_context=True,
        data=dataset_name,
        experiment_prefix=f"ci-{version}-{sha[:7]}" if sha else f"ci-{version}",
        metadata={"ci": True, "git_sha": sha, "git_branch": branch, "event": os.environ.get("GITHUB_EVENT_NAME", "local")},
        max_concurrency=max_concurrency,
    )
    scores = mean_scores(results)
    failures = check_thresholds(scores)
    try:
        url = client.read_project(project_name=results.experiment_name).url
    except Exception:
        url = results.experiment_name

    report = _report(version, scores, failures, url)
    print("\n" + report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(report + "\n")
    return {
        "version": version,
        "passed": not failures,
        "scores": scores,
        "failures": failures,
        "experiment_name": results.experiment_name,
        "url": url,
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the platform docs assistant eval gate.")
    parser.add_argument("--version", default=None, help="Agent version to evaluate (default: AGENT_VERSION).")
    parser.add_argument("--dataset", default=DATASET_NAME)
    parser.add_argument("--max-concurrency", type=int, default=4)
    args = parser.parse_args()
    result = run_gate(args.version or None, args.dataset, args.max_concurrency)
    sys.exit(0 if result["passed"] else 1)


def _demo() -> None:
    assert check_thresholds({"correctness": 0.9, "fairness": 1.0, "cites_sources": 1.0}) == []
    fails = check_thresholds({"correctness": 0.4, "fairness": 1.0})
    assert len(fails) == 2 and fails[0].startswith("correctness"), fails
    print("ci_gate self-check passed")


if __name__ == "__main__":
    main()
