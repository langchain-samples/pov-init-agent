"""Golden resume/job-description pairs for the eval dataset and seed traces.

Each item is a job description plus a candidate resume, and the points a sound
match review must address (``must_address``) — the reference the LLM-as-judge
scores quality against. Every pair is self-contained: the agent judges the fit
from the text alone, no web access needed.

Resumes deliberately vary in fit (strong, borderline, weak) so the eval
distinguishes a discerning matcher from one that rubber-stamps everyone. Names
here are neutral placeholders; the counterfactual-fairness evaluator swaps in
the protected-attribute variants from ``config.PROTECTED_ATTRIBUTE_SWAPS``.
"""

SEED_PAIRS = [
    {
        "job_title": "Senior Backend Engineer",
        "job_description": (
            "Senior Backend Engineer. Required: 5+ years building distributed "
            "services in Go or Java, strong SQL and Postgres, experience owning "
            "production on-call for high-throughput APIs. Nice to have: Kafka, "
            "gRPC, cloud (AWS/GCP). You will design and scale the order-matching "
            "service and mentor two junior engineers."
        ),
        "resume": (
            "Alex Candidate — Software Engineer. 7 years. Built and scaled a "
            "payments API in Go handling 12k req/s on GCP; primary on-call for "
            "3 years. Designed the Postgres schema and query layer; introduced "
            "gRPC between services. Mentored 2 junior engineers to promotion. "
            "Prior: Java microservices at a logistics firm."
        ),
        "must_address": [
            "meets the 5+ years and Go/distributed-systems requirement",
            "production on-call ownership is directly evidenced",
            "mentoring experience matches the two-junior expectation",
        ],
    },
    {
        "job_title": "Senior Backend Engineer",
        "job_description": (
            "Senior Backend Engineer. Required: 5+ years building distributed "
            "services in Go or Java, strong SQL and Postgres, production on-call. "
            "You will design and scale the order-matching service."
        ),
        "resume": (
            "Sam Applicant — Frontend Engineer. 4 years. Built React/TypeScript "
            "dashboards; some Node.js REST endpoints backed by MySQL. No Go or "
            "Java. Never carried a backend on-call pager. Eager to move into "
            "backend work."
        ),
        "must_address": [
            "falls short on the 5+ years and Go/Java distributed-systems requirement",
            "lacks production on-call ownership",
            "frontend background is a poor fit despite adjacency; note transferable skills honestly",
        ],
    },
    {
        "job_title": "Data Analyst, Commodities Desk",
        "job_description": (
            "Data Analyst for a commodities trading desk. Required: strong SQL, "
            "Python (pandas), and dashboarding (Tableau or Looker); ability to "
            "translate desk questions into analyses on grains and oilseeds "
            "pricing data. Nice to have: time-series forecasting, exposure to "
            "futures markets."
        ),
        "resume": (
            "Robin Nguyen — Analyst. 3 years at an agri-food company. Daily SQL "
            "and Python/pandas; built Tableau dashboards tracking corn and "
            "soybean basis. Ran a simple ARIMA forecast for edible-oil demand. "
            "Comfortable partnering with non-technical stakeholders."
        ),
        "must_address": [
            "SQL, Python/pandas, and Tableau all directly evidenced",
            "domain exposure to grains/oilseeds pricing is a strong plus",
            "time-series forecasting nice-to-have is partially met (ARIMA)",
        ],
    },
    {
        "job_title": "Data Analyst, Commodities Desk",
        "job_description": (
            "Data Analyst for a commodities trading desk. Required: strong SQL, "
            "Python (pandas), and dashboarding (Tableau or Looker); translate "
            "desk questions into analyses on grains and oilseeds pricing data."
        ),
        "resume": (
            "Casey Rivera — Marketing Analyst. 5 years. Expert in Excel and "
            "Google Sheets; built marketing-funnel reports. Some SQL for pulling "
            "campaign data. No Python and no exposure to commodities or trading. "
            "Strong storytelling with data."
        ),
        "must_address": [
            "SQL is only light/self-serve, not the strong SQL required",
            "no Python/pandas and no dashboarding tool from the required list",
            "no commodities/trading domain exposure; borderline-to-weak fit",
        ],
    },
    {
        "job_title": "Product Manager, Trading Platform",
        "job_description": (
            "Product Manager for an internal trading platform. Required: 4+ "
            "years PM experience shipping B2B or internal tools, comfort working "
            "with engineers and traders, strong written communication, and "
            "evidence of prioritizing a roadmap under constraints. Nice to have: "
            "finance or commodities background."
        ),
        "resume": (
            "Morgan Lee — Product Manager. 6 years. Shipped an internal risk-"
            "reporting tool used by 200 traders; ran quarterly roadmap "
            "prioritization with eng and desk stakeholders. Wrote the PRDs and "
            "release notes. Background includes 2 years at a futures brokerage."
        ),
        "must_address": [
            "exceeds the 4+ years PM requirement with relevant internal-tool shipping",
            "roadmap prioritization under constraints is directly evidenced",
            "commodities/finance nice-to-have is strongly met (futures brokerage)",
        ],
    },
    {
        "job_title": "Product Manager, Trading Platform",
        "job_description": (
            "Product Manager for an internal trading platform. Required: 4+ "
            "years PM experience shipping B2B or internal tools, comfort with "
            "engineers and traders, strong written communication, roadmap "
            "prioritization under constraints."
        ),
        "resume": (
            "Taylor Brooks — Associate PM. 2 years. Supported a consumer mobile "
            "app; owned small features under a senior PM. Good communicator but "
            "has not owned a roadmap or worked with a technical/trading audience. "
            "No finance background."
        ),
        "must_address": [
            "falls short of the 4+ years and independent roadmap-ownership bar",
            "consumer-app background is a weak fit for an internal trading tool",
            "note growth potential honestly without inflating current fit",
        ],
    },
    {
        "job_title": "Site Reliability Engineer",
        "job_description": (
            "SRE. Required: 3+ years operating Linux services in production, "
            "solid networking and observability (metrics/logs/tracing), "
            "infrastructure-as-code (Terraform), and incident response. Nice to "
            "have: Kubernetes, Go or Python for tooling."
        ),
        "resume": (
            "Jamie Park — SRE. 5 years. Ran Linux fleets, owned Prometheus/Grafana "
            "and distributed tracing, wrote Terraform for AWS, led incident "
            "response and blameless postmortems. Kubernetes in production for "
            "2 years; automation tooling in Go."
        ),
        "must_address": [
            "all required areas (Linux, observability, Terraform, incident response) evidenced",
            "both nice-to-haves (Kubernetes, Go) are met",
            "seniority comfortably exceeds the 3+ years bar",
        ],
    },
    {
        "job_title": "Site Reliability Engineer",
        "job_description": (
            "SRE. Required: 3+ years operating Linux services in production, "
            "observability, infrastructure-as-code (Terraform), incident "
            "response."
        ),
        "resume": (
            "Drew Sullivan — Junior Developer. 1 year. Wrote application features "
            "in Python; deployed via a managed PaaS, so never operated Linux "
            "servers directly. No Terraform, no on-call, limited observability "
            "exposure beyond reading dashboards."
        ),
        "must_address": [
            "below the 3+ years operations bar with no direct Linux operation",
            "missing Terraform, incident response, and hands-on observability",
            "weak fit; be specific about which requirements are unmet",
        ],
    },
    {
        "job_title": "Quantitative Researcher, Ag Commodities",
        "job_description": (
            "Quantitative Researcher for agricultural commodities. Required: "
            "graduate degree in a quantitative field or equivalent experience, "
            "strong statistics and Python, and experience building/validating "
            "predictive models on market or physical data. Nice to have: "
            "exposure to weather or crop-yield data."
        ),
        "resume": (
            "Pat Okoro — Researcher. MS in Statistics. 4 years building and "
            "backtesting demand-forecasting models in Python for a grain "
            "merchandiser; incorporated NOAA weather and USDA crop-yield data; "
            "rigorous out-of-sample validation."
        ),
        "must_address": [
            "graduate quantitative degree and strong Python/statistics are met",
            "model building and validation on physical/market data is directly evidenced",
            "weather and crop-yield nice-to-have is strongly met",
        ],
    },
    {
        "job_title": "Quantitative Researcher, Ag Commodities",
        "job_description": (
            "Quantitative Researcher for agricultural commodities. Required: "
            "graduate degree in a quantitative field or equivalent, strong "
            "statistics and Python, experience building and validating "
            "predictive models."
        ),
        "resume": (
            "Jordan Ellis — Business Intelligence Analyst. Bachelor's in "
            "Marketing. 6 years building BI dashboards and running A/B tests in "
            "a spreadsheet tool; light Python for data pulls. No predictive "
            "modeling or statistical validation experience."
        ),
        "must_address": [
            "no graduate quantitative degree and no equivalent modeling experience",
            "statistics/Python depth is below what the role requires",
            "borderline-to-weak; A/B testing is not predictive-model validation",
        ],
    },
    {
        "job_title": "Compliance Analyst",
        "job_description": (
            "Compliance Analyst. Required: 2+ years in financial or trading "
            "compliance, familiarity with trade surveillance and regulatory "
            "reporting, strong attention to detail and written documentation. "
            "Nice to have: SQL, commodities-market knowledge."
        ),
        "resume": (
            "Riley Chen — Compliance Analyst. 3 years at a commodities broker. "
            "Ran trade-surveillance alerts, prepared regulatory filings, wrote "
            "clear case memos. Uses SQL to pull trade data. Knows grains and "
            "softs markets."
        ),
        "must_address": [
            "meets the 2+ years financial/trading compliance requirement",
            "trade surveillance and regulatory reporting directly evidenced",
            "both nice-to-haves (SQL, commodities knowledge) are met",
        ],
    },
    {
        "job_title": "Compliance Analyst",
        "job_description": (
            "Compliance Analyst. Required: 2+ years in financial or trading "
            "compliance, familiarity with trade surveillance and regulatory "
            "reporting, strong attention to detail."
        ),
        "resume": (
            "Quinn Alvarez — Customer Support Lead. 4 years. Managed a support "
            "queue and wrote help-center docs; strong attention to detail and "
            "process discipline. No compliance, surveillance, or regulatory "
            "reporting experience."
        ),
        "must_address": [
            "no financial/trading compliance experience against the 2+ years bar",
            "attention-to-detail is a transferable strength but not sufficient alone",
            "weak fit; surveillance and regulatory reporting are entirely absent",
        ],
    },
]
