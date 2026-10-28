"""Drive the CI eval gate from a notebook: ship an agent version, watch the check.

``ship_version`` makes a commit that sets the repo-root ``AGENT_VERSION`` file and
pushes it to a fresh demo branch on the remote. It works in a temporary, detached
``git worktree`` created from your current ``HEAD``, so your working tree, current
branch, and local branch list are never touched. Commit your changes first: anything
uncommitted is not in the pushed branch.

``wait_for_ci`` polls the GitHub Actions run for that branch with the ``gh`` CLI and
returns its conclusion ("success" / "failure").

Nothing here force-pushes or deletes remote branches.
"""

import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pov_agent.config import REPO_ROOT, available_agent_versions

WORKFLOW_FILE = "agent-eval-gate.yml"


def _run(*cmd: str, cwd=REPO_ROOT) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.rstrip()


def uncommitted_changes() -> list[str]:
    """Tracked files with uncommitted changes (they would NOT be in a shipped branch)."""
    return [line for line in _run("git", "status", "--porcelain", "--untracked-files=no").splitlines() if line]


def ship_version(version: str, *, base: str = "HEAD", remote: str = "origin", branch: str | None = None) -> str:
    """Commit AGENT_VERSION=<version> on a new branch off ``base`` and push it.

    Returns the branch name. The push triggers the Agent eval gate workflow.
    """
    if version not in available_agent_versions():
        raise ValueError(f"Unknown version {version!r}; expected one of {available_agent_versions()}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = branch or f"ci-demo/{version}-{stamp}"
    worktree = tempfile.mkdtemp(prefix="pov-ci-demo-")
    _run("git", "worktree", "add", "--detach", worktree, base)
    try:
        Path(worktree, "AGENT_VERSION").write_text(f"{version}\n")
        _run("git", "add", "AGENT_VERSION", cwd=worktree)
        if _run("git", "status", "--porcelain", cwd=worktree):
            _run("git", "commit", "-m", f"ci demo: ship agent {version}", cwd=worktree)
        else:
            _run("git", "commit", "--allow-empty", "-m", f"ci demo: ship agent {version} (unchanged)", cwd=worktree)
        _run("git", "push", remote, f"HEAD:refs/heads/{branch}", cwd=worktree)
    finally:
        _run("git", "worktree", "remove", "--force", worktree)
    return branch


def latest_run(branch: str) -> dict | None:
    out = _run(
        "gh", "run", "list", "--workflow", WORKFLOW_FILE, "--branch", branch, "--limit", "1",
        "--json", "databaseId,status,conclusion,url,headSha,displayTitle",
    )
    runs = json.loads(out or "[]")
    return runs[0] if runs else None


def wait_for_ci(branch: str, timeout_s: int = 1200, poll_s: int = 15) -> dict:
    """Block until the branch's workflow run completes; return the run dict."""
    deadline = time.time() + timeout_s
    run, last_status = None, None
    while time.time() < deadline:
        run = latest_run(branch)
        status = run and run["status"]
        if status != last_status:
            print(f"[{branch}] {status or 'waiting for run to start'}" + (f" — {run['url']}" if run else ""))
            last_status = status
        if run and run["status"] == "completed":
            return run
        time.sleep(poll_s)
    raise TimeoutError(f"CI for {branch} did not finish in {timeout_s}s (last: {run})")


def open_pr(branch: str, base: str, title: str | None = None) -> str:
    """Open a PR from ``branch`` into ``base`` (the gate runs on the PR too). Returns its URL."""
    return _run(
        "gh", "pr", "create", "--head", branch, "--base", base,
        "--title", title or f"CI demo: {branch}",
        "--body", "Demo PR: the Agent eval gate runs the LangSmith experiment and passes or fails this check.",
    )
