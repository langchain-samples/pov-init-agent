# pov-init-agent — get a head start on your LangSmith trial

A new LangSmith workspace starts empty, which makes it hard to know where to begin.
This repo fixes that. It ships a small but real AI agent and **one command** that
connects to your workspace with an API key and pre-populates it with everything you'd
build over the first few weeks of a proof-of-concept:

- **Traces** — multi-step runs from a working agent
- **A dataset** — golden questions with reference answers, including fairness probes
- **Evaluators, offline _and_ online** — out-of-the-box LLM-as-judge **correctness** and
  **fairness** evaluators, plus a code check
- **A CI/CD eval gate** — the same experiment runs on every push and PR, and fails the
  check when scores regress
- **An annotation queue** — expert review with a matching rubric
- **Automations** — rules that route live traffic to the queue and grow your dataset
- **Context Hub** — the agent's prompt, memory, and a skill, managed in LangSmith

The agent is a **platform docs assistant**. It answers questions about **Nimbus AI
Platform**, a fictional private AI platform (an on-prem GPU cluster with a data-science
workbench, model serving, and a catalog of ML tools): what the platform is, and how to run
things on it. It searches a bundled docs corpus with two tools and cites what it used. It
needs **only an LLM API key**: no web search or other external services.

---

## Prerequisites

1. **A LangSmith account + API key.** Create a key under **Settings → API Keys**.
   - Use a **workspace-scoped** key (the default).
   - If you only have an **org-scoped** key, also set `LANGSMITH_WORKSPACE_ID` in `.env`.
2. **An LLM provider key** for `MODEL` (the agent) and `JUDGE_MODEL` (the evaluators).
3. **[uv](https://docs.astral.sh/uv/)** for Python (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

---

## Quickstart

```bash
git clone <this-repo> && cd pov-init-agent
uv sync                       # create the venv and install everything
cp .env.example .env          # then open .env and fill in your keys
uv run pov-bootstrap          # populate your workspace (~a few minutes)
uv run pov-eval-gate          # run the CI eval gate locally (exit 1 = fail)
```

The bootstrap is **idempotent**: re-running it won't create duplicates.

---

## Guided tour

### 1. Tracing
Open the **Tracing** project **`pov-docs-assistant`**. Each seed question produced a trace
showing the agent searching the docs, reading pages, and answering, with inputs, outputs,
tokens, and latency at every step.
→ [Observability docs](https://docs.langchain.com/langsmith/observability)

### 2. Datasets & Experiments
Open **Datasets & Experiments → `pov-docs-qa-eval`**. It holds ten questions, each with a
reference answer written from the docs. Five are **fairness probes**: the same kind of
technical question from someone who writes in non-fluent English, mentions their age, or
says they're junior or not an engineer. Each probe also carries a `neutral_question` (the
same question without the persona) so fairness can be tested counterfactually.
→ [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)

### 3. Evaluators
- **`correctness`** (offline, LLM-as-judge) — the prebuilt
  [openevals](https://github.com/langchain-ai/openevals) `CORRECTNESS_PROMPT`, graded
  against the reference answer.
- **`fairness`** (offline, LLM-as-judge) — the prebuilt openevals `FAIRNESS_PROMPT`, shown
  the persona's answer and the neutral answer side by side, so unequal treatment is visible.
  1.0 means no bias detected.
- **`cites_sources`** (offline code + online) — deterministic: does the answer end with a
  `Sources:` line that names real docs?

The judges run on `JUDGE_MODEL`, which should be stronger than the agent's model: small
judges are lenient.

### 4. The CI/CD eval gate
Two versions of the agent live in `src/pov_agent/agent_versions/`, and the one-line
repo-root **`AGENT_VERSION`** file picks which one ships:

| Version | What it is | Gate |
|---|---|---|
| `v1` | Searches the docs, cites sources, gives everyone the same complete answer | ✅ passes |
| `v2` | A "faster, audience-aware" regression: drops the docs tools and waters down answers for some users | ❌ fails correctness, fairness, and cites_sources |

`.github/workflows/agent-eval-gate.yml` runs `uv run pov-eval-gate` on every push and PR.
The gate runs a LangSmith experiment (tagged with the commit and branch), compares each mean
score to `CI_THRESHOLDS` in `src/pov_agent/config.py`, writes a score table to the job
summary, and exits non-zero if any score falls short.

To try it, add the repository secrets `LANGSMITH_API_KEY` and `OPENAI_API_KEY` (or your
provider's key), then push a branch with `AGENT_VERSION` set to `v1` and another with `v2`.
The evaluation notebook can push both for you (Part 3).

### 5. Annotation queue
**Annotation Queues → `pov-docs-answer-review`** has a rubric that mirrors the automated
evaluators: answer correctness, fair treatment, grounded in the docs, plus notes.
→ [Annotation queues](https://docs.langchain.com/langsmith/annotation-queues)

### 6. Automations
Two rules on the tracing project: send 50% of new runs to the review queue, and add 30% to
the dataset.
→ [Automation rules](https://docs.langchain.com/langsmith/rules)

### 7. Context Hub
The **agent repo** `pov-docs-assistant` holds the system prompt (mirrored from git), the
`AGENTS.md` memory, and a link to the **`docs-answer-guide`** skill.
→ [Context Hub](https://docs.langchain.com/langsmith/context-hub)

---

## Notebooks

- **`src/pov_agent/modules/langsmith_walkthrough.ipynb`** — the evaluation module: tracing,
  offline correctness + fairness evals, the CI/CD gate (including pushing `v1` and `v2` to
  GitHub and watching one pass and one fail), online evals, and the annotation queue.
- **`src/pov_agent/modules/prompt_iteration.ipynb`** — pairwise (A/B) evaluation for a
  model migration, and Align Evals for a house-style judge.

---

## Run and modify the agent

```bash
uv run langgraph dev      # local dev server + Studio
```

- **Docs corpus** — `src/pov_agent/platform_docs/`. Replace it with an export of your own
  docs; the search tool picks up any `.md` file.
- **Agent versions** — `src/pov_agent/agent_versions/` (system prompt + front matter for
  tools / skills / memory).
- **Dataset** — `src/pov_agent/langsmith/seed_data.py`. The gate syncs the LangSmith
  dataset to this file on every run.
- **Evaluators** — `src/pov_agent/langsmith/evaluators.py` (offline) and `online_eval.py`
  (online, self-contained because the sandbox can't import the repo).
- **Thresholds, models, object names** — `src/pov_agent/config.py`.

---

## Choosing models

```bash
MODEL=openai:gpt-5.4-nano          # the agent
JUDGE_MODEL=openai:gpt-5.4-mini    # the LLM-as-judge evaluators
```

Use any `provider:model` LangChain supports, and set that provider's API key.

---

## Project layout

```
AGENT_VERSION                 # which agent version ships (v1 | v2)
.github/workflows/agent-eval-gate.yml
src/pov_agent/
├── config.py                 # models, agent versions, CI thresholds, object names
├── agent.py                  # the deep agent (composite backend + Context Hub)
├── tools.py                  # search_platform_docs / read_platform_doc
├── agent_versions/           # v1.md (passes), v2.md (fails)
├── platform_docs/            # the bundled docs corpus
└── langsmith/
    ├── bootstrap.py          # `pov-bootstrap`
    ├── ci_gate.py            # `pov-eval-gate`: experiment + thresholds
    ├── ci_demo.py            # push a version to a demo branch, wait for the check
    ├── evaluators.py         # correctness + fairness (openevals) + cites_sources
    ├── offline_eval.py       # runs the offline experiment
    ├── online_eval.py        # online code evaluator
    ├── datasets.py           # syncs the dataset from seed_data.py
    ├── seed_data.py          # golden questions + fairness probes
    ├── traces.py, annotation_queues.py, automations.py, context_hub.py
    └── hub_content/          # AGENTS.md + the docs-answer-guide skill
```

---

## Notes

- Secrets live in `.env` (gitignored). Only `.env.example` is committed.
- Nimbus AI Platform and its docs are fictional and exist for this demo.
