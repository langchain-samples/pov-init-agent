# pov-init-agent — get a head start on your LangSmith trial

A new LangSmith workspace starts empty, which makes it hard to know where to begin.
This repo fixes that. It ships a small but real AI agent and **one command** that
connects to your workspace with an API key and pre-populates it with everything you'd
build over the first few weeks of a proof-of-concept:

- **Traces** — multi-step runs from a working agent
- **A dataset** — golden examples for evaluation
- **Evaluators, offline _and_ online** — quality checks plus a **bias/fairness** check
  that measures the agent's efficacy, run on test data and on live traffic
- **An annotation queue** — a human-review workflow with a scoring rubric
- **Automations** — rules that route live traffic to the queue and grow your dataset
- **Context Hub** — the agent's prompt, memory, and a skill, managed in LangSmith

You get a workspace that already looks like a project in flight, and this README
doubles as a guided tour of each LangSmith concept.

The agent is a **resume-to-job matcher**: give it a job description and a candidate's
resume, it extracts the role's requirements, assesses the resume against each one, and
returns a structured markdown review with a **match score (0.0–1.0)**, strengths, gaps,
and a recommendation. It needs **only an LLM API key** — no web search or other external
services — so it's easy to run.

Because match decisions are exactly where models can absorb bias, the repo ships a
**bias/fairness evaluator** that checks the agent's efficacy two ways (see §3).

---

## Prerequisites

1. **A LangSmith account + API key.** Create a key under **Settings → API Keys**.
   - Use a **workspace-scoped** key (the default). It resolves its own workspace and
     needs nothing else.
   - If you only have an **org-scoped** key, also set `LANGSMITH_WORKSPACE_ID` in `.env`.
2. **One LLM provider key** — Anthropic, OpenAI, or Google. You only need the one your
   `MODEL` points at.
3. **[uv](https://docs.astral.sh/uv/)** for Python (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

---

## Quickstart

```bash
git clone <this-repo> && cd pov-init-agent
uv sync                       # create the venv and install everything
cp .env.example .env          # then open .env and fill in your keys
uv run pov-bootstrap          # populate your workspace (~a few minutes)
```

`pov-bootstrap` prints its progress step by step and finishes with a link to your
workspace. Open it and start exploring — the guided tour below tells you what to look at.

> The bootstrap is **idempotent**: re-running it won't create duplicates. Re-run it
> any time you change the prompt, the dataset, or the seed pairs.

---

## Guided tour: what got created, and what each thing is

### 1. Tracing — see what your agent actually did
Open the **Tracing** project named **`pov-job-matcher`**. Each seed resume/JD pair
produced a trace: a tree of steps showing the agent extracting requirements, assessing
each one, and synthesizing the final review — with inputs, outputs, token counts, and
latency at every step. Tracing is the foundation everything else builds on.
→ [Observability docs](https://docs.langchain.com/langsmith/observability)

### 2. Datasets & Experiments — measure quality on known-good examples
Open **Datasets & Experiments → `pov-job-matcher-eval`**. It holds a dozen resume/JD
pairs — a mix of strong, borderline, and weak candidates — each with the points a sound
review *must address*. Running the agent over this dataset produces an **experiment**
with scores per example — that's **offline evaluation**: testing against fixed examples
before you ship.
→ [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)

### 3. Evaluators — quality *and* fairness, offline and online
This repo scores each match review four ways offline, and deploys the structure check
online too:

- **`match_structure`** (offline code + online) — deterministic: does the review have the
  required sections *and* a parseable `Match score:`?
- **`match_quality`** (offline, LLM-as-judge) — does the review engage the reference
  must-address points with evidence?
- **`reasoning_unbiased`** (offline, LLM-as-judge) — a **bias check on the agent's own
  output**: does the review's reasoning stay off protected attributes (name, gender, age,
  race, national origin, religion, disability, family status, school prestige)? Scores
  1.0 when fair, 0.0 when biased.
- **`counterfactual_fairness`** (offline) — the **efficacy check**: it re-runs the agent
  on protected-attribute-swapped variants of the *same* resume (different names and
  pronouns) and measures how much the match score moves. A stable score across variants =
  1.0; a score that swings with the candidate's name decays toward 0.0. This is the
  strongest signal that the agent is matching qualifications, not people.

Offline tells you "is the new version better *and fairer* than the old one on our test
set?" Online (`match-structure`, on the live project) tells you "how is structure
compliance trending on real traffic right now?"
→ [Online evaluators](https://docs.langchain.com/langsmith/code-evaluator-ui) ·
  [Offline evaluation](https://docs.langchain.com/langsmith/evaluate-llm-application)

> The counterfactual evaluator invokes the agent several times per example (once per
> attribute variant), so the offline experiment spends more tokens than a single-pass
> eval. That cost is the point: fairness is measured by *behavior under perturbation*,
> not by asking the model whether it's fair.

### 4. Annotation queues — put a human in the loop
Open **Annotation Queues → `pov-match-review`**. A handful of generated reviews are
queued for human review, with a **rubric**: an overall analysis-quality score, a pass/fail
**fair-reasoning** check, a pass/fail **score-calibrated** check, and a free-text notes
field. This is how subject-matter experts grade outputs — including for bias — and build
trustworthy datasets.
→ [Annotation queues](https://docs.langchain.com/langsmith/annotation-queues)

### 5. Automations — make the workspace work on its own
Back in the **`pov-job-matcher`** project, open **Automations**. Two rules are live:
- **Route sampled match reviews to the review queue** — 50% of new runs go to humans.
- **Grow the eval dataset from production** — 30% of new runs are added to a dataset,
  so your test set reflects real usage over time.

Rules match traces with a filter and fire an action (queue, dataset, webhook, or an
evaluator). They're how a trial graduates into a real feedback loop.
→ [Automation rules](https://docs.langchain.com/langsmith/rules)

### 6. Context Hub — manage the agent's brain in LangSmith
Open **Context Hub**. You'll see an **agent repo** `pov-job-matcher` containing the
agent's **system prompt**, its long-term memory **`AGENTS.md`**, and a link to the
**`match-rubric-guide`** skill repo. Editing these here changes the agent's behavior
**without a redeploy** — and the agent writes lessons back to `AGENTS.md` as it runs.
→ [Context Hub](https://docs.langchain.com/langsmith/context-hub)

---

## The agent, explained

It's a [**Deep Agent**](https://docs.langchain.com/oss/python/deepagents/overview)
(LangGraph under the hood) wired to a **composite filesystem backend**:

```
CompositeBackend(
    default = ContextHubBackend("pov-job-matcher"),   # prompt, /AGENTS.md, /skills/ live in LangSmith
    routes  = { "/scratch/", "/large_tool_results/", "/conversation_history/" -> StateBackend() },
)
```

- **Durable files** (the prompt, the `AGENTS.md` memory, and the skill) are served from
  the **Context Hub**, so they're versioned and editable in LangSmith.
- **Ephemeral files** (section drafts the agent writes to `/scratch/`, plus the deep
  agent's own internal scratch paths) go to an in-memory `StateBackend`, so they never
  clutter the Hub with commits.

At runtime the agent: **plans** by extracting the role's requirements → **assesses** the
resume against each one, drafting to `/scratch/` → **synthesizes** the final review with a
match score. That's what produces the rich, multi-step traces.

The graph is defined in `src/pov_agent/agent.py` and registered in `langgraph.json`.

---

## Run and modify the agent yourself

Launch it locally in LangGraph Studio (hot-reloads on edits):

```bash
uv run langgraph dev
```

Then send it a job description + resume and watch the trace appear in LangSmith.

**Customize:**
- **Prompt / memory / skill** — edit them in the Context Hub (or edit
  `src/pov_agent/langsmith/hub_content/` and re-run `uv run pov-bootstrap` to push).
- **Dataset pairs** — edit `src/pov_agent/langsmith/seed_data.py`.
- **Evaluators** — `src/pov_agent/langsmith/evaluators.py` (offline: structure, quality,
  and both fairness evaluators) and `online_eval.py` (online). The structure rule is
  intentionally duplicated between them because the online evaluator runs in a sandbox
  that can't import the repo.
- **Fairness knobs** — the protected-attribute swaps and the match-score tolerance live in
  `src/pov_agent/config.py` (`PROTECTED_ATTRIBUTE_SWAPS`, `MATCH_SCORE_TOLERANCE`).
- **Object names** — all in `src/pov_agent/config.py`.

---

## Deploy the agent (optional)

Run it locally, or ship it to **LangSmith Deployments** for a hosted, always-on endpoint:

```bash
uv run langgraph dev      # local dev server + Studio
uv run langgraph deploy   # deploy to LangSmith Deployments (requires Docker)
```

Set `MODEL` and your provider key (e.g. `ANTHROPIC_API_KEY`) as env vars on the
deployment — `LANGSMITH_API_KEY` is injected automatically. Run `uv run pov-bootstrap` in
the same workspace first so the Context Hub repo exists. The deployment spends whatever
provider key you set on it.

→ [LangSmith Deployments docs](https://docs.langchain.com/langsmith/deploy-to-cloud)

---

## Choosing a model (provider-agnostic)

The agent and the LLM-as-judge both read the `MODEL` env var, in `provider:model` form:

```bash
MODEL=anthropic:claude-sonnet-4-6     # default
# MODEL=openai:gpt-5.1
# MODEL=google_genai:gemini-2.5-flash
```

Set the API key for whichever provider you pick (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
or `GOOGLE_API_KEY`). Nothing else changes.

> **Optional — LLM Gateway.** For centralized key management and spend controls, you can
> route model calls through the [LangSmith LLM Gateway](https://docs.langchain.com/langsmith/llm-gateway)
> instead of using a provider key directly. Not required for this repo.

---

## Project layout

```
src/pov_agent/
├── config.py                 # model + all LangSmith object names + fairness knobs
├── agent.py                  # the deep agent (composite backend + Context Hub)
└── langsmith/
    ├── bootstrap.py          # `pov-bootstrap` — orchestrates every step
    ├── context_hub.py        # pushes prompt + AGENTS.md + skill to the Hub
    ├── datasets.py           # creates the eval dataset (resume/JD pairs)
    ├── traces.py             # runs the agent to generate seed traces
    ├── annotation_queues.py  # feedback configs + queue + seeds runs
    ├── evaluators.py         # offline: structure (code) + quality + fairness judges + counterfactual
    ├── online_eval.py        # online: self-contained structure evaluator
    ├── offline_eval.py       # runs the offline experiment
    ├── automations.py        # creates the run rules (REST)
    ├── seed_data.py          # the resume/JD pairs + must-address points
    └── hub_content/          # the prompt, AGENTS.md, and SKILL.md pushed to the Hub
```

---

## Notes

- Secrets live in `.env` (gitignored). Only `.env.example` is committed. Never commit a
  real key.
- A note on naming: LangSmith and Deep Agents use **`AGENTS.md`** for an agent's memory
  file; that's the "AGENT.md" this repo creates.
- The counterfactual-fairness evaluator perturbs candidate names and pronouns to *test*
  the agent; those placeholder identities are a fairness fixture, not real data.
