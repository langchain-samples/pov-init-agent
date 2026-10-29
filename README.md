# pov-init-agent — a voice + chat support agent that keeps sensitive data out of LangSmith

A new LangSmith workspace starts empty, which makes it hard to know where to begin.
This repo fixes that. It ships a small but real AI agent and **one command** that
connects to your workspace with an API key and pre-populates it with everything you'd
build over the first few weeks of a proof-of-concept:

- **Traces** — multi-step support conversations, **redacted before they leave your app**
- **A dataset** — golden voice and chat turns for evaluation
- **Evaluators, offline _and_ online** — resolution, privacy, sensitive-data leaks,
  correct actions, and channel fit
- **An annotation queue** — a human-review workflow with a scoring rubric
- **Automations** — rules that route live traffic to the queue and grow your dataset
- **Context Hub** — the agent's prompt, memory, and playbook skill, managed in LangSmith

The agent is a **customer support agent for a smart-TV brand** that serves two channels
from one graph:

- **Voice** — the customer's speech arrives as a speech-to-text transcript; the agent
  replies in short, speakable sentences for a text-to-speech layer (no markdown, numbers
  spoken as words, one step at a time).
- **Chat** — concise replies with numbered steps and help-center links.

It troubleshoots TVs (power, Wi-Fi, updates, remotes, panel faults), opens repair,
warranty, and billing tickets, and handles **Viewing Data (ACR)** privacy requests:
opt-outs, data-access requests, and deletion. Its backend data is shaped like real
smart-TV **ACR viewer data** — device, household, and advertising IDs, IP and MAC
addresses, coarse location, and raw viewing history — plus ordinary account PII. All of
it is synthetic.

That data is why this repo exists: it applies the practices in **`PHI Best
Practices.pdf`** ("Keeping sensitive data out of LangSmith") end to end.

---

## Sensitive-data controls (from `PHI Best Practices.pdf`)

The PDF's decision rule: *if the model should not see raw sensitive data — user-facing
intake, routing, agents handling unstructured user input — stack PII Middleware with SDK
masking.* A support agent is exactly that: it never needs a customer's email, card
number, MAC address, or watch history to fix a TV. So this repo stacks Levels 1 and 3,
and enables Level 2 by default.

| Level | Control | Where it lives | What it does here |
|---|---|---|---|
| **1** | **PII Middleware** | `privacy.build_pii_middleware()` → `agent.py` | Scrubs the customer's message, the model's output, **and tool results** before the model sees them. Custom detectors for SSNs, US phones, **spoken numbers** in voice transcripts, street addresses, TV serials, device/household IDs, coordinates, and viewing-history titles, alongside the built-in email, card, IP, and MAC detectors. Strategies: `mask` (cards, serials → last four), `redact`, `hash` (device/household IDs, so the model can tell them apart without seeing them). |
| **2** | **LLM Gateway** | `config.get_model()` (`USE_LANGSMITH_GATEWAY`, default on) | Routes agent + judge calls through the LangSmith LLM Gateway for centralized spend limits and gateway-side PII redaction (enable redaction in workspace settings). Catches what regex can't, e.g. person names. |
| **3** | **LangSmith SDK masking** | `privacy.install_trace_masking()` | An anonymizing `Client` becomes the process-wide tracing client. It catches what Level 1 can't: the raw graph input recorded on the root run, and model output before the middleware rewrites it. Redacts by key (`email`, `ip_address`, `content_title`, …) and by the same detectors as Level 1. |
| 4 | Engine (optional) | LangSmith UI | Detection backstop that monitors stored traces and flags anything that slipped through. Not configured by this repo. |

Gaps the PDF calls out, and how this repo closes them:

- **`apply_to_tool_results` is the most commonly missed knob.** It's on. Tools
  deliberately return over-shared payloads (contact details, card on file, IP/MAC, raw
  ACR events) so you can see the middleware strip them in the trace.
- **Middleware doesn't help other code paths.** Deep Agents auto-adds a
  `general-purpose` subagent that doesn't inherit user middleware. `agent.py` overrides
  it with the same PII middleware and no customer-data tools.
- **SDK masking only covers runs.** Direct LangSmith writes — Context Hub commits and
  dataset uploads — bypass it. So the agent's Context Hub access is **read-only**
  (filesystem permissions deny writes outside `/scratch/`), and the dataset is synthetic.
- **Identity comes from the session, not the conversation.** The channel (chat sign-in
  or the phone line's PIN check) passes `account_id` and `identity_verified` in graph
  state. Tools read them directly, so the model never asks for an email or SSN, and
  every account tool refuses when the caller isn't verified.

One detector set (`privacy.DETECTORS`) feeds both Level 1 and Level 3, so a pattern you
add is enforced everywhere. Run `uv run python -m pov_agent.privacy` to self-check it.

### Voice calls and audio

Voice scenarios run through real audio (`voice.py`). Each becomes a `voice_call` trace:

```
voice_call
├── speech_to_text   caller audio → transcript   (gpt-4o-mini-transcribe)
├── <agent>          transcript → reply text
└── text_to_speech   reply text → reply audio    (gpt-4o-mini-tts, attached to the trace)
```

The caller audio is synthesized once per scenario and cached in
`src/pov_agent/langsmith/voice_fixtures/`. **None of the controls above can redact
audio** — a recording of someone reading out a card number is stored as-is, and a voice
can identify the speaker. So caller audio is transcribed in-process and **never attached
to traces** (`ATTACH_CALLER_AUDIO=false`); only the transcript is traced, where SDK
masking scrubs it. The agent's reply audio **is** attached, because it is synthesized
from reply text the PII middleware already redacted. Set `VOICE_AUDIO=false` to run voice
turns as text transcripts instead.

---

## Prerequisites

1. **A LangSmith account + API key.** Create a key under **Settings → API Keys**.
   - Use a **workspace-scoped** key (the default). It resolves its own workspace and
     needs nothing else.
   - If you only have an **org-scoped** key, also set `LANGSMITH_WORKSPACE_ID` in `.env`.
2. **Model access** — via the LangSmith LLM Gateway (default; uses your LangSmith key), or
   set `USE_LANGSMITH_GATEWAY=false` and provide one provider key (Anthropic, OpenAI, or
   Google) for whichever provider `MODEL` points at.
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
> any time you change the prompt, the dataset, or the seed scenarios.

---

## Guided tour: what got created, and what each thing is

### 1. Tracing — see what your agent did, without seeing your customers' data
Open the **Tracing** project named **`pov-support-agent`**. Each seed scenario produced a
trace: the agent looking up the account, pulling diagnostics, searching the help center,
taking an action, and replying in the channel's style. Open a tool span and you'll see
`[REDACTED_IP]`, `****1188`, and `<device_id_hash:…>` where the backend returned raw
values; open the root run and the customer's own card number or spoken phone number is
redacted too. Filter by channel with the `channel` metadata key.
→ [Observability docs](https://docs.langchain.com/langsmith/observability)

### 2. Datasets & Experiments — measure quality on known-good examples
Open **Datasets & Experiments → `pov-support-agent-eval`**. It holds a dozen support turns
split evenly across voice and chat — troubleshooting, warranty and billing, opt-outs,
data requests, an unverified caller, and customers who volunteer card numbers or SSNs.
Each example carries the points a good resolution must address, the privacy expectation
for that turn, and the actions that must (and must not) be taken. Running the agent over
it produces an **experiment** — that's **offline evaluation**.
→ [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)

### 3. Evaluators — offline and online
Each support turn is scored six ways offline; the channel check also runs online:

- **`channel_format`** (offline code + online) — voice replies are speakable (no markdown,
  URLs, or digit strings; ≤ 75 words); chat replies are concise.
- **`no_sensitive_data_leak`** (offline code) — the reply contains no raw sensitive value:
  no detector hit and no literal value from the backend (serials, IPs, viewing titles…).
  This measures the PII middleware end to end.
- **`action_correctness`** (offline code) — the expected actions were taken and the
  forbidden ones weren't (e.g. no deletion for an unverified caller).
- **`resolution_quality`** (offline, LLM-as-judge) — does the reply cover the reference
  must-address points?
- **`privacy_compliant`** (offline, LLM-as-judge) — no viewing history disclosed, no
  identifiers read out, oversharing discouraged, no account action when unverified.
- **`channel_parity`** (offline) — replays the same request on the *other* channel and
  checks the agent takes the same actions. Voice and chat may differ in style, never in
  outcome.

Online evaluators run on traces **after** SDK masking, so they never touch raw data.
→ [Online evaluators](https://docs.langchain.com/langsmith/code-evaluator-ui) ·
  [Offline evaluation](https://docs.langchain.com/langsmith/evaluate-llm-application)

> `channel_parity` invokes the agent a second time per example, so the offline experiment
> spends roughly twice the tokens of a single-pass eval.

### 4. Annotation queues — put a human in the loop
Open **Annotation Queues → `pov-support-review`**. A handful of support turns are queued
with a rubric: a resolution score, a pass/fail **privacy-compliant** check, a pass/fail
**channel-appropriate** check, and notes. Reviewers work from redacted traces, so human
review never requires exposing customer data.
→ [Annotation queues](https://docs.langchain.com/langsmith/annotation-queues)

### 5. Automations — make the workspace work on its own
Back in the **`pov-support-agent`** project, open **Automations**. Two rules are live:
- **Route sampled support turns to the review queue** — 50% of new runs go to humans.
- **Sample production turns for labeling** — 30% of new runs are added to
  `pov-support-agent-production-samples`. That's deliberately *not* the golden eval
  dataset: sampled traces have no reference answers, so a person writes them before
  promoting an example into `pov-support-agent-eval`.

Both act on already-redacted traces.
→ [Automation rules](https://docs.langchain.com/langsmith/rules)

### 6. Context Hub — manage the agent's brain in LangSmith
Open **Context Hub**. The **agent repo** `pov-support-agent` holds the **system prompt**,
the team-curated memory **`AGENTS.md`**, and a link to the **`support-playbook`** skill
(troubleshooting flows, the Viewing Data privacy policy, identity rules, ticket types).
Edit them here to change the agent **without a redeploy**. The agent reads them but
can't write back, so customer data never lands in the Hub.
→ [Context Hub](https://docs.langchain.com/langsmith/context-hub)

---

## The agent, explained

It's a [**Deep Agent**](https://docs.langchain.com/oss/python/deepagents/overview)
(LangGraph under the hood). Each turn's input carries the session alongside the message:

```python
{
    "messages": [{"role": "user", "content": "<message or STT transcript>"}],
    "channel": "voice",            # or "chat"
    "account_id": "ACC-1001",      # set by the channel after authentication
    "identity_verified": True,
}
```

- **`ChannelMiddleware`** (`channels.py`) adds those fields to the agent's state and
  appends the active channel's style rules to the system prompt on every model call.
  `account_id` is never put in the prompt.
- **Tools** (`tools.py`): `get_account_overview`, `get_device_diagnostics`,
  `search_help_center`, `get_viewing_data_status`, `set_viewing_data_collection`,
  `submit_privacy_request`, `create_support_ticket` — backed by synthetic data in
  `support_data.py`.
- **PII middleware** (`privacy.py`) wraps the loop as described above.
- **Filesystem**: a composite backend — the prompt, `/AGENTS.md`, and `/skills/` come from
  the Context Hub (read-only); `/scratch/` and the deep agent's internal paths go to an
  in-memory `StateBackend`.

The graph is defined in `src/pov_agent/agent.py` and registered in `langgraph.json`.

---

## Run and modify the agent yourself

Launch it locally in LangGraph Studio (hot-reloads on edits):

```bash
uv run langgraph dev
```

Send it an input like the one above and watch the redacted trace appear in LangSmith.

**Customize:**
- **Prompt / memory / skill** — edit them in the Context Hub (or edit
  `src/pov_agent/langsmith/hub_content/` and re-run `uv run pov-bootstrap` to push).
- **Detectors and strategies** — `DETECTORS`, `STRATEGIES`, and `SENSITIVE_KEYS` in
  `src/pov_agent/privacy.py`.
- **Channel style** — `VOICE_STYLE`, `CHAT_STYLE`, and the word limits in
  `src/pov_agent/config.py`.
- **Scenarios** — `src/pov_agent/langsmith/seed_data.py`; backend data in
  `src/pov_agent/support_data.py`.
- **Evaluators** — `src/pov_agent/langsmith/evaluators.py` (offline) and `online_eval.py`
  (online). The channel rule is intentionally duplicated between them because the online
  evaluator runs in a sandbox that can't import the repo.
- **Object names** — all in `src/pov_agent/config.py`.

Notebooks in `src/pov_agent/modules/` walk through the same concepts interactively:
`langsmith_walkthrough.ipynb` (controls in action, tracing, evals, queues) and
`prompt_iteration.ipynb` (pairwise model comparison and Align Evals).

---

## Deploy the agent (optional)

```bash
uv run langgraph dev      # local dev server + Studio
uv run langgraph deploy   # deploy to LangSmith Deployments (requires Docker)
```

Set `MODEL` and your model credentials as env vars on the deployment —
`LANGSMITH_API_KEY` is injected automatically. Run `uv run pov-bootstrap` in the same
workspace first so the Context Hub repo exists. SDK masking is installed when the graph
module loads, so deployed traces are anonymized in-process too; verify it on your first
deployed trace.

→ [LangSmith Deployments docs](https://docs.langchain.com/langsmith/deploy-to-cloud)

---

## Choosing a model (provider-agnostic)

The agent and the LLM-as-judge both read the `MODEL` env var, in `provider:model` form:

```bash
MODEL=openai:gpt-5.4-nano          # default
# MODEL=anthropic:claude-sonnet-4-6
# MODEL=google_genai:gemini-2.5-flash
```

With the gateway on (default), calls go through the LangSmith LLM Gateway using your
LangSmith key. Set `USE_LANGSMITH_GATEWAY=false` to call the provider directly with its
own key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`).

---

## Project layout

```
src/pov_agent/
├── config.py                 # model + gateway, channel rules, LangSmith object names
├── agent.py                  # the deep agent (middleware, tools, Context Hub backend)
├── channels.py               # session state + voice/chat style middleware
├── privacy.py                # detectors, PII middleware (L1), SDK masking (L3)
├── tools.py                  # support tools (session-scoped, identity-gated)
├── support_data.py           # synthetic accounts, devices, ACR events, help center
├── runner.py                 # one way to invoke a turn (traces, evals, notebooks)
├── voice.py                  # audio pipeline: caller audio → STT → agent → TTS
├── modules/                  # walkthrough + prompt-iteration notebooks
└── langsmith/
    ├── bootstrap.py          # `pov-bootstrap` — orchestrates every step
    ├── context_hub.py        # pushes prompt + AGENTS.md + skill to the Hub
    ├── datasets.py           # creates the eval dataset
    ├── traces.py             # runs the agent to generate seed traces
    ├── annotation_queues.py  # feedback configs + queue + seeds runs
    ├── evaluators.py         # offline: format, leak, actions, resolution, privacy, parity
    ├── online_eval.py        # online: self-contained channel-format evaluator
    ├── offline_eval.py       # runs the offline experiment
    ├── automations.py        # creates the run rules (REST)
    ├── seed_data.py          # the voice + chat scenarios and references
    └── hub_content/          # the prompt, AGENTS.md, and SKILL.md pushed to the Hub
```

---

## Notes

- Secrets live in `.env` (gitignored). Only `.env.example` is committed. Never commit a
  real key.
- All customer data in this repo is synthetic: card numbers are public test numbers,
  phone numbers use the fictional 555-01xx range, and names, addresses, and IDs are
  invented. Never seed the dataset with real conversations — dataset uploads bypass SDK
  masking.
- Regex detectors are a floor, not a ceiling. Names and free-form addresses are hard to
  catch with patterns; that's what the gateway's Presidio-based redaction (Level 2) and
  Engine monitoring (Level 4) add.
