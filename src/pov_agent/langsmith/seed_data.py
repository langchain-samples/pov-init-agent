"""Golden topics for the evaluation dataset and for generating seed traces.

Each item is a report topic plus the points a good report on it must cover. The
``must_cover`` list is the reference the LLM-as-judge scores coverage against.
All topics are answerable from an LLM's own knowledge — no web access needed.
"""

SEED_TOPICS = [
    {
        "topic": "The trade-offs between microservices and a monolith for a mid-size engineering org",
        "must_cover": [
            "operational complexity and deployment overhead of microservices",
            "team autonomy and independent scaling benefits",
            "when a monolith is the better default",
        ],
    },
    {
        "topic": "How retrieval-augmented generation (RAG) improves LLM accuracy and where it falls short",
        "must_cover": [
            "grounding answers in retrieved context to reduce hallucination",
            "dependence on retrieval quality and chunking",
            "failure modes such as stale or missing documents",
        ],
    },
    {
        "topic": "Why observability matters for production LLM applications",
        "must_cover": [
            "non-determinism makes traditional testing insufficient",
            "tracing inputs, outputs, and intermediate steps",
            "feedback and evaluation loops on live traffic",
        ],
    },
    {
        "topic": "The business case for investing in developer platform engineering",
        "must_cover": [
            "reducing cognitive load and toil for product teams",
            "standardization and paved paths",
            "measuring ROI via lead time and reliability",
        ],
    },
    {
        "topic": "Evaluating build vs. buy for an internal AI assistant",
        "must_cover": [
            "total cost of ownership beyond licensing",
            "differentiation versus commodity capability",
            "time-to-value and maintenance burden",
        ],
    },
    {
        "topic": "Key risks of deploying autonomous agents in customer-facing roles",
        "must_cover": [
            "incorrect or harmful actions taken without review",
            "need for guardrails and human-in-the-loop",
            "auditability and accountability",
        ],
    },
    {
        "topic": "How feature flags reduce deployment risk",
        "must_cover": [
            "decoupling deploy from release",
            "progressive rollout and fast rollback",
            "added complexity and flag debt",
        ],
    },
    {
        "topic": "The role of human-in-the-loop review in AI workflows",
        "must_cover": [
            "catching errors the model cannot self-detect",
            "where to place review checkpoints",
            "cost and latency trade-offs of review",
        ],
    },
    {
        "topic": "Cost drivers of running large language models at scale",
        "must_cover": [
            "token volume and context length",
            "model size versus task fit",
            "caching, batching, and routing strategies",
        ],
    },
    {
        "topic": "Migrating a data pipeline from batch to streaming: when it's worth it",
        "must_cover": [
            "latency requirements that justify streaming",
            "operational complexity of streaming systems",
            "cases where batch remains the right choice",
        ],
    },
    {
        "topic": "Designing an effective on-call rotation for a small SRE team",
        "must_cover": [
            "sustainable rotation size and load",
            "clear escalation and runbooks",
            "blameless postmortems and follow-up",
        ],
    },
    {
        "topic": "Prompt engineering vs. fine-tuning: choosing an approach for a domain task",
        "must_cover": [
            "prompt engineering is faster and cheaper to iterate",
            "fine-tuning helps with consistent format and style at scale",
            "data and maintenance requirements of fine-tuning",
        ],
    },
]
